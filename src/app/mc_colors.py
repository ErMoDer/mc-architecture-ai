"""Minecraft 方块名 → 近似 RGBA（纯色，不捆绑原版贴图）。"""
from __future__ import annotations

from functools import lru_cache

# 短名（无 minecraft: 前缀）→ (r, g, b, a)，0–1
_BLOCK_RGBA: dict[str, tuple[float, float, float, float]] = {
    # 石 / 地
    "air": (0.0, 0.0, 0.0, 0.0),
    "stone": (0.49, 0.49, 0.49, 1.0),
    "cobblestone": (0.50, 0.50, 0.50, 1.0),
    "infested_cobblestone": (0.50, 0.50, 0.50, 1.0),
    "andesite": (0.53, 0.53, 0.55, 1.0),
    "stone_bricks": (0.48, 0.48, 0.48, 1.0),
    "stone_brick_stairs": (0.48, 0.48, 0.48, 1.0),
    "stone_brick_slab": (0.48, 0.48, 0.48, 1.0),
    "stone_brick_wall": (0.48, 0.48, 0.48, 1.0),
    "stone_slab": (0.49, 0.49, 0.49, 1.0),
    "smooth_stone_slab": (0.62, 0.62, 0.62, 1.0),
    "stone_pressure_plate": (0.49, 0.49, 0.49, 1.0),
    "cobblestone_stairs": (0.50, 0.50, 0.50, 1.0),
    "cobblestone_slab": (0.50, 0.50, 0.50, 1.0),
    "cobblestone_wall": (0.50, 0.50, 0.50, 1.0),
    "andesite_stairs": (0.53, 0.53, 0.55, 1.0),
    "andesite_wall": (0.53, 0.53, 0.55, 1.0),
    "deepslate_brick_wall": (0.28, 0.28, 0.30, 1.0),
    "mud_bricks": (0.54, 0.40, 0.30, 1.0),
    "mud_brick_stairs": (0.54, 0.40, 0.30, 1.0),
    "bricks": (0.59, 0.33, 0.25, 1.0),
    "dirt": (0.53, 0.37, 0.22, 1.0),
    "dirt_path": (0.58, 0.45, 0.28, 1.0),
    "grass_block": (0.36, 0.62, 0.28, 1.0),
    "short_grass": (0.40, 0.70, 0.30, 0.85),
    "sand": (0.86, 0.80, 0.60, 1.0),
    "sandstone": (0.85, 0.78, 0.55, 1.0),
    "cut_sandstone": (0.85, 0.78, 0.55, 1.0),
    "chiseled_sandstone": (0.82, 0.75, 0.52, 1.0),
    "smooth_sandstone": (0.88, 0.82, 0.60, 1.0),
    "sandstone_stairs": (0.85, 0.78, 0.55, 1.0),
    "sandstone_wall": (0.85, 0.78, 0.55, 1.0),
    "cut_sandstone_slab": (0.85, 0.78, 0.55, 1.0),
    "smooth_sandstone_stairs": (0.88, 0.82, 0.60, 1.0),
    "smooth_sandstone_slab": (0.88, 0.82, 0.60, 1.0),
    # 橡木
    "oak_planks": (0.68, 0.54, 0.30, 1.0),
    "oak_log": (0.45, 0.33, 0.18, 1.0),
    "stripped_oak_log": (0.70, 0.56, 0.32, 1.0),
    "oak_stairs": (0.68, 0.54, 0.30, 1.0),
    "oak_slab": (0.68, 0.54, 0.30, 1.0),
    "oak_fence": (0.65, 0.50, 0.28, 1.0),
    "oak_fence_gate": (0.65, 0.50, 0.28, 1.0),
    "oak_door": (0.60, 0.45, 0.22, 1.0),
    "oak_trapdoor": (0.60, 0.45, 0.22, 1.0),
    "oak_sign": (0.68, 0.54, 0.30, 1.0),
    "oak_leaves": (0.25, 0.55, 0.18, 0.92),
    # 云杉 / 深色橡木 / 白桦
    "spruce_planks": (0.45, 0.30, 0.16, 1.0),
    "spruce_log": (0.28, 0.18, 0.10, 1.0),
    "spruce_wood": (0.28, 0.18, 0.10, 1.0),
    "spruce_stairs": (0.45, 0.30, 0.16, 1.0),
    "spruce_slab": (0.45, 0.30, 0.16, 1.0),
    "spruce_fence": (0.42, 0.28, 0.14, 1.0),
    "spruce_fence_gate": (0.42, 0.28, 0.14, 1.0),
    "spruce_door": (0.40, 0.26, 0.12, 1.0),
    "spruce_trapdoor": (0.40, 0.26, 0.12, 1.0),
    "spruce_button": (0.45, 0.30, 0.16, 1.0),
    "spruce_wall_sign": (0.45, 0.30, 0.16, 1.0),
    "dark_oak_planks": (0.30, 0.20, 0.10, 1.0),
    "dark_oak_stairs": (0.30, 0.20, 0.10, 1.0),
    "dark_oak_slab": (0.30, 0.20, 0.10, 1.0),
    "dark_oak_fence": (0.28, 0.18, 0.09, 1.0),
    "dark_oak_fence_gate": (0.28, 0.18, 0.09, 1.0),
    "dark_oak_door": (0.28, 0.18, 0.09, 1.0),
    "dark_oak_trapdoor": (0.28, 0.18, 0.09, 1.0),
    "dark_oak_button": (0.30, 0.20, 0.10, 1.0),
    "dark_oak_pressure_plate": (0.30, 0.20, 0.10, 1.0),
    "dark_oak_wall_sign": (0.30, 0.20, 0.10, 1.0),
    "dark_oak_hanging_sign": (0.30, 0.20, 0.10, 1.0),
    "birch_stairs": (0.82, 0.75, 0.52, 1.0),
    "birch_slab": (0.82, 0.75, 0.52, 1.0),
    "birch_trapdoor": (0.78, 0.72, 0.50, 1.0),
    "birch_sign": (0.82, 0.75, 0.52, 1.0),
    "birch_leaves": (0.35, 0.62, 0.25, 0.90),
    "jungle_leaves": (0.22, 0.52, 0.12, 0.90),
    "cherry_leaves": (0.92, 0.70, 0.82, 0.90),
    "cherry_wood": (0.42, 0.28, 0.28, 1.0),
    # 玻璃（半透明）
    "glass": (0.75, 0.88, 0.95, 0.35),
    "glass_pane": (0.75, 0.88, 0.95, 0.30),
    "lime_stained_glass": (0.45, 0.85, 0.20, 0.40),
    "pink_stained_glass": (0.95, 0.55, 0.70, 0.40),
    "green_stained_glass": (0.25, 0.65, 0.25, 0.40),
    "white_stained_glass": (0.95, 0.95, 0.95, 0.35),
    "red_stained_glass": (0.85, 0.20, 0.20, 0.40),
    "black_stained_glass": (0.15, 0.15, 0.15, 0.45),
    "gray_stained_glass": (0.45, 0.45, 0.45, 0.40),
    # 混凝土 / 羊毛 / 陶瓦
    "white_concrete": (0.90, 0.90, 0.90, 1.0),
    "white_concrete_powder": (0.92, 0.92, 0.90, 1.0),
    "black_concrete": (0.08, 0.10, 0.12, 1.0),
    "gray_concrete": (0.35, 0.35, 0.38, 1.0),
    "light_gray_concrete": (0.60, 0.60, 0.62, 1.0),
    "lime_concrete": (0.45, 0.78, 0.12, 1.0),
    "lime_concrete_powder": (0.55, 0.85, 0.25, 1.0),
    "pink_concrete": (0.90, 0.55, 0.68, 1.0),
    "pink_concrete_powder": (0.92, 0.65, 0.75, 1.0),
    "white_wool": (0.95, 0.95, 0.95, 1.0),
    "yellow_wool": (0.95, 0.85, 0.20, 1.0),
    "gray_wool": (0.40, 0.40, 0.42, 1.0),
    "lime_wool": (0.50, 0.82, 0.15, 1.0),
    "pink_wool": (0.95, 0.65, 0.75, 1.0),
    "white_terracotta": (0.82, 0.78, 0.72, 1.0),
    "orange_terracotta": (0.72, 0.40, 0.18, 1.0),
    "cyan_terracotta": (0.35, 0.48, 0.48, 1.0),
    "pink_terracotta": (0.72, 0.45, 0.48, 1.0),
    "black_carpet": (0.10, 0.10, 0.12, 1.0),
    "brown_carpet": (0.48, 0.32, 0.18, 1.0),
    "lime_carpet": (0.50, 0.82, 0.15, 1.0),
    "green_carpet": (0.30, 0.55, 0.20, 1.0),
    # 海晶 / 石英 / 冰
    "prismarine": (0.35, 0.62, 0.55, 1.0),
    "prismarine_bricks": (0.38, 0.68, 0.58, 1.0),
    "prismarine_stairs": (0.35, 0.62, 0.55, 1.0),
    "prismarine_slab": (0.35, 0.62, 0.55, 1.0),
    "prismarine_wall": (0.35, 0.62, 0.55, 1.0),
    "prismarine_brick_stairs": (0.38, 0.68, 0.58, 1.0),
    "prismarine_brick_slab": (0.38, 0.68, 0.58, 1.0),
    "quartz_stairs": (0.92, 0.90, 0.86, 1.0),
    "packed_ice": (0.55, 0.75, 0.95, 0.95),
    # 菌 / 诡异 / 南瓜灯
    "brown_mushroom_block": (0.58, 0.42, 0.30, 1.0),
    "warped_stairs": (0.20, 0.55, 0.50, 1.0),
    "warped_trapdoor": (0.18, 0.50, 0.48, 1.0),
    "warped_fence": (0.18, 0.50, 0.48, 1.0),
    "shroomlight": (0.95, 0.70, 0.35, 1.0),
    "glowstone": (0.95, 0.82, 0.45, 1.0),
    "jack_o_lantern": (0.90, 0.55, 0.10, 1.0),
    "lantern": (0.70, 0.55, 0.25, 1.0),
    "campfire": (0.55, 0.30, 0.12, 1.0),
    "torch": (0.95, 0.80, 0.30, 1.0),
    "wall_torch": (0.95, 0.80, 0.30, 1.0),
    "end_rod": (0.90, 0.90, 0.85, 1.0),
    # 功能方块
    "chest": (0.55, 0.35, 0.12, 1.0),
    "barrel": (0.50, 0.35, 0.18, 1.0),
    "crafting_table": (0.55, 0.38, 0.18, 1.0),
    "furnace": (0.42, 0.42, 0.42, 1.0),
    "blast_furnace": (0.35, 0.35, 0.38, 1.0),
    "smoker": (0.40, 0.35, 0.30, 1.0),
    "cauldron": (0.35, 0.35, 0.38, 1.0),
    "water_cauldron": (0.30, 0.40, 0.70, 1.0),
    "composter": (0.40, 0.28, 0.12, 1.0),
    "bookshelf": (0.55, 0.40, 0.22, 1.0),
    "jukebox": (0.45, 0.28, 0.18, 1.0),
    "anvil": (0.40, 0.40, 0.42, 1.0),
    "grindstone": (0.50, 0.50, 0.52, 1.0),
    "stonecutter": (0.48, 0.48, 0.50, 1.0),
    "smithing_table": (0.25, 0.20, 0.18, 1.0),
    "brewing_stand": (0.55, 0.45, 0.25, 1.0),
    "bell": (0.90, 0.75, 0.20, 1.0),
    "chain": (0.35, 0.35, 0.38, 1.0),
    "ladder": (0.55, 0.40, 0.20, 1.0),
    "iron_bars": (0.55, 0.55, 0.58, 0.85),
    "nether_brick_fence": (0.30, 0.15, 0.18, 1.0),
    "cobweb": (0.85, 0.85, 0.85, 0.45),
    "tripwire_hook": (0.55, 0.45, 0.30, 1.0),
    "decorated_pot": (0.55, 0.35, 0.28, 1.0),
    "amethyst_cluster": (0.65, 0.40, 0.85, 0.90),
    "sea_pickle": (0.35, 0.70, 0.40, 1.0),
    # 花 / 盆栽
    "poppy": (0.85, 0.15, 0.15, 1.0),
    "blue_orchid": (0.25, 0.45, 0.85, 1.0),
    "lilac": (0.75, 0.55, 0.80, 1.0),
    "peony": (0.90, 0.55, 0.70, 1.0),
    "rose_bush": (0.80, 0.15, 0.20, 1.0),
    "potted_cactus": (0.25, 0.55, 0.20, 1.0),
    "potted_blue_orchid": (0.25, 0.45, 0.85, 1.0),
    "potted_birch_sapling": (0.35, 0.60, 0.25, 1.0),
    "potted_crimson_roots": (0.70, 0.20, 0.25, 1.0),
    "potted_fern": (0.30, 0.55, 0.25, 1.0),
    "potted_lily_of_the_valley": (0.90, 0.90, 0.90, 1.0),
    "potted_orange_tulip": (0.90, 0.45, 0.15, 1.0),
    "potted_red_tulip": (0.85, 0.20, 0.20, 1.0),
    "black_bed": (0.12, 0.12, 0.14, 1.0),
    "black_wall_banner": (0.10, 0.10, 0.12, 1.0),
}

