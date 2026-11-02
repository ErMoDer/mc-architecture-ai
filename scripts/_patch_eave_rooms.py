# -*- coding: utf-8 -*-
"""Patch eave/pitched skin roof + simple interior partitions (hollow-friendly)."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BAK = ROOT / "_xfer" / ("bak_eave_rooms_" + STAMP)
BAK.mkdir(parents=True, exist_ok=True)


HELPERS = r'''
def _gable_rise_map(
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


def _place_skin_gable_roof(
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
    roof_count = 0
    xs, zs = np.where(roof_fp)
    # 1) eave deck
    for x, z in zip(xs.tolist(), zs.tolist()):
        out[x, eave_y, z] = int(roof_id)
        roof_count += 1
    # 2) clear old mass above eave on footprint, then place skin
    for x, z in zip(xs.tolist(), zs.tolist()):
        h_off = int(rise_map[x, z])
        peak = int(min(sy - 1, eave_y + h_off))
        for yy in range(eave_y + 1, sy):
            # keep nothing above; rebuild skin
            if out[x, yy, z] != 0:
                out[x, yy, z] = 0
        # skin at peak (+ optional underlay)
        out[x, peak, z] = int(roof_id)
        roof_count += 1
        if peak - 1 > eave_y:
            out[x, peak - 1, z] = int(roof_id)
            roof_count += 1
        # gable-end wall under slope on peri only
        if peri[x, z] and wall_id is not None and peak > eave_y + 1:
            for yy in range(eave_y + 1, peak):
                if out[x, yy, z] == 0:
                    out[x, yy, z] = int(wall_id)
    # 3) clear interior attic (non-peri) between eave+1 and skin-1
    if clear_attic:
        for x, z in zip(xs.tolist(), zs.tolist()):
            if peri[x, z]:
                continue
            peak = int(min(sy - 1, eave_y + int(rise_map[x, z])))
            for yy in range(eave_y + 1, max(eave_y + 1, peak - 1)):
                # do not delete floor slabs or intentional interiors that aren't roof
                # attic should be air; floors are at known ys below eave usually
                if yy >= eave_y:
                    cur = int(out[x, yy, z])
                    if cur == int(roof_id) or cur == 0:
                        out[x, yy, z] = 0
    # 4) overhang eave ring
    oh = max(0, min(2, int(overhang)))
    oh_n = 0
    if oh > 0:
        px, pz = np.where(peri & roof_fp) if peri.shape == roof_fp.shape else np.where(peri)
        for x, z in zip(px.tolist(), pz.tolist()):
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for step in range(1, oh + 1):
                    nx, nz = x + dx * step, z + dz * step
                    if not (0 <= nx < sx and 0 <= nz < sz):
                        break
                    if roof_fp[nx, nz] if nx < roof_fp.shape[0] and nz < roof_fp.shape[1] else False:
                        break
                    if out[nx, eave_y, nz] == 0:
                        out[nx, eave_y, nz] = int(roof_id)
                        oh_n += 1
                        roof_count += 1
    info = {
        "roof_mode": "skin_gable",
        "eave_y": eave_y,
        "overhang": oh,
        "overhang_cells": oh_n,
        **ginfo,
    }
    return roof_count, info


def _place_interior_partitions(
    out: np.ndarray,
    *,
    build_fp: np.ndarray,
    peri: np.ndarray,
    y0: int,
    y1: int,
    wall_id: int,
    style: str | None = None,
) -> dict[str, Any]:
    """Light 1-thick room split (mid wall or L) with doorway; keep large connected room_air."""
    sx, sy, sz = out.shape
    y0, y1 = int(y0), int(y1)
    info: dict[str, Any] = {"partition_cells": 0, "door_cells": 0, "mode": "none"}
    if y1 <= y0 + 3 or not build_fp.any():
        return info
    # interior = footprint eroded (not on peri)
    interior = build_fp & ~peri
    # erode one more ring so partitions don't fuse into outer shell
    if interior.any():
        thick = _dilate_mask(peri, 1)
        interior = interior & ~thick
    xs, zs = np.where(interior)
    if xs.size < 20:
        return info
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    if min(wx, wz) < 5:
        return info
    style_l = (style or "").strip().lower()
    # Prefer split along longer axis
    split_along_x = wx >= wz  # wall runs parallel to X (constant z)
    cells = 0
    door_cells = 0
    y_lo = y0 + 1
    y_hi = min(y1 - 1, sy - 1)  # stop under eave/deck
    if y_hi <= y_lo:
        return info
    door_h = 2
    door_y0 = y_lo
    door_y1 = min(y_lo + door_h - 1, y_hi)

    def _paint_wall_line(coords: list[tuple[int, int]], door_idx: int) -> None:
        nonlocal cells, door_cells
        n = len(coords)
        if n < 3:
            return
        for i, (x, z) in enumerate(coords):
            is_door = abs(i - door_idx) <= 0
            for y in range(y_lo, y_hi + 1):
                if is_door and door_y0 <= y <= door_y1:
                    if out[x, y, z] != 0 and out[x, y, z] != int(wall_id):
                        continue
                    out[x, y, z] = 0
                    door_cells += 1
                    continue
                cur = int(out[x, y, z])
                if cur == 0:
                    out[x, y, z] = int(wall_id)
                    cells += 1

    if split_along_x:
        mid_z = int(round((minz + maxz) / 2.0))
        # snap mid_z onto interior row with most cells
        best_z, best_n = mid_z, -1
        for zz in range(minz, maxz + 1):
            n = int(interior[:, zz].sum()) if 0 <= zz < sz else 0
            if n > best_n:
                best_n, best_z = n, zz
        mid_z = best_z
        coords = [(int(x), mid_z) for x in range(minx, maxx + 1) if interior[x, mid_z]]
        door_idx = len(coords) // 2
        _paint_wall_line(coords, door_idx)
        info["mode"] = "mid_z"
        # L-stub for larger footprints
        if max(wx, wz) >= 10 and style_l not in ("modern",):
            mid_x = coords[door_idx][0] if coords else int(round((minx + maxx) / 2.0))
            stub_len = max(2, wz // 3)
            stub = []
            for z in range(mid_z + 1, min(maxz, mid_z + stub_len) + 1):
                if interior[mid_x, z]:
                    stub.append((mid_x, z))
            if len(stub) >= 2:
                _paint_wall_line(stub, door_idx=len(stub))  # no door on stub tip
                info["mode"] = "L_split"
    else:
        mid_x = int(round((minx + maxx) / 2.0))
        best_x, best_n = mid_x, -1
        for xx in range(minx, maxx + 1):
            n = int(interior[xx, :].sum()) if 0 <= xx < sx else 0
            if n > best_n:
                best_n, best_x = n, xx
        mid_x = best_x
        coords = [(mid_x, int(z)) for z in range(minz, maxz + 1) if interior[mid_x, z]]
        door_idx = len(coords) // 2
        _paint_wall_line(coords, door_idx)
        info["mode"] = "mid_x"
        if max(wx, wz) >= 10 and style_l not in ("modern",):
            mid_z = coords[door_idx][1] if coords else int(round((minz + maxz) / 2.0))
            stub_len = max(2, wx // 3)
            stub = []
            for x in range(mid_x + 1, min(maxx, mid_x + stub_len) + 1):
                if interior[x, mid_z]:
                    stub.append((x, mid_z))
            if len(stub) >= 2:
                _paint_wall_line(stub, door_idx=len(stub))
                info["mode"] = "L_split"

    info["partition_cells"] = int(cells)
    info["door_cells"] = int(door_cells)
    return info


'''


def backup(rel: str) -> Path:
    src = ROOT / rel
    dst = BAK / rel.replace("\\", "__").replace("/", "__")
    dst.write_bytes(src.read_bytes())
    return dst


def patch_gen_strategy() -> None:
    path = ROOT / "src" / "app" / "gen_strategy.py"
    backup("src/app/gen_strategy.py")
    text = path.read_text(encoding="utf-8")

    if "_place_skin_gable_roof" not in text:
        anchor = "def scaffold_from_occupancy("
        if anchor not in text:
            raise SystemExit("scaffold_from_occupancy missing")
        # Insert after _seal_shell_columns block if present, else before scaffold
        if "def _seal_shell_columns(" in text:
            # insert just before scaffold_from_occupancy
            text = text.replace(anchor, HELPERS + anchor, 1)
        else:
            text = text.replace(anchor, HELPERS + anchor, 1)
        print("helpers inserted")
    else:
        print("helpers already present")

    # Replace max_rise style block to allow real pitch for euro/rustic
    old_rise = '''    if style_l in ("rustic", "western", "japanese"):
        max_rise = 2
    elif style_l in ("fantasy", "medieval", "chinese"):
        max_rise = 3
    elif style_l == "european":
        # European sparse outlines: low deck; hollowness comes from ring floors / no posts
        max_rise = 1 if sparse_fp else 2
    else:
        max_rise = 2
    if sparse_fp and style_l in ("european", "medieval", "modern"):
        max_rise = min(max_rise, 1)
    stats["max_rise"] = int(max_rise)
'''
    new_rise = '''    # Skin-gable rise (hollow attic). Flat styles keep 0-1 for eave deck only.
    if style_l in ("industrial", "modern", "scifi"):
        max_rise = 0
    elif style_l in ("european", "rustic", "western"):
        max_rise = 3 if not sparse_fp else 3
    elif style_l in ("chinese", "japanese"):
        max_rise = 3
    elif style_l in ("fantasy", "medieval"):
        max_rise = 3
    else:
        max_rise = 2
    stats["max_rise"] = int(max_rise)
'''
    if old_rise not in text:
        raise SystemExit("max_rise block not found")
    text = text.replace(old_rise, new_rise, 1)
    print("max_rise updated")

    # Replace entire roof deck + gable block with skin gable / flat+eave
    old_roof_start = "    if build_fp.any() and 0 <= roof_deck_y < sy:\n        use_roof_fp = roof_fp if roof_fp is not None and roof_fp.any() else build_fp"
    # Find from old_roof_start through medieval gable block end (before corner posts)
    marker_end = "    # Load-bearing corner posts only (bbox corners snapped to peri)."
    if marker_end not in text:
        # older accent comment
        marker_end = "    # Corner accents on wall height (not roof / foundation)"
    idx0 = text.find(old_roof_start)
    idx1 = text.find(marker_end)
    if idx0 < 0 or idx1 < 0 or idx1 <= idx0:
        raise SystemExit("roof block bounds not found: %s %s" % (idx0, idx1))

    new_roof = '''    if build_fp.any() and 0 <= roof_deck_y < sy:
        use_roof_fp = roof_fp if roof_fp is not None and roof_fp.any() else build_fp
        want_skin_gable = style_l in (
            "european", "rustic", "western", "chinese", "japanese", "medieval", "fantasy",
        ) and int(max_rise) >= 2
        if want_skin_gable:
            # True eaves + pitched silhouette (skin only — do not solid-fill attic)
            plateau = 0.40 if style_l in ("european", "rustic", "western") else 0.72
            oh = 2 if style_l in ("european", "rustic", "chinese", "western") else 1
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
            )
            stats["roof"] = int(roof_count)
            stats["roof_mode"] = str(rinfo.get("roof_mode") or "skin_gable")
            stats["eave_overhang"] = int(rinfo.get("overhang") or 0)
            stats["gable_rise"] = int(rinfo.get("rise") or max_rise)
            stats["sparse_interior_posts"] = False
        else:
            # Flat / low deck (industrial, modern): coherent cover + eave ring
            xs, zs = np.where(use_roof_fp)
            roof_count = 0
            yy_deck = int(roof_deck_y)
            for x, z in zip(xs.tolist(), zs.tolist()):
                out[x, yy_deck, z] = int(roof_id)
                roof_count += 1
            # thin optional plateau bump (max_rise 0-1)
            if int(max_rise) > 0 and xs.size:
                cx = float(xs.mean()); cz = float(zs.mean())
                dists = np.sqrt((xs.astype(np.float64) - cx) ** 2 + (zs.astype(np.float64) - cz) ** 2)
                max_d = max(1.0, float(dists.max()) if dists.size else 1.0)
                for x, z, d in zip(xs.tolist(), zs.tolist(), dists.tolist()):
                    if float(d) / max_d <= 0.55:
                        yy = int(min(sy - 1, yy_deck + int(max_rise)))
                        if yy > yy_deck:
                            out[x, yy, z] = int(roof_id)
                            roof_count += 1
            # eave overhang ring for industrial/modern (visible lip, not pitch)
            oh = 1
            oh_n = 0
            px, pz = np.where(peri & use_roof_fp) if peri.shape == use_roof_fp.shape else np.where(peri)
            for x, z in zip(px.tolist(), pz.tolist()):
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, nz = x + dx, z + dz
                    if not (0 <= nx < sx and 0 <= nz < sz):
                        continue
                    if use_roof_fp[nx, nz]:
                        continue
                    if out[nx, yy_deck, nz] == 0:
                        out[nx, yy_deck, nz] = int(roof_id)
                        oh_n += 1
                        roof_count += 1
            # peri connect under deck (no interior posts)
            if sparse_fp:
                peri_roof = (peri & use_roof_fp) if peri.shape == use_roof_fp.shape else peri
                for x, z in zip(*np.where(peri_roof)):
                    for y in range(max(y_foundation + 1, yy_deck - 2), yy_deck):
                        if out[x, y, z] == 0:
                            out[x, y, z] = int(wall_id)
                            stats["shell"] += 1
            stats["roof"] = int(roof_count)
            stats["roof_mode"] = "flat_eave_deck"
            stats["eave_overhang"] = oh
            stats["eave_cells"] = int(oh_n)
            stats["sparse_interior_posts"] = False

    # Seal perimeter shell gaps (continuous walls under deck)
    seal_n = _seal_shell_columns(
        out,
        peri=peri,
        y0=y_foundation,
        y1=int(roof_deck_y),
        wall_id=int(wall_id),
        foundation_id=int(foundation_id),
    )
    if seal_n:
        stats["shell_seal"] = int(seal_n)
        stats["shell"] = int(stats.get("shell") or 0) + int(seal_n)

    # Simple interior partitions (1-thick + doorway); after shell/floors, under eave
    if build_fp.any():
        part = _place_interior_partitions(
            out,
            build_fp=build_fp if not sparse_fp else (roof_fp if roof_fp is not None and roof_fp.any() else build_fp),
            peri=peri,
            y0=int(y_foundation),
            y1=int(roof_deck_y),
            wall_id=int(wall_id),
            style=style_l,
        )
        stats["partition_mode"] = part.get("mode")
        stats["partition_cells"] = int(part.get("partition_cells") or 0)
        stats["partition_door_cells"] = int(part.get("door_cells") or 0)

'''
    text = text[:idx0] + new_roof + text[idx1:]
    path.write_text(text, encoding="utf-8")
    print("gen_strategy roof+partitions patched")


def patch_look_harden() -> None:
    path = ROOT / "src" / "app" / "look_harden.py"
    backup("src/app/look_harden.py")
    text = path.read_text(encoding="utf-8")

    # Bump eave overhang for euro/rustic; industrial gets overhang 1 + cornice
    old_eu = '''    "european": {
        # full_style_v2 seed102 glass~448 (curtain-wall relapse vs older ~224).
        # Mid dens: sp=4 bands=3 from_corner=3 -> probe ~256 (aim 200-280).
        "window_spacing": 4,
        "window_from_corner": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
'''
    new_eu = '''    "european": {
        # full_style_v2 seed102 glass~448 (curtain-wall relapse vs older ~224).
        # Mid dens: sp=4 bands=3 from_corner=3 -> probe ~256 (aim 200-280).
        "window_spacing": 4,
        "window_from_corner": 3,
        "window_width_max": 1,
        "eave_overhang": 2,
'''
    if old_eu in text:
        text = text.replace(old_eu, new_eu, 1)
        print("european eave_overhang -> 2")
    else:
        print("WARN european eave block not exact")

    old_ru = '''    "rustic": {
        "window_spacing": 4,
        "window_width_max": 1,
        "eave_overhang": 1,
'''
    new_ru = '''    "rustic": {
        "window_spacing": 4,
        "window_width_max": 1,
        "eave_overhang": 2,
'''
    if old_ru in text:
        text = text.replace(old_ru, new_ru, 1)
        print("rustic eave_overhang -> 2")

    old_ind = '''    "industrial": {
        # Was defaults (sp=3, bands=4, ww=2) -> ~450 glass; strip windows + solid panels between.
        "window_spacing": 4,
        "window_width_max": 1,
        "window_height_max": 2,
        "window_from_corner": 2,
        "eave_overhang": 0,
        "place_cornice": False,
'''
    new_ind = '''    "industrial": {
        # Was defaults (sp=3, bands=4, ww=2) -> ~450 glass; strip windows + solid panels between.
        "window_spacing": 4,
        "window_width_max": 1,
        "window_height_max": 2,
        "window_from_corner": 2,
        "eave_overhang": 1,
        "place_cornice": True,
'''
    if old_ind in text:
        text = text.replace(old_ind, new_ind, 1)
        print("industrial eave+cornice")

    # Allow euro/rustic/western/chinese to keep pitched; use skin-only in harden_roof
    old_force = '''    # Scaffold similar_scaffold already places low_pitch_deck / filled euro deck.
    # Aggressive gable here clears that deck and leaves a thin ridge (euro cover~0.05).
    # Keep flat/low deck for rustic/western/european (and chinese earth houses).
    if want_pitch and key in ("rustic", "western", "european", "chinese"):
        want_pitch = False
'''
    new_force = '''    # Scaffold now places hollow skin_gable for euro/rustic/western/chinese.
    # Do NOT force-flat (that wiped eaves). Still force flat for industrial family.
    # Skin-only pitch below preserves hollowness (no solid attic fill).
'''
    if old_force not in text:
        raise SystemExit("force-flat block not found")
    text = text.replace(old_force, new_force, 1)

    # Replace solid-fill pitched loop with skin-only
    old_placed = '''    placed = 0
    stair_n = 0
    ridge_z = (minz + maxz) / 2.0
    ridge_x = (minx + maxx) / 2.0
    # Broad ridge plateau so top_footprint_cover / roof_score are not needle-thin.
    # Medieval/fantasy: wider plateau (~0.72 of half) — still visibly pitched on the
    # outer ~28%% slope, but cover/roof_score leave the ~0.72-0.77 stall.
    if key in ("medieval", "fantasy"):
        plateau = max(2, int(0.72 * max(1, half)))
    else:
        plateau = max(1, int(0.32 * max(1, half)))
    for x, z in zip(ax.tolist(), az.tolist()):
        if ridge_along_x:
            dist = abs(float(z) - ridge_z)
        else:
            dist = abs(float(x) - ridge_x)
        if dist <= plateau:
            h = int(peak_y)
        else:
            # height falls from plateau edge to eave
            span = max(1e-6, float(half - plateau))
            tnorm = min(1.0, (dist - plateau) / span)
            h = int(round(peak_y - tnorm * (peak_y - eave_y)))
        h = max(eave_y, min(peak_y, h))
        # solid fill from eave_y to h
        for y in range(eave_y, h + 1):
            if y >= sy:
                break
            if win_mask is not None and win_mask[x, y, z]:
                continue
            if _cell_is_glass(int(out[x, y, z])):
                continue
            out[x, y, z] = int(roof_block)
            placed += 1
        # stairs on outer slope face (optional cosmetic)
        if stairs_id > 0 and h < peak_y and peri[x, z]:
            # place stairs at top cell instead of full block
            out[x, h, z] = int(stairs_id)
            stair_n += 1
'''
    # Note: %% may have been single % in file - try both
    if old_placed not in text:
        old_placed2 = old_placed.replace("28%%", "28%")
        if old_placed2 in text:
            old_placed = old_placed2
        else:
            # fuzzy find
            i = text.find("    placed = 0\n    stair_n = 0\n    ridge_z")
            j = text.find("    actions.append(\n        \"roof_pitched:rise=%d eave_y=%d peak_y=%d clear=%d place=%d stairs=%d along=%s\"")
            if i < 0 or j < 0:
                raise SystemExit("pitched fill block not found")
            old_placed = text[i:j]
            print("using fuzzy pitched block", i, j)

    new_placed = '''    placed = 0
    stair_n = 0
    ridge_z = (minz + maxz) / 2.0
    ridge_x = (minx + maxx) / 2.0
    # Broad ridge plateau. Euro/rustic: mid plateau for readable eaves + slope.
    # Medieval/fantasy: wider plateau (~0.72 of half).
    if key in ("medieval", "fantasy"):
        plateau = max(2, int(0.72 * max(1, half)))
    elif key in ("european", "rustic", "western", "chinese"):
        plateau = max(1, int(0.40 * max(1, half)))
    else:
        plateau = max(1, int(0.32 * max(1, half)))
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
        # Skin-only: eave deck + surface at h (+ underlay). No solid attic fill.
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
        # stairs on outer slope face (optional cosmetic)
        if stairs_id > 0 and h < peak_y and peri[x, z]:
            out[x, h, z] = int(stairs_id)
            stair_n += 1
'''
    text = text.replace(old_placed, new_placed, 1)
    path.write_text(text, encoding="utf-8")
    print("look_harden pitched skin + eave knobs patched")


def main() -> None:
    patch_gen_strategy()
    patch_look_harden()
    print("BAK", BAK)
    print("DONE")


if __name__ == "__main__":
    main()
