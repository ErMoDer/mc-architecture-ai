# -*- coding: utf-8 -*-
"""Patch 6 house-usable redstone stubs into canonical_templates + bootstrap."""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
if not ROOT.exists():
    ROOT = Path(__file__).resolve().parents[1]

p = ROOT / "src" / "app" / "redstone_templates.py"
text = p.read_text(encoding="utf-8")
needle = '"id": "comparator_chest_read"'
idx = text.find(needle)
if idx < 0:
    raise SystemExit("comparator_chest_read not found")
end = text.find("\n\n\n    ]", idx)
if end < 0:
    raise SystemExit("list end not found")

if "note_block_alert" in text:
    print("already patched canonical_templates")
else:
    stubs = [
        {
            "id": "note_block_alert",
            "matches": ["note_block_alert", "doorbell", "note_alert"],
            "label_zh": "音符盒提示桩（按钮→粉尘→音符盒）",
            "size": [3, 1, 1],
            "blocks_src": [
                '_b(0, 0, 0, "stone_button", face="floor", facing="east")',
                '_b(1, 0, 0, "redstone_wire")',
                '_b(2, 0, 0, "note_block")',
            ],
            "notes": "教学桩：门铃/提示音；非完整音乐机。",
        },
        {
            "id": "dropper_dispenser_pulse",
            "matches": ["dropper_pulse", "dispenser_pulse", "item_spit"],
            "label_zh": "投掷器脉冲桩（按钮→粉尘→投掷器）",
            "size": [3, 1, 1],
            "blocks_src": [
                '_b(0, 0, 0, "stone_button", face="floor", facing="east")',
                '_b(1, 0, 0, "redstone_wire")',
                '_b(2, 0, 0, "dropper", facing="east")',
            ],
            "notes": "教学桩：单次脉冲投掷；可换发射器。",
        },
        {
            "id": "water_stream_item_tiny",
            "matches": ["water_stream", "item_waterway", "water_item_move"],
            "label_zh": "水流运物小桩（源→水→漏斗）",
            "size": [4, 1, 1],
            "blocks_src": [
                '_b(0, 0, 0, "water")',
                '_b(1, 0, 0, "water")',
                '_b(2, 0, 0, "water")',
                '_b(3, 0, 0, "hopper", facing="east")',
            ],
            "notes": "教学桩：极小水流运物入漏斗；需在源处放水桶/冰。",
        },
        {
            "id": "trapped_chest_signal",
            "matches": ["trapped_chest", "chest_trap_signal", "secret_chest"],
            "label_zh": "陷阱箱信号桩（陷阱箱→粉尘→灯）",
            "size": [3, 1, 1],
            "blocks_src": [
                '_b(0, 0, 0, "trapped_chest", facing="south")',
                '_b(1, 0, 0, "redstone_wire")',
                '_b(2, 0, 0, "redstone_lamp")',
            ],
            "notes": "教学桩：打开陷阱箱出信号；非完整陷阱。",
        },
        {
            "id": "daylight_sensor_lamp_stub",
            "matches": ["daylight_lamp", "outdoor_auto_lamp", "daylight_sensor_lamp"],
            "label_zh": "日光传感器夜灯桩（反相日光→粉尘→灯）",
            "size": [3, 1, 1],
            "blocks_src": [
                '_b(0, 0, 0, "daylight_detector", inverted="true")',
                '_b(1, 0, 0, "redstone_wire")',
                '_b(2, 0, 0, "redstone_lamp")',
            ],
            "notes": "教学桩：夜间点灯；与 daylight_clock（正常日光）区分。",
        },
        {
            "id": "pressure_plate_iron_door",
            "matches": ["pressure_door", "plate_door", "auto_iron_door"],
            "label_zh": "压力板铁门桩（石板→粉尘→铁门）",
            "size": [3, 2, 1],
            "blocks_src": [
                '_b(0, 0, 0, "stone_pressure_plate")',
                '_b(1, 0, 0, "redstone_wire")',
                '_b(2, 0, 0, "iron_door", facing="east", half="lower", open="false")',
                '_b(2, 1, 0, "iron_door", facing="east", half="upper", open="false")',
            ],
            "notes": "教学桩：踏板开铁门；非完整自动门系统。",
        },
    ]
    parts = []
    for s in stubs:
        blocks = ",\n                ".join(s["blocks_src"])
        matches = ", ".join(f'"{m}"' for m in s["matches"])
        parts.append(
            f'''        {{
            "id": "{s['id']}",
            "matches": [{matches}],
            "label_zh": "{s['label_zh']}",
            "size": {s['size']},
            "blocks": [
                {blocks},
            ],
            "notes": "{s['notes']}",
        }},
'''
        )
    text = text[:end] + "\n" + "".join(parts) + text[end:]
    p.write_text(text, encoding="utf-8")
    print("patched", len(stubs), "stubs into", p)

sys.path.insert(0, str(ROOT))
from src.app.redstone_templates import canonical_templates, bootstrap_templates

ids = [t["id"] for t in canonical_templates()]
want = [
    "note_block_alert",
    "dropper_dispenser_pulse",
    "water_stream_item_tiny",
    "trapped_chest_signal",
    "daylight_sensor_lamp_stub",
    "pressure_plate_iron_door",
]
print("canonical_n", len(ids))
print("new_present", [i for i in want if i in ids])
root = bootstrap_templates(force=True)
cat = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
print("catalog_n", len(cat.get("templates") or []))
print("ok")