_DEFAULT = (0.55, 0.48, 0.40, 1.0)  # 未知：灰棕


def short_name(full: str) -> str:
    if ":" in full:
        return full.split(":", 1)[1]
    return full


@lru_cache(maxsize=512)
def rgba_for_name(full_or_short: str) -> tuple[float, float, float, float]:
    """Prefer texture average; else palette/heuristics."""
    try:
        from src.app.mc_textures import average_rgba as _tex_avg

        sampled = _tex_avg(full_or_short)
        if sampled is not None:
            return sampled
    except Exception:
        pass
    return _rgba_for_name_palette(full_or_short)


@lru_cache(maxsize=512)
def _rgba_for_name_palette(full_or_short: str) -> tuple[float, float, float, float]:
    """Palette + keyword fallback (original body)."""
    name = short_name(full_or_short).lower()
    if name in _BLOCK_RGBA:
        return _BLOCK_RGBA[name]
    # 关键字回退
    rules: list[tuple[str, tuple[float, float, float, float]]] = [
        ("glass", (0.75, 0.88, 0.95, 0.35)),
        ("leaves", (0.28, 0.55, 0.20, 0.90)),
        ("planks", (0.65, 0.50, 0.28, 1.0)),
        ("log", (0.40, 0.28, 0.14, 1.0)),
        ("wood", (0.40, 0.28, 0.14, 1.0)),
        ("stairs", (0.55, 0.48, 0.40, 1.0)),
        ("slab", (0.55, 0.48, 0.40, 1.0)),
        ("fence", (0.50, 0.40, 0.25, 1.0)),
        ("door", (0.50, 0.38, 0.20, 1.0)),
        ("trapdoor", (0.50, 0.38, 0.20, 1.0)),
        ("concrete", (0.55, 0.55, 0.55, 1.0)),
        ("wool", (0.75, 0.75, 0.75, 1.0)),
        ("carpet", (0.70, 0.70, 0.70, 1.0)),
        ("terracotta", (0.65, 0.45, 0.35, 1.0)),
        ("sandstone", (0.85, 0.78, 0.55, 1.0)),
        ("brick", (0.55, 0.32, 0.25, 1.0)),
        ("stone", (0.50, 0.50, 0.50, 1.0)),
        ("dirt", (0.53, 0.37, 0.22, 1.0)),
        ("grass", (0.36, 0.62, 0.28, 1.0)),
        ("ore", (0.45, 0.45, 0.48, 1.0)),
        ("copper", (0.70, 0.45, 0.30, 1.0)),
        ("iron", (0.75, 0.75, 0.78, 1.0)),
        ("gold", (0.90, 0.75, 0.20, 1.0)),
        ("water", (0.25, 0.40, 0.85, 0.55)),
        ("lava", (0.90, 0.35, 0.08, 0.95)),
    ]
    for key, color in rules:
        if key in name:
            return color
    return _DEFAULT


def rgba_for_id(block_id: int, palette: dict[int, str]) -> tuple[float, float, float, float]:
    if block_id <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    name = palette.get(int(block_id), f"unknown:{block_id}")
    return rgba_for_name(name)


def clear_color_caches() -> None:
    rgba_for_name.cache_clear()
    _rgba_for_name_palette.cache_clear()
    try:
        from src.app.mc_textures import clear_caches

        clear_caches()
    except Exception:
        pass
