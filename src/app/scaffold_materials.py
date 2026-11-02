# -*- coding: utf-8 -*-
"""Role-based material palettes for scaffold / look_harden.

Roles: foundation, wall, roof, floor, accent, window_frame.
Glass / door stay resolved separately by look_harden.
"""
from __future__ import annotations

from typing import Any

# Style-aware fallbacks (short names). Order = preference.
STYLE_ROLE_FALLBACKS: dict[str, dict[str, tuple[str, ...]]] = {
    "medieval": {
        "foundation": ("cobblestone", "mossy_cobblestone", "stone_bricks", "stone"),
        "wall": ("stone_bricks", "cobblestone", "oak_planks", "bricks"),
        "roof": ("dark_oak_planks", "spruce_planks", "stone_bricks", "deepslate_bricks"),
        "floor": ("oak_planks", "spruce_planks", "smooth_stone"),
        "accent": ("oak_log", "spruce_log", "dark_oak_log", "stripped_oak_log"),
        "window_frame": ("oak_log", "spruce_log", "stone_bricks"),
        "load_bearing": ("oak_log", "spruce_log", "stone_bricks"),
    },
    "european": {
        "foundation": ("stone_bricks", "cobblestone", "bricks", "stone"),
        "wall": ("bricks", "stone_bricks", "oak_planks", "smooth_stone"),
        "roof": ("dark_oak_planks", "spruce_planks", "bricks", "stone_bricks"),
        "floor": ("oak_planks", "spruce_planks", "smooth_stone"),
        "accent": ("oak_log", "spruce_log", "stone_bricks"),
        "window_frame": ("oak_log", "stone_bricks", "spruce_log"),
        "load_bearing": ("oak_log", "spruce_log", "stone_bricks"),
    },
    "chinese": {
        "foundation": ("stone_bricks", "stone", "cobblestone", "smooth_stone"),
        "wall": ("dark_oak_planks", "spruce_planks", "oak_planks", "white_wool"),
        "roof": ("dark_oak_planks", "spruce_planks", "red_wool", "stone_bricks"),
        "floor": ("oak_planks", "smooth_stone", "spruce_planks"),
        "accent": ("dark_oak_log", "spruce_log", "cherry_log", "gold_block"),
        "window_frame": ("dark_oak_log", "spruce_log", "stone_bricks"),
        "load_bearing": ("dark_oak_log", "spruce_log", "stone_bricks"),
    },
    "japanese": {
        "foundation": ("stone", "cobblestone", "stone_bricks", "smooth_stone"),
        "wall": ("spruce_planks", "white_wool", "oak_planks", "bamboo_planks"),
        "roof": ("dark_oak_planks", "spruce_planks", "stone_bricks"),
        "floor": ("oak_planks", "smooth_stone", "bamboo_planks"),
        "accent": ("dark_oak_log", "spruce_log", "stripped_spruce_log"),
        "window_frame": ("dark_oak_log", "spruce_log"),
        "load_bearing": ("dark_oak_log", "spruce_log", "stripped_spruce_log"),
    },
    "modern": {
        "foundation": ("gray_concrete", "smooth_stone", "stone", "black_concrete"),
        "wall": ("white_concrete", "light_gray_concrete", "quartz_block", "smooth_quartz"),
        "roof": ("gray_concrete", "black_concrete", "light_gray_concrete", "iron_block"),
        "floor": ("smooth_stone", "white_concrete", "gray_concrete", "quartz_block"),
        "accent": ("iron_block", "quartz_block", "black_concrete", "glass"),
        "window_frame": ("iron_block", "gray_concrete", "white_concrete"),
        "load_bearing": ("iron_block", "quartz_block", "gray_concrete"),
    },
    "rustic": {
        "foundation": ("cobblestone", "stone", "mossy_cobblestone", "bricks"),
        "wall": ("oak_planks", "spruce_planks", "stripped_oak_log", "oak_log"),
        "roof": ("spruce_planks", "dark_oak_planks", "oak_planks", "cobblestone"),
        "floor": ("oak_planks", "spruce_planks", "smooth_stone"),
        "accent": ("oak_log", "spruce_log", "stripped_oak_log", "hay_block"),
        "window_frame": ("oak_log", "spruce_log", "cobblestone"),
        "load_bearing": ("oak_log", "spruce_log", "stripped_oak_log"),
    },
    "fantasy": {
        "foundation": ("stone_bricks", "cobblestone", "deepslate_bricks", "blackstone"),
        "wall": ("stone_bricks", "purpur_block", "dark_oak_planks", "spruce_planks"),
        "roof": ("dark_oak_planks", "deepslate_tiles", "purpur_block", "spruce_planks"),
        "floor": ("spruce_planks", "dark_oak_planks", "smooth_stone"),
        "accent": ("amethyst_block", "purpur_block", "purple_wool", "dark_oak_log"),
        "window_frame": ("dark_oak_log", "stone_bricks", "purpur_pillar"),
        "load_bearing": ("dark_oak_log", "stone_bricks", "spruce_log"),
    },
    "industrial": {
        "foundation": ("cobbled_deepslate", "stone_bricks", "gray_concrete", "iron_block"),
        "wall": ("gray_concrete", "stone_bricks", "iron_block", "polished_deepslate"),
        "roof": ("black_concrete", "iron_block", "gray_concrete", "deepslate_bricks"),
        "floor": ("smooth_stone", "gray_concrete", "iron_block"),
        "accent": ("iron_block", "copper_block", "polished_deepslate", "stone_bricks"),
        "window_frame": ("iron_block", "gray_concrete", "polished_deepslate"),
        "load_bearing": ("iron_block", "polished_deepslate", "stone_bricks"),
    },
    "desert": {
        "foundation": ("sandstone", "smooth_sandstone", "cut_sandstone", "terracotta"),
        "wall": ("sandstone", "cut_sandstone", "terracotta", "smooth_sandstone"),
        "roof": ("smooth_sandstone", "red_sandstone", "terracotta", "sandstone"),
        "floor": ("smooth_sandstone", "sandstone", "terracotta"),
        "accent": ("terracotta", "cut_sandstone", "red_sandstone"),
        "window_frame": ("cut_sandstone", "terracotta"),
        "load_bearing": ("cut_sandstone", "terracotta", "sandstone"),
    },
    "western": {
        "foundation": ("cobblestone", "stone", "oak_planks"),
        "wall": ("oak_planks", "spruce_planks", "stripped_oak_log"),
        "roof": ("spruce_planks", "dark_oak_planks", "oak_planks"),
        "floor": ("oak_planks", "spruce_planks"),
        "accent": ("oak_log", "hay_block", "stripped_oak_log"),
        "window_frame": ("oak_log", "spruce_log"),
        "load_bearing": ("oak_log", "spruce_log", "stripped_oak_log"),
    },
    "scifi": {
        "foundation": ("iron_block", "gray_concrete", "quartz_block"),
        "wall": ("white_concrete", "quartz_block", "iron_block", "cyan_concrete"),
        "roof": ("iron_block", "black_concrete", "gray_concrete"),
        "floor": ("quartz_block", "smooth_stone", "white_concrete"),
        "accent": ("sea_lantern", "cyan_concrete", "light_blue_concrete"),
        "window_frame": ("iron_block", "quartz_block"),
        "load_bearing": ("iron_block", "quartz_block", "gray_concrete"),
    },
    "unknown": {
        "foundation": ("cobblestone", "stone", "stone_bricks"),
        "wall": ("stone_bricks", "cobblestone", "oak_planks"),
        "roof": ("spruce_planks", "dark_oak_planks", "stone_bricks"),
        "floor": ("oak_planks", "smooth_stone", "spruce_planks"),
        "accent": ("oak_log", "spruce_log", "stone_bricks"),
        "window_frame": ("oak_log", "stone_bricks"),
        "load_bearing": ("oak_log", "spruce_log", "stone_bricks"),
    },
}

