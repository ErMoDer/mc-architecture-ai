# -*- coding: utf-8 -*-
"""Patch look_harden: door frame/threshold + wall pier rhythm."""
from __future__ import annotations

from pathlib import Path

PATH = Path("src/app/look_harden.py")
text = PATH.read_text(encoding="utf-8")

# --- 1) Expand _STYLE_FACADE with door/wall knobs ---
OLD_STYLE = '''_STYLE_FACADE: dict[str, dict[str, Any]] = {
    "european": {
        "window_spacing": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 4,
    },
    "chinese": {
        "window_spacing": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 4,
    },
    "rustic": {
        "window_spacing": 4,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
    },
    "medieval": {
        "window_spacing": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 4,
    },
    "modern": {
        "window_spacing": 4,
        "window_width_max": 2,
        "window_height_max": 2,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 2,
    },
    "fantasy": {
        "window_spacing": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 4,
    },
    "western": {
        "window_spacing": 4,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
    },
}
'''

NEW_STYLE = '''_STYLE_FACADE: dict[str, dict[str, Any]] = {
    "european": {
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
        "wall_pier_spacing": 3,
    },
    "rustic": {
        "window_spacing": 4,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 4,
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
        "wall_pier_spacing": 3,
    },
    "modern": {
        "window_spacing": 4,
        "window_width_max": 2,
        "window_height_max": 2,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 2,
        "door_width": 2,
        "door_height": 2,
        "place_door_frame": False,
        "place_wall_piers": False,
        "corner_pillars": False,
    },
    "fantasy": {
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
        "wall_pier_spacing": 4,
    },
}
'''

if OLD_STYLE not in text:
    raise SystemExit("OLD_STYLE missing")
text = text.replace(OLD_STYLE, NEW_STYLE, 1)

# --- 2) hole-fill: skip door blocks ---
OLD_HOLE = '''                    if preserve_windows and win_mask[x, y, z]:
                        continue
                    nsolid = 0
'''
NEW_HOLE = '''                    if preserve_windows and win_mask[x, y, z]:
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
'''
if OLD_HOLE not in text:
    raise SystemExit("OLD_HOLE missing")
text = text.replace(OLD_HOLE, NEW_HOLE, 1)

# --- 3) Replace carve_front_door ---
# Find function body until harden_roof_silhouette
start = text.find("def carve_front_door(")
end = text.find("\ndef harden_roof_silhouette(", start)
if start < 0 or end < 0:
    raise SystemExit("carve_front_door bounds missing")

NEW_DOOR = '''def carve_front_door(
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


'''

text = text[:start] + NEW_DOOR + text[end:]

# --- 4) Insert place_wall_piers before harden_facade ---
PIERS = '''
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


'''

anchor = "\ndef harden_facade("
if "def place_wall_piers(" not in text:
    if anchor not in text:
        raise SystemExit("harden_facade anchor missing")
    text = text.replace(anchor, PIERS + anchor, 1)
    print("inserted place_wall_piers")
else:
    print("place_wall_piers exists")

PATH.write_text(text, encoding="utf-8")
import ast
ast.parse(text)
print("part1 ok", PATH.stat().st_size)
