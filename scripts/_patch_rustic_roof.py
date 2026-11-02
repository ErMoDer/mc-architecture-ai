# -*- coding: utf-8 -*-
"""Patch scaffold roof + roof_score elevated footprint for rustic lakeside."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"E:\ai agent\mc-architecture-ai")

NEW_SCAFFOLD_BLOCK = r'''def _perimeter_mask(fp: np.ndarray) -> np.ndarray:
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


def _building_footprint_from_occ(occ: np.ndarray) -> np.ndarray:
    """Building mass footprint, skipping full-box ground fill slabs common in 32^3 skeletons."""
    occ = np.asarray(occ).astype(bool)
    sx, sy, sz = occ.shape
    per_y = occ.sum(axis=(0, 2)).astype(np.int64)
    ys = np.where(per_y > 0)[0]
    if ys.size == 0:
        return np.zeros((sx, sz), dtype=bool)
    y0, y1 = int(ys.min()), int(ys.max())
    pmax = int(per_y.max())
    cut = y0
    found = False
    for y in range(y0, y1 + 1):
        if int(per_y[y]) <= max(20, int(0.55 * pmax)):
            cut = y
            found = True
            break
    if not found:
        cut = y0 + max(1, (y1 - y0) // 4)
    if cut <= y0 and y0 + 1 <= y1:
        cut = y0 + 1
    fp = occ[:, cut : y1 + 1, :].any(axis=1) if cut <= y1 else occ.any(axis=1)
    if int(fp.sum()) < 16:
        fp2 = np.zeros((sx, sz), dtype=bool)
        for x in range(sx):
            for z in range(sz):
                col = occ[x, :, z]
                if not col.any():
                    continue
                ys_c = np.where(col)[0]
                if int(ys_c.max()) - int(ys_c.min()) >= 2 or int(col.sum()) >= 3:
                    fp2[x, z] = True
        if int(fp2.sum()) >= 8:
            fp = fp2
    if int(fp.sum()) < 8:
        fp = occ.any(axis=1)
    return fp


def scaffold_from_occupancy(
    occupancy: np.ndarray,
    *,
    wall_id: int,
    floor_id: int,
    floor_ys: list[int] | None = None,
    shell_thickness: int = 1,
    style: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Turn 32^3 occupancy into hollow shell + floor slabs + covering low-pitch roof.

    Uses a building footprint (not full ground-fill) so lakeside/irregular refs keep a
    real roof deck instead of a few peak voxels after shell extraction.
    """
    occ = np.asarray(occupancy).astype(bool)
    if occ.ndim != 3:
        raise ValueError("occupancy must be 3D")
    sx, sy, sz = occ.shape
    out = np.zeros((sx, sy, sz), dtype=np.int16)
    stats: dict[str, Any] = {
        "shell": 0,
        "floors": 0,
        "roof": 0,
        "floor_ys": [],
        "build_fp": 0,
        "roof_deck_y": -1,
        "roof_mode": "none",
    }

    footprint_all = occ.any(axis=1)
    build_fp = _building_footprint_from_occ(occ)
    if not build_fp.any():
        build_fp = footprint_all
    peri = _perimeter_mask(build_fp)
    stats["build_fp"] = int(build_fp.sum())

    ys_with = [int(y) for y in range(sy) if occ[:, y, :].any()]
    y_foundation = ys_with[0] if ys_with else 0

    hmap = np.full((sx, sz), -1, dtype=np.int16)
    xs_b, zs_b = np.where(build_fp)
    for x, z in zip(xs_b.tolist(), zs_b.tolist()):
        ys_c = np.where(occ[x, :, z])[0]
        if ys_c.size:
            hmap[x, z] = int(ys_c.max())
    valid_h = hmap[hmap >= 0]
    if valid_h.size:
        roof_deck_y = int(np.percentile(valid_h.astype(np.float64), 80))
        roof_peak_y = int(valid_h.max())
        roof_deck_y = int(np.clip(roof_deck_y, y_foundation + 2, sy - 1))
        if roof_peak_y - roof_deck_y > 6:
            roof_deck_y = max(roof_deck_y, roof_peak_y - 4)
    else:
        roof_deck_y = max(y_foundation + 3, (sy - 1) // 2)
        roof_peak_y = roof_deck_y
    stats["roof_deck_y"] = int(roof_deck_y)

    if not floor_ys:
        if ys_with:
            y0, y1 = y_foundation, int(roof_deck_y)
            spacing = 4
            floor_ys = list(range(y0, y1 + 1, spacing))
            if y0 not in floor_ys:
                floor_ys.insert(0, y0)
            if y1 not in floor_ys:
                floor_ys.append(y1)
        else:
            floor_ys = [0]
    floor_ys = sorted({int(y) for y in floor_ys if 0 <= int(y) < sy})
    floor_ys = [y for y in floor_ys if y <= roof_deck_y + 1] or [y_foundation]
    if y_foundation not in floor_ys:
        floor_ys = sorted(set(floor_ys + [y_foundation]))
    stats["floor_ys"] = floor_ys

    style_l = (style or "").strip().lower()
    if style_l in ("rustic", "western", "japanese"):
        max_rise = 2
    elif style_l in ("fantasy", "medieval", "european", "chinese"):
        max_rise = 3
    else:
        max_rise = 2

    for y in range(y_foundation, min(roof_deck_y, sy - 1) + 1):
        slice_fp = occ[:, y, :] & build_fp
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
            out[:, y, :][slice_peri] = int(wall_id)
            stats["shell"] += int(slice_peri.sum())
            floor_mask = slice_fp
        else:
            out[:, y, :][peri] = int(wall_id)
            stats["shell"] += int(peri.sum())
            floor_mask = build_fp

        if y in floor_ys and build_fp.any():
            use_fp = floor_mask if floor_mask.any() else build_fp
            out[:, y, :][use_fp] = int(floor_id)
            out[:, y, :][peri] = int(wall_id)
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
                out[x, yy, z] = int(wall_id)
                roof_count += 1
            if peri[x, z] and yy_deck - 1 >= y_foundation:
                if out[x, yy_deck - 1, z] == 0:
                    out[x, yy_deck - 1, z] = int(wall_id)
                    roof_count += 1
        stats["roof"] = int(roof_count)
        stats["roof_mode"] = "low_pitch_deck"

    return out, stats


def rule_scaffold_voxels(
'''


def patch_gen_strategy() -> None:
    p = ROOT / "src" / "app" / "gen_strategy.py"
    text = p.read_text(encoding="utf-8")
    start = text.index("def _perimeter_mask(fp: np.ndarray)")
    end = text.index("def rule_scaffold_voxels(")
    rest = text[end:]
    rest_body = "".join(rest.splitlines(keepends=True)[1:])
    text2 = text[:start] + NEW_SCAFFOLD_BLOCK + rest_body

    old_call = (
        "                vox, sc_stats = scaffold_from_occupancy(\n"
        "                    occ, wall_id=wall_id, floor_id=floor_id, floor_ys=floor_ys or None\n"
        "                )"
    )
    new_call = (
        "                vox, sc_stats = scaffold_from_occupancy(\n"
        "                    occ,\n"
        "                    wall_id=wall_id,\n"
        "                    floor_id=floor_id,\n"
        "                    floor_ys=floor_ys or None,\n"
        "                    style=style,\n"
        "                )"
    )
    if old_call not in text2:
        raise SystemExit("scaffold call site not found")
    text2 = text2.replace(old_call, new_call, 1)
    p.write_text(text2, encoding="utf-8")
    print("patched", p)


def patch_structure_constraints() -> None:
    p = ROOT / "src" / "app" / "structure_constraints.py"
    text = p.read_text(encoding="utf-8")

    old = '''def _roof_score(solid: np.ndarray) -> dict[str, float]:
    ys = np.where(solid.any(axis=(0, 2)))[0]
    if ys.size == 0:
        return {"roof_score": 0.0, "top_y": -1, "top_band_frac": 0.0}
    y_min, y_max = int(ys.min()), int(ys.max())
    height = max(1, y_max - y_min + 1)
    band = max(1, height // 5)
    top = solid[:, y_max - band + 1 : y_max + 1, :]
    mid_lo = y_min + height // 3
    mid_hi = y_min + (2 * height) // 3
    mid = solid[:, mid_lo:mid_hi, :] if mid_hi > mid_lo else solid[:, y_min : y_max + 1, :]
    top_frac = float(top.mean()) if top.size else 0.0
    mid_frac = float(mid.mean()) if mid.size else 0.0
    top_slice = solid[:, y_max, :]
    fp, fp_n = _footprint(solid)
    cover = float((top_slice & fp).sum() / max(1, fp_n))
    score = 0.45 * cover + 0.35 * min(1.0, top_frac * 4) + 0.2 * float(top_frac >= mid_frac * 0.5)
    return {
        "roof_score": float(np.clip(score, 0.0, 1.0)),
        "top_y": float(y_max),
        "top_band_frac": top_frac,
        "top_footprint_cover": cover,
        "mid_frac": mid_frac,
    }
'''

    new = '''def _elevated_footprint(solid: np.ndarray) -> tuple[np.ndarray, int]:
    """Footprint for roof cover: columns with mass above the ground band.

    Full-box ground slabs (common after scaffold floors) inflate `_footprint` to
    ~32x32 and make sparse-but-real roofs look like cover~0.02. Prefer columns
    that rise above the foundation band.
    """
    fp_all, fp_all_n = _footprint(solid)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    if ys.size == 0:
        return fp_all, fp_all_n
    y_min, y_max = int(ys.min()), int(ys.max())
    height = max(1, y_max - y_min + 1)
    band = max(1, min(3, height // 4))
    y_cut = y_min + band
    if y_cut > y_max:
        return fp_all, fp_all_n
    elev = solid[:, y_cut : y_max + 1, :].any(axis=1)
    # Drop lone ground stubs: need at least 2 solids in the column span
    xs, zs = np.where(elev)
    for x, z in zip(xs.tolist(), zs.tolist()):
        if int(solid[x, y_min : y_max + 1, z].sum()) < 2:
            elev[x, z] = False
    elev_n = int(elev.sum())
    # Fallback if elevated mask collapsed (very flat pads)
    if elev_n < max(8, int(0.05 * max(1, fp_all_n))):
        return fp_all, fp_all_n
    return elev, elev_n


def _roof_score(solid: np.ndarray) -> dict[str, float]:
    ys = np.where(solid.any(axis=(0, 2)))[0]
    if ys.size == 0:
        return {"roof_score": 0.0, "top_y": -1, "top_band_frac": 0.0}
    y_min, y_max = int(ys.min()), int(ys.max())
    height = max(1, y_max - y_min + 1)
    band = max(1, height // 5)
    top = solid[:, y_max - band + 1 : y_max + 1, :]
    mid_lo = y_min + height // 3
    mid_hi = y_min + (2 * height) // 3
    mid = solid[:, mid_lo:mid_hi, :] if mid_hi > mid_lo else solid[:, y_min : y_max + 1, :]
    top_frac = float(top.mean()) if top.size else 0.0
    mid_frac = float(mid.mean()) if mid.size else 0.0
    top_slice = solid[:, y_max, :]
    fp_all, fp_all_n = _footprint(solid)
    fp_elev, fp_n = _elevated_footprint(solid)
    cover = float((top_slice & fp_elev).sum() / max(1, fp_n))
    cover_all = float((top_slice & fp_all).sum() / max(1, fp_all_n))
    # Density of top band relative to elevated footprint volume slice
    elev_band = top & fp_elev[:, None, :] if False else None  # placeholder kept simple
    # Prefer cover vs elevated fp; also reward top_band vs mid
    score = 0.45 * cover + 0.35 * min(1.0, top_frac * 4) + 0.2 * float(top_frac >= mid_frac * 0.5)
    # Mild boost when elevated cover is strong but volume-box top_frac is diluted by empty sky
    if cover >= 0.35 and cover_all < cover * 0.5:
        score = max(score, 0.40 * cover + 0.40 * min(1.0, cover * 1.2) + 0.2)
    return {
        "roof_score": float(np.clip(score, 0.0, 1.0)),
        "top_y": float(y_max),
        "top_band_frac": top_frac,
        "top_footprint_cover": cover,
        "top_footprint_cover_all": cover_all,
        "elevated_footprint": float(fp_n),
        "mid_frac": mid_frac,
    }
'''

    # Clean the dead placeholder line from new for cleanliness
    new = new.replace(
        "    # Density of top band relative to elevated footprint volume slice\n"
        "    elev_band = top & fp_elev[:, None, :] if False else None  # placeholder kept simple\n"
        "    # Prefer cover vs elevated fp; also reward top_band vs mid\n",
        "    # Prefer cover vs elevated fp; also reward top_band vs mid\n",
    )

    if old not in text:
        raise SystemExit("_roof_score block not found exactly")
    text2 = text.replace(old, new, 1)

    # Note in SCAFFOLD_THRESHOLDS comment — keep min_roof at 0.18 (no further loosen)
    old_c = (
        "# similar_scaffold / rule_scaffold: thin perimeter shells + sparse roofs fail VAE-era cuts\n"
        "# (e.g. exterior 0.02-0.05, roof ~0.20) even when the footprint/shell is visually sane.\n"
    )
    new_c = (
        "# similar_scaffold / rule_scaffold: thin perimeter shells + sparse roofs fail VAE-era cuts\n"
        "# (e.g. exterior 0.02-0.05, roof ~0.20) even when the footprint/shell is visually sane.\n"
        "# Roof cover uses elevated footprint (see _elevated_footprint); min_roof stays 0.18.\n"
    )
    if old_c in text2:
        text2 = text2.replace(old_c, new_c, 1)

    p.write_text(text2, encoding="utf-8")
    print("patched", p)


def patch_look_harden_rustic_low() -> None:
    """Short rustic buildings: prefer flat/low deck over aggressive pitch that clears mass."""
    p = ROOT / "src" / "app" / "look_harden.py"
    text = p.read_text(encoding="utf-8")
    needle = '''    key = (style or "unknown").strip().lower() or "unknown"
    want_pitch = key in _PITCHED_STYLES and key not in _FLAT_ROOF_STYLES
    # also pitch unknown/fantasy; force flat for industrial family
    if key in _FLAT_ROOF_STYLES:
        want_pitch = False
'''
    repl = '''    key = (style or "unknown").strip().lower() or "unknown"
    want_pitch = key in _PITCHED_STYLES and key not in _FLAT_ROOF_STYLES
    # also pitch unknown/fantasy; force flat for industrial family
    if key in _FLAT_ROOF_STYLES:
        want_pitch = False
    # Short rustic/western cabins: aggressive gable clears the deck and kills roof_score
    # against ground-inflated footprints. Prefer flat/low deck when wall height is small.
    height = int(y1) - int(y0) + 1
    if want_pitch and key in ("rustic", "western") and height <= 12:
        want_pitch = False
'''
    if needle not in text:
        raise SystemExit("harden_roof_silhouette pitch gate not found")
    # Only replace first occurrence in harden_roof_silhouette
    text2 = text.replace(needle, repl, 1)
    p.write_text(text2, encoding="utf-8")
    print("patched", p)


def main() -> None:
    patch_gen_strategy()
    patch_structure_constraints()
    patch_look_harden_rustic_low()
    print("OK")


if __name__ == "__main__":
    main()