_ROLES = ("foundation", "wall", "roof", "floor", "accent", "window_frame", "load_bearing")

_SKIP_SUBSTR = (
    "grass", "dirt", "farmland", "podzol", "mycelium", "nylium", "path",
    "flower", "tulip", "orchid", "daisy", "bluet", "poppy", "allium",
    "cornflower", "lilac", "rose", "peony", "sunflower", "petal", "leaves",
    "sapling", "mushroom", "vine", "kelp", "seagrass", "torch", "lantern",
    "candle", "carpet", "bed", "door", "trapdoor", "fence", "gate", "button",
    "pressure_plate", "sign", "banner", "rail", "chest", "furnace", "crafting",
    "barrel", "hopper", "dropper", "dispenser", "piston", "observer",
    "water", "lava", "ice", "snow", "powder", "scaffolding", "ladder",
    "pot", "cake", "skull", "head", "bee", "nest", "hive", "campfire",
    "short_grass", "tall_grass", "fern", "dead_bush", "cactus",
    "honeycomb", "honey_block", "slime", "dried_kelp", "magma", "shulker",
    # look-polish junk / non-structure clutter
    "coral", "sponge", "tnt", "command_block", "structure_block", "jigsaw",
    "bedrock", "barrier", "spawner", "end_portal", "nether_portal",
    "obsidian", "crying_obsidian", "respawn_anchor", "lodestone",
    "sculk", "froglight", "ochre_froglight", "verdant_froglight",
    "reinforced_deepslate", "budding_amethyst", "amethyst_cluster",
    "pointed_dripstone", "dripstone_block",
    "raw_iron", "raw_copper", "raw_gold", "ore", "ancient_debris",
    "netherrack", "soul_sand", "soul_soil",
    "glowstone", "shroomlight", "redstone", "repeater", "comparator",
    "note_block", "jukebox", "lectern", "bookshelf", "enchanting",
    "anvil", "grindstone", "smithing", "loom", "stonecutter", "composter",
    "cauldron", "brewing", "beacon", "conduit", "bell", "end_rod",
)

