from pathlib import Path
p = Path("docs/look_harden.md")
text = p.read_text(encoding="utf-8")
note = """

## euro_fan_dens (2026-10-19)

After `full_style_v2_20261019_211250` user picked **压欧式玻璃 / 奇幻壁柱**:

| style | knob | before (v2) | after | aim |
|---|---|---|---|---|
| european | `window_spacing` 3→**4**, `max_window_bands` 4→**3**, `window_from_corner` 2→**3** | glass **448** | ~**256** (smoke) | 200–280 |
| fantasy | `wall_pier_spacing` 3→**5** | piers **221** (000) / 115 (001) | ~**81** / ~**56** | ~60–120 / rustic~90 |

First mid-patch overshot (eu sp5/bands2 → glass~130; fantasy pier12 → ~33); settled on values above.

**Untouched:** modern `window_spacing=6`, industrial `=4`, rustic `wall_pier_spacing=12`, scaffold_struct, flat-deck preserve, doors/windows/eaves generally.

Smoke: `outputs/design/euro_fan_dens_<timestamp>/`.
"""
if "euro_fan_dens (2026-10-19)" not in text:
    p.write_text(text.rstrip() + note, encoding="utf-8")
    print("docs appended")
else:
    print("docs already has note")
