# -*- coding: utf-8 -*-
"""Post-hoc look hardening for 32^3 samples (shell / floors / materials).

No retrain. Complements structure_constraints with:
- style-conditioned structural whitelist
- top-K palette limit (kill rainbow / junk fills)
- stronger outer shell (perimeter continuity, optional 1-block thickness, hole fill)
- regular flat floor slabs + cheap roof/eaves tidy
- window-aware shell: keep rectangular / glass / repeating perimeter openings
- facade rhythm: front door, pitched/flat roof, eave overhang, cornice, window sill/header, banding, corner pillars

Docs: docs/look_harden.md, docs/structure_constraints.md
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from src.app.morph import prune_strays, regularize_form
from src.app.structure_constraints import (
    _connected_components,
    _floor_metrics,
    _footprint,
    check_structure,
)
from src.app.scaffold_materials import resolve_role_materials, role_ids_list

_RULES_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "mc-knowledge"
    / "builds"
    / "look_harden_rules.json"
)


@lru_cache(maxsize=1)
def load_knowledge_rules() -> dict[str, Any]:
    """Load machine-readable building-principle defaults (original abstracts)."""
    p = _RULES_PATH
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    return {}


def knowledge_defaults() -> dict[str, Any]:
    """Flattened defaults for look_harden knobs; safe if JSON missing."""
    base: dict[str, Any] = {
        "foundation_height": 1,
        "shell_thickness": 1,
        "min_story_clear": 3,
        "floor_spacing": 5,
        "window_height_min": 1,
        "window_height_max": 2,
        "window_width_min": 1,
        "window_width_max": 2,
        "window_spacing": 3,
        "window_from_corner": 2,
        "window_from_floor": 1,
        "preserve_windows": True,
        "place_window_glass": True,
        "door_width": 1,
        "door_height": 2,
        "door_centered": True,
        "place_door": True,
        "eave_overhang": 1,
        "roof_rise_max": 5,
        "roof_rise_min": 2,
        "facade_banding": True,
        "corner_pillars": True,
        "geometry_mode": "strong",
        "facade_detail": True,
    }
    data = load_knowledge_rules()
    d = data.get("defaults") if isinstance(data, dict) else None
    if isinstance(d, dict):
        base.update({k: v for k, v in d.items()})
    return base



# Per-style facade polish (window rhythm + eaves/cornice). Keys merge over knowledge defaults.
_STYLE_FACADE: dict[str, dict[str, Any]] = {
    "european": {
        # full_style_v2 seed102 glass~448 (curtain-wall relapse vs older ~224).
        # Mid dens: sp=4 bands=3 from_corner=3 -> probe ~256 (aim 200-280).
        "window_spacing": 4,
        "window_from_corner": 3,
        "window_width_max": 1,
        "eave_overhang": 2,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 2,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 8,
    },
    "chinese": {
        "window_spacing": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 4,
        "door_width": 2,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 8,
    },
    "rustic": {
        "window_spacing": 4,
        "window_width_max": 1,
        "eave_overhang": 2,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        # Was sp=4 then 10 (~300 then ~100 pier cells / 柱林); widen so vertical accent stays but thinner rhythm.
        "wall_pier_spacing": 12,
    },
    "medieval": {
        "window_spacing": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 4,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 8,
    },
    "modern": {
        # Opener than euro (wider bays) but not curtain-wall: sp=6, ww=2, only 2 story bands.
        # 2:30 polish: strict openings (Phase F-style) — G modern window_cells 529 was mostly
        # weak-peri / near_rect holes; glass~224. Probe strict -> win~225.
        "window_spacing": 6,
        "window_width_max": 2,
        "window_height_max": 2,
        "window_from_corner": 3,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 2,
        "door_width": 2,
        "door_height": 2,
        "place_door_frame": False,
        "place_wall_piers": False,
        "corner_pillars": False,
        "strict_window_openings": True,
    },
    "industrial": {
        # Was defaults (sp=3, bands=4, ww=2) -> ~450 glass; strip windows + solid panels between.
        "window_spacing": 4,
        "window_width_max": 1,
        "window_height_max": 2,
        "window_from_corner": 2,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": False,
        "max_window_bands": 3,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 8,
        "corner_pillars": True,
    },
    "fantasy": {
        # Phase E2 dens + Phase F strict openings (seal irregular shell holes).
        "window_spacing": 6,
        "window_from_corner": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 1,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 8,
        "strict_window_openings": True,
    },
    "western": {
        "window_spacing": 4,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 1,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 8,
        "strict_window_openings": True,
    },
}


def style_facade_rules(style: str | None, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge knowledge defaults with per-style window/eave polish knobs."""
    out = dict(base or knowledge_defaults())
    key = (style or "").strip().lower()
    extra = _STYLE_FACADE.get(key)
    if extra:
        out.update(extra)
    return out


def _clamp_floor_spacing(spacing: int | None, rules: dict[str, Any] | None = None) -> int:
    r = rules or knowledge_defaults()
    min_clear = max(3, int(r.get("min_story_clear", 3)))
    default_sp = int(r.get("floor_spacing", min_clear + 1))
    sp = default_sp if spacing is None else int(spacing)
    return max(min_clear + 1, sp)


# Substrings that mark non-structural mass (should not dominate walls/floors).
_JUNK_SUBSTR = (
    "sign",
    "banner",
    "candle",
    "flower",
    "tulip",
    "orchid",
    "daisy",
    "bluet",
    "poppy",
    "allium",
    "cornflower",
    "lilac",
    "rose_bush",
    "peony",
    "sunflower",
    "wither_rose",
    "torchflower",
    "pitcher",
    "wheat",
    "carrot",
    "potato",
    "beetroot",
    "melon_stem",
    "pumpkin_stem",
    "sugar_cane",
    "bamboo",
    "kelp",
    "seagrass",
    "sea_pickle",
    "lily_pad",
    "carpet",
    "pressure_plate",
    "button",
    "lever",
    "tripwire",
    "rail",
    "minecart",
    "skull",
    "head",
    "pot",
    "cake",
    "candle_cake",
    "bed",
    "door",
    "trapdoor",
    "fence_gate",
    "coral_fan",
    "dead_brain",
    "dead_bubble",
    "dead_fire",
    "dead_horn",
    "dead_tube_coral_fan",
    "hanging_roots",
    "spore_blossom",
    "glow_lichen",
    "vine",
    "cave_vines",
    "scaffolding",
    "ladder",
    "torch",
    "lantern",
    "campfire",
    "soul_fire",
    "powder_snow",
    "dripstone",
    "mycelium",
    "netherrack",
    "nylium",
    "grass_block",
    "dirt_path",
    "farmland",
    "podzol",
    "rooted_dirt",
    "coarse_dirt",
    "mud",
    "dirt",
    "clay",
    "gravel",
    "soul_sand",
    "soul_soil",
    "magma_block",
    "lodestone",
    "infested",
    "sapling",
    "mushroom",
    "moss_block",
    "moss_carpet",
    "sculk",
    "sponge",
    "target",
    "tnt",
    "obsidian",
    "crying_obsidian",
    "bedrock",
    "barrier",
    "structure_void",
    "bone_block",
    "hopper",
    "dropper",
    "dispenser",
)

_TRIM_SUBSTR = (
    "stairs",
    "slab",
    "fence",
    "wall",
    "pane",
    "bars",
    "chain",
    "leaves",
    "glass",
)

STYLE_STRUCTURAL: dict[str, tuple[str, ...]] = {
    "industrial": (
        "iron_block",
        "iron_bars",
        "stone_bricks",
        "stone",
        "cobblestone",
        "deepslate_bricks",
        "polished_deepslate",
        "cobbled_deepslate",
        "gray_concrete",
        "light_gray_concrete",
        "black_concrete",
        "smooth_stone",
        "glass",
        "waxed_copper",
        "copper_block",
        "chain",
    ),
    "medieval": (
        "cobblestone",
        "stone_bricks",
        "mossy_stone_bricks",
        "oak_planks",
        "oak_log",
        "spruce_planks",
        "spruce_log",
        "dark_oak_planks",
        "dark_oak_log",
        "bricks",
        "stone",
        "glass_pane",
        "glass",
    ),
    "chinese": (
        "dark_oak",
        "spruce",
        "oak_planks",
        "stone_bricks",
        "stone",
        "cobblestone",
        "red_wool",
        "white_wool",
        "cherry_planks",
        "cherry_log",
        "gold_block",
        "smooth_stone",
    ),
    "japanese": (
        "spruce",
        "dark_oak",
        "oak_planks",
        "white_wool",
        "stone",
        "cobblestone",
        "stone_bricks",
        "cherry",
        "bamboo_planks",
        "smooth_stone",
    ),
    "modern": (
        "white_concrete",
        "gray_concrete",
        "light_gray_concrete",
        "black_concrete",
        "quartz_block",
        "smooth_quartz",
        "smooth_stone",
        "glass",
        "glass_pane",
        "iron_block",
        "white_wool",
        "stone",
    ),
    "fantasy": (
        "stone_bricks",
        "deepslate",
        "dark_oak",
        "spruce",
        "purple_wool",
        "amethyst_block",
        "prismarine",
        "purpur_block",
        "glass",
        "cobblestone",
    ),
    "rustic": (
        "oak_planks",
        "oak_log",
        "spruce_planks",
        "spruce_log",
        "cobblestone",
        "stone",
        "hay_block",
        "stripped_oak",
        "stripped_spruce",
    ),
    "european": (
        "stone_bricks",
        "cobblestone",
        "oak_planks",
        "spruce_planks",
        "bricks",
        "stone",
        "glass_pane",
        "glass",
        "smooth_stone",
    ),
    "desert": (
        "sandstone",
        "smooth_sandstone",
        "cut_sandstone",
        "red_sandstone",
        "terracotta",
        "sand",
        "smooth_stone",
        "glass",
    ),
    "western": (
        "oak_planks",
        "oak_log",
        "spruce_planks",
        "cobblestone",
        "hay_block",
        "stone",
        "stripped_oak",
    ),
    "scifi": (
        "iron_block",
        "quartz_block",
        "glass",
        "cyan_concrete",
        "light_blue_concrete",
        "sea_lantern",
        "smooth_stone",
        "white_concrete",
    ),
    "unknown": (
        "stone",
        "cobblestone",
        "oak_planks",
        "stone_bricks",
        "glass",
        "spruce_planks",
        "bricks",
    ),
}

_FALLBACK_WALL = (
    "stone_bricks",
    "cobblestone",
    "stone",
    "oak_planks",
    "spruce_planks",
    "gray_concrete",
    "bricks",
)
_FALLBACK_FLOOR = (
    "oak_planks",
    "spruce_planks",
    "smooth_stone",
    "stone",
    "cobblestone",
    "gray_concrete",
    "stone_bricks",
)


@dataclass
class LookHardenReport:
    ok: bool
    actions: list[str] = field(default_factory=list)
    metrics_before: dict[str, Any] = field(default_factory=dict)
    metrics_after: dict[str, Any] = field(default_factory=dict)
    palette_stats: dict[str, Any] = field(default_factory=dict)
    uniqu_before: int = 0
    uniqu_after: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _short(name: str) -> str:
    if ":" in name:
        return name.split(":", 1)[1]
    return name


def _token_match(short: str, tok: str) -> bool:
    """Match style token against block short name without false hits (stone vs dripstone)."""
    s = short.lower()
    tk = tok.lower()
    if s == tk:
        return True
    if s.startswith(tk + "_") or s.endswith("_" + tk) or ("_" + tk + "_") in s:
        return True
    # multi-part tokens may appear mid-name (waxed_cut_copper)
    if "_" in tk and tk in s:
        return True
    return False



def _is_junk(short: str) -> bool:
    s = short.lower()
    if s == "air":
        return False
    if s == "snow" or s.startswith("snow_"):
        return True
    if s in ("fire", "soul_fire", "bamboo"):
        return True
    # avoid substring false positives: bedrock, bamboo_planks, etc.
    skip_as_substr = {"bamboo", "bed", "pot", "head", "door"}
    for tok in _JUNK_SUBSTR:
        if tok in skip_as_substr:
            continue
        if tok in s:
            return True
    if s.endswith("_bed") or s.endswith("_door") or s == "door":
        return True
    if s.endswith("_pot") or s == "flower_pot":
        return True
    if s.endswith("_head") or s.endswith("_skull"):
        return True
    return False


def _is_trim(short: str) -> bool:
    s = short.lower()
    if _is_junk(s):
        return False
    for tok in _TRIM_SUBSTR:
        if tok in s:
            return True
    return False


def _is_full_structural(short: str) -> bool:
    s = short.lower()
    if s in ("air",) or _is_junk(s) or _is_trim(s):
        return False
    if "coral" in s and "block" not in s:
        return False
    return True


