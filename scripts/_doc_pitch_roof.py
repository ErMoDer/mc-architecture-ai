# -*- coding: utf-8 -*-
"""Append pitch_roof section to docs/look_harden.md and close residual note."""
from __future__ import annotations

from pathlib import Path

DOC = Path("docs/look_harden.md")
text = DOC.read_text(encoding="utf-8")

SECTION = """
## pitch_roof (medieval / fantasy, 2026-10-20)

After `fantasy_glass_dens_20261020_090033`, remaining shortfall was **pitched roof_score ~0.72–0.77** (medieval/fantasy). Metric uses `top_footprint_cover` at absolute `y_max`; look_harden's pitched gable used plateau **0.32×half** + rise≈half (cap 5), so only a thin ridge hit `y_max` (cover ~0.37–0.49) while wiping scaffold `low_pitch_deck+gable`.

**Fix (pitched styles only — medieval/fantasy):**

| path | knob | before | after |
|---|---|---|---|
| `look_harden.harden_roof_silhouette` | ridge plateau | 0.32×half | **0.72×half** |
| same | rise | min(5, half) | **cap 3** (still ≥2) |
| `gen_strategy` scaffold gable + `rule_scaffold_voxels` | plateau / rise | 0.35×half / ≤4 | **0.72×half / ≤3** |

Flat-deck preserve for rustic/western/european/chinese **unchanged** (want_pitch forced off). Facade dens knobs **unchanged** (fantasy sp4/bands3/c2 pier5; euro 4/3/c3; rustic pier12).

Smoke: `outputs/design/pitch_roof_20261020_090715/` — **5/5** structure_ok.

| style | roof before→after | cover before→after | glass | piers | note |
|---|---|---|---|---|---|
| medieval | 0.750→**0.937** | 0.445→0.860 | 348→344 | 174→183 | pitched kept |
| fantasy | 0.770→**0.967** | 0.490→0.926 | 230→228 | 81→88 | dens held |
| fantasy | 0.718→**0.935** | 0.374→0.855 | 144→138 | 56→33 | glass dens; pier thinner on sparse sample |
| european | 1.000→1.000 | 1.0 | 256 | 109 | flat control |
| rustic | 1.000→1.000 | 1.0 | 168 | 88 | flat control |

**Residual:** scores ~0.93–0.97, not flat 1.0 (outer ~28% still slopes — honest). Sparse fantasy pier cells can dip when eave/peak shift pier column height; spacing knob untouched. Further →1.0 would need near-flat plateau or a top-band cover metric change.

Scripts: `scripts/_patch_pitch_roof.py`, `_run_pitch_roof_smoke.py`.
"""

# Soften prior residual line in fantasy_glass_dens section
OLD_RES = "**Residual:** medieval/fantasy pitched roof_score ~0.72–0.77 still needs a later scaffold pass (not this dens)."
NEW_RES = "**Residual (closed by pitch_roof):** medieval/fantasy pitched roof_score ~0.72–0.77 → see § pitch_roof (plateau 0.72 / rise cap 3)."

if OLD_RES in text:
    text = text.replace(OLD_RES, NEW_RES, 1)
    print("fantasy_glass residual updated")
elif "closed by pitch_roof" in text:
    print("fantasy_glass residual already updated")
else:
    print("WARN fantasy_glass residual line not found")

if "## pitch_roof (medieval / fantasy, 2026-10-20)" in text:
    print("pitch_roof section already present")
else:
    text = text.rstrip() + "\n" + SECTION
    print("pitch_roof section appended")

DOC.write_text(text, encoding="utf-8")
print("docs ok", DOC)
