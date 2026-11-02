"""把建筑数据集统一锚定到地面：最低实心层对齐到 y=0（沿高度轴平移）。

体素约定 voxels[x, y, z]：轴 1 是高度（与 mc_render 的 origin=[x,z,y] 一致）。

用法：
  python scripts/anchor_dataset.py --src data/processed/mixed_v3 --dst data/processed/mixed_v4
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

HEIGHT_AXIS = 1


def ground_offset(vox: np.ndarray) -> int:
    """返回最低实心层的高度索引；全空返回 0。"""
    solid = vox > 0
    if not solid.any():
        return 0
    layers = np.where(solid.any(axis=(0, 2)))[0]
    return int(layers[0])


def anchor(vox: np.ndarray) -> tuple[np.ndarray, int]:
    """把最低实心层滚到 y=0。下方各层按定义为空，滚出后落在顶部，不丢方块。"""
    y0 = ground_offset(vox)
    if y0 == 0:
        return vox, 0
    return np.roll(vox, -y0, axis=HEIGHT_AXIS), y0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--overwrite", action="store_true", help="目标已存在时清空重建")
    args = ap.parse_args()

    src = Path(args.src)
    if not src.is_absolute():
        src = Path(__file__).resolve().parents[1] / src
    dst = Path(args.dst)
    if not dst.is_absolute():
        dst = Path(__file__).resolve().parents[1] / dst

    files = sorted(p for p in src.glob("*.npz") if not p.name.startswith("_"))
    if not files:
        raise SystemExit(f"未找到数据：{src}\\*.npz")

    if dst.exists() and any(dst.glob("*.npz")):
        if not args.overwrite:
            raise SystemExit(f"目标已存在数据：{dst}（加 --overwrite 重建）")
        for p in dst.glob("*.npz"):
            p.unlink()

    dst.mkdir(parents=True, exist_ok=True)

    total = 0
    already = 0
    shifted = 0
    offsets: list[int] = []
    vols_before: list[int] = []
    vols_after: list[int] = []

    for path in files:
        vox = np.load(path)["voxels"].astype(np.int16)
        out, y0 = anchor(vox)
        total += 1
        if y0 == 0:
            already += 1
        else:
            shifted += 1
        offsets.append(y0)
        vols_before.append(int((vox > 0).sum()))
        vols_after.append(int((out > 0).sum()))
        np.savez_compressed(dst / path.name, voxels=out)

    labels = src / "labels.json"
    if labels.exists():
        shutil.copy2(labels, dst / labels.name)

    offs = np.asarray(offsets)
    vb = np.asarray(vols_before)
    va = np.asarray(vols_after)
    print(f"src={src}")
    print(f"dst={dst}")
    print(f"samples={total}  already_grounded={already} ({already/total:.1%})  shifted={shifted}")
    print(
        f"offset(y0): min={offs.min()} med={int(np.median(offs))} p90={int(np.percentile(offs, 90))} max={offs.max()}"
    )
    print(f"solid voxels before: med={int(np.median(vb))}  after: med={int(np.median(va))}")
    print(f"volume changed samples={int((vb != va).sum())} (应为 0，平移不丢方块)")

    # 锚定后复核：每个样本最低实心层都应落在 y=0
    bad = 0
    for path in sorted(dst.glob("*.npz")):
        v = np.load(path)["voxels"]
        if (v > 0).any() and ground_offset(v) != 0:
            bad += 1
    print(f"verify: 未落地样本={bad}")


if __name__ == "__main__":
    main()