# Style+role deny: odd ref picks (Victorian acacia, chinese mud house walls, etc.).
# Substrings matched against short block name. Empty roles inherit nothing.
_STYLE_ROLE_DENY: dict[str, dict[str, tuple[str, ...]]] = {
    "european": {
        "wall": (
            "acacia", "mangrove", "bamboo", "cherry", "crimson", "warped", "jungle",
            "mud", "packed_mud", "mud_brick", "nether", "blackstone",
            "purpur", "end_stone", "prismarine", "copper", "terracotta",
            "concrete", "wool", "hay", "mushroom", "stem", "bone", "tuff",
            "sandstone", "red_sandstone", "cut_red", "chiseled_red",
            "dirt", "moss", "deepslate", "calcite", "amethyst",
        ),
        "roof": (
            "acacia", "mangrove", "bamboo", "cherry", "mud", "packed_mud",
            "wool", "concrete", "glass", "copper", "sandstone", "red_sandstone",
            "bone", "dirt", "moss", "tuff",
        ),
        "floor": ("acacia", "mangrove", "bamboo", "cherry", "mud", "wool", "concrete", "sandstone", "red_sandstone", "bone", "dirt"),
        "foundation": ("acacia", "plank", "log", "wool", "sandstone", "red_sandstone", "copper", "mud", "bone", "dirt"),
        "accent": ("mud", "packed_mud", "mangrove", "bamboo", "acacia", "sandstone", "red_sandstone", "bone", "dirt", "concrete"),
        "window_frame": ("acacia", "mangrove", "bamboo", "mud", "sandstone", "red_sandstone", "bone"),
        "load_bearing": ("acacia", "mangrove", "bamboo", "mud", "bone", "dirt", "concrete", "wool"),
    },
    "medieval": {
        "wall": (
            "acacia", "mangrove", "bamboo", "cherry", "crimson", "warped", "jungle",
            "mud", "packed_mud", "concrete", "quartz", "purpur", "copper",
            "wool", "terracotta", "bone", "dirt", "moss", "tuff", "calcite",
        ),
        "roof": ("acacia", "mangrove", "bamboo", "cherry", "concrete", "quartz", "wool", "mud", "bone", "dirt"),
        "floor": ("acacia", "mangrove", "bamboo", "concrete", "quartz", "wool", "bone", "dirt", "mud"),
        "foundation": ("plank", "log", "wool", "concrete", "acacia", "bone", "dirt"),
        "accent": ("acacia", "mangrove", "bamboo", "bone", "dirt", "concrete", "quartz", "wool"),
        "window_frame": ("acacia", "mangrove", "bamboo", "bone", "dirt", "concrete"),
        "load_bearing": ("acacia", "mangrove", "bamboo", "bone", "dirt", "concrete", "wool"),
    },
    "chinese": {
        # Prefer wood / stone / plaster over mud-brick earth unless desert.
        "wall": (
            "mud_brick", "packed_mud", "mud", "acacia", "mangrove", "bamboo",
            "crimson", "warped", "concrete", "quartz", "purpur", "copper",
            "nether", "blackstone", "prismarine",
        ),
        "roof": ("mud", "packed_mud", "concrete", "quartz", "acacia", "mangrove", "copper", "waxed"),
        "foundation": ("mud_brick", "packed_mud", "mud", "acacia", "plank", "log", "wool", "copper", "waxed"),
        "accent": ("mud_brick", "packed_mud", "mud", "acacia", "copper", "waxed"),
        "floor": ("mud_brick", "packed_mud", "mud", "acacia", "concrete", "copper", "waxed"),
        "window_frame": ("mud_brick", "packed_mud", "mud", "acacia", "copper", "waxed"),
    },
    "japanese": {
        "wall": ("mud_brick", "packed_mud", "acacia", "mangrove", "crimson", "warped", "concrete", "purpur"),
    },
    "modern": {
        "wall": (
            "acacia", "mangrove", "bamboo", "cherry", "mud", "packed_mud",
            "nether", "purpur", "hay", "wool", "log", "plank", "bone", "dirt",
            "moss", "sandstone", "terracotta", "brick",
        ),
        "roof": ("plank", "log", "mud", "wool", "hay", "acacia", "bone", "dirt", "brick"),
        "floor": ("plank", "log", "mud", "wool", "hay", "bone", "dirt"),
        "foundation": ("plank", "log", "wool", "hay", "bone", "dirt", "mud"),
        "accent": ("plank", "log", "wool", "hay", "bone", "dirt", "mud"),
        "window_frame": ("plank", "log", "wool", "hay", "bone", "dirt"),
        "load_bearing": ("plank", "log", "wool", "hay", "bone", "dirt"),
    },
    "rustic": {
        "wall": (
            "acacia", "mangrove", "crimson", "warped", "bamboo", "cherry", "jungle",
            "concrete", "quartz", "purpur", "copper", "mud_brick", "packed_mud",
            "bone", "dirt", "moss", "nether", "calcite",
        ),
        "roof": ("concrete", "quartz", "purpur", "acacia", "mangrove", "mud", "bone", "dirt", "wool"),
        "floor": ("acacia", "mangrove", "concrete", "quartz", "bone", "dirt", "mud"),
        "foundation": ("acacia", "plank", "log", "wool", "concrete", "bone", "dirt"),
        "accent": ("acacia", "mangrove", "bone", "dirt", "concrete", "quartz"),
        "window_frame": ("acacia", "mangrove", "bone", "dirt"),
        "load_bearing": ("acacia", "mangrove", "bone", "dirt", "concrete"),
    },
    "fantasy": {
        "wall": (
            "acacia", "mangrove", "bamboo", "mud_brick", "packed_mud", "concrete",
            "bone", "dirt", "moss", "sandstone", "tuff",
        ),
        "roof": ("acacia", "mangrove", "concrete", "bone", "dirt", "mud"),
        "floor": ("acacia", "mangrove", "concrete", "bone", "dirt", "mud"),
        "foundation": ("acacia", "plank", "log", "wool", "concrete", "bone", "dirt"),
        "accent": ("acacia", "mangrove", "bone", "dirt", "concrete"),
        "window_frame": ("acacia", "mangrove", "bone", "dirt"),
        "load_bearing": ("acacia", "mangrove", "bone", "dirt", "concrete"),
    },
    "industrial": {
        "wall": (
            "acacia", "mangrove", "bamboo", "cherry", "wool", "hay", "mud", "plank", "log",
            "bone", "tuff", "green_concrete", "lime_concrete", "yellow_concrete",
            "orange_concrete", "red_concrete", "blue_concrete", "cyan_concrete",
            "purple_concrete", "magenta_concrete", "pink_concrete", "brown_concrete",
            "terracotta", "sandstone", "dirt", "moss", "nether", "purpur", "quartz",
        ),
        "roof": (
            "plank", "log", "wool", "hay", "mud", "bone", "green_concrete", "lime_concrete",
            "yellow_concrete", "terracotta", "sandstone", "dirt", "moss",
        ),
        "floor": ("plank", "log", "wool", "hay", "mud", "bone", "dirt", "moss", "green_concrete"),
        "foundation": ("plank", "log", "wool", "hay", "mud", "bone", "dirt", "green_concrete"),
        "accent": ("plank", "wool", "hay", "mud", "bone", "dirt", "moss", "green_concrete"),
        "window_frame": ("plank", "wool", "hay", "mud", "bone", "dirt"),
        "load_bearing": ("plank", "wool", "hay", "mud", "bone", "dirt", "moss", "log","green_concrete", "lime_concrete", "yellow_concrete", "orange_concrete","red_concrete", "blue_concrete", "cyan_concrete", "purple_concrete","magenta_concrete", "pink_concrete", "brown_concrete", "terracotta", "brick",),
    },
    "desert": {
        # mud/sandstone/terracotta OK for desert
        "wall": ("acacia", "mangrove", "crimson", "warped", "concrete", "quartz", "purpur", "plank", "log"),
    },
    "western": {
        "wall": (
            "acacia", "mangrove", "crimson", "warped", "bamboo", "cherry", "jungle",
            "concrete", "quartz", "mud_brick", "packed_mud", "bone", "dirt", "moss",
            "purpur", "nether", "copper", "terracotta",
        ),
        "roof": ("acacia", "mangrove", "bamboo", "cherry", "concrete", "quartz", "bone", "dirt", "wool"),
        "floor": ("acacia", "mangrove", "bamboo", "concrete", "quartz", "bone", "dirt"),
        "foundation": ("acacia", "plank", "log", "wool", "concrete", "bone", "dirt"),
        "accent": ("acacia", "mangrove", "bamboo", "bone", "dirt", "concrete", "quartz"),
        "window_frame": ("acacia", "mangrove", "bamboo", "bone", "dirt"),
        "load_bearing": ("acacia", "mangrove", "bamboo", "bone", "dirt", "concrete"),
    },
    "scifi": {
        "wall": ("plank", "log", "mud", "wool", "hay", "acacia", "mangrove", "bamboo"),
    },
}

