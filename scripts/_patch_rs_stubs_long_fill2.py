# -*- coding: utf-8 -*-
"""Long fill2: add 6 house-usable indoor RS stubs into canonical + bootstrap. No VAE."""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
if not ROOT.exists():
    ROOT = Path(__file__).resolve().parents[1]

p = ROOT / "src" / "app" / "redstone_templates.py"
text = p.read_text(encoding="utf-8")

WANT = [
    "item_filter_stub",
    "torch_tower_elevator_frag",
    "hopper_clock_xor_alt",
    "lectern_book_signal",
    "target_block_signal",
    "brewing_stand_hopper_stub",
]

if all(w in text for w in WANT):
    print("already patched canonical_templates")
else:
    needle = '"id": "pressure_plate_iron_door"'
    idx = text.find(needle)
    if idx < 0:
        raise SystemExit("pressure_plate_iron_door not found")
    insert_at = text.find("\n\n\n    ]", idx)
    if insert_at < 0:
        insert_at = text.find("\n    ]", idx)
    if insert_at < 0:
        raise SystemExit("list end not found for insert")

    stubs = [
        {
            "id": "item_filter_stub",
            "matches": ["item_filter", "hopper_filter", "sorter_stub"],
            "label_zh": "物品过滤桩（箱→漏斗→侧漏斗+比较器）",
            "size": [3, 2, 2],
            "blocks_src": [
                '_b(0, 1, 0, "chest", facing="south")',
                '_b(0, 0, 0, "hopper", facing="east")',
                '_b(1, 0, 0, "hopper", facing="east")',
                '_b(1, 0, 1, "hopper", facing="south")',
                '_b(1, 1, 1, "comparator", facing="north")',
                '_b(2, 0, 0, "chest", facing="south")',
            ],
            "notes": "教学桩：极简过滤骨架；非完整分类机，需按物品改过滤槽。",
        },
        {
            "id": "torch_tower_elevator_frag",
            "matches": ["torch_tower", "torch_elevator", "vertical_torch_power"],
            "label_zh": "火把塔电梯碎片（竖向火把供电示意）",
            "size": [1, 4, 2],
            "blocks_src": [
                '_b(0, 0, 0, "stone")',
                '_b(0, 1, 0, "stone")',
                '_b(0, 2, 0, "stone")',
                '_b(0, 3, 0, "stone")',
                '_b(0, 0, 1, "redstone_torch")',
                '_b(0, 1, 1, "redstone_torch")',
                '_b(0, 2, 1, "redstone_torch")',
                '_b(0, 3, 1, "redstone_wire")',
            ],
            "notes": "教学桩：竖向火把塔供电碎片；非完整气泡/投掷电梯。",
        },
        {
            "id": "hopper_clock_xor_alt",
            "matches": ["hopper_clock_alt", "xor_hopper_clock", "etho_alt"],
            "label_zh": "漏斗钟交替布局（对吐+侧比较器）",
            "size": [3, 1, 2],
            "blocks_src": [
                '_b(0, 0, 0, "hopper", facing="east")',
                '_b(1, 0, 0, "hopper", facing="west")',
                '_b(2, 0, 0, "comparator", facing="west")',
                '_b(2, 0, 1, "redstone_wire")',
                '_b(1, 0, 1, "redstone_wire")',
                '_b(0, 0, 1, "redstone_lamp")',
            ],
            "notes": "教学桩：与 hopper_clock_basic 不同的输出侧布局；需放物品走钟。",
        },
        {
            "id": "lectern_book_signal",
            "matches": ["lectern_signal", "book_signal", "lectern_comparator"],
            "label_zh": "讲台书信号桩（讲台→比较器→灯）",
            "size": [3, 1, 1],
            "blocks_src": [
                '_b(0, 0, 0, "lectern", facing="south", has_book="true")',
                '_b(1, 0, 0, "comparator", facing="west")',
                '_b(2, 0, 0, "redstone_lamp")',
            ],
            "notes": "教学桩：翻书页改变比较器强度；需放入成书面。",
        },
        {
            "id": "target_block_signal",
            "matches": ["target_block", "target_signal", "archery_signal"],
            "label_zh": "标靶信号桩（标靶→粉尘→灯）",
            "size": [3, 1, 1],
            "blocks_src": [
                '_b(0, 0, 0, "target")',
                '_b(1, 0, 0, "redstone_wire")',
                '_b(2, 0, 0, "redstone_lamp")',
            ],
            "notes": "教学桩：箭/弹射物击中标靶出信号；可作家门铃变体。",
        },
        {
            "id": "brewing_stand_hopper_stub",
            "matches": ["brewing_hopper", "alchemy_feed", "brewing_stand_in"],
            "label_zh": "酿造台进料漏斗桩（箱→漏斗→酿造台）",
            "size": [2, 2, 1],
            "blocks_src": [
                '_b(0, 1, 0, "chest", facing="south")',
                '_b(0, 0, 0, "hopper", facing="east")',
                '_b(1, 0, 0, "brewing_stand")',
            ],
            "notes": "教学桩：屋内炼药进料；非完整自动酿造机。",
        },
    ]
    parts = []
    for s in stubs:
        if s["id"] in text:
            print("skip existing", s["id"])
            continue
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
    if not parts:
        print("nothing to insert")
    else:
        text = text[:insert_at] + "\n" + "".join(parts) + text[insert_at:]
        p.write_text(text, encoding="utf-8")
        print("patched", len(parts), "stubs into", p)

sys.path.insert(0, str(ROOT))
from src.app.redstone_templates import canonical_templates, bootstrap_templates

ids = [t["id"] for t in canonical_templates()]
print("canonical_n", len(ids))
print("new_present", [i for i in WANT if i in ids])
missing = [i for i in WANT if i not in ids]
if missing:
    raise SystemExit(f"missing after patch: {missing}")
root = bootstrap_templates(force=True)
cat = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
print("catalog_n", len(cat.get("templates") or []))
print("ok")
