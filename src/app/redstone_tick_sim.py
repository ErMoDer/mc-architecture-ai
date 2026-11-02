# -*- coding: utf-8 -*-
"""Simplified discrete-tick redstone simulation (NOT Minecraft parity).

Updates per tick (coarse):
- Dust strength relax along shape arms (−1/step, cap 15)
- Repeater: delay queue (1–4 rt), output 15 or 0
- Comparator: compare/subtract from rear/side signals / container heuristic
- Torch: ON unless attachment powered; burnout after sustained rapid schedule (soft-lock first)
- Observer: 1-tick pulse on coarse 'update' cue
- Piston: direct vs QC (+1 tick) vs BUD-arm-until-neighbor-change; extend flag only

Hard limits documented in SIM_LIMITS / report.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from typing import Any

from src.app.dust_connect import build_dust_adjacency

_FACING = {
    "east": (1, 0, 0),
    "west": (-1, 0, 0),
    "up": (0, 1, 0),
    "down": (0, -1, 0),
    "south": (0, 0, 1),
    "north": (0, 0, -1),
}
_OPP = {
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up",
    "south": "north",
    "north": "south",
}
_HORIZ = ("east", "west", "south", "north")

# One simulation step == 1 redstone tick (rt). Java: 1 rt = 2 game ticks (gt).
TICK_UNIT = "rt"
GAME_TICKS_PER_SIM_TICK = 2
BUTTON_PULSE_RT = 10  # coarse: button/plate stays ON this many sim ticks from t=0

SIM_LIMITS = [
    "离散 tick 上限默认 60（可调 40–80）；**1 sim tick = 1 红石 tick (rt) = 2 game tick (gt)**，非逐 gt 全量引擎",
    "粉尘：沿形状臂 −1/格松弛；中继器/比较器顶实心块时粗模拟强充→邻接粉尘 15；无弱充穿块全图、无微更新序",
    "中继器：1–4 档延迟队列与侧向锁定近似；无锁定边沿特例",
    "比较器：compare/subtract + **1 rt 输出延迟**；容器满度启发档（默认 8）；无物品 NBT",
    "按钮/压力板：开局起粗脉冲 BUTTON_PULSE_RT 个 rt 后熄灭（无按压动画/实体站立）",
    "火把：1 rt 延迟翻转；60 rt 内≥8 次翻转先 soft-lock；再狂翻才烧毁",
    "观察者：face watched -> 1rt pulse; rear 15; may wake QC-BUD; no full NC/PP",
    "活塞：direct extend; QC above>=1rt then BUD arm; neighbor/observer wake; **no push**",
    "门/灯：邻接有电记开/亮（粗）",
    "绝非 Minecraft 红石引擎对等；见 docs/mc-knowledge/redstone/tile-ticks.md 与 signals-timing.md",
]


def _delay_of(n: dict[str, Any]) -> int:
    try:
        d = int(n.get("delay") or 1)
    except (TypeError, ValueError):
        d = 1
    return max(1, min(4, d))


def _container_signal(n: dict[str, Any], by_pos: dict, kind_at) -> int:
    """Heuristic fill → 0–15 when no inventory NBT."""
    # Allow schematic/meta override later; default half-full (stable for hopper clocks)
    try:
        if n.get("fill_signal") is not None:
            return max(0, min(15, int(n["fill_signal"])))
    except (TypeError, ValueError):
        pass
    return 8


def _is_opaque_for_strong(kind: str | None) -> bool:
    """Blocks that can be strongly powered and pass to adjacent dust (coarse)."""
    if not kind:
        return True
    transparent = {
        "redstone_wire", "redstone_torch", "repeater", "comparator",
        "piston", "sticky_piston", "piston_head", "hopper", "lever",
        "button", "pressure_plate", "observer", "air", "water", "lava",
        "door", "iron_door", "trapdoor", "fence_gate", "rail", "powered_rail",
        "detector_rail", "activator_rail", "scaffolding",
    }
    return kind not in transparent


def _rear_front(n: dict[str, Any]) -> tuple[tuple | None, tuple | None]:
    facing = n.get("facing")
    if not facing or facing not in _FACING:
        return None, None
    d_out = _FACING[facing]
    d_in = _FACING[_OPP[facing]]
    pos = n["pos"]
    front = (pos[0] + d_out[0], pos[1] + d_out[1], pos[2] + d_out[2])
    rear = (pos[0] + d_in[0], pos[1] + d_in[1], pos[2] + d_in[2])
    return rear, front


def run_tick_simulation(
    nodes: list[dict[str, Any]],
    graph: dict[str, Any] | None = None,
    *,
    max_ticks: int = 60,
    voxels=None,
    palette: list[str] | None = None,
) -> dict[str, Any]:
    """Run capped discrete-tick simulation; return summary + timeline samples."""
    max_ticks = max(40, min(80, int(max_ticks)))
    by_pos = {n["pos"]: n for n in nodes}
    dust_nodes = [n for n in nodes if n["kind"] == "redstone_wire"]
    dust_set = {n["pos"] for n in dust_nodes}
    dust_graph = build_dust_adjacency(dust_nodes)
    dust_nei = dust_graph["adjacency"]

    repeaters = [n for n in nodes if n["kind"] == "repeater"]
    comparators = [n for n in nodes if n["kind"] == "comparator"]
    torches = [n for n in nodes if n["kind"] == "redstone_torch"]
    observers = [n for n in nodes if n["kind"] == "observer"]
    pistons = [n for n in nodes if n["kind"] in ("piston", "sticky_piston")]
    door_nodes = [
        n for n in nodes
        if n["kind"] in ("door", "iron_door", "trapdoor", "fence_gate")
    ]
    lamp_nodes = [
        n for n in nodes
        if n["kind"] in ("redstone_lamp", "copper_bulb", "note_block")
    ]
    levers = [n for n in nodes if n["kind"] == "lever"]
    buttons = [n for n in nodes if n["kind"] in ("button", "pressure_plate")]
    rs_blocks = [n for n in nodes if n["kind"] == "redstone_block"]

    button_left: dict[tuple, int] = {
        n["pos"]: BUTTON_PULSE_RT for n in buttons
    }

    # state
    dust_s: dict[tuple, int] = {p: 0 for p in dust_set}
    # schematic baked power as optional initial (usually 0)
    for n in dust_nodes:
        try:
            dust_s[n["pos"]] = max(0, min(15, int(n.get("wire_power") or 0)))
        except ValueError:
            pass

    # repeater: queue of upcoming outputs (length=delay), current out
    rep_state: dict[tuple, dict[str, Any]] = {}
    for n in repeaters:
        d = _delay_of(n)
        powered0 = n.get("powered") == "true"
        rep_state[n["pos"]] = {
            "delay": d,
            "queue": deque([1 if powered0 else 0] * d),  # length==delay; popleft/append each tick
            "out": 15 if powered0 else 0,
            "locked": False,
            "node": n,
        }

    comp_out: dict[tuple, int] = {n["pos"]: 0 for n in comparators}
    # comparator 1-rt delay (Java comparator delay = 1 redstone tick)
    comp_queue: dict[tuple, int] = {n["pos"]: 0 for n in comparators}  # pending output
    comp_mode: dict[tuple, str] = {}
    torch_on: dict[tuple, bool] = {n["pos"]: True for n in torches}
    torch_burn: dict[tuple, bool] = {n["pos"]: False for n in torches}
    # 1 redstone-tick delay on torch state changes (Java-ish)
    torch_pending: dict[tuple, bool | None] = {n["pos"]: None for n in torches}
    # burnout: record flip tick times; soft-lock before permanent burn
    torch_flip_ticks: dict[tuple, list[int]] = {n["pos"]: [] for n in torches}
    torch_soft_lock_until: dict[tuple, int] = {n["pos"]: -1 for n in torches}
    torch_post_lock_flips: dict[tuple, int] = {n["pos"]: 0 for n in torches}
    obs_pulse: dict[tuple, int] = {n["pos"]: 0 for n in observers}  # ticks left
    observer_pulse_total = 0
    piston_ext: dict[tuple, bool] = {
        n["pos"]: n.get("extended") == "true" for n in pistons
    }

    # constant sources: redstone blocks always 15; levers if powered
    def lever_on(n: dict) -> bool:
        return n.get("powered") != "false"  # default on if unknown → optimistic

    # Track signature for periodicity: tuple of key outputs
    def snapshot() -> tuple:
        dust_sig = tuple(sorted((p, dust_s[p]) for p in dust_s if dust_s[p] > 0)[:24])
        rep_sig = tuple(sorted((p, st["out"]) for p, st in rep_state.items()))
        torch_sig = tuple(sorted((p, int(torch_on[p] and not torch_burn[p])) for p in torch_on))
        comp_sig = tuple(sorted((p, comp_out[p]) for p in comp_out))
        pist_sig = tuple(sorted((p, int(piston_ext[p])) for p in piston_ext))
        obs_sig = tuple(sorted((p, obs_pulse[p]) for p in obs_pulse))
        return (dust_sig, rep_sig, torch_sig, comp_sig, pist_sig, obs_sig)

    def cell_power_for_torch_attach(torch_pos: tuple) -> int:
        """Power into the *opaque attachment* block (floor torch → below).

        If below is dust/air/mechanism, do not treat it as attachment — avoids
        self-quench when a schematic places torch on top of redstone_wire.
        """
        below = (torch_pos[0], torch_pos[1] - 1, torch_pos[2])
        # non-opaque / dust under torch → no quench via that cell
        if below in dust_s:
            return 0
        if below in by_pos:
            k = by_pos[below]["kind"]
            if k in (
                "redstone_wire", "redstone_torch", "repeater", "comparator",
                "piston", "sticky_piston", "piston_head", "hopper", "lever",
                "button", "pressure_plate", "observer",
            ):
                return 0
        s = 0
        for d in _FACING.values():
            q = (below[0] + d[0], below[1] + d[1], below[2] + d[2])
            if q == torch_pos:
                continue  # ignore the torch cell itself
            if q in dust_s:
                s = max(s, dust_s[q])
            if q in rep_state and rep_state[q]["out"] > 0:
                rn = rep_state[q]["node"]
                facing = rn.get("facing")
                if facing:
                    fd = _FACING[facing]
                    front = (q[0] + fd[0], q[1] + fd[1], q[2] + fd[2])
                    if front == below:
                        s = 15
            if q in by_pos and by_pos[q]["kind"] == "redstone_block":
                s = 15
            if q in by_pos and by_pos[q]["kind"] == "redstone_torch":
                oth = q
                if torch_on.get(oth) and not torch_burn.get(oth) and oth != torch_pos:
                    # other torch adjacent to attachment — weak heuristic skip to reduce cross-talk
                    pass
        return s

    def inject_sources_into_dust(target: dict[tuple, int]) -> None:
        for n in rs_blocks:
            for d in _FACING.values():
                q = (n["pos"][0] + d[0], n["pos"][1] + d[1], n["pos"][2] + d[2])
                if q in target:
                    target[q] = max(target[q], 15)
        for n in torches:
            if torch_burn[n["pos"]] or not torch_on[n["pos"]]:
                continue
            for d in _FACING.values():
                q = (n["pos"][0] + d[0], n["pos"][1] + d[1], n["pos"][2] + d[2])
                if q in target:
                    target[q] = max(target[q], 15)
        for n in levers:
            if not lever_on(n):
                continue
            for d in _FACING.values():
                q = (n["pos"][0] + d[0], n["pos"][1] + d[1], n["pos"][2] + d[2])
                if q in target:
                    target[q] = max(target[q], 15)
        for p, st in rep_state.items():
            if st["out"] <= 0:
                continue
            facing = st["node"].get("facing")
            if not facing:
                continue
            fd = _FACING[facing]
            front = (p[0] + fd[0], p[1] + fd[1], p[2] + fd[2])
            if front in target:
                target[front] = max(target[front], 15)
        for p, outv in comp_out.items():
            if outv <= 0:
                continue
            n = by_pos[p]
            _, front = _rear_front(n)
            if front and front in target:
                target[front] = max(target[front], min(15, outv))
        for p, left in obs_pulse.items():
            if left <= 0:
                continue
            n = by_pos[p]
            facing = n.get("facing")
            if not facing:
                continue
            back = _FACING[_OPP[facing]]
            bp = (p[0] + back[0], p[1] + back[1], p[2] + back[2])
            if bp in target:
                target[bp] = max(target[bp], 15)
        for n in buttons:
            left = button_left.get(n["pos"], 0)
            if left <= 0:
                continue
            for d in _FACING.values():
                q = (n["pos"][0] + d[0], n["pos"][1] + d[1], n["pos"][2] + d[2])
                if q in target:
                    target[q] = max(target[q], 15)

    def relax_dust(seed: dict[tuple, int]) -> dict[tuple, int]:
        out = {p: 0 for p in dust_set}
        for p, v in seed.items():
            if p in out:
                out[p] = max(out[p], v)
        heap: list[tuple[int, tuple]] = []
        import heapq
        for p, v in out.items():
            if v > 0:
                heapq.heappush(heap, (-v, p))
        while heap:
            neg, p = heapq.heappop(heap)
            v = -neg
            if v != out[p] or v <= 1:
                continue
            nxt = v - 1
            for q in dust_nei.get(p, ()):
                if nxt > out[q]:
                    out[q] = nxt
                    heapq.heappush(heap, (-nxt, q))
        return out

    def signal_at(pos: tuple | None) -> int:
        if pos is None:
            return 0
        if pos in dust_s:
            return dust_s[pos]
        if pos in rep_state:
            return rep_state[pos]["out"]
        if pos in comp_out:
            return comp_out[pos]
        if pos in by_pos:
            k = by_pos[pos]["kind"]
            if k == "redstone_block":
                return 15
            if k == "redstone_torch" and torch_on.get(pos) and not torch_burn.get(pos):
                return 15
            if k in ("hopper", "chest", "barrel", "dropper", "dispenser", "furnace", "crafter"):
                return _container_signal(by_pos[pos], by_pos, None)
            if k == "lever" and lever_on(by_pos[pos]):
                return 15
        # Observer rear hard pulse (coarse)
        for on in observers:
            op = on["pos"]
            if obs_pulse.get(op, 0) <= 0:
                continue
            fac = on.get("facing")
            if not fac or fac not in _OPP:
                continue
            back = _FACING[_OPP[fac]]
            rear = (op[0] + back[0], op[1] + back[1], op[2] + back[2])
            if rear == pos:
                return 15
        return 0
    def piston_direct_power(n: dict) -> bool:
        """Body/side/below power only. Cell *above* is QC territory (not direct)."""
        pos = n["pos"]
        for name, d in _FACING.items():
            if name == "up":
                continue  # above-cell powering is QC, not direct
            q = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
            if signal_at(q) > 0:
                return True
            if q in by_pos and by_pos[q]["kind"] == "redstone_torch":
                if torch_on.get(q) and not torch_burn.get(q):
                    return True
            if q in by_pos and by_pos[q]["kind"] == "redstone_block":
                return True
        return False

    def piston_qc_power(n: dict) -> bool:
        """Java QC: power at the cell *above* the piston (or dust beside that cell)."""
        pos = n["pos"]
        ay = pos[1] + 1
        above = (pos[0], ay, pos[2])
        if signal_at(above) > 0:
            return True
        if above in by_pos and by_pos[above]["kind"] == "redstone_block":
            return True
        for name in _HORIZ:
            d = _FACING[name]
            side = (pos[0] + d[0], ay, pos[2] + d[2])
            if signal_at(side) > 0:
                return True
            if side in by_pos and by_pos[side]["kind"] == "redstone_block":
                return True
            # repeater/comparator pointing into above cell
            if side in rep_state and rep_state[side]["out"] > 0:
                rn = rep_state[side]["node"]
                fac = rn.get("facing")
                if fac:
                    fd = _FACING[fac]
                    if (side[0] + fd[0], side[1] + fd[1], side[2] + fd[2]) == above:
                        return True
            if side in comp_out and comp_out[side] > 0:
                cn = by_pos.get(side)
                if cn:
                    fac = cn.get("facing")
                    if fac:
                        fd = _FACING[fac]
                        if (side[0] + fd[0], side[1] + fd[1], side[2] + fd[2]) == above:
                            return True
        return False

    history_sig: list[tuple] = []
    timeline: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    event_counts: Counter[str] = Counter()
    # pick probe points: dust with neighbors, repeater outs, torches
    probes: list[dict[str, Any]] = []
    for n in dust_nodes[:6]:
        probes.append({"id": f"dust{n['pos']}", "kind": "dust", "pos": n["pos"]})
    for n in repeaters[:6]:
        probes.append({"id": f"rep{n['pos']}", "kind": "repeater", "pos": n["pos"]})
    for n in torches[:4]:
        probes.append({"id": f"torch{n['pos']}", "kind": "torch", "pos": n["pos"]})
    for n in comparators[:4]:
        probes.append({"id": f"cmp{n['pos']}", "kind": "comparator", "pos": n["pos"]})
    for n in pistons[:4]:
        probes.append({"id": f"pis{n['pos']}", "kind": "piston", "pos": n["pos"]})
    for n in observers[:4]:
        probes.append({
            "id": f"obs{n['pos']}",
            "kind": "observer",
            "pos": n["pos"],
            "facing": n.get("facing"),
        })

    prev_obs_env: dict[tuple, tuple] = {}
    # QC/BUD coarse state per piston
    piston_qc_stable: dict[tuple, int] = {n["pos"]: 0 for n in pistons}
    piston_bud_armed: dict[tuple, bool] = {n["pos"]: False for n in pistons}
    piston_prev_nb_sig: dict[tuple, tuple] = {}

    def piston_neighbor_signature(pos: tuple) -> tuple:
        vals = []
        for d in _FACING.values():
            q = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
            vals.append(signal_at(q))
        ay = pos[1] + 1
        for name in _HORIZ:
            d = _FACING[name]
            side = (pos[0] + d[0], ay, pos[2] + d[2])
            vals.append(signal_at(side))
        vals.append(signal_at((pos[0], ay, pos[2])))
        return tuple(vals)

    def _emit(tick: int, kind: str, **extra: Any) -> None:
        event_counts[kind] += 1
        if len(events) < 80:
            row = {"t": tick, "kind": kind}
            row.update(extra)
            events.append(row)

    def _strong_power_dust_from_outputs(target: dict[tuple, int]) -> None:
        """If repeater/comparator faces an opaque non-dust cell, feed 15 into adjacent dust (strong charge coarse)."""
        for p, st in rep_state.items():
            if st["out"] <= 0:
                continue
            facing = st["node"].get("facing")
            if not facing:
                continue
            fd = _FACING[facing]
            front = (p[0] + fd[0], p[1] + fd[1], p[2] + fd[2])
            if front in target:
                continue  # already handled as direct dust inject
            kind = by_pos[front]["kind"] if front in by_pos else None
            if front in by_pos and not _is_opaque_for_strong(kind):
                continue
            # treat missing / opaque as solid
            if front in by_pos and not _is_opaque_for_strong(kind):
                continue
            for d in _FACING.values():
                q = (front[0] + d[0], front[1] + d[1], front[2] + d[2])
                if q == p:
                    continue
                if q in target:
                    target[q] = max(target[q], 15)
        for p, outv in comp_out.items():
            if outv <= 0:
                continue
            n = by_pos[p]
            _, front = _rear_front(n)
            if not front or front in target:
                continue
            kind = by_pos[front]["kind"] if front in by_pos else None
            if front in by_pos and not _is_opaque_for_strong(kind):
                continue
            for d in _FACING.values():
                q = (front[0] + d[0], front[1] + d[1], front[2] + d[2])
                if q == p:
                    continue
                if q in target:
                    target[q] = max(target[q], min(15, outv))

    for tick in range(max_ticks):
        # 1) observer: face watches front; pulse 1 rt; rear outputs 15
        for n in observers:
            facing = n.get("facing")
            front = None
            rear = None
            if facing and facing in _FACING:
                fd = _FACING[facing]
                front = (n["pos"][0] + fd[0], n["pos"][1] + fd[1], n["pos"][2] + fd[2])
                bd = _FACING[_OPP[facing]]
                rear = (n["pos"][0] + bd[0], n["pos"][1] + bd[1], n["pos"][2] + bd[2])
            front_kind = None
            if front and front in by_pos:
                front_kind = by_pos[front]["kind"]
            env = (
                signal_at(front) if front else 0,
                piston_ext.get(front, False) if front else False,
                dust_s.get(front, 0) if front else 0,
                front_kind,
            )
            old = prev_obs_env.get(n["pos"])
            if old is not None and old != env:
                obs_pulse[n["pos"]] = 1
                observer_pulse_total += 1
                reasons = []
                if old[0] != env[0]:
                    reasons.append("front_signal")
                if old[1] != env[1]:
                    reasons.append("front_piston_ext")
                if old[2] != env[2]:
                    reasons.append("front_dust")
                if old[3] != env[3]:
                    reasons.append("front_kind")
                _emit(
                    tick,
                    "observer_pulse",
                    pos=list(n["pos"]),
                    facing=facing,
                    front=list(front) if front else None,
                    rear=list(rear) if rear else None,
                    reason="+".join(reasons) or "env_change",
                )
            prev_obs_env[n["pos"]] = env
        # 2) torches: 1-tick delay + soft-lock burnout (not brief-flip spam)
        for n in torches:
            p = n["pos"]
            if torch_burn[p]:
                torch_on[p] = False
                torch_pending[p] = None
                continue
            # apply pending state from previous tick (1 rt delay)
            if torch_pending[p] is not None:
                prev = torch_on[p]
                torch_on[p] = torch_pending[p]
                torch_pending[p] = None
                if torch_on[p] != prev:
                    torch_flip_ticks[p].append(tick)
                    torch_flip_ticks[p] = [ft for ft in torch_flip_ticks[p] if tick - ft < 60]
            # soft-lock: force OFF
            if tick < torch_soft_lock_until[p]:
                if torch_on[p]:
                    torch_on[p] = False
                torch_pending[p] = False
                continue
            attach_pow = cell_power_for_torch_attach(p)
            desired = attach_pow <= 0
            # schedule change for next tick if differs from current
            if desired != torch_on[p]:
                torch_pending[p] = desired
            recent = len(torch_flip_ticks[p])
            had_soft_lock = torch_soft_lock_until[p] >= 0
            after_lock = had_soft_lock and tick >= torch_soft_lock_until[p]
            if after_lock and recent >= 8:
                torch_burn[p] = True
                torch_on[p] = False
                torch_pending[p] = None
                _emit(tick, "torch_burn", pos=list(p))
                continue
            if (not had_soft_lock) and recent >= 8:
                torch_soft_lock_until[p] = tick + 3
                torch_flip_ticks[p] = []
                torch_post_lock_flips[p] = 0
                torch_on[p] = False
                torch_pending[p] = False
                _emit(tick, "torch_soft_lock", pos=list(p))
                continue

        # 3) comparators — compute desired, apply 1-rt delayed output
        for n in comparators:
            rear, front = _rear_front(n)
            mode = (n.get("mode") or "compare").lower()
            if "sub" in mode:
                mode = "subtract"
            else:
                mode = "compare"
            comp_mode[n["pos"]] = mode
            rear_s = signal_at(rear)
            # measuring: if rear is container, use fill heuristic
            if rear in by_pos and by_pos[rear]["kind"] in (
                "hopper", "chest", "barrel", "dropper", "dispenser", "furnace", "crafter",
            ):
                rear_s = max(rear_s, _container_signal(by_pos[rear], by_pos, None))
            side_max = 0
            facing = n.get("facing")
            if facing:
                for name in _HORIZ:
                    if name == facing or name == _OPP[facing]:
                        continue
                    d = _FACING[name]
                    sp = (n["pos"][0] + d[0], n["pos"][1] + d[1], n["pos"][2] + d[2])
                    side_max = max(side_max, signal_at(sp))
            if rear_s == 0:
                for name in _HORIZ:
                    d = _FACING[name]
                    sp = (n["pos"][0] + d[0], n["pos"][1] + d[1], n["pos"][2] + d[2])
                    if sp in by_pos and by_pos[sp]["kind"] in (
                        "hopper", "chest", "barrel", "dropper", "dispenser", "crafter",
                    ):
                        rear_s = max(rear_s, _container_signal(by_pos[sp], by_pos, None))
            if mode == "subtract":
                desired = max(0, rear_s - side_max)
            else:
                desired = rear_s if rear_s >= side_max else 0
            # 1 rt delay: publish previous pending, stage new desired
            prev_out = comp_out[n["pos"]]
            comp_out[n["pos"]] = comp_queue[n["pos"]]
            comp_queue[n["pos"]] = desired
            if comp_out[n["pos"]] != prev_out:
                _emit(tick, "comparator_out", pos=list(n["pos"]), mode=mode, value=comp_out[n["pos"]])

        # 4) repeaters: sample input, push queue
        for p, st in rep_state.items():
            n = st["node"]
            rear, front = _rear_front(n)
            inp = 1 if signal_at(rear) > 0 else 0
            # soft lock: side repeater/comparator powered
            locked = False
            facing = n.get("facing")
            if facing:
                for name in _HORIZ:
                    if name == facing or name == _OPP[facing]:
                        continue
                    d = _FACING[name]
                    sp = (p[0] + d[0], p[1] + d[1], p[2] + d[2])
                    if sp in rep_state and rep_state[sp]["out"] > 0:
                        locked = True
                    if sp in comp_out and comp_out[sp] > 0:
                        locked = True
            st["locked"] = locked
            if locked:
                # hold output; do not shift delay line
                pass
            else:
                # pop oldest (input from `delay` ticks ago), push new sample
                if st["queue"]:
                    out_bit = st["queue"].popleft()
                else:
                    out_bit = 0
                st["queue"].append(inp)
                st["out"] = 15 if out_bit else 0

        # 5) dust (+ coarse strong charge through opaque)
        seed = {p: 0 for p in dust_set}
        inject_sources_into_dust(seed)
        _strong_power_dust_from_outputs(seed)
        prev_dust_on = sum(1 for v in dust_s.values() if v > 0)
        dust_s = relax_dust(seed)
        dust_on = sum(1 for v in dust_s.values() if v > 0)
        if dust_on != prev_dust_on:
            _emit(tick, "dust_powered_count", count=dust_on)

        # 6) pistons — direct vs QC (>=1 rt) vs BUD arm; observer pulse = coarse update
        for n in pistons:
            pos = n["pos"]
            direct = piston_direct_power(n)
            qc = piston_qc_power(n)
            nb_sig = piston_neighbor_signature(pos)
            prev_nb = piston_prev_nb_sig.get(pos)
            nb_changed = prev_nb is not None and prev_nb != nb_sig
            obs_wake = False
            ay = pos[1] + 1
            check_cells = {(pos[0], ay, pos[2]), pos}
            for d in _FACING.values():
                check_cells.add((pos[0] + d[0], pos[1] + d[1], pos[2] + d[2]))
                check_cells.add((pos[0] + d[0], ay, pos[2] + d[2]))
            for on in observers:
                op = on["pos"]
                if obs_pulse.get(op, 0) <= 0:
                    continue
                if op in check_cells:
                    obs_wake = True
                    break
                fac = on.get("facing")
                if fac and fac in _FACING:
                    fd = _FACING[fac]
                    front = (op[0] + fd[0], op[1] + fd[1], op[2] + fd[2])
                    if front == pos or front == (pos[0], ay, pos[2]):
                        obs_wake = True
                        break
            if obs_wake:
                nb_changed = True
            piston_prev_nb_sig[pos] = nb_sig

            if direct:
                was = piston_ext[pos]
                piston_qc_stable[pos] = 0
                piston_bud_armed[pos] = False
                piston_ext[pos] = True
                if not was:
                    _emit(tick, "piston_extend_direct", pos=list(pos))
            elif qc:
                was_qc = piston_qc_stable[pos]
                piston_qc_stable[pos] += 1
                if was_qc == 0:
                    _emit(tick, "piston_qc_power", pos=list(pos), above=[pos[0], ay, pos[2]])
                if piston_qc_stable[pos] < 2:
                    pass
                elif piston_qc_stable[pos] >= 2:
                    if piston_ext[pos]:
                        piston_ext[pos] = True
                        piston_bud_armed[pos] = False
                    elif not piston_bud_armed[pos]:
                        piston_bud_armed[pos] = True
                        piston_ext[pos] = False
                        _emit(tick, "piston_bud_arm", pos=list(pos), via="qc")
                    elif nb_changed:
                        piston_ext[pos] = True
                        piston_bud_armed[pos] = False
                        _emit(
                            tick,
                            "piston_extend_bud",
                            pos=list(pos),
                            via="observer_wake" if obs_wake else "neighbor_sig",
                        )
            else:
                was_ext = piston_ext[pos]
                was_armed = piston_bud_armed[pos]
                piston_qc_stable[pos] = 0
                piston_bud_armed[pos] = False
                piston_ext[pos] = False
                if was_ext:
                    _emit(tick, "piston_retract", pos=list(pos))
                elif was_armed:
                    _emit(tick, "piston_bud_disarm", pos=list(pos))
        # 6b) button pulse countdown
        for n in buttons:
            p = n["pos"]
            if button_left.get(p, 0) > 0:
                button_left[p] -= 1
                if button_left[p] == 0:
                    _emit(tick, "button_pulse_end", pos=list(p))

        # 7) decay observer pulses
        for p in list(obs_pulse.keys()):
            if obs_pulse[p] > 0:
                # pulse active this tick; clear next
                pass
        # clear pulses at end of tick after being used in inject (already used at start next)
        for p in list(obs_pulse.keys()):
            if obs_pulse[p] > 0:
                obs_pulse[p] -= 1

        sig = snapshot()
        history_sig.append(sig)

        # timeline every tick for probes (compact)
        row = {"t": tick}
        for pr in probes:
            pos = pr["pos"]
            k = pr["kind"]
            if k == "dust":
                row[pr["id"]] = dust_s.get(pos, 0)
            elif k == "repeater":
                row[pr["id"]] = rep_state[pos]["out"]
            elif k == "torch":
                row[pr["id"]] = 0 if torch_burn[pos] else (15 if torch_on[pos] else 0)
            elif k == "comparator":
                row[pr["id"]] = comp_out.get(pos, 0)
            elif k == "piston":
                row[pr["id"]] = 1 if piston_ext.get(pos) else 0
        timeline.append(row)

    # analyze periodicity / stability
    period = None
    # search period in second half
    half = max_ticks // 2
    tail = history_sig[half:]
    for per in range(1, min(24, len(tail) // 2) + 1):
        ok = True
        for i in range(len(tail) - per):
            if tail[i] != tail[i + per]:
                ok = False
                break
        if ok and per < len(tail):
            # verify at least 2 full periods
            if len(tail) >= per * 2:
                period = per
                break

    stable = False
    if len(history_sig) >= 2 and all(
        history_sig[i] == history_sig[-1] for i in range(half, max_ticks)
    ):
        stable = True
        period = 0  # steady

    oscillating = period is not None and period > 0

    # burnout count
    burned = sum(1 for v in torch_burn.values() if v)

    # summarize final
    final_dust_on = sum(1 for v in dust_s.values() if v > 0)
    final_rep_on = sum(1 for st in rep_state.values() if st["out"] > 0)
    final_torch_on = sum(
        1 for p, on in torch_on.items() if on and not torch_burn[p]
    )
    final_pist = sum(1 for v in piston_ext.values() if v)

    def _cell_signal(pos: tuple) -> int:
        s = 0
        if pos in dust_s:
            s = max(s, dust_s[pos])
        for d in _FACING.values():
            q = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
            if q in dust_s:
                s = max(s, dust_s[q])
            if q in rep_state and rep_state[q]["out"] > 0:
                s = max(s, 15)
            if q in by_pos and by_pos[q]["kind"] == "redstone_block":
                s = 15
            if q in torch_on and torch_on[q] and not torch_burn.get(q, False):
                s = max(s, 15)
            if q in comp_out:
                s = max(s, comp_out[q])
        return s

    doors_powered = sum(1 for n in door_nodes if _cell_signal(n["pos"]) > 0)
    lamps_powered = sum(1 for n in lamp_nodes if _cell_signal(n["pos"]) > 0)


    # downsample timeline for report (every N ticks + last)
    step = max(1, max_ticks // 12)
    timeline_sample = [timeline[i] for i in range(0, max_ticks, step)]
    if timeline and timeline[-1] not in timeline_sample:
        timeline_sample.append(timeline[-1])

    probe_meta = [
        {"id": pr["id"], "kind": pr["kind"], "pos": list(pr["pos"])} for pr in probes
    ]

    behavior = "stable" if stable else ("oscillating" if oscillating else "transient_or_chaotic")
    period_note = None
    if stable:
        period_note = "后半段状态不变 → 稳态"
    elif oscillating:
        period_note = f"后半段近似周期 ≈ {period} tick（简化时钟）"
    else:
        period_note = "未检出清晰周期（可能无钟、或超出简化模型）"

    # principle KB hooks (tick-relevant rules)
    principle_rule_ids = [
        "tile_vs_redstone_tick",
        "strong_weak_charge",
        "nc_pp_block_update",
        "signals_timing_templates",
    ]
    try:
        from src.app.redstone_principles import load_principle_rules

        _rules = load_principle_rules()
        principle_cites = []
        for rule in _rules.get("rules") or []:
            if rule.get("id") in principle_rule_ids:
                principle_cites.append(
                    {
                        "id": rule["id"],
                        "title": rule.get("title"),
                        "cites": rule.get("cites") or [],
                        "note_zh": rule.get("note_zh"),
                    }
                )
    except Exception:
        principle_cites = []

    period_rt = period
    period_gt = None if period is None else (0 if period == 0 else period * GAME_TICKS_PER_SIM_TICK)

    return {
        "max_ticks": max_ticks,
        "tick_unit": TICK_UNIT,
        "game_ticks_per_sim_tick": GAME_TICKS_PER_SIM_TICK,
        "max_game_ticks_equiv": max_ticks * GAME_TICKS_PER_SIM_TICK,
        "behavior": behavior,
        "stable": stable,
        "oscillating": oscillating,
        "period_ticks": period,
        "period_rt": period_rt,
        "period_gt": period_gt,
        "period_note": period_note,
        "events": events,
        "event_counts": dict(event_counts),
        "principle_rule_ids": principle_rule_ids,
        "principle_cites": principle_cites,
        "final": {
            "dust_powered": final_dust_on,
            "dust_total": len(dust_set),
            "repeaters_on": final_rep_on,
            "torches_on": final_torch_on,
            "torches_burned": burned,
            "torches_soft_locked": sum(1 for p, u in torch_soft_lock_until.items() if u >= max_ticks - 1),
            "pistons_extended": final_pist,
            "pistons_bud_armed_end": sum(1 for v in piston_bud_armed.values() if v),
            "observers_total": len(observers),
            "observers_pulsed_total": observer_pulse_total,
            "comparators_nonzero": sum(1 for v in comp_out.values() if v > 0),
            "doors_powered": doors_powered,
            "doors_total": len(door_nodes),
            "lamps_powered": lamps_powered,
            "lamps_total": len(lamp_nodes),
        },
        "probes": probe_meta,
        "timeline_sample": timeline_sample,
        "dust_shape_edges": dust_graph.get("edge_count"),
        "limits": SIM_LIMITS,
        "note": "简化 tick 仿真（1 tick=1 rt=2 gt）：周期/稳态/事件线索，非原版对等、不推动方块。",
    }


def tick_sim_to_markdown(sim: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    lines.append("### D7. 简化 tick 仿真")
    lines.append("")
    if not sim:
        lines.append("- （无仿真结果）")
        lines.append("")
        return lines
    lines.append(f"- **说明**: {sim.get('note', '')}")
    lines.append(
        f"- **时间单位**: 1 sim tick = **1 红石 tick (rt)** = "
        f"**{sim.get('game_ticks_per_sim_tick', 2)} game tick (gt)**"
        f"（非逐 gt 引擎；计划刻见 `tile-ticks.md`）"
    )
    lines.append(
        f"- **仿真长度**: {sim.get('max_ticks')} rt"
        f"（约 {sim.get('max_game_ticks_equiv', (sim.get('max_ticks') or 0) * 2)} gt）"
    )
    lines.append(
        f"- **行为**: **{sim.get('behavior')}** — {sim.get('period_note')}"
    )
    if sim.get("period_rt"):
        lines.append(
            f"- **检出周期**: {sim.get('period_rt')} rt"
            + (f" ≈ {sim.get('period_gt')} gt" if sim.get("period_gt") else "")
        )
    elif sim.get("period_ticks") == 0 and sim.get("stable"):
        lines.append("- **检出周期**: 0（稳态）")
    fin = sim.get("final") or {}
    lines.append(
        f"- **终态**: 粉尘有电 {fin.get('dust_powered')}/{fin.get('dust_total')}；"
        f"中继器开 {fin.get('repeaters_on')}；"
        f"火把亮 {fin.get('torches_on')}（烧毁 {fin.get('torches_burned')}）；"
        f"比较器非零 {fin.get('comparators_nonzero')}；"
        f"活塞伸出 {fin.get('pistons_extended')}"
        f"（BUD待机 {fin.get('pistons_bud_armed_end', 0)}）；"
        f"门类开 {fin.get('doors_powered', 0)}/{fin.get('doors_total', 0)}；"
        f"灯类亮 {fin.get('lamps_powered', 0)}/{fin.get('lamps_total', 0)}"
    )
    if fin.get("observers_total") is not None:
        lines.append(
            f"- **Observers**: pulsed_total={fin.get('observers_pulsed_total', 0)}"
            f" / {fin.get('observers_total', 0)}"
        )
    ec = sim.get("event_counts") or {}
    if ec:
        top = ", ".join(f"{k}×{v}" for k, v in sorted(ec.items(), key=lambda kv: -kv[1])[:10])
        lines.append(f"- **事件计数**: {top}")
    ev = sim.get("events") or []
    if ev:
        lines.append("- **事件摘录**（最多 12 条）:")
        for e in ev[:12]:
            extra = {k: v for k, v in e.items() if k not in ("t", "kind")}
            lines.append(f"  - t={e.get('t')} `{e.get('kind')}` {extra}")
    prules = sim.get("principle_rule_ids") or []
    if prules:
        lines.append(
            "- **关联原理规则**: "
            + ", ".join(f"`{r}`" for r in prules)
            + " ← [`redstone_principles_rules.json`](docs/mc-knowledge/redstone/redstone_principles_rules.json)"
        )
    for cite in sim.get("principle_cites") or []:
        paths = ", ".join(f"[`{c}`]({c})" for c in (cite.get("cites") or [])[:3])
        lines.append(f"  - `{cite.get('id')}` {cite.get('title')}: {paths}")
    probes = sim.get("probes") or []
    if probes:
        lines.append("- **探针**:")
        for pr in probes[:12]:
            lines.append(f"  - `{pr.get('id')}` {pr.get('kind')} @ `{pr.get('pos')}`")
    tl = sim.get("timeline_sample") or []
    if tl and probes:
        keys = []
        seen_kind = set()
        for pr in probes:
            if pr["kind"] not in seen_kind or len(keys) < 3:
                keys.append(pr["id"])
                seen_kind.add(pr["kind"])
            if len(keys) >= 6:
                break
        if len(keys) < 6:
            for pr in probes:
                if pr["id"] not in keys:
                    keys.append(pr["id"])
                if len(keys) >= 6:
                    break
        header = "| t(rt) | " + " | ".join(keys) + " |"
        sep = "|---|" + "|".join(["---"] * len(keys)) + "|"
        lines.append("- **时间线抽样**（列单位：信号强度或 0/1）:")
        lines.append("")
        lines.append(header)
        lines.append(sep)
        for row in tl:
            cells = [str(row.get("t", ""))] + [str(row.get(k, "")) for k in keys]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    lines.append("- **硬性局限**:")
    for a in sim.get("limits") or []:
        lines.append(f"  - {a}")
    lines.append(
        "- **再次声明**: 本仿真 **不是** 原版红石引擎；无完整 NC/PP 计划队列、无活塞推方块、无物品 NBT。"
    )
    lines.append("")
    return lines
