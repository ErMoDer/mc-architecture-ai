# -*- coding: utf-8 -*-
from pathlib import Path

# Append eave_rooms section to look_harden.md and gen_strategy.md
lh = Path("docs/look_harden.md")
text = lh.read_text(encoding="utf-8")
section = """

## eave_rooms (2026-10-20)

True eaves / pitched **skin** silhouette + simple interior partitions (no VAE).

- **Scaffold** (`gen_strategy`): `skin_gable` for european/rustic/western/chinese/medieval/fantasy — eave **ring** (not full attic slab) + roof surface only + overhang 1–2; industrial/modern keep `flat_eave_deck` + eave lip. Interior mid/L partition (1-thick, doorway). Ring floors + corner load posts kept.
- **look_harden**: stop force-flat on euro/rustic/western/chinese; pitched path is **skin-only** (no solid attic fill). european/rustic `eave_overhang=2`; industrial overhang=1 + cornice.
- Smoke: `scripts/_run_eave_rooms.py` → `outputs/design/eave_rooms_*`; schematics `檐分_*_v26.3`.
- vs `block_struct_20261020_200345`: euro/industrial/rustic room_air up / int_cover down; pitched roof_score ~0.74–0.85 (silhouette tradeoff vs flat 1.0). structure_ok 8/8.

**Residual:** boxy massing; partitions are crude L/mid only; chinese solids still high; roof_score heuristic underrates skin gables.
"""
if "eave_rooms (2026-10-20)" not in text:
    lh.write_text(text.rstrip() + section, encoding="utf-8")
    print("look_harden.md updated")
else:
    print("look_harden.md already has section")

gs = Path("docs/gen_strategy.md")
gt = gs.read_text(encoding="utf-8")
gsec = """

## eave_rooms roof + partitions (2026-10-20)

`scaffold_from_occupancy` roof modes:

| style family | roof_mode | notes |
|---|---|---|
| european / rustic / western / chinese / medieval / fantasy | `skin_gable` | hollow attic; eave ring + overhang; gable-end peri walls under slope |
| industrial / modern | `flat_eave_deck` | flat cover + 1-cell eave lip |

Also: `_place_interior_partitions` (mid wall or L-split, doorway). Medieval/fantasy use thinner ring floors so `interior_cover` stays under scaffold gate.

Helpers: `_gable_rise_map`, `_place_skin_gable_roof`, `_place_interior_partitions`.
Smoke: `scripts/_run_eave_rooms.py`.
"""
if "eave_rooms roof + partitions" not in gt:
    gs.write_text(gt.rstrip() + gsec, encoding="utf-8")
    print("gen_strategy.md updated")
else:
    print("gen_strategy.md already has section")

# knowledge note
kn = Path("docs/mc-knowledge/builds/look_harden_rules.json")
import json
data = json.loads(kn.read_text(encoding="utf-8"))
notes = data.setdefault("notes", [])
if isinstance(notes, list) and not any("eave_rooms" in str(n) for n in notes):
    notes.append("eave_rooms 2026-10-20: skin_gable eaves + interior L/mid partitions; no solid attic fill.")
    kn.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("knowledge updated")
