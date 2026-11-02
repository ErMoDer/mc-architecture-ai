# -*- coding: utf-8 -*-
"""Patch look_harden: window rhythm sill/header + cornice + eave overhang."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src" / "app" / "look_harden.py"

OLD_RHYTHM = '''def place_window_rhythm(
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
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    """Regular mid-story window columns on each facade (knowledge window rhythm)."""
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    info: dict[str, Any] = {"placed_cells": 0, "columns": 0, "bands": []}
    if not peri.any() or int(glass_id) <= 0:
        return out, actions, info
    sy = out.shape[1]
    sp = max(2, int(spacing))
    fc = max(1, int(from_corner))
    ff = max(1, int(from_floor))
    wh = max(1, min(2, int(win_h)))
    ww = max(1, min(2, int(win_w)))
    faces = _bbox_faces(peri)
    placed = 0
    cols = 0
    ys = sorted({int(y) for y in floor_ys if y0 <= int(y) < y1})
    if y0 not in ys:
        ys = [int(y0)] + ys
    bands: list[tuple[int, int]] = []
    for i, fy in enumerate(ys):
        nxt = ys[i + 1] if i + 1 < len(ys) else int(y1)
        y_bot = int(fy) + ff
        y_top = y_bot + wh - 1
        if y_top >= int(nxt) or y_bot <= int(fy) or y_top >= int(y1):
            continue
        bands.append((y_bot, y_top))
    info["bands"] = bands
    if not bands:
        return out, actions, info

    for face, cells in faces.items():
        if len(cells) < fc * 2 + ww:
            continue
        if face in ("x0", "x1"):
            cells_s = sorted(cells, key=lambda t: t[1])
        else:
            cells_s = sorted(cells, key=lambda t: t[0])
        usable = cells_s[fc : max(fc, len(cells_s) - fc)]
        if not usable:
            continue
        idx = 0
        while idx < len(usable):
            group = usable[idx : idx + ww]
            if len(group) < ww:
                break
            for y_bot, y_top in bands:
                for x, z in group:
                    for y in range(y_bot, y_top + 1):
                        cur = int(out[x, y, z])
                        if _cell_is_glass(cur):
                            continue
                        if _PALETTE_REF is not None:
                            sn = _short(_PALETTE_REF.get(cur, ""))
                            if sn.endswith("_door") or sn == "door":
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
                            out[x, y, z] = int(glass_id)
                            placed += 1
                cols += 1
            idx += sp

    if placed:
        actions.append("window_rhythm:cells=%d cols~=%d sp=%d" % (placed, cols, sp))
    info["placed_cells"] = placed
    info["columns"] = cols
    return out, actions, info
'''

NEW_RHYTHM = '''def place_window_rhythm(
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
    faces = _bbox_faces(peri)
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
        if len(cells) < fc * 2 + ww:
            continue
        if face in ("x0", "x1"):
            cells_s = sorted(cells, key=lambda t: t[1])
        else:
            cells_s = sorted(cells, key=lambda t: t[0])
        usable = cells_s[fc : max(fc, len(cells_s) - fc)]
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
                        if ysill > int(y0) and ysill < sy:
                            for x, z in group:
                                cur = int(out[x, ysill, z])
                                if _cell_is_glass(cur) or _is_door(cur):
                                    continue
                                if cur == 0 or cur == int(wall_id) or _cell_is_nonstructural_mass(cur):
                                    out[x, ysill, z] = fid
                                    sill_n += 1
                        yhead = y_top + 1
                        if yhead < int(y1) and yhead < sy:
                            for x, z in group:
                                cur = int(out[x, yhead, z])
                                if _cell_is_glass(cur) or _is_door(cur):
                                    continue
                                if cur == 0 or cur == int(wall_id) or _cell_is_nonstructural_mass(cur):
                                    out[x, yhead, z] = fid
                                    sill_n += 1
            if col_hit:
                cols += 1
            idx += sp

    if placed:
        actions.append(
            "window_rhythm:cells=%d cols=%d sp=%d bands=%d sill=%d"
            % (placed, cols, sp, len(bands), sill_n)
        )
    info["placed_cells"] = placed
    info["columns"] = cols
    info["sill_header"] = sill_n
    return out, actions, info
'''

OLD_EAVE = '''def place_eave_strip(
    voxels: np.ndarray,
    *,
    active: np.ndarray,
    peri: np.ndarray,
    roof_y: int,
    wall_id: int,
    stairs_id: int = 0,
    roof_id: int | None = None,
) -> tuple[np.ndarray, list[str], int]:
    """One-block outward eave ring at roof_y (flat) or eave level."""
    out = np.asarray(voxels, dtype=np.int16)
    actions: list[str] = []
    sx, sy, sz = out.shape
    if roof_y < 0 or roof_y >= sy:
        return out, actions, 0
    added = 0
    roof_block = int(roof_id) if roof_id is not None and int(roof_id) > 0 else int(wall_id)
    block = int(stairs_id) if int(stairs_id) > 0 else int(roof_block)
    px, pz = np.where(peri)
    for x, z in zip(px.tolist(), pz.tolist()):
        if not active[x, z]:
            continue
        # ensure eave support on peri
        if out[x, roof_y, z] == 0:
            out[x, roof_y, z] = int(roof_block)
            added += 1
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, nz = x + dx, z + dz
            if not (0 <= nx < sx and 0 <= nz < sz):
                continue
            if active[nx, nz] or peri[nx, nz]:
                continue
            # only hang off exterior
            if out[nx, roof_y, nz] != 0:
                continue
            # prefer empty column outside footprint
            out[nx, roof_y, nz] = block
            added += 1
    if added:
        actions.append("eave_strip:%d@y=%d" % (added, roof_y))
    return out, actions, added
'''

NEW_EAVE = '''def place_eave_strip(
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
        if cur > 0 and _cell_is_glass(cur):
            continue
        if _PALETTE_REF is not None:
            sn = _short(_PALETTE_REF.get(cur, ""))
            if sn.endswith("_door") or sn == "door":
                continue
        if cur == 0 or cur == int(wall_id) or _cell_is_nonstructural_mass(cur):
            out[x, cy, z] = tid
            changed += 1
        elif cur != tid and cur == int(wall_id):
            out[x, cy, z] = tid
            changed += 1
    if changed:
        actions.append("cornice_ring:%d@y=%d" % (changed, cy))
    return out, actions, changed
'''

text = PATH.read_text(encoding="utf-8")
if OLD_RHYTHM not in text:
    raise SystemExit("OLD_RHYTHM not found")
if OLD_EAVE not in text:
    raise SystemExit("OLD_EAVE not found")
text = text.replace(OLD_RHYTHM, NEW_RHYTHM, 1)
text = text.replace(OLD_EAVE, NEW_EAVE, 1)
PATH.write_text(text, encoding="utf-8")
print("replaced rhythm + eave/cornice ok", PATH.stat().st_size)
