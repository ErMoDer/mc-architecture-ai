# -*- coding: utf-8 -*-
"""Strengthen scaffold shell / floors / roof in gen_strategy.scaffold_from_occupancy."""
from __future__ import annotations

from pathlib import Path

PATH = Path("src/app/gen_strategy.py")
text = PATH.read_text(encoding="utf-8")

HELPERS = '''
def _normalize_story_floors(
    candidates: list[int] | None,
    *,
    y0: int,
    y_roof: int,
    spacing: int = 5,
    min_gap: int = 3,
    max_stories: int = 5,
) -> list[int]:
    """Regular story slabs: spacing rhythm, no roof slab, capped story count.

    Ref y_peaks are hints only — dense irregular peaks were painting a floor every
    3 cells (industrial) and thickening interiors.
    """
    y0 = int(y0)
    y_roof = int(y_roof)
    if y_roof <= y0 + 1:
        return [y0]
    sp = max(3, int(spacing))
    gap = max(2, int(min_gap))
    # Prefer even grid from foundation up to just under roof deck
    grid = list(range(y0, y_roof, sp))
    if y0 not in grid:
        grid.insert(0, y0)
    # Merge nearby ref peaks onto grid (tolerance), ignore roof-level peaks
    peaks = sorted({int(y) for y in (candidates or []) if y0 < int(y) < y_roof - 1})
    merged = list(grid)
    for p in peaks:
        if min(abs(p - g) for g in merged) >= max(gap, sp // 2):
            merged.append(p)
    merged = sorted(set(merged))
    # Enforce min gap
    out: list[int] = []
    for y in merged:
        if out and y - out[-1] < gap:
            continue
        if y >= y_roof:
            continue
        out.append(y)
    if y0 not in out:
        out = [y0] + out
    # Cap stories (keep ground + evenly subsample upper)
    if len(out) > int(max_stories):
        keep = [out[0]]
        rest = out[1:]
        n = int(max_stories) - 1
        if n <= 0:
            return [out[0]]
        idxs = [int(round(i * (len(rest) - 1) / max(1, n - 1))) for i in range(n)] if len(rest) > 1 else list(range(min(n, len(rest))))
        for i in idxs:
            if 0 <= i < len(rest) and rest[i] not in keep:
                keep.append(rest[i])
        out = sorted(set(keep))[: int(max_stories)]
        if y0 not in out:
            out = [y0] + out
    return out or [y0]


def _seal_shell_columns(
    out: np.ndarray,
    *,
    peri: np.ndarray,
    y0: int,
    y1: int,
    wall_id: int,
    foundation_id: int,
) -> int:
    """Fill air gaps on perimeter columns so the shell is continuous up to roof deck."""
    sx, sy, sz = out.shape
    added = 0
    y0 = int(y0)
    y1 = int(min(y1, sy - 1))
    if y1 <= y0:
        return 0
    px, pz = np.where(peri)
    for x, z in zip(px.tolist(), pz.tolist()):
        for y in range(y0, y1 + 1):
            if out[x, y, z] != 0:
                continue
            # Only seal if neighbors above/below (or both sides) suggest a wall hole
            below = y > y0 and out[x, y - 1, z] != 0
            above = y < y1 and out[x, y + 1, z] != 0
            side = False
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, zz = x + dx, z + dz
                if 0 <= xx < sx and 0 <= zz < sz and peri[xx, zz] and out[xx, y, zz] != 0:
                    side = True
                    break
            if below or above or side or y == y0:
                out[x, y, z] = int(foundation_id) if y <= y0 else int(wall_id)
                added += 1
    return added

'''

# Insert helpers before scaffold_from_occupancy
anchor = "def scaffold_from_occupancy("
if "_normalize_story_floors" not in text:
    if anchor not in text:
        raise SystemExit("scaffold_from_occupancy missing")
    text = text.replace(anchor, HELPERS + anchor, 1)
    print("helpers inserted")
else:
    print("helpers exist")

# Replace floor_ys scheduling block inside scaffold_from_occupancy
OLD_FLOORS = '''    if not floor_ys:
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
'''

NEW_FLOORS = '''    # Story slabs: regularize ref peaks (avoid floor every 3 cells) and never paint roof as floor
    floor_ys = _normalize_story_floors(
        floor_ys,
        y0=int(y_foundation),
        y_roof=int(roof_deck_y),
        spacing=5,
        min_gap=3,
        max_stories=5,
    )
    stats["floor_ys"] = floor_ys
'''

if OLD_FLOORS not in text:
    raise SystemExit("OLD_FLOORS missing")
text = text.replace(OLD_FLOORS, NEW_FLOORS, 1)

# Soften sparse floor fill: only ground story uses roof_fp fill; upper stories keep build slice
OLD_FLOOR_PAINT = '''        if y in floor_ys and build_fp.any():
            use_fp = floor_mask if floor_mask.any() else build_fp
            # For sparse outlines, fill floor with roof_fp interior so rooms aren't empty rings
            if sparse_fp and roof_fp is not None and int(roof_fp.sum()) > int(use_fp.sum()):
                use_fp = roof_fp
            out[:, y, :][use_fp] = int(floor_id)
            out[:, y, :][peri] = peri_block
            stats["floors"] += int(use_fp.sum())
'''

NEW_FLOOR_PAINT = '''        if y in floor_ys and build_fp.any():
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

if OLD_FLOOR_PAINT not in text:
    raise SystemExit("OLD_FLOOR_PAINT missing")
text = text.replace(OLD_FLOOR_PAINT, NEW_FLOOR_PAINT, 1)

# After roof deck block, before corner accents: seal shell + optional pitched ridge
OLD_ACCENT = '''    # Corner accents on wall height (not roof / foundation)
    if build_fp.any() and int(accent_id) > 0 and int(accent_id) != int(wall_id):
