# -*- coding: utf-8 -*-
"""Phase F: strict window openings for fantasy/western — seal irregular holes."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
LH = ROOT / "src" / "app" / "look_harden.py"


def main() -> None:
    src = LH.read_text(encoding="utf-8")

    # --- 1) facade knobs ---
    old_fan = '''    "fantasy": {
        # Phase E2: window_cells~784 vs euro~461 on seed908 tall ref. Stronger dens.
        # spacing 6 / from_corner 3 / bands 1 — target closer to euro window_cells band.
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
    },'''
    new_fan = '''    "fantasy": {
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
    },'''
    if old_fan not in src:
        raise SystemExit("fantasy block not found")
    src = src.replace(old_fan, new_fan, 1)

    old_west = '''    "western": {
        "window_spacing": 4,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 1,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 8,
    },'''
    new_west = '''    "western": {
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
    },'''
    if old_west not in src:
        raise SystemExit("western block not found")
    src = src.replace(old_west, new_west, 1)

    # --- 2) detect_window_mask signature + strict logic ---
    old_sig = '''def detect_window_mask(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    y0: int,
    y1: int,
    floor_ys: list[int],
    preserve: bool = True,
) -> tuple[np.ndarray, dict[str, Any]]:'''
    new_sig = '''def detect_window_mask(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    y0: int,
    y1: int,
    floor_ys: list[int],
    preserve: bool = True,
    style: str | None = None,
    strict: bool | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:'''
    if old_sig not in src:
        raise SystemExit("detect_window_mask sig not found")
    src = src.replace(old_sig, new_sig, 1)

    # After info init / if not preserve, add strict resolution
    old_preserve = '''    if not preserve:
        return win, info

    floor_set = {int(y) for y in floor_ys if 0 <= int(y) < sy}'''
    new_preserve = '''    if not preserve:
        return win, info

    style_l = (style or "").strip().lower()
    if strict is None:
        # Facade knobs or known inflated-opening styles
        fr = style_facade_rules(style_l) if style_l else {}
        strict = bool(fr.get("strict_window_openings")) or style_l in (
            "fantasy",
            "western",
        )
    info["strict"] = bool(strict)

    floor_set = {int(y) for y in floor_ys if 0 <= int(y) < sy}'''
    if old_preserve not in src:
        raise SystemExit("preserve early-return block not found")
    src = src.replace(old_preserve, new_preserve, 1)

    # Replace classification loop
    old_class = '''    defect_cells = 0
    window_comps = 0
    for c in comps:
        h, w, size = c["h"], c["w"], c["size"]
        is_win = False
        reason = ""
        # size-1 irregular at floor junction → defect
        if size <= 2 and not c["rectangular"] and not c["mid"]:
            is_win = False
            reason = "tiny_irregular"
        elif 1 <= h <= 2 and 1 <= w <= 3 and c["rectangular"] and c["mid"]:
            is_win = True
            reason = "rect_mid"
        elif 1 <= h <= 2 and 1 <= w <= 3 and c["rectangular"] and int(round(c["y_mid"])) in repeating_ys:
            is_win = True
            reason = "rect_repeat"
        elif size <= 6 and 1 <= h <= 2 and 1 <= w <= 3 and c["mid"]:
            # near-rect mid openings
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
            defect_cells += size'''

    new_class = '''    defect_cells = 0
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
            # Phase F: only clear rectangular mid-wall or repeating bands.
            # Drop near_rect_mid (was keeping ragged 1–6 cell holes as windows).
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
            defect_cells += size'''

    if old_class not in src:
        raise SystemExit("classification block not found")
    src = src.replace(old_class, new_class, 1)

    # --- 3) pass style into detect_window_mask calls ---
    old_call1 = '''    win_mask, win_info = detect_window_mask(
        out,
        peri=peri,
        y0=y0,
        y1=y1,
        floor_ys=peaks,
        preserve=bool(preserve_windows),
    )'''
    new_call1 = '''    win_mask, win_info = detect_window_mask(
        out,
        peri=peri,
        y0=y0,
        y1=y1,
        floor_ys=peaks,
        preserve=bool(preserve_windows),
        style=style,
    )'''
    if old_call1 not in src:
        raise SystemExit("call1 not found")
    src = src.replace(old_call1, new_call1, 1)

    old_call2 = '''            wmask2, _ = detect_window_mask(
                out, peri=peri, y0=y0, y1=y1, floor_ys=peaks, preserve=True
            )'''
    new_call2 = '''            wmask2, _ = detect_window_mask(
                out, peri=peri, y0=y0, y1=y1, floor_ys=peaks, preserve=True, style=style
            )'''
    if old_call2 not in src:
        raise SystemExit("call2 not found")
    src = src.replace(old_call2, new_call2, 1)

    # window_opening_count: add optional style passthrough
    old_woc = '''def window_opening_count(
    voxels: np.ndarray,
    y0: int | None = None,
    y1: int | None = None,
    floor_ys: list[int] | None = None,
) -> dict[str, Any]:
    """Count perimeter openings classified as window-like (for A/B metrics)."""
    out = np.asarray(voxels)
    solid = out > 0
    if not solid.any():
        return {"window_cells": 0, "window_components": 0, "defect_cells": 0}
    fp, _ = _footprint(solid)
    peri = _perimeter_mask(fp)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    if ys.size == 0:
        return {"window_cells": 0, "window_components": 0, "defect_cells": 0}
    lo = int(ys.min()) if y0 is None else int(y0)
    hi = int(ys.max()) if y1 is None else int(y1)
    peaks = list(floor_ys) if floor_ys is not None else list(_floor_metrics(solid).get("y_peaks") or [])
    mask, info = detect_window_mask(
        out, peri=peri, y0=lo, y1=hi, floor_ys=peaks, preserve=True
    )
    return {
        "window_cells": int(info.get("window_cells", 0)),
        "window_components": int(info.get("window_components", 0)),
        "defect_cells": int(info.get("defect_cells", 0)),
        "glass_cells": int(info.get("glass_cells", 0)),
    }'''
    new_woc = '''def window_opening_count(
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
    }'''
    if old_woc not in src:
        raise SystemExit("window_opening_count not found")
    src = src.replace(old_woc, new_woc, 1)

    # --- 4) stricter hole fill for strict styles: 3 passes ---
    old_holes = '''    # --- fill remaining wall holes (continuity) — skip windows ---
    hole_filled = 0
    if fill_wall_holes:
        for _pass in range(2):'''
    new_holes = '''    # --- fill remaining wall holes (continuity) — skip windows ---
    hole_filled = 0
    if fill_wall_holes:
        _strict_holes = bool(
            (style_facade_rules(style) if style else {}).get("strict_window_openings")
        ) or (str(style or "").lower() in ("fantasy", "western"))
        _hole_passes = 3 if _strict_holes else 2
        for _pass in range(_hole_passes):'''
    if old_holes not in src:
        raise SystemExit("hole fill block not found")
    src = src.replace(old_holes, new_holes, 1)

    LH.write_text(src, encoding="utf-8")
    ast.parse(src)
    print("look_harden patched OK")

    # rules JSON
    rp = ROOT / "docs" / "mc-knowledge" / "builds" / "look_harden_rules.json"
    data = json.loads(rp.read_text(encoding="utf-8"))
    data["version"] = 5
    data["updated"] = "2026-10-21"
    data["id"] = "look_harden_rules_v5"
    data["defaults"]["strict_window_openings"] = False
    data["notes"]["strict_window_openings"] = (
        "Phase F: fantasy/western set strict_window_openings in _STYLE_FACADE. "
        "Only rectangular mid (≤2×2) or repeating rect bands are kept; near_rect_mid "
        "holes seal as defects. Metrics: report window_cells and glass_cells separately."
    )
    rp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("rules v5")

    kb = ROOT / "docs" / "mc-knowledge" / "builds" / "window-opening-seal.md"
    kb.write_text(
        """# Window openings vs shell defects (Phase F)

## Problem

Tall / irregular refs (fantasy, western) leave many 1–6 cell perimeter holes.
`detect_window_mask` used to keep `near_rect_mid` openings, so `window_cells` stayed
huge while true `glass_cells` (panes) were low.

## Policy

| Class | Keep? | Notes |
|-------|-------|-------|
| Existing glass panes | yes | always |
| Rectangular mid 1×1–2×2 | yes | intentional slit/window |
| Rectangular repeating across ≥2 faces | yes | band rhythm |
| `near_rect_mid` / ragged / tall / wide | **no** (strict styles) | seal as wall |

Strict styles (facade `strict_window_openings`): **fantasy**, **western**.

## Wired

- `look_harden.detect_window_mask(..., style=)`
- `_STYLE_FACADE["fantasy"|"western"]["strict_window_openings"]=true`
- Extra wall-hole pass when strict
- Metrics: always distinguish `window_cells` vs `glass_cells`
""",
        encoding="utf-8",
    )
    print("wrote", kb.name)


if __name__ == "__main__":
    main()