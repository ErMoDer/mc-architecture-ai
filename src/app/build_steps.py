# -*- coding: utf-8 -*-
"""把 32^3 体素建筑拆成 MCBlock 风格的「建造阶段」。

阶段顺序即施工顺序：
    地基 → 墙体 → 楼板/内构 → 屋顶 → 装饰

每个阶段给出「本阶段新增方块掩码」与「累计掩码」，界面据此逐步预览。
纯 numpy 实现，可单独跑：

    python -m src.app.build_steps outputs/samples/sample_xxx.npz
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np

VERTICAL_AXIS = 1

STAGE_ORDER = ("foundation", "walls", "interior", "roof", "details")
STAGE_LABELS = {
    "foundation": "地基",
    "walls": "墙体",
    "interior": "楼板/内构",
    "roof": "屋顶",
    "details": "装饰",
}
STAGE_HINTS = {
    "foundation": "找平地面，铺底座与墙脚",
    "walls": "沿轮廓砌承重墙与立柱",
    "interior": "内部楼板、隔墙与房间划分",
    "roof": "架屋顶与檐口，封顶收边",
    "details": "门窗玻璃与装饰细节",
}

# 名字里含这些词的方块算装饰（门窗/植被/小物件）
_DECOR_WORDS = (
    "glass", "pane", "leaves", "vine", "flower", "torch", "lantern",
    "candle", "pot", "carpet", "chain", "sign", "fence", "button",
    "lever", "rail", "sapling", "fern", "mushroom", "skull", "head",
    "banner", "painting", "ladder", "cobweb", "snow", "trapdoor",
    "door", "window", "bell", "candle", "coral", "azalea",
)


def _shifted_air(solid: np.ndarray, axis: int, direction: int) -> np.ndarray:
    """返回「沿 axis 的 direction 方向相邻格是空气」的掩码。"""
    air = ~solid
    out = np.zeros_like(solid)
    src = [slice(None)] * 3
    dst = [slice(None)] * 3
    if direction < 0:
        src[axis] = slice(1, None)
        dst[axis] = slice(0, -1)
    else:
        src[axis] = slice(0, -1)
        dst[axis] = slice(1, None)
    out[tuple(dst)] = air[tuple(src)]
    return out


def _horizontal_solid_count(solid: np.ndarray) -> np.ndarray:
    """水平 4 邻域实体数（0–4）。"""
    counts = np.zeros(solid.shape, dtype=np.int16)
    for axis in (0, 2):
        for direction in (-1, 1):
            air = _shifted_air(solid, axis, direction)
            counts += (~air).astype(np.int16)
    return counts


def _plate_mask(solid: np.ndarray) -> np.ndarray:
    """水平板状块：上下有空气、水平方向连续（楼板/平台），与竖直墙体区分。"""
    above_air = _shifted_air(solid, VERTICAL_AXIS, 1)
    below_air = _shifted_air(solid, VERTICAL_AXIS, -1)
    horiz = _horizontal_solid_count(solid)
    return (above_air | below_air) & (horiz >= 3)


def _neighbor_counts(solid: np.ndarray) -> np.ndarray:
    """6 邻域实体数（用于识别孤立装饰块）。"""
    counts = np.zeros(solid.shape, dtype=np.int16)
    for axis in range(3):
        for shift in (-1, 1):
            moved = np.zeros_like(solid)
            src = [slice(None)] * 3
            dst = [slice(None)] * 3
            if shift < 0:
                src[axis] = slice(1, None)
                dst[axis] = slice(0, -1)
            else:
                src[axis] = slice(0, -1)
                dst[axis] = slice(1, None)
            moved[tuple(dst)] = solid[tuple(src)]
            counts += moved.astype(np.int16)
    return counts


def _detect_roof_start(area: np.ndarray, base_y: int, top_y: int) -> int:
    """用各层面积突变找屋顶起始层（屋顶通常比墙体宽/实）。"""
    span = top_y - base_y + 1
    lo = base_y + int(round(span * 0.25))
    hi = base_y + int(round(span * 0.75))
    mid_areas = [int(area[y]) for y in range(lo, hi + 1) if area[y] > 0]
    wall_px = float(np.median(mid_areas)) if mid_areas else 0.0
    thresh = max(wall_px * 1.55, 4.0)

    lower = base_y + int(round(span * 0.45))
    start: int | None = None
    for y in range(top_y, lower - 1, -1):
        if int(area[y]) >= thresh:
            start = y
        elif start is not None:
            break
    if start is None:
        start = top_y - max(1, int(round(span * 0.2))) + 1
    return max(start, lower)


def compute_stages(
    voxels: np.ndarray,
    *,
    palette: dict[int, str] | None = None,
    max_materials: int = 3,
) -> list[dict[str, Any]]:
    """把体素按施工顺序拆分。

    返回阶段列表（仅包含非空阶段），每项字段：
    key/label/hint/mask/cumulative/count/cum_count/total/percent/materials
    """
    arr = np.asarray(voxels)
    if arr.ndim != 3:
        raise ValueError(f"需要 3D 体素数组，收到 shape={arr.shape}")
    solid = arr > 0
    total = int(solid.sum())
    if total == 0:
        return []

    axis = VERTICAL_AXIS
    other = tuple(i for i in range(3) if i != axis)
    area = solid.sum(axis=other)
    occ = np.where(solid.any(axis=other))[0]
    base_y = int(occ.min())
    top_y = int(occ.max())
    span = top_y - base_y + 1

    y_grid = np.arange(arr.shape[axis]).reshape(
        tuple(1 if i != axis else -1 for i in range(3))
    )

    found_top = base_y + max(0, int(round(span * 0.10)) - 1)
    roof_start = _detect_roof_start(np.asarray(area), base_y, top_y)

    foundation = solid & (y_grid <= found_top)
    roof = solid & ~foundation & (y_grid >= roof_start)

    plate = _plate_mask(solid)
    rest = solid & ~foundation & ~roof
    walls = rest & ~plate
    interior = rest & plate

    # 装饰：孤立块或方块名属于装饰类
    counts = _neighbor_counts(solid)
    decor = (walls | interior) & (counts <= 1)
    if palette:
        for bid, name in palette.items():
            lname = str(name).lower()
            if any(w in lname for w in _DECOR_WORDS):
                decor |= (walls | interior) & (arr == bid)
    walls &= ~decor
    interior &= ~decor

    masks: dict[str, np.ndarray] = {
        "foundation": foundation,
        "walls": walls,
        "interior": interior,
        "roof": roof,
        "details": decor,
    }

    steps: list[dict[str, Any]] = []
    cumulative = np.zeros(solid.shape, dtype=bool)
    cum_count = 0
    for key in STAGE_ORDER:
        mask = masks[key]
        count = int(mask.sum())
        if count <= 0:
            continue
        cumulative = cumulative | mask
        cum_count = int(cumulative.sum())
        ids, id_counts = np.unique(arr[mask], return_counts=True)
        order = np.argsort(id_counts)[::-1][:max_materials]
        materials = [(int(ids[i]), int(id_counts[i])) for i in order]
        steps.append(
            {
                "key": key,
                "label": STAGE_LABELS[key],
                "hint": STAGE_HINTS[key],
                "mask": mask,
                "cumulative": cumulative.copy(),
                "count": count,
                "cum_count": cum_count,
                "total": total,
                "percent": round(cum_count / total * 100.0, 1),
                "materials": materials,
            }
        )
    return steps


def stages_summary(steps: list[dict[str, Any]], *, name_of=None) -> str:
    """把阶段列表压成一行摘要，给信息面板用。"""
    if not steps:
        return "建造步骤：无数据"
    parts = []
    for st in steps:
        parts.append(f"{st['label']} {st['count']}")
    return "建造步骤：" + " · ".join(parts)


def apply_upto(voxels: np.ndarray, steps: list[dict[str, Any]], index: int) -> np.ndarray:
    """只保留前 index+1 个阶段的方块（index<0 时返回全部）。"""
    arr = np.asarray(voxels)
    if not steps or index < 0 or index >= len(steps):
        return arr.copy()
    mask = steps[index]["cumulative"]
    out = np.zeros_like(arr)
    out[mask] = arr[mask]
    return out


def _load_npz(path: Path) -> np.ndarray:
    with np.load(path) as z:
        for key in ("voxels", "arr_0", "data"):
            if key in z.files:
                return np.asarray(z[key])
        return np.asarray(z[z.files[0]])


def _main(argv: Iterable[str] | None = None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("用法: python -m src.app.build_steps <sample.npz> [更多.npz...]")
        return 2
    for raw in args:
        path = Path(raw)
        vox = _load_npz(path)
        steps = compute_stages(vox)
        print(f"\n== {path.name} shape={vox.shape} non_air={int((vox > 0).sum())}")
        for i, st in enumerate(steps, 1):
            mats = ", ".join(f"id{b}×{c}" for b, c in st["materials"])
            print(
                f"  {i}. {st['label']:<8} 新增 {st['count']:>6}  "
                f"累计 {st['cum_count']:>6} ({st['percent']:>5}%)  [{mats}]"
            )
        print("  " + stages_summary(steps))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