# Woods that look wrong as European / medieval primary walls even if not denied above.
_HOUSE_WALL_WEIRD_WOOD = ("acacia", "mangrove", "bamboo", "cherry", "crimson", "warped", "jungle")

_FOUNDATION_HINT = (
    "cobble", "stone_brick", "deepslate", "blackstone", "brick", "smooth_stone",
    "andesite", "diorite", "granite", "basalt", "concrete", "sandstone", "tuff",
)
_ROOF_HINT = (
    "stair", "tile", "roof", "copper", "nether_brick", "prismarine_brick",
)
_WALL_HINT = (
    "plank", "concrete", "terracotta", "wool", "stone_brick", "brick",
    "quartz", "purpur", "sandstone", "prismarine",
)
_FLOOR_HINT = ("plank", "smooth_stone", "concrete", "wool", "quartz", "purpur")
_ACCENT_HINT = (
    "log", "stripped", "pillar", "copper", "amethyst", "purpur", "gold",
    "iron_block", "hay", "quartz_pillar", "bone_block",
)


def short_block_name(name: str) -> str:
    n = str(name).replace("minecraft:", "")
    if n.startswith("block.minecraft."):
        n = n[len("block.minecraft.") :]
    if ":" in n:
        n = n.split(":", 1)[1]
    return n