def _name_to_id(palette: dict[int, str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, name in palette.items():
        out[_short(name)] = int(i)
    return out


def _resolve_id(name_to_id: dict[str, int], candidates: tuple[str, ...] | list[str]) -> int:
    for c in candidates:
        if c in name_to_id and name_to_id[c] > 0:
            return int(name_to_id[c])
    for c in candidates:
        for pn, pid in name_to_id.items():
            if pid > 0 and (_token_match(pn, c) or _token_match(c, pn)):
                return int(pid)
    return 1


def style_token_list(style: str | None) -> tuple[str, ...]:
    key = (style or "unknown").strip().lower() or "unknown"
    if key in STYLE_STRUCTURAL:
        return STYLE_STRUCTURAL[key]
    return STYLE_STRUCTURAL["unknown"]


def whitelist_ids(palette: dict[int, str], style: str | None) -> set[int]:
    tokens = style_token_list(style)
    ids: set[int] = set()
    for i, name in palette.items():
        if int(i) <= 0:
            continue
        s = _short(name).lower()
        if _is_junk(s):
            continue
        for tok in tokens:
            if _token_match(s, tok):
                ids.add(int(i))
                break
    return ids


def pick_fill_ids(
    voxels: np.ndarray,
    palette: dict[int, str],
    style: str | None = None,
    role_materials: dict[str, int] | None = None,
) -> tuple[int, int, dict[str, Any]]:
    """Pick wall/floor ids. When role_materials is set (scaffold path), prefer it
    so look_harden does not scramble role-based paints into majority mush.
    """
    if role_materials:
        roles, info = resolve_role_materials(palette, style)
        # overlay provided roles
        for k, v in role_materials.items():
            if v is not None and int(v) > 0:
                roles[k] = int(v)
        info = dict(info)
        info["source"] = "role_materials_override"
        info["roles"] = dict(roles)
        info["role_names"] = {
            k: _short(palette.get(int(v), "?")) for k, v in roles.items()
        }
        info["wall_id"] = int(roles.get("wall") or 1)
        info["floor_id"] = int(roles.get("floor") or info["wall_id"])
        info["roof_id"] = int(roles.get("roof") or info["wall_id"])
        info["foundation_id"] = int(roles.get("foundation") or info["wall_id"])
        info["accent_id"] = int(roles.get("accent") or info["wall_id"])
        info["window_frame_id"] = int(roles.get("window_frame") or info["accent_id"])
        info["wall_name"] = _short(palette.get(info["wall_id"], "?"))
        info["floor_name"] = _short(palette.get(info["floor_id"], "?"))
        return int(info["wall_id"]), int(info["floor_id"]), info

    name_to_id = _name_to_id(palette)
    wl = whitelist_ids(palette, style)
    solid = np.asarray(voxels)
    solid_ids = solid[solid > 0]
    info: dict[str, Any] = {"style": style or "unknown"}

    counts: dict[int, int] = {}
    if solid_ids.size:
        ids, cts = np.unique(solid_ids, return_counts=True)
        for i, c in zip(ids.tolist(), cts.tolist()):
            s = _short(palette.get(int(i), str(i)))
            if _is_full_structural(s):
                counts[int(i)] = int(c)

    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    wall_id = None
    floor_id = None
    for bid, _c in ranked:
        if wl and bid not in wl:
            continue
        if wall_id is None:
            wall_id = bid
            continue
        if floor_id is None and bid != wall_id:
            floor_id = bid
            break
    if wall_id is None:
        for bid, _c in ranked:
            wall_id = bid
            break
    if floor_id is None:
        for bid, _c in ranked:
            if bid != wall_id:
                floor_id = bid
                break

    if wall_id is None:
        toks = style_token_list(style)
        wall_id = _resolve_id(name_to_id, list(toks) + list(_FALLBACK_WALL))
    if floor_id is None:
        toks = style_token_list(style)
        floor_prefs = [t for t in toks if "plank" in t or "concrete" in t or "smooth" in t]
        floor_id = _resolve_id(
            name_to_id,
            floor_prefs + list(_FALLBACK_FLOOR) + list(toks),
        )

    if floor_id == wall_id:
        alt = _resolve_id(name_to_id, _FALLBACK_FLOOR)
        if alt != wall_id:
            floor_id = alt

    # Enrich with full role fallbacks even on VAE path
    roles, rinfo = resolve_role_materials(palette, style)
    roles["wall"] = int(wall_id)
    roles["floor"] = int(floor_id)
    info.update(rinfo)
    info["roles"] = dict(roles)
    info["wall_id"] = int(wall_id)
    info["floor_id"] = int(floor_id)
    info["roof_id"] = int(roles.get("roof") or wall_id)
    info["foundation_id"] = int(roles.get("foundation") or wall_id)
    info["accent_id"] = int(roles.get("accent") or wall_id)
    info["window_frame_id"] = int(roles.get("window_frame") or roles.get("accent") or wall_id)
    info["wall_name"] = _short(palette.get(int(wall_id), "?"))
    info["floor_name"] = _short(palette.get(int(floor_id), "?"))
    info["source"] = "majority+style_roles"
    return int(wall_id), int(floor_id), info


def limit_palette(
    voxels: np.ndarray,
    palette: dict[int, str],
    *,
    style: str | None = None,
    top_k: int = 6,
    keep_trim_top: int = 2,
    force_keep: list[int] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    out = np.asarray(voxels, dtype=np.int16).copy()
    solid = out[out > 0]
    if solid.size == 0:
        return out, {"remapped": 0, "unique_before": 0, "unique_after": 0, "kept": []}

    ids, counts = np.unique(solid, return_counts=True)
    order = ids[np.argsort(-counts)]
    unique_before = int(len(order))
    wl = whitelist_ids(palette, style)

    struct_ranked: list[int] = []
    trim_ranked: list[int] = []
    junk_ids: list[int] = []

    for bid in order.tolist():
        bid = int(bid)
        s = _short(palette.get(bid, str(bid)))
        if _is_junk(s):
            junk_ids.append(bid)
        elif _is_trim(s):
            trim_ranked.append(bid)
        elif _is_full_structural(s):
            struct_ranked.append(bid)

    # Prefer style whitelist only — do NOT spill rainbow majority into kept set
    preferred = [b for b in struct_ranked if (not wl) or b in wl]
    rest = [b for b in struct_ranked if b not in preferred]
    struct_pick = preferred[: max(1, int(top_k))]
    # Force-keep role materials so scaffold paints survive palette limit
    for bid in force_keep or []:
        bid = int(bid)
        if bid > 0 and bid not in struct_pick:
            struct_pick.insert(0, bid)
    struct_pick = struct_pick[: max(len(struct_pick), int(top_k))]
    # de-dupe preserve order
    seen = set()
    struct_pick = [b for b in struct_pick if not (b in seen or seen.add(b))]

    name_to_id = _name_to_id(palette)
    # Always try to inject style defaults so industrial/medieval get sane blocks
    for tok in style_token_list(style):
        if len(struct_pick) >= int(top_k):
            break
        pid = name_to_id.get(tok)
        if pid is None:
            for pn, i in name_to_id.items():
                if _token_match(pn, tok) and _is_full_structural(pn) and not _is_junk(pn):
                    pid = i
                    break
        if pid and int(pid) > 0 and int(pid) not in struct_pick:
            struct_pick.append(int(pid))

    if len(struct_pick) < 2:
        # last resort: allow top structural from sample (still non-junk)
        for b in rest:
            if b not in struct_pick:
                struct_pick.append(b)
            if len(struct_pick) >= min(3, int(top_k)):
                break

    if not struct_pick:
        struct_pick = [_resolve_id(name_to_id, _FALLBACK_WALL)]

    trim_pick = trim_ranked[: max(0, int(keep_trim_top))]
    kept = list(dict.fromkeys(struct_pick + trim_pick))
    primary = struct_pick[0]
    secondary = struct_pick[1] if len(struct_pick) > 1 else primary

    mapping: dict[int, int] = {}
    for i, bid in enumerate(order.tolist()):
        bid = int(bid)
        if bid in kept:
            continue
        mapping[bid] = secondary if (i % 3 == 1 and secondary != primary) else primary

    remapped = 0
    for src, dst in mapping.items():
        mask = out == src
        n = int(mask.sum())
        if n:
            out[mask] = dst
            remapped += n

    unique_after = int(len(np.unique(out[out > 0]))) if (out > 0).any() else 0
    return out, {
        "remapped": remapped,
        "unique_before": unique_before,
        "unique_after": unique_after,
        "kept": [
            {
                "id": int(b),
                "name": _short(palette.get(int(b), "?")),
                "kind": (
                    "trim"
                    if _is_trim(_short(palette.get(int(b), "")))
                    else "structural"
                ),
            }
            for b in kept
        ],
        "junk_ids": junk_ids[:20],
        "mapping_size": len(mapping),
        "top_k": int(top_k),
    }


_PALETTE_REF: dict[int, str] | None = None
_JUNK_ID_CACHE: dict[int, bool] = {}


def _set_palette_ref(palette: dict[int, str] | None) -> None:
    global _PALETTE_REF, _JUNK_ID_CACHE
    _PALETTE_REF = palette
    _JUNK_ID_CACHE = {}


def _cell_is_nonstructural_mass(block_id: int) -> bool:
    bid = int(block_id)
    if bid <= 0:
        return False
    if bid in _JUNK_ID_CACHE:
        return _JUNK_ID_CACHE[bid]
    if _PALETTE_REF is None:
        return False
    s = _short(_PALETTE_REF.get(bid, ""))
    flag = _is_junk(s)
    _JUNK_ID_CACHE[bid] = flag
    return flag


def _is_fp_edge(fp: np.ndarray, x: int, z: int) -> bool:
    sx, sz = fp.shape
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, nz = x + dx, z + dz
        if not (0 <= nx < sx and 0 <= nz < sz) or not fp[nx, nz]:
            return True
    return False


def _perimeter_mask(fp: np.ndarray) -> np.ndarray:
    """True on footprint cells that touch outside or non-fp neighbor (outer ring)."""
    sx, sz = fp.shape
    peri = np.zeros_like(fp, dtype=bool)
    xs, zs = np.where(fp)
    for x, z in zip(xs.tolist(), zs.tolist()):
        if _is_fp_edge(fp, int(x), int(z)):
            peri[x, z] = True
    return peri



def _is_glass_name(short: str) -> bool:
    s = short.lower()
    return "glass" in s  # glass / glass_pane / stained_glass*


def _glass_ids_from_palette(palette: dict[int, str] | None) -> set[int]:
    if not palette:
        return set()
    out: set[int] = set()
    for i, name in palette.items():
        if int(i) <= 0:
            continue
        if _is_glass_name(_short(name)):
            out.add(int(i))
    return out


def _resolve_glass_id(palette: dict[int, str] | None, style: str | None = None) -> int:
    """Prefer glass_pane then glass from style whitelist / palette."""
    if not palette:
        return 0
    name_to_id = _name_to_id(palette)
    # style-preferred order
    preferred: list[str] = []
    toks = style_token_list(style)
    for t in toks:
        tl = t.lower()
        if "glass" in tl:
            preferred.append(tl)
    for c in preferred + ["glass_pane", "glass", "white_stained_glass_pane", "white_stained_glass"]:
        if c in name_to_id and name_to_id[c] > 0:
            return int(name_to_id[c])
    for pn, pid in name_to_id.items():
        if pid > 0 and _is_glass_name(pn):
            return int(pid)
    return 0


def _cell_is_glass(block_id: int) -> bool:
    pal = _PALETTE_REF
    if not pal or int(block_id) <= 0:
        return False
    name = pal.get(int(block_id))
    if not name:
        return False
    return _is_glass_name(_short(name))


def window_opening_count(
    voxels: np.ndarray,
    y0: int | None = None,
    y1: int | None = None,
    floor_ys: list[int] | None = None,
    style: str | None = None,
) -> dict[str, Any]:
    """Count perimeter openings classified as window-like (for A/B metrics).

    Returns both window_cells (kept openings) and glass_cells (pane blocks).
    Pass style= so strict_window_openings styles match generation-time sealing.
    """
    out = np.asarray(voxels)
    solid = out > 0
    if not solid.any():
        return {"window_cells": 0, "window_components": 0, "defect_cells": 0, "glass_cells": 0}
    fp, _ = _footprint(solid)
    peri = _perimeter_mask(fp)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    if ys.size == 0:
        return {"window_cells": 0, "window_components": 0, "defect_cells": 0, "glass_cells": 0}
    lo = int(ys.min()) if y0 is None else int(y0)
    hi = int(ys.max()) if y1 is None else int(y1)
    peaks = list(floor_ys) if floor_ys is not None else list(_floor_metrics(solid).get("y_peaks") or [])
    mask, info = detect_window_mask(
        out, peri=peri, y0=lo, y1=hi, floor_ys=peaks, preserve=True, style=style
    )
    return {
        "window_cells": int(info.get("window_cells", 0)),
        "window_components": int(info.get("window_components", 0)),
        "defect_cells": int(info.get("defect_cells", 0)),
        "glass_cells": int(info.get("glass_cells", 0)),
        "strict": bool(info.get("strict")),
    }


def detect_window_mask(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    y0: int,
    y1: int,
    floor_ys: list[int],
    preserve: bool = True,
    style: str | None = None,
    strict: bool | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Mark perimeter cells that look like intentional window openings.

    Window heuristics (any is enough):
    - already glass / pane
    - rectangular air blob: height 1–2, width 1–3, size ≈ h*w, mid-wall between floors
    - repeating similar openings at same relative Y on ≥2 faces / sides

    When preserve=False, returns empty mask (fill-all behaviour).
    """
    out = np.asarray(voxels)
    sx, sy, sz = out.shape
    win = np.zeros_like(out, dtype=bool)
    info: dict[str, Any] = {
        "window_cells": 0,
        "window_components": 0,
        "defect_cells": 0,
        "glass_cells": 0,
        "components": [],
    }
    if not preserve:
        return win, info

    style_l = (style or "").strip().lower()
    if strict is None:
        # Facade knobs or known inflated-opening styles
        fr = style_facade_rules(style_l) if style_l else {}
        strict = bool(fr.get("strict_window_openings")) or style_l in (
            "fantasy",
            "western",
            "modern",
        )
    info["strict"] = bool(strict)
    # Weak peri columns (mass 0–2) are eaves tips / jagged footprint, not wall face.
    # Counting their air as windows inflated fantasy/western window_cells (~739/770).
    min_col_mass = 3 if strict else 2
    info["min_col_mass"] = int(min_col_mass)

    floor_set = {int(y) for y in floor_ys if 0 <= int(y) < sy}
    # never treat floors / roof / ground band as window body
    forbidden_y = set(floor_set) | {int(y0), int(y1)}

    col_mass = np.zeros(peri.shape, dtype=np.int16)
    px_all, pz_all = np.where(peri)
    for x, z in zip(px_all.tolist(), pz_all.tolist()):
        col_mass[x, z] = int((out[x, max(0, y0) : min(sy, y1 + 1), z] > 0).sum())
    wall_peri = peri & (col_mass >= int(min_col_mass))

    # --- glass already present on wall-strength perimeter ---
    glass_cells = 0
    px, pz = np.where(wall_peri)
    for x, z in zip(px.tolist(), pz.tolist()):
        for y in range(max(0, y0), min(sy, y1 + 1)):
            bid = int(out[x, y, z])
            if bid > 0 and _cell_is_glass(bid):
                win[x, y, z] = True
                glass_cells += 1
    info["glass_cells"] = glass_cells

    # --- connected air components on perimeter (between y0+1 .. y1-1) ---
    visited = np.zeros_like(out, dtype=bool)
    comps: list[dict[str, Any]] = []

    def neighbors(x: int, y: int, z: int):
        for dx, dy, dz in (
            (1, 0, 0),
            (-1, 0, 0),
            (0, 1, 0),
            (0, -1, 0),
            (0, 0, 1),
            (0, 0, -1),
        ):
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz:
                yield nx, ny, nz

    air_lo = int(y0) + 1
    air_hi = int(y1) - 1
    if air_hi < air_lo:
        info["window_cells"] = int(win.sum())
        return win, info

    px, pz = np.where(wall_peri)
    for x, z in zip(px.tolist(), pz.tolist()):
        for y in range(air_lo, air_hi + 1):
            if visited[x, y, z] or out[x, y, z] != 0:
                continue
            if y in forbidden_y:
                continue
            # BFS on wall-strength peri only
            stack = [(x, y, z)]
            visited[x, y, z] = True
            cells: list[tuple[int, int, int]] = []
            while stack:
                cx, cy, cz = stack.pop()
                cells.append((cx, cy, cz))
                for nx, ny, nz in neighbors(cx, cy, cz):
                    if visited[nx, ny, nz]:
                        continue
                    if not wall_peri[nx, nz]:
                        continue
                    if out[nx, ny, nz] != 0:
                        continue
                    if ny < air_lo or ny > air_hi or ny in forbidden_y:
                        continue
                    visited[nx, ny, nz] = True
                    stack.append((nx, ny, nz))

            ys_c = [c[1] for c in cells]
            xz = {(c[0], c[2]) for c in cells}
            h = int(max(ys_c) - min(ys_c) + 1)
            w = int(len(xz))
            size = len(cells)
            # rectangularity: size should be close to h*w (single layer wall)
            rect_target = h * w
            rectangular = size <= rect_target + 1 and size >= max(1, rect_target - 1)

            # mid-wall: not touching floor_set / roof / ground
            ymin, ymax = min(ys_c), max(ys_c)
            touches_floor = any((ymin - 1) in floor_set or (ymax + 1) in floor_set for _ in (0,))
            # stronger: opening entirely in an inter-floor band
            mid = True
            if ymin <= y0 or ymax >= y1:
                mid = False
            if ymin in floor_set or ymax in floor_set:
                mid = False

            # face hint for repeating pattern
            # crude: which bbox edge of footprint
            xs_all = [c[0] for c in cells]
            zs_all = [c[2] for c in cells]
            # classify by mean position vs footprint center later
            face = "unk"
            comps.append(
                {
                    "cells": cells,
                    "h": h,
                    "w": w,
                    "size": size,
                    "rectangular": rectangular,
                    "mid": mid,
                    "ymin": ymin,
                    "ymax": ymax,
                    "y_mid": float(sum(ys_c) / len(ys_c)),
                    "face": face,
                    "mean_x": float(sum(xs_all) / len(xs_all)),
                    "mean_z": float(sum(zs_all) / len(zs_all)),
                }
            )

    # face assignment using footprint bbox
    if peri.any():
        pxs, pzs = np.where(peri)
        minx, maxx = int(pxs.min()), int(pxs.max())
        minz, maxz = int(pzs.min()), int(pzs.max())
        for c in comps:
            mx, mz = c["mean_x"], c["mean_z"]
            dist = {
                "x0": abs(mx - minx),
                "x1": abs(mx - maxx),
                "z0": abs(mz - minz),
                "z1": abs(mz - maxz),
            }
            c["face"] = min(dist, key=dist.get)

    # repeating: same-ish y_mid (±1) on ≥2 different faces, h/w in window range
    repeat_keys: dict[int, set[str]] = {}
    for c in comps:
        if not (1 <= c["h"] <= 2 and 1 <= c["w"] <= 3):
            continue
        key = int(round(c["y_mid"]))
        repeat_keys.setdefault(key, set()).add(c["face"])
    repeating_ys = {k for k, faces in repeat_keys.items() if len(faces) >= 2}

    defect_cells = 0
    window_comps = 0
    for c in comps:
        h, w, size = c["h"], c["w"], c["size"]
        is_win = False
        reason = ""
        # size-1 irregular at floor junction → defect
        if size <= 2 and not c["rectangular"] and not c["mid"]:
            is_win = False
            reason = "tiny_irregular"
        elif strict:
            # Phase F: wall-column filter already dropped eaves-tip holes.
            # Keep rect mid or repeating bands; still drop near_rect_mid.
            if (
                1 <= h <= 2
                and 1 <= w <= 2
                and c["rectangular"]
                and c["mid"]
                and size <= 4
            ):
                is_win = True
                reason = "rect_mid_strict"
            elif (
                1 <= h <= 2
                and 1 <= w <= 3
                and c["rectangular"]
                and int(round(c["y_mid"])) in repeating_ys
                and size <= 6
            ):
                is_win = True
                reason = "rect_repeat_strict"
            else:
                is_win = False
                reason = "defect_strict"
        elif 1 <= h <= 2 and 1 <= w <= 3 and c["rectangular"] and c["mid"]:
            is_win = True
            reason = "rect_mid"
        elif 1 <= h <= 2 and 1 <= w <= 3 and c["rectangular"] and int(round(c["y_mid"])) in repeating_ys:
            is_win = True
            reason = "rect_repeat"
        elif size <= 6 and 1 <= h <= 2 and 1 <= w <= 3 and c["mid"]:
            # near-rect mid openings (non-strict styles only)
            is_win = True
            reason = "near_rect_mid"
        else:
            # ragged / tall / wide / roof-touching → defect
            is_win = False
            reason = "defect"

        c["is_window"] = is_win
        c["reason"] = reason
        if is_win:
            window_comps += 1
            for cx, cy, cz in c["cells"]:
                win[cx, cy, cz] = True
        else:
            defect_cells += size

    info["window_components"] = window_comps
    info["window_cells"] = int(win.sum())
    info["defect_cells"] = defect_cells
    # compact component summary (no cell lists)
    info["components"] = [
        {
            "h": c["h"],
            "w": c["w"],
            "size": c["size"],
            "is_window": c["is_window"],
            "reason": c["reason"],
            "face": c["face"],
            "y_mid": c["y_mid"],
        }
        for c in comps
    ]
    return win, info


def wall_hole_count(voxels: np.ndarray, y0: int | None = None, y1: int | None = None) -> int:
    """Count air cells on footprint perimeter between y0..y1 (shell gaps)."""
    out = np.asarray(voxels)
    solid = out > 0
    if not solid.any():
        return 0
    fp, _ = _footprint(solid)
    peri = _perimeter_mask(fp)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    if ys.size == 0:
        return 0
    lo = int(ys.min()) if y0 is None else int(y0)
    hi = int(ys.max()) if y1 is None else int(y1)
    holes = 0
    xs, zs = np.where(peri)
    for x, z in zip(xs.tolist(), zs.tolist()):
        # skip skinny columns
        if int((out[x, lo : hi + 1, z] > 0).sum()) < 2:
            continue
        for y in range(lo, hi + 1):
            if out[x, y, z] == 0:
                holes += 1
    return int(holes)


def floor_flatness_score(voxels: np.ndarray, floor_ys: list[int] | None = None) -> dict[str, Any]:
    """Fraction of active footprint filled at each floor Y (mean = flatness)."""
    out = np.asarray(voxels)
    solid = out > 0
    if not solid.any():
        return {"floor_flatness": 0.0, "per_floor": {}, "floor_ys": []}
    fp, fp_n = _footprint(solid)
    if fp_n == 0:
        return {"floor_flatness": 0.0, "per_floor": {}, "floor_ys": []}
    ys = np.where(solid.any(axis=(0, 2)))[0]
    y0, y1 = int(ys.min()), int(ys.max())
    if floor_ys is None:
        floors = _floor_metrics(solid)
        floor_ys = list(floors["y_peaks"]) or [y0]
    # only columns with some mass count toward denom
    active = np.zeros_like(fp, dtype=bool)
    xs, zs = np.where(fp)
    for x, z in zip(xs.tolist(), zs.tolist()):
        if int((out[x, y0 : y1 + 1, z] > 0).sum()) >= 2:
            active[x, z] = True
    denom = int(active.sum()) or 1
    per: dict[str, float] = {}
    scores: list[float] = []
    for y in floor_ys:
        y = int(y)
        if y < 0 or y >= out.shape[1]:
            continue
        filled = int(((out[:, y, :] > 0) & active).sum())
        sc = float(filled / denom)
        per[str(y)] = sc
        scores.append(sc)
    return {
        "floor_flatness": float(sum(scores) / len(scores)) if scores else 0.0,
        "per_floor": per,
        "floor_ys": [int(y) for y in floor_ys],
    }



def harden_shell_and_floors_basic(
    voxels: np.ndarray,
    *,
    wall_id: int,
    floor_id: int,
    floor_spacing: int = 5,
    clear_interior_clutter: bool = True,
) -> tuple[np.ndarray, list[str]]:
    """Legacy shell/floors (pre shell-harden pass) for A/B baseline."""
    out = np.asarray(voxels, dtype=np.int16).copy()
    actions: list[str] = []
    solid = out > 0
    if not solid.any():
        return out, ["empty_skip"]

    sx, sy, sz = out.shape
    n_cc, sizes, labels = _connected_components(solid)
    if n_cc > 1 and sizes:
        best_label = 1
        best_count = 0
        for lab in range(1, n_cc + 1):
            c = int((labels == lab).sum())
            if c > best_count:
                best_count = c
                best_label = lab
        drop = (labels > 0) & (labels != best_label)
        n_drop = int(drop.sum())
        if n_drop:
            out[drop] = 0
            actions.append("drop_float_cc:%d" % n_drop)
            solid = out > 0

    fp, fp_n = _footprint(solid)
    if fp_n == 0:
        return out, actions + ["no_footprint"]

    ys = np.where(solid.any(axis=(0, 2)))[0]
    y0, y1 = int(ys.min()), int(ys.max())
    floors = _floor_metrics(solid)
    peaks = list(floors["y_peaks"])
    if not peaks:
        peaks = list(range(y0, y1 + 1, max(3, int(floor_spacing))))
    if y0 not in peaks:
        peaks = [y0] + peaks
    peaks = sorted({int(y) for y in peaks if 0 <= int(y) < sy})

    floor_added = 0
    xs, zs = np.where(fp)
    for y in peaks:
        for x, z in zip(xs.tolist(), zs.tolist()):
            col = out[x, :, z]
            if int((col[y0 : y1 + 1] > 0).sum()) < 1:
                continue
            if out[x, y, z] == 0 or _cell_is_nonstructural_mass(out[x, y, z]):
                out[x, y, z] = int(floor_id)
                floor_added += 1
            if clear_interior_clutter and y + 1 < sy and y + 1 < y1:
                if out[x, y + 1, z] != 0 and _cell_is_nonstructural_mass(out[x, y + 1, z]):
                    edge = False
                    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, nz = x + dx, z + dz
                        if not (0 <= nx < sx and 0 <= nz < sz) or not fp[nx, nz]:
                            edge = True
                            break
                    if not edge:
                        out[x, y + 1, z] = 0
    if floor_added:
        actions.append("flat_floors:%d@y=%s" % (floor_added, peaks))

    shell_added = 0
    shell_fixed = 0
    for x, z in zip(xs.tolist(), zs.tolist()):
        edge = False
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (0 <= nx < sx and 0 <= nz < sz) or not fp[nx, nz]:
                edge = True
                break
        if not edge:
            continue
        if int((out[x, y0 : y1 + 1, z] > 0).sum()) < 2:
            continue
        for y in range(y0, y1 + 1):
            if out[x, y, z] == 0:
                out[x, y, z] = int(wall_id)
                shell_added += 1
            elif _cell_is_nonstructural_mass(out[x, y, z]):
                out[x, y, z] = int(wall_id)
                shell_fixed += 1
    if shell_added or shell_fixed:
        actions.append("shell_wall:+%d/~%d" % (shell_added, shell_fixed))

    roof_added = 0
    for x, z in zip(xs.tolist(), zs.tolist()):
        if int((out[x, y0 : y1 + 1, z] > 0).sum()) < 3:
            continue
        if out[x, y1, z] == 0 or _cell_is_nonstructural_mass(out[x, y1, z]):
            out[x, y1, z] = int(wall_id)
            roof_added += 1
    if roof_added:
        actions.append("roof_cap:%d@y=%d" % (roof_added, y1))

    vol = int(out.size)
    if int((out > 0).sum()) > int(0.70 * vol) and min(out.shape) >= 5:
        trimmed = 0
        coords = []
        peak_set = set(peaks)
        for x in range(2, sx - 2):
            for y in range(2, sy - 2):
                for z in range(2, sz - 2):
                    if out[x, y, z] == 0:
                        continue
                    if y in peak_set:
                        continue
                    edge = False
                    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, nz = x + dx, z + dz
                        if not (0 <= nx < sx and 0 <= nz < sz) or not fp[nx, nz]:
                            edge = True
                            break
                    if edge:
                        continue
                    block = out[x - 1 : x + 2, y - 1 : y + 2, z - 1 : z + 2]
                    coords.append((int((block > 0).sum()), x, y, z))
        coords.sort(reverse=True)
        cap = int(0.62 * vol)
        for score, x, y, z in coords:
            if int((out > 0).sum()) <= cap:
                break
            if score < 16:
                break
            out[x, y, z] = 0
            trimmed += 1
        if trimmed:
            actions.append("interior_trim:%d" % trimmed)

    return out, actions


def harden_shell_and_floors(
    voxels: np.ndarray,
    *,
    wall_id: int,
    floor_id: int,
    floor_spacing: int = 5,
    clear_interior_clutter: bool = True,
    shell_thickness: int = 1,
    fill_wall_holes: bool = True,
    regular_floors: bool = True,
    hollow_floors: bool = True,
    smooth_roof: bool = True,
    preserve_windows: bool = True,
    place_window_glass: bool = True,
    glass_id: int = 0,
    facade_detail: bool = True,
    style: str | None = None,
    palette: dict[int, str] | None = None,
    use_knowledge: bool = True,
    role_materials: dict[str, int] | None = None,
) -> tuple[np.ndarray, list[str]]:
    """Stronger shell continuity + ring floor slabs + cheap roof tidy.

    - Perimeter wall filled (optional 1-block thickness inward).
    - With preserve_windows (default): keep window-like openings; fill only
      tiny/irregular perimeter defects. Optionally place glass in openings.
    - With preserve_windows=False: fill-all (legacy strong shell).
    - Floors at regular Y spacing as walkable rings (not full footprint fill).
    - Roof cap + single-cell dip fill; trim lonely eaves spikes.
    """
    out = np.asarray(voxels, dtype=np.int16).copy()
    actions: list[str] = []
    solid = out > 0
    if not solid.any():
        return out, ["empty_skip"]

    sx, sy, sz = out.shape
    n_cc, sizes, labels = _connected_components(solid)
    if n_cc > 1 and sizes:
        best_label = 1
        best_count = 0
        for lab in range(1, n_cc + 1):
            c = int((labels == lab).sum())
            if c > best_count:
                best_count = c
                best_label = lab
        drop = (labels > 0) & (labels != best_label)
        n_drop = int(drop.sum())
        if n_drop:
            out[drop] = 0
            actions.append("drop_float_cc:%d" % n_drop)
            solid = out > 0

    fp, fp_n = _footprint(solid)
    if fp_n == 0:
        return out, actions + ["no_footprint"]

    ys = np.where(solid.any(axis=(0, 2)))[0]
    y0, y1 = int(ys.min()), int(ys.max())
    spacing = _clamp_floor_spacing(int(floor_spacing))
    if hollow_floors:
        spacing = max(int(spacing), 6)

    # --- floor Y schedule: peaks ∪ regular grid ---
    floors = _floor_metrics(solid)
    peaks = list(floors["y_peaks"])
    if regular_floors:
        grid = list(range(y0, y1, spacing))  # exclude roof y1
        if not grid:
            grid = [y0]
        merged = list(grid)
        for p in peaks:
            p = int(p)
            if p <= y0 or p >= y1:
                continue
            if min(abs(p - g) for g in merged) >= max(2, spacing // 2):
                merged.append(p)
        peaks = merged
    if not peaks:
        peaks = list(range(y0, y1, spacing)) or [y0]
    if y0 not in peaks:
        peaks = [y0] + peaks
    peaks = [int(y) for y in peaks if 0 <= int(y) < sy and int(y) < y1]
    peaks = sorted(set(peaks))
    # enforce min story clear between consecutive floors (knowledge)
    min_gap = max(2, int(knowledge_defaults().get("min_story_clear", 3)))
    merged2: list[int] = []
    for y in peaks:
        if merged2 and y - merged2[-1] < min_gap:
            continue
        merged2.append(y)
    peaks = merged2 or [y0]

    # Active columns: enough mass to be part of the building
    xs_fp, zs_fp = np.where(fp)
    active = np.zeros_like(fp, dtype=bool)
    for x, z in zip(xs_fp.tolist(), zs_fp.tolist()):
        if int((out[x, y0 : y1 + 1, z] > 0).sum()) >= 2:
            active[x, z] = True
    peri = _perimeter_mask(fp)

    # --- detect windows BEFORE shell fill (on current volume) ---
    win_mask, win_info = detect_window_mask(
        out,
        peri=peri,
        y0=y0,
        y1=y1,
        floor_ys=peaks,
        preserve=bool(preserve_windows),
        style=style,
    )
    if preserve_windows:
        actions.append(
            "windows:keep=%d_cells/%d_comp defect=%d glass=%d"
            % (
                int(win_info.get("window_cells", 0)),
                int(win_info.get("window_components", 0)),
                int(win_info.get("defect_cells", 0)),
                int(win_info.get("glass_cells", 0)),
            )
        )
    else:
        actions.append("windows:fill_all")

    gid = int(glass_id) if int(glass_id) > 0 else 0
    do_glass = bool(place_window_glass) and bool(preserve_windows) and gid > 0

    # --- regular floor slabs (ring / edge by default so rooms stay open) ---
    floor_added = 0
    floor_fixed = 0
    floor_cleared = 0
    peak_set = set(int(y) for y in peaks)
    # Dilate perimeter into a walkable ring inside active footprint
    ring = peri.copy()
    if hollow_floors and active.any():
        xs_p, zs_p = np.where(peri & active)
        for x, z in zip(xs_p.tolist(), zs_p.tolist()):
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    xx, zz = x + dx, z + dz
                    if 0 <= xx < sx and 0 <= zz < sz and active[xx, zz]:
                        ring[xx, zz] = True
        # No X-corridor: cross beams read as scaffolds through the room.
        ring &= active
        floor_mask = ring
        actions.append("hollow_floors:ring_no_cross")
    else:
        floor_mask = active
        actions.append("hollow_floors:off")
    ax, az = np.where(floor_mask)
    for y in peaks:
        for x, z in zip(ax.tolist(), az.tolist()):
            cur = int(out[x, y, z])
            if cur == 0:
                out[x, y, z] = int(floor_id)
                floor_added += 1
            elif _cell_is_nonstructural_mass(cur) and not _cell_is_glass(cur):
                out[x, y, z] = int(floor_id)
                floor_fixed += 1
            if clear_interior_clutter and y + 1 < sy and y + 1 < y1:
                above = int(out[x, y + 1, z])
                if (
                    above != 0
                    and _cell_is_nonstructural_mass(above)
                    and not peri[x, z]
                    and not _cell_is_glass(above)
                ):
                    out[x, y + 1, z] = 0
        # Carve center of full slabs left by older scaffolds (open the room)
        if hollow_floors and active.any():
            axs2, azs2 = np.where(active & (~floor_mask))
            for x, z in zip(axs2.tolist(), azs2.tolist()):
                if peri[x, z]:
                    continue
                cur = int(out[x, y, z])
                if cur == int(floor_id) or (
                    cur > 0 and _cell_is_nonstructural_mass(cur) and not _cell_is_glass(cur)
                ):
                    # keep a denser ground walk-ring; still clear deep interior on y0
                    out[x, y, z] = 0
                    floor_cleared += 1
    if floor_added or floor_fixed or floor_cleared:
        actions.append(
            "flat_floors:+%d/~%d/-%d@y=%s" % (floor_added, floor_fixed, floor_cleared, peaks)
        )

    # --- outer shell: solid perimeter wall (skip window mask) ---
    shell_added = 0
    shell_fixed = 0
    glass_placed = 0
    windows_left = 0
    px, pz = np.where(peri & active)
    for x, z in zip(px.tolist(), pz.tolist()):
        for y in range(y0, y1 + 1):
            if y in peak_set:
                if out[x, y, z] == 0 or (
                    _cell_is_nonstructural_mass(out[x, y, z]) and not _cell_is_glass(out[x, y, z])
                ):
                    out[x, y, z] = int(floor_id)
                    shell_fixed += 1
                continue
            # existing glass: keep only when preserving windows; else wall over
            if out[x, y, z] > 0 and _cell_is_glass(out[x, y, z]):
                if preserve_windows:
                    windows_left += 1
                    continue
                out[x, y, z] = int(wall_id)
                shell_fixed += 1
                continue
            if win_mask[x, y, z]:
                # intentional opening
                if out[x, y, z] == 0:
                    if do_glass:
                        out[x, y, z] = gid
                        glass_placed += 1
                    else:
                        windows_left += 1
                elif _cell_is_nonstructural_mass(out[x, y, z]):
                    # junk in window slot → clear or glass
                    if do_glass:
                        out[x, y, z] = gid
                        glass_placed += 1
                    else:
                        out[x, y, z] = 0
                        windows_left += 1
                else:
                    windows_left += 1
                continue
            if out[x, y, z] == 0:
                out[x, y, z] = int(wall_id)
                shell_added += 1
            elif _cell_is_nonstructural_mass(out[x, y, z]):
                out[x, y, z] = int(wall_id)
                shell_fixed += 1
    if shell_added or shell_fixed:
        actions.append("shell_wall:+%d/~%d" % (shell_added, shell_fixed))
    if glass_placed:
        actions.append("window_glass:%d" % glass_placed)
    if windows_left and preserve_windows:
        actions.append("windows_open:%d" % windows_left)

    # Optional thicker wall: shell_thickness>=2 adds one inward ring
    thick_added = 0
    if int(shell_thickness) >= 2:
        inner_ring = np.zeros_like(fp, dtype=bool)
        for x, z in zip(xs_fp.tolist(), zs_fp.tolist()):
            if peri[x, z] or not active[x, z]:
                continue
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = x + dx, z + dz
                if 0 <= nx < sx and 0 <= nz < sz and peri[nx, nz]:
                    inner_ring[x, z] = True
                    break
        ix, iz = np.where(inner_ring)
        for x, z in zip(ix.tolist(), iz.tolist()):
            for y in range(y0, y1 + 1):
                if y in peak_set:
                    continue
                if out[x, y, z] != 0 and not _cell_is_nonstructural_mass(out[x, y, z]):
                    continue
                ok = False
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, nz = x + dx, z + dz
                    if 0 <= nx < sx and 0 <= nz < sz and peri[nx, nz] and out[nx, y, nz] > 0:
                        # don't thicken behind an open window cell
                        if preserve_windows and win_mask[nx, y, nz]:
                            continue
                        if preserve_windows and _cell_is_glass(int(out[nx, y, nz])):
                            continue
                        ok = True
                        break
                if not ok:
                    continue
                if out[x, y, z] == 0 or _cell_is_nonstructural_mass(out[x, y, z]):
                    out[x, y, z] = int(wall_id)
                    thick_added += 1
        if thick_added:
            actions.append("shell_thickness:%d" % thick_added)

    # --- fill remaining wall holes (continuity) — skip windows ---
    hole_filled = 0
    if fill_wall_holes:
        _strict_holes = bool(
            (style_facade_rules(style) if style else {}).get("strict_window_openings")
        ) or (str(style or "").lower() in ("fantasy", "western", "modern"))
        _hole_passes = 3 if _strict_holes else 2
        for _pass in range(_hole_passes):
            filled_this = 0
            for x, z in zip(px.tolist(), pz.tolist()):
                for y in range(y0, y1 + 1):
                    if out[x, y, z] != 0:
                        continue
                    if preserve_windows and win_mask[x, y, z]:
                        continue
                    # never seal existing door blocks / openings beside a door
                    cur0 = int(out[x, y, z])
                    if cur0 == 0:
                        # skip if a neighboring peri cell already holds a door
                        skip_door = False
                        if _PALETTE_REF is not None:
                            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (0, 0)):
                                nx, nz = x + dx, z + dz
                                if not (0 <= nx < sx and 0 <= nz < sz):
                                    continue
                                sn = _short(_PALETTE_REF.get(int(out[nx, y, nz]), ""))
                                if sn.endswith("_door") or sn == "door":
                                    skip_door = True
                                    break
                        if skip_door:
                            continue
                    nsolid = 0
                    for dx, dy, dz in (
                        (0, 1, 0),
                        (0, -1, 0),
                        (1, 0, 0),
                        (-1, 0, 0),
                        (0, 0, 1),
                        (0, 0, -1),
                    ):
                        nx, ny, nz = x + dx, y + dy, z + dz
                        if 0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz and out[nx, ny, nz]:
                            nsolid += 1
                    above = y + 1 < sy and out[x, y + 1, z] > 0
                    below = y - 1 >= 0 and out[x, y - 1, z] > 0
                    if (above and below) or nsolid >= 2:
                        out[x, y, z] = int(wall_id)
                        filled_this += 1
            hole_filled += filled_this
            if filled_this == 0:
                break
        if hole_filled:
            actions.append("wall_holes:%d" % hole_filled)

    # --- roof cap + smooth eaves ---
    roof_added = 0
    roof_fixed = 0
    for x, z in zip(ax.tolist(), az.tolist()):
        if int((out[x, y0 : y1 + 1, z] > 0).sum()) < 3:
            continue
        if out[x, y1, z] == 0:
            out[x, y1, z] = int(wall_id)
            roof_added += 1
        elif _cell_is_nonstructural_mass(out[x, y1, z]) and not _cell_is_glass(out[x, y1, z]):
            out[x, y1, z] = int(wall_id)
            roof_fixed += 1
    if roof_added or roof_fixed:
        actions.append("roof_cap:+%d/~%d@y=%d" % (roof_added, roof_fixed, y1))

    if smooth_roof and y1 > y0 + 1:
        dip_filled = 0
        for x, z in zip(ax.tolist(), az.tolist()):
            if out[x, y1, z] == 0:
                continue
            y_dip = y1 - 1
            if out[x, y_dip, z] != 0:
                continue
            if preserve_windows and win_mask[x, y_dip, z]:
                continue
            n_roof = 0
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = x + dx, z + dz
                if 0 <= nx < sx and 0 <= nz < sz and out[nx, y1, nz] > 0:
                    n_roof += 1
            if n_roof >= 3:
                out[x, y_dip, z] = int(wall_id)
                dip_filled += 1
        if dip_filled:
            actions.append("roof_dip:%d" % dip_filled)

        trim_eaves = 0
        for x, z in zip(xs_fp.tolist(), zs_fp.tolist()):
            if out[x, y1, z] == 0:
                continue
            n_xz = 0
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = x + dx, z + dz
                if 0 <= nx < sx and 0 <= nz < sz and out[nx, y1, nz] > 0:
                    n_xz += 1
            below_ok = y1 > 0 and out[x, y1 - 1, z] > 0
            if n_xz <= 1 and not below_ok:
                out[x, y1, z] = 0
                trim_eaves += 1
        if trim_eaves:
            actions.append("eaves_trim:%d" % trim_eaves)

    # --- density trim (preserve floors + shell) ---
    vol = int(out.size)
    if int((out > 0).sum()) > int(0.70 * vol) and min(out.shape) >= 5:
        trimmed = 0
        coords = []
        peak_set2 = set(peaks) | {y1}
        for x in range(2, sx - 2):
            for y in range(2, sy - 2):
                for z in range(2, sz - 2):
                    if out[x, y, z] == 0:
                        continue
                    if y in peak_set2:
                        continue
                    if peri[x, z]:
                        continue
                    block = out[x - 1 : x + 2, y - 1 : y + 2, z - 1 : z + 2]
                    coords.append((int((block > 0).sum()), x, y, z))
        coords.sort(reverse=True)
        cap = int(0.62 * vol)
        for score, x, y, z in coords:
            if int((out > 0).sum()) <= cap:
                break
            if score < 16:
                break
            out[x, y, z] = 0
            trimmed += 1
        if trimmed:
            actions.append("interior_trim:%d" % trimmed)

    # --- facade rhythm (door / roof / eaves / banding / pillars) ---
    if facade_detail:
        out, fac_act, fac_stats = harden_facade(
            out,
            wall_id=int(wall_id),
            floor_id=int(floor_id),
            style=style,
            palette=palette,
            floor_ys=list(peaks),
            preserve_windows=bool(preserve_windows),
            win_mask=win_mask,
            place_door=True,
            place_door_block=True,
            roof_silhouette=True,
            eave_strip=True,
            facade_banding=True,
            corner_pillars=True,
            use_knowledge=bool(use_knowledge),
            roof_id=(role_materials or {}).get("roof"),
            foundation_id=(role_materials or {}).get("foundation"),
            accent_id=(role_materials or {}).get("accent"),
            window_frame_id=(role_materials or {}).get("window_frame"),
        )
        actions.extend(fac_act)
        # stash for callers via action tokens
        actions.append(
            "facade_stats:door=%d eave=%d band=%d pillar=%d pier=%d cornice=%d roof=%s"
            % (
                int(fac_stats.get("door_cells", 0)),
                int(fac_stats.get("eave_cells", 0)),
                int(fac_stats.get("banding_cells", 0)),
                int(fac_stats.get("pillar_cells", 0)),
                int(fac_stats.get("wall_pier_cells", 0)),
                int(fac_stats.get("cornice_cells", 0)),
                str(fac_stats.get("roof_mode") or ""),
            )
        )

    return out, actions



# ---------------------------------------------------------------------------

def place_foundation_band(
    voxels: np.ndarray,
    *,
    active: np.ndarray,
    peri: np.ndarray,
    y0: int,
    wall_id: int,
    floor_id: int,
    height: int = 1,
    foundation_id: int | None = None,
) -> tuple[np.ndarray, list[str], int]:
    """Footing band on perimeter at ground (knowledge: foundation before walls)."""
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    h = max(0, int(height))
    if h <= 0 or not peri.any():
        return out, actions, 0
    sy = out.shape[1]
    if foundation_id is not None and int(foundation_id) > 0:
        block = int(foundation_id)
    else:
        block = int(floor_id) if int(floor_id) > 0 and int(floor_id) != int(wall_id) else int(wall_id)
    added = 0
    for dy in range(h):
        y = int(y0) + dy
        if y < 0 or y >= sy:
            continue
        xs, zs = np.where(peri)
        for x, z in zip(xs.tolist(), zs.tolist()):
            if not active[x, z]:
                continue
            cur = int(out[x, y, z])
            if _PALETTE_REF is not None:
                sn = _short(_PALETTE_REF.get(cur, ""))
                if sn.endswith("_door") or sn == "door":
                    continue
            if cur == 0 or _cell_is_nonstructural_mass(cur) or (
                cur != block and not _cell_is_glass(cur)
            ):
                out[x, y, z] = block
                added += 1
    if added:
        actions.append("foundation:%d@h=%d" % (added, h))
    return out, actions, added


def place_window_rhythm(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    y0: int,
    y1: int,
    floor_ys: list[int],
    glass_id: int,
    wall_id: int,
    spacing: int = 3,
    from_corner: int = 2,
    from_floor: int = 1,
    win_h: int = 2,
    win_w: int = 1,
    frame_id: int = 0,
    place_sill_header: bool = True,
    floor_spacing: int = 5,
    max_bands: int = 4,
    fp: np.ndarray | None = None,
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    """Regular mid-story window columns on each facade (knowledge window rhythm).

    Uses evenly spaced story bands (floor_spacing) so irregular floor peaks do not
    glass every wall. Optional sill/header with frame_id above/below each opening.
    """
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    info: dict[str, Any] = {
        "placed_cells": 0,
        "columns": 0,
        "bands": [],
        "sill_header": 0,
    }
    if not peri.any() or int(glass_id) <= 0:
        return out, actions, info
    sy = out.shape[1]
    sp = max(2, int(spacing))
    fc = max(1, int(from_corner))
    ff = max(1, int(from_floor))
    wh = max(1, min(3, int(win_h)))
    ww = max(1, min(3, int(win_w)))
    fid = int(frame_id) if int(frame_id) > 0 else 0
    faces = _facade_face_cells(peri, fp=fp)
    placed = 0
    cols = 0
    sill_n = 0

    # Prefer regular story grid so dense floor peaks do not create glass curtains.
    fsp = max(3, int(floor_spacing) if floor_spacing else 5)
    story_ys = list(range(int(y0), int(y1) - 1, fsp))
    if int(y0) not in story_ys:
        story_ys = [int(y0)] + story_ys
    # Keep peaks that sit near the grid (tolerance) for irregular scaffolds.
    for p in floor_ys:
        p = int(p)
        if p <= y0 or p >= y1 - 2:
            continue
        if min(abs(p - g) for g in story_ys) >= max(2, fsp // 2):
            story_ys.append(p)
    story_ys = sorted(set(int(y) for y in story_ys if y0 <= int(y) < y1))

    bands: list[tuple[int, int]] = []
    for i, fy in enumerate(story_ys):
        nxt = story_ys[i + 1] if i + 1 < len(story_ys) else int(y1)
        # Need room for glass + optional sill/header without eating next floor / roof.
        clear = int(nxt) - int(fy)
        need = ff + wh + (1 if place_sill_header and fid > 0 else 0)
        if clear < need + 1:
            continue
        y_bot = int(fy) + ff
        y_top = y_bot + wh - 1
        # leave top cell under roof/deck for cornice
        if y_top >= int(y1) - 1:
            continue
        if y_top >= int(nxt) - (1 if place_sill_header else 0):
            continue
        bands.append((y_bot, y_top))
    if max_bands > 0 and len(bands) > int(max_bands):
        # keep lower bands (street-facing stories) first
        bands = bands[: int(max_bands)]
    # Fallback: one mid-wall band when schedule was too strict but wall is tall enough.
    if not bands and int(y1) - int(y0) >= ff + wh + 2:
        y_bot = int(y0) + max(ff, 2)
        y_top = min(y_bot + wh - 1, int(y1) - 2)
        if y_top >= y_bot:
            bands = [(y_bot, y_top)]
    info["bands"] = bands
    if not bands:
        return out, actions, info

    def _is_door(bid: int) -> bool:
        if bid <= 0 or _PALETTE_REF is None:
            return False
        sn = _short(_PALETTE_REF.get(bid, ""))
        return sn.endswith("_door") or sn == "door"

    def _can_carve(bid: int) -> bool:
        if bid == 0 or bid == int(wall_id) or _cell_is_nonstructural_mass(bid):
            return True
        if _cell_is_glass(bid) or _is_door(bid):
            return False
        if _PALETTE_REF is not None and _is_full_structural(
            _short(_PALETTE_REF.get(bid, "stone"))
        ):
            return True
        return False

    for face, cells in faces.items():
        if len(cells) < max(ww + 2, fc + ww):
            continue
        if face in ("x0", "x1"):
            cells_s = sorted(cells, key=lambda t: t[1])
        else:
            cells_s = sorted(cells, key=lambda t: t[0])
        face_fc = fc if len(cells_s) >= fc * 2 + ww + 1 else max(1, min(fc, 1))
        usable = cells_s[face_fc : max(face_fc, len(cells_s) - face_fc)]
        if not usable:
            continue
        # Center the column grid on the facade for regular rhythm.
        span = len(usable)
        n_slots = max(1, (span - ww) // sp + 1)
        used = (n_slots - 1) * sp + ww
        start = max(0, (span - used) // 2)
        idx = start
        while idx + ww <= len(usable):
            group = usable[idx : idx + ww]
            col_hit = False
            for y_bot, y_top in bands:
                for x, z in group:
                    for y in range(y_bot, y_top + 1):
                        cur = int(out[x, y, z])
                        if _cell_is_glass(cur):
                            col_hit = True
                            continue
                        if _is_door(cur):
                            continue
                        if _can_carve(cur):
                            out[x, y, z] = int(glass_id)
                            placed += 1
                            col_hit = True
                    if place_sill_header and fid > 0:
                        # sill just below glass (often on floor band peri)
                        ysill = y_bot - 1
                        if ysill >= int(y0) and ysill < sy:
                            for x, z in group:
                                cur = int(out[x, ysill, z])
                                if cur == fid or _cell_is_glass(cur) or _is_door(cur):
                                    continue
                                if (
                                    cur == 0
                                    or cur == int(wall_id)
                                    or _cell_is_nonstructural_mass(cur)
                                    or (
                                        _PALETTE_REF is not None
                                        and _is_full_structural(
                                            _short(_PALETTE_REF.get(cur, "stone"))
                                        )
                                    )
                                ):
                                    out[x, ysill, z] = fid
                                    sill_n += 1
                        yhead = y_top + 1
                        if yhead < int(y1) and yhead < sy:
                            for x, z in group:
                                cur = int(out[x, yhead, z])
                                if cur == fid or _cell_is_glass(cur) or _is_door(cur):
                                    continue
                                if (
                                    cur == 0
                                    or cur == int(wall_id)
                                    or _cell_is_nonstructural_mass(cur)
                                    or (
                                        _PALETTE_REF is not None
                                        and _is_full_structural(
                                            _short(_PALETTE_REF.get(cur, "stone"))
                                        )
                                    )
                                ):
                                    out[x, yhead, z] = fid
                                    sill_n += 1
            if col_hit:
                cols += 1
            idx += sp

    if placed or sill_n:
        actions.append(
            "window_rhythm:cells=%d cols=%d sp=%d bands=%d sill=%d"
            % (placed, cols, sp, len(bands), sill_n)
        )
    info["placed_cells"] = placed
    info["columns"] = cols
    info["sill_header"] = sill_n
    return out, actions, info


# Facade rhythm: door, roof silhouette, eaves, banding, corner pillars
# Applied after shell/floors/windows; does not undo palette top-K.
# ---------------------------------------------------------------------------

_PITCHED_STYLES = frozenset(
    {
        "medieval",
        "european",
        "rustic",
        "chinese",
        "japanese",
        "fantasy",
        "western",
        "unknown",
    }
)
_FLAT_ROOF_STYLES = frozenset({"industrial", "modern", "scifi", "desert"})

_DOOR_BY_STYLE: dict[str, tuple[str, ...]] = {
    "industrial": ("iron_door", "oak_door", "spruce_door"),
    "modern": ("iron_door", "oak_door", "spruce_door"),
    "scifi": ("iron_door", "oak_door"),
    "medieval": ("oak_door", "spruce_door", "dark_oak_door"),
    "european": ("oak_door", "spruce_door", "dark_oak_door"),
    "rustic": ("oak_door", "spruce_door"),
    "chinese": ("dark_oak_door", "spruce_door", "oak_door"),
    "japanese": ("spruce_door", "dark_oak_door", "oak_door"),
    "western": ("oak_door", "spruce_door"),
    "fantasy": ("dark_oak_door", "spruce_door", "oak_door"),
    "desert": ("oak_door", "spruce_door"),
    "unknown": ("oak_door", "spruce_door", "dark_oak_door", "iron_door"),
}


def _resolve_door_id(palette: dict[int, str] | None, style: str | None = None) -> int:
    if not palette:
        return 0
    name_to_id = _name_to_id(palette)
    key = (style or "unknown").strip().lower() or "unknown"
    preferred = list(_DOOR_BY_STYLE.get(key, _DOOR_BY_STYLE["unknown"]))
    preferred += ["oak_door", "spruce_door", "dark_oak_door", "iron_door", "birch_door"]
    for c in preferred:
        if c in name_to_id and name_to_id[c] > 0:
            return int(name_to_id[c])
    for pn, pid in name_to_id.items():
        if int(pid) > 0 and pn.endswith("_door") and "trapdoor" not in pn:
            return int(pid)
    return 0


def _resolve_stairs_id(
    palette: dict[int, str] | None,
    wall_id: int,
    style: str | None = None,
) -> int:
    """Prefer stairs matching wall material; else style wood/stone stairs."""
    if not palette:
        return 0
    name_to_id = _name_to_id(palette)
    wall_short = _short(palette.get(int(wall_id), "")).lower()
    # strip common suffixes to find family
    base = wall_short
    for suf in ("_bricks", "_brick", "_planks", "_block", "_concrete", ""):
        if suf and base.endswith(suf):
            base = base[: -len(suf)]
            break
    candidates: list[str] = []
    if base:
        candidates += [base + "_stairs", base + "s_stairs"]
    if "brick" in wall_short:
        candidates += ["stone_brick_stairs", "brick_stairs", "cobblestone_stairs"]
    if "deepslate" in wall_short:
        candidates += ["deepslate_brick_stairs", "cobbled_deepslate_stairs"]
    if "concrete" in wall_short or "quartz" in wall_short:
        candidates += ["quartz_stairs", "smooth_quartz_stairs"]
    toks = style_token_list(style)
    for t in toks:
        tl = t.lower()
        if "plank" in tl or tl.endswith("_log"):
            wood = tl.replace("_planks", "").replace("_log", "")
            candidates.append(wood + "_stairs")
        if "stone" in tl or "cobble" in tl:
            candidates += ["cobblestone_stairs", "stone_brick_stairs", "stone_stairs"]
    candidates += [
        "oak_stairs",
        "spruce_stairs",
        "cobblestone_stairs",
        "stone_brick_stairs",
        "dark_oak_stairs",
    ]
    for c in candidates:
        if c in name_to_id and name_to_id[c] > 0:
            return int(name_to_id[c])
    for pn, pid in name_to_id.items():
        if int(pid) > 0 and pn.endswith("_stairs"):
            return int(pid)
    return 0


def _resolve_pillar_id(
    palette: dict[int, str] | None,
    wall_id: int,
    style: str | None = None,
) -> int:
    if not palette:
        return int(wall_id)
    name_to_id = _name_to_id(palette)
    key = (style or "unknown").strip().lower() or "unknown"
    prefs: list[str] = []
    if key in ("medieval", "european", "rustic", "western", "chinese", "japanese"):
        prefs = ["oak_log", "spruce_log", "dark_oak_log", "stripped_oak_log"]
    elif key in ("industrial", "modern", "scifi"):
        prefs = ["iron_block", "polished_deepslate", "smooth_stone", "gray_concrete"]
    prefs += list(style_token_list(style))
    for c in prefs:
        if c in name_to_id and name_to_id[c] > 0 and name_to_id[c] != wall_id:
            return int(name_to_id[c])
        for pn, pid in name_to_id.items():
            if int(pid) > 0 and _token_match(pn, c) and int(pid) != int(wall_id):
                if _is_full_structural(pn):
                    return int(pid)
    return int(wall_id)


def _bbox_faces(peri: np.ndarray) -> dict[str, list[tuple[int, int]]]:
    px, pz = np.where(peri)
    if px.size == 0:
        return {"x0": [], "x1": [], "z0": [], "z1": []}
    minx, maxx = int(px.min()), int(px.max())
    minz, maxz = int(pz.min()), int(pz.max())
    cols = list(zip(px.tolist(), pz.tolist()))
    return {
        "x0": [(x, z) for x, z in cols if x == minx],
        "x1": [(x, z) for x, z in cols if x == maxx],
        "z0": [(x, z) for x, z in cols if z == minz],
        "z1": [(x, z) for x, z in cols if z == maxz],
        "_bbox": [(minx, maxx, minz, maxz)],  # type: ignore[list-item]
    }



def _facade_face_cells(
    peri: np.ndarray,
    fp: np.ndarray | None = None,
) -> dict[str, list[tuple[int, int]]]:
    """Perimeter cells that face open air (real facade), not only bbox extremes.

    Organic / fantasy footprints often have almost no peri on the AABB faces;
    this keeps window rhythm working on irregular outlines.
    """
    if fp is None:
        return _bbox_faces(peri)
    faces: dict[str, list[tuple[int, int]]] = {"x0": [], "x1": [], "z0": [], "z1": []}
    sx, sz = peri.shape
    px, pz = np.where(peri)
    for x, z in zip(px.tolist(), pz.tolist()):
        if x <= 0 or not fp[x - 1, z]:
            faces["x0"].append((x, z))
        if x >= sx - 1 or not fp[x + 1, z]:
            faces["x1"].append((x, z))
        if z <= 0 or not fp[x, z - 1]:
            faces["z0"].append((x, z))
        if z >= sz - 1 or not fp[x, z + 1]:
            faces["z1"].append((x, z))
    # If a face is still tiny, fall back to bbox for that face only.
    bb = _bbox_faces(peri)
    for k, cells in list(faces.items()):
        if len(cells) < 3 and bb.get(k):
            faces[k] = bb[k]
    return faces


def _pick_front_face(faces: dict[str, list[tuple[int, int]]]) -> str:
    """Longest side wins; tie-break prefer z0 (south-ish)."""
    best = "z0"
    best_n = -1
    for name in ("z0", "z1", "x0", "x1"):
        n = len(faces.get(name) or [])
        if n > best_n:
            best_n = n
            best = name
    return best


def facade_metrics(
    voxels: np.ndarray,
    *,
    door_cells: int = 0,
    eave_cells: int = 0,
    banding_cells: int = 0,
    pillar_cells: int = 0,
    roof_mode: str = "",
) -> dict[str, Any]:
    return {
        "door_cells": int(door_cells),
        "eave_cells": int(eave_cells),
        "banding_cells": int(banding_cells),
        "pillar_cells": int(pillar_cells),
        "roof_mode": str(roof_mode or ""),
    }


def carve_front_door(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    active: np.ndarray,
    y0: int,
    y1: int,
    floor_ys: list[int],
    win_mask: np.ndarray | None = None,
    door_id: int = 0,
    place_door_block: bool = True,
    width: int = 0,
    height: int = 2,
    fp: np.ndarray | None = None,
    frame_id: int = 0,
    threshold_id: int = 0,
    place_frame: bool = True,
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    """Clear a 1–2 wide × 2 tall front door on the primary (longest) facade.

    Adds optional threshold on the ground slab and frame/lintel with accent.
    Uses real outward-facing peri cells so irregular footprints still get an entrance.
    """
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    info: dict[str, Any] = {
        "door_cells": 0,
        "face": "",
        "placed_door": False,
        "frame_cells": 0,
        "threshold_cells": 0,
    }
    sx, sy, sz = out.shape
    if y1 <= y0 + 2:
        return out, actions, info

    faces = _facade_face_cells(peri, fp=fp) if fp is not None else _bbox_faces(peri)
    face = _pick_front_face(faces)
    cols = list(faces.get(face) or [])
    cols = [(x, z) for x, z in cols if active[x, z]]
    if len(cols) < 1:
        # fallback bbox if facade faces empty on this side
        faces = _bbox_faces(peri)
        face = _pick_front_face(faces)
        cols = [(x, z) for x, z in (faces.get(face) or []) if active[x, z]]
    if len(cols) < 1:
        return out, actions, info

    if face in ("x0", "x1"):
        cols.sort(key=lambda c: c[1])
    else:
        cols.sort(key=lambda c: c[0])

    # dedupe while preserving order (facade faces may list corners twice)
    seen: set[tuple[int, int]] = set()
    cols_u: list[tuple[int, int]] = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            cols_u.append(c)
    cols = cols_u

    w = int(width) if int(width) > 0 else (2 if len(cols) >= 5 else 1)
    w = 2 if w >= 2 else 1
    if len(cols) < w:
        w = 1
    mid = len(cols) // 2
    if len(cols) >= 4:
        lo = max(1, mid - (w // 2))
        hi = min(len(cols) - 1, lo + w)
        if hi - lo < w:
            lo = max(1, hi - w)
        pick = cols[lo:hi]
    else:
        pick = cols[mid : mid + max(1, w)]
        pick = pick[:w]

    ground = int(y0)
    y_bot = ground + 1
    h = max(2, min(3, int(height) if int(height) > 0 else 2))
    y_top = ground + h
    if y_top >= y1:
        y_top = min(ground + 2, y1 - 1)
    if y_bot >= sy or y_bot >= y1 or y_top < y_bot:
        return out, actions, info

    def _is_door_name(bid: int) -> bool:
        if bid <= 0 or _PALETTE_REF is None:
            return False
        sn = _short(_PALETTE_REF.get(bid, ""))
        return sn.endswith("_door") or sn == "door"

    carved = 0
    door_mask = np.zeros_like(out, dtype=bool)
    for x, z in pick:
        for y in range(y_bot, y_top + 1):
            if y < 0 or y >= sy or y >= y1:
                continue
            out[x, y, z] = 0
            door_mask[x, y, z] = True
            carved += 1
            if win_mask is not None:
                win_mask[x, y, z] = False

    placed = False
    if place_door_block and int(door_id) > 0 and pick:
        x, z = pick[len(pick) // 2]
        if 0 <= y_bot < sy and peri[x, z]:
            out[x, y_bot, z] = int(door_id)
            door_mask[x, y_bot, z] = True
            placed = True
            # keep clearance above door block
            if y_bot + 1 <= y_top and y_bot + 1 < sy:
                out[x, y_bot + 1, z] = 0
                door_mask[x, y_bot + 1, z] = True

    thr_n = 0
    tid = int(threshold_id) if int(threshold_id) > 0 else 0
    if tid > 0 and pick and 0 <= ground < sy:
        for x, z in pick:
            cur = int(out[x, ground, z])
            if _is_door_name(cur) or (cur > 0 and _cell_is_glass(cur)):
                continue
            out[x, ground, z] = tid
            thr_n += 1

    frame_n = 0
    fid = int(frame_id) if int(frame_id) > 0 else 0
    if place_frame and fid > 0 and pick:
        pick_set = set(pick)
        # side posts: neighboring face columns
        idx0 = cols.index(pick[0]) if pick[0] in cols else -1
        idx1 = cols.index(pick[-1]) if pick[-1] in cols else -1
        side_cols: list[tuple[int, int]] = []
        if idx0 > 0:
            side_cols.append(cols[idx0 - 1])
        if idx1 >= 0 and idx1 + 1 < len(cols):
            side_cols.append(cols[idx1 + 1])
        for x, z in side_cols:
            if (x, z) in pick_set:
                continue
            for y in range(y_bot, y_top + 1):
                if y >= y1 or y >= sy:
                    continue
                cur = int(out[x, y, z])
                if _is_door_name(cur) or (cur > 0 and _cell_is_glass(cur)):
                    continue
                if win_mask is not None and win_mask[x, y, z]:
                    continue
                if cur == 0 or cur != fid:
                    out[x, y, z] = fid
                    frame_n += 1
        # lintel above opening
        y_lin = y_top + 1
        if y_lin < y1 and y_lin < sy:
            for x, z in pick:
                cur = int(out[x, y_lin, z])
                if _is_door_name(cur) or (cur > 0 and _cell_is_glass(cur)):
                    continue
                if win_mask is not None and win_mask[x, y_lin, z]:
                    continue
                out[x, y_lin, z] = fid
                frame_n += 1

    if carved or placed or frame_n or thr_n:
        actions.append(
            "front_door:face=%s w=%d h=%d cells=%d door=%s frame=%d thr=%d"
            % (
                face,
                len(pick),
                y_top - y_bot + 1,
                carved,
                "yes" if placed else "air",
                frame_n,
                thr_n,
            )
        )
    info.update(
        {
            "door_cells": carved,
            "face": face,
            "placed_door": placed,
            "door_y": [y_bot, y_top],
            "width": len(pick),
            "frame_cells": frame_n,
            "threshold_cells": thr_n,
            "door_mask": door_mask,
            "pick": pick,
        }
    )
    return out, actions, info



def harden_roof_silhouette(
    voxels: np.ndarray,
    *,
    active: np.ndarray,
    peri: np.ndarray,
    y0: int,
    y1: int,
    wall_id: int,
    style: str | None = None,
    stairs_id: int = 0,
    win_mask: np.ndarray | None = None,
    roof_id: int | None = None,
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    """Flat cap tidy or cheap pitched gable massing by style."""
    out = np.asarray(voxels, dtype=np.int16)
    roof_block = int(roof_id) if roof_id is not None and int(roof_id) > 0 else int(wall_id)
    actions: list[str] = []
    info: dict[str, Any] = {"roof_mode": "flat", "roof_cells": 0}
    sx, sy, sz = out.shape
    ax, az = np.where(active)
    if ax.size == 0 or y1 <= y0 + 2:
        return out, actions, info

    key = (style or "unknown").strip().lower() or "unknown"
    want_pitch = key in _PITCHED_STYLES and key not in _FLAT_ROOF_STYLES
    # also pitch unknown/fantasy; force flat for industrial family
    if key in _FLAT_ROOF_STYLES:
        want_pitch = False
    # Scaffold now places hollow skin_gable for euro/rustic/western/chinese.
    # Do NOT force-flat (that wiped eaves). Still force flat for industrial family.
    # Skin-only pitch below preserves hollowness (no solid attic fill).

    minx, maxx = int(ax.min()), int(ax.max())
    minz, maxz = int(az.min()), int(az.max())
    wx = maxx - minx + 1
    wz = maxz - minz + 1

    if not want_pitch or min(wx, wz) < 5:
        # flat: ensure continuous roof deck on active + trim lonely spikes above y1
        filled = 0
        cleared = 0
        for x, z in zip(ax.tolist(), az.tolist()):
            if out[x, y1, z] == 0 or (
                _cell_is_nonstructural_mass(int(out[x, y1, z]))
                and not _cell_is_glass(int(out[x, y1, z]))
            ):
                out[x, y1, z] = int(roof_block)
                filled += 1
            # clear anything above y1 in-bounds (spike cleanup)
            for y in range(y1 + 1, sy):
                if out[x, y, z] != 0:
                    out[x, y, z] = 0
                    cleared += 1
        if filled or cleared:
            actions.append("roof_flat:fill=%d clear_above=%d" % (filled, cleared))
        info["roof_mode"] = "flat"
        info["roof_cells"] = filled
        return out, actions, info

    # pitched gable: ridge along longer axis
    ridge_along_x = wx >= wz  # ridge line parallel to X → height varies with Z
    half = (wz // 2) if ridge_along_x else (wx // 2)
    rules = knowledge_defaults()
    rise_max = max(2, int(rules.get("roof_rise_max", 5)))
    rise_min = max(2, int(rules.get("roof_rise_min", 2)))
    rise = int(min(rise_max, max(rise_min, half)))
    # Medieval/fantasy: milder low-pitch (cap rise) so ridge plateau can own more of
    # the elevated footprint at y_max — raises roof_score without flat-deck wipe.
    if key in ("medieval", "fantasy"):
        # Phase 3: G-like low pitch (cap 3) + wide plateau → higher peak cover
        rise = int(min(3, max(2, min(rise, max(2, half // 3)))))
    elif key in ("european", "rustic", "western", "chinese", "japanese"):
        rise = int(min(5, max(3, rise)))
    # eave / wall-top stays near y1 - rise; peak at y1 (may extend if room)
    peak_y = int(min(sy - 1, y1))
    eave_y = int(max(y0 + 3, peak_y - rise))
    if peak_y <= eave_y:
        info["roof_mode"] = "flat_fallback"
        return out, actions, info

    # clear old roof zone then rebuild
    roof_lo = eave_y
    cleared = 0
    for x, z in zip(ax.tolist(), az.tolist()):
        for y in range(roof_lo, sy):
            if out[x, y, z] == 0:
                continue
            # never wipe preserved windows / glass (even in roof band)
            if win_mask is not None and win_mask[x, y, z]:
                continue
            if _cell_is_glass(int(out[x, y, z])):
                continue
            out[x, y, z] = 0
            cleared += 1

    placed = 0
    stair_n = 0
    ridge_z = (minz + maxz) / 2.0
    ridge_x = (minx + maxx) / 2.0
    # Broad ridge plateau. Euro/rustic: mid plateau for readable eaves + slope.
    # Medieval/fantasy: wider plateau (~0.72 of half).
    # Phase 3: med/fantasy wide plateau (~G 0.72) to close roof gap; keep euro stairs
    if key in ("medieval", "fantasy"):
        plateau = max(2, int(0.70 * max(1, half)))
    elif key in ("european", "rustic", "western"):
        plateau = max(1, int(0.38 * max(1, half)))
    elif key in ("chinese", "japanese"):
        plateau = max(1, int(0.48 * max(1, half)))
    else:
        plateau = max(1, int(0.36 * max(1, half)))
    for x, z in zip(ax.tolist(), az.tolist()):
        if ridge_along_x:
            dist = abs(float(z) - ridge_z)
        else:
            dist = abs(float(x) - ridge_x)
        if dist <= plateau:
            h = int(peak_y)
        else:
            span = max(1e-6, float(half - plateau))
            tnorm = min(1.0, (dist - plateau) / span)
            h = int(round(peak_y - tnorm * (peak_y - eave_y)))
        h = max(eave_y, min(peak_y, h))
        # Skin-only: peri eave ring + surface at h (+ underlay). No solid attic fill/deck.
        if peri[x, z]:
            if win_mask is not None and win_mask[x, eave_y, z]:
                pass
            elif not _cell_is_glass(int(out[x, eave_y, z])):
                out[x, eave_y, z] = int(roof_block)
                placed += 1
        if h > eave_y:
            if not (win_mask is not None and win_mask[x, h, z]) and not _cell_is_glass(int(out[x, h, z])):
                out[x, h, z] = int(roof_block)
                placed += 1
            if h - 1 > eave_y and not (win_mask is not None and win_mask[x, h - 1, z]):
                if not _cell_is_glass(int(out[x, h - 1, z])):
                    out[x, h - 1, z] = int(roof_block)
                    placed += 1
            # clear attic interior under skin (keep peri walls)
            if not peri[x, z]:
                for y in range(eave_y + 1, h - 1):
                    if win_mask is not None and win_mask[x, y, z]:
                        continue
                    if _cell_is_glass(int(out[x, y, z])):
                        continue
                    # only clear roof mass / air; leave intentional walls/floors alone if not roof
                    cur = int(out[x, y, z])
                    if cur == 0 or cur == int(roof_block):
                        out[x, y, z] = 0
            else:
                # peri: fill wall up under slope so gable end reads
                for y in range(eave_y + 1, h):
                    if win_mask is not None and win_mask[x, y, z]:
                        continue
                    if out[x, y, z] == 0:
                        out[x, y, z] = int(wall_id)
        # stairs on slope face (peri + near-peri) for stepped silhouette
        if stairs_id > 0 and h < peak_y:
            near_peri = bool(peri[x, z])
            if not near_peri:
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, nz = x + dx, z + dz
                    if 0 <= nx < sx and 0 <= nz < sz and peri[nx, nz]:
                        near_peri = True
                        break
            if near_peri:
                out[x, h, z] = int(stairs_id)
                stair_n += 1

    actions.append(
        "roof_pitched:rise=%d eave_y=%d peak_y=%d clear=%d place=%d stairs=%d along=%s"
        % (
            rise,
            eave_y,
            peak_y,
            cleared,
            placed,
            stair_n,
            "x" if ridge_along_x else "z",
        )
    )
    info.update(
        {
            "roof_mode": "pitched",
            "roof_cells": placed,
            "roof_eave_y": eave_y,
            "roof_peak_y": peak_y,
            "roof_stairs": stair_n,
        }
    )
    return out, actions, info


def place_eave_strip(
    voxels: np.ndarray,
    *,
    active: np.ndarray,
    peri: np.ndarray,
    roof_y: int,
    wall_id: int,
    stairs_id: int = 0,
    roof_id: int | None = None,
    overhang: int = 1,
) -> tuple[np.ndarray, list[str], int]:
    """Outward eave ring at roof_y (flat) or eave level.

    ``overhang`` walks 1..N cells outside the footprint. Never clears existing
    roof deck on ``active`` columns (look_polish flat-deck preserve).
    """
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    sx, sy, sz = out.shape
    if roof_y < 0 or roof_y >= sy:
        return out, actions, 0
    oh = max(0, min(2, int(overhang)))
    if oh <= 0:
        return out, actions, 0
    added = 0
    roof_block = int(roof_id) if roof_id is not None and int(roof_id) > 0 else int(wall_id)
    block = int(stairs_id) if int(stairs_id) > 0 else int(roof_block)
    px, pz = np.where(peri)
    for x, z in zip(px.tolist(), pz.tolist()):
        if not active[x, z]:
            continue
        # ensure eave support on peri — fill air only, do not overwrite deck
        if out[x, roof_y, z] == 0:
            out[x, roof_y, z] = int(roof_block)
            added += 1
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, oh + 1):
                nx, nz = x + dx * step, z + dz * step
                if not (0 <= nx < sx and 0 <= nz < sz):
                    break
                if active[nx, nz]:
                    break
                if out[nx, roof_y, nz] != 0:
                    break
                out[nx, roof_y, nz] = block
                added += 1
    if added:
        actions.append("eave_strip:%d@y=%d oh=%d" % (added, roof_y, oh))
    return out, actions, added


def place_cornice_ring(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    active: np.ndarray,
    cornice_y: int,
    trim_id: int,
    wall_id: int,
    win_mask: np.ndarray | None = None,
    y0: int = 0,
    y1: int | None = None,
) -> tuple[np.ndarray, list[str], int]:
    """Decorative cornice band on perimeter under the roof/deck (works when overhang has no room)."""
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    sy = out.shape[1]
    cy = int(cornice_y)
    if cy < 0 or cy >= sy or int(trim_id) <= 0:
        return out, actions, 0
    if y1 is not None and cy >= int(y1):
        return out, actions, 0
    if cy <= int(y0):
        return out, actions, 0
    changed = 0
    tid = int(trim_id)
    px, pz = np.where(peri & active)
    for x, z in zip(px.tolist(), pz.tolist()):
        if win_mask is not None and win_mask[x, cy, z]:
            continue
        cur = int(out[x, cy, z])
        if cur == tid:
            continue
        if cur > 0 and _cell_is_glass(cur):
            continue
        if _PALETTE_REF is not None:
            sn = _short(_PALETTE_REF.get(cur, ""))
            if sn.endswith("_door") or sn == "door":
                continue
            # do not strip existing roof stairs/slabs on the peri lip
            if "stairs" in sn or sn.endswith("_slab"):
                continue
        if (
            cur == 0
            or cur == int(wall_id)
            or _cell_is_nonstructural_mass(cur)
            or (
                _PALETTE_REF is not None
                and _is_full_structural(_short(_PALETTE_REF.get(cur, "stone")))
            )
        ):
            out[x, cy, z] = tid
            changed += 1
    if changed:
        actions.append("cornice_ring:%d@y=%d" % (changed, cy))
    return out, actions, changed


def place_facade_banding(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    active: np.ndarray,
    floor_ys: list[int],
    y0: int,
    y1: int,
    band_id: int,
    wall_id: int,
    win_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, list[str], int]:
    """Light horizontal belt on perimeter at each floor Y (skip glass/windows/doors)."""
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    sy = out.shape[1]
    changed = 0
    ys = sorted({int(y) for y in floor_ys if y0 < int(y) < y1})
    # also band at mid-story belt: floor Y itself on exterior
    px, pz = np.where(peri & active)
    for y in ys:
        if y < 0 or y >= sy:
            continue
        for x, z in zip(px.tolist(), pz.tolist()):
            cur = int(out[x, y, z])
            if cur == 0:
                continue
            if _cell_is_glass(cur):
                continue
            if win_mask is not None and win_mask[x, y, z]:
                continue
            sn = ""
            if _PALETTE_REF is not None:
                sn = _short(_PALETTE_REF.get(cur, ""))
            if sn.endswith("_door") or sn == "door":
                continue
            if cur == int(band_id):
                continue
            # only recolor structural wall-ish cells
            if cur == int(wall_id) or _is_full_structural(sn or "stone"):
                out[x, y, z] = int(band_id)
                changed += 1
    if changed:
        actions.append("facade_band:%d@y=%s" % (changed, ys))
    return out, actions, changed


def place_corner_pillars(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    active: np.ndarray,
    y0: int,
    y1: int,
    pillar_id: int,
    win_mask: np.ndarray | None = None,
) -> tuple[np.ndarray, list[str], int]:
    """Reinforce four footprint-bbox corners as continuous pillars."""
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    sx, sy, sz = out.shape
    px, pz = np.where(peri & active)
    if px.size == 0:
        return out, actions, 0
    minx, maxx = int(px.min()), int(px.max())
    minz, maxz = int(pz.min()), int(pz.max())
    corners = [
        (minx, minz),
        (minx, maxz),
        (maxx, minz),
        (maxx, maxz),
    ]
    # snap to nearest peri/active cell if exact corner missing
    peri_set = set(zip(px.tolist(), pz.tolist()))
    snapped: list[tuple[int, int]] = []
    for cx, cz in corners:
        if (cx, cz) in peri_set:
            snapped.append((cx, cz))
            continue
        best = None
        best_d = 10**9
        for x, z in peri_set:
            d = abs(x - cx) + abs(z - cz)
            if d < best_d:
                best_d = d
                best = (x, z)
        if best is not None and best_d <= 2:
            snapped.append(best)
    snapped = list(dict.fromkeys(snapped))

    filled = 0
    for x, z in snapped:
        for y in range(y0, min(y1, sy - 1) + 1):
            if win_mask is not None and win_mask[x, y, z]:
                continue
            cur = int(out[x, y, z])
            if cur > 0 and _cell_is_glass(cur):
                continue
            sn = ""
            if _PALETTE_REF is not None:
                sn = _short(_PALETTE_REF.get(cur, ""))
            if sn.endswith("_door") or sn == "door":
                continue
            if cur != int(pillar_id):
                out[x, y, z] = int(pillar_id)
                filled += 1
    if filled:
        actions.append("corner_pillars:%d_cols=%d" % (filled, len(snapped)))
    return out, actions, filled


def place_wall_piers(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    active: np.ndarray,
    y0: int,
    y1: int,
    pier_id: int,
    wall_id: int,
    spacing: int = 3,
    from_corner: int = 2,
    win_mask: np.ndarray | None = None,
    door_mask: np.ndarray | None = None,
    fp: np.ndarray | None = None,
    skip_glass_cols: bool = True,
) -> tuple[np.ndarray, list[str], int]:
    """Vertical accent piers on facades between window bays (wall panel rhythm)."""
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    if int(pier_id) <= 0 or int(pier_id) == int(wall_id):
        return out, actions, 0
    sy = out.shape[1]
    sp = max(2, int(spacing))
    fc = max(1, int(from_corner))
    faces = _facade_face_cells(peri, fp=fp) if fp is not None else _bbox_faces(peri)
    filled = 0
    pier_cols = 0
    y_lo = int(y0) + 1
    y_hi = min(int(y1), sy - 1)

    def _is_door(bid: int) -> bool:
        if bid <= 0 or _PALETTE_REF is None:
            return False
        sn = _short(_PALETTE_REF.get(bid, ""))
        return sn.endswith("_door") or sn == "door"

    for face, cells in faces.items():
        if face.startswith("_"):
            continue
        if len(cells) < fc * 2 + 1:
            continue
        if face in ("x0", "x1"):
            cells_s = sorted(set(cells), key=lambda t: t[1])
        else:
            cells_s = sorted(set(cells), key=lambda t: t[0])
        usable = cells_s[fc : max(fc, len(cells_s) - fc)]
        if not usable:
            continue
        # Offset half-spacing so piers sit between typical window columns.
        start = (sp // 2) % sp
        idx = start
        while idx < len(usable):
            x, z = usable[idx]
            if not active[x, z]:
                idx += sp
                continue
            # Skip columns that are mostly glass/window (void bay).
            if skip_glass_cols:
                glass_n = 0
                solid_n = 0
                for y in range(y_lo, y_hi + 1):
                    cur = int(out[x, y, z])
                    if cur > 0 and _cell_is_glass(cur):
                        glass_n += 1
                    elif win_mask is not None and win_mask[x, y, z]:
                        glass_n += 1
                    elif cur > 0:
                        solid_n += 1
                if glass_n >= max(1, (y_hi - y_lo + 1) // 3):
                    idx += sp
                    continue
            col_hit = False
            for y in range(y_lo, y_hi + 1):
                if door_mask is not None and door_mask[x, y, z]:
                    continue
                if win_mask is not None and win_mask[x, y, z]:
                    continue
                cur = int(out[x, y, z])
                if cur > 0 and _cell_is_glass(cur):
                    continue
                if _is_door(cur):
                    continue
                if cur == 0:
                    continue  # don't fill intentional openings
                if cur == int(pier_id):
                    continue
                if cur == int(wall_id) or (
                    _PALETTE_REF is not None
                    and _is_full_structural(_short(_PALETTE_REF.get(cur, "stone")))
                ):
                    out[x, y, z] = int(pier_id)
                    filled += 1
                    col_hit = True
            if col_hit:
                pier_cols += 1
            idx += sp

    if filled:
        actions.append("wall_piers:%d cols=%d sp=%d" % (filled, pier_cols, sp))
    return out, actions, filled



def harden_facade(
    voxels: np.ndarray,
    *,
    wall_id: int,
    floor_id: int,
    style: str | None = None,
    palette: dict[int, str] | None = None,
    floor_ys: list[int] | None = None,
    preserve_windows: bool = True,
    win_mask: np.ndarray | None = None,
    place_door: bool = True,
    place_door_block: bool = True,
    roof_silhouette: bool = True,
    eave_strip: bool = True,
    facade_banding: bool = True,
    corner_pillars: bool = True,
    use_knowledge: bool = True,
    roof_id: int | None = None,
    foundation_id: int | None = None,
    accent_id: int | None = None,
    window_frame_id: int | None = None,
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    """Door(+frame) + roof + eaves/cornice + window rhythm + wall piers. Keeps openings."""
    out = np.asarray(voxels, dtype=np.int16).copy()
    actions: list[str] = []
    stats: dict[str, Any] = facade_metrics(out)
    solid = out > 0
    if not solid.any():
        return out, ["facade_empty_skip"], stats

    sx, sy, sz = out.shape
    fp, fp_n = _footprint(solid)
    if fp_n == 0:
        return out, actions + ["facade_no_footprint"], stats

    ys = np.where(solid.any(axis=(0, 2)))[0]
    y0, y1 = int(ys.min()), int(ys.max())
    peri = _perimeter_mask(fp)
    xs_fp, zs_fp = np.where(fp)
    active = np.zeros_like(fp, dtype=bool)
    for x, z in zip(xs_fp.tolist(), zs_fp.tolist()):
        if int((out[x, y0 : y1 + 1, z] > 0).sum()) >= 2:
            active[x, z] = True

    peaks = list(floor_ys) if floor_ys is not None else list(
        _floor_metrics(solid).get("y_peaks") or []
    )
    peaks = sorted({int(y) for y in peaks if 0 <= int(y) < sy})
    if y0 not in peaks:
        peaks = [y0] + peaks

    rules = style_facade_rules(style) if use_knowledge else {}
    if use_knowledge and rules:
        actions.append(
            "knowledge:story>=%s floor_sp_hint=%s wall=%s win_sp=%s eave=%s roof_rise_max=%s cornice=%s"
            % (
                rules.get("min_story_clear"),
                rules.get("floor_spacing"),
                rules.get("shell_thickness"),
                rules.get("window_spacing"),
                rules.get("eave_overhang"),
                rules.get("roof_rise_max"),
                rules.get("place_cornice", True),
            )
        )

    # foundation band (before openings)
    fh = max(0, int(rules.get("foundation_height", 1))) if use_knowledge else 0
    if fh:
        out, act, _n = place_foundation_band(
            out,
            active=active,
            peri=peri,
            y0=y0,
            wall_id=wall_id,
            floor_id=floor_id,
            height=fh,
            foundation_id=foundation_id,
        )
        actions.extend(act)

    # rhythmic windows on mid-story bands (regular spacing + optional sill/header)
    gid = _resolve_glass_id(palette, style=style) if use_knowledge else 0
    frame_for_win = (
        int(window_frame_id)
        if window_frame_id is not None and int(window_frame_id) > 0
        else (
            int(accent_id)
            if accent_id is not None and int(accent_id) > 0
            else 0
        )
    )
    if use_knowledge and gid > 0 and bool(rules.get("place_window_glass", True)):
        wh = max(
            int(rules.get("window_height_min", 1)),
            min(3, int(rules.get("window_height_max", 2))),
        )
        ww = max(
            int(rules.get("window_width_min", 1)),
            min(3, int(rules.get("window_width_max", 2))),
        )
        out, act, wr = place_window_rhythm(
            out,
            peri=peri,
            y0=y0,
            y1=y1,
            floor_ys=peaks,
            glass_id=int(gid),
            wall_id=int(wall_id),
            spacing=int(rules.get("window_spacing", 3)),
            from_corner=int(rules.get("window_from_corner", 2)),
            from_floor=int(rules.get("window_from_floor", 1)),
            win_h=wh,
            win_w=ww,
            frame_id=int(frame_for_win),
            place_sill_header=bool(rules.get("place_sill_header", True)),
            floor_spacing=int(rules.get("floor_spacing", 5)),
            max_bands=int(rules.get("max_window_bands", 4)),
            fp=fp,
        )
        actions.extend(act)
        stats["window_rhythm_cells"] = int(wr.get("placed_cells", 0))
        stats["window_sill_header"] = int(wr.get("sill_header", 0))
        # refresh win mask so door carve respects new glass
        if preserve_windows:
            wmask2, _ = detect_window_mask(
                out, peri=peri, y0=y0, y1=y1, floor_ys=peaks, preserve=True, style=style
            )
            if win_mask is None:
                win_mask = wmask2
            else:
                win_mask = win_mask | wmask2

    # local win mask copy so door carve can clear slots without touching caller oddly
    if win_mask is None:
        wmask = np.zeros_like(out, dtype=bool)
    else:
        wmask = win_mask.copy()

    door_id = _resolve_door_id(palette, style=style) if place_door_block else 0
    stairs_id = _resolve_stairs_id(palette, wall_id, style=style)
    roof_block = int(roof_id) if roof_id is not None and int(roof_id) > 0 else int(wall_id)
    pillar_id = (
        int(accent_id)
        if accent_id is not None and int(accent_id) > 0
        else _resolve_pillar_id(palette, wall_id, style=style)
    )
    band_id = (
        int(accent_id)
        if accent_id is not None and int(accent_id) > 0 and int(accent_id) != int(wall_id)
        else (int(floor_id) if int(floor_id) != int(wall_id) else int(pillar_id))
    )

    door_cells = 0
    door_mask = np.zeros_like(out, dtype=bool)
    place_door = bool(place_door and (rules.get("place_door", True) if rules else True))
    if place_door:
        thr_id = int(floor_id) if int(floor_id) > 0 else 0
        frame_door = (
            int(accent_id)
            if accent_id is not None and int(accent_id) > 0
            else (
                int(window_frame_id)
                if window_frame_id is not None and int(window_frame_id) > 0
                else int(pillar_id)
            )
        )
        out, act, dinfo = carve_front_door(
            out,
            peri=peri,
            active=active,
            y0=y0,
            y1=y1,
            floor_ys=peaks,
            win_mask=wmask,
            door_id=door_id,
            place_door_block=place_door_block,
            width=int(rules.get("door_width", 0) or 0),
            height=int(rules.get("door_height", 2) or 2),
            fp=fp,
            frame_id=int(frame_door),
            threshold_id=thr_id,
            place_frame=bool(rules.get("place_door_frame", True)),
        )
        actions.extend(act)
        door_cells = int(dinfo.get("door_cells", 0))
        stats["door_face"] = dinfo.get("face", "")
        stats["door_block"] = bool(dinfo.get("placed_door"))
        stats["door_frame"] = int(dinfo.get("frame_cells", 0))
        stats["door_threshold"] = int(dinfo.get("threshold_cells", 0))
        dm = dinfo.get("door_mask")
        if isinstance(dm, np.ndarray) and dm.shape == out.shape:
            door_mask = dm

    roof_mode = "flat"
    roof_eave_y = y1
    if roof_silhouette:
        out, act, rinfo = harden_roof_silhouette(
            out,
            active=active,
            peri=peri,
            y0=y0,
            y1=y1,
            wall_id=wall_id,
            style=style,
            stairs_id=stairs_id,
            win_mask=wmask if preserve_windows else None,
            roof_id=roof_block,
        )
        actions.extend(act)
        roof_mode = str(rinfo.get("roof_mode") or "flat")
        roof_eave_y = int(rinfo.get("roof_eave_y") or y1)
        # refresh y1 after pitched rebuild
        ys2 = np.where((out > 0).any(axis=(0, 2)))[0]
        if ys2.size:
            y1 = int(ys2.max())
            if roof_mode != "pitched":
                roof_eave_y = y1

    eave_n = 0
    cornice_n = 0
    ey = roof_eave_y if roof_mode == "pitched" else y1
    oh = int(rules.get("eave_overhang", 1)) if rules else 1
    if eave_strip and oh > 0:
        out, act, eave_n = place_eave_strip(
            out,
            active=active,
            peri=peri,
            roof_y=ey,
            wall_id=wall_id,
            stairs_id=stairs_id if roof_mode == "pitched" else 0,
            roof_id=roof_block,
            overhang=oh,
        )
        actions.extend(act)

    # Cornice under roof/deck — works even when footprint fills the box (no overhang room).
    do_cornice = bool(rules.get("place_cornice", True)) if rules else True
    if do_cornice:
        cy = int(ey) - 1
        trim = (
            int(accent_id)
            if accent_id is not None and int(accent_id) > 0 and int(accent_id) != int(wall_id)
            else int(roof_block)
        )
        if trim == int(wall_id):
            trim = int(frame_for_win) if frame_for_win > 0 else trim
        out, act, cornice_n = place_cornice_ring(
            out,
            peri=peri,
            active=active,
            cornice_y=cy,
            trim_id=trim,
            wall_id=wall_id,
            win_mask=wmask if preserve_windows else None,
            y0=y0,
            y1=y1,
        )
        actions.extend(act)

    band_n = 0
    facade_banding = bool(facade_banding and (rules.get("facade_banding", True) if rules else True))
    if facade_banding:
        out, act, band_n = place_facade_banding(
            out,
            peri=peri,
            active=active,
            floor_ys=peaks,
            y0=y0,
            y1=y1,
            band_id=band_id,
            wall_id=wall_id,
            win_mask=wmask if preserve_windows else None,
        )
        actions.extend(act)

    pillar_n = 0
    corner_pillars = bool(corner_pillars and (rules.get("corner_pillars", True) if rules else True))
    if corner_pillars:
        out, act, pillar_n = place_corner_pillars(
            out,
            peri=peri,
            active=active,
            y0=y0,
            y1=y1,
            pillar_id=pillar_id,
            win_mask=wmask if preserve_windows else None,
        )
        actions.extend(act)

    pier_n = 0
    do_piers = bool(rules.get("place_wall_piers", True)) if rules else True
    if do_piers and int(pillar_id) > 0 and int(pillar_id) != int(wall_id):
        pier_sp = int(rules.get("wall_pier_spacing") or rules.get("window_spacing") or 3)
        out, act, pier_n = place_wall_piers(
            out,
            peri=peri,
            active=active,
            y0=y0,
            y1=y1,
            pier_id=int(pillar_id),
            wall_id=int(wall_id),
            spacing=pier_sp,
            from_corner=int(rules.get("window_from_corner", 2)),
            win_mask=wmask if preserve_windows else None,
            door_mask=door_mask,
            fp=fp,
        )
        actions.extend(act)

    stats.update(
        facade_metrics(
            out,
            door_cells=door_cells,
            eave_cells=eave_n,
            banding_cells=band_n,
            pillar_cells=pillar_n + pier_n,
            roof_mode=roof_mode,
        )
    )
    stats["cornice_cells"] = int(cornice_n)
    stats["wall_pier_cells"] = int(pier_n)
    if actions:
        actions.insert(0, "facade:on")
    else:
        actions.append("facade:noop")
    return out, actions, stats



def despeckle_solids(
    voxels: np.ndarray,
    *,
    min_neighbors: int = 2,
    protected_ids: set[int] | None = None,
) -> tuple[np.ndarray, int]:
    """Remove solid cells with fewer than min_neighbors solid 6-neighbors (speckles)."""
    out = np.asarray(voxels, dtype=np.int16).copy()
    prot = set(int(x) for x in (protected_ids or set()) if int(x) > 0)
    solid = out > 0
    if not solid.any():
        return out, 0
    nb = np.zeros(out.shape, dtype=np.int16)
    nb[1:, :, :] += solid[:-1, :, :]
    nb[:-1, :, :] += solid[1:, :, :]
    nb[:, 1:, :] += solid[:, :-1, :]
    nb[:, :-1, :] += solid[:, 1:, :]
    nb[:, :, 1:] += solid[:, :, :-1]
    nb[:, :, :-1] += solid[:, :, 1:]
    drop = solid & (nb < int(min_neighbors))
    if prot:
        for pid in prot:
            drop &= out != int(pid)
    if _PALETTE_REF is not None:
        for bid in np.unique(out[drop]):
            bid = int(bid)
            if bid <= 0:
                continue
            sn = _short(_PALETTE_REF.get(bid, ""))
            if sn.endswith("_door") or sn == "door" or "glass" in sn:
                drop &= out != bid
    n = int(drop.sum())
    if n:
        out[drop] = 0
    return out, n


def unify_role_surfaces(
    voxels: np.ndarray,
    palette: dict[int, str],
    *,
    wall_id: int,
    floor_id: int,
    roof_id: int,
    foundation_id: int,
    accent_id: int,
    load_bearing_id: int = 0,
    floor_ys: list[int] | None = None,
    max_accent_frac: float = 0.12,
) -> tuple[np.ndarray, list[str]]:
    """Force one wall / roof / floor mat; keep glass/door/stairs; cap accent spam."""
    out = np.asarray(voxels, dtype=np.int16).copy()
    actions: list[str] = []
    solid = out > 0
    if not solid.any():
        return out, ["unify_skip_empty"]

    sx, sy, sz = out.shape
    wall_id = int(wall_id)
    floor_id = int(floor_id) or wall_id
    roof_id = int(roof_id) or wall_id
    foundation_id = int(foundation_id) or wall_id
    accent_id = int(accent_id) or wall_id
    load_bearing_id = int(load_bearing_id) or accent_id

    glass_ids = _glass_ids_from_palette(palette)
    door_ids: set[int] = set()
    stair_ids: set[int] = set()
    for i, name in palette.items():
        sn = _short(name).lower()
        if int(i) <= 0:
            continue
        if sn.endswith("_door") or sn == "door":
            door_ids.add(int(i))
        if "stair" in sn:
            stair_ids.add(int(i))

    keep_special = set(glass_ids) | door_ids | stair_ids
    keep_special |= {wall_id, floor_id, roof_id, foundation_id}
    # Only keep accent/load_bearing if they look structural (not colored junk / bone / dirt)
    def _accent_ok(bid: int) -> bool:
        if bid <= 0 or bid == wall_id:
            return False
        sn = _short(palette.get(bid, "")).lower()
        if _is_junk(sn):
            return False
        bad = (
            "bone", "dirt", "moss", "hopper", "green_concrete", "lime_concrete",
            "yellow_concrete", "pink_concrete", "magenta_concrete", "purple_concrete",
            "blue_concrete", "cyan_concrete", "orange_concrete", "brown_concrete",
            "red_concrete", "acacia", "mangrove", "bamboo",
        )
        return not any(b in sn for b in bad)

    if _accent_ok(accent_id):
        keep_special.add(accent_id)
    if _accent_ok(load_bearing_id):
        keep_special.add(load_bearing_id)
    keep_special.discard(0)

    fp, _ = _footprint(solid)
    peri = _perimeter_mask(fp)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    y0, y1 = int(ys.min()), int(ys.max())

    xs_fp, zs_fp = np.where(fp)
    if xs_fp.size:
        minx, maxx = int(xs_fp.min()), int(xs_fp.max())
        minz, maxz = int(zs_fp.min()), int(zs_fp.max())
        corners = {(minx, minz), (minx, maxz), (maxx, minz), (maxx, maxz)}
    else:
        corners = set()

    remapped = 0
    accent_cleared = 0
    for bid in np.unique(out[out > 0]).tolist():
        bid = int(bid)
        if bid in keep_special:
            continue
        sn = _short(palette.get(bid, "")).lower()
        if sn.endswith("_door") or "glass" in sn or "stair" in sn:
            continue
        mask = out == bid
        n = int(mask.sum())
        if n:
            out[mask] = wall_id
            remapped += n
    if remapped:
        actions.append("unify_remap_to_wall:%d" % remapped)

    n_found = 0
    xs, zs = np.where(fp)
    for x, z in zip(xs.tolist(), zs.tolist()):
        cur = int(out[x, y0, z])
        if cur > 0 and cur not in glass_ids and cur not in door_ids:
            if cur != foundation_id:
                out[x, y0, z] = foundation_id
                n_found += 1
    if n_found:
        actions.append("unify_foundation:%d" % n_found)

    peaks = [int(y) for y in (floor_ys or []) if y0 < int(y) < y1]
    if not peaks:
        floors = _floor_metrics(out > 0)
        peaks = [int(y) for y in (floors.get("y_peaks") or []) if y0 < int(y) < y1]
    n_floor = 0
    for y in peaks:
        for x, z in zip(xs.tolist(), zs.tolist()):
            if not fp[x, z]:
                continue
            cur = int(out[x, y, z])
            if cur <= 0:
                continue
            if cur in glass_ids or cur in door_ids:
                continue
            if peri[x, z]:
                continue
            if cur != floor_id:
                out[x, y, z] = floor_id
                n_floor += 1
    if n_floor:
        actions.append("unify_floors:%d" % n_floor)

    n_roof = 0
    for x, z in zip(xs.tolist(), zs.tolist()):
        col = out[x, :, z]
        ys_col = np.where(col > 0)[0]
        if ys_col.size == 0:
            continue
        yt = int(ys_col.max())
        cur = int(out[x, yt, z])
        if cur in glass_ids or cur in door_ids or cur in stair_ids:
            continue
        if cur != roof_id:
            out[x, yt, z] = roof_id
            n_roof += 1
    if n_roof:
        actions.append("unify_roof:%d" % n_roof)

    n_wall = 0
    accent_ids = {accent_id, load_bearing_id}
    for x, z in zip(xs.tolist(), zs.tolist()):
        if not peri[x, z]:
            continue
        is_corner = (x, z) in corners
        for y in range(y0 + 1, y1):
            cur = int(out[x, y, z])
            if cur <= 0:
                continue
            if cur in glass_ids or cur in door_ids or cur in stair_ids:
                continue
            if is_corner and cur in accent_ids:
                continue
            if cur == wall_id:
                continue
            out[x, y, z] = wall_id
            n_wall += 1
            if cur in accent_ids:
                accent_cleared += 1
    if n_wall:
        actions.append("unify_peri_wall:%d" % n_wall)

    solids_n = int((out > 0).sum())
    if solids_n > 0 and accent_id > 0 and accent_id != wall_id:
        acc_n = int((out == accent_id).sum())
        if load_bearing_id and load_bearing_id != wall_id and load_bearing_id != accent_id:
            acc_n += int((out == load_bearing_id).sum())
        frac = acc_n / float(solids_n)
        if frac > float(max_accent_frac):
            budget = int(float(max_accent_frac) * solids_n)
            extra = acc_n - budget
            cleared = 0
            for x in range(sx):
                for z in range(sz):
                    if cleared >= extra:
                        break
                    if (x, z) in corners:
                        continue
                    for y in range(sy):
                        if cleared >= extra:
                            break
                        cur = int(out[x, y, z])
                        if cur in accent_ids and cur != wall_id:
                            out[x, y, z] = wall_id
                            cleared += 1
                            accent_cleared += 1
            if cleared:
                actions.append(
                    "accent_cap:%d (frac %.3f->target %.3f)"
                    % (cleared, frac, max_accent_frac)
                )

    if accent_cleared and not any(a.startswith("accent_cap") for a in actions):
        actions.append("accent_cleared_peri:%d" % accent_cleared)

    solid2 = out > 0
    n_cc, sizes, labels = _connected_components(solid2)
    if n_cc > 1 and sizes:
        best_label = 1
        best_count = 0
        for lab in range(1, n_cc + 1):
            c = int((labels == lab).sum())
            if c > best_count:
                best_count = c
                best_label = lab
        drop = (labels > 0) & (labels != best_label)
        n_drop = int(drop.sum())
        if n_drop:
            out[drop] = 0
            actions.append("unify_drop_float_cc:%d" % n_drop)

    prot = set(door_ids) | set(glass_ids)
    out, n_sp = despeckle_solids(out, min_neighbors=2, protected_ids=prot)
    if n_sp:
        actions.append("despeckle:%d" % n_sp)

    return out, actions



def look_harden(
    voxels: np.ndarray,
    palette: dict[int, str],
    *,
    style: str | None = None,
    top_k: int = 6,
    keep_trim_top: int = 2,
    harden_geometry: bool = True,
    geometry_mode: str | None = None,
    floor_spacing: int | None = None,
    shell_thickness: int | None = None,
    fill_wall_holes: bool = True,
    regular_floors: bool = True,
    smooth_roof: bool = True,
    preserve_windows: bool | None = None,
    place_window_glass: bool | None = None,
    facade_detail: bool | None = None,
    use_knowledge: bool = True,
    role_materials: dict[str, int] | None = None,
) -> tuple[np.ndarray, LookHardenReport]:
    rules = knowledge_defaults() if use_knowledge else {}
    if geometry_mode is None:
        geometry_mode = str(rules.get("geometry_mode", "strong"))
    floor_spacing = _clamp_floor_spacing(floor_spacing, rules or None)
    if shell_thickness is None:
        shell_thickness = int(rules.get("shell_thickness", 1))
    if preserve_windows is None:
        preserve_windows = bool(rules.get("preserve_windows", True))
    if place_window_glass is None:
        place_window_glass = bool(rules.get("place_window_glass", True))
    if facade_detail is None:
        facade_detail = bool(rules.get("facade_detail", True))

    vox0 = np.asarray(voxels, dtype=np.int16)
    before = check_structure(vox0)
    uniq_b = int(len(np.unique(vox0[vox0 > 0]))) if (vox0 > 0).any() else 0
    _set_palette_ref(palette)

    actions: list[str] = []
    if use_knowledge and rules:
        actions.append(
            "knowledge_rules:v%s floor_sp=%d shell=%d win_sp=%s"
            % (
                load_knowledge_rules().get("version", 0),
                int(floor_spacing),
                int(shell_thickness),
                rules.get("window_spacing"),
            )
        )
    force_keep = role_ids_list(role_materials) if role_materials else None
    # With role materials, keep palette tight (wall/roof/floor/accent + glass/door).
    _tk = 4 if force_keep else int(top_k)
    _kt = 1 if force_keep else int(keep_trim_top)
    out, pal_stats = limit_palette(
        vox0,
        palette,
        style=style,
        top_k=max(_tk, len(force_keep or [])),
        keep_trim_top=_kt,
        force_keep=force_keep,
    )
    actions.append(
        "palette_limit: %d->%d remapped=%d"
        % (pal_stats["unique_before"], pal_stats["unique_after"], pal_stats["remapped"])
    )

    wall_id, floor_id, fill_info = pick_fill_ids(
        out, palette, style=style, role_materials=role_materials
    )
    pal_stats["fill"] = fill_info
    roof_id = int(fill_info.get("roof_id") or wall_id)
    foundation_id = int(fill_info.get("foundation_id") or wall_id)
    accent_id = int(fill_info.get("accent_id") or wall_id)
    load_bearing_id = int(
        (role_materials or {}).get("load_bearing")
        or fill_info.get("load_bearing_id")
        or (fill_info.get("roles") or {}).get("load_bearing")
        or accent_id
    )
    if role_materials:
        actions.append(
            "role_materials:wall=%s roof=%s floor=%s foundation=%s accent=%s load=%s"
            % (
                fill_info.get("wall_name"),
                _short(palette.get(roof_id, "?")),
                fill_info.get("floor_name"),
                _short(palette.get(foundation_id, "?")),
                _short(palette.get(accent_id, "?")),
                _short(palette.get(load_bearing_id, "?")),
            )
        )

    geo_extra: dict[str, Any] = {}
    if harden_geometry:
        # shell/floor metrics before geometry harden (after palette)
        ys = np.where((out > 0).any(axis=(0, 2)))[0]
        y0 = int(ys.min()) if ys.size else 0
        y1 = int(ys.max()) if ys.size else 0
        holes_b = wall_hole_count(out, y0, y1)
        flat_b = floor_flatness_score(out)
        mode = (geometry_mode or "strong").strip().lower()
        if mode in ("basic", "legacy", "old"):
            out, geo = harden_shell_and_floors_basic(
                out,
                wall_id=wall_id,
                floor_id=floor_id,
                floor_spacing=_clamp_floor_spacing(int(floor_spacing)),
            )
            actions.append("geometry_mode:basic")
        else:
            glass_id = _resolve_glass_id(palette, style=style) if place_window_glass else 0
            out, geo = harden_shell_and_floors(
                out,
                wall_id=wall_id,
                floor_id=floor_id,
                floor_spacing=int(floor_spacing),
                shell_thickness=int(shell_thickness),
                fill_wall_holes=bool(fill_wall_holes),
                regular_floors=bool(regular_floors),
                hollow_floors=True,
                smooth_roof=bool(smooth_roof),
                preserve_windows=bool(preserve_windows),
                place_window_glass=bool(place_window_glass),
                glass_id=int(glass_id),
                facade_detail=bool(facade_detail),
                style=style,
                palette=palette,
                use_knowledge=bool(use_knowledge),
                role_materials={
                    "wall": int(wall_id),
                    "floor": int(floor_id),
                    "roof": int(roof_id),
                    "foundation": int(foundation_id),
                    "accent": int(load_bearing_id if load_bearing_id else accent_id),
                    "window_frame": int(fill_info.get("window_frame_id") or accent_id),
                    "load_bearing": int(load_bearing_id),
                },
            )
            actions.append("geometry_mode:strong")
            actions.append(
                "preserve_windows:%s" % ("on" if preserve_windows else "off")
            )
        actions.extend(geo)
        ys2 = np.where((out > 0).any(axis=(0, 2)))[0]
        y0a = int(ys2.min()) if ys2.size else 0
        y1a = int(ys2.max()) if ys2.size else 0
        holes_a = wall_hole_count(out, y0a, y1a)
        placed_ys: list[int] = []
        for a in geo:
            if "@y=" in a and "flat_floors" in a:
                try:
                    raw = a.split("@y=", 1)[1].strip()
                    placed_ys = [int(x) for x in raw.strip("[]").replace(" ", "").split(",") if x]
                except Exception:
                    placed_ys = []
        flat_a = floor_flatness_score(out, floor_ys=placed_ys or None)
        win_a = window_opening_count(out, y0=y0a, y1=y1a, floor_ys=placed_ys or None)
        # total glass anywhere (eaves expand footprint so peri-glass can look like 0)
        glass_ids = _glass_ids_from_palette(palette)
        glass_total = (
            int(sum(int((out == g).sum()) for g in glass_ids))
            if glass_ids
            else int(win_a.get("glass_cells", 0))
        )
        fac_door = fac_eave = fac_band = fac_pillar = 0
        fac_roof = ""
        for a in geo:
            if a.startswith("facade_stats:"):
                # facade_stats:door=%d eave=%d band=%d pillar=%d roof=%s
                try:
                    body = a.split(":", 1)[1]
                    parts = dict(
                        kv.split("=", 1) for kv in body.split() if "=" in kv
                    )
                    fac_door = int(parts.get("door", 0))
                    fac_eave = int(parts.get("eave", 0))
                    fac_band = int(parts.get("band", 0))
                    fac_pillar = int(parts.get("pillar", 0))
                    fac_roof = str(parts.get("roof", ""))
                except Exception:
                    pass
        geo_extra = {
            "wall_holes_before": holes_b,
            "wall_holes_after": holes_a,
            "floor_flatness_before": flat_b.get("floor_flatness", 0.0),
            "floor_flatness_after": flat_a.get("floor_flatness", 0.0),
            "floor_ys": placed_ys or flat_a.get("floor_ys", []),
            "preserve_windows": bool(preserve_windows),
            "window_cells_after": int(win_a.get("window_cells", 0)),
            "window_components_after": int(win_a.get("window_components", 0)),
            "glass_cells_after": int(win_a.get("glass_cells", 0)),
            "glass_total_after": glass_total,
            "facade_detail": bool(facade_detail),
            "door_cells": fac_door,
            "eave_cells": fac_eave,
            "banding_cells": fac_band,
            "pillar_cells": fac_pillar,
            "roof_mode": fac_roof,
        }
        pal_stats["shell_floors"] = geo_extra

    # --- clean material noise (one wall/roof/floor; despeckle; cap accent) ---
    if role_materials:
        fl_ys = []
        for a in actions:
            if "flat_floors" in a and "@y=" in a:
                try:
                    raw = a.split("@y=", 1)[1].strip()
                    fl_ys = [int(x) for x in raw.strip("[]").replace(" ", "").split(",") if x]
                except Exception:
                    fl_ys = []
        out, clean_acts = unify_role_surfaces(
            out,
            palette,
            wall_id=int(wall_id),
            floor_id=int(floor_id),
            roof_id=int(roof_id),
            foundation_id=int(foundation_id),
            accent_id=int(load_bearing_id if load_bearing_id else accent_id),
            load_bearing_id=int(load_bearing_id),
            floor_ys=fl_ys or None,
            max_accent_frac=0.10,
        )
        actions.extend(clean_acts)
        if clean_acts:
            actions.append("clean_mats:on")

    # --- final stray cleanup: decor passes (roof/eave/pillar) run after
    # harden_facade's internal despeckle, so prune again at the exit ---
    prot_ids = {
        int(bid)
        for bid, name in palette.items()
        if int(bid) > 0
        and any(
            tok in _short(name)
            for tok in ("door", "glass", "stair", "water", "ladder", "torch", "lantern")
        )
    }
    out, reg_stats = regularize_form(out, protect_ids=prot_ids)
    if reg_stats["flatten"] or reg_stats["roof_removed"] or reg_stats["roof_added"]:
        actions.append(
            "regularize_form: flat=%d roof=-%d/+%d"
            % (reg_stats["flatten"], reg_stats["roof_removed"], reg_stats["roof_added"])
        )

    out, stray_stats = prune_strays(out, protect_ids=prot_ids)
    if stray_stats["total"]:
        actions.append(
            "prune_strays:%d (iso=%d spike=%d island=%d)"
            % (
                stray_stats["total"],
                stray_stats["isolated"],
                stray_stats["spike"],
                stray_stats["island"],
            )
        )

    after = check_structure(out)
    # attach shell/floor metrics into after metrics for easy A/B
    if geo_extra:
        after_m = dict(after.metrics)
        after_m["wall_hole_count"] = geo_extra["wall_holes_after"]
        after_m["floor_flatness"] = geo_extra["floor_flatness_after"]
        after_m["window_cells"] = geo_extra.get("window_cells_after", 0)
        after_m["window_components"] = geo_extra.get("window_components_after", 0)
        after_m["glass_cells"] = geo_extra.get("glass_cells_after", 0)
        after_m["glass_total"] = geo_extra.get("glass_total_after", 0)
        after_m["preserve_windows"] = geo_extra.get("preserve_windows", True)
        after_m["door_cells"] = geo_extra.get("door_cells", 0)
        after_m["eave_cells"] = geo_extra.get("eave_cells", 0)
        after_m["banding_cells"] = geo_extra.get("banding_cells", 0)
        after_m["pillar_cells"] = geo_extra.get("pillar_cells", 0)
        after_m["roof_mode"] = geo_extra.get("roof_mode", "")
        after_m["facade_detail"] = geo_extra.get("facade_detail", True)
        after = type(after)(ok=after.ok, reasons=list(after.reasons), metrics=after_m, repairs=list(getattr(after, "repairs", []) or []))
    uniq_a = int(len(np.unique(out[out > 0]))) if (out > 0).any() else 0
    report = LookHardenReport(
        ok=bool(after.ok),
        actions=actions,
        metrics_before=dict(before.metrics),
        metrics_after=dict(after.metrics),
        palette_stats=pal_stats,
        uniqu_before=uniq_b,
        uniqu_after=uniq_a,
    )
    return out, report


def summarize_look_reports(reports: list[LookHardenReport]) -> dict[str, Any]:
    if not reports:
        return {"n": 0}
    return {
        "n": len(reports),
        "avg_unique_before": float(sum(r.uniqu_before for r in reports) / len(reports)),
        "avg_unique_after": float(sum(r.uniqu_after for r in reports) / len(reports)),
        "pass_after": sum(1 for r in reports if r.ok) / len(reports),
        "avg_hollow_after": float(
            sum(float(r.metrics_after.get("hollow_score", 0)) for r in reports)
            / len(reports)
        ),
        "avg_roof_after": float(
            sum(float(r.metrics_after.get("roof_score", 0)) for r in reports)
            / len(reports)
        ),
    }
