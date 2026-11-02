# -*- coding: utf-8 -*-
"""CraftGPT TransformerBlock2Vec — reconstructed for inference from DeepSpeed weights.

Official GitHub ships no inference code; architecture is reverse-engineered from
mp_rank_00_model_states.pt + model card (MIT). Chunk limit: 16x8x16 → 144-d.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

VOCAB_SIZE = 1099
D_MODEL = 144
N_LAYERS = 6
N_HEADS = 8
FFN_HIDDEN = 576
MAX_X, MAX_Y, MAX_Z = 16, 8, 16
ROPE_DIM_PER_AXIS = 24  # 24 pairs * 2 = 48 dims/axis; 3 axes = 144
SEP_ID, PAD_ID, MASK_ID = 1096, 1097, 1098
DEFAULT_CKPT = "checkpoints/transformer_block2vec/mp_rank_00_model_states.pt"


class SwiGLU(nn.Module):
    def __init__(self, d_model: int = D_MODEL, hidden: int = FFN_HIDDEN) -> None:
        super().__init__()
        self.linear1 = nn.Linear(d_model, hidden)
        self.linear2 = nn.Linear(d_model, hidden)
        self.linear_out = nn.Linear(hidden, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear_out(F.silu(self.linear1(x)) * self.linear2(x))


class Rotary3D(nn.Module):
    """Buffered 3D RoPE: each axis owns 48 dims (24 cos/sin pairs)."""

    def __init__(self) -> None:
        super().__init__()
        self.register_buffer("cos_x", torch.zeros(MAX_X, ROPE_DIM_PER_AXIS), persistent=True)
        self.register_buffer("sin_x", torch.zeros(MAX_X, ROPE_DIM_PER_AXIS), persistent=True)
        self.register_buffer("cos_y", torch.zeros(MAX_Y, ROPE_DIM_PER_AXIS), persistent=True)
        self.register_buffer("sin_y", torch.zeros(MAX_Y, ROPE_DIM_PER_AXIS), persistent=True)
        self.register_buffer("cos_z", torch.zeros(MAX_Z, ROPE_DIM_PER_AXIS), persistent=True)
        self.register_buffer("sin_z", torch.zeros(MAX_Z, ROPE_DIM_PER_AXIS), persistent=True)

    def forward(self, q: torch.Tensor, k: torch.Tensor, pos_xyz: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Apply RoPE to q,k of shape (B,T,D) using integer positions (B,T,3)."""
        return apply_rope3d(q, self, pos_xyz), apply_rope3d(k, self, pos_xyz)


def _rotate_pairs(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    # x: (..., 48), cos/sin: (..., 24)
    x1 = x[..., 0::2]
    x2 = x[..., 1::2]
    out1 = x1 * cos - x2 * sin
    out2 = x1 * sin + x2 * cos
    out = torch.stack((out1, out2), dim=-1).reshape_as(x)
    return out


def apply_rope3d(x: torch.Tensor, rope: Rotary3D, pos_xyz: torch.Tensor) -> torch.Tensor:
    """x (B,T,144); pos_xyz (B,T,3) long."""
    B, T, D = x.shape
    assert D == D_MODEL
    px = pos_xyz[..., 0].clamp(0, MAX_X - 1)
    py = pos_xyz[..., 1].clamp(0, MAX_Y - 1)
    pz = pos_xyz[..., 2].clamp(0, MAX_Z - 1)
    # gather (B,T,24)
    cos_x = rope.cos_x[px]
    sin_x = rope.sin_x[px]
    cos_y = rope.cos_y[py]
    sin_y = rope.sin_y[py]
    cos_z = rope.cos_z[pz]
    sin_z = rope.sin_z[pz]
    x0 = _rotate_pairs(x[..., 0:48], cos_x, sin_x)
    x1 = _rotate_pairs(x[..., 48:96], cos_y, sin_y)
    x2 = _rotate_pairs(x[..., 96:144], cos_z, sin_z)
    return torch.cat([x0, x1, x2], dim=-1)


class EncoderLayer(nn.Module):
    def __init__(self, d_model: int = D_MODEL, n_heads: int = N_HEADS, dropout: float = 0.0) -> None:
        super().__init__()
        assert d_model % n_heads == 0
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_model, d_model)
        self.v_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.linear1 = SwiGLU(d_model, FFN_HIDDEN)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        rope: Rotary3D,
        pos_xyz: torch.Tensor,
        key_padding_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        # Pre-LN attention
        h = self.norm1(x)
        q = self.q_proj(h)
        k = self.k_proj(h)
        v = self.v_proj(h)
        q, k = rope(q, k, pos_xyz)
        B, T, _ = h.shape
        q = q.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.n_heads, self.head_dim).transpose(1, 2)
        # SDPA expects (B,H,T,Dh); mask True = keep in newer API via attn_mask
        attn_mask = None
        if key_padding_mask is not None:
            # key_padding_mask: (B,T) True where PAD → block
            # build (B,1,1,T) additive mask
            blocked = key_padding_mask
            attn_mask = torch.zeros(B, 1, 1, T, device=x.device, dtype=q.dtype)
            attn_mask = attn_mask.masked_fill(blocked[:, None, None, :], torch.finfo(q.dtype).min)
        try:
            attn = F.scaled_dot_product_attention(q, k, v, attn_mask=attn_mask, dropout_p=0.0)
        except TypeError:
            scale = self.head_dim ** -0.5
            scores = torch.matmul(q, k.transpose(-2, -1)) * scale
            if attn_mask is not None:
                scores = scores + attn_mask
            attn = torch.matmul(scores.softmax(dim=-1), v)
        attn = attn.transpose(1, 2).contiguous().view(B, T, -1)
        x = x + self.dropout(self.out_proj(attn))
        x = x + self.dropout(self.linear1(self.norm2(x)))
        return x


