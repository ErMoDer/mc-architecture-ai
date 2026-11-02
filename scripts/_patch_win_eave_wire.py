# -*- coding: utf-8 -*-
"""Wire harden_facade to sill/header, cornice, eave overhang, style facade knobs."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src" / "app" / "look_harden.py"
text = PATH.read_text(encoding="utf-8")

# --- insert style facade knobs after knowledge_defaults / near top helpers ---
MARKER = "def _clamp_floor_spacing(spacing: int | None, rules: dict[str, Any] | None = None) -> int:"
STYLE_BLOCK = '''
# Per-style facade polish (window rhythm + eaves/cornice). Keys merge over knowledge defaults.
_STYLE_FACADE: dict[str, dict[str, Any]] = {
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
        "window_spacing": 2,
        "window_width_max": 2,
        "window_height_max": 2,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 5,
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


def style_facade_rules(style: str | None, base: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge knowledge defaults with per-style window/eave polish knobs."""
    out = dict(base or knowledge_defaults())
    key = (style or "").strip().lower()
    extra = _STYLE_FACADE.get(key)
    if extra:
        out.update(extra)
    return out


'''

if "_STYLE_FACADE" not in text:
    if MARKER not in text:
        raise SystemExit("marker for style block missing")
    text = text.replace(MARKER, STYLE_BLOCK + MARKER, 1)
    print("inserted _STYLE_FACADE")
else:
    print("_STYLE_FACADE already present")

# --- harden_facade signature: add window_frame_id ---
OLD_SIG = '''def harden_facade(
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
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    """Door + roof + eaves + light banding/pillars. Keeps window openings."""
'''

NEW_SIG = '''def harden_facade(
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
    """Door + roof + eaves/cornice + window rhythm (sill/header). Keeps openings."""
'''

if OLD_SIG not in text:
    raise SystemExit("OLD_SIG not found")
text = text.replace(OLD_SIG, NEW_SIG, 1)

# --- rules load: use style_facade_rules ---
OLD_RULES = '''    rules = knowledge_defaults() if use_knowledge else {}
    if use_knowledge and rules:
        actions.append(
            "knowledge:story>=%s floor_sp_hint=%s wall=%s win_sp=%s eave=%s roof_rise_max=%s"
            % (
                rules.get("min_story_clear"),
                rules.get("floor_spacing"),
                rules.get("shell_thickness"),
                rules.get("window_spacing"),
                rules.get("eave_overhang"),
                rules.get("roof_rise_max"),
            )
        )
'''

NEW_RULES = '''    rules = style_facade_rules(style) if use_knowledge else {}
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
'''

if OLD_RULES not in text:
    raise SystemExit("OLD_RULES not found")
text = text.replace(OLD_RULES, NEW_RULES, 1)

# --- window rhythm call ---
OLD_WR = '''    # rhythmic windows on mid-story bands
    gid = _resolve_glass_id(palette, style=style) if use_knowledge else 0
    if use_knowledge and gid > 0 and bool(rules.get("place_window_glass", True)):
        wh = max(
            int(rules.get("window_height_min", 1)),
            min(2, int(rules.get("window_height_max", 2))),
        )
        ww = max(
            int(rules.get("window_width_min", 1)),
            min(2, int(rules.get("window_width_max", 2))),
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
        )
        actions.extend(act)
        stats["window_rhythm_cells"] = int(wr.get("placed_cells", 0))
'''

NEW_WR = '''    # rhythmic windows on mid-story bands (regular spacing + optional sill/header)
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
        )
        actions.extend(act)
        stats["window_rhythm_cells"] = int(wr.get("placed_cells", 0))
        stats["window_sill_header"] = int(wr.get("sill_header", 0))
'''

if OLD_WR not in text:
    raise SystemExit("OLD_WR not found")
text = text.replace(OLD_WR, NEW_WR, 1)

# --- eave + cornice section ---
OLD_EAVE_CALL = '''    eave_n = 0
    if eave_strip:
        ey = roof_eave_y if roof_mode == "pitched" else y1
        out, act, eave_n = place_eave_strip(
            out,
            active=active,
            peri=peri,
            roof_y=ey,
            wall_id=wall_id,
            stairs_id=stairs_id if roof_mode == "pitched" else 0,
            roof_id=roof_block,
        )
        actions.extend(act)

    band_n = 0
'''

NEW_EAVE_CALL = '''    eave_n = 0
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
'''

if OLD_EAVE_CALL not in text:
    raise SystemExit("OLD_EAVE_CALL not found")
text = text.replace(OLD_EAVE_CALL, NEW_EAVE_CALL, 1)

# --- facade_metrics update to include cornice ---
OLD_METRICS_UPDATE = '''    stats.update(
        facade_metrics(
            out,
            door_cells=door_cells,
            eave_cells=eave_n,
            banding_cells=band_n,
            pillar_cells=pillar_n,
            roof_mode=roof_mode,
        )
    )
'''

NEW_METRICS_UPDATE = '''    stats.update(
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

if OLD_METRICS_UPDATE not in text:
    raise SystemExit("OLD_METRICS_UPDATE not found")
text = text.replace(OLD_METRICS_UPDATE, NEW_METRICS_UPDATE, 1)

# --- harden_geometry call site: pass window_frame ---
OLD_CALL = '''        out, fac_act, fac_stats = harden_facade(
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

        )
        actions.extend(fac_act)
        # stash for callers via action tokens
        actions.append(
            "facade_stats:door=%d eave=%d band=%d pillar=%d roof=%s"
            % (
                int(fac_stats.get("door_cells", 0)),
                int(fac_stats.get("eave_cells", 0)),
                int(fac_stats.get("banding_cells", 0)),
                int(fac_stats.get("pillar_cells", 0)),
                str(fac_stats.get("roof_mode") or ""),
            )
        )
'''

NEW_CALL = '''        out, fac_act, fac_stats = harden_facade(
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

if OLD_CALL not in text:
    raise SystemExit("OLD_CALL not found")
text = text.replace(OLD_CALL, NEW_CALL, 1)

# --- look_harden geo_extra parse for cornice if present ---
# optional: update facade_stats parse in look_harden()
OLD_PARSE = '''            if a.startswith("facade_stats:"):
                # facade_stats:door=%d eave=%d band=%d pillar=%d roof=%s
'''
# leave parse tolerant — existing split may ignore unknown keys

PATH.write_text(text, encoding="utf-8")
print("wired harden_facade ok", PATH.stat().st_size)
