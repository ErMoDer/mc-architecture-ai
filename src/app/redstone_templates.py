# -*- coding: utf-8 -*-
"""Phase 4: redstone principle templates — match analyze patterns and paste snippets.

Does NOT invent circuits with VAE. Templates are hand-authored block placements.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from src.app.schematic_analyze import analyze_litematic
from src.data.litematic import (
    _bits_per_block,
    _pack_block_states,
    load_litematic,
)

try:
    import nbtlib
except ImportError:  # pragma: no cover
    nbtlib = None  # type: ignore


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


TEMPLATES_DIR = "data/redstone_templates"


# ---------------------------------------------------------------------------
# Canonical hand templates (also written to disk by bootstrap_templates)
# ---------------------------------------------------------------------------

def _b(x: int, y: int, z: int, block: str, **props: str) -> dict[str, Any]:
    d: dict[str, Any] = {"x": x, "y": y, "z": z, "block": block if block.startswith("minecraft:") else "minecraft:" + block}
    if props:
        d["props"] = {k: str(v) for k, v in props.items()}
    return d


def canonical_templates() -> list[dict[str, Any]]:
    """Small principle-level snippets (Java-ish). Facing via props when saved."""
    return [
        {
            "id": "hopper_clock_basic",
            "matches": ["hopper_clock", "etho_hopper_clock", "hopper_line"],
            "label_zh": "漏斗钟（对吐+比较器）",
            "confidence_prefer": "high",
            "size": [3, 1, 2],
            "blocks": [
                _b(0, 0, 0, "hopper", facing="east"),
                _b(1, 0, 0, "hopper", facing="west"),
                _b(0, 0, 1, "comparator", facing="south"),
                _b(1, 0, 1, "redstone_wire"),
                _b(2, 0, 1, "redstone_lamp"),
            ],
            "notes": "两漏斗对吐；比较器读满度；粉尘→灯作输出示意。需放入物品才能走钟。",
        },
        {
            "id": "simple_io_lever_lamp",
            "matches": ["simple_io", "lamp_line", "door_line"],
            "label_zh": "杠杆→粉尘→红石灯",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "lever", face="floor", facing="north", powered="false"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "redstone_lamp"),
            ],
            "notes": "最简 IO 示意；门线可把灯换成铁门（本模板保留灯）。",
        },
        {
            "id": "rs_latch_torch",
            "matches": ["rs_latch", "torch_logic_lattice"],
            "label_zh": "RS 锁存（双火把）粗骨架",
            "size": [3, 1, 2],
            "blocks": [
                _b(0, 0, 0, "redstone_torch"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "redstone_torch"),
                _b(0, 0, 1, "redstone_wire"),
                _b(2, 0, 1, "redstone_wire"),
                _b(1, 0, 1, "redstone_block"),
            ],
            "notes": "教学向双火把互锁示意，落地后常需按游戏版微调，非验证真值表。",
        },
        {
            "id": "piston_door_2wide",
            "matches": ["piston_door"],
            "label_zh": "双活塞门（并排）",
            "size": [2, 2, 3],
            "blocks": [
                _b(0, 0, 0, "piston", facing="south"),
                _b(1, 0, 0, "piston", facing="south"),
                _b(0, 1, 0, "piston", facing="south"),
                _b(1, 1, 0, "piston", facing="south"),
                _b(0, 0, 1, "redstone_wire"),
                _b(1, 0, 1, "redstone_wire"),
                _b(0, 0, 2, "lever", face="floor", facing="south"),
                _b(1, 0, 2, "redstone_wire"),
            ],
            "notes": "2×2 活塞排；杠杆供电示意。不含粘活塞收回与门面装修。",
        },
        {
            "id": "sticky_swapper",
            "matches": ["sticky_piston_pair"],
            "label_zh": "粘活塞换块器（红石块）",
            "size": [1, 1, 5],
            "blocks": [
                _b(0, 0, 0, "sticky_piston", facing="south"),
                _b(0, 0, 1, "redstone_block"),
                _b(0, 0, 2, "air"),
                _b(0, 0, 3, "sticky_piston", facing="north"),
                _b(0, 0, 4, "lever", face="floor", facing="west"),
            ],
            "notes": "对置粘活塞夹红石块；需另接时钟（见漏斗钟模板）。空气格为行程留白。",
        },
        {
            "id": "qc_piston_row",
            "matches": ["qc_piston_bank", "zero_tick_bud_freerun"],
            "label_zh": "QC 侧置活塞排（粉尘在上邻）",
            "size": [2, 2, 4],
            "blocks": [
                _b(1, 0, 0, "piston", facing="east"),
                _b(1, 0, 1, "piston", facing="east"),
                _b(1, 0, 2, "piston", facing="east"),
                _b(1, 0, 3, "piston", facing="east"),
                _b(0, 1, 0, "redstone_wire"),
                _b(0, 1, 1, "redstone_wire"),
                _b(0, 1, 2, "redstone_wire"),
                _b(0, 1, 3, "redstone_wire"),
            ],
            "notes": "活塞本体旁上方邻格走粉尘 = Java QC 粗示意；需强充电源，BUD 时序不保证。",
        },
        {
            "id": "torch_clock_basic",
            "matches": ["torch_clock", "torch_burn_clock"],
            "label_zh": "火把钟粗骨架",
            "size": [2, 2, 1],
            "blocks": [
                _b(0, 0, 0, "redstone_wire"),
                _b(1, 0, 0, "repeater", facing="west", delay="1"),
                _b(0, 1, 0, "redstone_torch"),
            ],
            "notes": "易烧毁；仅作原理示意，建议游戏内加中继器档位。",
        },
        {
            "id": "daylight_clock",
            "matches": ["daylight_detector_clock"],
            "label_zh": "日光传感器→粉尘→灯",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "daylight_detector"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "redstone_lamp"),
            ],
            "notes": "昼夜控制示意；反相需额外火把（未放入）。",
        },
        {
            "id": "observer_edge",
            "matches": ["edge_detector", "observer_clock", "t_flip_flop"],
            "label_zh": "观察者边沿脉冲",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "observer", facing="west"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "redstone_lamp"),
            ],
            "notes": "观察者背面输出短脉冲；面对方块更新才触发。",
        },
        {
            "id": "pulse_repeater_line",
            "matches": ["pulse_extender", "pulse_limiter", "monostable", "instant_wire"],
            "label_zh": "中继器链（延迟/脉冲处理示意）",
            "size": [5, 1, 1],
            "blocks": [
                _b(0, 0, 0, "lever", face="floor", facing="east"),
                _b(1, 0, 0, "repeater", facing="east", delay="2"),
                _b(2, 0, 0, "repeater", facing="east", delay="4"),
                _b(3, 0, 0, "redstone_wire"),
                _b(4, 0, 0, "redstone_lamp"),
            ],
            "notes": "不同 delay 档串联；锁定限幅需侧向中继器，此处从简。",
        },
        {
            "id": "dropper_vator_stack",
            "matches": ["dropper_vator", "item_elevator"],
            "label_zh": "投掷器电梯（两格）",
            "size": [1, 3, 2],
            "blocks": [
                _b(0, 0, 0, "dropper", facing="up"),
                _b(0, 1, 0, "dropper", facing="up"),
                _b(0, 2, 0, "hopper", facing="down"),
                _b(0, 0, 1, "observer", facing="north"),
                _b(0, 1, 1, "redstone_wire"),
            ],
            "notes": "观察者检测投掷更新的粗电梯骨架；高度可复制叠层。",
        },
        {
            "id": "tripwire_trap_basic",
            "matches": ["tripwire_trap"],
            "label_zh": "绊线陷阱",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "tripwire_hook", facing="east"),
                _b(1, 0, 0, "tripwire"),
                _b(2, 0, 0, "tripwire_hook", facing="west"),
            ],
            "notes": "钩+线+钩；输出需接到发射器等（未含）。",
        },

        {
            "id": "furnace_input_hopper_stub",
            "matches": ["furnace_input", "smelter_feed", "hopper_furnace_in"],
            "label_zh": "\u7194\u7089\u8fdb\u6599\u6f0f\u6597\u6869\uff08\u7bb1\u2192\u6f0f\u6597\u2192\u7194\u7089\uff09",
            "size": [3, 2, 1],
            "blocks": [
                _b(0, 1, 0, "chest", facing="south"),
                _b(1, 1, 0, "hopper", facing="east"),
                _b(2, 1, 0, "furnace", facing="south", lit="false"),
                _b(1, 0, 0, "oak_planks"),
                _b(2, 0, 0, "oak_planks"),
                _b(0, 0, 0, "oak_planks"),
            ],
            "notes": "\u6559\u5b66\u6869\uff1a\u7bb1\u4fa7\u6f0f\u6597\u5582\u7194\u7089\u9876\u53e3\uff1b\u975e\u5b8c\u6574\u81ea\u52a8\u7194\u7089\u673a\u3002",
        },
        {
            "id": "furnace_output_hopper_stub",
            "matches": ["furnace_output", "smelter_drain", "hopper_furnace_out"],
            "label_zh": "\u7194\u7089\u51fa\u6599\u6f0f\u6597\u6869\uff08\u7194\u7089\u2192\u6f0f\u6597\u2192\u7bb1\uff09",
            "size": [3, 2, 1],
            "blocks": [
                _b(0, 1, 0, "furnace", facing="south", lit="false"),
                _b(0, 0, 0, "hopper", facing="east"),
                _b(1, 0, 0, "hopper", facing="east"),
                _b(2, 0, 0, "chest", facing="south"),
                _b(1, 1, 0, "oak_planks"),
                _b(2, 1, 0, "oak_planks"),
            ],
            "notes": "\u6559\u5b66\u6869\uff1a\u7194\u7089\u5e95\u90e8\u6f0f\u6597\u62C9\u51FA\u5230\u7bb1\uff1b\u53ef\u4e0e furnace_input_hopper_stub \u62fc\u63a5\u3002",
        },
        {
            "id": "piston_door_1wide_2high",
            "matches": ["piston_door_narrow", "flush_door_1wide"],
            "label_zh": "\u5355\u5217\u53cc\u9ad8\u6d3b\u585e\u95e8\uff08\u6559\u5b66\uff09",
            "size": [1, 2, 3],
            "blocks": [
                _b(0, 0, 0, "sticky_piston", facing="south"),
                _b(0, 1, 0, "sticky_piston", facing="south"),
                _b(0, 0, 1, "redstone_wire"),
                _b(0, 0, 2, "lever", face="floor", facing="south", powered="false"),
            ],
            "notes": "1\u5bbd\u00d72\u9ad8\u7c98\u6027\u6d3b\u585e\u95e8\u793a\u610f\uff1b\u5b9e\u88c5\u9700\u8865\u95e8\u677f\u4e0e\u85cf\u7ebf\u3002",
        },
        {
            "id": "or_gate_torch",
            "matches": ["or_gate", "torch_or"],
            "label_zh": "\u706b\u628a OR \u95e8\uff08\u53cc\u6746\u6746\u2192\u706f\uff09",
            "size": [3, 1, 2],
            "blocks": [
                _b(0, 0, 0, "lever", face="floor", facing="north", powered="false"),
                _b(2, 0, 0, "lever", face="floor", facing="north", powered="false"),
                _b(0, 0, 1, "redstone_wire"),
                _b(1, 0, 1, "redstone_wire"),
                _b(2, 0, 1, "redstone_wire"),
                _b(1, 0, 0, "redstone_lamp"),
            ],
            "notes": "\u7b80\u5316 OR\uff1a\u4efb\u4e00\u6746\u6746\u901a\u7535\u5373\u4eae\u706f\uff08\u7ebf\u6216\uff09\u3002",
        },
        {
            "id": "and_gate_torch",
            "matches": ["and_gate", "torch_and"],
            "label_zh": "\u706b\u628a AND \u95e8\uff08\u53cc\u8f93\u5165\u793a\u610f\uff09",
            "size": [3, 2, 2],
            "blocks": [
                _b(0, 0, 0, "lever", face="floor", facing="north", powered="false"),
                _b(2, 0, 0, "lever", face="floor", facing="north", powered="false"),
                _b(0, 0, 1, "redstone_torch", lit="true"),
                _b(2, 0, 1, "redstone_torch", lit="true"),
                _b(1, 0, 1, "redstone_wire"),
                _b(1, 1, 1, "redstone_torch", lit="false"),
                _b(1, 1, 0, "redstone_lamp"),
                _b(1, 0, 0, "oak_planks"),
            ],
            "notes": "\u6559\u5b66\u7ea7 AND \u6869\uff1a\u4e24\u8def NOR \u518d\u53cd\u76f8\uff1b\u975e\u7cbe\u786e\u5b9e\u88c5\u56fe\u3002",
        },
        {
            "id": "button_iron_door",
            "matches": ["button_door", "iron_door_pulse"],
            "label_zh": "\u77f3\u94ae\u94c1\u95e8\u8109\u51b2\uff08\u6237\u5916\uff09",
            "size": [2, 2, 1],
            "blocks": [
                _b(0, 0, 0, "iron_door", facing="south", half="lower", hinge="left", open="false"),
                _b(0, 1, 0, "iron_door", facing="south", half="upper", hinge="left", open="false"),
                _b(1, 0, 0, "stone_button", face="wall", facing="east", powered="false"),
            ],
            "notes": "\u77f3\u94ae\u77ed\u8109\u51b2\u5f00\u94c1\u95e8\uff1b\u9002\u5408\u8d34\u8fdb\u623f\u5c4b\u5165\u53e3\u3002",
        },
        {
            "id": "hopper_line_transfer",
            "matches": ["hopper_line", "item_pipe", "hopper_transfer"],
            "label_zh": "\u6f0f\u6597\u4f20\u8f93\u6869\uff08\u7bb1\u2192\u6f0f\u6597\u2192\u6f0f\u6597\u2192\u7bb1\uff09",
            "size": [4, 2, 1],
            "blocks": [
                _b(0, 1, 0, "chest", facing="south"),
                _b(1, 1, 0, "hopper", facing="east"),
                _b(2, 1, 0, "hopper", facing="east"),
                _b(3, 1, 0, "chest", facing="south"),
                _b(1, 0, 0, "oak_planks"),
                _b(2, 0, 0, "oak_planks"),
                _b(3, 0, 0, "oak_planks"),
            ],
            "notes": "\u6559\u5b66\u6869\uff1a\u7eaf\u7269\u54c1\u6c34\u5e73\u4f20\u8f93\uff1b\u975e\u5b8c\u6574\u5206\u62e3/\u519c\u573a\u3002",
        },
        {
            "id": "observer_clock_loop",
            "matches": ["observer_clock", "observer_loop", "fast_clock"],
            "label_zh": "\u89c2\u5bdf\u8005\u5bf9\u649e\u949f\uff08\u53cc\u89c2\u5bdf\u8005\uff09",
            "size": [2, 1, 2],
            "blocks": [
                _b(0, 0, 0, "observer", facing="east"),
                _b(1, 0, 0, "observer", facing="west"),
                _b(0, 0, 1, "redstone_wire"),
                _b(1, 0, 1, "redstone_lamp"),
            ],
            "notes": "\u6559\u5b66\u6869\uff1a\u4e24\u89c2\u5bdf\u8005\u5bf9\u8138\u5f62\u6210\u5feb\u949f\uff1b\u8f93\u51fa\u63a5\u706f\u3002\u975e\u5b8c\u6574\u673a\u5668\u3002",
        },
        {
            "id": "furnace_fuel_side_hopper",
            "matches": ["furnace_fuel", "smelter_fuel", "hopper_furnace_side"],
            "label_zh": "\u7194\u7089\u4fa7\u5411\u71c3\u6599\u6f0f\u6597\u6869\uff08\u7bb1\u2192\u6f0f\u6597\u2192\u7194\u7089\u4fa7\u9762\uff09",
            "size": [3, 2, 1],
            "blocks": [
                _b(0, 1, 0, "chest", facing="south"),
                _b(1, 1, 0, "hopper", facing="east"),
                _b(2, 1, 0, "furnace", facing="south", lit="false"),
                _b(1, 0, 0, "oak_planks"),
                _b(2, 0, 0, "oak_planks"),
            ],
            "notes": "\u6559\u5b66\u6869\uff1a\u4fa7\u9762\u6f0f\u6597\u5582\u71c3\u6599\uff1b\u4e0e\u8fdb\u6599\u9876\u53e3/\u51fa\u6599\u5e95\u53e3\u914d\u5957\u3002",
        },
        {
            "id": "comparator_chest_read",
            "matches": ["comparator_read", "container_signal", "fullness_detector"],
            "label_zh": "\u6bd4\u8f83\u5668\u8bfb\u7bb1\u6869\uff08\u7bb1\u2192\u6bd4\u8f83\u5668\u2192\u706f\uff09",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "chest", facing="south"),
                _b(1, 0, 0, "comparator", facing="west", mode="compare", powered="false"),
                _b(2, 0, 0, "redstone_lamp"),
            ],
            "notes": "\u6559\u5b66\u6869\uff1a\u6bd4\u8f83\u5668\u8bfb\u5bb9\u5668\u6ee1\u5ea6\uff1b\u975e\u5b8c\u6574\u5206\u62e3\u7cfb\u7edf\u3002",
        },
        {
            "id": "note_block_alert",
            "matches": ["note_block_alert", "doorbell", "note_alert"],
            "label_zh": "音符盒提示桩（按钮→粉尘→音符盒）",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "stone_button", face="floor", facing="east"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "note_block"),
            ],
            "notes": "教学桩：门铃/提示音；非完整音乐机。",
        },
        {
            "id": "dropper_dispenser_pulse",
            "matches": ["dropper_pulse", "dispenser_pulse", "item_spit"],
            "label_zh": "投掷器脉冲桩（按钮→粉尘→投掷器）",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "stone_button", face="floor", facing="east"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "dropper", facing="east"),
            ],
            "notes": "教学桩：单次脉冲投掷；可换发射器。",
        },
        {
            "id": "water_stream_item_tiny",
            "matches": ["water_stream", "item_waterway", "water_item_move"],
            "label_zh": "水流运物小桩（源→水→漏斗）",
            "size": [4, 1, 1],
            "blocks": [
                _b(0, 0, 0, "water"),
                _b(1, 0, 0, "water"),
                _b(2, 0, 0, "water"),
                _b(3, 0, 0, "hopper", facing="east"),
            ],
            "notes": "教学桩：极小水流运物入漏斗；需在源处放水桶/冰。",
        },
        {
            "id": "trapped_chest_signal",
            "matches": ["trapped_chest", "chest_trap_signal", "secret_chest"],
            "label_zh": "陷阱箱信号桩（陷阱箱→粉尘→灯）",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "trapped_chest", facing="south"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "redstone_lamp"),
            ],
            "notes": "教学桩：打开陷阱箱出信号；非完整陷阱。",
        },
        {
            "id": "daylight_sensor_lamp_stub",
            "matches": ["daylight_lamp", "outdoor_auto_lamp", "daylight_sensor_lamp"],
            "label_zh": "日光传感器夜灯桩（反相日光→粉尘→灯）",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "daylight_detector", inverted="true"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "redstone_lamp"),
            ],
            "notes": "教学桩：夜间点灯；与 daylight_clock（正常日光）区分。",
        },
        {
            "id": "pressure_plate_iron_door",
            "matches": ["pressure_door", "plate_door", "auto_iron_door"],
            "label_zh": "压力板铁门桩（石板→粉尘→铁门）",
            "size": [3, 2, 1],
            "blocks": [
                _b(0, 0, 0, "stone_pressure_plate"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "iron_door", facing="east", half="lower", open="false"),
                _b(2, 1, 0, "iron_door", facing="east", half="upper", open="false"),
            ],
            "notes": "教学桩：踏板开铁门；非完整自动门系统。",
        },

        {
            "id": "item_filter_stub",
            "matches": ["item_filter", "hopper_filter", "sorter_stub"],
            "label_zh": "物品过滤桩（箱→漏斗→侧漏斗+比较器）",
            "size": [3, 2, 2],
            "blocks": [
                _b(0, 1, 0, "chest", facing="south"),
                _b(0, 0, 0, "hopper", facing="east"),
                _b(1, 0, 0, "hopper", facing="east"),
                _b(1, 0, 1, "hopper", facing="south"),
                _b(1, 1, 1, "comparator", facing="north"),
                _b(2, 0, 0, "chest", facing="south"),
            ],
            "notes": "教学桩：极简过滤骨架；非完整分类机，需按物品改过滤槽。",
        },
        {
            "id": "torch_tower_elevator_frag",
            "matches": ["torch_tower", "torch_elevator", "vertical_torch_power"],
            "label_zh": "火把塔电梯碎片（竖向火把供电示意）",
            "size": [1, 4, 2],
            "blocks": [
                _b(0, 0, 0, "stone"),
                _b(0, 1, 0, "stone"),
                _b(0, 2, 0, "stone"),
                _b(0, 3, 0, "stone"),
                _b(0, 0, 1, "redstone_torch"),
                _b(0, 1, 1, "redstone_torch"),
                _b(0, 2, 1, "redstone_torch"),
                _b(0, 3, 1, "redstone_wire"),
            ],
            "notes": "教学桩：竖向火把塔供电碎片；非完整气泡/投掷电梯。",
        },
        {
            "id": "hopper_clock_xor_alt",
            "matches": ["hopper_clock_alt", "xor_hopper_clock", "etho_alt"],
            "label_zh": "漏斗钟交替布局（对吐+侧比较器）",
            "size": [3, 1, 2],
            "blocks": [
                _b(0, 0, 0, "hopper", facing="east"),
                _b(1, 0, 0, "hopper", facing="west"),
                _b(2, 0, 0, "comparator", facing="west"),
                _b(2, 0, 1, "redstone_wire"),
                _b(1, 0, 1, "redstone_wire"),
                _b(0, 0, 1, "redstone_lamp"),
            ],
            "notes": "教学桩：与 hopper_clock_basic 不同的输出侧布局；需放物品走钟。",
        },
        {
            "id": "lectern_book_signal",
            "matches": ["lectern_signal", "book_signal", "lectern_comparator"],
            "label_zh": "讲台书信号桩（讲台→比较器→灯）",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "lectern", facing="south", has_book="true"),
                _b(1, 0, 0, "comparator", facing="west"),
                _b(2, 0, 0, "redstone_lamp"),
            ],
            "notes": "教学桩：翻书页改变比较器强度；需放入成书面。",
        },
        {
            "id": "target_block_signal",
            "matches": ["target_block", "target_signal", "archery_signal"],
            "label_zh": "标靶信号桩（标靶→粉尘→灯）",
            "size": [3, 1, 1],
            "blocks": [
                _b(0, 0, 0, "target"),
                _b(1, 0, 0, "redstone_wire"),
                _b(2, 0, 0, "redstone_lamp"),
            ],
            "notes": "教学桩：箭/弹射物击中标靶出信号；可作家门铃变体。",
        },
        {
            "id": "brewing_stand_hopper_stub",
            "matches": ["brewing_hopper", "alchemy_feed", "brewing_stand_in"],
            "label_zh": "酿造台进料漏斗桩（箱→漏斗→酿造台）",
            "size": [2, 2, 1],
            "blocks": [
                _b(0, 1, 0, "chest", facing="south"),
                _b(0, 0, 0, "hopper", facing="east"),
                _b(1, 0, 0, "brewing_stand"),
            ],
            "notes": "教学桩：屋内炼药进料；非完整自动酿造机。",
        },



    ]


def templates_root(index_dir: str | Path | None = None) -> Path:
    root = project_root()
    d = Path(index_dir) if index_dir else root / TEMPLATES_DIR
    return d if d.is_absolute() else root / d


def bootstrap_templates(force: bool = False) -> Path:
    """Write canonical templates + catalog.json under data/redstone_templates/."""
    root = templates_root()
    root.mkdir(parents=True, exist_ok=True)
    catalog = []
    for tpl in canonical_templates():
        tid = tpl["id"]
        tdir = root / tid
        tdir.mkdir(parents=True, exist_ok=True)
        meta_path = tdir / "meta.json"
        blocks_path = tdir / "blocks.json"
        if force or not meta_path.exists():
            meta = {k: v for k, v in tpl.items() if k != "blocks"}
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            blocks_path.write_text(json.dumps(tpl["blocks"], ensure_ascii=False, indent=2), encoding="utf-8")
        catalog.append(
            {
                "id": tid,
                "matches": tpl.get("matches"),
                "label_zh": tpl.get("label_zh"),
                "dir": tid,
            }
        )
    (root / "catalog.json").write_text(
        json.dumps({"version": 1, "templates": catalog}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return root


def load_all_templates(index_dir: str | Path | None = None) -> list[dict[str, Any]]:
    root = templates_root(index_dir)
    if not (root / "catalog.json").exists():
        bootstrap_templates()
    cat = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    out = []
    for ent in cat.get("templates") or []:
        tid = ent["id"]
        tdir = root / (ent.get("dir") or tid)
        meta = json.loads((tdir / "meta.json").read_text(encoding="utf-8"))
        blocks = json.loads((tdir / "blocks.json").read_text(encoding="utf-8"))
        meta["blocks"] = blocks
        meta.setdefault("id", tid)
        out.append(meta)
    return out


@dataclass
class MatchResult:
    pattern_id: str
    pattern_label: str
    pattern_confidence: str
    template_id: str
    template_label: str
    score: float
    notes: str = ""
    principle_rule_ids: list[str] | None = None


def match_templates_to_analyze(
    analyze: dict[str, Any],
    templates: list[dict[str, Any]] | None = None,
) -> list[MatchResult]:
    templates = templates or load_all_templates()
    rs = analyze.get("redstone") or {}
    patterns = (rs.get("common_patterns") or {}).get("patterns") or []
    # also clocks
    for c in (rs.get("clocks") or {}).get("clocks") or []:
        patterns.append(
            {
                "id": c.get("id"),
                "label": c.get("label"),
                "confidence": c.get("confidence"),
                "score": c.get("score") or 0.5,
            }
        )
    # dedupe pattern ids keeping higher score
    best_p: dict[str, dict] = {}
    for p in patterns:
        pid = p.get("id")
        if not pid:
            continue
        if pid not in best_p or float(p.get("score") or 0) > float(best_p[pid].get("score") or 0):
            best_p[pid] = p

    # inverted index match_id -> templates
    by_match: dict[str, list[dict]] = {}
    for t in templates:
        for m in t.get("matches") or []:
            by_match.setdefault(m, []).append(t)

    results: list[MatchResult] = []
    used_tpl: set[str] = set()
    for pid, p in sorted(best_p.items(), key=lambda kv: -float(kv[1].get("score") or 0)):
        cands = by_match.get(pid) or []
        if not cands:
            continue
        # pick first unused
        tpl = None
        for c in cands:
            if c["id"] not in used_tpl:
                tpl = c
                break
        if tpl is None:
            # already pasted this template for another pattern — skip duplicate strip
            continue
        used_tpl.add(tpl["id"])
        conf = str(p.get("confidence") or "low")
        base = float(p.get("score") or 0.4)
        boost = {"high": 0.2, "medium": 0.1, "low": 0.0}.get(conf, 0.0)
        from src.app.redstone_principles import principle_notes_for_template

        rule_ids, rule_notes = principle_notes_for_template(pid, str(tpl["id"]))
        base_notes = str(tpl.get("notes") or "")
        merged_notes = base_notes
        if rule_notes:
            merged_notes = (base_notes + " | " if base_notes else "") + rule_notes
        results.append(
            MatchResult(
                pattern_id=pid,
                pattern_label=str(p.get("label") or pid),
                pattern_confidence=conf,
                template_id=tpl["id"],
                template_label=str(tpl.get("label_zh") or tpl["id"]),
                score=min(1.0, base + boost),
                notes=merged_notes,
                principle_rule_ids=rule_ids or None,
            )
        )
    results.sort(key=lambda r: -r.score)
    return results


def _palette_key(block: str, props: dict[str, str] | None) -> tuple:
    return (block, tuple(sorted((props or {}).items())))


def build_canvas_from_templates(
    matches: list[MatchResult],
    templates: list[dict[str, Any]],
    *,
    padding: int = 2,
    gap: int = 2,
    include_labels_as_signs: bool = False,
) -> tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]]]:
    """Paste matched templates side-by-side on air canvas.

    Returns (voxels index array, palette_states[{Name,Properties}], placements meta).
    """
    by_id = {t["id"]: t for t in templates}
    chosen = []
    for m in matches:
        t = by_id.get(m.template_id)
        if t:
            chosen.append((m, t))
    if not chosen:
        # empty 1x1 air
        return np.zeros((1, 1, 1), dtype=np.int32), [{"Name": "minecraft:air", "Properties": {}}], []

    # layout along X
    cursor_x = padding
    max_y = 1
    max_z = 1
    placements = []
    for m, t in chosen:
        sx, sy, sz = t.get("size") or _infer_size(t["blocks"])
        placements.append(
            {
                "template_id": t["id"],
                "label_zh": t.get("label_zh"),
                "pattern_id": m.pattern_id,
                "origin": [cursor_x, padding, padding],
                "size": [sx, sy, sz],
                "score": m.score,
            }
        )
        cursor_x += sx + gap
        max_y = max(max_y, padding + sy + padding)
        max_z = max(max_z, padding + sz + padding)
    width = cursor_x + padding

    # build palette states
    palette_states: list[dict[str, Any]] = [{"Name": "minecraft:air", "Properties": {}}]
    key_to_idx: dict[tuple, int] = {_palette_key("minecraft:air", {}): 0}

    def idx_for(block: str, props: dict | None) -> int:
        block = block if block.startswith("minecraft:") else "minecraft:" + block
        props = dict(props or {})
        key = _palette_key(block, props)
        if key not in key_to_idx:
            key_to_idx[key] = len(palette_states)
            palette_states.append({"Name": block, "Properties": props})
        return key_to_idx[key]

    voxels = np.zeros((width, max_y, max_z), dtype=np.int32)
    for place, (m, t) in zip(placements, chosen):
        ox, oy, oz = place["origin"]
        for b in t.get("blocks") or []:
            if b.get("block") in ("minecraft:air", "air"):
                continue
            x = ox + int(b["x"])
            y = oy + int(b["y"])
            z = oz + int(b["z"])
            if 0 <= x < width and 0 <= y < max_y and 0 <= z < max_z:
                voxels[x, y, z] = idx_for(b["block"], b.get("props"))

    return voxels, palette_states, placements


def _infer_size(blocks: list[dict]) -> list[int]:
    if not blocks:
        return [1, 1, 1]
    xs = [int(b["x"]) for b in blocks]
    ys = [int(b["y"]) for b in blocks]
    zs = [int(b["z"]) for b in blocks]
    return [max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, max(zs) - min(zs) + 1]


def save_litematic_states(
    voxels: np.ndarray,
    palette_states: list[dict[str, Any]],
    out_path: str | Path,
    *,
    name: str | None = None,
    author: str = "mc-architecture-ai",
    description: str = "Redstone template paste (Phase 4)",
) -> dict[str, Any]:
    """Write litematic with BlockState Properties (needed for hopper/piston facing)."""
    if nbtlib is None:
        raise RuntimeError("nbtlib required")
    from time import time

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    vox = np.asarray(voxels, dtype=np.int32)
    sx, sy, sz = map(int, vox.shape)
    # clamp indices
    vox = np.clip(vox, 0, len(palette_states) - 1)

    remapped = np.transpose(vox, (1, 2, 0)).reshape(-1)
    bits = _bits_per_block(len(palette_states))
    packed = _pack_block_states(remapped, bits)
    non_air = int((remapped != 0).sum())

    palette_tag = nbtlib.List[nbtlib.Compound]([])
    for st in palette_states:
        comp = nbtlib.Compound({"Name": nbtlib.String(st["Name"])})
        props = st.get("Properties") or {}
        if props:
            comp["Properties"] = nbtlib.Compound(
                {k: nbtlib.String(str(v)) for k, v in props.items()}
            )
        palette_tag.append(comp)

    schematic_name = name or out_path.stem
    now_ms = int(time() * 1000)
    region = nbtlib.Compound(
        {
            "Size": nbtlib.Compound(
                {"x": nbtlib.Int(sx), "y": nbtlib.Int(sy), "z": nbtlib.Int(sz)}
            ),
            "Position": nbtlib.Compound(
                {"x": nbtlib.Int(0), "y": nbtlib.Int(0), "z": nbtlib.Int(0)}
            ),
            "BlockStatePalette": palette_tag,
            "BlockStates": nbtlib.LongArray([nbtlib.Long(v) for v in packed]),
            "TileEntities": nbtlib.List[nbtlib.Compound]([]),
            "Entities": nbtlib.List[nbtlib.Compound]([]),
            "PendingBlockTicks": nbtlib.List([]),
            "PendingFluidTicks": nbtlib.List([]),
        }
    )
    root = nbtlib.File(
        {
            "Version": nbtlib.Int(7),
            "SubVersion": nbtlib.Int(1),
            "MinecraftDataVersion": nbtlib.Int(3953),
            "Metadata": nbtlib.Compound(
                {
                    "Name": nbtlib.String(schematic_name),
                    "Author": nbtlib.String(author),
                    "Description": nbtlib.String(description),
                    "TimeCreated": nbtlib.Long(now_ms),
                    "TimeModified": nbtlib.Long(now_ms),
                    "RegionCount": nbtlib.Int(1),
                    "TotalBlocks": nbtlib.Int(non_air),
                    "TotalVolume": nbtlib.Int(sx * sy * sz),
                    "EnclosingSize": nbtlib.Compound(
                        {"x": nbtlib.Int(sx), "y": nbtlib.Int(sy), "z": nbtlib.Int(sz)}
                    ),
                }
            ),
            "Regions": nbtlib.Compound({schematic_name: region}),
        },
        gzipped=True,
        byteorder="big",
    )
    # nbtlib File save
    root.save(out_path)
    return {
        "path": str(out_path),
        "size": [sx, sy, sz],
        "non_air": non_air,
        "palette_len": len(palette_states),
    }


def replicate_redstone_from_litematic(
    path: str | Path,
    *,
    out_dir: str | Path | None = None,
    max_templates: int = 8,
) -> dict[str, Any]:
    """Analyze → match templates → paste litematic + Chinese markdown report."""
    root = project_root()
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    bootstrap_templates()
    templates = load_all_templates()
    analyze = analyze_litematic(path)
    matches = match_templates_to_analyze(analyze, templates)[: max(1, int(max_templates))]

    stem = path.stem
    out_dir = Path(out_dir) if out_dir else root / "outputs" / "redstone_replicate" / stem
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    voxels, states, placements = build_canvas_from_templates(matches, templates)
    lite_path = out_dir / ("%s_templates.litematic" % stem)
    save_info = save_litematic_states(
        voxels,
        states,
        lite_path,
        name="%s_rs_templates" % stem[:40],
        description="Phase4 template paste from analyze patterns (not VAE)",
    )

    # also dump voxels npz indices + states json
    np.savez_compressed(out_dir / ("%s_templates.npz" % stem), voxels=voxels)
    (out_dir / ("%s_palette_states.json" % stem)).write_text(
        json.dumps(states, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report_lines = [
        "# 红石原理级复刻报告（模板粘贴）",
        "",
        f"- **参考**: `{path.name}`",
        f"- **时间**: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- **说明**: 根据 Phase1 D9 模式匹配**手写模板**并排粘贴；**不是** VAE 发明电路，也非原版 tick 对等。",
        "",
        "## 匹配结果",
        "",
    ]
    if not matches:
        report_lines.append("- （未匹配到库内模板；参考可能几乎无红石或模式未覆盖）")
    for m in matches:
        report_lines.append(
            f"- **{m.pattern_label}** (`{m.pattern_id}`, {m.pattern_confidence}) "
            f"→ 模板 **{m.template_label}** (`{m.template_id}`, score={m.score:.2f})"
        )
        if m.notes:
            report_lines.append(f"  - {m.notes}")
    report_lines += [
        "",
        "## 粘贴布局",
        "",
        f"- 画布尺寸: {list(map(int, voxels.shape))}（X,Y,Z）",
        f"- 输出: `{lite_path.relative_to(root)}`",
        "",
    ]
    for p in placements:
        report_lines.append(
            f"- `{p['template_id']}` @ origin={p['origin']} size={p['size']}"
        )
    report_lines += [
        "",
        "## 局限",
        "",
        "- 模板为教学向最小骨架，需在游戏内接电、填物品、调朝向细节",
        "- 不复刻参考中的具体坐标与装修；QC/BUD/零刻仅示意",
        "- `save` 含 Properties，但未写入漏斗物品 NBT",
        "",
    ]
    report_path = out_dir / ("%s_replicate_report.md" % stem)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    summary = {
        "reference": str(path.relative_to(root)) if str(path).startswith(str(root)) else str(path),
        "matches": [m.__dict__ for m in matches],
        "placements": placements,
        "litematic": str(lite_path.relative_to(root)),
        "report": str(report_path.relative_to(root)),
        "save": save_info,
        "analyze_pattern_ids": [
            p.get("id")
            for p in ((analyze.get("redstone") or {}).get("common_patterns") or {}).get("patterns")
            or []
        ],
    }
    (out_dir / ("%s_replicate.json" % stem)).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary

# ---------------------------------------------------------------------------
# Paste templates INTO an architectural design (32^3 palette voxels)
# ---------------------------------------------------------------------------

_DEFAULT_DOOR_NAMES = (
    "minecraft:oak_door",
    "minecraft:iron_door",
    "minecraft:spruce_door",
    "minecraft:birch_door",
    "minecraft:dark_oak_door",
    "minecraft:acacia_door",
    "minecraft:jungle_door",
    "minecraft:crimson_door",
    "minecraft:warped_door",
    "minecraft:mangrove_door",
    "minecraft:cherry_door",
    "minecraft:bamboo_door",
)


def invert_palette(palette: dict[int, str]) -> dict[str, int]:
    return {str(v): int(k) for k, v in palette.items()}


def resolve_template(
    template_id: str,
    templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # Resolve template by id; auto / auto:door / auto:io pick defaults.
    bootstrap_templates()
    templates = templates if templates is not None else load_all_templates()
    by_id = {t["id"]: t for t in templates}
    tid = (template_id or "auto").strip().lower()
    if tid in ("auto", "auto:io", "auto:lamp", "default"):
        tid = "simple_io_lever_lamp"
    elif tid in ("auto:door", "auto:piston_door", "door"):
        tid = "piston_door_2wide"
    elif tid in ("auto:clock", "auto:hopper"):
        tid = "hopper_clock_basic"
    if tid not in by_id:
        raise KeyError(
            "unknown template_id=%r; known=%s"
            % (template_id, ", ".join(sorted(by_id)))
        )
    return by_id[tid]


def door_ids_from_palette(palette: dict[int, str]) -> set[int]:
    names = set(_DEFAULT_DOOR_NAMES)
    out: set[int] = set()
    for i, name in palette.items():
        n = str(name)
        if n in names or n.endswith("_door"):
            out.add(int(i))
    return out


def find_paste_origin(
    voxels: np.ndarray,
    size: list[int] | tuple[int, int, int],
    *,
    palette: dict[int, str] | None = None,
    prefer_near_door: bool = False,
    margin: int = 1,
    min_air_frac: float = 0.55,
) -> tuple[tuple[int, int, int], dict[str, Any]]:
    # Pick an interior floor pocket for a template of size (sx,sy,sz).
    vox = np.asarray(voxels)
    if vox.ndim != 3:
        raise ValueError("voxels must be 3D")
    W, H, D = map(int, vox.shape)
    tx, ty, tz = (int(size[0]), int(size[1]), int(size[2]))
    solid = vox > 0
    door_ids = door_ids_from_palette(palette) if palette else set()
    door_cells = []
    if prefer_near_door and door_ids:
        for i in door_ids:
            ys = np.argwhere(vox == i)
            for row in ys:
                door_cells.append((int(row[0]), int(row[1]), int(row[2])))

    best: tuple | None = None
    floor_ys = []
    for y in range(0, H - 1):
        if int(solid[:, y, :].sum()) >= 40:
            floor_ys.append(y)
    if not floor_ys:
        floor_ys = [0]

    x0 = max(0, margin)
    z0 = max(0, margin)
    x1 = max(x0, W - tx - margin)
    z1 = max(z0, D - tz - margin)

    for y_floor in floor_ys:
        y_paste = y_floor + 1
        if y_paste + ty > H:
            continue
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                region = vox[x : x + tx, y_paste : y_paste + ty, z : z + tz]
                total = tx * ty * tz
                air_n = int((region == 0).sum())
                if air_n < int(total * min_air_frac):
                    continue
                below = solid[x : x + tx, y_floor, z : z + tz]
                if int(below.sum()) < max(1, (tx * tz) // 4):
                    continue
                wall_touch = 0
                for dx, dz in ((-1, 0), (tx, 0), (0, -1), (0, tz)):
                    nx, nz = x + dx, z + dz
                    if 0 <= nx < W and 0 <= nz < D and solid[nx, y_floor, nz]:
                        wall_touch += 1
                door_bonus = 0
                if door_cells:
                    cx, cy, cz = x + tx // 2, y_paste, z + tz // 2
                    dist = min(
                        abs(cx - dx) + abs(cy - dy) + abs(cz - dz)
                        for dx, dy, dz in door_cells
                    )
                    door_bonus = max(0, 40 - dist)
                score = air_n * 10 + wall_touch * 35 + door_bonus - y_paste * 2
                cand = (score, x, y_paste, z, air_n, wall_touch, door_bonus, y_floor)
                if best is None or cand[0] > best[0]:
                    best = cand

    if best is None:
        ox = min(margin, max(0, W - tx))
        oy = min(1, max(0, H - ty))
        oz = min(margin, max(0, D - tz))
        return (ox, oy, oz), {
            "fallback": True,
            "reason": "no interior air pocket; used padded corner",
            "size": [tx, ty, tz],
        }

    _score, ox, oy, oz, air_n, wall_touch, door_bonus, y_floor = best
    return (ox, oy, oz), {
        "fallback": False,
        "score": int(_score),
        "air_in_bbox": int(air_n),
        "wall_touch": int(wall_touch),
        "door_bonus": int(door_bonus),
        "floor_y": int(y_floor),
        "size": [tx, ty, tz],
        "prefer_near_door": bool(prefer_near_door),
    }


def paste_template_into_voxels(
    voxels: np.ndarray,
    template: dict[str, Any],
    origin: tuple[int, int, int],
    palette: dict[int, str],
    *,
    collision_mode: str = "air_only",
) -> dict[str, Any]:
    # Paste one template into palette-index voxels (templates only, no VAE).
    vox = np.asarray(voxels).copy()
    name_to_id = invert_palette(palette)
    ox, oy, oz = (int(origin[0]), int(origin[1]), int(origin[2]))
    W, H, D = map(int, vox.shape)
    placed = 0
    skipped_solid = 0
    skipped_oob = 0
    skipped_unknown = 0
    unknown_blocks: list[str] = []
    written: list[dict[str, Any]] = []

    mode = (collision_mode or "air_only").strip().lower()
    if mode not in ("air_only", "overwrite"):
        raise ValueError("collision_mode must be air_only|overwrite")

    for b in template.get("blocks") or []:
        block = str(b.get("block") or "minecraft:air")
        if not block.startswith("minecraft:"):
            block = "minecraft:" + block
        if block in ("minecraft:air", "air"):
            continue
        x = ox + int(b["x"])
        y = oy + int(b["y"])
        z = oz + int(b["z"])
        if not (0 <= x < W and 0 <= y < H and 0 <= z < D):
            skipped_oob += 1
            continue
        bid = name_to_id.get(block)
        if bid is None:
            skipped_unknown += 1
            if block not in unknown_blocks:
                unknown_blocks.append(block)
            continue
        if mode == "air_only" and int(vox[x, y, z]) != 0:
            skipped_solid += 1
            continue
        vox[x, y, z] = int(bid)
        placed += 1
        written.append(
            {
                "x": x,
                "y": y,
                "z": z,
                "block": block,
                "props": dict(b.get("props") or {}),
                "palette_id": int(bid),
            }
        )

    return {
        "voxels": vox,
        "origin": [ox, oy, oz],
        "template_id": template.get("id"),
        "label_zh": template.get("label_zh"),
        "placed": placed,
        "skipped_solid": skipped_solid,
        "skipped_oob": skipped_oob,
        "skipped_unknown": skipped_unknown,
        "unknown_blocks": unknown_blocks,
        "collision_mode": mode,
        "written": written,
        "size": template.get("size") or _infer_size(template.get("blocks") or []),
    }


def design_to_states_with_template(
    voxels_before: np.ndarray,
    palette: dict[int, str],
    template: dict[str, Any],
    origin: tuple[int, int, int],
    *,
    collision_mode: str = "air_only",
) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    # House Names from palette + template props for litematic export.
    vox = np.asarray(voxels_before)
    W, H, D = map(int, vox.shape)
    palette_states: list[dict[str, Any]] = [{"Name": "minecraft:air", "Properties": {}}]
    key_to_idx: dict[tuple, int] = {_palette_key("minecraft:air", {}): 0}

    def idx_for(block: str, props: dict | None) -> int:
        block = block if block.startswith("minecraft:") else "minecraft:" + block
        props = dict(props or {})
        key = _palette_key(block, props)
        if key not in key_to_idx:
            key_to_idx[key] = len(palette_states)
            palette_states.append({"Name": block, "Properties": props})
        return key_to_idx[key]

    out = np.zeros((W, H, D), dtype=np.int32)
    xs, ys, zs = np.where(vox > 0)
    for i in range(xs.size):
        x, y, z = int(xs[i]), int(ys[i]), int(zs[i])
        bid = int(vox[x, y, z])
        name = palette.get(bid, "minecraft:stone")
        out[x, y, z] = idx_for(str(name), {})

    ox, oy, oz = (int(origin[0]), int(origin[1]), int(origin[2]))
    mode = (collision_mode or "air_only").strip().lower()
    placed = 0
    skipped_solid = 0
    skipped_oob = 0
    for b in template.get("blocks") or []:
        block = str(b.get("block") or "minecraft:air")
        if not block.startswith("minecraft:"):
            block = "minecraft:" + block
        if block in ("minecraft:air", "air"):
            continue
        x = ox + int(b["x"])
        y = oy + int(b["y"])
        z = oz + int(b["z"])
        if not (0 <= x < W and 0 <= y < H and 0 <= z < D):
            skipped_oob += 1
            continue
        if mode == "air_only" and int(vox[x, y, z]) != 0:
            skipped_solid += 1
            continue
        out[x, y, z] = idx_for(block, b.get("props"))
        placed += 1

    meta = {
        "placed": placed,
        "skipped_solid": skipped_solid,
        "skipped_oob": skipped_oob,
        "collision_mode": mode,
        "origin": [ox, oy, oz],
        "template_id": template.get("id"),
    }
    return out, palette_states, meta


def paste_redstone_into_design(
    npz_path: str | Path,
    *,
    template_id: str = "auto",
    out_dir: str | Path | None = None,
    origin: tuple[int, int, int] | None = None,
    collision_mode: str = "air_only",
    prefer_near_door: bool | None = None,
    palette_path: str | Path | None = None,
    export_litematic: bool = True,
    export_name: str | None = None,
    companion_export: bool = False,
    companion_name: str | None = None,
) -> dict[str, Any]:
    # Load house npz, paste template, structure-check, preview + litematic.
    from src.app.structure_constraints import SCAFFOLD_THRESHOLDS, check_structure
    from src.utils import load_config, load_palette

    root = project_root()
    npz_path = Path(npz_path)
    if not npz_path.is_absolute():
        npz_path = root / npz_path
    if not npz_path.is_file():
        raise FileNotFoundError(npz_path)

    cfg = load_config(root / "configs/default.yaml")
    pal_path = Path(palette_path) if palette_path else root / cfg["data"]["palette_path"]
    if not pal_path.is_absolute():
        pal_path = root / pal_path
    palette = load_palette(pal_path)

    with np.load(npz_path) as data:
        key = "voxels" if "voxels" in data.files else data.files[0]
        voxels = np.asarray(data[key])

    template = resolve_template(template_id)
    size = template.get("size") or _infer_size(template.get("blocks") or [])
    tid = str(template.get("id") or "")
    if prefer_near_door is None:
        prefer_near_door = tid in (
            "piston_door_2wide",
            "simple_io_lever_lamp",
            "tripwire_trap_basic",
        )

    if origin is None:
        origin, place_meta = find_paste_origin(
            voxels,
            size,
            palette=palette,
            prefer_near_door=bool(prefer_near_door),
        )
    else:
        origin = (int(origin[0]), int(origin[1]), int(origin[2]))
        place_meta = {"fallback": False, "manual_origin": True}

    before = check_structure(voxels, SCAFFOLD_THRESHOLDS)
    paste = paste_template_into_voxels(
        voxels, template, origin, palette, collision_mode=collision_mode
    )
    after = check_structure(paste["voxels"], SCAFFOLD_THRESHOLDS)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if out_dir is None:
        out_dir = root / "outputs" / "design" / ("rs_paste_%s" % ts)
    else:
        out_dir = Path(out_dir)
        if not out_dir.is_absolute():
            out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "previews").mkdir(exist_ok=True)

    stem = npz_path.stem
    before_path = out_dir / ("%s_before.npz" % stem)
    after_path = out_dir / ("%s_after.npz" % stem)
    np.savez_compressed(before_path, voxels=voxels)
    np.savez_compressed(after_path, voxels=paste["voxels"])

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from src.app.mc_render import render_mc_voxels

        for tag, arr in (("before", voxels), ("after", paste["voxels"])):
            fig = plt.figure(figsize=(6, 6))
            ax = fig.add_subplot(111, projection="3d")
            render_mc_voxels(ax, fig, arr, palette, performance=True)
            ax.set_title("%s / %s" % (stem, tag), fontsize=9)
            fig.savefig(
                out_dir / "previews" / ("%s_%s.png" % (stem, tag)),
                dpi=120,
                bbox_inches="tight",
            )
            plt.close(fig)
    except Exception as ex:  # pragma: no cover
        place_meta["preview_error"] = str(ex)

    lite_info = None
    lite_path = None
    if export_litematic:
        states_vox, states, st_meta = design_to_states_with_template(
            voxels, palette, template, origin, collision_mode=collision_mode
        )
        lite_name = export_name or ("%s__%s" % (stem[:40], tid))
        lite_path = out_dir / ("%s.litematic" % lite_name)
        lite_info = save_litematic_states(
            states_vox,
            states,
            lite_path,
            name=lite_name[:80],
            description="Design + redstone template paste (not VAE); template=%s" % tid,
        )
        lite_info["states_meta"] = st_meta

    companion_info = None
    if companion_export:
        try:
            from src.data.export_litematic_util import export_voxels_to_companion

            cname = companion_name or (
                "\u6b27\u5f0f_\u7ea2\u77f3\u95e8\u63a7"
                if ("door" in tid or "piston" in tid)
                else "\u5efa\u7b51_\u7ea2\u77f3\u7c98\u8d34"
            )
            companion_info = export_voxels_to_companion(
                paste["voxels"],
                palette,
                name=cname,
                author="mc-architecture-ai",
                verify=True,
            )
        except Exception as ex:
            companion_info = {"ok": False, "error": str(ex)}

    report_lines = [
        "# \u7ea2\u77f3\u6a21\u677f\u5d4c\u5165\u5efa\u7b51\u8bbe\u8ba1\u62a5\u544a",
        "",
        f"- **\u5efa\u7b51**: `{npz_path.name}`",
        f"- **\u6a21\u677f**: **{template.get('label_zh')}** (`{tid}`)",
        f"- **\u65f6\u95f4**: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- **\u539f\u70b9**: `{list(origin)}`\uff08\u78b0\u649e\u6a21\u5f0f `{collision_mode}`\uff09",
        f"- **\u8bf4\u660e**: \u624b\u5199\u539f\u7406\u9aa8\u67b6\u5d4c\u5165 32\u00b3 \u5916\u58f3\uff1b**\u4e0d\u662f** VAE \u53d1\u660e\u7535\u8def\uff0c\u4e5f\u975e\u5b8c\u6574\u7ea2\u77f3\u519c\u573a\u3002",
        "",
        "## \u653e\u7f6e",
        "",
        f"- \u542f\u53d1\u5f0f: `{json.dumps(place_meta, ensure_ascii=False)}`",
        f"- \u5199\u5165\u65b9\u5757: **{paste['placed']}**\uff1b\u8df3\u8fc7\u5b9e\u5fc3 {paste['skipped_solid']}\uff1b\u8d8a\u754c {paste['skipped_oob']}\uff1b\u672a\u77e5 id {paste['skipped_unknown']}",
        "",
        "## \u7ed3\u6784\u7ea6\u675f\uff08scaffold \u9608\u503c\uff09",
        "",
        f"- \u7c98\u8d34\u524d: ok=**{before.ok}** non_air={before.metrics.get('non_air')} hollow={before.metrics.get('hollow_score')}",
        f"- \u7c98\u8d34\u540e: ok=**{after.ok}** non_air={after.metrics.get('non_air')} hollow={after.metrics.get('hollow_score')}",
    ]
    if after.reasons:
        report_lines.append(f"- \u7c98\u8d34\u540e reasons: {after.reasons}")
    report_lines += [
        "",
        "## \u5c40\u9650",
        "",
        "- \u6a21\u677f\u4e3a\u6559\u5b66\u5411\u6700\u5c0f\u9aa8\u67b6\uff0c\u9700\u5728\u6e38\u620f\u5185\u63a5\u7535\u3001\u586b\u7269\u54c1\u3001\u5fae\u8c03\u671d\u5411",
        "- `air_only` \u4e0d\u4f1a\u51ff\u7a7f\u5899\u4f53\uff1b\u82e5\u8df3\u8fc7\u8f83\u591a\uff0c\u53ef\u6362 `--collision overwrite` \u6216\u624b\u52a8 `--origin`",
        "- companion \u5bfc\u51fa\u8d70\u8c03\u8272\u677f\u8def\u5f84\u65f6\u90e8\u5206\u671d\u5411 Properties \u53ef\u80fd\u4e22\u5931\uff1b\u672c\u76ee\u5f55 `.litematic` \u7528 states \u4fdd\u7559\u6a21\u677f\u671d\u5411",
        "- \u4e0d\u81ea\u52a8\u5d4c\u7194\u7089/\u5237\u602a\u5854\u7b49\u5927\u673a\u6784\uff1b\u90a3\u4e9b\u4ecd\u7528 early_tech \u6574\u5305\u6295\u5f71",
        "",
    ]
    report_path = out_dir / "paste_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    summary = {
        "npz": str(npz_path.relative_to(root)) if str(npz_path).startswith(str(root)) else str(npz_path),
        "template_id": tid,
        "label_zh": template.get("label_zh"),
        "origin": list(origin),
        "placement": place_meta,
        "paste": {
            "placed": paste["placed"],
            "skipped_solid": paste["skipped_solid"],
            "skipped_oob": paste["skipped_oob"],
            "skipped_unknown": paste["skipped_unknown"],
            "unknown_blocks": paste["unknown_blocks"],
            "collision_mode": paste["collision_mode"],
        },
        "structure_before": before.to_dict(),
        "structure_after": after.to_dict(),
        "before_npz": str(before_path.relative_to(root)),
        "after_npz": str(after_path.relative_to(root)),
        "litematic": str(lite_path.relative_to(root)) if lite_path else None,
        "litematic_info": lite_info,
        "companion": companion_info,
        "report": str(report_path.relative_to(root)),
        "out_dir": str(out_dir.relative_to(root)),
        "notes": template.get("notes"),
    }

    def _jsonable(obj):
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, dict):
            return {k: _jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_jsonable(v) for v in obj]
        return obj

    summary = _jsonable(summary)

    (out_dir / "paste_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary