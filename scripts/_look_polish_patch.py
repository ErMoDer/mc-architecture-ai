# -*- coding: utf-8 -*-
"""Apply look-polish patches to scaffold_materials.py and gen_strategy.py."""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"E:\ai agent\mc-architecture-ai")

# ---------------------------------------------------------------------------
# scaffold_materials.py
# ---------------------------------------------------------------------------
SM = ROOT / "src" / "app" / "scaffold_materials.py"
sm = SM.read_text(encoding="utf-8")

OLD_SKIP = '''_SKIP_SUBSTR = (
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
)'''

NEW_SKIP = '''_SKIP_SUBSTR = (
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
            "acacia", "mangrove", "bamboo", "cherry", "crimson", "warped",
            "mud", "packed_mud", "mud_brick", "nether", "blackstone",
            "purpur", "end_stone", "prismarine", "copper", "terracotta",
            "concrete", "wool", "hay", "mushroom", "stem",
        ),
        "roof": (
            "acacia", "mangrove", "bamboo", "cherry", "mud", "packed_mud",
            "wool", "concrete", "glass", "copper",
        ),
        "accent": ("mud", "packed_mud", "mangrove", "bamboo"),
    },
    "medieval": {
        "wall": (
            "acacia", "mangrove", "bamboo", "cherry", "crimson", "warped",
            "mud", "packed_mud", "concrete", "quartz", "purpur", "copper",
            "wool", "terracotta",
        ),
        "roof": ("acacia", "mangrove", "bamboo", "cherry", "concrete", "quartz", "wool", "mud"),
        "foundation": ("plank", "log", "wool", "concrete", "acacia"),
    },
    "chinese": {
        # Prefer wood / stone / plaster over mud-brick earth unless desert.
        "wall": (
            "mud_brick", "packed_mud", "mud", "acacia", "mangrove", "bamboo",
            "crimson", "warped", "concrete", "quartz", "purpur", "copper",
            "nether", "blackstone", "prismarine",
        ),
        "roof": ("mud", "packed_mud", "concrete", "quartz", "acacia", "mangrove"),
    },
    "japanese": {
        "wall": ("mud_brick", "packed_mud", "acacia", "mangrove", "crimson", "warped", "concrete", "purpur"),
    },
    "modern": {
        "wall": (
            "acacia", "mangrove", "bamboo", "cherry", "mud", "packed_mud",
            "nether", "purpur", "hay", "wool", "log", "plank",
        ),
        "roof": ("plank", "log", "mud", "wool", "hay", "acacia"),
    },
    "rustic": {
        "wall": (
            "acacia", "mangrove", "crimson", "warped", "concrete", "quartz",
            "purpur", "copper", "mud_brick", "packed_mud",
        ),
        "roof": ("concrete", "quartz", "purpur", "acacia", "mangrove", "mud"),
    },
    "fantasy": {
        "wall": ("acacia", "mangrove", "mud_brick", "packed_mud", "concrete"),
    },
    "industrial": {
        "wall": ("acacia", "mangrove", "bamboo", "cherry", "wool", "hay", "mud", "plank"),
    },
    "desert": {
        # mud/sandstone/terracotta OK for desert
        "wall": ("acacia", "mangrove", "crimson", "warped", "concrete", "quartz", "purpur", "plank", "log"),
    },
    "western": {
        "wall": ("acacia", "mangrove", "crimson", "warped", "concrete", "quartz", "mud_brick", "packed_mud"),
    },
    "scifi": {
        "wall": ("plank", "log", "mud", "wool", "hay", "acacia", "mangrove", "bamboo"),
    },
}

# Woods that look wrong as European / medieval primary walls even if not denied above.
_HOUSE_WALL_WEIRD_WOOD = ("acacia", "mangrove", "bamboo", "cherry", "crimson", "warped", "jungle")'''

if OLD_SKIP not in sm:
    raise SystemExit("OLD_SKIP block not found in scaffold_materials.py")
sm = sm.replace(OLD_SKIP, NEW_SKIP, 1)

# Insert helpers after _is_skip
OLD_IS_SKIP = '''def _is_skip(short: str) -> bool:
    s = short.lower()
    if s in ("air", "barrier", "structure_void", "light"):
        return True
    for tok in _SKIP_SUBSTR:
        if tok in s:
            return True
    return False


def _score_role(short: str, role: str) -> float:'''

