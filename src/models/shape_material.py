"""形状条件材质 VAE：材质模型吃 occupancy 作为输入通道与多尺度 skip。

设计动机
--------
原材质模型只吃 (z, style, terrain)，从未看到空间形状，只能给整栋建筑刷同一种材质。
这里把 occupancy（实心掩码）当作额外输入通道送进编码器，并在解码器每一级
上采样后重新拼上对应分辨率的掩码 —— 既是条件，也是 skip，避免细节被 128 维
全局隐变量抹平。空气由 occupancy 决定，材质只负责"实心处刷什么"。
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .vae import ConvBlock


def _resize_mask(mask: torch.Tensor, n: int) -> torch.Tensor:
    if mask.shape[-1] == n and mask.shape[-2] == n and mask.shape[-3] == n:
        return mask
    return F.interpolate(mask, size=(n, n, n), mode="nearest")


class ShapeMaterialVAE(nn.Module):
    """输入材质体素 + occupancy 掩码，输出实心处的材质类别 logits。"""

    def __init__(
        self,
        num_classes: int,
        num_styles: int,
        num_terrains: int,
        latent_dim: int = 128,
        base_channels: int = 32,
        size: int = 32,
        cond_emb_dim: int = 32,
    ):
        super().__init__()
        if size % 16 != 0:
            raise ValueError("size 必须能被 16 整除（例如 32/64）")
        self.num_classes = num_classes
        self.latent_dim = latent_dim
        self.size = size
        self.num_styles = num_styles
        self.num_terrains = num_terrains
        self.cond_emb_dim = cond_emb_dim
        c = base_channels
        self._c = c
        self._lat = size // 16

        self.embed = nn.Embedding(num_classes, c)
        # 输入通道 = 材质 embedding(c) + 形状掩码(1)
        self.enc = nn.Sequential(
            ConvBlock(c + 1, c, stride=2),          # /2
            ConvBlock(c, c * 2, stride=2),          # /4
            ConvBlock(c * 2, c * 4, stride=2),      # /8
            ConvBlock(c * 4, c * 4, stride=2),      # /16
        )
        flat = c * 4 * self._lat ** 3
        self.fc_mu = nn.Linear(flat, latent_dim)
        self.fc_logvar = nn.Linear(flat, latent_dim)
        self.fc_dec = nn.Linear(latent_dim, flat)

        # 解码：每级上采样后拼回该分辨率的 occupancy 掩码
        self.up1 = ConvBlock(c * 4 + 1, c * 4)  # /16
        self.up2 = ConvBlock(c * 4 + 1, c * 2)  # /8
        self.up3 = ConvBlock(c * 2 + 1, c)      # /4
        self.up4 = ConvBlock(c + 1, c)          # /2
        self.up5 = ConvBlock(c + 1, c)          # 原尺寸
        self.out = nn.Conv3d(c, num_classes, 1)

        self.style_emb = nn.Embedding(num_styles, cond_emb_dim)
        self.terrain_emb = nn.Embedding(num_terrains, cond_emb_dim)
        self.cond_to_z = nn.Sequential(
            nn.Linear(latent_dim + 2 * cond_emb_dim, latent_dim),
            nn.SiLU(),
            nn.Linear(latent_dim, latent_dim),
        )

    # ---- 条件 ----
    def fuse_condition(
        self,
        z: torch.Tensor,
        style_id: torch.Tensor,
        terrain_id: torch.Tensor,
    ) -> torch.Tensor:
        s = self.style_emb(style_id.long())
        t = self.terrain_emb(terrain_id.long())
        return self.cond_to_z(torch.cat([z, s, t], dim=-1))

    # ---- 编码 / 解码 ----
    def encode(self, x: torch.Tensor, occ: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: [B, D, H, W] long；occ: [B, 1, D, H, W] float
        h = self.embed(x).permute(0, 4, 1, 2, 3).contiguous()
        h = self.enc(torch.cat([h, occ], dim=1))
        h = h.flatten(1)
        return self.fc_mu(h), self.fc_logvar(h)

    @staticmethod
    def reparameterize(mu: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z: torch.Tensor, occ: torch.Tensor) -> torch.Tensor:
        b = z.size(0)
        lat = self._lat
        h = self.fc_dec(z).view(b, self._c * 4, lat, lat, lat)
        h = self.up1(torch.cat([h, _resize_mask(occ, lat)], dim=1))
        for blk, n in (
            (self.up2, lat * 2),
            (self.up3, lat * 4),
            (self.up4, lat * 8),
            (self.up5, lat * 16),
        ):
            h = F.interpolate(h, scale_factor=2, mode="trilinear", align_corners=False)
            h = blk(torch.cat([h, _resize_mask(occ, n)], dim=1))
        return self.out(h)

    def forward(
        self,
        x: torch.Tensor,
        occ: torch.Tensor,
        style_id: torch.Tensor,
        terrain_id: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        mu, logvar = self.encode(x, occ)
        z = self.reparameterize(mu, logvar)
        z_c = self.fuse_condition(z, style_id, terrain_id)
        logits = self.decode(z_c, occ)
        return logits, mu, logvar

    def loss(
        self,
        x: torch.Tensor,
        occ: torch.Tensor,
        style_id: torch.Tensor,
        terrain_id: torch.Tensor,
        beta: float = 0.01,
        class_weights: torch.Tensor | None = None,
        ignore_air: bool = True,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        logits, mu, logvar = self.forward(x, occ, style_id, terrain_id)
        recon = F.cross_entropy(
            logits, x, weight=class_weights, ignore_index=0 if ignore_air else -100
        )
        kl = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
        total = recon + beta * kl
        with torch.no_grad():
            pred = logits.argmax(dim=1)
            solid = x > 0
            acc = (pred[solid] == x[solid]).float().mean().item() if solid.any() else 0.0
            pred_solid = acc  # 占位：材质阶段不做实心比例塌陷判定
        stats = {
            "loss": float(total.item()),
            "recon": float(recon.item()),
            "kl": float(kl.item()),
            "acc": acc,
            "solid_acc": acc,
            "pred_solid": pred_solid,
        }
        return total, stats

    @torch.no_grad()
    def sample(
        self,
        occ: torch.Tensor,
        style_id: int | torch.Tensor = 0,
        terrain_id: int | torch.Tensor = 0,
        temperature: float = 1.0,
    ) -> torch.Tensor:
        b = occ.size(0)
        z = torch.randn(b, self.latent_dim, device=occ.device) * temperature
        if isinstance(style_id, int):
            style_id = torch.full((b,), style_id, device=occ.device, dtype=torch.long)
        if isinstance(terrain_id, int):
            terrain_id = torch.full((b,), terrain_id, device=occ.device, dtype=torch.long)
        z_c = self.fuse_condition(z, style_id, terrain_id)
        logits = self.decode(z_c, occ)
        logits[:, 0] = -1e9  # 材质不产出空气
        return logits.argmax(dim=1)