def _is_skip(short: str) -> bool:
    s = short.lower()
    if s in ("air", "barrier", "structure_void", "light"):
        return True
    for tok in _SKIP_SUBSTR:
        if tok in s:
            return True
    return False


def _style_role_denied(short: str, role: str, style: str | None) -> bool:
    """True when ref block is a junk/odd pick for this style+role."""
    s = short.lower()
    style_l = (style or "unknown").strip().lower() or "unknown"
    deny_map = _STYLE_ROLE_DENY.get(style_l) or {}
    for tok in deny_map.get(role, ()):
        if tok in s:
            return True
    # Global house-wall weird woods for european/medieval primary walls
    if role == "wall" and style_l in ("european", "medieval"):
        for tok in _HOUSE_WALL_WEIRD_WOOD:
            if tok in s:
                return True
    # calcite / amethyst / froglight never as mass wall/floor/foundation
    if role in ("wall", "floor", "foundation", "roof"):
        if any(t in s for t in ("calcite", "amethyst_cluster", "froglight", "budding")):
            return True
    return False


def _score_role(short: str, role: str, style: str | None = None) -> float:
    s = short.lower()
    if _is_skip(s):
        return -1.0
    if _style_role_denied(s, role, style):
        return -1.0
    # Glass / panes never carry mass or load.
    if role in ("foundation", "wall", "roof", "floor", "accent", "load_bearing"):
        if "glass" in s or s.endswith("_pane") or s in ("iron_bars", "chain", "ladder", "scaffolding"):
            return -1.0
        if any(x in s for x in (
            "moss", "grass", "dirt", "mud", "leaves", "wool", "carpet", "honey", "slime", "tnt",
            "bone", "hopper", "ore", "raw_iron", "raw_copper", "raw_gold", "netherrack",
            "sculk", "sponge", "coral", "mushroom", "nylium", "podzol", "farmland",
        )):
            return -1.0
    if role == "window_frame" and ("glass" in s or s.endswith("_pane") or any(x in s for x in ("moss", "dirt", "leaves", "wool", "carpet"))):
        return -1.0
    # stairs/slabs are weak full blocks; prefer for roof only
    is_stair = "stair" in s
    is_slab = "slab" in s
    is_pane = "pane" in s or s.endswith("_bars") or s.endswith("_wall")
    if is_pane and role != "window_frame":
        return -0.5
    score = 0.0
    if role == "foundation":
        if any(h in s for h in _FOUNDATION_HINT):
            score += 3.0
        if "plank" in s or "log" in s or "wool" in s:
            score -= 1.5
        if is_stair or is_slab:
            score -= 4.0  # footing needs full cubes
    elif role == "wall":
        if any(h in s for h in _WALL_HINT):
            score += 2.5
        if "log" in s and "stripped" not in s:
            score += 1.0  # log cabins
        if is_stair or is_slab:
            score -= 4.0  # walls need full cubes
        if "glass" in s:
            score -= 3.0
    elif role == "roof":
        if is_stair:
            score += 3.5
        if any(h in s for h in _ROOF_HINT):
            score += 2.0
        if "plank" in s or "tile" in s or "terracotta" in s:
            score += 1.5
        if "wool" in s and any(c in s for c in ("red", "orange", "brown", "black")):
            score += 1.0
        if is_slab:
            score += 1.0
        if "glass" in s:
            score -= 2.0
    elif role == "floor":
        if "plank" in s or "smooth_stone" in s:
            score += 3.2
        elif any(h in s for h in _FLOOR_HINT):
            score += 2.0
        if "wool" in s:
            score -= 1.2  # wool often facade/tent; prefer planks for decks
        if "copper" in s or "ore" in s or "honey" in s or "slime" in s:
            score -= 2.5
        if not any(x in s for x in ("plank", "smooth_stone", "concrete", "wool", "quartz", "purpur", "brick", "stone")):
            score -= 1.5
        if is_stair:
            score -= 4.0
        if is_slab:
            score -= 3.5  # decks need full cubes in 32^3 scaffold
        if "log" in s:
            score -= 1.0
    elif role == "accent":
        if any(h in s for h in _ACCENT_HINT):
            score += 3.0
        if "wool" in s and any(c in s for c in ("purple", "magenta", "cyan", "blue", "red", "yellow")):
            score += 1.5
        if is_stair or is_slab:
            score -= 1.5
    elif role == "window_frame":
        if "log" in s or "stripped" in s:
            score += 3.0
        if "stone_brick" in s or "iron" in s:
            score += 2.0
        if is_stair or is_slab or "glass" in s:
            score -= 2.0
    return score