'''

NEW_BEFORE_ACCENT = '''    # Seal perimeter shell gaps (continuous walls under deck)
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

    # Medieval / fantasy: broad low gable on top of deck (flat-deck styles keep plateau only)
    if (
        build_fp.any()
        and 0 <= roof_deck_y < sy
        and style_l in ("medieval", "fantasy")
    ):
        use_roof_fp = roof_fp if roof_fp is not None and roof_fp.any() else build_fp
        xs, zs = np.where(use_roof_fp)
        if xs.size:
            minx, maxx = int(xs.min()), int(xs.max())
            minz, maxz = int(zs.min()), int(zs.max())
            wx, wz = maxx - minx + 1, maxz - minz + 1
            ridge_along_x = wx >= wz
            half = max(1, (wz // 2) if ridge_along_x else (wx // 2))
            rise = int(min(4, max(2, max_rise + 1)))
            ridge_z = (minz + maxz) / 2.0
            ridge_x = (minx + maxx) / 2.0
            plateau = max(1, int(0.35 * half))
            gable_n = 0
            for x, z in zip(xs.tolist(), zs.tolist()):
                dist = abs(float(z) - ridge_z) if ridge_along_x else abs(float(x) - ridge_x)
                if dist <= plateau:
                    h = int(min(sy - 1, roof_deck_y + rise))
                else:
                    t = (dist - plateau) / max(1e-6, (half - plateau))
                    h = int(min(sy - 1, roof_deck_y + max(0, int(round(rise * (1.0 - t))))))
                for yy in range(int(roof_deck_y) + 1, h + 1):
                    if out[x, yy, z] == 0 or out[x, yy, z] == int(roof_id):
                        out[x, yy, z] = int(roof_id)
                        gable_n += 1
            if gable_n:
                stats["roof"] = int(stats.get("roof") or 0) + int(gable_n)
                stats["roof_mode"] = "low_pitch_deck+gable"
                stats["gable_rise"] = int(rise)

    # Corner accents on wall height (not roof / foundation)
    if build_fp.any() and int(accent_id) > 0 and int(accent_id) != int(wall_id):
'''

if OLD_ACCENT not in text:
    raise SystemExit("OLD_ACCENT missing")
text = text.replace(OLD_ACCENT, NEW_BEFORE_ACCENT, 1)

# rule_scaffold: spacing 5, no floor at roof, better gable plateau
OLD_RULE = '''    floor_ys = list(range(y0, y1 + 1, 4))
    if y1 not in floor_ys:
        floor_ys.append(y1)

    for y in floor_ys:
        if y >= sy:
            continue
        out[x0:x1, y, z0:z1] = int(floor_id)

    for y in range(y0, min(y1 + 1, sy)):
        block = int(foundation_id) if y == y0 else int(wall_id)
        out[x0:x1, y, z0] = block
        out[x0:x1, y, z1 - 1] = block
        out[x0, y, z0:z1] = block
        out[x1 - 1, y, z0:z1] = block
        # corner accents
        if y > y0 and int(accent_id) != int(wall_id):
            for cx, cz in ((x0, z0), (x0, z1 - 1), (x1 - 1, z0), (x1 - 1, z1 - 1)):
                out[cx, y, cz] = int(accent_id)

    ridge = y1
    for t in range(0, max(1, bw // 2)):
        yy = min(sy - 1, ridge + t)
        xx0 = x0 + t
        xx1 = x1 - t
        if xx0 >= xx1:
            break
        out[xx0:xx1, yy, z0:z1] = int(roof_id)
'''

NEW_RULE = '''    floor_ys = _normalize_story_floors(
        None, y0=y0, y_roof=y1, spacing=5, min_gap=3, max_stories=4
    )

    for y in floor_ys:
        if y >= sy or y >= y1:
            continue
        out[x0:x1, y, z0:z1] = int(floor_id)

    for y in range(y0, min(y1 + 1, sy)):
        block = int(foundation_id) if y == y0 else int(wall_id)
        out[x0:x1, y, z0] = block
        out[x0:x1, y, z1 - 1] = block
        out[x0, y, z0:z1] = block
        out[x1 - 1, y, z0:z1] = block
        # corner accents
        if y > y0 and int(accent_id) != int(wall_id):
            for cx, cz in ((x0, z0), (x0, z1 - 1), (x1 - 1, z0), (x1 - 1, z1 - 1)):
                out[cx, y, cz] = int(accent_id)

    # Roof deck at y1 + broad low gable (plateau near ridge)
    out[x0:x1, y1, z0:z1] = int(roof_id)
    half = max(1, min(bw, bd) // 2)
    rise = min(3, max(2, half // 2))
    plateau = max(1, int(0.35 * half))
    cx = (x0 + x1 - 1) / 2.0
    cz = (z0 + z1 - 1) / 2.0
    ridge_along_x = bw >= bd
    for x in range(x0, x1):
        for z in range(z0, z1):
            dist = abs(float(z) - cz) if ridge_along_x else abs(float(x) - cx)
            if dist <= plateau:
                h = min(sy - 1, y1 + rise)
            else:
                t = (dist - plateau) / max(1e-6, (half - plateau))
                h = min(sy - 1, y1 + max(0, int(round(rise * (1.0 - t)))))
            for yy in range(y1 + 1, h + 1):
                out[x, yy, z] = int(roof_id)
'''

if OLD_RULE not in text:
    raise SystemExit("OLD_RULE missing")
text = text.replace(OLD_RULE, NEW_RULE, 1)

PATH.write_text(text, encoding="utf-8")
import ast
ast.parse(PATH.read_text(encoding="utf-8"))
print("gen_strategy ok", PATH.stat().st_size)
