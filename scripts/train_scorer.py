"""训练建筑合理性评分器：判断 32³ 体素是否是“像样的建筑”。

正例 = mixed_v3 清洗后的真实建筑；负例 = 对正例做破坏（实心化/打散/翻转/加噪/压扁）。
产出一个小 3D CNN，可给生成候选打分，自动筛掉不合理的形态。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_N_FAMILY = 8


def _family(name: str) -> int:
    n = name.split(":", 1)[-1]
    if any(k in n for k in ("planks", "log", "_wood", "bamboo", "stripped")):
        return 0
    if any(k in n for k in ("glass", "pane")):
        return 2
    if any(k in n for k in ("iron", "copper", "gold", "netherite", "chain", "anvil")):
        return 3
    if any(k in n for k in ("leaves", "grass", "hay", "flower", "vine", "moss")):
        return 4
    if any(k in n for k in ("water", "ice", "kelp", "seagrass")):
        return 5
    if any(k in n for k in ("torch", "lantern", "glowstone", "sea_lantern", "shroomlight", "froglight")):
        return 6
    if any(k in n for k in ("stone", "cobble", "brick", "deepslate", "andesite",
                            "granite", "diorite", "basalt", "blackstone", "obsidian",
                            "sand", "dirt", "gravel", "terracotta", "concrete", "quartz",
                            "tuff", "calcite", "prismarine", "purpur", "netherrack")):
        return 1
    return 7


def encode(vox: np.ndarray, fam_table: np.ndarray) -> np.ndarray:
    """4 通道：实心 / 材质族 / 高度 / 邻接度。"""
    solid = (vox > 0).astype(np.float32)
    ch = np.zeros((4,) + vox.shape, dtype=np.float32)
    ch[0] = solid
    ch[1] = np.where(solid > 0, fam_table[np.clip(vox, 0, len(fam_table) - 1)] / _N_FAMILY, 0)
    ys = np.arange(vox.shape[1], dtype=np.float32)[None, :, None] / max(vox.shape[1] - 1, 1)
    ch[2] = solid * ys
    nb = np.zeros_like(solid)
    for ax in (0, 1, 2):
        for d in (-1, 1):
            nb += np.roll(solid, d, axis=ax)
    ch[3] = solid * (nb / 6.0)
    return ch


def corrupt(vox: np.ndarray, kind: str, rng: np.random.Generator) -> np.ndarray:
    v = vox.copy()
    solid = v > 0
    if not solid.any():
        return v
    if kind == "solid_blob":
        idx = np.where(solid.any(axis=(1, 2)))[0]
        jdx = np.where(solid.any(axis=(0, 2)))[0]
        kdx = np.where(solid.any(axis=(0, 1)))[0]
        v[idx[0]:idx[-1] + 1, jdx[0]:jdx[-1] + 1, kdx[0]:kdx[-1] + 1] = 1
    elif kind == "scatter":
        n = int(solid.sum())
        v[:] = 0
        flat = rng.integers(0, v.size, size=n)
        v.reshape(-1)[flat] = 1
    elif kind == "invert":
        lo, hi = int(v.min()), int(v.max())
        v = np.where(solid, 0, max(hi, 1)).astype(vox.dtype)
    elif kind == "noise":
        k = max(1, int(v.size * 0.05))
        pts = rng.choice(v.size, size=k, replace=False)
        v.reshape(-1)[pts] = 1
    elif kind == "squash":
        idx = np.where(solid.any(axis=(1, 2)))[0]
        v[idx[0]:idx[-1] + 1, :, :] = 0
        v[idx[0]:idx[0] + max(1, (idx[-1] - idx[0] + 1) // 3), :, :] = 1
    elif kind == "shuffle_axis":
        v = np.transpose(v, (0, 2, 1))
    elif kind == "punch":
        k = rng.integers(2, 5)
        for _ in range(int(k)):
            c = tuple(int(rng.integers(0, d)) for d in v.shape)
            v[c[0] - 3:c[0] + 4, c[1] - 3:c[1] + 4, c[2] - 3:c[2] + 4] = 0
    return v


class Scorer(nn.Module):
    def __init__(self, in_ch: int = 4, base: int = 24):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv3d(in_ch, base, 3, padding=1), nn.GroupNorm(4, base), nn.SiLU(),
            nn.Conv3d(base, base, 3, padding=1), nn.GroupNorm(4, base), nn.SiLU(),
            nn.MaxPool3d(2),
            nn.Conv3d(base, base * 2, 3, padding=1), nn.GroupNorm(8, base * 2), nn.SiLU(),
            nn.Conv3d(base * 2, base * 2, 3, padding=1), nn.GroupNorm(8, base * 2), nn.SiLU(),
            nn.MaxPool3d(2),
            nn.Conv3d(base * 2, base * 4, 3, padding=1), nn.GroupNorm(8, base * 4), nn.SiLU(),
            nn.AdaptiveAvgPool3d(1),
        )
        self.fc = nn.Linear(base * 4, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.net(x).flatten(1)).squeeze(1)


class ScorerSet(torch.utils.data.Dataset):
    KINDS = ("solid_blob", "scatter", "invert", "noise", "squash", "shuffle_axis", "punch")

    def __init__(self, files: list[pathlib.Path], fam_table: np.ndarray, *, neg_per: int = 2):
        self.files = files
        self.fam = fam_table
        self.neg_per = neg_per

    def __len__(self) -> int:
        return len(self.files) * (1 + self.neg_per)

    def __getitem__(self, i: int):
        fi = i % len(self.files)
        kind_idx = i // len(self.files)
        rng = np.random.default_rng(1_000_003 * i + 7)
        f = np.load(self.files[fi])
        vox = (f["voxels"] if "voxels" in f else f[f.files[0]]).astype(np.int32)
        if kind_idx == 0:
            return torch.from_numpy(encode(vox, self.fam)), torch.tensor(1.0)
        kind = self.KINDS[int(rng.integers(0, len(self.KINDS)))]
        return torch.from_numpy(encode(corrupt(vox, kind, rng), self.fam)), torch.tensor(0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/processed/mixed_v3")
    ap.add_argument("--palette", default="data/palette.json")
    ap.add_argument("--out", required=True, help="评分器 checkpoint 输出路径")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--neg-per", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()

    raw_pal = json.load(open(ROOT / args.palette, encoding="utf-8"))
    n_classes = max(int(k) for k in raw_pal) + 1
    fam_table = np.zeros(n_classes, dtype=np.float32)
    for k, v in raw_pal.items():
        fam_table[int(k)] = _family(str(v))
    # 空气也算 7（会被 solid 通道屏蔽）

    files = sorted((ROOT / args.data).glob("*.npz"))
    random.Random(0).shuffle(files)
    n_val = max(1, int(len(files) * 0.1))
    tr, va = files[n_val:], files[:n_val]
    ds_tr = ScorerSet(tr, fam_table, neg_per=args.neg_per)
    ds_va = ScorerSet(va, fam_table, neg_per=args.neg_per)
    dl_tr = torch.utils.data.DataLoader(ds_tr, batch_size=args.batch, shuffle=True, num_workers=4, drop_last=True)
    dl_va = torch.utils.data.DataLoader(ds_va, batch_size=args.batch, shuffle=False, num_workers=4)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = Scorer().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    print(f"train={len(ds_tr)} val={len(ds_va)} classes={n_classes} device={device}")

    best = 0.0
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for ep in range(1, args.epochs + 1):
        model.train()
        tot = cor = 0
        for x, y in dl_tr:
            x, y = x.to(device), y.to(device)
            opt.zero_grad(set_to_none=True)
            logit = model(x)
            loss = F.binary_cross_entropy_with_logits(logit, y)
            loss.backward()
            opt.step()
            tot += y.numel()
            cor += ((logit > 0) == (y > 0.5)).sum().item()
        model.eval()
        vtot = vcor = 0
        vloss = 0.0
        with torch.no_grad():
            for x, y in dl_va:
                x, y = x.to(device), y.to(device)
                logit = model(x)
                vloss += float(F.binary_cross_entropy_with_logits(logit, y).item()) * y.numel()
                vtot += y.numel()
                vcor += ((logit > 0) == (y > 0.5)).sum().item()
        acc = cor / max(tot, 1)
        vacc = vcor / max(vtot, 1)
        print(f"epoch {ep}: train_acc={acc:.4f} val_acc={vacc:.4f} val_loss={vloss/max(vtot,1):.4f}")
        if vacc >= best:
            best = vacc
            torch.save({"model": model.state_dict(), "n_classes": n_classes, "family_table": fam_table,
                        "val_acc": vacc, "epoch": ep}, out)
            print(f"  saved -> {out} (val_acc={vacc:.4f})")
    print("done. best val_acc", best)


if __name__ == "__main__":
    main()
