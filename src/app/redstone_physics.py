# -*- coding: utf-8 -*-
"""Phase-1 redstone physics heuristics: strength decay, QC/BUD cues, clocks.

NOT a tick simulator. Approximations are documented on each public function
and echoed into the analysis report.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from heapq import heappop, heappush
from typing import Any

# [X,Y,Z] deltas
_FACING_DELTA: dict[str, tuple[int, int, int]] = {
    "east": (1, 0, 0),
    "west": (-1, 0, 0),
    "up": (0, 1, 0),
    "down": (0, -1, 0),
    "south": (0, 0, 1),
    "north": (0, 0, -1),
}
_OPPOSITE = {a: b for a, b in [
    ("east", "west"), ("west", "east"), ("up", "down"),
    ("down", "up"), ("south", "north"), ("north", "south"),
]}
_HORIZ = ("east", "west", "south", "north")

_AIRISH = frozenset({
    "air", "cave_air", "void_air", "structure_void",
    "redstone_wire", "redstone_torch", "redstone_wall_torch",
    "lever", "tripwire", "rail", "powered_rail", "detector_rail", "activator_rail",
    "repeater", "comparator", "ladder", "vine", "scaffolding",
})

_STRENGTH_LIMITS = [
    "粉尘：沿相邻粉尘每步强度 −1，封顶 15；从电源注入的粉尘记 15",
    "中继器：若背面收到 >0（粉尘/邻接启发式），输出侧粉尘记 15（忽略锁定与延迟）",
    "比较器：近似为「背面强度透传/维持」，不做比较/减法真值运算",
    "火把/红石块/拉杆按钮踏板：邻接粉尘注入 15（不区分强弱充能穿块）",
    "不模拟：实心块强弱充能传导网、粉尘形状十字连接、QC 充能空气格的完整规则、tick 序",
]

_QC_LIMITS = [
    "Java QC: piston/sticky/dispenser/dropper check cell above (see qc-bud.md)",
    "Coarse: dust/rs-block in/beside above-cell, or repeater/comparator into above-cell",
    "QC groups: adjacent QC-candidate pistons clustered as qc_groups",
    "BUD suspect: QC without direct body power (pattern only; not full BUD engine)",
    "Observer: face=watched / rear=1rt output; may replace legacy piston-BUD",
    "Not done: NC/PP order, BUD self-reset pulse, Bedrock, block pushing",
]


def _short(name: str) -> str:
    n = str(name).strip()
    return n[len("minecraft:"):] if n.startswith("minecraft:") else n


def _is_opaque_solid(short: str) -> bool:
    if short in _AIRISH:
        return False
    if short.endswith("_button") or short.endswith("_pressure_plate"):
        return False
    if short.endswith("_door") or short.endswith("_trapdoor") or short.endswith("_sign"):
        return False
    if "piston" in short or short in {
        "hopper", "dropper", "dispenser", "observer", "chest", "trapped_chest",
        "ender_chest", "barrel", "furnace", "note_block", "redstone_lamp",
        "daylight_detector", "target", "crafter",
    }:
        return False  # treat as non-full for soft-power path simplicity
    return True


def _build_lookups(nodes: list[dict[str, Any]]):
    by_pos = {n["pos"]: n for n in nodes}
    dust = {n["pos"] for n in nodes if n["kind"] == "redstone_wire"}
    return by_pos, dust


def estimate_dust_strength(nodes, graph, voxels=None, palette=None):
    """Delegate to redstone_strength (strong/weak opaque + comparators)."""
    from src.app.redstone_strength import estimate_dust_strength as _impl
    return _impl(nodes, graph, voxels=voxels, palette=palette)



def detect_qc_bud(
    nodes: list[dict[str, Any]],
    voxels,
    palette: list[str],
    strength: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Flag QC / BUD-ish piston & dispenser candidates (Java heuristics)."""
    import numpy as np

    by_pos = {n["pos"]: n for n in nodes}
    strength_map: dict[tuple, int] = {}
    if strength and strength.get("strength_by_pos"):
        for k, v in strength["strength_by_pos"].items():
            parts = k.split(",")
            strength_map[(int(parts[0]), int(parts[1]), int(parts[2]))] = int(v)

    sx, sy, sz = voxels.shape
    shorts = [_short(n) for n in palette]

    def cell_short(x: int, y: int, z: int) -> str | None:
        if not (0 <= x < sx and 0 <= y < sy and 0 <= z < sz):
            return None
        pid = int(voxels[x, y, z])
        if 0 <= pid < len(shorts):
            return shorts[pid]
        return None

    def dust_power_at(x: int, y: int, z: int) -> int:
        return int(strength_map.get((x, y, z), 0))

    def above_cell_powered(x: int, y: int, z: int) -> tuple[bool, list[str]]:
        """Is the cell directly above (x,y,z) heuristically powered?"""
        ay = y + 1
        reasons: list[str] = []
        if ay >= sy:
            return False, reasons
        # dust sitting in the above cell
        if (x, ay, z) in by_pos and by_pos[(x, ay, z)]["kind"] == "redstone_wire":
            reasons.append("dust_in_above_cell")
        if dust_power_at(x, ay, z) > 0:
            reasons.append(f"dust_strength_above={dust_power_at(x, ay, z)}")
        # redstone block in/above-adjacent
        for dx, dy, dz, lab in (
            (0, 0, 0, "block_in_above"),
            (1, 0, 0, "block_east"),
            (-1, 0, 0, "block_west"),
            (0, 0, 1, "block_south"),
            (0, 0, -1, "block_north"),
            (0, 1, 0, "block_up"),
        ):
            p = (x + dx, ay + dy, z + dz)
            if p in by_pos and by_pos[p]["kind"] == "redstone_block":
                reasons.append(lab)
        # dust on neighbors of above cell (classic QC floor wiring)
        for name in _HORIZ:
            d = _FACING_DELTA[name]
            p = (x + d[0], ay, z + d[2])
            if p in by_pos and by_pos[p]["kind"] == "redstone_wire":
                reasons.append(f"dust_beside_above:{name}")
            if dust_power_at(*p) > 0:
                reasons.append(f"powered_dust_beside_above:{name}")
        # repeater/comparator pointing into above cell or into solid at above
        for n in nodes:
            if n["kind"] not in ("repeater", "comparator") or not n.get("facing"):
                continue
            facing = n["facing"]
            d = _FACING_DELTA[facing]
            out = (n["pos"][0] + d[0], n["pos"][1] + d[1], n["pos"][2] + d[2])
            if out == (x, ay, z):
                reasons.append(f"{n['kind']}_into_above")
            # pointing into opaque solid that occupies above? rare
        # torch adjacent to above cell
        for d in _FACING_DELTA.values():
            p = (x + d[0], ay + d[1], z + d[2])
            if p in by_pos and by_pos[p]["kind"] == "redstone_torch":
                reasons.append("torch_near_above")
        # dedupe reasons
        reasons = list(dict.fromkeys(reasons))
        return bool(reasons), reasons

    def direct_body_power(x: int, y: int, z: int) -> list[str]:
        reasons = []
        for d in _FACING_DELTA.values():
            p = (x + d[0], y + d[1], z + d[2])
            if p not in by_pos:
                continue
            k = by_pos[p]["kind"]
            if k in (
                "redstone_wire", "redstone_torch", "redstone_block",
                "repeater", "comparator", "lever", "button", "pressure_plate",
            ):
                reasons.append(k)
        return list(dict.fromkeys(reasons))

    qc_targets = []
    for n in nodes:
        if n["kind"] not in ("piston", "sticky_piston", "dispenser", "dropper"):
            continue
        x, y, z = n["pos"]
        powered, reasons = above_cell_powered(x, y, z)
        body = direct_body_power(x, y, z)
        if not powered and not body:
            continue
        bud = bool(powered and not body)
        qc_targets.append(
            {
                "pos": [x, y, z],
                "kind": n["kind"],
                "facing": n.get("facing"),
                "qc_candidate": powered,
                "qc_reasons": reasons,
                "direct_body_power": body,
                "bud_standby_suspect": bud,
                "confidence": "medium" if powered and len(reasons) >= 2 else ("low" if powered or bud else "low"),
            }
        )

    # Observer catalog: face (watched) / rear (output); BUD-alternative cues
    observer_catalog = []
    observer_budish = []
    _OPP_LOCAL = {
        "north": "south", "south": "north", "east": "west", "west": "east",
        "up": "down", "down": "up",
    }
    for n in nodes:
        if n["kind"] != "observer":
            continue
        facing = n.get("facing")
        front = rear = None
        watched = None
        if facing and facing in _FACING_DELTA:
            d = _FACING_DELTA[facing]
            front = (n["pos"][0] + d[0], n["pos"][1] + d[1], n["pos"][2] + d[2])
            od = _OPP_LOCAL.get(facing)
            if od and od in _FACING_DELTA:
                bd = _FACING_DELTA[od]
                rear = (n["pos"][0] + bd[0], n["pos"][1] + bd[1], n["pos"][2] + bd[2])
            if front in by_pos:
                watched = by_pos[front]["kind"]
            else:
                watched = cell_short(*front) if front else None
        entry = {
            "pos": list(n["pos"]),
            "facing": facing,
            "front": list(front) if front else None,
            "rear": list(rear) if rear else None,
            "watched": watched,
            "output_dir": _OPP_LOCAL.get(facing) if facing else None,
        }
        observer_catalog.append(entry)
        note = None
        if watched in (
            "piston", "sticky_piston", "note_block", "redstone_lamp",
            "hopper", "dropper", "dispenser", "door", "trapdoor",
        ):
            note = f"faces_{watched}"
        elif watched and ("piston" in str(watched)):
            note = f"faces_block:{watched}"
        if note:
            observer_budish.append(
                {
                    "pos": list(n["pos"]),
                    "facing": facing,
                    "front": list(front) if front else None,
                    "rear": list(rear) if rear else None,
                    "cue": note,
                    "label": "observer may replace legacy piston-BUD detect",
                    "confidence": "medium" if "piston" in str(note) else "low",
                }
            )

    # Cluster adjacent QC-candidate pistons into groups
    qc_only = [t for t in qc_targets if t.get("qc_candidate")]
    parent: dict[tuple, tuple] = {}

    def _find(a: tuple) -> tuple:
        while parent.get(a, a) != a:
            parent[a] = parent.get(parent[a], parent[a])
            a = parent[a]
        return a

    def _union(a: tuple, b: tuple) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    for t in qc_only:
        p = tuple(t["pos"])
        parent.setdefault(p, p)
    for i, a in enumerate(qc_only):
        pa = tuple(a["pos"])
        for b in qc_only[i + 1 :]:
            pb = tuple(b["pos"])
            if abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2]) == 1:
                _union(pa, pb)
    groups_map: dict[tuple, list] = {}
    for t in qc_only:
        p = tuple(t["pos"])
        root = _find(p)
        groups_map.setdefault(root, []).append(t)
    qc_groups = []
    for members in groups_map.values():
        positions = [m["pos"] for m in members]
        qc_groups.append(
            {
                "size": len(members),
                "positions": positions,
                "kinds": sorted({m["kind"] for m in members}),
                "facings": sorted({m.get("facing") for m in members if m.get("facing")}),
                "bud_suspects": sum(1 for m in members if m.get("bud_standby_suspect")),
                "sample_reasons": list(
                    dict.fromkeys(r for m in members for r in (m.get("qc_reasons") or []))
                )[:6],
            }
        )
    qc_groups.sort(key=lambda g: -g["size"])

    qc_n = sum(1 for t in qc_targets if t["qc_candidate"])
    bud_n = sum(1 for t in qc_targets if t["bud_standby_suspect"])
    return {
        "qc_candidate_count": qc_n,
        "bud_standby_suspect_count": bud_n,
        "targets": qc_targets[:30],
        "qc_groups": qc_groups[:12],
        "qc_group_count": len(qc_groups),
        "observers": observer_catalog[:30],
        "observer_count": len(observer_catalog),
        "observer_update_cues": observer_budish[:20],
        "principle_rule_ids": ["nc_pp_block_update", "observer_face_pulse"],
        "coarse_rules": [
            "QC check cell = piston.pos + (0,+1,0) even if air",
            "Offset powering: dust/repeater beside that above-cell counts (heuristic)",
            "BUD = QC powered + no direct body power + waiting for update (pattern only)",
            "Observer: face=watched, rear=1rt hard pulse; not QC",
        ],
        "limits": _QC_LIMITS,
        "kb_cite": "docs/mc-knowledge/redstone/qc-bud.md",
    }



