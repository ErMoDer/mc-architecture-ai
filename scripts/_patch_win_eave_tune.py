# -*- coding: utf-8 -*-
"""Tune modern density + sill/cornice overwrite floor peri cells."""
from __future__ import annotations
from pathlib import Path

PATH = Path("src/app/look_harden.py")
text = PATH.read_text(encoding="utf-8")

# modern: less glass curtain
old_mod = '''    "modern": {
        "window_spacing": 2,
        "window_width_max": 2,
        "window_height_max": 2,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 5,
    },'''
new_mod = '''    "modern": {
        "window_spacing": 3,
        "window_width_max": 2,
        "window_height_max": 2,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 3,
    },'''
if old_mod not in text:
    raise SystemExit("modern block missing")
text = text.replace(old_mod, new_mod, 1)

# sill: also allow replacing floor_id-like peri cells (pass floor_id into rhythm)
# Simpler: in sill/header placement, also overwrite any non-glass non-door structural on peri
old_sill = '''                    if place_sill_header and fid > 0:
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
                                    sill_n += 1'''

new_sill = '''                    if place_sill_header and fid > 0:
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
                                    sill_n += 1'''

if old_sill not in text:
    raise SystemExit("old_sill missing")
text = text.replace(old_sill, new_sill, 1)

# cornice: overwrite peri structural that is not already trim / glass / door
old_corn = '''    changed = 0
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
'''

new_corn = '''    changed = 0
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
'''

if old_corn not in text:
    raise SystemExit("old_corn missing")
text = text.replace(old_corn, new_corn, 1)

PATH.write_text(text, encoding="utf-8")
print("tuned ok")