class TransformerBlock2Vec(nn.Module):
    def __init__(self, vocab_size: int = VOCAB_SIZE, d_model: int = D_MODEL, n_layers: int = N_LAYERS) -> None:
        super().__init__()
        self.token_embeddings = nn.Embedding(vocab_size, d_model, padding_idx=PAD_ID)
        self.rope = Rotary3D()
        self.transformer_encoder_layers = nn.ModuleList([EncoderLayer(d_model) for _ in range(n_layers)])
        self.fc = nn.Linear(d_model, vocab_size)
        self.d_model = d_model

    def forward_hidden(
        self,
        tokens: torch.Tensor,
        pos_xyz: torch.Tensor,
        key_padding_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """tokens (B,T) long; pos_xyz (B,T,3); returns (B,T,D)."""
        x = self.token_embeddings(tokens)
        for layer in self.transformer_encoder_layers:
            x = layer(x, self.rope, pos_xyz, key_padding_mask)
        return x

    def embed_pooled(
        self,
        tokens: torch.Tensor,
        pos_xyz: torch.Tensor,
        key_padding_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Mean-pool non-pad tokens → (B,D) L2-normalized."""
        h = self.forward_hidden(tokens, pos_xyz, key_padding_mask)
        if key_padding_mask is None:
            mask = tokens != PAD_ID
        else:
            mask = ~key_padding_mask
        mask_f = mask.unsqueeze(-1).to(h.dtype)
        summed = (h * mask_f).sum(dim=1)
        denom = mask_f.sum(dim=1).clamp(min=1.0)
        pooled = summed / denom
        return F.normalize(pooled, dim=-1)


def _strip_module_prefix(state: dict[str, Any]) -> dict[str, torch.Tensor]:
    out = {}
    for k, v in state.items():
        if not torch.is_tensor(v):
            continue
        nk = k[7:] if k.startswith("module.") else k
        out[nk] = v
    return out


def load_block2vec(
    checkpoint: str | Path | None = None,
    *,
    device: str | torch.device | None = None,
    dtype: torch.dtype | None = None,
) -> TransformerBlock2Vec:
    root = Path(__file__).resolve().parents[2]
    ckpt_path = Path(checkpoint) if checkpoint else root / DEFAULT_CKPT
    if not ckpt_path.is_absolute():
        ckpt_path = root / ckpt_path
    if not ckpt_path.exists():
        raise FileNotFoundError(ckpt_path)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if dtype is None:
        dtype = torch.float16 if str(device).startswith("cuda") else torch.float32

    raw = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    if isinstance(raw, dict) and "module" in raw:
        state = _strip_module_prefix(raw["module"])
    elif isinstance(raw, dict) and any(torch.is_tensor(v) for v in raw.values()):
        state = _strip_module_prefix(raw)
    else:
        raise ValueError("unrecognized checkpoint format: %s" % ckpt_path)

    model = TransformerBlock2Vec()
    missing, unexpected = model.load_state_dict(state, strict=False)
    # buffers may already match; report soft
    if unexpected:
        raise RuntimeError("unexpected keys: %s" % unexpected[:8])
    # missing should be empty if architecture matches
    critical = [k for k in missing if not k.startswith("rope.")]
    if critical:
        raise RuntimeError("missing critical keys: %s" % critical[:12])

    model.to(device=device, dtype=dtype)
    # embeddings stay usable; LayerNorm/Linear in dtype
    model.eval()
    return model
