from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, stride: int = 1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv3d(in_ch, out_ch, 3, stride=stride, padding=1),
            nn.GroupNorm(8, out_ch),
            nn.SiLU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class VoxelVAE(nn.Module):
    """分类体素 VAE：输入方块 ID，输出每体素类别 logits。"""

    def __init__(
        self,
        num_classes: int,
        latent_dim: int = 256,
        base_channels: int = 32,
        size: int = 64,
    ):
        super().__init__()
        if size % 16 != 0:
            raise ValueError("size 必须能被 16 整除（例如 32/64）")
        self.num_classes = num_classes
        self.latent_dim = latent_dim
        self.size = size
        c = base_channels

        self.embed = nn.Embedding(num_classes, c)
        self.enc = nn.Sequential(
            ConvBlock(c, c, stride=2),      # /2
            ConvBlock(c, c * 2, stride=2),  # /4
            ConvBlock(c * 2, c * 4, stride=2),  # /8
            ConvBlock(c * 4, c * 4, stride=2),  # /16
        )
        flat = c * 4 * (size // 16) ** 3
        self.fc_mu = nn.Linear(flat, latent_dim)
        self.fc_logvar = nn.Linear(flat, latent_dim)
        self.fc_dec = nn.Linear(latent_dim, flat)

        self.dec = nn.Sequential(
            nn.Upsample(scale_factor=2, mode="trilinear", align_corners=False),
            ConvBlock(c * 4, c * 4),
            nn.Upsample(scale_factor=2, mode="trilinear", align_corners=False),
            ConvBlock(c * 4, c * 2),
            nn.Upsample(scale_factor=2, mode="trilinear", align_corners=False),
            ConvBlock(c * 2, c),
            nn.Upsample(scale_factor=2, mode="trilinear", align_corners=False),
            ConvBlock(c, c),
            nn.Conv3d(c, num_classes, 1),
        )
        self._flat_shape = (c * 4, size // 16, size // 16, size // 16)

    def encode(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: [B, D, H, W] long
        h = self.embed(x).permute(0, 4, 1, 2, 3).contiguous()
        h = self.enc(h)
        h = h.flatten(1)
        return self.fc_mu(h), self.fc_logvar(h)

    @staticmethod
    def reparameterize(mu: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        h = self.fc_dec(z)
        h = h.view(z.size(0), *self._flat_shape)
        return self.dec(h)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        logits = self.decode(z)
        return logits, mu, logvar

    def loss(
        self,
        x: torch.Tensor,
        beta: float = 0.01,
        class_weights: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        logits, mu, logvar = self.forward(x)
        # air 占绝大多数时，压低 air 权重，避免模型学会「全输出空气」
        recon = F.cross_entropy(logits, x, weight=class_weights)
        kl = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
        total = recon + beta * kl
        with torch.no_grad():
            pred = logits.argmax(dim=1)
            acc = (pred == x).float().mean().item()
            solid = x > 0
            solid_acc = (pred[solid] == x[solid]).float().mean().item() if solid.any() else 0.0
        stats = {
            "loss": float(total.item()),
            "recon": float(recon.item()),
            "kl": float(kl.item()),
            "acc": acc,
            "solid_acc": solid_acc,
        }
        return total, stats

    @torch.no_grad()
    def sample(self, n: int, device: torch.device, temperature: float = 1.0) -> torch.Tensor:
        z = torch.randn(n, self.latent_dim, device=device) * temperature
        logits = self.decode(z)
        return logits.argmax(dim=1)