from pathlib import Path
p = Path("docs/look_harden.md")
text = p.read_text(encoding="utf-8")
if "## full_style_v3" in text:
    print("already has section")
else:
    note = """

## full_style_v3 (2026-10-20)

Full-style similar_scaffold smoke after `euro_fan_dens_20261019_212806` knobs (no code change this run).

- out: `outputs/design/full_style_v3_20261020_085033/`
- structure_ok: **9/9**
- euro/chinese/rustic roof~1: **True**
- vs: `full_style_v2_20261019_211250` (pre dens) + `euro_fan_dens_20261019_212806`

| style | ok | roof | glass v2 -> v3 | piers v2 -> v3 | note |
|---|---|---|---|---|---|
| chinese | True | 1.000 | 242 -> 242 | 25 -> 25 | stable |
| european | True | 1.000 | **448 -> 256** | 60 -> 109 | matches euro_fan_dens; aim 200-280 |
| medieval | True | 0.750 | 348 -> 348 | 174 -> 174 | pitched+gable residual |
| modern | True | 1.000 | 208 -> 208 | 0 -> 0 | glass_dens held |
| rustic | True | 1.000 | 168 -> 168 | 88 -> 88 | pier=12 held |
| rustic | True | 1.000 | 346 -> 346 | 90 -> 90 | second sample |
| fantasy | True | 0.770 | 374 -> 374 | **221 -> 81** | matches euro_fan_dens |
| fantasy | True | 0.718 | 238 -> 238 | **115 -> 56** | matches euro_fan_dens |
| industrial | True | 1.000 | 186 -> 186 | 35 -> 35 | glass_dens held |

**No regression:** eu glass not back near 448; fantasy piers not back near 200+; roofs unchanged vs v2. Previews under that run dir `previews/`.
"""
    p.write_text(text.rstrip() + note, encoding="utf-8")
    print("appended full_style_v3 section")
print("tail check:")
print(p.read_text(encoding="utf-8")[-900:])