NEW_IS_SKIP = '''def _is_skip(short: str) -> bool:
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


def _score_role(short: str, role: str, style: str | None = None) -> float:'''

if OLD_IS_SKIP not in sm:
    raise SystemExit("_is_skip block not found")
sm = sm.replace(OLD_IS_SKIP, NEW_IS_SKIP, 1)

# Update _score_role body start to check style deny
OLD_SCORE_START = '''def _score_role(short: str, role: str, style: str | None = None) -> float:
    s = short.lower()
    if _is_skip(s):
        return -1.0
    # stairs/slabs are weak full blocks; prefer for roof only'''

NEW_SCORE_START = '''def _score_role(short: str, role: str, style: str | None = None) -> float:
    s = short.lower()
    if _is_skip(s):
        return -1.0
    if _style_role_denied(s, role, style):
        return -1.0
    # stairs/slabs are weak full blocks; prefer for roof only'''

if OLD_SCORE_START not in sm:
    raise SystemExit("_score_role start not found after patch")
sm = sm.replace(OLD_SCORE_START, NEW_SCORE_START, 1)

# Update pick() to pass style and track denials
OLD_PICK = '''    def pick(role: str) -> int:
        best_id = None
        best_score = -1.0
        best_name = None
        for n, w in ref_names:
            sc = _score_role(n, role)
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
        if best_id is not None and best_score >= 1.0:
            info["source"] = "reference+style"
            return int(best_id)
        # style fallback
        pid = _resolve_id(name_to_id, list(fallbacks.get(role, ())))
        if pid is None:
            pid = _resolve_id(
                name_to_id,
                ["stone_bricks", "cobblestone", "oak_planks", "stone", "spruce_planks"],
            )
        return int(pid or 1)'''

NEW_PICK = '''    def pick(role: str) -> int:
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
        if best_id is not None and best_score >= 1.0:
            info["source"] = "reference+style"
            return int(best_id)
        # style fallback (preferred when refs were odd for this style)
        if denied and not (best_id is not None and best_score >= 1.0):
            info["source"] = "style_fallback_denied_ref"
        pid = _resolve_id(name_to_id, list(fallbacks.get(role, ())))
        if pid is None:
            pid = _resolve_id(
                name_to_id,
                ["stone_bricks", "cobblestone", "oak_planks", "stone", "spruce_planks"],
            )
        return int(pid or 1)'''

if OLD_PICK not in sm:
    raise SystemExit("pick() block not found")
sm = sm.replace(OLD_PICK, NEW_PICK, 1)

# After prefer_full_cube loop, re-diversify roof/floor so remap can't collapse roof==wall
OLD_CUBE = '''    # Scaffold paints full cells: avoid stairs/slabs for mass roles (keep stair as roof hint only in name)
    for role in ("foundation", "wall", "floor", "accent", "window_frame", "roof"):
        bid = int(roles[role])
        short = role_names.get(role) or short_block_name(palette.get(bid, "?"))
        full = prefer_full_cube(name_to_id, short, palette, bid)
        if full != bid:
            roles[role] = full
            role_names[role] = short_block_name(palette.get(full, "?"))
            info.setdefault("full_cube_remap", {})[role] = {"from": short, "to": role_names[role]}

    info["roles"] = dict(roles)'''

NEW_CUBE = '''    # Scaffold paints full cells: avoid stairs/slabs for mass roles (keep stair as roof hint only in name)
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

    info["roles"] = dict(roles)'''

if OLD_CUBE not in sm:
    raise SystemExit("cube remap block not found")
sm = sm.replace(OLD_CUBE, NEW_CUBE, 1)

SM.write_text(sm, encoding="utf-8")
print("patched", SM)

# ---------------------------------------------------------------------------
# gen_strategy.py — sparse footprint fill + coherent euro deck
# ---------------------------------------------------------------------------
GS = ROOT / "src" / "app" / "gen_strategy.py"
gs = GS.read_text(encoding="utf-8")

OLD_PERI = '''def _perimeter_mask(fp: np.ndarray) -> np.ndarray:
    fp = np.asarray(fp, dtype=bool)
    peri = np.zeros_like(fp)
    h, w = fp.shape
    for x in range(h):
        for z in range(w):
            if not fp[x, z]:
                continue
            if x == 0 or z == 0 or x == h - 1 or z == w - 1:
                peri[x, z] = True
                continue
            if not (fp[x - 1, z] and fp[x + 1, z] and fp[x, z - 1] and fp[x, z + 1]):
                peri[x, z] = True
    return peri


def _building_footprint_from_occ(occ: np.ndarray) -> np.ndarray:'''