def _directed_successors(graph: dict[str, Any], allowed: set[tuple] | None = None):
    succ: dict[tuple, list[tuple]] = defaultdict(list)
    for key, edges in (graph.get("adjacency") or {}).items():
        parts = key.split(",")
        a = (int(parts[0]), int(parts[1]), int(parts[2]))
        if allowed is not None and a not in allowed:
            continue
        for e in edges:
            if not e.get("directed"):
                continue
            b = tuple(e["to"]) if not isinstance(e["to"], tuple) else e["to"]
            if allowed is not None and b not in allowed:
                continue
            succ[a].append(b)
    return succ


def _find_cycles(succ: dict[tuple, list[tuple]], max_cycles: int = 8) -> list[list[tuple]]:
    cycles: list[list[tuple]] = []
    color: dict[tuple, int] = {}
    stack: list[tuple] = []

    def dfs(u: tuple) -> None:
        if len(cycles) >= max_cycles:
            return
        color[u] = 1
        stack.append(u)
        for v in succ.get(u, ()):
            if color.get(v, 0) == 0:
                dfs(v)
            elif color.get(v) == 1:
                # cycle
                if v in stack:
                    i = stack.index(v)
                    cyc = stack[i:]
                    if len(cyc) >= 2:
                        cycles.append(list(cyc))
            if len(cycles) >= max_cycles:
                break
        stack.pop()
        color[u] = 2

    for node in list(succ.keys()):
        if color.get(node, 0) == 0:
            dfs(node)
    return cycles


