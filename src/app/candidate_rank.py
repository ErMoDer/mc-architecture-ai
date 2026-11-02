"""候选建筑自动打分与择优。

一次生成多张候选，按结构完整性/对称性/体积感打分，挑出最好的那张。

    python -m src.app.candidate_rank <目录或npz> [...]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from src.app.morph import largest_component_ratio


def _symmetry(solid: np.ndarray, axis: int) -> float:
    """沿某轴镜像后的重合率（只在与建筑等长的范围内比较）。"""
    nz = np.argwhere(solid)
    if nz.size == 0:
        return 0.0
    lo = nz[:, axis].min()
    hi = nz[:, axis].max()
    sub = np.take(solid, range(lo, hi + 1), axis=axis)
    flipped = np.flip(sub, axis=axis)
    denom = float(sub.sum() + flipped.sum())
    if denom == 0:
        return 0.0
    return float(2.0 * np.logical_and(sub, flipped).sum() / denom)


def _main_component_ratio(solid: np.ndarray) -> float:
    return float(largest_component_ratio(solid))


def _floating_ratio(solid: np.ndarray) -> float:
    """悬空方块占比：下方与四周都没有实体（近似孤岛）。"""
    pad = np.pad(solid, 1, mode="constant", constant_values=False)
    core = pad[1:-1, 1:-1, 1:-1]
    below = pad[:-2, 1:-1, 1:-1]
    up = pad[2:, 1:-1, 1:-1]
    sides = (
        pad[1:-1, :-2, 1:-1] | pad[1:-1, 2:, 1:-1]
        | pad[1:-1, 1:-1, :-2] | pad[1:-1, 1:-1, 2:]
    )
    lonely = core & ~(below | up | sides)
    n = int(core.sum())
    return float(lonely.sum() / n) if n else 0.0


def score_voxels(voxels: np.ndarray) -> dict:
    """0-100 综合分，附各分项。"""
    solid = np.asarray(voxels) > 0
    n = int(solid.sum())
    if n == 0:
        return {"total": 0.0, "fill": 0, "symmetry": 0, "height": 0,
                "solid_ratio": 0, "floating": 0, "non_air": 0}

    nz = np.argwhere(solid)
    lo = nz.min(axis=0)
    hi = nz.max(axis=0)
    dims = (hi - lo + 1).astype(float)
    bbox_vol = float(dims.prod())
    fill = n / bbox_vol

    # 填充率：空心壳建筑经验区间 0.12~0.30，越接近 0.22 越好
    fill_score = max(0.0, 1.0 - abs(fill - 0.22) / 0.22) * 100.0

    sym = 0.5 * (_symmetry(solid, 0) + _symmetry(solid, 2)) * 100.0

    # 体量：高度与最大占地边长的比值，目标 0.7~1.5
    foot = max(dims[0], dims[2])
    ratio = float(dims[1]) / max(1.0, foot)
    height_score = max(0.0, 1.0 - abs(ratio - 1.05) / 1.05) * 100.0

    conn = _main_component_ratio(solid) * 100.0
    floating = _floating_ratio(solid)
    conn_score = conn * max(0.0, 1.0 - floating * 3.0)

    total = (
        fill_score * 0.22
        + sym * 0.26
        + height_score * 0.18
        + conn_score * 0.34
    )
    return {
        "total": round(total, 2),
        "fill": round(fill_score, 1),
        "symmetry": round(sym, 1),
        "height": round(height_score, 1),
        "solid_ratio": round(conn_score, 1),
        "floating": round(floating, 3),
        "non_air": n,
    }


def _load_voxels(path: str | Path) -> np.ndarray:
    path = Path(path)
    if path.is_dir():
        raise ValueError("需要 npz 文件")
    with np.load(path) as z:
        for key in ("voxels", "arr_0", "data"):
            if key in z:
                return z[key].astype(np.int16)
    raise KeyError(f"{path} 里没有 voxels")


def rank_files(paths: list[str | Path]) -> list[dict]:
    """对一批 npz 打分，按总分降序。"""
    out: list[dict] = []
    for p in paths:
        try:
            sc = score_voxels(_load_voxels(p))
        except Exception:  # noqa: BLE001
            continue
        sc["path"] = str(p)
        out.append(sc)
    out.sort(key=lambda d: d["total"], reverse=True)
    return out


def rank_results(results: list[dict]) -> list[dict]:
    """对 generate_samples 返回的条目（含 npz_path）打分排序。"""
    out: list[dict] = []
    for item in results:
        try:
            sc = score_voxels(_load_voxels(item["npz_path"]))
        except Exception:  # noqa: BLE001
            continue
        merged = dict(item)
        merged.update(sc)
        out.append(merged)
    out.sort(key=lambda d: d["total"], reverse=True)
    return out


def _main(argv: list[str] | None = None) -> int:  # pragma: no cover - 手动调试
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("用法: python -m src.app.candidate_rank <a.npz> [b.npz ...]")
        return 2
    for row in rank_files(args):
        print(
            f"{row['total']:6.2f}  fill={row['fill']:5.1f} sym={row['symmetry']:5.1f} "
            f"h={row['height']:5.1f} conn={row['solid_ratio']:5.1f} "
            f"float={row['floating']:.3f} n={row['non_air']:5d}  {Path(row['path']).name}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