NEW_PERI = '''def _perimeter_mask(fp: np.ndarray) -> np.ndarray:
    fp = np.asarray(fp, dtype=bool)
    peri = np.zeros_like(fp)
    h, w = fp.shape
    for x in range(h):
        for z in range(w):
            if not fp[x, z]:
                continue
            if x == 0 or z == 0 or x == h - 1 or z == w - 1:
                peri[x, z] = True
                continue
            if not (fp[x - 1, z] and fp[x + 1, z] and fp[x, z - 1] and fp[x, z + 1]):
                peri[x, z] = True
    return peri


def _fill_footprint_holes(fp: np.ndarray) -> np.ndarray:
    """Fill interior holes / sparse outline rings so roof deck is coherent.

    Flood-fill from border through empty cells; remaining False = enclosed voids → True.
    Also dilate once then erode (morph close) for thin Victorian outline gaps.
    """
    fp = np.asarray(fp, dtype=bool)
    h, w = fp.shape
    if not fp.any():
        return fp.copy()
    # Morphological close (1-cell) to bridge 1-voxel gaps in outlines
    dil = fp.copy()
    xs, zs = np.where(fp)
    for x, z in zip(xs.tolist(), zs.tolist()):
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                xx, zz = x + dx, z + dz
                if 0 <= xx < h and 0 <= zz < w:
                    dil[xx, zz] = True
    # erode back
    closed = np.zeros_like(fp)
    for x in range(h):
        for z in range(w):
            if not dil[x, z]:
                continue
            ok = True
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    xx, zz = x + dx, z + dz
                    if not (0 <= xx < h and 0 <= zz < w and dil[xx, zz]):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                closed[x, z] = True
    if int(closed.sum()) < max(8, int(0.5 * int(fp.sum()))):
        closed = dil  # fall back to dilation if erode wiped thin rings
    # Flood-fill exterior empties
    exterior = np.zeros_like(closed)
    stack = []
    for x in range(h):
        for z in (0, w - 1):
            if not closed[x, z] and not exterior[x, z]:
                stack.append((x, z))
                exterior[x, z] = True
    for z in range(w):
        for x in (0, h - 1):
            if not closed[x, z] and not exterior[x, z]:
                stack.append((x, z))
                exterior[x, z] = True
    while stack:
        x, z = stack.pop()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, zz = x + dx, z + dz
            if 0 <= xx < h and 0 <= zz < w and (not closed[xx, zz]) and (not exterior[xx, zz]):
                exterior[xx, zz] = True
                stack.append((xx, zz))
    filled = closed | (~exterior & ~closed)
    # Keep original solid columns; never shrink
    filled = filled | fp
    # If fill exploded (>3x), keep closed only
    if int(filled.sum()) > max(int(3 * int(fp.sum())), int(0.85 * h * w)):
        filled = closed | fp
    return filled


def _footprint_sparse(fp: np.ndarray) -> bool:
    """True when footprint is outline-like (low fill inside bbox)."""
    fp = np.asarray(fp, dtype=bool)
    if not fp.any():
        return True
    xs, zs = np.where(fp)
    x0, x1 = int(xs.min()), int(xs.max())
    z0, z1 = int(zs.min()), int(zs.max())
    area = max(1, (x1 - x0 + 1) * (z1 - z0 + 1))
    fill = float(fp.sum()) / float(area)
    peri = _perimeter_mask(fp)
    peri_frac = float(peri.sum()) / max(1.0, float(fp.sum()))
    return fill < 0.48 or peri_frac > 0.72


def _building_footprint_from_occ(occ: np.ndarray) -> np.ndarray:'''

if OLD_PERI not in gs:
    raise SystemExit("perimeter block not found in gen_strategy")
gs = gs.replace(OLD_PERI, NEW_PERI, 1)

