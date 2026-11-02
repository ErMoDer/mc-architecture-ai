# -*- coding: utf-8 -*-
"""Patch similar_scaffold for hollow shell floors / no sparse interior posts."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_gen_strategy() -> None:
    path = ROOT / "src" / "app" / "gen_strategy.py"
    text = path.read_text(encoding="utf-8")
    marker = "def _perimeter_mask(fp: np.ndarray) -> np.ndarray:"
    if "_ring_floor_mask" not in text:
        helper = '''
def _dilate_mask(fp: np.ndarray, radius: int = 1) -> np.ndarray:
    """Chebyshev dilate of a 2D bool mask."""
    fp = np.asarray(fp, dtype=bool)
    if radius <= 0 or not fp.any():
        return fp.copy()
    h, w = fp.shape
    out = fp.copy()
    xs, zs = np.where(fp)
    r = int(radius)
    for x, z in zip(xs.tolist(), zs.tolist()):
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                xx, zz = x + dx, z + dz
                if 0 <= xx < h and 0 <= zz < w:
                    out[xx, zz] = True
    return out


def _ring_floor_mask(
    fp: np.ndarray,
    *,
    depth: int = 2,
    keep_cross: bool = True,
) -> np.ndarray:
    """Walkable ring (+ optional cross corridor) leaving a large open room in the middle.

    Full-footprint floor slabs every story made exteriors look like solid crates.
    """
    fp = np.asarray(fp, dtype=bool)
    if not fp.any():
        return fp.copy()
    peri = _perimeter_mask(fp)
    ring = _dilate_mask(peri, max(1, int(depth))) & fp
    # If footprint is too thin, fall back to full slab (still rare for houses).
    if int(ring.sum()) >= max(8, int(0.85 * int(fp.sum()))):
        return fp.copy()
    if keep_cross:
        xs, zs = np.where(fp)
        cx = int(round(float(xs.mean())))
        cz = int(round(float(zs.mean())))
        # 1-cell corridor through centroid so rooms stay reachable
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(x - cx) <= 0 or abs(z - cz) <= 0:
                ring[x, z] = True
        ring &= fp
    # Guarantee at least a usable walk band
    if int(ring.sum()) < max(12, int(0.18 * int(fp.sum()))):
        ring = _dilate_mask(peri, max(2, int(depth) + 1)) & fp
    return ring


'''
        text = text.replace(marker, helper + marker, 1)

    # Replace floor painting block inside scaffold_from_occupancy
    old_floors = '''        if y in floor_ys and build_fp.any():
            use_fp = floor_mask if floor_mask.any() else build_fp
            # Sparse outlines: fill interior only on the ground slab (avoid over-thick upper decks)
            if (
                sparse_fp
                and y == y_foundation
                and roof_fp is not None
                and int(roof_fp.sum()) > int(use_fp.sum())
            ):
                use_fp = roof_fp
            out[:, y, :][use_fp] = int(floor_id)
            out[:, y, :][peri] = peri_block
            stats["floors"] += int(use_fp.sum())
'''
    new_floors = '''        if y in floor_ys and build_fp.any():
            use_fp = floor_mask if floor_mask.any() else build_fp
            # Sparse outlines: ground slab may use filled outline, then ring-carve open room
            if (
                sparse_fp
                and y == y_foundation
                and roof_fp is not None
                and int(roof_fp.sum()) > int(use_fp.sum())
            ):
                use_fp = roof_fp
            # Hollow house: ring floors (not full footprint) so rooms stay open
            depth = 3 if y == y_foundation else 2
            use_fp = _ring_floor_mask(use_fp, depth=depth, keep_cross=True)
            out[:, y, :][use_fp] = int(floor_id)
            out[:, y, :][peri] = peri_block
            stats["floors"] += int(use_fp.sum())
            stats["floor_mode"] = "ring"
'''
    if old_floors not in text:
        raise SystemExit("floor block not found in gen_strategy")
    text = text.replace(old_floors, new_floors, 1)

    # Normalize story floors: fewer slabs, taller clear
    old_norm_call = '''    floor_ys = _normalize_story_floors(
        floor_ys,
        y0=int(y_foundation),
        y_roof=int(roof_deck_y),
        spacing=5,
        min_gap=3,
        max_stories=5,
    )
'''
    new_norm_call = '''    floor_ys = _normalize_story_floors(
        floor_ys,
        y0=int(y_foundation),
        y_roof=int(roof_deck_y),
        spacing=6,
        min_gap=4,
        max_stories=4,
    )
'''
    if old_norm_call not in text:
        raise SystemExit("normalize story floors call not found")
    text = text.replace(old_norm_call, new_norm_call, 1)

    # Remove sparse interior posts under filled roof; perimeter seal only
    old_posts = '''        # 3) Ensure shell walls connect up to deck under filled roof (reduce drop_float_cc)
        if sparse_fp:
            for x, z in zip(*np.where(use_roof_fp)):
                if not peri[x, z]:
                    # thin interior posts every few cells keep roof CC-linked
                    if (x + z) % 3 != 0:
                        continue
                for y in range(max(y_foundation + 1, yy_deck - 2), yy_deck):
                    if out[x, y, z] == 0:
                        out[x, y, z] = int(wall_id)
                        stats["shell"] += 1
        stats["roof"] = int(roof_count)
        stats["roof_mode"] = "low_pitch_deck_filled" if sparse_fp else "low_pitch_deck"
'''
    new_posts = '''        # 3) Connect ONLY perimeter columns up to deck (no interior pier forest).
        # Sparse euro used to plant (x+z)%3 posts under filled deck → killed hollowness.
        if sparse_fp:
            for x, z in zip(*np.where(peri & use_roof_fp if peri.shape == use_roof_fp.shape else peri)):
                for y in range(max(y_foundation + 1, yy_deck - 2), yy_deck):
                    if out[x, y, z] == 0:
                        out[x, y, z] = int(wall_id)
                        stats["shell"] += 1
        stats["roof"] = int(roof_count)
        # Keep a covering roof deck; name distinguishes no-interior-posts path
        stats["roof_mode"] = "low_pitch_deck_shell" if sparse_fp else "low_pitch_deck"
        stats["sparse_interior_posts"] = False
'''
    if old_posts not in text:
        raise SystemExit("sparse posts block not found")
    text = text.replace(old_posts, new_posts, 1)

    # European sparse: prefer shell roof without over-filling interior mass under deck
    old_euro = '''    elif style_l == "european":
        # European sparse outlines: prefer coherent low deck over needle peak
        max_rise = 1 if sparse_fp else 2
'''
    new_euro = '''    elif style_l == "european":
        # European sparse outlines: low deck; hollowness comes from ring floors / no posts
        max_rise = 1 if sparse_fp else 2
'''
    if old_euro in text:
        text = text.replace(old_euro, new_euro, 1)

    # rule_scaffold ring floors
    old_rule_floors = '''    for y in floor_ys:
        if y >= sy or y >= y1:
            continue
        out[x0:x1, y, z0:z1] = int(floor_id)
'''
    new_rule_floors = '''    build_box = np.zeros((sx, sz), dtype=bool)
    build_box[x0:x1, z0:z1] = True
    for y in floor_ys:
        if y >= sy or y >= y1:
            continue
        depth = 3 if y == y0 else 2
        ring = _ring_floor_mask(build_box, depth=depth, keep_cross=True)
        out[:, y, :][ring] = int(floor_id)
'''
    if old_rule_floors not in text:
        raise SystemExit("rule_scaffold floors not found")
    text = text.replace(old_rule_floors, new_rule_floors, 1)

    old_rule_norm = '''    floor_ys = _normalize_story_floors(
        None, y0=y0, y_roof=y1, spacing=5, min_gap=3, max_stories=4
    )
'''
    new_rule_norm = '''    floor_ys = _normalize_story_floors(
        None, y0=y0, y_roof=y1, spacing=6, min_gap=4, max_stories=3
    )
'''
    if old_rule_norm in text:
        text = text.replace(old_rule_norm, new_rule_norm, 1)

    path.write_text(text, encoding="utf-8")
    print("patched", path)


def patch_look_harden() -> None:
    path = ROOT / "src" / "app" / "look_harden.py"
    text = path.read_text(encoding="utf-8")

    # Add hollow_floors param to harden_shell_and_floors
    old_sig = '''def harden_shell_and_floors(
    voxels: np.ndarray,
    *,
    wall_id: int,
    floor_id: int,
    floor_spacing: int = 5,
    clear_interior_clutter: bool = True,
    shell_thickness: int = 1,
    fill_wall_holes: bool = True,
    regular_floors: bool = True,
    smooth_roof: bool = True,
    preserve_windows: bool = True,
    place_window_glass: bool = True,
    glass_id: int = 0,
    facade_detail: bool = True,
    style: str | None = None,
    palette: dict[int, str] | None = None,
    use_knowledge: bool = True,
    role_materials: dict[str, int] | None = None,
) -> tuple[np.ndarray, list[str]]:
    """Stronger shell continuity + regular flat floor slabs + cheap roof tidy.

    - Perimeter wall filled (optional 1-block thickness inward).
    - With preserve_windows (default): keep window-like openings; fill only
      tiny/irregular perimeter defects. Optionally place glass in openings.
    - With preserve_windows=False: fill-all (legacy strong shell).
    - Floors at regular Y spacing across active footprint.
    - Roof cap + single-cell dip fill; trim lonely eaves spikes.
    """
'''
    new_sig = '''def harden_shell_and_floors(
    voxels: np.ndarray,
    *,
    wall_id: int,
    floor_id: int,
    floor_spacing: int = 5,
    clear_interior_clutter: bool = True,
    shell_thickness: int = 1,
    fill_wall_holes: bool = True,
    regular_floors: bool = True,
    hollow_floors: bool = True,
    smooth_roof: bool = True,
    preserve_windows: bool = True,
    place_window_glass: bool = True,
    glass_id: int = 0,
    facade_detail: bool = True,
    style: str | None = None,
    palette: dict[int, str] | None = None,
    use_knowledge: bool = True,
    role_materials: dict[str, int] | None = None,
) -> tuple[np.ndarray, list[str]]:
    """Stronger shell continuity + ring floor slabs + cheap roof tidy.

    - Perimeter wall filled (optional 1-block thickness inward).
    - With preserve_windows (default): keep window-like openings; fill only
      tiny/irregular perimeter defects. Optionally place glass in openings.
    - With preserve_windows=False: fill-all (legacy strong shell).
    - Floors at regular Y spacing as walkable rings (not full footprint fill).
    - Roof cap + single-cell dip fill; trim lonely eaves spikes.
    """
'''
    if old_sig not in text:
        raise SystemExit("harden_shell_and_floors sig not found")
    text = text.replace(old_sig, new_sig, 1)

    old_floor_loop = '''    # --- regular flat floor slabs ---
    floor_added = 0
    floor_fixed = 0
    ax, az = np.where(active)
    peak_set = set(int(y) for y in peaks)
    for y in peaks:
        for x, z in zip(ax.tolist(), az.tolist()):
            cur = int(out[x, y, z])
            if cur == 0:
                out[x, y, z] = int(floor_id)
                floor_added += 1
            elif _cell_is_nonstructural_mass(cur) and not _cell_is_glass(cur):
                out[x, y, z] = int(floor_id)
                floor_fixed += 1
            if clear_interior_clutter and y + 1 < sy and y + 1 < y1:
                above = int(out[x, y + 1, z])
                if (
                    above != 0
                    and _cell_is_nonstructural_mass(above)
                    and not peri[x, z]
                    and not _cell_is_glass(above)
                ):
                    out[x, y + 1, z] = 0
    if floor_added or floor_fixed:
        actions.append(
            "flat_floors:+%d/~%d@y=%s" % (floor_added, floor_fixed, peaks)
        )
'''
    new_floor_loop = '''    # --- regular floor slabs (ring / edge by default so rooms stay open) ---
    floor_added = 0
    floor_fixed = 0
    floor_cleared = 0
    peak_set = set(int(y) for y in peaks)
    # Dilate perimeter into a walkable ring inside active footprint
    ring = peri.copy()
    if hollow_floors and active.any():
        xs_p, zs_p = np.where(peri & active)
        for x, z in zip(xs_p.tolist(), zs_p.tolist()):
            for dx in (-2, -1, 0, 1, 2):
                for dz in (-2, -1, 0, 1, 2):
                    xx, zz = x + dx, z + dz
                    if 0 <= xx < sx and 0 <= zz < sz and active[xx, zz]:
                        ring[xx, zz] = True
        # thin cross corridor for reachability
        axs, azs = np.where(active)
        if axs.size:
            cx = int(round(float(axs.mean())))
            cz = int(round(float(azs.mean())))
            for x, z in zip(axs.tolist(), azs.tolist()):
                if abs(x - cx) <= 0 or abs(z - cz) <= 0:
                    ring[x, z] = True
        ring &= active
        floor_mask = ring
        actions.append("hollow_floors:ring")
    else:
        floor_mask = active
        actions.append("hollow_floors:off")
    ax, az = np.where(floor_mask)
    for y in peaks:
        for x, z in zip(ax.tolist(), az.tolist()):
            cur = int(out[x, y, z])
            if cur == 0:
                out[x, y, z] = int(floor_id)
                floor_added += 1
            elif _cell_is_nonstructural_mass(cur) and not _cell_is_glass(cur):
                out[x, y, z] = int(floor_id)
                floor_fixed += 1
            if clear_interior_clutter and y + 1 < sy and y + 1 < y1:
                above = int(out[x, y + 1, z])
                if (
                    above != 0
                    and _cell_is_nonstructural_mass(above)
                    and not peri[x, z]
                    and not _cell_is_glass(above)
                ):
                    out[x, y + 1, z] = 0
        # Carve center of full slabs left by older scaffolds (open the room)
        if hollow_floors and active.any():
            axs2, azs2 = np.where(active & (~floor_mask))
            for x, z in zip(axs2.tolist(), azs2.tolist()):
                if peri[x, z]:
                    continue
                cur = int(out[x, y, z])
                if cur == int(floor_id) or (
                    cur > 0 and _cell_is_nonstructural_mass(cur) and not _cell_is_glass(cur)
                ):
                    # keep ground-ish foundation band denser near y0
                    if y <= y0:
                        continue
                    out[x, y, z] = 0
                    floor_cleared += 1
    if floor_added or floor_fixed or floor_cleared:
        actions.append(
            "flat_floors:+%d/~%d/-%d@y=%s" % (floor_added, floor_fixed, floor_cleared, peaks)
        )
'''
    if old_floor_loop not in text:
        raise SystemExit("floor loop not found in look_harden")
    text = text.replace(old_floor_loop, new_floor_loop, 1)

    # Wire hollow_floors through look_harden -> harden_shell_and_floors
    old_call = '''            out, geo = harden_shell_and_floors(
                out,
                wall_id=wall_id,
                floor_id=floor_id,
                floor_spacing=int(floor_spacing),
                shell_thickness=int(shell_thickness),
                fill_wall_holes=bool(fill_wall_holes),
                regular_floors=bool(regular_floors),
                smooth_roof=bool(smooth_roof),
                preserve_windows=bool(preserve_windows),
                place_window_glass=bool(place_window_glass),
                glass_id=int(glass_id),
                facade_detail=bool(facade_detail),
                style=style,
                palette=palette,
                use_knowledge=bool(use_knowledge),
                role_materials={
                    "wall": int(wall_id),
                    "floor": int(floor_id),
                    "roof": int(roof_id),
                    "foundation": int(foundation_id),
                    "accent": int(accent_id),
                    "window_frame": int(fill_info.get("window_frame_id") or accent_id),
                },
            )
'''
    new_call = '''            out, geo = harden_shell_and_floors(
                out,
                wall_id=wall_id,
                floor_id=floor_id,
                floor_spacing=int(floor_spacing),
                shell_thickness=int(shell_thickness),
                fill_wall_holes=bool(fill_wall_holes),
                regular_floors=bool(regular_floors),
                hollow_floors=True,
                smooth_roof=bool(smooth_roof),
                preserve_windows=bool(preserve_windows),
                place_window_glass=bool(place_window_glass),
                glass_id=int(glass_id),
                facade_detail=bool(facade_detail),
                style=style,
                palette=palette,
                use_knowledge=bool(use_knowledge),
                role_materials={
                    "wall": int(wall_id),
                    "floor": int(floor_id),
                    "roof": int(roof_id),
                    "foundation": int(foundation_id),
                    "accent": int(accent_id),
                    "window_frame": int(fill_info.get("window_frame_id") or accent_id),
                },
            )
'''
    if old_call not in text:
        raise SystemExit("look_harden call not found")
    text = text.replace(old_call, new_call, 1)

    # Soften dense european wall piers slightly when they fight hollowness (prefer openings)
    # bump european pier spacing 3 -> 4 if present
    text2 = text
    # Find european place_wall_piers spacing
    import re
    # manual: european block wall_pier_spacing": 3 -> 4
    # Only first european occurrence after "european"
    idx = text.find('"european"')
    if idx < 0:
        idx = text.find("'european'")
    if idx >= 0:
        chunk = text[idx : idx + 500]
        if '"wall_pier_spacing": 3' in chunk:
            text = text[:idx] + chunk.replace('"wall_pier_spacing": 3', '"wall_pier_spacing": 4', 1) + text[idx + 500 :]
            print("widened european wall_pier_spacing 3->4")

    path.write_text(text, encoding="utf-8")
    print("patched", path)


def patch_structure() -> None:
    path = ROOT / "src" / "app" / "structure_constraints.py"
    text = path.read_text(encoding="utf-8")

    if "max_enclosed_air_cc" not in text:
        insert_after = "def _hollow_metrics(solid: np.ndarray) -> dict[str, float]:"
        # Find end of _hollow_metrics function - insert new function after it
        idx = text.find(insert_after)
        if idx < 0:
            raise SystemExit("hollow_metrics not found")
        # find next def after this one
        next_def = text.find("\ndef _floor_metrics", idx)
        if next_def < 0:
            raise SystemExit("floor_metrics not found after hollow")
        helper = '''

def _enclosed_air_metrics(solid: np.ndarray) -> dict[str, Any]:
    """Largest enclosed air cavity (air not reachable from the volume border).

    Full floor slabs / interior posts fragment rooms; max_enclosed_air_cc is the
    house-like open-room signal that hollow_score alone misses.
    """
    solid = np.asarray(solid, dtype=bool)
    sx, sy, sz = solid.shape
    air = ~solid
    if not air.any():
        return {
            "max_enclosed_air_cc": 0,
            "enclosed_air_total": 0,
            "enclosed_air_ccs": 0,
            "exterior_air_cells": 0,
        }
    exterior = np.zeros(solid.shape, dtype=bool)
    q: deque[tuple[int, int, int]] = deque()
    # seed all border air
    for x in range(sx):
        for y in range(sy):
            for z in (0, sz - 1):
                if air[x, y, z] and not exterior[x, y, z]:
                    exterior[x, y, z] = True
                    q.append((x, y, z))
        for z in range(sz):
            for y in (0, sy - 1):
                if air[x, y, z] and not exterior[x, y, z]:
                    exterior[x, y, z] = True
                    q.append((x, y, z))
    for y in range(sy):
        for z in range(sz):
            for x in (0, sx - 1):
                if air[x, y, z] and not exterior[x, y, z]:
                    exterior[x, y, z] = True
                    q.append((x, y, z))
    neigh = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    while q:
        x, y, z = q.popleft()
        for dx, dy, dz in neigh:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz:
                if air[nx, ny, nz] and not exterior[nx, ny, nz]:
                    exterior[nx, ny, nz] = True
                    q.append((nx, ny, nz))
    enclosed = air & (~exterior)
    if not enclosed.any():
        return {
            "max_enclosed_air_cc": 0,
            "enclosed_air_total": 0,
            "enclosed_air_ccs": 0,
            "exterior_air_cells": int(exterior.sum()),
        }
    n_cc, sizes, _ = _connected_components(enclosed)
    return {
        "max_enclosed_air_cc": int(sizes[0]) if sizes else 0,
        "enclosed_air_total": int(enclosed.sum()),
        "enclosed_air_ccs": int(n_cc),
        "exterior_air_cells": int(exterior.sum()),
    }


def _floor_cover_metrics(solid: np.ndarray) -> dict[str, Any]:
    """Mean footprint fill at detected floor Y peaks (1.0 = solid slab)."""
    floors = _floor_metrics(solid)
    peaks = list(floors.get("y_peaks") or [])
    fp, fp_n = _footprint(solid)
    if fp_n <= 0 or not peaks:
        return {"floor_cover_mean": 0.0, "floor_cover_per_y": {}, "floor_ys": []}
    per: dict[str, float] = {}
    scores: list[float] = []
    for y in peaks:
        y = int(y)
        if y < 0 or y >= solid.shape[1]:
            continue
        filled = int((solid[:, y, :] & fp).sum())
        cov = float(filled) / float(fp_n)
        per[str(y)] = round(cov, 4)
        scores.append(cov)
    return {
        "floor_cover_mean": float(sum(scores) / len(scores)) if scores else 0.0,
        "floor_cover_per_y": per,
        "floor_ys": [int(y) for y in peaks],
    }

'''
        # Note: _floor_cover_metrics calls _floor_metrics and _footprint which are defined
        # later — need to place _enclosed_air after _floor_metrics/_footprint OR inline carefully.
        # Safer: insert _enclosed_air_metrics before _floor_metrics (only uses _connected_components),
        # and insert _floor_cover_metrics after _footprint.
        text = text[:next_def] + helper.split("def _floor_cover_metrics")[0] + text[next_def:]

    # Insert floor_cover after _footprint definition
    if "def _floor_cover_metrics" not in text:
        fp_anchor = "def _elevated_footprint(solid: np.ndarray)"
        idx = text.find(fp_anchor)
        if idx < 0:
            raise SystemExit("elevated_footprint not found")
        cover_fn = '''
def _floor_cover_metrics(solid: np.ndarray) -> dict[str, Any]:
    """Mean footprint fill at detected floor Y peaks (1.0 = solid slab)."""
    floors = _floor_metrics(solid)
    peaks = list(floors.get("y_peaks") or [])
    fp, fp_n = _footprint(solid)
    if fp_n <= 0 or not peaks:
        return {"floor_cover_mean": 0.0, "floor_cover_per_y": {}, "floor_ys": []}
    per: dict[str, float] = {}
    scores: list[float] = []
    for y in peaks:
        y = int(y)
        if y < 0 or y >= solid.shape[1]:
            continue
        filled = int((solid[:, y, :] & fp).sum())
        cov = float(filled) / float(fp_n)
        per[str(y)] = round(cov, 4)
        scores.append(cov)
    return {
        "floor_cover_mean": float(sum(scores) / len(scores)) if scores else 0.0,
        "floor_cover_per_y": per,
        "floor_ys": [int(y) for y in peaks],
    }


'''
        text = text[:idx] + cover_fn + text[idx:]

    # Wire into compute_structure_metrics
    old_compute = '''def compute_structure_metrics(voxels: np.ndarray) -> dict[str, Any]:
'''
    # find the return/build section
    old_block = '''    hollow = _hollow_metrics(solid)
    floors = _floor_metrics(solid)
    roof = _roof_score(solid)
    _fp, fp_n = _footprint(solid)
'''
    new_block = '''    hollow = _hollow_metrics(solid)
    floors = _floor_metrics(solid)
    roof = _roof_score(solid)
    _fp, fp_n = _footprint(solid)
    enclosed = _enclosed_air_metrics(solid)
    floor_cover = _floor_cover_metrics(solid)
'''
    if old_block not in text:
        raise SystemExit("compute metrics block not found")
    text = text.replace(old_block, new_block, 1)

    # Find where metrics dict is assembled
    # Read a bit more
    marker = '**hollow,'
    if marker not in text:
        # try alternate
        idx = text.find("hollow = _hollow_metrics")
        print("DEBUG around compute:", text[idx:idx+800])
        raise SystemExit("hollow expand marker missing")

    # Expand return dict - find pattern after **hollow
    old_ret = '''    return {
        "non_air": non_air,
        "non_air_frac": float(non_air) / float(vox.size) if vox.size else 0.0,
        "n_cc": int(n_cc),
        "largest_cc": int(sizes[0]) if sizes else 0,
        "largest_cc_frac": float(sizes[0]) / float(non_air) if non_air and sizes else 0.0,
        **hollow,
        **floors,
        **roof,
        "footprint": int(fp_n),
    }
'''
    # might differ - search flexibly
    if old_ret not in text:
        # try to find return in compute_structure_metrics
        start = text.find("def compute_structure_metrics")
        end = text.find("\ndef check_structure", start)
        chunk = text[start:end]
        print("COMPUTE CHUNK:\n", chunk[-600:])
        # build replacement from actual content
        if '"footprint": int(fp_n),' in chunk and "**enclosed" not in chunk:
            text = text[:start] + chunk.replace(
                '"footprint": int(fp_n),',
                '"footprint": int(fp_n),\n        **enclosed,\n        **floor_cover,',
                1,
            ) + text[end:]
        else:
            raise SystemExit("could not wire enclosed into return")
    else:
        text = text.replace(
            old_ret,
            old_ret.replace(
                '"footprint": int(fp_n),\n    }',
                '"footprint": int(fp_n),\n        **enclosed,\n        **floor_cover,\n    }',
            ),
            1,
        )

    # Soft scaffold gate
    old_th = '''SCAFFOLD_THRESHOLDS: dict[str, float] = {
    **DEFAULT_THRESHOLDS,
    "min_exterior_solid_frac": 0.0,  # volume-box faces; centered scaffolds often 0
    "min_roof_score": 0.18,
    "min_hollow_score": 0.28,
    "min_largest_cc_frac": 0.35,
    "min_non_air": 80,
}
'''
    new_th = '''SCAFFOLD_THRESHOLDS: dict[str, float] = {
    **DEFAULT_THRESHOLDS,
    "min_exterior_solid_frac": 0.0,  # volume-box faces; centered scaffolds often 0
    "min_roof_score": 0.18,
    "min_hollow_score": 0.30,
    "min_largest_cc_frac": 0.35,
    "min_non_air": 80,
    # Soft house-likeness: prefer a real enclosed room (advisory hard-fail below)
    "min_max_enclosed_air_cc": 120,
    "max_floor_cover_mean": 0.72,
}
'''
    if old_th not in text:
        raise SystemExit("SCAFFOLD_THRESHOLDS not found")
    text = text.replace(old_th, new_th, 1)

    # check_structure reasons
    old_check_tail = '''    if m["hollow_score"] < th["min_hollow_score"]:
'''
    # Find check_structure and add after hollow check
    start = text.find("def check_structure")
    end = text.find("\ndef _mode_solid_id", start)
    chunk = text[start:end]
    if "min_max_enclosed_air_cc" not in chunk:
        needle = 'if m["hollow_score"] < th["min_hollow_score"]:'
        pos = chunk.find(needle)
        if pos < 0:
            raise SystemExit("hollow check not in check_structure")
        # find end of that if block (next if)
        rest = chunk[pos:]
        next_if = rest.find('\n    if m["exterior_solid_frac"]')
        if next_if < 0:
            next_if = rest.find("\n    if m[")
        insert = '''    if m["hollow_score"] < th["min_hollow_score"]:
        reasons.append(
            "内部不空 hollow=%.2f<%s" % (m["hollow_score"], th["min_hollow_score"])
        )
    max_enc = float(th.get("min_max_enclosed_air_cc") or 0)
    if max_enc > 0 and float(m.get("max_enclosed_air_cc") or 0) < max_enc:
        reasons.append(
            "房间空腔过小 max_enclosed=%s<%s"
            % (int(m.get("max_enclosed_air_cc") or 0), int(max_enc))
        )
    max_fc = float(th.get("max_floor_cover_mean") or 0)
    if max_fc > 0 and float(m.get("floor_cover_mean") or 0) > max_fc:
        reasons.append(
            "楼板过满 floor_cover=%.2f>%s" % (float(m.get("floor_cover_mean") or 0), max_fc)
        )
'''
        # Replace the hollow if block start through before exterior check
        # Simpler: just insert before exterior_solid check
        ext = 'if m["exterior_solid_frac"] < th["min_exterior_solid_frac"]:'
        if ext not in chunk:
            # insert before return
            ret = "return StructureReport"
            chunk2 = chunk.replace(
                ret,
                '''    max_enc = float(th.get("min_max_enclosed_air_cc") or 0)
    if max_enc > 0 and float(m.get("max_enclosed_air_cc") or 0) < max_enc:
        reasons.append(
            "房间空腔过小 max_enclosed=%s<%s"
            % (int(m.get("max_enclosed_air_cc") or 0), int(max_enc))
        )
    max_fc = float(th.get("max_floor_cover_mean") or 0)
    if max_fc > 0 and float(m.get("floor_cover_mean") or 0) > max_fc:
        reasons.append(
            "楼板过满 floor_cover=%.2f>%s" % (float(m.get("floor_cover_mean") or 0), max_fc)
        )
    ''' + ret,
                1,
            )
            text = text[:start] + chunk2 + text[end:]
        else:
            chunk2 = chunk.replace(
                ext,
                '''max_enc = float(th.get("min_max_enclosed_air_cc") or 0)
    if max_enc > 0 and float(m.get("max_enclosed_air_cc") or 0) < max_enc:
        reasons.append(
            "房间空腔过小 max_enclosed=%s<%s"
            % (int(m.get("max_enclosed_air_cc") or 0), int(max_enc))
        )
    max_fc = float(th.get("max_floor_cover_mean") or 0)
    if max_fc > 0 and float(m.get("floor_cover_mean") or 0) > max_fc:
        reasons.append(
            "楼板过满 floor_cover=%.2f>%s" % (float(m.get("floor_cover_mean") or 0), max_fc)
        )
    if m["exterior_solid_frac"] < th["min_exterior_solid_frac"]:''',
                1,
            )
            text = text[:start] + chunk2 + text[end:]

    path.write_text(text, encoding="utf-8")
    print("patched", path)


if __name__ == "__main__":
    patch_gen_strategy()
    patch_look_harden()
    patch_structure()
    print("ALL OK")
