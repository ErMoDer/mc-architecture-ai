# -*- coding: utf-8 -*-
from pathlib import Path
path = Path("src/app/gen_strategy.py")
text = path.read_text(encoding="utf-8")

old = """            # Hollow house: ring floors (not full footprint) so rooms stay open
            depth = 2 if y == y_foundation else 1
            use_fp = _ring_floor_mask(use_fp, depth=depth, keep_cross=False)
"""
new = """            # Hollow house: ring floors (not full footprint) so rooms stay open
            # Medieval/fantasy refs stay dense — keep ring thinner so interior_cover < 0.7
            if style_l in (\"medieval\", \"fantasy\"):
                depth = 1
            else:
                depth = 2 if y == y_foundation else 1
            use_fp = _ring_floor_mask(use_fp, depth=depth, keep_cross=False)
"""
if old not in text:
    raise SystemExit("floor depth block missing")
text = text.replace(old, new, 1)

# Move style_l earlier OR use (style or '').strip().lower() in normalize.
# Currently style_l is set AFTER floor_ys normalize. Reorder: set style_l before floors.
old_order = """    stats[\"roof_deck_y\"] = int(roof_deck_y)

    # Story slabs: regularize ref peaks (avoid floor every 3 cells) and never paint roof as floor
    floor_ys = _normalize_story_floors(
        floor_ys,
        y0=int(y_foundation),
        y_roof=int(roof_deck_y),
        spacing=6,
        min_gap=4,
        max_stories=4,
    )
    stats[\"floor_ys\"] = floor_ys

    style_l = (style or \"\").strip().lower()
"""
new_order = """    stats[\"roof_deck_y\"] = int(roof_deck_y)

    style_l = (style or \"\").strip().lower()
    # Story slabs: regularize ref peaks (avoid floor every 3 cells) and never paint roof as floor
    _max_stories = 3 if style_l in (\"medieval\", \"fantasy\") else 4
    _spacing = 7 if style_l in (\"medieval\", \"fantasy\") else 6
    floor_ys = _normalize_story_floors(
        floor_ys,
        y0=int(y_foundation),
        y_roof=int(roof_deck_y),
        spacing=_spacing,
        min_gap=4,
        max_stories=_max_stories,
    )
    stats[\"floor_ys\"] = floor_ys
"""
if old_order not in text:
    raise SystemExit("floor/style order block missing")
text = text.replace(old_order, new_order, 1)

# Remove duplicate style_l if left
dup = "\n    style_l = (style or \"\").strip().lower()\n    sparse_fp"
if text.count("style_l = (style or \"\").strip().lower()") > 1:
    # keep first; remove second occurrence near sparse_fp
    first = text.find("style_l = (style or \"\").strip().lower()")
    second = text.find("style_l = (style or \"\").strip().lower()", first + 1)
    if second > 0:
        # remove the line
        end = text.find("\n", second)
        text = text[:second] + text[end+1:]
        print("removed duplicate style_l")

path.write_text(text, encoding="utf-8")
import ast
ast.parse(text)
print("ok")
