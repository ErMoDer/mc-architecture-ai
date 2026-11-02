# -*- coding: utf-8 -*-
"""Wire harden_facade to door frame/threshold + wall piers."""
from __future__ import annotations
from pathlib import Path

PATH = Path("src/app/look_harden.py")
text = PATH.read_text(encoding="utf-8")

OLD_DOOR_CALL = '''    door_cells = 0
    place_door = bool(place_door and (rules.get("place_door", True) if rules else True))
    if place_door:
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
        )
        actions.extend(act)
        door_cells = int(dinfo.get("door_cells", 0))
        stats["door_face"] = dinfo.get("face", "")
        stats["door_block"] = bool(dinfo.get("placed_door"))
'''

NEW_DOOR_CALL = '''    door_cells = 0
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
'''

if OLD_DOOR_CALL not in text:
    raise SystemExit("OLD_DOOR_CALL missing")
text = text.replace(OLD_DOOR_CALL, NEW_DOOR_CALL, 1)

# After corner pillars, add wall piers (or before banding - after pillars is fine)
OLD_PILLAR = '''    pillar_n = 0
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

    stats.update(
        facade_metrics(
            out,
            door_cells=door_cells,
            eave_cells=eave_n,
            banding_cells=band_n,
            pillar_cells=pillar_n,
            roof_mode=roof_mode,
        )
    )
    stats["cornice_cells"] = int(cornice_n)
'''

NEW_PILLAR = '''    pillar_n = 0
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
'''

if OLD_PILLAR not in text:
    raise SystemExit("OLD_PILLAR missing")
text = text.replace(OLD_PILLAR, NEW_PILLAR, 1)

# Update facade_stats token to include pier
OLD_STATS = '''        actions.append(
            "facade_stats:door=%d eave=%d band=%d pillar=%d cornice=%d roof=%s"
            % (
                int(fac_stats.get("door_cells", 0)),
                int(fac_stats.get("eave_cells", 0)),
                int(fac_stats.get("banding_cells", 0)),
                int(fac_stats.get("pillar_cells", 0)),
                int(fac_stats.get("cornice_cells", 0)),
                str(fac_stats.get("roof_mode") or ""),
            )
        )
'''
NEW_STATS = '''        actions.append(
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
'''
if OLD_STATS not in text:
    raise SystemExit("OLD_STATS missing")
text = text.replace(OLD_STATS, NEW_STATS, 1)

# docstring tweak
text = text.replace(
    '"""Door + roof + eaves/cornice + window rhythm (sill/header). Keeps openings."""',
    '"""Door(+frame) + roof + eaves/cornice + window rhythm + wall piers. Keeps openings."""',
    1,
)

PATH.write_text(text, encoding="utf-8")
import ast
ast.parse(PATH.read_text(encoding="utf-8"))
print("wire ok", PATH.stat().st_size)