def _name_to_id(palette: dict[int, str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, name in palette.items():
        out[short_block_name(name)] = int(i)
    return out


def _resolve_id(name_to_id: dict[str, int], candidates: list[str] | tuple[str, ...]) -> int | None:
    for c in candidates:
        c = short_block_name(c)
        if c in name_to_id and name_to_id[c] > 0:
            return int(name_to_id[c])
        for pn, pid in name_to_id.items():
            if pid <= 0:
                continue
            if pn == c or pn.endswith("_" + c) or c.endswith("_" + pn) or c in pn:
                # avoid stone matching dripstone / redstone via crude containment
                if c == "stone" and pn not in ("stone", "smooth_stone", "stone_bricks", "end_stone"):
                    if "stone" in pn and pn not in ("stone", "smooth_stone"):
                        # allow stone_bricks already handled by endswith
                        if "brick" in pn or pn.startswith("stone_"):
                            return int(pid)
                        continue
                return int(pid)
    return None


def _collect_ref_names(
    top_blocks: list[dict[str, Any]] | None,
    remap_targets: list[str] | None,
) -> list[tuple[str, float]]:
    """Return (short_name, weight) from reference materials."""
    scored: dict[str, float] = {}
    if top_blocks:
        for i, tb in enumerate(top_blocks):
            if not isinstance(tb, dict):
                continue
            n = short_block_name(tb.get("name") or "")
            if not n or _is_skip(n):
                continue
            w = float(tb.get("count") or tb.get("frac") or (100 - i))
            scored[n] = scored.get(n, 0.0) + max(1.0, w)
    if remap_targets:
        for i, t in enumerate(remap_targets):
            n = short_block_name(t)
            if not n or _is_skip(n):
                continue
            scored[n] = scored.get(n, 0.0) + max(1.0, 40.0 - i)
    return sorted(scored.items(), key=lambda kv: -kv[1])



def prefer_full_cube(name_to_id: dict[str, int], short: str, palette: dict[int, str], bid: int) -> int:
    """If bid is stairs/slab, try matching full cube (planks/stone_bricks/etc)."""
    s = short_block_name(palette.get(int(bid), short)).lower()
    if "stair" not in s and "slab" not in s:
        return int(bid)
    base = s
    for suf in ("_stairs", "_stair", "_slab"):
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    cands: list[str] = []
    if base.endswith("_brick"):
        cands.append(base + "s")  # stone_brick -> stone_bricks
    if base.endswith("_plank"):
        cands.append(base + "s")
    cands.extend(
        [
            base + "_planks",
            base + "_block",
            base + "_bricks",
            base,
            "quartz_block" if "quartz" in base else "",
            "smooth_quartz" if "quartz" in base else "",
            "smooth_stone" if base == "stone" else "",
            "dark_oak_planks",
            "spruce_planks",
            "oak_planks",
            "stone_bricks",
        ]
    )
    cands = [c for c in cands if c]
    pid = _resolve_id(name_to_id, cands)
    return int(pid) if pid else int(bid)


def resolve_role_materials(
    palette: dict[int, str],
    style: str | None = None,
    *,
    top_blocks: list[dict[str, Any]] | None = None,
    remap_targets: list[str] | None = None,
) -> tuple[dict[str, int], dict[str, Any]]:
    """Pick block ids for foundation/wall/roof/floor/accent/window_frame."""
    name_to_id = _name_to_id(palette)
    style_l = (style or "unknown").strip().lower() or "unknown"
    fallbacks = STYLE_ROLE_FALLBACKS.get(style_l) or STYLE_ROLE_FALLBACKS["unknown"]
    ref_names = _collect_ref_names(top_blocks, remap_targets)

    info: dict[str, Any] = {
        "style": style_l,
        "source": "style_fallback",
        "ref_candidates": [n for n, _ in ref_names[:12]],
    }
    roles: dict[str, int] = {}
    role_names: dict[str, str] = {}
    used: set[int] = set()

    def pick(role: str) -> int:
        best_id = None
        best_score = -1.0
        best_name = None
        denied = 0
        for n, w in ref_names:
            if _style_role_denied(n, role, style_l):
                denied += 1
                continue
            sc = _score_role(n, role, style_l)
            if sc < 0:
                continue
            # weight by ref frequency
            sc = sc + min(2.0, w / 80.0)
            pid = _resolve_id(name_to_id, [n])
            if pid is None or pid <= 0:
                continue
            # mild penalty if already used by another role (except accent/frame can share)
            if pid in used and role in ("wall", "roof", "floor", "foundation"):
                sc -= 0.8
            if sc > best_score:
                best_score = sc
                best_id = pid
                best_name = n
        if denied:
            info.setdefault("style_denied_refs", {})[role] = int(denied)
        # Clean-house: ALL roles use style fallbacks so ref rainbow / junk
        # (green_concrete, bone, acacia, tuff, odd load_bearing) cannot paint the build.
        info["source"] = "style_fallback_clean"
        if denied:
            info.setdefault("style_denied_refs", {})[role] = int(denied)
        pid = _resolve_id(name_to_id, list(fallbacks.get(role, ())))
        if pid is None:
            pid = _resolve_id(
                name_to_id,
                ["stone_bricks", "cobblestone", "oak_planks", "stone", "spruce_planks", "oak_log", "iron_block"],
            )
        return int(pid or 1)

    for role in _ROLES:
        bid = pick(role)
        roles[role] = bid
        role_names[role] = short_block_name(palette.get(bid, "?"))
        if role in ("wall", "roof", "floor", "foundation"):
            used.add(bid)

    # Ensure roof != wall and floor != wall when possible
    def diversify(role: str, alts: tuple[str, ...]) -> None:
        if roles[role] != roles.get("wall"):
            return
        for a in alts:
            pid = _resolve_id(name_to_id, [a])
            if pid and pid > 0 and pid != roles["wall"]:
                roles[role] = int(pid)
                role_names[role] = short_block_name(palette.get(int(pid), "?"))
                return
        fb = fallbacks.get(role, ())
        pid = _resolve_id(name_to_id, list(fb))
        if pid and pid != roles["wall"]:
            roles[role] = int(pid)
            role_names[role] = short_block_name(palette.get(int(pid), "?"))

    diversify("roof", fallbacks.get("roof", ()))
    diversify("floor", fallbacks.get("floor", ()))
    diversify("foundation", fallbacks.get("foundation", ()))
    if roles["accent"] == roles["wall"]:
        diversify("accent", fallbacks.get("accent", ()))
    if roles["window_frame"] == roles["wall"]:
        roles["window_frame"] = roles["accent"]
        role_names["window_frame"] = role_names["accent"]

    # Scaffold paints full cells: avoid stairs/slabs for mass roles (keep stair as roof hint only in name)
    for role in ("foundation", "wall", "floor", "accent", "window_frame", "roof"):
        bid = int(roles[role])
        short = role_names.get(role) or short_block_name(palette.get(bid, "?"))
        full = prefer_full_cube(name_to_id, short, palette, bid)
        if full != bid:
            roles[role] = full
            role_names[role] = short_block_name(palette.get(full, "?"))
            info.setdefault("full_cube_remap", {})[role] = {"from": short, "to": role_names[role]}

    # Re-diversify AFTER cube remap (stairs→planks often collapsed roof==wall).
    diversify("roof", fallbacks.get("roof", ()))
    diversify("floor", fallbacks.get("floor", ()))
    diversify("foundation", fallbacks.get("foundation", ()))
    if roles["roof"] == roles["wall"]:
        # Hard force style roof fallback chain
        for a in list(fallbacks.get("roof", ())) + [
            "dark_oak_planks", "spruce_planks", "stone_bricks", "deepslate_bricks",
            "gray_concrete", "black_concrete", "bricks",
        ]:
            pid = _resolve_id(name_to_id, [a])
            if pid and pid > 0 and pid != roles["wall"]:
                roles["roof"] = int(pid)
                role_names["roof"] = short_block_name(palette.get(int(pid), "?"))
                info["roof_forced_distinct"] = True
                break
    if roles["accent"] == roles["wall"]:
        diversify("accent", fallbacks.get("accent", ()))
    if roles["window_frame"] == roles["wall"]:
        roles["window_frame"] = roles["accent"]
        role_names["window_frame"] = role_names["accent"]
    if not roles.get("load_bearing"):
        roles["load_bearing"] = int(roles.get("accent") or roles["wall"])
        role_names["load_bearing"] = role_names.get("accent") or role_names["wall"]
        # Harden load_bearing: full cube, never glass/stairs, prefer != wall.
    lb = int(roles.get("load_bearing") or 0)
    lb_short = role_names.get("load_bearing") or short_block_name(palette.get(lb, "?"))
    if any(tok in lb_short for tok in ("glass", "pane", "stair", "slab", "bar", "chain")):
        fb = list((fallbacks.get("load_bearing") or ())) + list((fallbacks.get("accent") or ())) + [
            "oak_log", "spruce_log", "stone_bricks", "iron_block", "cobblestone",
        ]
        pid = _resolve_id(name_to_id, fb)
        if pid:
            roles["load_bearing"] = int(pid)
            role_names["load_bearing"] = short_block_name(palette.get(int(pid), "?"))
            info["load_bearing_remapped"] = True
    lb = int(roles["load_bearing"])
    lb = prefer_full_cube(name_to_id, role_names.get("load_bearing", ""), palette, lb)
    roles["load_bearing"] = int(lb)
    role_names["load_bearing"] = short_block_name(palette.get(int(lb), "?"))
    if roles["load_bearing"] == roles["wall"]:
        for a in list((fallbacks.get("load_bearing") or ())) + list((fallbacks.get("accent") or ())) + [
            "oak_log", "spruce_log", "dark_oak_log", "iron_block", "stone_bricks",
        ]:
            pid = _resolve_id(name_to_id, [a])
            if pid and pid > 0 and pid != roles["wall"]:
                roles["load_bearing"] = int(pid)
                role_names["load_bearing"] = short_block_name(palette.get(int(pid), "?"))
                break

    info["load_bearing_id"] = int(roles["load_bearing"])

    info["roles"] = dict(roles)
    info["role_names"] = role_names
    info["wall_id"] = roles["wall"]
    info["floor_id"] = roles["floor"]
    info["roof_id"] = roles["roof"]
    info["foundation_id"] = roles["foundation"]
    info["accent_id"] = roles["accent"]
    info["window_frame_id"] = roles["window_frame"]
    info["wall_name"] = role_names["wall"]
    info["floor_name"] = role_names["floor"]
    return roles, info


def role_ids_list(roles: dict[str, int]) -> list[int]:
    out: list[int] = []
    for r in _ROLES:
        bid = int(roles.get(r) or 0)
        if bid > 0 and bid not in out:
            out.append(bid)
    return out
