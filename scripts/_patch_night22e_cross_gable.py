# -*- coding: utf-8 -*-
"""Patch gen_strategy.py: lightweight intersecting / cross-gable rise map (night22e)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
SRC = ROOT / "src" / "app" / "gen_strategy.py"
text = SRC.read_text(encoding="utf-8")

OLD_GABLE = '''def _gable_rise_map(
    fp: np.ndarray,
    *,
    rise: int,
    plateau_frac: float = 0.35,
    ridge_along_x: bool | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Per-column height *offset above eave* for a gable (0..rise)."""
    fp = np.asarray(fp, dtype=bool)
    hmap = np.zeros(fp.shape, dtype=np.int16)
    info: dict[str, Any] = {"rise": 0, "ridge_along_x": True, "half": 0}
    xs, zs = np.where(fp)
    if xs.size == 0:
        return hmap, info
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    if ridge_along_x is None:
        ridge_along_x = wx >= wz
    half = max(1, (wz // 2) if ridge_along_x else (wx // 2))
    rise = int(max(1, min(int(rise), half)))
    plateau = max(1, int(float(plateau_frac) * half))
    ridge_z = (minz + maxz) / 2.0
    ridge_x = (minx + maxx) / 2.0
    for x, z in zip(xs.tolist(), zs.tolist()):
        dist = abs(float(z) - ridge_z) if ridge_along_x else abs(float(x) - ridge_x)
        if dist <= plateau:
            h = rise
        else:
            span = max(1e-6, float(half - plateau))
            tnorm = min(1.0, (dist - plateau) / span)
            h = int(round(rise * (1.0 - tnorm)))
        hmap[x, z] = int(max(0, min(rise, h)))
    info.update({"rise": rise, "ridge_along_x": bool(ridge_along_x), "half": half, "plateau": plateau})
    return hmap, info
'''

NEW_GABLE = '''def _gable_rise_map(
    fp: np.ndarray,
    *,
    rise: int,
    plateau_frac: float = 0.35,
    ridge_along_x: bool | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Per-column height *offset above eave* for a gable (0..rise)."""
    fp = np.asarray(fp, dtype=bool)
    hmap = np.zeros(fp.shape, dtype=np.int16)
    info: dict[str, Any] = {"rise": 0, "ridge_along_x": True, "half": 0}
    xs, zs = np.where(fp)
    if xs.size == 0:
        return hmap, info
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    if ridge_along_x is None:
        ridge_along_x = wx >= wz
    half = max(1, (wz // 2) if ridge_along_x else (wx // 2))
    rise = int(max(1, min(int(rise), half)))
    plateau = max(1, int(float(plateau_frac) * half))
    ridge_z = (minz + maxz) / 2.0
    ridge_x = (minx + maxx) / 2.0
    for x, z in zip(xs.tolist(), zs.tolist()):
        dist = abs(float(z) - ridge_z) if ridge_along_x else abs(float(x) - ridge_x)
        if dist <= plateau:
            h = rise
        else:
            span = max(1e-6, float(half - plateau))
            tnorm = min(1.0, (dist - plateau) / span)
            h = int(round(rise * (1.0 - tnorm)))
        hmap[x, z] = int(max(0, min(rise, h)))
    info.update({"rise": rise, "ridge_along_x": bool(ridge_along_x), "half": half, "plateau": plateau})
    return hmap, info


def _cross_gable_rise_map(
    fp: np.ndarray,
    *,
    rise: int,
    plateau_frac: float = 0.35,
    cross_band_frac: float = 0.42,
    cross_rise_scale: float = 0.92,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Primary gable + perpendicular cross ridge on a central band (max of both).

    Lightweight intersecting-gable silhouette without hip fill. The secondary
    ridge only raises columns inside a mid-band along the primary axis so eaves
    stay low and interior_cover is not flooded.
    """
    fp = np.asarray(fp, dtype=bool)
    primary, pinfo = _gable_rise_map(fp, rise=rise, plateau_frac=plateau_frac, ridge_along_x=None)
    info: dict[str, Any] = {
        "rise": int(pinfo.get("rise") or 0),
        "ridge_along_x": bool(pinfo.get("ridge_along_x", True)),
        "half": int(pinfo.get("half") or 0),
        "plateau": int(pinfo.get("plateau") or 0),
        "cross_gable": False,
        "cross_cells": 0,
    }
    xs, zs = np.where(fp)
    if xs.size == 0 or int(pinfo.get("rise") or 0) < 2:
        return primary, info
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    # Need enough span on both axes for a readable cross
    if min(wx, wz) < 8 or max(wx, wz) < 10:
        return primary, info

    ridge_along_x = bool(pinfo.get("ridge_along_x", True))
    # Secondary ridge is perpendicular to primary
    secondary, sinfo = _gable_rise_map(
        fp,
        rise=max(2, int(round(int(pinfo["rise"]) * float(cross_rise_scale)))),
        plateau_frac=min(0.55, float(plateau_frac) + 0.06),
        ridge_along_x=(not ridge_along_x),
    )
    # Restrict secondary to a central band along the *primary* ridge axis
    band = max(2, int(round(float(cross_band_frac) * (wx if ridge_along_x else wz))))
    if ridge_along_x:
        mid = (minx + maxx) / 2.0
        band_mask = np.zeros(fp.shape, dtype=bool)
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(float(x) - mid) <= band / 2.0 + 0.51:
                band_mask[x, z] = True
    else:
        mid = (minz + maxz) / 2.0
        band_mask = np.zeros(fp.shape, dtype=bool)
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(float(z) - mid) <= band / 2.0 + 0.51:
                band_mask[x, z] = True

    hmap = primary.copy()
    cross_n = 0
    raised = 0
    for x, z in zip(xs.tolist(), zs.tolist()):
        if not band_mask[x, z]:
            continue
        sec = int(secondary[x, z])
        if sec > int(hmap[x, z]):
            hmap[x, z] = sec
            raised += 1
        cross_n += 1
    # Require a meaningful lift; else keep pure primary
    if raised < max(6, int(0.04 * int(fp.sum()))):
        return primary, info
    info.update(
        {
            "cross_gable": True,
            "cross_cells": int(cross_n),
            "cross_raised": int(raised),
            "cross_band": int(band),
            "cross_ridge_along_x": bool(sinfo.get("ridge_along_x")),
            "cross_rise": int(sinfo.get("rise") or 0),
            "rise": max(int(pinfo.get("rise") or 0), int(sinfo.get("rise") or 0)),
        }
    )
    return hmap, info
'''

if OLD_GABLE not in text:
    raise SystemExit("OLD_GABLE block not found")
text = text.replace(OLD_GABLE, NEW_GABLE, 1)

# Patch _place_skin_gable_roof signature + rise_map call + info
OLD_PLACE_SIG = '''def _place_skin_gable_roof(
    out: np.ndarray,
    *,
    roof_fp: np.ndarray,
    peri: np.ndarray,
    eave_y: int,
    roof_id: int,
    rise: int,
    plateau_frac: float = 0.35,
    overhang: int = 1,
    wall_id: int | None = None,
    clear_attic: bool = True,
    stairs_id: int = 0,
) -> tuple[int, dict[str, Any]]:
    """Hollow-friendly pitched roof: place roof *skin* only (not solid attic fill).

    - Base eave deck on footprint at eave_y
    - Roof surface at eave_y + rise_map (1-2 thick)
    - Optional overhang ring outside peri at eave_y
    - Clear interior attic under the skin so room stays open
    - Raise gable-end peri walls under the slope
    """
    sx, sy, sz = out.shape
    eave_y = int(eave_y)
    if eave_y < 0 or eave_y >= sy or not np.asarray(roof_fp).any():
        return 0, {"roof_mode": "none"}
    rise_map, ginfo = _gable_rise_map(roof_fp, rise=rise, plateau_frac=plateau_frac)
'''

NEW_PLACE_SIG = '''def _place_skin_gable_roof(
    out: np.ndarray,
    *,
    roof_fp: np.ndarray,
    peri: np.ndarray,
    eave_y: int,
    roof_id: int,
    rise: int,
    plateau_frac: float = 0.35,
    overhang: int = 1,
    wall_id: int | None = None,
    clear_attic: bool = True,
    stairs_id: int = 0,
    cross_gable: bool = False,
    cross_band_frac: float = 0.42,
) -> tuple[int, dict[str, Any]]:
    """Hollow-friendly pitched roof: place roof *skin* only (not solid attic fill).

    - Base eave deck on footprint at eave_y
    - Roof surface at eave_y + rise_map (1-2 thick)
    - Optional overhang ring outside peri at eave_y
    - Clear interior attic under the skin so room stays open
    - Raise gable-end peri walls under the slope
    - Optional lightweight intersecting / cross gable (max of primary + band secondary)
    """
    sx, sy, sz = out.shape
    eave_y = int(eave_y)
    if eave_y < 0 or eave_y >= sy or not np.asarray(roof_fp).any():
        return 0, {"roof_mode": "none"}
    if cross_gable:
        rise_map, ginfo = _cross_gable_rise_map(
            roof_fp,
            rise=rise,
            plateau_frac=plateau_frac,
            cross_band_frac=float(cross_band_frac),
        )
    else:
        rise_map, ginfo = _gable_rise_map(roof_fp, rise=rise, plateau_frac=plateau_frac)
'''

if OLD_PLACE_SIG not in text:
    raise SystemExit("OLD_PLACE_SIG block not found")
text = text.replace(OLD_PLACE_SIG, NEW_PLACE_SIG, 1)

OLD_INFO = '''    info = {
        "roof_mode": "skin_gable",
        "eave_y": eave_y,
        "overhang": oh,
        "overhang_cells": oh_n,
        "roof_stairs": int(stair_n),
        **ginfo,
    }
    return roof_count, info
'''

NEW_INFO = '''    mode = "skin_cross_gable" if ginfo.get("cross_gable") else "skin_gable"
    info = {
        "roof_mode": mode,
        "eave_y": eave_y,
        "overhang": oh,
        "overhang_cells": oh_n,
        "roof_stairs": int(stair_n),
        **ginfo,
    }
    return roof_count, info
'''

if OLD_INFO not in text:
    raise SystemExit("OLD_INFO block not found")
text = text.replace(OLD_INFO, NEW_INFO, 1)

# Wire call site in scaffold builder (the main want_skin_gable block)
OLD_CALL = '''            oh = 2 if style_l in ("european", "rustic", "chinese", "western") else 1
            roof_count, rinfo = _place_skin_gable_roof(
                out,
                roof_fp=use_roof_fp,
                peri=peri,
                eave_y=int(roof_deck_y),
                roof_id=int(roof_id),
                rise=int(max_rise),
                plateau_frac=float(plateau),
                overhang=int(oh),
                wall_id=int(wall_id),
                clear_attic=True,
                stairs_id=int(stairs_id or 0),
            )
            # Phase 2 ridge reinforce: ensure peak_y solids along ridge for roof_score cover
            ridge_n = _reinforce_ridge_peak(
                out,
                roof_fp=use_roof_fp,
                eave_y=int(roof_deck_y),
                rise=int(rinfo.get("rise") or max_rise),
                roof_id=int(roof_id),
                ridge_along_x=bool(rinfo.get("ridge_along_x", True)),
                style=style_l,
            )
            roof_count += int(ridge_n)
            stats["roof"] = int(roof_count)
            stats["roof_mode"] = str(rinfo.get("roof_mode") or "skin_gable")
            stats["eave_overhang"] = int(rinfo.get("overhang") or 0)
            stats["gable_rise"] = int(rinfo.get("rise") or max_rise)
            stats["roof_stairs"] = int(rinfo.get("roof_stairs") or 0)
            stats["ridge_reinforce"] = int(ridge_n)
            stats["sparse_interior_posts"] = False
'''

NEW_CALL = '''            oh = 2 if style_l in ("european", "rustic", "chinese", "western") else 1
            # Night22e: light intersecting gable for euro/chinese (+ rustic).
            # Skip industrial/modern (flat). Avoid med/fantasy (interior_cover risk).
            want_cross = style_l in ("european", "chinese", "rustic")
            cross_band = 0.40 if style_l == "european" else (0.44 if style_l == "chinese" else 0.38)
            roof_count, rinfo = _place_skin_gable_roof(
                out,
                roof_fp=use_roof_fp,
                peri=peri,
                eave_y=int(roof_deck_y),
                roof_id=int(roof_id),
                rise=int(max_rise),
                plateau_frac=float(plateau),
                overhang=int(oh),
                wall_id=int(wall_id),
                clear_attic=True,
                stairs_id=int(stairs_id or 0),
                cross_gable=bool(want_cross),
                cross_band_frac=float(cross_band),
            )
            # Phase 2 ridge reinforce: ensure peak_y solids along ridge for roof_score cover
            ridge_n = _reinforce_ridge_peak(
                out,
                roof_fp=use_roof_fp,
                eave_y=int(roof_deck_y),
                rise=int(rinfo.get("rise") or max_rise),
                roof_id=int(roof_id),
                ridge_along_x=bool(rinfo.get("ridge_along_x", True)),
                style=style_l,
            )
            # Cross ridge reinforce (perpendicular) when intersecting gable fired
            cross_ridge_n = 0
            if rinfo.get("cross_gable"):
                cross_ridge_n = _reinforce_ridge_peak(
                    out,
                    roof_fp=use_roof_fp,
                    eave_y=int(roof_deck_y),
                    rise=int(rinfo.get("cross_rise") or rinfo.get("rise") or max_rise),
                    roof_id=int(roof_id),
                    ridge_along_x=bool(rinfo.get("cross_ridge_along_x", not rinfo.get("ridge_along_x", True))),
                    style=style_l,
                )
                ridge_n += int(cross_ridge_n)
            roof_count += int(ridge_n)
            stats["roof"] = int(roof_count)
            stats["roof_mode"] = str(rinfo.get("roof_mode") or "skin_gable")
            stats["eave_overhang"] = int(rinfo.get("overhang") or 0)
            stats["gable_rise"] = int(rinfo.get("rise") or max_rise)
            stats["roof_stairs"] = int(rinfo.get("roof_stairs") or 0)
            stats["ridge_reinforce"] = int(ridge_n)
            stats["cross_gable"] = bool(rinfo.get("cross_gable"))
            stats["cross_raised"] = int(rinfo.get("cross_raised") or 0)
            stats["cross_ridge_reinforce"] = int(cross_ridge_n)
            stats["sparse_interior_posts"] = False
'''

# Only replace the first occurrence (scaffold path); rule-based may differ slightly
count = text.count(OLD_CALL)
if count < 1:
    raise SystemExit(f"OLD_CALL not found (count={count})")
text = text.replace(OLD_CALL, NEW_CALL, 1)

# Also patch rule-based path if identical block exists again
if OLD_CALL in text:
    text = text.replace(OLD_CALL, NEW_CALL, 1)
    print("also patched second call site")

SRC.write_text(text, encoding="utf-8")
print("PATCHED", SRC)
print("has _cross_gable_rise_map:", "_cross_gable_rise_map" in text)
print("has skin_cross_gable:", "skin_cross_gable" in text)
print("has want_cross:", "want_cross" in text)
