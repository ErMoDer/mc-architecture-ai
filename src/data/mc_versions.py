# -*- coding: utf-8 -*-
"""Minecraft Java target versions + block remapping for litematic export.

Generation keeps one training palette; export remaps/downgrades IDs for the
chosen Java target. Default is 26.3 (Wilderness Bound) for the companion.
Bedrock is not supported.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

DEFAULT_VERSION_ID = "26.3"


@dataclass(frozen=True)
class McVersion:
    id: str
    display_name: str
    edition: str = "java"
    notes: str = ""
    # Order index: higher = newer. Used to decide when a block must downgrade.
    order: int = 0


# Short honest Java list. Labels must say Java (not Bedrock).
VERSIONS: tuple[McVersion, ...] = (
    McVersion(
        "1.16.5",
        "Java 1.16.5",
        notes="Nether Update era; deepslate/copper/moss remapped away",
        order=16,
    ),
    McVersion(
        "1.19.4",
        "Java 1.19.4",
        notes="Pre-Trails & Tales; cherry/bamboo planks remapped",
        order=19,
    ),
    McVersion(
        "1.20.4",
        "Java 1.20.4",
        notes="Trails & Tales era; trial copper / pale oak remapped",
        order=20,
    ),
    McVersion(
        "1.21",
        "Java 1.21 / Tricky Trials",
        notes="Copper bulbs/grates/tuff bricks OK; 26.3-only still remapped",
        order=21,
    ),
    McVersion(
        "26.3",
        "Java 26.3 / Wilderness Bound",
        notes="Companion default (Fabric). Poplar / wool stairs / shelves kept if present",
        order=263,
    ),
)

_BY_ID: dict[str, McVersion] = {v.id: v for v in VERSIONS}


def list_versions() -> list[McVersion]:
    return list(VERSIONS)


def get_version(version_id: str | None) -> McVersion:
    if version_id is None or str(version_id).strip() == "":
        return _BY_ID[DEFAULT_VERSION_ID]
    key = str(version_id).strip()
    # allow "v26.3" / "Java 26.3"
    if key.lower().startswith("v") and key[1:] in _BY_ID:
        key = key[1:]
    if key in _BY_ID:
        return _BY_ID[key]
    # match display menu labels like "Java 26.3 / Wilderness Bound"
    for v in VERSIONS:
        if key == v.display_name or key.startswith(v.id) or v.id in key:
            return v
    raise KeyError(f"unknown Java target version: {version_id!r}; known={list(_BY_ID)}")


def version_menu_labels() -> list[str]:
    """UI OptionMenu values (id embedded for parsing)."""
    out: list[str] = []
    for v in VERSIONS:
        suffix = " (default)" if v.id == DEFAULT_VERSION_ID else ""
        out.append(f"{v.display_name}{suffix}")
    return out


def version_id_from_menu_label(label: str) -> str:
    label = (label or "").strip()
    for v in VERSIONS:
        if label.startswith(v.display_name) or label.startswith(v.id):
            return v.id
        if v.id in label:
            return v.id
    return DEFAULT_VERSION_ID


def filename_version_tag(version_id: str | None) -> str:
    vid = get_version(version_id).id
    return f"v{vid}"


# ---------------------------------------------------------------------------
# Remap: exact + family rules. order = minimum version.order required.
# If target.order < required, replace with substitute (or family map).
# ---------------------------------------------------------------------------

# Exact block name (with minecraft:) -> (min_order, substitute)
_EXACT: dict[str, tuple[int, str]] = {
    # 26.3 / late 1.21.x shelves & statues
    "minecraft:oak_shelf": (263, "minecraft:bookshelf"),
    "minecraft:spruce_shelf": (263, "minecraft:bookshelf"),
    "minecraft:dark_oak_shelf": (263, "minecraft:bookshelf"),
    "minecraft:oxidized_copper_golem_statue": (263, "minecraft:oxidized_copper"),
    "minecraft:bush": (21, "minecraft:short_grass"),
    "minecraft:firefly_bush": (21, "minecraft:sweet_berry_bush"),
    # 1.21 trial
    "minecraft:crafter": (21, "minecraft:crafting_table"),
    "minecraft:waxed_copper_bulb": (21, "minecraft:glowstone"),
    "minecraft:waxed_exposed_copper_bulb": (21, "minecraft:glowstone"),
    "minecraft:waxed_copper_grate": (21, "minecraft:waxed_cut_copper"),
    "minecraft:waxed_exposed_copper_grate": (21, "minecraft:waxed_exposed_cut_copper"),
    "minecraft:waxed_weathered_copper_grate": (21, "minecraft:waxed_weathered_cut_copper"),
    "minecraft:waxed_oxidized_copper_grate": (21, "minecraft:waxed_oxidized_cut_copper"),
    "minecraft:waxed_chiseled_copper": (21, "minecraft:waxed_cut_copper"),
    "minecraft:tuff_bricks": (21, "minecraft:deepslate_bricks"),
    "minecraft:tuff_brick_slab": (21, "minecraft:deepslate_brick_slab"),
    "minecraft:tuff_brick_stairs": (21, "minecraft:deepslate_brick_stairs"),
    "minecraft:tuff_brick_wall": (21, "minecraft:deepslate_brick_wall"),
    "minecraft:chiseled_tuff": (21, "minecraft:chiseled_deepslate"),
    "minecraft:chiseled_tuff_bricks": (21, "minecraft:chiseled_deepslate"),
    "minecraft:polished_tuff": (21, "minecraft:polished_deepslate"),
    "minecraft:polished_tuff_slab": (21, "minecraft:polished_deepslate_slab"),
    # pale garden ~1.21.4 → treat as needing >1.21 for our ladder (order 22 virtual)
    "minecraft:pale_moss_block": (22, "minecraft:moss_block"),
    "minecraft:pale_moss_carpet": (22, "minecraft:moss_carpet"),
    "minecraft:open_eyeblossom": (22, "minecraft:poppy"),
    "minecraft:potted_open_eyeblossom": (22, "minecraft:potted_red_tulip"),
    "minecraft:potted_closed_eyeblossom": (22, "minecraft:potted_red_tulip"),
    # 1.20
    "minecraft:decorated_pot": (20, "minecraft:terracotta"),
    "minecraft:chiseled_bookshelf": (20, "minecraft:bookshelf"),
    "minecraft:pitcher_plant": (20, "minecraft:lilac"),
    "minecraft:pitcher_crop": (20, "minecraft:wheat"),
    "minecraft:torchflower": (20, "minecraft:orange_tulip"),
    "minecraft:torchflower_crop": (20, "minecraft:wheat"),
    "minecraft:potted_torchflower": (20, "minecraft:potted_orange_tulip"),
    "minecraft:bamboo_mosaic": (20, "minecraft:jungle_planks"),
    "minecraft:short_grass": (20, "minecraft:grass"),
    # 1.19
    "minecraft:mud_bricks": (19, "minecraft:bricks"),
    "minecraft:mud_brick_slab": (19, "minecraft:brick_slab"),
    "minecraft:mud_brick_stairs": (19, "minecraft:brick_stairs"),
    "minecraft:mud_brick_wall": (19, "minecraft:brick_wall"),
    "minecraft:packed_mud": (19, "minecraft:dirt"),
    "minecraft:ochre_froglight": (19, "minecraft:shroomlight"),
    "minecraft:verdant_froglight": (19, "minecraft:shroomlight"),
    "minecraft:pearlescent_froglight": (19, "minecraft:shroomlight"),
    "minecraft:sculk": (19, "minecraft:deepslate"),
    "minecraft:sculk_vein": (19, "minecraft:moss_carpet"),
    "minecraft:sculk_catalyst": (19, "minecraft:deepslate"),
    "minecraft:sculk_sensor": (19, "minecraft:observer"),
    "minecraft:calibrated_sculk_sensor": (19, "minecraft:observer"),
    "minecraft:sculk_shrieker": (19, "minecraft:deepslate"),
    # 1.17 vs 1.16.5
    "minecraft:moss_block": (17, "minecraft:green_wool"),
    "minecraft:moss_carpet": (17, "minecraft:green_carpet"),
    "minecraft:dripstone_block": (17, "minecraft:stone"),
    "minecraft:pointed_dripstone": (17, "minecraft:cobblestone"),
    "minecraft:amethyst_block": (17, "minecraft:purple_concrete"),
    "minecraft:amethyst_cluster": (17, "minecraft:glowstone"),
    "minecraft:large_amethyst_bud": (17, "minecraft:glowstone"),
    "minecraft:medium_amethyst_bud": (17, "minecraft:glowstone"),
    "minecraft:small_amethyst_bud": (17, "minecraft:glowstone"),
    "minecraft:calcite": (17, "minecraft:quartz_block"),
    "minecraft:tuff": (17, "minecraft:andesite"),
    "minecraft:copper_block": (17, "minecraft:orange_concrete"),
    "minecraft:exposed_copper": (17, "minecraft:orange_terracotta"),
    "minecraft:weathered_copper": (17, "minecraft:cyan_terracotta"),
    "minecraft:oxidized_copper": (17, "minecraft:oxidized_cut_copper"),  # will chain if needed
    "minecraft:raw_iron_block": (17, "minecraft:iron_block"),
    "minecraft:raw_copper_block": (17, "minecraft:orange_concrete"),
    "minecraft:raw_gold_block": (17, "minecraft:gold_block"),
    "minecraft:powder_snow": (17, "minecraft:snow_block"),
    "minecraft:glow_lichen": (17, "minecraft:vine"),
    "minecraft:hanging_roots": (17, "minecraft:dead_bush"),
    "minecraft:rooted_dirt": (17, "minecraft:dirt"),
    "minecraft:deepslate": (17, "minecraft:stone"),
    "minecraft:cobbled_deepslate": (17, "minecraft:cobblestone"),
    "minecraft:polished_deepslate": (17, "minecraft:smooth_stone"),
    "minecraft:deepslate_bricks": (17, "minecraft:stone_bricks"),
    "minecraft:deepslate_tiles": (17, "minecraft:stone_bricks"),
    "minecraft:chiseled_deepslate": (17, "minecraft:chiseled_stone_bricks"),
    "minecraft:cracked_deepslate_bricks": (17, "minecraft:cracked_stone_bricks"),
    "minecraft:cracked_deepslate_tiles": (17, "minecraft:cracked_stone_bricks"),
    "minecraft:cobbled_deepslate_slab": (17, "minecraft:cobblestone_slab"),
    "minecraft:cobbled_deepslate_stairs": (17, "minecraft:cobblestone_stairs"),
    "minecraft:cobbled_deepslate_wall": (17, "minecraft:cobblestone_wall"),
    "minecraft:deepslate_brick_slab": (17, "minecraft:stone_brick_slab"),
    "minecraft:deepslate_brick_stairs": (17, "minecraft:stone_brick_stairs"),
    "minecraft:deepslate_brick_wall": (17, "minecraft:stone_brick_wall"),
    "minecraft:deepslate_tile_slab": (17, "minecraft:stone_brick_slab"),
    "minecraft:polished_deepslate_stairs": (17, "minecraft:stone_brick_stairs"),
    "minecraft:deepslate_iron_ore": (17, "minecraft:iron_ore"),
    "minecraft:deepslate_coal_ore": (17, "minecraft:coal_ore"),
    "minecraft:deepslate_copper_ore": (17, "minecraft:iron_ore"),
    "minecraft:deepslate_gold_ore": (17, "minecraft:gold_ore"),
    "minecraft:deepslate_diamond_ore": (17, "minecraft:diamond_ore"),
    "minecraft:deepslate_lapis_ore": (17, "minecraft:lapis_ore"),
    "minecraft:deepslate_redstone_ore": (17, "minecraft:redstone_ore"),
    "minecraft:smooth_basalt": (17, "minecraft:basalt"),
}

# Family prefix remaps: (prefix, min_order, replacement_prefix)
# Applied when name.startswith(prefix) and no exact hit already resolved.
_FAMILY: list[tuple[str, int, str]] = [
    # 26.3 poplar → birch
    ("minecraft:poplar_", 263, "minecraft:birch_"),
    ("minecraft:stripped_poplar_", 263, "minecraft:stripped_birch_"),
    # pale oak → birch / light gray feel
    ("minecraft:pale_oak_", 22, "minecraft:birch_"),
    ("minecraft:stripped_pale_oak_", 22, "minecraft:stripped_birch_"),
    # cherry → birch (1.20+)
    ("minecraft:cherry_", 20, "minecraft:birch_"),
    ("minecraft:stripped_cherry_", 20, "minecraft:stripped_birch_"),
    # bamboo wood set → jungle (1.20+); bare "bamboo" plant stays if older? plant is older
    ("minecraft:bamboo_planks", 20, "minecraft:jungle_planks"),
    ("minecraft:bamboo_block", 20, "minecraft:jungle_log"),
    ("minecraft:bamboo_", 20, "minecraft:jungle_"),  # door/trapdoor/etc — careful with bamboo plant
    # mangrove → dark oak (1.19+)
    ("minecraft:mangrove_", 19, "minecraft:dark_oak_"),
    ("minecraft:stripped_mangrove_", 19, "minecraft:stripped_dark_oak_"),
    # hanging signs (1.20)
    ("minecraft:_hanging_sign", 20, ""),  # handled specially
]

# Wool/concrete stairs & slabs introduced in 26.3 — map to full block / older slab
_COLORS = (
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
)

for _c in _COLORS:
    _EXACT[f"minecraft:{_c}_wool_stairs"] = (263, f"minecraft:{_c}_wool")
    _EXACT[f"minecraft:{_c}_wool_slab"] = (263, f"minecraft:{_c}_wool")
    _EXACT[f"minecraft:{_c}_concrete_stairs"] = (263, f"minecraft:{_c}_concrete")
    _EXACT[f"minecraft:{_c}_concrete_slab"] = (263, f"minecraft:{_c}_concrete")

# waxed copper doors/trapdoors/bulbs variants → older substitutes when < 1.21
for _stage in ("", "exposed_", "weathered_", "oxidized_"):
    base = f"minecraft:waxed_{_stage}copper"
    cut = f"minecraft:waxed_{_stage}cut_copper"
    _EXACT[f"{base}_door"] = (21, "minecraft:oak_door")
    _EXACT[f"{base}_trapdoor"] = (21, "minecraft:oak_trapdoor")
    # cut copper itself is 1.17 — remap below for 1.16
    _EXACT[cut] = (17, "minecraft:orange_concrete")
    _EXACT[f"{cut}_slab"] = (17, "minecraft:orange_terracotta")
    _EXACT[f"{cut}_stairs"] = (17, "minecraft:sandstone_stairs")
    _EXACT[f"minecraft:waxed_{_stage}copper_block"] = (17, "minecraft:orange_concrete")

# oxidized_copper fallback for 1.16 was wrong above — fix
_EXACT["minecraft:oxidized_copper"] = (17, "minecraft:cyan_terracotta")
_EXACT["minecraft:waxed_oxidized_copper"] = (17, "minecraft:cyan_terracotta")
_EXACT["minecraft:waxed_copper_block"] = (17, "minecraft:orange_concrete")
_EXACT["minecraft:waxed_exposed_copper"] = (17, "minecraft:orange_terracotta")
_EXACT["minecraft:waxed_weathered_copper"] = (17, "minecraft:cyan_terracotta")


def _norm(name: str) -> str:
    name = str(name).strip()
    if not name:
        return "minecraft:air"
    if "[" in name:
        name = name.split("[", 1)[0]
    if ":" not in name:
        name = f"minecraft:{name}"
    return name


def _family_remap(name: str, target_order: int) -> str | None:
    # bamboo plant block alone is ancient — don't remap bare minecraft:bamboo
    if name == "minecraft:bamboo":
        return None
    if name.endswith("_hanging_sign") or name.endswith("_wall_hanging_sign"):
        if target_order < 20:
            # oak_hanging_sign -> oak_sign
            base = name.replace("minecraft:", "").replace("_wall_hanging_sign", "").replace("_hanging_sign", "")
            return f"minecraft:{base}_sign"
        return None
    for prefix, min_ord, repl_prefix in _FAMILY:
        if min_ord <= target_order:
            continue
        if prefix.endswith("_") and name.startswith(prefix):
            # bamboo_ special-case: skip minecraft:bamboo alone (already handled)
            if prefix == "minecraft:bamboo_" and name == "minecraft:bamboo":
                continue
            suffix = name[len(prefix) :]
            # jungle_hanging_sign etc still ok via hanging rule above
            if repl_prefix.endswith("_"):
                return f"{repl_prefix}{suffix}"
            return repl_prefix  # full replacement string rarely
        if not prefix.endswith("_") and name == prefix:
            return repl_prefix
    return None


def remap_block_name(name: str, target_version: str | None) -> str:
    """Return a block id safe-ish for the Java target version."""
    ver = get_version(target_version)
    n = _norm(name)
    if n in {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}:
        return "minecraft:air"

    # Iterate a few times for chained remaps (e.g. pale_oak -> birch OK; oxidized -> ...)
    for _ in range(4):
        hit = _EXACT.get(n)
        if hit is not None:
            min_ord, sub = hit
            if ver.order < min_ord:
                n = _norm(sub)
                continue
        fam = _family_remap(n, ver.order)
        if fam is not None and fam != n:
            n = _norm(fam)
            continue
        break
    return n


def remap_palette(
    palette: dict[int, str] | list[str],
    target_version: str | None,
) -> dict[int, str] | list[str]:
    """Remap every palette entry; keys/indices preserved."""
    if isinstance(palette, dict):
        return {int(k): remap_block_name(v, target_version) for k, v in palette.items()}
    return [remap_block_name(v, target_version) for v in palette]


def remap_summary(
    palette: dict[int, str],
    target_version: str | None,
    used_ids: Iterable[int] | None = None,
) -> dict:
    """How many distinct names changed for used (or all) palette ids."""
    ver = get_version(target_version)
    ids = list(used_ids) if used_ids is not None else list(palette.keys())
    changed = []
    for i in ids:
        if int(i) not in palette:
            continue
        src = palette[int(i)]
        dst = remap_block_name(src, ver.id)
        if _norm(src) != _norm(dst):
            changed.append((_norm(src), _norm(dst)))
    # unique pairs
    uniq = sorted(set(changed))
    return {
        "target_version": ver.id,
        "display_name": ver.display_name,
        "changed_pairs": len(uniq),
        "examples": uniq[:12],
    }
