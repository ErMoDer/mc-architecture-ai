# -*- coding: utf-8 -*-
"""自动装修：给空心壳建筑放置内饰。

装修层只关心「怎么摆家具」，不关心「怎么找室内」。后者由 src.app.interior 统一提供。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np

from src.app.interior import interior_air as _interior_air  # 统一室内识别入口

VERTICAL_AXIS = 1

# 家具轮换表（贴墙地板位）
_WALL_FURNITURE = (
    "minecraft:crafting_table",
    "minecraft:furnace",
    "minecraft:chest",
    "minecraft:bookshelf",
    "minecraft:barrel",
    "minecraft:anvil",
    "minecraft:smithing_table",
    "minecraft:smoker",
)
_BED = "minecraft:red_bed"
_CARPETS = ("minecraft:brown_carpet", "minecraft:green_carpet", "minecraft:black_carpet")
_WALL_LIGHTS = ("minecraft:torch", "minecraft:lantern")


def _neighbor_solid_count(solid: np.ndarray) -> np.ndarray:
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


def furnish(
    voxels: np.ndarray,
    palette: dict[int, str],
    *,
    seed: int = 42,
    max_items: int = 60,
    light_every: int = 4,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """给建筑放内饰。返回 (新体素, 放置记录)。

    记录字段：pos/role/name（role: furniture|bed|carpet|light）。
    只写空气格，不覆盖已有方块；max_items 控制总量。
    """
    arr = np.asarray(voxels).copy()
    name_to_id = {v: k for k, v in palette.items()}
    rng = np.random.default_rng(seed)

    solid = arr > 0
    interior = _interior_air(arr)
    if not interior.any():
        return arr, []

    neigh = _neighbor_solid_count(solid)
    # 地板：室内空气，正下方是实体
    below_solid = np.zeros_like(solid)
    below_solid[:, 1:, :] = solid[:, :-1, :]  # y 索引向上：下方 = y-1
    floor = interior & below_solid
    # 贴墙地板：水平方向与实体相邻
    horiz = np.zeros(solid.shape, dtype=np.int16)
    for axis in (0, 2):
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
            horiz += moved.astype(np.int16)

    wall_floor = floor & (horiz >= 1)
    open_floor = floor & (horiz == 0)

    placements: list[dict[str, Any]] = []
    placed = np.zeros_like(solid)  # 本函数放置的方块
    counts = {"furniture": 0, "bed": 0, "carpet": 0, "light": 0}
    quota = {"furniture": max(4, max_items // 2), "bed": 3,
             "carpet": max(6, max_items // 3), "light": max(6, max_items // 3)}

    def _put(x: int, y: int, z: int, name: str, role: str) -> bool:
        bid = name_to_id.get(name)
        if bid is None or placed[x, y, z] or arr[x, y, z] != 0:
            return False
        if counts[role] >= quota[role]:
            return False
        arr[x, y, z] = bid
        placed[x, y, z] = True
        counts[role] += 1
        placements.append({"pos": (int(x), int(y), int(z)), "role": role, "name": name})
        return True

    # 1) 角落放床（水平两方向都贴墙）
    corner = wall_floor & (horiz >= 2)
    corner_pos = np.argwhere(corner)
    if len(corner_pos):
        rng.shuffle(corner_pos)
        for x, y, z in corner_pos:
            if counts["bed"] >= quota["bed"]:
                break
            if placed[max(0, x - 2): x + 3, y, max(0, z - 2): z + 3].any():
                continue
            _put(x, y, z, _BED, "bed")

    # 2) 墙上光源：室内空气、脚下非实体（挂墙），按间隔放
    wall_air = interior & ~below_solid & (horiz >= 1)
    light_pos = np.argwhere(wall_air)
    if len(light_pos):
        rng.shuffle(light_pos)
        li = 0
        for x, y, z in light_pos:
            if counts["light"] >= quota["light"]:
                break
            if placed[max(0, x - light_every): x + light_every + 1,
                      max(0, y - 2): y + 3,
                      max(0, z - light_every): z + light_every + 1].any():
                continue
            if _put(x, y, z, _WALL_LIGHTS[li % len(_WALL_LIGHTS)], "light"):
                li += 1

    # 3) 贴墙功能方块（轮换），间隔 >=2 避免拥挤
    wall_pos = np.argwhere(wall_floor)
    if len(wall_pos):
        rng.shuffle(wall_pos)
        fi = 0
        for x, y, z in wall_pos:
            if counts["furniture"] >= quota["furniture"]:
                break
            if placed[max(0, x - 2): x + 3, y, max(0, z - 2): z + 3].any():
                continue
            if _put(x, y, z, _WALL_FURNITURE[fi % len(_WALL_FURNITURE)], "furniture"):
                fi += 1

    # 4) 中央地毯：开阔地板稀疏铺
    open_pos = np.argwhere(open_floor)
    if len(open_pos):
        rng.shuffle(open_pos)
        ci = 0
        step = max(1, len(open_pos) // quota["carpet"])
        for x, y, z in open_pos[::step]:
            if counts["carpet"] >= quota["carpet"]:
                break
            if _put(x, y, z, _CARPETS[ci % len(_CARPETS)], "carpet"):
                ci += 1

    return arr, placements


def furnish_summary(placements: list[dict[str, Any]]) -> str:
    if not placements:
        return "无可装修室内空间"
    by_role: dict[str, int] = {}
    for p in placements:
        by_role[p["role"]] = by_role.get(p["role"], 0) + 1
    names = {"furniture": "家具", "bed": "床", "carpet": "地毯", "light": "光源"}
    parts = [f"{names.get(r, r)}×{c}" for r, c in sorted(by_role.items())]
    return f"共 {len(placements)} 件：" + " · ".join(parts)


def _load_npz(path: Path) -> np.ndarray:
    with np.load(path) as z:
        for key in ("voxels", "arr_0", "data"):
            if key in z.files:
                return np.asarray(z[key])
        return np.asarray(z[z.files[0]])


def _main(argv: Iterable[str] | None = None) -> int:
    import json
    import sys

    root = Path(__file__).resolve().parents[2]
    palette = {int(k): v for k, v in json.loads((root / "data/palette.json").read_text(encoding="utf-8")).items()}

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("用法: python -m src.app.furnish <sample.npz> [更多.npz...]")
        return 2
    for raw in args:
        path = Path(raw)
        vox = _load_npz(path)
        out, placed = furnish(vox, palette)
        diff = int((out != vox).sum())
        print(f"{path.name}: {furnish_summary(placed)}（体素变化 {diff} 格）")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
