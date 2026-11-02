# -*- coding: utf-8 -*-
"""Phase 1 redstone: composition graph + principle hints (no tick simulation).

Approximations (documented):
- Uses blockstate Properties when available via load_litematic_detailed.
- Dust: undirected edges to 6-neighbors that are redstone-related (over-connects
  vs real dust shape, but good for inventory topology).
- Repeater / comparator: directed edge from rear (input) toward facing (output);
  also weak undirected link to side neighbors (lock / subtract side).
- Observer: directed soft edge from facing (detection face) to opposite (output).
- Piston / hopper / dropper / dispenser: directed soft edge along facing.
- Lever / button / plate / torch / lamp / block: undirected 6-neigh to other RS nodes.
- No QC, no soft power through solid blocks, no dust strength decay, no tick order.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any
from src.app.dust_connect import build_dust_adjacency
from src.app.redstone_patterns import detect_common_patterns
from src.app.redstone_physics import detect_clocks, detect_qc_bud, estimate_dust_strength
from src.app.redstone_tick_sim import run_tick_simulation, tick_sim_to_markdown

# Facing → delta in voxel [X,Y,Z] (Litematica layout used by this project)
_FACING_DELTA: dict[str, tuple[int, int, int]] = {
    "east": (1, 0, 0),
    "west": (-1, 0, 0),
    "up": (0, 1, 0),
    "down": (0, -1, 0),
    "south": (0, 0, 1),
    "north": (0, 0, -1),
}
_OPPOSITE = {
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up",
    "south": "north",
    "north": "south",
}

# kind → coarse role bucket
_KIND_ROLE: dict[str, str] = {
    "redstone_wire": "wire",
    "redstone_torch": "power_source",
    "redstone_block": "power_source",
    "lever": "power_source",
    "button": "power_source",
    "pressure_plate": "power_source",
    "daylight_detector": "power_source",
    "repeater": "logic",
    "comparator": "logic",
    "observer": "observer",
    "piston": "piston",
    "sticky_piston": "piston",
    "piston_head": "piston",
    "moving_piston": "piston",
    "hopper": "transport",
    "dropper": "transport",
    "dispenser": "transport",
    "rail": "transport",
    "powered_rail": "transport",
    "detector_rail": "transport",
    "activator_rail": "transport",
    "sculk_sensor": "sensor",
    "target": "sensor",
    "tripwire": "sensor",
    "note_block": "output",
    "redstone_lamp": "output",
    "copper_bulb": "output",
    "door": "output",
    "iron_door": "output",
    "trapdoor": "output",
    "fence_gate": "output",
    "crafter": "transport",
    "brewing_stand": "transport",
    "furnace": "transport",
    "smoker": "transport",
    "blast_furnace": "transport",
    "trapped_chest": "sensor",
    "lectern": "sensor",
    "chiseled_bookshelf": "sensor",
    "nether_portal": "other",
    "shulker_box": "transport",
    "slime_block": "piston",
    "honey_block": "piston",
    "trial_spawner": "other",
    "vault": "other",
}

_KIND_ORDER = [
    "redstone_wire",
    "redstone_torch",
    "redstone_block",
    "repeater",
    "comparator",
    "lever",
    "button",
    "pressure_plate",
    "piston",
    "sticky_piston",
    "observer",
    "hopper",
    "dropper",
    "dispenser",
    "note_block",
    "target",
    "redstone_lamp",
    "door",
    "iron_door",
    "trapdoor",
    "fence_gate",
    "tripwire",
    "daylight_detector",
    "powered_rail",
    "detector_rail",
    "activator_rail",
    "rail",
    "sculk_sensor",
    "piston_head",
    "moving_piston",
    "copper_bulb",
    "crafter",
    "brewing_stand",
    "furnace",
    "smoker",
    "blast_furnace",
    "trapped_chest",
    "lectern",
    "chiseled_bookshelf",
    "nether_portal",
    "shulker_box",
    "slime_block",
    "honey_block",
    "trial_spawner",
    "vault",
]

# Pattern id → principle blurb + knowledge cites (relative to project root)
_PRINCIPLE_BLURBS: dict[str, dict[str, Any]] = {
    "observer_clock": {
        "title": "观察者时钟嫌疑",
        "blurb": "相邻观察者互看/对着可更新块时，常形成极快时钟，驱动灯、活塞或发射器；生存需注意卡顿与烧毁风险。",
        "cites": [
            "docs/mc-knowledge/redstone/circuits-common.md",
            "docs/mc-knowledge/redstone/components.md",
        ],
    },
    "repeater_ring_clock": {
        "title": "中继器环时钟嫌疑",
        "blurb": "中继器首尾相接成有向环时可作时钟；周期约等于环上延迟档位之和（每档 1～4 红石 tick）。需先注入一次信号，断环即停。",
        "cites": [
            "docs/mc-knowledge/redstone/circuits-common.md",
            "docs/mc-knowledge/redstone/basics.md",
        ],
    },
    "hopper_clock_or_line": {
        "title": "漏斗钟 / 物品线嫌疑",
        "blurb": "成串漏斗多为物品传输；漏斗对吐 + 比较器读满度则是可调速漏斗钟，常见于农场与仓储。",
        "cites": [
            "docs/mc-knowledge/redstone/circuits-common.md",
            "docs/mc-knowledge/redstone/components.md",
        ],
    },
    "rs_latch_like": {
        "title": "RS 锁存嫌疑",
        "blurb": "两枚红石火把交叉互锁，或中继器锁定结构，可实现「按一次开、按另一次关」的记忆；请人工确认 SET/RESET 端。",
        "cites": [
            "docs/mc-knowledge/redstone/circuits-common.md",
        ],
    },
    "piston_mechanism": {
        "title": "活塞机械嫌疑",
        "blurb": "多枚活塞/粘性活塞与粉尘或中继器相邻时，常见于活塞门、推拉平台、隐藏楼梯；可能涉及 QC/BUD 与方块更新顺序，本阶段只给线索。",
        "cites": [
            "docs/mc-knowledge/redstone/qc-bud.md",
            "docs/mc-knowledge/redstone/block-updates.md",
            "docs/mc-knowledge/redstone/signals-timing.md",
            "docs/mc-knowledge/redstone/circuits-common.md",
        ],
    },
    "signal_bus": {
        "title": "信号总线 / 延迟链",
        "blurb": "粉尘负责传播（每格强度 -1，满电约 15 格）；中继器把任意输入抬到 15 并加 1～4 rt 延迟，用于续航和脉冲整形。穿过实心块续航需强充能（中继器顶方块）。",
        "cites": [
            "docs/mc-knowledge/redstone/basics.md",
            "docs/mc-knowledge/redstone/powering-charging.md",
            "docs/mc-knowledge/redstone/components.md",
        ],
    },
    "simple_input_output": {
        "title": "简单输入→输出",
        "blurb": "拉杆/按钮/压力板提供电源，红石灯/铜灯泡/音符盒等作输出；短距可直接邻接，较远需粉尘或中继器。",
        "cites": [
            "docs/mc-knowledge/redstone/basics.md",
            "docs/mc-knowledge/redstone/ai-constraints.md",
        ],
    },
    "decor_inputs": {
        "title": "偏装饰的弱红石",
        "blurb": "大量按钮/拉杆/压力板但几乎无粉尘与逻辑件时，多半是装饰开关；真正接线应进机房，避免客厅铺满粉尘。",
        "cites": [
            "docs/mc-knowledge/redstone/ai-constraints.md",
        ],
    },
    "rail_transport": {
        "title": "轨道运输",
        "blurb": "动力/探测/激活铁轨常与红石供电配合；本阶段只统计邻接，不模拟矿车时序。",
        "cites": [
            "docs/mc-knowledge/redstone/components.md",
        ],
    },
    "comparator_logic": {
        "title": "比较器测量 / 减法",
        "blurb": "比较器可读容器满度或做比较/减法模式，延迟固定 1 rt；常与漏斗、火把钟、物品分类一起出现。",
        "cites": [
            "docs/mc-knowledge/redstone/components.md",
            "docs/mc-knowledge/redstone/circuits-common.md",
        ],
    },
    "hopper_clock": {
        "title": "漏斗钟",
        "blurb": "两漏斗对吐并用比较器读一侧满度，可用物品数调节周期；稳定、适合农场。",
        "cites": ["docs/mc-knowledge/redstone/circuits-common.md", "docs/mc-knowledge/redstone/components.md"],
    },
    "torch_burn_clock": {
        "title": "火把烧灭钟嫌疑",
        "blurb": "火把与粉尘反馈可形成快速闪烁，但易烧毁且嘈杂；现代装置更常用中继器环或漏斗钟。",
        "cites": ["docs/mc-knowledge/redstone/circuits-common.md"],
    },
    "sculk_sensor_clockish": {
        "title": "幽匿感测振荡嫌疑",
        "blurb": "幽匿感测器把振动变成信号，邻近观察者/粉尘时可能形成触发环；非经典时钟，需实测。",
        "cites": ["docs/mc-knowledge/redstone/circuits-common.md"],
    },
    "qc_bud": {
        "title": "准连接 / BUD 线索",
        "blurb": "Java 活塞/发射器/投掷器会检查正上方一格充能（QC）。有 QC 无线接本体时可能 BUD 住，等方块更新才动。Bedrock 无 QC。",
        "cites": ["docs/mc-knowledge/redstone/qc-bud.md", "docs/mc-knowledge/redstone/block-updates.md", "docs/mc-knowledge/redstone/powering-charging.md", "docs/mc-knowledge/redstone/ai-constraints.md"],
    },

    "instant_wire": {
        "title": "瞬时导线嫌疑（仅概念/模板）",
        "blurb": "远距几乎同 tick 传信通常依赖活塞/特殊更新模板，不是粉尘升级。分析只标嫌疑；复刻须粘贴人工模板，禁止生成器发明。",
        "cites": [
            "docs/mc-knowledge/redstone/signals-timing.md",
            "docs/mc-knowledge/redstone/ai-constraints.md",
        ],
    },
    "pulse_extender": {
        "title": "脉冲延长嫌疑",
        "blurb": "短输入拉成更长电平（中继器串/比较器容器定时等）。延迟单位是红石 tick；与计划刻无关。",
        "cites": [
            "docs/mc-knowledge/redstone/circuits-common.md",
            "docs/mc-knowledge/redstone/signals-timing.md",
            "docs/mc-knowledge/redstone/tile-ticks.md",
        ],
    },
    "pulse_limiter": {
        "title": "脉冲缩短 / 边沿限制",
        "blurb": "把长电平收成短脉冲（粉尘短路、观察者、中继器差速）。报告区分 pulse vs level。",
        "cites": [
            "docs/mc-knowledge/redstone/circuits-common.md",
            "docs/mc-knowledge/redstone/signals-timing.md",
            "docs/mc-knowledge/redstone/powering-charging.md",
        ],
    },
    "zero_tick_bud_freerun": {
        "title": "零刻 / BUD 自走嫌疑",
        "blurb": "依赖方块更新与 QC 时序的高阶结构；简化仿真不对等。仅作线索，复刻用验证过的模板。",
        "cites": [
            "docs/mc-knowledge/redstone/block-updates.md",
            "docs/mc-knowledge/redstone/qc-bud.md",
            "docs/mc-knowledge/redstone/signals-timing.md",
        ],
    },
    "piston_door": {
        "title": "活塞门骨架",
        "blurb": "多活塞齐平门常涉 QC 与同 tick 伸出顺序；模板旋转后必须重测。",
        "cites": [
            "docs/mc-knowledge/redstone/qc-bud.md",
            "docs/mc-knowledge/redstone/signals-timing.md",
            "docs/mc-knowledge/redstone/block-updates.md",
        ],
    },
    "edge_detector": {
        "title": "边沿检测",
        "blurb": "观察者或脉冲限制器把变化变成短脉冲；与「方块更新可见」直接相关。",
        "cites": [
            "docs/mc-knowledge/redstone/block-updates.md",
            "docs/mc-knowledge/redstone/signals-timing.md",
            "docs/mc-knowledge/redstone/circuits-common.md",
        ],
    },
    "misc": {
        "title": "红石元件存在但模式不清",
        "blurb": "有红石相关方块，但未命中常见时钟/锁存/活塞门骨架；请结合朝向与游戏内实测判断。",
        "cites": [
            "docs/mc-knowledge/redstone/basics.md",
            "docs/mc-knowledge/redstone/circuits-common.md",
        ],
    },
}


def _short(name: str) -> str:
    n = str(name).strip()
    if n.startswith("minecraft:"):
        n = n[len("minecraft:") :]
    return n


def classify_redstone_kind(short: str) -> str | None:
    if short in ("redstone_wire", "redstone"):
        return "redstone_wire"
    if short in ("redstone_torch", "redstone_wall_torch"):
        return "redstone_torch"
    if short == "redstone_block":
        return "redstone_block"
    if short == "sticky_piston":
        return "sticky_piston"
    if short == "piston":
        return "piston"
    if short == "piston_head":
        return "piston_head"
    if short == "moving_piston":
        return "moving_piston"
    exact = {
        "repeater": "repeater",
        "comparator": "comparator",
        "lever": "lever",
        "observer": "observer",
        "hopper": "hopper",
        "dropper": "dropper",
        "dispenser": "dispenser",
        "note_block": "note_block",
        "target": "target",
        "redstone_lamp": "redstone_lamp",
        "daylight_detector": "daylight_detector",
        "powered_rail": "powered_rail",
        "detector_rail": "detector_rail",
        "activator_rail": "activator_rail",
        "rail": "rail",
        "sculk_sensor": "sculk_sensor",
        "calibrated_sculk_sensor": "sculk_sensor",
        "tripwire": "tripwire",
        "tripwire_hook": "tripwire",
        "crafter": "crafter",
        "brewing_stand": "brewing_stand",
        "furnace": "furnace",
        "smoker": "smoker",
        "blast_furnace": "blast_furnace",
        "trapped_chest": "trapped_chest",
        "lectern": "lectern",
        "chiseled_bookshelf": "chiseled_bookshelf",
        "nether_portal": "nether_portal",
        "slime_block": "slime_block",
        "honey_block": "honey_block",
        "trial_spawner": "trial_spawner",
        "vault": "vault",
    }
    if short in exact:
        return exact[short]
    if "copper_bulb" in short:
        return "copper_bulb"
    if short.endswith("_button"):
        return "button"
    if short.endswith("_pressure_plate"):
        return "pressure_plate"
    if "tripwire" in short:
        return "tripwire"
    if short == "iron_door":
        return "iron_door"
    if short.endswith("_door") or short == "door":
        return "door"
    if short.endswith("_trapdoor") or short == "trapdoor":
        return "trapdoor"
    if short.endswith("_fence_gate") or short == "fence_gate":
        return "fence_gate"
    if short.endswith("_shulker_box") or short == "shulker_box":
        return "shulker_box"
    return None


def role_of_kind(kind: str) -> str:
    return _KIND_ROLE.get(kind, "other")


def _props_at(props_list: list[dict[str, str]] | None, pid: int) -> dict[str, str]:
    if not props_list or pid < 0 or pid >= len(props_list):
        return {}
    return dict(props_list[pid] or {})


def _facing_of(kind: str, props: dict[str, str]) -> str | None:
    f = props.get("facing")
    if f in _FACING_DELTA:
        return f
    return None


def build_redstone_nodes(
    voxels,
    palette: list[str],
    props_list: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    """Collect redstone-related voxels as graph nodes."""
    import numpy as np

    nodes: list[dict[str, Any]] = []
    shorts = [_short(n) for n in palette]
    for pid, s in enumerate(shorts):
        kind = classify_redstone_kind(s)
        if not kind:
            continue
        mask = voxels == pid
        if not mask.any():
            continue
        props = _props_at(props_list, pid)
        xs, ys, zs = np.where(mask)
        for j in range(xs.size):
            x, y, z = int(xs[j]), int(ys[j]), int(zs[j])
            facing = _facing_of(kind, props)
            nodes.append(
                {
                    "pos": (x, y, z),
                    "kind": kind,
                    "role": role_of_kind(kind),
                    "block": s,
                    "facing": facing,
                    "face": props.get("face"),
                    "delay": props.get("delay"),
                    "powered": props.get("powered"),
                    "lit": props.get("lit"),
                    "extended": props.get("extended"),
                    "mode": props.get("mode"),
                    # dust wire shape (from BlockState Properties)
                    "wire_east": props.get("east"),
                    "wire_west": props.get("west"),
                    "wire_south": props.get("south"),
                    "wire_north": props.get("north"),
                    "wire_power": props.get("power"),
                }
            )
    return nodes


def _add_undirected(adj: dict, a: tuple, b: tuple, etype: str) -> None:
    if a == b:
        return
    adj[a].append({"to": b, "type": etype, "directed": False})
    adj[b].append({"to": a, "type": etype, "directed": False})


def _add_directed(adj: dict, a: tuple, b: tuple, etype: str) -> None:
    if a == b:
        return
    adj[a].append({"to": b, "type": etype, "directed": True})


def build_redstone_graph(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Heuristic adjacency among redstone nodes."""
    by_pos = {n["pos"]: n for n in nodes}
    positions = set(by_pos)
    adj: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    sx = max((p[0] for p in positions), default=0) + 1
    sy = max((p[1] for p in positions), default=0) + 1
    sz = max((p[2] for p in positions), default=0) + 1

    def in_bounds(p: tuple[int, int, int]) -> bool:
        x, y, z = p
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    neigh6 = list(_FACING_DELTA.values())

    for pos, node in by_pos.items():
        kind = node["kind"]
        facing = node.get("facing")

        # Always: undirected link to any RS 6-neighbor (composition glue)
        # Add once per pair (pos < npos) to avoid duplicates.
        for d in neigh6:
            npos = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
            if npos in positions and pos < npos:
                _add_undirected(adj, pos, npos, "adj6")

        if kind == "redstone_wire":
            for _name, d in _FACING_DELTA.items():
                npos = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
                if (
                    npos in positions
                    and by_pos[npos]["kind"] == "redstone_wire"
                    and pos < npos
                ):
                    _add_undirected(adj, pos, npos, "dust")

        if kind in ("repeater", "comparator") and facing:
            # Output along facing; input from opposite
            d_out = _FACING_DELTA[facing]
            d_in = _FACING_DELTA[_OPPOSITE[facing]]
            out_p = (pos[0] + d_out[0], pos[1] + d_out[1], pos[2] + d_out[2])
            in_p = (pos[0] + d_in[0], pos[1] + d_in[1], pos[2] + d_in[2])
            if in_p in positions:
                _add_directed(adj, in_p, pos, f"{kind}_in")
            if out_p in positions:
                _add_directed(adj, pos, out_p, f"{kind}_out")
            # side soft undirected already via adj6

        if kind == "observer" and facing:
            d_front = _FACING_DELTA[facing]
            d_back = _FACING_DELTA[_OPPOSITE[facing]]
            front = (pos[0] + d_front[0], pos[1] + d_front[1], pos[2] + d_front[2])
            back = (pos[0] + d_back[0], pos[1] + d_back[1], pos[2] + d_back[2])
            if front in positions:
                _add_directed(adj, front, pos, "observer_sense")
            if back in positions:
                _add_directed(adj, pos, back, "observer_out")

        if kind in ("piston", "sticky_piston", "hopper", "dropper", "dispenser") and facing:
            d = _FACING_DELTA[facing]
            front = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
            if front in positions:
                _add_directed(adj, pos, front, f"{kind}_face")


    # Shape-aware dust edges (incl. west=up vertical steps) from dust_connect
    dust_nodes = [n for n in nodes if n["kind"] == "redstone_wire"]
    if dust_nodes:
        try:
            dgraph = build_dust_adjacency(dust_nodes)
            for a, nset in (dgraph.get("adjacency") or {}).items():
                for b in nset:
                    if a < b:
                        _add_undirected(adj, a, b, "dust_shape")
        except Exception:
            pass

    # Deduplicate edges per undirected pair for counting
    edge_keys = set()
    edge_count = 0
    directed_count = 0
    for a, edges in adj.items():
        for e in edges:
            b = e["to"]
            if e["directed"]:
                directed_count += 1
                edge_keys.add(("D", a, b, e["type"]))
            else:
                lo, hi = (a, b) if a <= b else (b, a)
                key = ("U", lo, hi, e["type"])
                if key not in edge_keys:
                    edge_keys.add(key)
                    edge_count += 1

    return {
        "nodes": nodes,
        "adjacency": {f"{x},{y},{z}": v for (x, y, z), v in adj.items()},
        "undirected_edge_approx": edge_count,
        "directed_edge_approx": directed_count,
        "approximations": [
            "粉尘：6 邻接软连 + dust_connect 形状臂（含 up 垂直步进）",
            "中继器/比较器：有 facing 时建 输入←器件→输出 有向边",
            "观察者：探测面→观察者→背面输出 有向边",
            "活塞/漏斗/投掷/发射：沿 facing 软有向边",
            "不做 QC、不做实心块强弱充能传导、不做强度衰减与 tick 序",
        ],
    }