# Replace roof deck section inside scaffold_from_occupancy
OLD_ROOF = '''    style_l = (style or "").strip().lower()
    if style_l in ("rustic", "western", "japanese"):
        max_rise = 2
    elif style_l in ("fantasy", "medieval", "european", "chinese"):
        max_rise = 3
    else:
        max_rise = 2

    for y in range(y_foundation, min(roof_deck_y, sy - 1) + 1):
        slice_fp = occ[:, y, :] & build_fp
        # Always paint full build perimeter so tapered upper rings stay connected
        # to the lower shell (otherwise repair drop_float_cc chops the roof).
        peri_block = int(foundation_id) if y <= y_foundation else int(wall_id)
        out[:, y, :][peri] = peri_block
        if y <= y_foundation:
            stats["foundation"] += int(peri.sum())
        else:
            stats["shell"] += int(peri.sum())
        floor_mask = build_fp
        if slice_fp.any():
            slice_peri = _perimeter_mask(slice_fp)
            if not slice_peri.any():
                slice_peri = peri & slice_fp
            if shell_thickness > 1:
                thick = slice_peri.copy()
                xs, zs = np.where(slice_peri)
                for x, z in zip(xs.tolist(), zs.tolist()):
                    for dx in range(-shell_thickness + 1, shell_thickness):
                        for dz in range(-shell_thickness + 1, shell_thickness):
                            xx, zz = x + dx, z + dz
                            if 0 <= xx < sx and 0 <= zz < sz and slice_fp[xx, zz]:
                                thick[xx, zz] = True
                slice_peri = thick
            out[:, y, :][slice_peri] = peri_block
            if y <= y_foundation:
                stats["foundation"] += int(slice_peri.sum())
            else:
                stats["shell"] += int(slice_peri.sum())
            floor_mask = slice_fp

        if y in floor_ys and build_fp.any():
            use_fp = floor_mask if floor_mask.any() else build_fp
            out[:, y, :][use_fp] = int(floor_id)
            out[:, y, :][peri] = peri_block
            stats["floors"] += int(use_fp.sum())

    if build_fp.any() and 0 <= roof_deck_y < sy:
        xs, zs = np.where(build_fp)
        cx = float(xs.mean())
        cz = float(zs.mean())
        dists = np.sqrt((xs.astype(np.float64) - cx) ** 2 + (zs.astype(np.float64) - cz) ** 2)
        max_d = float(dists.max()) if dists.size else 1.0
        max_d = max(1.0, max_d)
        roof_count = 0
        for x, z, d in zip(xs.tolist(), zs.tolist(), dists.tolist()):
            rise = int(round(max_rise * (1.0 - float(d) / max_d)))
            yy_deck = int(roof_deck_y)
            yy_peak = int(min(sy - 1, yy_deck + max(0, rise)))
            hy = int(hmap[x, z])
            if hy >= 0:
                yy_peak = int(min(sy - 1, max(yy_peak, min(hy, yy_deck + max_rise + 1))))
            for yy in range(yy_deck, yy_peak + 1):
                out[x, yy, z] = int(roof_id)
                roof_count += 1
            if peri[x, z] and yy_deck - 1 >= y_foundation:
                if out[x, yy_deck - 1, z] == 0:
                    out[x, yy_deck - 1, z] = int(roof_id)
                    roof_count += 1
        stats["roof"] = int(roof_count)
        stats["roof_mode"] = "low_pitch_deck"'''

