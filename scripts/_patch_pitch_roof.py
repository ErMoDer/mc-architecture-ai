# -*- coding: utf-8 -*-
"""Widen medieval/fantasy ridge plateau + cap rise (look_harden + scaffold gable)."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- look_harden.harden_roof_silhouette ---
LH = ROOT / "src/app/look_harden.py"
lh = LH.read_text(encoding="utf-8")

OLD_RISE = """    rise_max = max(2, int(rules.get("roof_rise_max", 5)))
    rise_min = max(2, int(rules.get("roof_rise_min", 2)))
    rise = int(min(rise_max, max(rise_min, half)))
    # eave / wall-top stays near y1 - rise; peak at y1 (may extend if room)
    peak_y = int(min(sy - 1, y1))
"""

NEW_RISE = """    rise_max = max(2, int(rules.get("roof_rise_max", 5)))
    rise_min = max(2, int(rules.get("roof_rise_min", 2)))
    rise = int(min(rise_max, max(rise_min, half)))
    # Medieval/fantasy: milder low-pitch (cap rise) so ridge plateau can own more of
    # the elevated footprint at y_max — raises roof_score without flat-deck wipe.
    if key in ("medieval", "fantasy"):
        rise = int(min(3, max(2, min(rise, max(2, half // 3)))))
    # eave / wall-top stays near y1 - rise; peak at y1 (may extend if room)
    peak_y = int(min(sy - 1, y1))
"""

OLD_PLAT = """    # Broad ridge plateau so top_footprint_cover / roof_score are not needle-thin
    plateau = max(1, int(0.32 * max(1, half)))
"""

NEW_PLAT = """    # Broad ridge plateau so top_footprint_cover / roof_score are not needle-thin.
    # Medieval/fantasy: wider plateau (~0.72 of half) — still visibly pitched on the
    # outer ~28%% slope, but cover/roof_score leave the ~0.72-0.77 stall.
    if key in ("medieval", "fantasy"):
        plateau = max(2, int(0.72 * max(1, half)))
    else:
        plateau = max(1, int(0.32 * max(1, half)))
"""

if "if key in (\"medieval\", \"fantasy\"):\n        rise = int(min(3," in lh:
    print("look_harden rise already patched")
else:
    if OLD_RISE not in lh:
        raise SystemExit("look_harden rise block missing")
    lh = lh.replace(OLD_RISE, NEW_RISE, 1)
    print("look_harden rise patched")

if "0.72 * max(1, half)" in lh and 'key in ("medieval", "fantasy")' in lh:
    # may already have plateau from partial; check
    if OLD_PLAT in lh:
        lh = lh.replace(OLD_PLAT, NEW_PLAT, 1)
        print("look_harden plateau patched")
    elif "plateau = max(2, int(0.72" in lh:
        print("look_harden plateau already patched")
    else:
        raise SystemExit("look_harden plateau ambiguous")
else:
    if OLD_PLAT not in lh:
        raise SystemExit("look_harden plateau block missing")
    lh = lh.replace(OLD_PLAT, NEW_PLAT, 1)
    print("look_harden plateau patched")

LH.write_text(lh, encoding="utf-8")
ast.parse(lh)
print("look_harden ast ok")

# --- gen_strategy scaffold medieval/fantasy gable ---
GS = ROOT / "src/app/gen_strategy.py"
gs = GS.read_text(encoding="utf-8")

OLD_GABLE = """            rise = int(min(4, max(2, max_rise + 1)))
            ridge_z = (minz + maxz) / 2.0
            ridge_x = (minx + maxx) / 2.0
            plateau = max(1, int(0.35 * half))
"""

NEW_GABLE = """            # Mild low gable: match look_harden medieval/fantasy plateau/rise
            rise = int(min(3, max(2, max_rise + 1)))
            ridge_z = (minz + maxz) / 2.0
            ridge_x = (minx + maxx) / 2.0
            plateau = max(2, int(0.72 * half))
"""

if "0.72 * half" in gs and "Mild low gable" in gs:
    print("scaffold gable already patched")
else:
    if OLD_GABLE not in gs:
        raise SystemExit("scaffold gable block missing")
    gs = gs.replace(OLD_GABLE, NEW_GABLE, 1)
    print("scaffold gable patched")

# rule_scaffold_voxels gable (procedural box) — keep in sync
OLD_RULE = """    # Roof deck at y1 + broad low gable (plateau near ridge)
    out[x0:x1, y1, z0:z1] = int(roof_id)
    half = max(1, min(bw, bd) // 2)
    rise = min(3, max(2, half // 2))
    plateau = max(1, int(0.35 * half))
"""

NEW_RULE = """    # Roof deck at y1 + broad low gable (plateau near ridge; match pitched harden)
    out[x0:x1, y1, z0:z1] = int(roof_id)
    half = max(1, min(bw, bd) // 2)
    rise = min(3, max(2, half // 3))
    plateau = max(2, int(0.72 * half))
"""

if "0.72 * half" in gs and "match pitched harden" in gs:
    print("rule_scaffold gable already patched")
elif OLD_RULE in gs:
    gs = gs.replace(OLD_RULE, NEW_RULE, 1)
    print("rule_scaffold gable patched")
else:
    print("WARN rule_scaffold gable block not found (ok if unused path)")

GS.write_text(gs, encoding="utf-8")
ast.parse(gs)
print("gen_strategy ast ok")
print("DONE pitch_roof patch")