def detect_clocks(
    nodes: list[dict[str, Any]],
    graph: dict[str, Any],
) -> dict[str, Any]:
    """Heuristic clock recognition with confidence scores."""
    by_pos = {n["pos"]: n for n in nodes}
    clocks: list[dict[str, Any]] = []

    # --- repeater / logic directed rings ---
    logic_pos = {
        n["pos"] for n in nodes
        if n["kind"] in ("repeater", "comparator", "redstone_wire", "redstone_torch", "observer")
    }
    succ = _directed_successors(graph, allowed=logic_pos)
    # also allow undirected dust as bidirectional for ring through dust
    for key, edges in (graph.get("adjacency") or {}).items():
        parts = key.split(",")
        a = (int(parts[0]), int(parts[1]), int(parts[2]))
        if a not in logic_pos:
            continue
        for e in edges:
            b = tuple(e["to"]) if not isinstance(e["to"], tuple) else e["to"]
            if b not in logic_pos:
                continue
            if not e.get("directed"):
                # dust-dust bidirectional soft
                if by_pos.get(a, {}).get("kind") == "redstone_wire" or by_pos.get(b, {}).get("kind") == "redstone_wire":
                    succ[a].append(b)
                    succ[b].append(a)

    cycles = _find_cycles(succ, max_cycles=12)
    for cyc in cycles:
        kinds = Counter(by_pos[p]["kind"] for p in cyc if p in by_pos)
        rep = kinds.get("repeater", 0)
        obs = kinds.get("observer", 0)
        torch = kinds.get("redstone_torch", 0)
        wire = kinds.get("redstone_wire", 0)
        delays = [
            by_pos[p].get("delay")
            for p in cyc
            if p in by_pos and by_pos[p]["kind"] == "repeater" and by_pos[p].get("delay")
        ]
        if rep >= 2 and obs == 0:
            conf = "high" if rep >= 3 else "medium"
            clocks.append(
                {
                    "id": "repeater_ring_clock",
                    "label": "中继器环时钟",
                    "confidence": conf,
                    "score": min(0.95, 0.45 + 0.1 * rep),
                    "cycle_size": len(cyc),
                    "kinds": dict(kinds),
                    "repeater_delays": delays,
                    "detail": "有向/粉尘桥接环路上存在 ≥2 中继器，疑似中继器钟（需注入一次信号）。",
                }
            )
        elif obs >= 2:
            clocks.append(
                {
                    "id": "observer_clock",
                    "label": "观察者环路时钟",
                    "confidence": "medium",
                    "score": min(0.9, 0.4 + 0.15 * obs),
                    "cycle_size": len(cyc),
                    "kinds": dict(kinds),
                    "detail": "环路含多枚观察者，可能为极快观察者钟。",
                }
            )
        elif torch >= 1 and wire >= 1 and rep >= 1:
            clocks.append(
                {
                    "id": "torch_burn_clock",
                    "label": "火把烧灭/脉冲钟嫌疑",
                    "confidence": "low",
                    "score": 0.35,
                    "cycle_size": len(cyc),
                    "kinds": dict(kinds),
                    "detail": "火把与粉尘/中继器成环，可能为火把钟（易烧毁，仅线索）。",
                }
            )

    # --- observer mutual / adjacent facing ---
    observers = [n for n in nodes if n["kind"] == "observer"]
    for i, a in enumerate(observers):
        for b in observers[i + 1 :]:
            pa, pb = a["pos"], b["pos"]
            manhattan = abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
            if manhattan != 1:
                continue
            mutual = False
            fa, fb = a.get("facing"), b.get("facing")
            if fa and fb:
                da, db = _FACING_DELTA[fa], _FACING_DELTA[fb]
                # A faces toward B and B toward A
                if (pa[0] + da[0], pa[1] + da[1], pa[2] + da[2]) == pb and (
                    pb[0] + db[0], pb[1] + db[1], pb[2] + db[2]
                ) == pa:
                    mutual = True
            clocks.append(
                {
                    "id": "observer_clock",
                    "label": "观察者互看/相邻时钟" if mutual else "观察者相邻时钟嫌疑",
                    "confidence": "high" if mutual else "medium",
                    "score": 0.9 if mutual else 0.55,
                    "positions": [list(pa), list(pb)],
                    "mutual_facing": mutual,
                    "detail": "两枚观察者相邻" + ("且互相正对" if mutual else "（朝向未互指，置信较低）"),
                }
            )

    # --- hopper clock: hoppers facing each other + comparator ---
    hoppers = [n for n in nodes if n["kind"] == "hopper"]
    comps = [n for n in nodes if n["kind"] == "comparator"]
    hopper_clock_hits = 0
    for i, a in enumerate(hoppers):
        fa = a.get("facing")
        if not fa:
            continue
        da = _FACING_DELTA[fa]
        front = (a["pos"][0] + da[0], a["pos"][1] + da[1], a["pos"][2] + da[2])
        for b in hoppers[i + 1 :]:
            fb = b.get("facing")
            if not fb:
                continue
            db = _FACING_DELTA[fb]
            b_front = (b["pos"][0] + db[0], b["pos"][1] + db[1], b["pos"][2] + db[2])
            facing_each = front == b["pos"] and b_front == a["pos"]
            if not facing_each:
                continue
            near_comp = False
            for c in comps:
                cp = c["pos"]
                for hp in (a["pos"], b["pos"]):
                    if max(abs(cp[0] - hp[0]), abs(cp[1] - hp[1]), abs(cp[2] - hp[2])) <= 1:
                        near_comp = True
            conf = "high" if near_comp else "medium"
            clocks.append(
                {
                    "id": "hopper_clock",
                    "label": "漏斗钟",
                    "confidence": conf,
                    "score": 0.85 if near_comp else 0.65,
                    "positions": [list(a["pos"]), list(b["pos"])],
                    "facing_each_other": True,
                    "comparator_nearby": near_comp,
                    "detail": "漏斗对吐" + ("+旁路比较器读满度" if near_comp else "") + "，经典可调速漏斗钟骨架。",
                }
            )
            hopper_clock_hits += 1

    if hopper_clock_hits == 0 and len(hoppers) >= 2 and comps:
        clocks.append(
            {
                "id": "hopper_clock",
                "label": "漏斗+比较器时钟/测量嫌疑",
                "confidence": "low",
                "score": 0.4,
                "hopper_count": len(hoppers),
                "comparator_count": len(comps),
                "detail": "有多漏斗与比较器但未检出对吐朝向，可能是漏斗钟或物品线读信。",
            }
        )

    # --- sculk sensor + observer / dust ---
    sculks = [n for n in nodes if n["kind"] == "sculk_sensor"]
    for s in sculks:
        near_obs = any(
            abs(s["pos"][0] - o["pos"][0]) + abs(s["pos"][1] - o["pos"][1]) + abs(s["pos"][2] - o["pos"][2]) <= 2
            for o in observers
        )
        near_dust = any(
            abs(s["pos"][0] - n["pos"][0]) + abs(s["pos"][1] - n["pos"][1]) + abs(s["pos"][2] - n["pos"][2]) <= 2
            for n in nodes if n["kind"] == "redstone_wire"
        )
        if near_obs or near_dust:
            clocks.append(
                {
                    "id": "sculk_sensor_clockish",
                    "label": "幽匿感测器触发环嫌疑",
                    "confidence": "low",
                    "score": 0.4 if near_obs else 0.3,
                    "pos": list(s["pos"]),
                    "detail": "幽匿感测器邻近观察者/粉尘，可能构成振动触发振荡（非经典时钟）。",
                }
            )

    # --- torch spam rapid clock (no full cycle needed) ---
    torches = [n for n in nodes if n["kind"] == "redstone_torch"]
    for t in torches:
        dust_adj = 0
        for d in _FACING_DELTA.values():
            q = (t["pos"][0] + d[0], t["pos"][1] + d[1], t["pos"][2] + d[2])
            if q in by_pos and by_pos[q]["kind"] == "redstone_wire":
                dust_adj += 1
        if dust_adj >= 2 and len(torches) >= 2:
            clocks.append(
                {
                    "id": "torch_burn_clock",
                    "label": "多火把粉尘烧灭钟嫌疑",
                    "confidence": "low",
                    "score": 0.3,
                    "detail": "火把邻接多段粉尘且火把≥2，可能快速闪烁/烧毁型时钟。",
                }
            )
            break

    # dedupe by id keeping highest score
    best: dict[str, dict[str, Any]] = {}
    for c in clocks:
        cid = c["id"]
        if cid not in best or c.get("score", 0) > best[cid].get("score", 0):
            best[cid] = c
    # also keep multiple observer pairs? keep list of all but summarize unique ids
    ranked = sorted(clocks, key=lambda x: -x.get("score", 0))
    uniq: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_pos: set = set()
    for c in ranked:
        cid = c["id"]
        pos_key = tuple(sorted(map(tuple, c.get("positions") or [])))
        if cid in seen_ids and c.get("score", 0) < 0.8:
            continue
        if pos_key and pos_key in seen_pos:
            continue
        if cid in seen_ids and not pos_key:
            continue
        seen_ids.add(cid)
        if pos_key:
            seen_pos.add(pos_key)
        # allow a second high-score distinct pair for same id
        if sum(1 for u in uniq if u["id"] == cid) >= 2:
            continue
        uniq.append(c)

    return {
        "count": len(uniq),
        "clocks": uniq[:15],
        "best": uniq[0] if uniq else None,
        "limits": [
            "环路检测基于有向边 + 粉尘双向桥接，可能漏检隔空/QC 钟，也可能误报装饰环",
            "漏斗钟依赖 hopper facing；缺 Properties 时置信下降",
            "不做 tick 级周期测量与烧毁判定",
        ],
        "kb_cite": "docs/mc-knowledge/redstone/circuits-common.md",
    }