NEW_ROOF = '''    style_l = (style or "").strip().lower()
    sparse_fp = _footprint_sparse(build_fp)
    stats["sparse_fp"] = bool(sparse_fp)
    # Roof footprint: fill outline holes so Victorian/sparse euro refs get a real deck
    roof_fp = _fill_footprint_holes(build_fp) if build_fp.any() else build_fp
    stats["roof_fp"] = int(roof_fp.sum()) if roof_fp is not None else 0
    if style_l in ("rustic", "western", "japanese"):
        max_rise = 2
    elif style_l in ("fantasy", "medieval", "chinese"):
        max_rise = 3
    elif style_l == "european":
        # European sparse outlines: prefer coherent low deck over needle peak
        max_rise = 1 if sparse_fp else 2
    else:
        max_rise = 2
    if sparse_fp and style_l in ("european", "medieval", "modern"):
        max_rise = min(max_rise, 1)
    stats["max_rise"] = int(max_rise)

    for y in range(y_foundation, min(roof_deck_y, sy - 1) + 1):
        slice_fp = occ[:, y, :] & build_fp
        # Always paint full build perimeter so tapered upper rings stay connected
        # to the lower shell (otherwise repair drop_float_cc chops the roof).
        peri_block = int(foundation_id) if y <= y_foundation else int(wall_id)
        out[:, y, :][peri] = peri_block
        if y <= y_foundation:
            stats["foundation"] += int(peri.sum())
        else:
            stats["shell"] += int(peri.sum())
        floor_mask = build_fp
        if slice_fp.any():
            slice_peri = _perimeter_mask(slice_fp)
            if not slice_peri.any():
                slice_peri = peri & slice_fp
            if shell_thickness > 1:
                thick = slice_peri.copy()
                xs, zs = np.where(slice_peri)
                for x, z in zip(xs.tolist(), zs.tolist()):
                    for dx in range(-shell_thickness + 1, shell_thickness):
                        for dz in range(-shell_thickness + 1, shell_thickness):
                            xx, zz = x + dx, z + dz
                            if 0 <= xx < sx and 0 <= zz < sz and slice_fp[xx, zz]:
                                thick[xx, zz] = True
                slice_peri = thick
            out[:, y, :][slice_peri] = peri_block
            if y <= y_foundation:
                stats["foundation"] += int(slice_peri.sum())
            else:
                stats["shell"] += int(slice_peri.sum())
            floor_mask = slice_fp

        if y in floor_ys and build_fp.any():
            use_fp = floor_mask if floor_mask.any() else build_fp
            # For sparse outlines, fill floor with roof_fp interior so rooms aren't empty rings
            if sparse_fp and roof_fp is not None and int(roof_fp.sum()) > int(use_fp.sum()):
                use_fp = roof_fp
            out[:, y, :][use_fp] = int(floor_id)
            out[:, y, :][peri] = peri_block
            stats["floors"] += int(use_fp.sum())

    if build_fp.any() and 0 <= roof_deck_y < sy:
        use_roof_fp = roof_fp if roof_fp is not None and roof_fp.any() else build_fp
        xs, zs = np.where(use_roof_fp)
        cx = float(xs.mean())
        cz = float(zs.mean())
        dists = np.sqrt((xs.astype(np.float64) - cx) ** 2 + (zs.astype(np.float64) - cz) ** 2)
        max_d = float(dists.max()) if dists.size else 1.0
        max_d = max(1.0, max_d)
        roof_count = 0
        yy_deck = int(roof_deck_y)
        # 1) Solid coherent deck over filled footprint (fixes sparse euro tip roofs)
        for x, z in zip(xs.tolist(), zs.tolist()):
            out[x, yy_deck, z] = int(roof_id)
            roof_count += 1
            if peri[x, z] if x < peri.shape[0] and z < peri.shape[1] else False:
                if yy_deck - 1 >= y_foundation and out[x, yy_deck - 1, z] == 0:
                    out[x, yy_deck - 1, z] = int(roof_id)
                    roof_count += 1
        # 2) Optional low pitch / plateau on top of deck (avoid needle peaks)
        plateau_r = 0.78 if sparse_fp or style_l == "european" else 0.45
        for x, z, d in zip(xs.tolist(), zs.tolist(), dists.tolist()):
            rise = int(round(max_rise * (1.0 - float(d) / max_d)))
            # Broad plateau: inner footprint shares nearly the same top Y
            if float(d) / max_d <= plateau_r:
                rise = max(rise, max_rise)
            yy_peak = int(min(sy - 1, yy_deck + max(0, rise)))
            hy = int(hmap[x, z]) if 0 <= x < hmap.shape[0] and 0 <= z < hmap.shape[1] else -1
            if hy >= yy_deck:
                yy_peak = int(min(sy - 1, max(yy_peak, min(hy, yy_deck + max_rise))))
            for yy in range(yy_deck + 1, yy_peak + 1):
                out[x, yy, z] = int(roof_id)
                roof_count += 1
        # 3) Ensure shell walls connect up to deck under filled roof (reduce drop_float_cc)
        if sparse_fp:
            for x, z in zip(*np.where(use_roof_fp)):
                if not peri[x, z]:
                    # thin interior posts every few cells keep roof CC-linked
                    if (x + z) % 3 != 0:
                        continue
                for y in range(max(y_foundation + 1, yy_deck - 2), yy_deck):
                    if out[x, y, z] == 0:
                        out[x, y, z] = int(wall_id)
                        stats["shell"] += 1
        stats["roof"] = int(roof_count)
        stats["roof_mode"] = "low_pitch_deck_filled" if sparse_fp else "low_pitch_deck"'''

if OLD_ROOF not in gs:
    raise SystemExit("roof block not found in gen_strategy — file may have drifted")
gs = gs.replace(OLD_ROOF, NEW_ROOF, 1)

GS.write_text(gs, encoding="utf-8")
print("patched", GS)
print("OK")
