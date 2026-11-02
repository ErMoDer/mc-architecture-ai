"""条件体素 VAE：style + terrain embedding 拼到 latent 再 decode。"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .vae import ConvBlock, VoxelVAE


class ConditionalVoxelVAE(VoxelVAE):
    """在 VoxelVAE 上增加可选 style/terrain 条件（解码侧注入，编码器不变）。"""

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
        super().__init__(
            num_classes=num_classes,
            latent_dim=latent_dim,
            base_channels=base_channels,
            size=size,
        )
        self.num_styles = num_styles
        self.num_terrains = num_terrains
        self.cond_emb_dim = cond_emb_dim
        self.style_emb = nn.Embedding(num_styles, cond_emb_dim)
        self.terrain_emb = nn.Embedding(num_terrains, cond_emb_dim)
        self.cond_to_z = nn.Sequential(
            nn.Linear(latent_dim + 2 * cond_emb_dim, latent_dim),
            nn.SiLU(),
            nn.Linear(latent_dim, latent_dim),
        )
        # 覆盖父类的 fc_dec 输入：仍吃 latent_dim（条件先融进 z）
        # 已在 super 里建好 fc_dec

    def fuse_condition(
        self,
        z: torch.Tensor,
        style_id: torch.Tensor,
        terrain_id: torch.Tensor,
    ) -> torch.Tensor:
        s = self.style_emb(style_id.long())
        t = self.terrain_emb(terrain_id.long())
        return self.cond_to_z(torch.cat([z, s, t], dim=-1))

    def forward(
        self,
        x: torch.Tensor,
        style_id: torch.Tensor,
        terrain_id: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        z_c = self.fuse_condition(z, style_id, terrain_id)
        logits = self.decode(z_c)
        return logits, mu, logvar

    def loss(
        self,
        x: torch.Tensor,
        style_id: torch.Tensor,
        terrain_id: torch.Tensor,
        beta: float = 0.01,
        class_weights: torch.Tensor | None = None,
        ignore_air: bool = False,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        logits, mu, logvar = self.forward(x, style_id, terrain_id)
        if ignore_air:
            # 材质阶段：损失只在实心体素上算，空气完全不参与
            recon = F.cross_entropy(logits, x, weight=class_weights, ignore_index=0)
        else:
            recon = F.cross_entropy(logits, x, weight=class_weights)
        kl = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
        total = recon + beta * kl
        with torch.no_grad():
            pred = logits.argmax(dim=1)
            solid = x > 0
            if ignore_air:
                # 只关心实心位置的命中率；空气位置输出无监督，不统计
                acc = (pred[solid] == x[solid]).float().mean().item() if solid.any() else 0.0
                pred_solid = acc  # 占位，避免塌陷保护误触发（材质阶段不做该判定）
            else:
                acc = (pred == x).float().mean().item()
                pred_solid = (pred > 0).float().mean().item()
            solid_acc = (
                (pred[solid] == x[solid]).float().mean().item() if solid.any() else 0.0
            )
        stats = {
            "loss": float(total.item()),
            "recon": float(recon.item()),
            "kl": float(kl.item()),
            "acc": acc,
            "solid_acc": solid_acc,
            "pred_solid": pred_solid,
        }
        return total, stats

    @torch.no_grad()
    def sample(
        self,
        n: int,
        device: torch.device,
        temperature: float = 1.0,
        style_id: int | torch.Tensor = 0,
        terrain_id: int | torch.Tensor = 0,
    ) -> torch.Tensor:
        z = torch.randn(n, self.latent_dim, device=device) * temperature
        if isinstance(style_id, int):
            style_id = torch.full((n,), style_id, device=device, dtype=torch.long)
        else:
            style_id = style_id.to(device=device, dtype=torch.long)
            if style_id.ndim == 0:
                style_id = style_id.expand(n)
        if isinstance(terrain_id, int):
            terrain_id = torch.full((n,), terrain_id, device=device, dtype=torch.long)
        else:
            terrain_id = terrain_id.to(device=device, dtype=torch.long)
            if terrain_id.ndim == 0:
                terrain_id = terrain_id.expand(n)
        z_c = self.fuse_condition(z, style_id, terrain_id)
        logits = self.decode(z_c)
        return logits.argmax(dim=1)
