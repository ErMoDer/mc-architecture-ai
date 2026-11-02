# -*- coding: utf-8 -*-
"""风格迁移：把已有建筑的材质整体换成另一种风格，结构不动。

按方块「角色」映射（原木/木板/楼梯/台阶/石墙/玻璃/装饰），
每种风格给出对应材质档案。装饰、家具、红石、植物保持不变。

    python -m src.app.restyle <sample.npz> --to modern
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np

# 角色类别（按方块名模式匹配，顺序即优先级）
_ROLE_PATTERNS: list[tuple[str, str]] = [
    ("log", r"(_log|_wood)$"),
    ("planks", r"_planks$"),
    ("stairs", r"_stairs$"),
    ("slab", r"_slab$"),
    ("glass", r"(^glass$|_glass$|glass_pane|stained_glass)"),
    ("stone_wall", r"^(stone|stone_bricks|cobblestone|mossy_cobblestone|bricks|mud_bricks|"
                    r"andesite|sandstone|cut_sandstone|smooth_sandstone|prismarine|prismarine_bricks|"
                    r"deepslate_bricks|red_nether_bricks|netherrack)$"),
    ("concrete", r"^.*_concrete$"),
    ("terracotta", r"^.*_terracotta$"),
    ("wool", r"^.*_wool$"),
    ("fence", r"_fence$"),
    ("wall", r"_wall$"),
]

# 风格档案：角色 → 目标方块（palette 里必须存在才生效）
STYLE_PROFILES: dict[str, dict[str, str]] = {
    "medieval": {
        "log": "minecraft:oak_log",
        "planks": "minecraft:oak_planks",
        "stairs": "minecraft:oak_stairs",
        "slab": "minecraft:oak_slab",
        "stone_wall": "minecraft:stone_bricks",
        "concrete": "minecraft:cobblestone",
        "terracotta": "minecraft:bricks",
        "wool": "minecraft:brown_wool",
        "fence": "minecraft:oak_fence",
        "wall": "minecraft:cobblestone_wall",
    },
    "modern": {
        "log": "minecraft:stripped_spruce_log",
        "planks": "minecraft:dark_oak_planks",
        "stairs": "minecraft:quartz_stairs",
        "slab": "minecraft:smooth_stone_slab",
        "stone_wall": "minecraft:white_concrete",
        "concrete": "minecraft:white_concrete",
        "terracotta": "minecraft:light_gray_concrete",
        "wool": "minecraft:white_wool",
        "fence": "minecraft:iron_bars",
        "wall": "minecraft:andesite_wall",
    },
    "chinese": {
        "log": "minecraft:spruce_log",
        "planks": "minecraft:dark_oak_planks",
        "stairs": "minecraft:dark_oak_stairs",
        "slab": "minecraft:dark_oak_slab",
        "stone_wall": "minecraft:bricks",
        "concrete": "minecraft:bricks",
        "terracotta": "minecraft:red_nether_bricks",
        "wool": "minecraft:red_wool",
        "fence": "minecraft:dark_oak_fence",
        "wall": "minecraft:stone_brick_wall",
    },
    "desert": {
        "log": "minecraft:stripped_oak_log",
        "planks": "minecraft:oak_planks",
        "stairs": "minecraft:sandstone_stairs",
        "slab": "minecraft:sandstone_slab",
        "stone_wall": "minecraft:sandstone",
        "concrete": "minecraft:sandstone",
        "terracotta": "minecraft:orange_terracotta",
        "wool": "minecraft:yellow_wool",
        "fence": "minecraft:sandstone_wall",
        "wall": "minecraft:sandstone_wall",
    },
    "rustic": {
        "log": "minecraft:spruce_log",
        "planks": "minecraft:spruce_planks",
        "stairs": "minecraft:spruce_stairs",
        "slab": "minecraft:spruce_slab",
        "stone_wall": "minecraft:mossy_cobblestone",
        "concrete": "minecraft:cobblestone",
        "terracotta": "minecraft:bricks",
        "wool": "minecraft:green_wool",
        "fence": "minecraft:spruce_fence",
        "wall": "minecraft:andesite_wall",
    },
}

STYLE_LABELS = {
    "medieval": "中世纪",
    "modern": "现代",
    "chinese": "中式",
    "desert": "沙漠",
    "rustic": "乡村",
}


def _role_of(name: str) -> str | None:
    short = name.split(":", 1)[-1]
    for role, pat in _ROLE_PATTERNS:
        if re.search(pat, short):
            return role
    return None


def build_style_map(palette: dict[int, str], target_style: str) -> dict[int, int]:
    """返回 {旧方块 id: 新方块 id}，只含 palette 里双方块都存在的映射。"""
    profile = STYLE_PROFILES.get(target_style)
    if profile is None:
        raise ValueError(f"未知风格：{target_style}（可选：{list(STYLE_PROFILES)}）")
    name_to_id = {v: k for k, v in palette.items()}
    out: dict[int, int] = {}
    for bid, name in palette.items():
        if bid <= 0:
            continue
        role = _role_of(name)
        if role is None or role == "glass":
            continue
        target_name = profile.get(role)
        if not target_name:
            continue
        tid = name_to_id.get(target_name)
        if tid is None or tid == bid:
            continue
        out[bid] = tid
    return out


def restyle(
    voxels: np.ndarray,
    palette: dict[int, str],
    target_style: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    """整体替换材质。返回 (新体素, 统计 {changed, map_size, style})。"""
    mapping = build_style_map(palette, target_style)
    arr = np.asarray(voxels).copy()
    changed = 0
    for old_id, new_id in mapping.items():
        mask = arr == old_id
        n = int(mask.sum())
        if n:
            arr[mask] = new_id
            changed += n
    stats = {"changed": changed, "map_size": len(mapping), "style": target_style,
             "style_label": STYLE_LABELS.get(target_style, target_style)}
    return arr, stats


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
    target = "modern"
    if "--to" in args:
        i = args.index("--to")
        target = args[i + 1]
        del args[i: i + 2]
    if not args:
        print("用法: python -m src.app.restyle <sample.npz> [--to modern|medieval|chinese|desert|rustic]")
        return 2
    for raw in args:
        path = Path(raw)
        vox = _load_npz(path)
        out, stats = restyle(vox, palette, target)
        diff = int((out != vox).sum())
        print(f"{path.name} → {stats['style_label']}：替换 {diff} 格（映射规则 {stats['map_size']} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
