# -*- coding: utf-8 -*-
"""Patch clean materials: stronger deny, style-forced mass roles, despeckle + unify."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SM = ROOT / "src" / "app" / "scaffold_materials.py"
LH = ROOT / "src" / "app" / "look_harden.py"


def patch_scaffold_materials(text: str) -> str:
    # Expand industrial deny
    old_ind = '''    "industrial": {
        "wall": ("acacia", "mangrove", "bamboo", "cherry", "wool", "hay", "mud", "plank"),
    },'''
    new_ind = '''    "industrial": {
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
        "load_bearing": ("plank", "wool", "hay", "mud", "bone", "dirt", "moss"),
    },'''
    if old_ind not in text:
        raise SystemExit("industrial deny block not found")
    text = text.replace(old_ind, new_ind, 1)

    old_euro = '''    "european": {
        "wall": (
            "acacia", "mangrove", "bamboo", "cherry", "crimson", "warped",
            "mud", "packed_mud", "mud_brick", "nether", "blackstone",
            "purpur", "end_stone", "prismarine", "copper", "terracotta",
            "concrete", "wool", "hay", "mushroom", "stem",
            "sandstone", "red_sandstone", "cut_red", "chiseled_red", "copper",
        ),
        "roof": (
            "acacia", "mangrove", "bamboo", "cherry", "mud", "packed_mud",
            "wool", "concrete", "glass", "copper", "sandstone", "red_sandstone",
        ),
        "floor": ("acacia", "mangrove", "bamboo", "cherry", "mud", "wool", "concrete", "sandstone", "red_sandstone"),
        "foundation": ("acacia", "plank", "log", "wool", "sandstone", "red_sandstone", "copper", "mud"),
        "accent": ("mud", "packed_mud", "mangrove", "bamboo", "acacia", "sandstone", "red_sandstone"),
        "window_frame": ("acacia", "mangrove", "bamboo", "mud", "sandstone", "red_sandstone"),
    },'''
    new_euro = '''    "european": {
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
    },'''
    if old_euro not in text:
        raise SystemExit("european deny block not found")
    text = text.replace(old_euro, new_euro, 1)

    old_med = '''    "medieval": {
        "wall": (
            "acacia", "mangrove", "bamboo", "cherry", "crimson", "warped",
            "mud", "packed_mud", "concrete", "quartz", "purpur", "copper",
            "wool", "terracotta",
        ),
        "roof": ("acacia", "mangrove", "bamboo", "cherry", "concrete", "quartz", "wool", "mud"),
        "foundation": ("plank", "log", "wool", "concrete", "acacia"),
    },'''
    new_med = '''    "medieval": {
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
    },'''
    if old_med not in text:
        raise SystemExit("medieval deny block not found")
    text = text.replace(old_med, new_med, 1)

    old_west = '''    "western": {
        "wall": ("acacia", "mangrove", "crimson", "warped", "concrete", "quartz", "mud_brick", "packed_mud"),
    },'''
    new_west = '''    "western": {
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
    },'''
    if old_west not in text:
        raise SystemExit("western deny block not found")
    text = text.replace(old_west, new_west, 1)

    old_rustic = '''    "rustic": {
        "wall": (
            "acacia", "mangrove", "crimson", "warped", "concrete", "quartz",
            "purpur", "copper", "mud_brick", "packed_mud",
        ),
        "roof": ("concrete", "quartz", "purpur", "acacia", "mangrove", "mud"),
    },'''
    new_rustic = '''    "rustic": {
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
    },'''
    if old_rustic not in text:
        raise SystemExit("rustic deny block not found")
    text = text.replace(old_rustic, new_rustic, 1)

    old_modern = '''    "modern": {
        "wall": (
            "acacia", "mangrove", "bamboo", "cherry", "mud", "packed_mud",
            "nether", "purpur", "hay", "wool", "log", "plank",
        ),
        "roof": ("plank", "log", "mud", "wool", "hay", "acacia"),
    },'''
    new_modern = '''    "modern": {
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
    },'''
    if old_modern not in text:
        raise SystemExit("modern deny block not found")
    text = text.replace(old_modern, new_modern, 1)

    old_fan = '''    "fantasy": {
        "wall": ("acacia", "mangrove", "mud_brick", "packed_mud", "concrete"),
    },'''
    new_fan = '''    "fantasy": {
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
    },'''
    if old_fan not in text:
        raise SystemExit("fantasy deny block not found")
    text = text.replace(old_fan, new_fan, 1)

    # Force style mass roles: prefer STYLE_ROLE_FALLBACKS for wall/roof/floor/foundation
    old_pick_end = '''        # If we denied several odd refs for mass roles, prefer style fallback
        # unless the remaining ref scores strongly and looks house-like.
        prefer_fallback = denied >= 2 and role in ("wall", "roof", "foundation", "floor")
        if best_id is not None and best_score >= 1.0 and not prefer_fallback:
            info["source"] = "reference+style"
            return int(best_id)
        if best_id is not None and best_score >= 2.8 and prefer_fallback:
            # strong remaining candidate still wins
            info["source"] = "reference+style"
            return int(best_id)
        if denied:
            info["source"] = "style_fallback_denied_ref"
        pid = _resolve_id(name_to_id, list(fallbacks.get(role, ())))
        if pid is None:
            pid = _resolve_id(
                name_to_id,
                ["stone_bricks", "cobblestone", "oak_planks", "stone", "spruce_planks"],
            )
        return int(pid or 1)'''
    new_pick_end = '''        # Clean-house: mass roles (wall/roof/floor/foundation) always use style
        # fallbacks so ref rainbow / junk (green_concrete, bone, acacia, tuff) cannot
        # paint the shell. Accent / frame / load_bearing may still take a clean ref.
        mass = role in ("wall", "roof", "foundation", "floor")
        if mass:
            info["source"] = "style_fallback_clean"
            if denied:
                info.setdefault("style_denied_refs", {})[role] = int(denied)
            pid = _resolve_id(name_to_id, list(fallbacks.get(role, ())))
            if pid is None:
                pid = _resolve_id(
                    name_to_id,
                    ["stone_bricks", "cobblestone", "oak_planks", "stone", "spruce_planks"],
                )
            return int(pid or 1)
        # Non-mass: allow clean ref if it scored well
        if best_id is not None and best_score >= 1.5:
            info["source"] = "reference+style"
            return int(best_id)
        if denied:
            info["source"] = "style_fallback_denied_ref"
        pid = _resolve_id(name_to_id, list(fallbacks.get(role, ())))
        if pid is None:
            pid = _resolve_id(
                name_to_id,
                ["stone_bricks", "cobblestone", "oak_planks", "stone", "spruce_planks"],
            )
        return int(pid or 1)'''
    if old_pick_end not in text:
        raise SystemExit("pick() prefer_fallback block not found")
    text = text.replace(old_pick_end, new_pick_end, 1)

    # Global deny extras in _score_role for mass
    old_score_moss = '''        if any(x in s for x in ("moss", "grass", "dirt", "mud", "leaves", "wool", "carpet", "honey", "slime", "tnt")):
            return -1.0'''
    new_score_moss = '''        if any(x in s for x in (
            "moss", "grass", "dirt", "mud", "leaves", "wool", "carpet", "honey", "slime", "tnt",
            "bone", "hopper", "ore", "raw_iron", "raw_copper", "raw_gold", "netherrack",
            "sculk", "sponge", "coral", "mushroom", "nylium", "podzol", "farmland",
        )):
            return -1.0'''
    if old_score_moss not in text:
        raise SystemExit("score moss deny not found")
    text = text.replace(old_score_moss, new_score_moss, 1)

    return text


CLEAN_FN = r'''
def despeckle_solids(
    voxels: np.ndarray,
    *,
    min_neighbors: int = 2,
    protected_ids: set[int] | None = None,
) -> tuple[np.ndarray, int]:
    """Remove solid cells with fewer than min_neighbors solid 6-neighbors (speckles)."""
    out = np.asarray(voxels, dtype=np.int16).copy()
    sx, sy, sz = out.shape
    prot = set(int(x) for x in (protected_ids or set()) if int(x) > 0)
    solid = out > 0
    if not solid.any():
        return out, 0
    # Count 6-neighbors
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
    # Never drop door-like if palette known
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
    keep_special |= {wall_id, floor_id, roof_id, foundation_id, accent_id, load_bearing_id}
    keep_special.discard(0)

    fp, _ = _footprint(solid)
    peri = _perimeter_mask(fp)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    y0, y1 = int(ys.min()), int(ys.max())

    # Corner columns for allowed accent / load_bearing
    xs_fp, zs_fp = np.where(fp)
    if xs_fp.size:
        minx, maxx = int(xs_fp.min()), int(xs_fp.max())
        minz, maxz = int(zs_fp.min()), int(zs_fp.max())
        corners = {(minx, minz), (minx, maxz), (maxx, minz), (maxx, maxz)}
    else:
        corners = set()

    remapped = 0
    accent_cleared = 0
    # 1) Remap junk / off-role solids to wall (except specials)
    for bid in np.unique(out[out > 0]).tolist():
        bid = int(bid)
        if bid in keep_special:
            continue
        sn = _short(palette.get(bid, "")).lower()
        if sn.endswith("_door") or "glass" in sn or "stair" in sn:
            continue
        # off-palette structural noise -> wall
        mask = out == bid
        n = int(mask.sum())
        if n:
            out[mask] = wall_id
            remapped += n
    if remapped:
        actions.append("unify_remap_to_wall:%d" % remapped)

    # 2) Foundation strip
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

    # 3) Floor layers
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
                continue  # leave shell / piers on perimeter
            if cur != floor_id:
                out[x, y, z] = floor_id
                n_floor += 1
    if n_floor:
        actions.append("unify_floors:%d" % n_floor)

    # 4) Roof skin: top solid per column -> roof_id (keep stairs)
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
        # also one below if was roof-ish and not wall shell mid
        if yt - 1 > y0 and int(out[x, yt - 1, z]) == cur and cur not in (wall_id, floor_id, foundation_id):
            if int(out[x, yt - 1, z]) not in stair_ids and not peri[x, z]:
                pass
    if n_roof:
        actions.append("unify_roof:%d" % n_roof)

    # 5) Perimeter walls: force wall_id except corners (accent/load) and glass/door/stair
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
            # non-corner accent / mixed mat -> wall
            out[x, y, z] = wall_id
            n_wall += 1
            if cur in accent_ids:
                accent_cleared += 1
    if n_wall:
        actions.append("unify_peri_wall:%d" % n_wall)

    # 6) Cap accent fraction globally
    solids_n = int((out > 0).sum())
    if solids_n > 0 and accent_id > 0 and accent_id != wall_id:
        acc_n = int((out == accent_id).sum())
        if load_bearing_id and load_bearing_id != wall_id and load_bearing_id != accent_id:
            acc_n += int((out == load_bearing_id).sum())
        frac = acc_n / float(solids_n)
        if frac > float(max_accent_frac):
            # Convert non-corner accents to wall until under cap
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
                actions.append("accent_cap:%d (frac %.3f->target %.3f)" % (cleared, frac, max_accent_frac))

    if accent_cleared and "accent_cap" not in "".join(actions):
        actions.append("accent_cleared_peri:%d" % accent_cleared)

    # 7) Drop floating CCs again
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

    # 8) Despeckle
    prot = set(door_ids) | set(glass_ids)
    out, n_sp = despeckle_solids(out, min_neighbors=2, protected_ids=prot)
    if n_sp:
        actions.append("despeckle:%d" % n_sp)

    return out, actions


'''


def patch_look_harden(text: str) -> str:
    # Remove hopper from industrial structural; dirt from rustic
    text = text.replace(
        '''        "smooth_stone",
        "glass",
        "waxed_copper",
        "copper_block",
        "chain",
        "hopper",
    ),
    "medieval": (''',
        '''        "smooth_stone",
        "glass",
        "waxed_copper",
        "copper_block",
        "chain",
        "tuff_bricks",
    ),
    "medieval": (''',
        1,
    )
    text = text.replace(
        '''        "hay_block",
        "dirt",
        "coarse_dirt",
        "stripped_oak",
        "stripped_spruce",
    ),
    "european": (''',
        '''        "hay_block",
        "stripped_oak",
        "stripped_spruce",
        "cobblestone",
    ),
    "european": (''',
        1,
    )

    # Add bone/hopper/ore to junk substr if not present
    if '"bone_block"' not in text and '"hopper"' not in text[text.find("_JUNK_SUBSTR"):text.find("_JUNK_SUBSTR")+800]:
        junk_anchor = '    "structure_void",\n)'
        if junk_anchor not in text:
            raise SystemExit("junk anchor not found")
        text = text.replace(
            junk_anchor,
            '    "structure_void",\n'
            '    "bone_block",\n'
            '    "hopper",\n'
            '    "dropper",\n'
            '    "dispenser",\n'
            '    "observer",\n'
            '    "piston",\n'
            '    "sticky_piston",\n'
            ')',
            1,
        )

    # Widen pier spacing (reduce oak_log forest)
    text = text.replace('"wall_pier_spacing": 3,\n    },\n    "chinese":', '"wall_pier_spacing": 8,\n    },\n    "chinese":', 1)
    # chinese still 3 - bump
    text = text.replace(
        '''    "chinese": {
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
        "wall_pier_spacing": 3,
    },''',
        '''    "chinese": {
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
    },''',
        1,
    )
    text = text.replace(
        '''    "medieval": {
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
        "wall_pier_spacing": 3,
    },''',
        '''    "medieval": {
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
    },''',
        1,
    )
    text = text.replace('"wall_pier_spacing": 4,\n    },\n}\n\n\ndef style_facade_rules', '"wall_pier_spacing": 8,\n    },\n}\n\n\ndef style_facade_rules', 1)
    text = text.replace('"wall_pier_spacing": 5,\n        "corner_pillars": True,\n    },\n    "fantasy":', '"wall_pier_spacing": 8,\n        "corner_pillars": True,\n    },\n    "fantasy":', 1)
    text = text.replace(
        '''        "place_wall_piers": True,
        "wall_pier_spacing": 5,
    },
    "western":''',
        '''        "place_wall_piers": True,
        "wall_pier_spacing": 8,
    },
    "western":''',
        1,
    )

    # Insert clean helpers before look_harden def
    marker = "\ndef look_harden(\n"
    if marker not in text:
        raise SystemExit("look_harden def not found")
    if "def unify_role_surfaces(" not in text:
        text = text.replace(marker, "\n" + CLEAN_FN + marker, 1)

    # Wire into look_harden near end — find where final metrics computed
    # After geometry harden + facade, before building report.
    # Search for uniqu_a assignment pattern
    wire_anchor = '''    uniq_a = int(len(np.unique(out[out > 0]))) if (out > 0).any() else 0
    after = check_structure(out)'''
    if wire_anchor not in text:
        # try alternate
        alt = None
        for line in text.splitlines():
            if "uniq_a" in line and "np.unique" in line:
                alt = line
                break
        raise SystemExit("wire anchor not found; sample=" + repr(alt))

    wire_insert = '''    # --- clean material noise (one wall/roof/floor; despeckle; cap accent) ---
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

    uniq_a = int(len(np.unique(out[out > 0]))) if (out > 0).any() else 0
    after = check_structure(out)'''
    text = text.replace(wire_anchor, wire_insert, 1)

    # Also lower default top_k when called with role — change look_harden top_k default usage
    # already force_keep expands; reduce keep_trim_top default in call site inside look_harden:
    old_lim = '''    out, pal_stats = limit_palette(
        vox0,
        palette,
        style=style,
        top_k=max(int(top_k), 6 if force_keep else int(top_k)),
        keep_trim_top=keep_trim_top,
        force_keep=force_keep,
    )'''
    new_lim = '''    # With role materials, keep palette tight (wall/roof/floor/accent + glass/door).
    _tk = 4 if force_keep else int(top_k)
    _kt = 1 if force_keep else int(keep_trim_top)
    out, pal_stats = limit_palette(
        vox0,
        palette,
        style=style,
        top_k=max(_tk, len(force_keep or [])),
        keep_trim_top=_kt,
        force_keep=force_keep,
    )'''
    if old_lim not in text:
        raise SystemExit("limit_palette call not found")
    text = text.replace(old_lim, new_lim, 1)

    return text


def main() -> None:
    sm = SM.read_text(encoding="utf-8")
    sm2 = patch_scaffold_materials(sm)
    SM.write_text(sm2, encoding="utf-8")
    print("patched", SM, "delta", len(sm2) - len(sm))

    lh = LH.read_text(encoding="utf-8")
    lh2 = patch_look_harden(lh)
    LH.write_text(lh2, encoding="utf-8")
    print("patched", LH, "delta", len(lh2) - len(lh))


if __name__ == "__main__":
    main()