def connected_components_from_nodes(
    nodes: list[dict[str, Any]],
    graph: dict[str, Any],
) -> list[dict[str, Any]]:
    by_pos = {n["pos"]: n for n in nodes}
    neigh: dict[tuple[int, int, int], set[tuple[int, int, int]]] = defaultdict(set)
    for key, edges in (graph.get("adjacency") or {}).items():
        parts = key.split(",")
        a = (int(parts[0]), int(parts[1]), int(parts[2]))
        for e in edges:
            b = tuple(e["to"]) if not isinstance(e["to"], tuple) else e["to"]
            neigh[a].add(b)
            neigh[b].add(a)

    visited: set[tuple[int, int, int]] = set()
    comps: list[dict[str, Any]] = []
    for n in nodes:
        start = n["pos"]
        if start in visited:
            continue
        q = deque([start])
        visited.add(start)
        members: list[tuple[int, int, int]] = []
        while q:
            cur = q.popleft()
            members.append(cur)
            for nxt in neigh.get(cur, ()):
                if nxt not in visited and nxt in by_pos:
                    visited.add(nxt)
                    q.append(nxt)
        kinds = Counter(by_pos[p]["kind"] for p in members)
        roles = Counter(by_pos[p]["role"] for p in members)
        facings = Counter(
            by_pos[p]["facing"] for p in members if by_pos[p].get("facing")
        )
        delays = [
            by_pos[p].get("delay")
            for p in members
            if by_pos[p]["kind"] == "repeater" and by_pos[p].get("delay")
        ]
        # directed cycle check among members (repeater ring)
        has_cycle = _has_directed_cycle(members, graph, kinds)
        inference = infer_component_roles(kinds, roles, members, by_pos, has_cycle)
        comps.append(
            {
                "size": len(members),
                "kinds": dict(kinds),
                "roles": dict(roles),
                "facings": dict(facings),
                "repeater_delays": delays,
                "has_directed_cycle": has_cycle,
                "inferred": inference,
            }
        )
    comps.sort(key=lambda c: -c["size"])
    return comps


def _has_directed_cycle(
    members: list[tuple[int, int, int]],
    graph: dict[str, Any],
    kinds: Counter,
) -> bool:
    member_set = set(members)
    # only interesting if logic pieces present
    if kinds.get("repeater", 0) + kinds.get("comparator", 0) + kinds.get("observer", 0) < 2:
        return False
    succ: dict[tuple, list[tuple]] = defaultdict(list)
    for key, edges in (graph.get("adjacency") or {}).items():
        parts = key.split(",")
        a = (int(parts[0]), int(parts[1]), int(parts[2]))
        if a not in member_set:
            continue
        for e in edges:
            if not e.get("directed"):
                continue
            b = tuple(e["to"]) if not isinstance(e["to"], tuple) else e["to"]
            if b in member_set:
                succ[a].append(b)
    # DFS cycle
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {p: WHITE for p in members}

    def dfs(u: tuple) -> bool:
        color[u] = GRAY
        for v in succ.get(u, ()):
            if color[v] == GRAY:
                return True
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False

    for p in members:
        if color[p] == WHITE and dfs(p):
            return True
    return False


def infer_component_roles(
    kinds: Counter,
    roles: Counter,
    members: list[tuple],
    by_pos: dict,
    has_cycle: bool,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    wire = kinds.get("redstone_wire", 0)
    rep = kinds.get("repeater", 0)
    comp = kinds.get("comparator", 0)
    obs = kinds.get("observer", 0)
    pist = kinds.get("piston", 0) + kinds.get("sticky_piston", 0)
    hop = kinds.get("hopper", 0)
    torch = kinds.get("redstone_torch", 0)
    inputs = (
        kinds.get("lever", 0)
        + kinds.get("button", 0)
        + kinds.get("pressure_plate", 0)
    )
    outputs = (
        kinds.get("redstone_lamp", 0)
        + kinds.get("copper_bulb", 0)
        + kinds.get("note_block", 0)
    )
    rails = (
        kinds.get("rail", 0)
        + kinds.get("powered_rail", 0)
        + kinds.get("detector_rail", 0)
        + kinds.get("activator_rail", 0)
    )
    logic_or_wire = wire + rep + comp + obs + pist + hop + torch

    # observer adjacent pairs
    obs_pos = [p for p in members if by_pos[p]["kind"] == "observer"]
    obs_adj = False
    for i, a in enumerate(obs_pos):
        for b in obs_pos[i + 1 :]:
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) == 1:
                obs_adj = True
                break
    if obs >= 2 and obs_adj:
        out.append({"id": "observer_clock", "label": "观察者时钟候选", "confidence": "medium"})

    if has_cycle and rep >= 2:
        out.append({"id": "repeater_ring_clock", "label": "中继器环时钟候选", "confidence": "medium"})

    if hop >= 2 or (hop >= 1 and comp >= 1):
        out.append({"id": "hopper_clock_or_line", "label": "漏斗钟/输送线候选", "confidence": "low" if hop < 2 else "medium"})

    if torch >= 2 and pist == 0 and (wire >= 1 or torch >= 2):
        tpos = [p for p in members if by_pos[p]["kind"] == "redstone_torch"]
        near = False
        for i, a in enumerate(tpos):
            for b in tpos[i + 1 :]:
                if max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])) <= 2:
                    near = True
                    break
        if near:
            out.append({"id": "rs_latch_like", "label": "RS 锁存嫌疑（火把对）", "confidence": "low"})

    if pist >= 2 and (wire + rep + inputs + torch) >= 1:
        out.append({"id": "piston_mechanism", "label": "活塞门/推拉结构候选", "confidence": "medium"})
    elif pist >= 1 and torch >= 1:
        out.append({"id": "piston_mechanism", "label": "火把驱动活塞候选", "confidence": "low"})

    if (wire >= 3 and rep >= 2) or (rep >= 4):
        out.append({"id": "signal_bus", "label": "信号总线/延迟链", "confidence": "medium"})

    if comp >= 1:
        out.append({"id": "comparator_logic", "label": "比较器逻辑/测量", "confidence": "medium"})

    if rails >= 3:
        out.append({"id": "rail_transport", "label": "轨道运输", "confidence": "medium"})

    if inputs and outputs and logic_or_wire <= inputs + outputs:
        out.append({"id": "simple_input_output", "label": "简单输入→输出", "confidence": "medium"})

    if inputs >= 5 and logic_or_wire <= max(2, inputs // 10):
        out.append({"id": "decor_inputs", "label": "偏装饰弱红石", "confidence": "high"})

    if not out:
        if sum(kinds.values()) == 0:
            out.append({"id": "none", "label": "无红石", "confidence": "high"})
        else:
            out.append({"id": "misc", "label": "模式不明确", "confidence": "low"})
    return out


def _load_cite_snippet(path: Path, max_chars: int = 160, prefer_keywords: list[str] | None = None) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    paras: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            if buf:
                paras.append(" ".join(buf))
                buf = []
            # keep heading text as soft para
            heading = s.lstrip("#").strip()
            if heading:
                paras.append(heading)
            continue
        if not s or s.startswith("|") or s.startswith("---") or s.startswith(">"):
            if buf:
                paras.append(" ".join(buf))
                buf = []
            continue
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
        s = s.replace("**", "")
        buf.append(s)
    if buf:
        paras.append(" ".join(buf))
    prefer = [k.lower() for k in (prefer_keywords or []) if k]
    ranked: list[tuple[int, str]] = []
    for para in paras:
        if len(para) < 16:
            continue
        score = sum(1 for k in prefer if k in para.lower()) if prefer else 0
        ranked.append((score, para))
    if not ranked:
        return ""
    ranked.sort(key=lambda x: (-x[0], -len(x[1])))
    # if prefer matched, take best; else first reasonably long body para
    if prefer and ranked[0][0] > 0:
        para = ranked[0][1]
    else:
        para = next((p for _s, p in ranked if len(p) >= 40), ranked[0][1])
    return para[:max_chars].rstrip() + ("…" if len(para) > max_chars else "")


def build_principle_section(
    inferences: list[dict[str, str]],
    project_root: Path | None = None,
) -> list[dict[str, Any]]:
    root = project_root or Path(__file__).resolve().parents[2]
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for inf in inferences:
        pid = inf.get("id") or "misc"
        if pid in seen or pid == "none":
            continue
        seen.add(pid)
        meta = _PRINCIPLE_BLURBS.get(pid) or _PRINCIPLE_BLURBS["misc"]
        cites = []
        prefer = {
            "observer_clock": ["观察者", "时钟", "clock"],
            "repeater_ring_clock": ["中继器", "时钟", "环"],
            "hopper_clock_or_line": ["漏斗", "时钟"],
            "rs_latch_like": ["锁存", "RS", "火把"],
            "piston_mechanism": ["活塞", "QC", "门"],
            "signal_bus": ["粉尘", "中继器", "满电", "续航", "每经过"],
            "simple_input_output": ["拉杆", "按钮", "灯"],
            "decor_inputs": ["装饰", "弱红石"],
            "comparator_logic": ["比较器"],
            "rail_transport": ["铁轨", "轨道"],
            "hopper_clock": ["漏斗", "时钟"],
            "torch_burn_clock": ["火把", "时钟", "烧毁"],
            "sculk_sensor_clockish": ["幽匿", "振动"],
            "qc_bud": ["准连接", "QC", "BUD", "活塞"],
        }.get(pid, [meta.get("title", "")])
        for rel in meta.get("cites") or []:
            p = root / rel
            snippet = _load_cite_snippet(p, prefer_keywords=prefer)
            cites.append({"path": rel, "snippet": snippet})
        out.append(
            {
                "id": pid,
                "title": meta["title"],
                "blurb": meta["blurb"],
                "from_component_label": inf.get("label"),
                "confidence": inf.get("confidence"),
                "cites": cites,
            }
        )
    return out


def analyze_redstone(
    voxels,
    palette: list[str],
    props_list: list[dict[str, str]] | None = None,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Full Phase-1 redstone package for a schematic."""
    nodes = build_redstone_nodes(voxels, palette, props_list)
    inventory: Counter[str] = Counter(n["kind"] for n in nodes)
    role_counts: Counter[str] = Counter(n["role"] for n in nodes)
    full_inv = {k: int(inventory.get(k, 0)) for k in _KIND_ORDER}
    for k, v in inventory.items():
        full_inv[k] = int(v)

    graph = build_redstone_graph(nodes)
    components = connected_components_from_nodes(nodes, graph)
    strength = estimate_dust_strength(nodes, graph, voxels=voxels, palette=palette)
    qc_bud = detect_qc_bud(nodes, voxels, palette, strength)
    clocks = detect_clocks(nodes, graph)
    tick_sim = run_tick_simulation(
        nodes, graph, max_ticks=60, voxels=voxels, palette=palette
    )
    common_patterns = detect_common_patterns(
        nodes, graph, qc_bud=qc_bud, clocks=clocks,
        voxels=voxels, palette=palette,
    )

    # flatten inferences
    all_inf: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for c in components:
        for inf in c.get("inferred") or []:
            if inf["id"] not in seen_ids:
                seen_ids.add(inf["id"])
                all_inf.append(inf)
    # drop weak misc if stronger tags exist
    strong = [i for i in all_inf if i["id"] not in ("misc", "none")]
    if strong:
        all_inf = [i for i in all_inf if i["id"] != "misc"]
    # global soft tags
    plates_buttons = inventory.get("pressure_plate", 0) + inventory.get("button", 0)
    core = (
        inventory.get("redstone_wire", 0)
        + inventory.get("repeater", 0)
        + inventory.get("comparator", 0)
        + inventory.get("observer", 0)
        + inventory.get("piston", 0)
        + inventory.get("sticky_piston", 0)
    )
    if plates_buttons >= 8 and plates_buttons >= max(1, core):
        tag = {"id": "decor_inputs", "label": "大量踏板/按钮偏装饰", "confidence": "medium"}
        if tag["id"] not in seen_ids:
            seen_ids.add(tag["id"])
            all_inf.append(tag)
    if not nodes:
        all_inf = [{"id": "none", "label": "未检测到红石相关方块", "confidence": "high"}]

    # merge clock detections into inferences
    for clk in clocks.get("clocks") or []:
        cid = clk.get("id")
        if not cid or cid in seen_ids:
            continue
        seen_ids.add(cid)
        all_inf.append({
            "id": cid,
            "label": clk.get("label") or cid,
            "confidence": clk.get("confidence") or "low",
        })
    if qc_bud.get("qc_candidate_count") or qc_bud.get("bud_standby_suspect_count"):
        if "qc_bud" not in seen_ids:
            seen_ids.add("qc_bud")
            all_inf.append({
                "id": "qc_bud",
                "label": f"QC候选{qc_bud.get('qc_candidate_count',0)}/BUD嫌疑{qc_bud.get('bud_standby_suspect_count',0)}",
                "confidence": "medium" if qc_bud.get("qc_candidate_count") else "low",
            })

    # merge common patterns into inferences
    for pat in common_patterns.get("patterns") or []:
        pid = pat.get("id")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        all_inf.append({
            "id": pid,
            "label": pat.get("label") or pid,
            "confidence": pat.get("confidence") or "low",
        })

    principles = build_principle_section(all_inf, project_root=project_root)

    from src.app.redstone_principles import apply_principle_rules_to_analyze

    _rs_partial = {
        "global_inferences": all_inf,
        "common_patterns": common_patterns,
        "clocks": clocks,
        "qc_bud": qc_bud,
        "principles": principles,
        "total_redstone_blocks": len(nodes),
    }
    principle_rules = apply_principle_rules_to_analyze(
        _rs_partial, root=project_root or Path(__file__).resolve().parents[2]
    )
    principles = _rs_partial.get("principles") or principles

    # composition summary
    facing_known = sum(1 for n in nodes if n.get("facing"))
    composition = {
        "total": len(nodes),
        "inventory": full_inv,
        "inventory_nonzero": {k: v for k, v in full_inv.items() if v > 0},
        "roles": dict(role_counts),
        "facing_props_known": facing_known,
        "facing_props_missing": len(nodes) - facing_known,
        "taxonomy_note": (
            "角色桶：power_source / wire / logic / observer / piston / "
            "transport / sensor / output（同一块可偏输出兼传感，如音符盒归 output）"
        ),
    }

    return {
        "composition": composition,
        "graph": {
            "node_count": len(nodes),
            "undirected_edge_approx": graph["undirected_edge_approx"],
            "directed_edge_approx": graph["directed_edge_approx"],
            "approximations": graph["approximations"],
        },
        "components": components[:20],
        "component_count": len(components),
        "global_inferences": all_inf,
        "principles": principles,
        "principle_rules": principle_rules,
        "total_redstone_blocks": len(nodes),
        "inventory": full_inv,
        "inventory_nonzero": composition["inventory_nonzero"],
        "strength": strength,
        "qc_bud": qc_bud,
        "clocks": clocks,
        "common_patterns": common_patterns,
        "tick_sim": tick_sim,
        "no_tick_simulation": False,
        "note": "Phase 1：构成/图/强度/QC/结构钟/常用模式 + 简化 tick 仿真（非原版对等）。",
        # backward-compatible aliases used by older markdown bits
        "pattern_hints": [
            {"id": i["id"], "label": i["label"], "detail": f"confidence={i.get('confidence')}"}
            for i in all_inf
        ],
        "largest_components": components[:8],
        "component_sizes": [c["size"] for c in components[:15]],
    }


def redstone_to_markdown_sections(rs: dict[str, Any]) -> list[str]:
    """Expanded Chinese markdown blocks for section D."""
    lines: list[str] = []
    lines.append("## D. 红石")
    lines.append("")
    lines.append(f"- **红石相关方块总数**: {rs.get('total_redstone_blocks', 0)}")
    lines.append(f"- **说明**: {rs.get('note', '')}")
    lines.append("")

    # D1 构成
    lines.append("### D1. 构成（分类）")
    lines.append("")
    comp = rs.get("composition") or {}
    lines.append(f"- {comp.get('taxonomy_note', '')}")
    roles = comp.get("roles") or {}
    if roles:
        lines.append("- **角色桶计数**:")
        for k, v in sorted(roles.items(), key=lambda x: -x[1]):
            lines.append(f"  - `{k}`: {v}")
    lines.append(
        f"- **朝向属性**: 已知 {comp.get('facing_props_known', 0)} / "
        f"缺失 {comp.get('facing_props_missing', 0)} "
        f"（依赖 `load_litematic_detailed` 的 Properties）"
    )
    lines.append("- **元件清单**（含 0）:")
    lines.append("")
    lines.append("| 种类 | 数量 | 角色 |")
    lines.append("|------|------|------|")
    inv = rs.get("inventory") or comp.get("inventory") or {}
    for k in sorted(inv.keys(), key=lambda x: (-inv[x], x)):
        lines.append(f"| `{k}` | {inv[k]} | `{role_of_kind(k)}` |")
    lines.append("")

    # D2 连通
    lines.append("### D2. 连通组件")
    lines.append("")
    g = rs.get("graph") or {}
    lines.append(
        f"- **图规模**: 节点 {g.get('node_count', 0)}；"
        f"无向边约 {g.get('undirected_edge_approx', 0)}；"
        f"有向边约 {g.get('directed_edge_approx', 0)}"
    )
    lines.append("- **连边近似规则**:")
    for a in g.get("approximations") or []:
        lines.append(f"  - {a}")
    lines.append(
        f"- **无向连通分量数**: {rs.get('component_count', 0)}；"
        f"大小 Top: {rs.get('component_sizes', [])}"
    )
    for i, c in enumerate((rs.get("components") or rs.get("largest_components") or [])[:8], 1):
        lines.append(f"- **组件 #{i}** size={c.get('size')}")
        lines.append(f"  - 种类: {c.get('kinds')}")
        lines.append(f"  - 角色: {c.get('roles')}")
        if c.get("facings"):
            lines.append(f"  - facing 分布: {c.get('facings')}")
        if c.get("repeater_delays"):
            lines.append(f"  - 中继器 delay: {c.get('repeater_delays')}")
        if c.get("has_directed_cycle"):
            lines.append("  - 有向环: 是（时钟/环路嫌疑）")
        for inf in c.get("inferred") or []:
            lines.append(
                f"  - 推断: **{inf.get('label')}** (`{inf.get('id')}`, "
                f"confidence={inf.get('confidence')})"
            )
    lines.append("")

    # D3 原理
    # D3 强度
    lines.append("### D3. 信号强度（粉尘衰减启发）")
    lines.append("")
    st = rs.get("strength") or {}
    lines.append(
        f"- **粉尘格**: {st.get('dust_count', 0)}；"
        f"有电 {st.get('powered_dust', 0)}；"
        f"无电 {st.get('unpowered_dust', 0)}；"
        f"最大强度 {st.get('max_strength', 0)}"
    )
    if st.get("strength_hist"):
        lines.append(f"- **强度直方图**: {st.get('strength_hist')}")
    if st.get("source_kinds"):
        lines.append("- **注入源种类（次数）**:")
        for s in st["source_kinds"]:
            lines.append(f"  - `{s.get('via')}` × {s.get('injections')}")
    if st.get("sample_top"):
        lines.append("- **高强度粉尘样本** (pos → strength):")
        for s in st["sample_top"][:8]:
            lines.append(f"  - `{s.get('pos')}` → {s.get('strength')}")
    if st.get("opaque_strong_count") is not None:
        lines.append(
            f"- **实心块强充能**: {st.get('opaque_strong_count', 0)}；"
            f"**仅弱充能**: {st.get('opaque_weak_count', 0)}"
            "（弱充不点亮邻接粉尘，Java）"
        )
    if st.get("opaque_strong_sample"):
        lines.append("- **强充能实心样本**:")
        for s in st["opaque_strong_sample"][:8]:
            lines.append(
                f"  - `{s.get('pos')}` `{s.get('block')}` strong={s.get('strong')}"
            )
    dc = st.get("dust_connectivity") or {}
    if dc:
        lines.append(
            f"- **粉尘形状连通**: 边={dc.get('edge_count', 0)}"
            f"（soft={dc.get('soft_edge_count', 0)}）；"
            f"形状统计={dc.get('shape_hist')}"
        )
        if dc.get("inferred_arm_nodes"):
            lines.append(f"  - 缺 Properties 推断臂的粉尘格: {dc.get('inferred_arm_nodes')}")
        for s in (dc.get("samples") or [])[:6]:
            lines.append(
                f"  - `{s.get('pos')}` shape=**{s.get('shape')}** arms={s.get('arms')} "
                f"deg={s.get('degree')} schem_pow={s.get('schematic_power')}"
            )
        svd = dc.get("schematic_vs_computed") or {}
        if svd.get("with_power_prop"):
            lines.append(
                f"  - 与原理图 power 对照: 同意 {svd.get('agree')}/{svd.get('with_power_prop')}，"
                f"分歧 {svd.get('disagree')}"
            )
            for d in (svd.get("top_diffs") or [])[:4]:
                lines.append(
                    f"    - `{d.get('pos')}` schem={d.get('schematic')} vs computed={d.get('computed')}"
                )
        for a in (dc.get("limits") or [])[:3]:
            lines.append(f"  - _{a}_")
    comps = st.get("comparators") or []

    if comps:
        lines.append(f"- **比较器明细** ({len(comps)}):")
        for c in comps[:8]:
            truth = c.get("truth") or {}
            lines.append(
                f"  - @ `{c.get('pos')}` facing={c.get('facing')} "
                f"mode=**{c.get('mode')}** out={c.get('approx_output')} "
                f"[{c.get('approx_output_lower')}–{c.get('approx_output_upper')}] "
                f"rear={c.get('rear_kind')} rear_sig={c.get('rear_signal')} "
                f"side_max={c.get('side_signal_max', truth.get('side_max'))} "
                f"container={c.get('rear_container')}"
            )
            if truth.get("formula"):
                lines.append(f"    - 公式: `{truth.get('formula')}`")
            if c.get("side_inputs"):
                lines.append(f"    - 侧向输入: {c.get('side_inputs')}")
            if c.get("side_containers"):
                lines.append(f"    - 邻接容器启发: {c.get('side_containers')}")
            for note in (c.get("notes") or [])[:4]:
                lines.append(f"    - _{note}_")
            for cap in (c.get("caps") or [])[:2]:
                lines.append(f"    - 上限说明: _{cap}_")
    lines.append("- **近似规则**:")
    for a in st.get("limits") or []:
        lines.append(f"  - {a}")
    lines.append("")

    # D4 时钟
    lines.append("### D4. 时钟识别")
    lines.append("")
    clocks = rs.get("clocks") or {}
    lines.append(f"- **检出时钟线索数**: {clocks.get('count', 0)}")
    best = clocks.get("best")
    if best:
        lines.append(
            f"- **最强候选**: **{best.get('label')}** "
            f"(`{best.get('id')}`, confidence={best.get('confidence')}, "
            f"score={best.get('score')})"
        )
        if best.get("detail"):
            lines.append(f"  - {best.get('detail')}")
    for c in (clocks.get("clocks") or [])[:8]:
        lines.append(
            f"- **{c.get('label')}** (`{c.get('id')}`, "
            f"confidence={c.get('confidence')}, score={c.get('score')})"
        )
        if c.get("detail"):
            lines.append(f"  - {c.get('detail')}")
        if c.get("kinds"):
            lines.append(f"  - 环内种类: {c.get('kinds')}")
        if c.get("repeater_delays"):
            lines.append(f"  - 中继器 delay: {c.get('repeater_delays')}")
    if not (clocks.get("clocks")):
        lines.append("- （未识别到明确时钟骨架）")
    lines.append("- **局限**:")
    for a in clocks.get("limits") or []:
        lines.append(f"  - {a}")
    if clocks.get("kb_cite"):
        lines.append(f"- 参阅 [`{clocks['kb_cite']}`]({clocks['kb_cite']})")
    lines.append("")

    # D5 QC/BUD + observer face/output
    lines.append("### D5. QC / BUD / observer (Java coarse)")
    lines.append("")
    qc = rs.get("qc_bud") or {}
    lines.append(
        f"- **QC actuators**: {qc.get('qc_candidate_count', 0)}; "
        f"**BUD standby suspects**: {qc.get('bud_standby_suspect_count', 0)}; "
        f"**QC groups**: {qc.get('qc_group_count', len(qc.get('qc_groups') or []))}"
    )
    if qc.get("principle_rule_ids"):
        lines.append(
            "- **Principle rules**: "
            + ", ".join(f"`{r}`" for r in qc["principle_rule_ids"])
            + " (not a full update engine)"
        )
    for g in (qc.get("qc_groups") or [])[:6]:
        lines.append(
            f"- **QC group** size={g.get('size')} facings={g.get('facings')} "
            f"BUD_suspects={g.get('bud_suspects')} pos={g.get('positions')}"
        )
        if g.get("sample_reasons"):
            lines.append(f"  - reasons: {g.get('sample_reasons')}")
    for t in (qc.get("targets") or [])[:10]:
        flag = []
        if t.get("qc_candidate"):
            flag.append("QC")
        if t.get("bud_standby_suspect"):
            flag.append("BUD?")
        lines.append(
            f"- `{t.get('kind')}` @ `{t.get('pos')}` facing={t.get('facing')} "
            f"[{','.join(flag) or 'direct'}] confidence={t.get('confidence')}"
        )
        if t.get("qc_reasons"):
            lines.append(f"  - QC reasons: {t.get('qc_reasons')}")
        if t.get("direct_body_power"):
            lines.append(f"  - body power: {t.get('direct_body_power')}")
    obs_cat = qc.get("observers") or []
    if obs_cat:
        lines.append(
            f"- **Observers** ({qc.get('observer_count', len(obs_cat))}): "
            "face->watched / rear->output"
        )
        for o in obs_cat[:8]:
            lines.append(
                f"  - @ `{o.get('pos')}` face={o.get('facing')} "
                f"front={o.get('front')} watched={o.get('watched')} "
                f"rear={o.get('rear')} (out_dir={o.get('output_dir')})"
            )
    for o in (qc.get("observer_update_cues") or [])[:5]:
        lines.append(
            f"- observer update cue @ `{o.get('pos')}`: {o.get('label')} ({o.get('cue')})"
        )
    if not (qc.get("targets") or qc.get("observer_update_cues") or obs_cat):
        lines.append("- (no clear QC/BUD/observer cues)")
    if qc.get("coarse_rules"):
        lines.append("- **Coarse rules**:")
        for a in qc["coarse_rules"]:
            lines.append(f"  - {a}")
    lines.append("- **Limits**:")
    for a in qc.get("limits") or []:
        lines.append(f"  - {a}")
    if qc.get("kb_cite"):
        lines.append(f"- See [`{qc['kb_cite']}`]({qc['kb_cite']})")
    lines.append("")
    # D6 原理
    lines.append("### D6. 原理猜测（线索，非证明）")
    lines.append("")
    principles = rs.get("principles") or []
    prules = rs.get("principle_rules") or {}
    if prules.get("loaded"):
        lines.append(
            f"- **原理规则表**: [`{prules.get('rules_path')}`]({prules.get('rules_path')}) "
            f"(schema v{prules.get('schema_version')})"
        )
        lines.append(f"- **声明**: {prules.get('disclaimer')}")
        applied = prules.get("applied") or []
        if applied:
            lines.append(f"- **本图触发的规则** ({len(applied)}):")
            for rule in applied:
                trig = ", ".join(rule.get("triggered_by") or [])
                lines.append(
                    f"  - `{rule.get('id')}` **{rule.get('title')}** ← `{trig}`"
                )
                if rule.get("note_zh"):
                    lines.append(f"    - {rule.get('note_zh')}")
                cites = rule.get("cites") or []
                if cites:
                    lines.append("    - 依据: " + ", ".join(f"[`{c}`]({c})" for c in cites))
        lines.append("")
    if not principles:
        lines.append("- （无可用原理线索）")
    for pitem in principles:
        rid = pitem.get("principle_rule_ids") or []
        rid_s = f", rules={rid}" if rid else ""
        lines.append(
            f"- **{pitem.get('title')}** (`{pitem.get('id')}`, "
            f"confidence={pitem.get('confidence')}{rid_s})"
        )
        lines.append(f"  - {pitem.get('blurb')}")
        for cite in pitem.get("cites") or []:
            sn = cite.get("snippet") or ""
            via = f" _(via {cite.get('via')})_" if cite.get("via") else ""
            if sn:
                lines.append(f"  - 参阅 [`{cite.get('path')}`]({cite.get('path')}){via}：{sn}")
            else:
                lines.append(f"  - 参阅 [`{cite.get('path')}`]({cite.get('path')}){via}")
    lines.append("")

    # D9 常用模式
    lines.append("### D9. 常用电路模式")
    lines.append("")
    cp = rs.get("common_patterns") or {}
    lines.append(f"- **检出模式数**: {cp.get('count', 0)}")
    cats = cp.get("by_category") or {}
    if cats:
        nonempty = {k: len(v) for k, v in cats.items() if v}
        if nonempty:
            lines.append(f"- **分类计数**: {nonempty}")
    for pat in (cp.get("patterns") or [])[:12]:
        lines.append(
            f"- **{pat.get('label')}** (`{pat.get('id')}`, "
            f"confidence={pat.get('confidence')}, score={pat.get('score')})"
        )
        if pat.get("detail"):
            lines.append(f"  - {pat.get('detail')}")
    if not (cp.get("patterns")):
        lines.append("- （未识别到常用电路骨架；可能是纯建筑或红石过稀）")
    lines.append("- **局限**:")
    for a in cp.get("limits") or []:
        lines.append(f"  - {a}")
    lines.append("")

    # D7 局限
    lines.extend(tick_sim_to_markdown(rs.get("tick_sim") or {}))

    lines.append("### D8. 局限")
    lines.append("")
    lines.append("- **明确声明**: 已有 **简化 tick 仿真**（见 D7），但 **不是** Minecraft 红石引擎对等；QC/推动/物品 NBT 等仍大量省略。")
    lines.append("- 粉尘按形状臂连通；比较器/容器满度为启发；tick 仿真无推动方块；火把烧毁经 soft-lock；QC/BUD 为粗时序。")
    lines.append("- QC 只检查「上方格及相关邻接」常见形态；不模拟 BUD 更新传播时序。")
    lines.append("- 图连接偏宽松；原理段落为知识库摘要 + 启发式标签；`principle_rules` 为规则表触发记录（非引擎）。")
    lines.append("")
    return lines
