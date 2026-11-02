# -*- coding: utf-8 -*-
"""Dust strength with strong/weak powering of opaque cubes + comparator detail.

Java-oriented heuristics (NOT tick-accurate):
- Strong power on opaque: repeater/comparator output into face; redstone_block
  on any adjacent face; redstone_torch strongly powers the block ABOVE it.
- Weak power on opaque: redstone dust on top of or orthogonally adjacent to it.
- Strongly powered opaque lights adjacent dust at that strength.
- Weakly powered opaque does NOT light adjacent dust (Java).
- Dust-to-dust: each step −1, cap 15.
- Comparators: read mode/subtract from Properties; rear container / side dust;
  output strength approximated; hard-power opaque in front when output > 0.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from heapq import heappop, heappush
from typing import Any

from src.app.dust_connect import build_dust_adjacency

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
_HORIZ = ("east", "west", "south", "north")

_AIR = frozenset({"air", "cave_air", "void_air", "structure_void"})

# Non-full / non-opaque for strong/weak cube power
_NON_OPAQUE_EXACT = frozenset({
    "redstone_wire", "redstone_torch", "redstone_wall_torch", "redstone_block",
    "repeater", "comparator", "lever", "tripwire", "tripwire_hook",
    "rail", "powered_rail", "detector_rail", "activator_rail",
    "ladder", "vine", "scaffolding", "cobweb", "torch", "wall_torch", "soul_torch",
    "piston", "sticky_piston", "piston_head", "moving_piston",
    "hopper", "dropper", "dispenser", "observer",
    "chest", "trapped_chest", "ender_chest", "barrel", "furnace", "blast_furnace",
    "smoker", "crafter", "brewing_stand", "lectern", "jukebox",
    "note_block", "redstone_lamp", "copper_bulb", "daylight_detector", "target",
    "bell", "composter", "cauldron", "water_cauldron", "lava_cauldron",
    "powder_snow_cauldron", "beacon", "conduit", "spawner",
})

_CONTAINER_KINDS = frozenset({
    "hopper", "dropper", "dispenser", "chest", "trapped_chest", "ender_chest",
    "barrel", "furnace", "blast_furnace", "smoker", "crafter", "brewing_stand",
    "lectern", "jukebox", "shulker_box",
})

_STRENGTH_LIMITS = [
    "强充能实心块：中继器/比较器输出顶面、红石块邻接面、火把正上方块 → 该块可照亮邻接粉尘",
    "弱充能实心块：粉尘在块顶或侧边 → 弱充；按 Java，弱充能块不照亮邻接粉尘",
    "粉尘互传：仅沿形状臂（Properties none/side/up）连通的邻尘每步 −1，封顶 15",
    "比较器：compare/subtract 真值用已知侧/背信号；容器无 NBT 时用满度启发档（默认半满≈8，powered 时抬升）；报告 upper/lower",
    "半砖/楼梯/活板等不按完整实心块强充；活塞/漏斗等机构块不当作可强充立方体",
    "不做：tick 序、粉尘十字形状、QC 空气格充能细节",
]


def _short(name: str) -> str:
    n = str(name).strip()
    return n[len("minecraft:"):] if n.startswith("minecraft:") else n


def is_opaque_cube(short: str) -> bool:
    if not short or short in _AIR or short in _NON_OPAQUE_EXACT:
        return False
    if short.endswith("_button") or short.endswith("_pressure_plate"):
        return False
    if short.endswith("_slab") or short.endswith("_stairs") or short.endswith("_carpet"):
        return False
    if short.endswith("_door") or short.endswith("_trapdoor") or short.endswith("_fence"):
        return False
    if short.endswith("_fence_gate") or short.endswith("_wall") or short.endswith("_sign"):
        return False
    if short.endswith("_pane") or "glass" in short:
        return False
    if short.startswith("potted_") or short.endswith("_sapling"):
        return False
    if "shulker_box" in short:
        return False
    return True


def _build_grid(voxels, palette: list[str]):
    sx, sy, sz = voxels.shape
    shorts = [_short(n) for n in palette]
    # pad lut
    mx = int(voxels.max()) if voxels.size else 0
    while len(shorts) <= mx:
        shorts.append("air")

    def at(x: int, y: int, z: int) -> str | None:
        if not (0 <= x < sx and 0 <= y < sy and 0 <= z < sz):
            return None
        return shorts[int(voxels[x, y, z])]

    opaque: set[tuple[int, int, int]] = set()
    for x in range(sx):
        for y in range(sy):
            for z in range(sz):
                s = shorts[int(voxels[x, y, z])]
                if is_opaque_cube(s):
                    opaque.add((x, y, z))
    return at, opaque, (sx, sy, sz)



# Container fill heuristic when chest/hopper NBT unavailable (0-15 redstone scale)
_CONTAINER_FILL_DEFAULT = 8  # ~half → signal 8
_CONTAINER_FILL_IF_POWERED = 15


def recompute_comparator_output(c: dict[str, Any], strength: dict[tuple, int] | None) -> None:
    """Apply compare/subtract truth given rear/side signal estimates."""
    strength = strength or {}
    mode = c.get("mode") or "compare"
    rear_sig = int(c.get("rear_signal") or 0)
    # prefer live dust strength at rear
    rear = tuple(c["rear"]) if c.get("rear") else None
    if rear is not None and rear in strength:
        rear_sig = max(rear_sig, int(strength[rear]))
        c["rear_signal_source"] = "dust_strength"
    side_max = 0
    side_sources = []
    for si in c.get("side_inputs") or []:
        sp = tuple(si["pos"])
        sv = int(strength.get(sp, 0))
        if si.get("kind") in ("redstone_block", "redstone_torch"):
            sv = max(sv, 15)
        if "signal" in si:
            sv = max(sv, int(si["signal"]))
        side_max = max(side_max, sv)
        side_sources.append({"pos": si["pos"], "signal": sv})
    c["side_signal_max"] = side_max
    c["side_signals"] = side_sources

    lower = 0
    upper = 15
    if c.get("rear_container") or c.get("side_containers"):
        # unknown fill: band
        lower = 0
        upper = 15
        rear_used = int(c.get("rear_signal") or _CONTAINER_FILL_DEFAULT)
        if c.get("powered_prop") == "true":
            rear_used = max(rear_used, 1)
            upper = 15
        rear_sig = max(rear_sig, rear_used)
        c["rear_signal"] = rear_sig
        c["container_fill_heuristic"] = rear_used
    else:
        rear_sig = max(rear_sig, int(c.get("rear_signal") or 0))
        c["rear_signal"] = rear_sig
        lower = upper = rear_sig  # known-ish

    if mode == "subtract":
        out = max(0, rear_sig - side_max)
        out_lo = max(0, (0 if c.get("rear_container") or c.get("side_containers") else rear_sig) - 15)
        out_hi = max(0, (15 if c.get("rear_container") or c.get("side_containers") else rear_sig) - 0)
        # tighter: side_max known from dust
        if side_sources or side_max:
            out_lo = max(0, (0 if (c.get("rear_container") or c.get("side_containers")) else rear_sig) - side_max)
            out_hi = max(0, (15 if (c.get("rear_container") or c.get("side_containers")) else rear_sig) - side_max)
        else:
            out_lo = out
            out_hi = out if not (c.get("rear_container") or c.get("side_containers")) else max(0, 15 - side_max)
    else:
        # compare
        if side_max > rear_sig:
            out = 0
        else:
            out = rear_sig
        if c.get("rear_container") or c.get("side_containers"):
            # if sides known high, may be 0; else band
            if side_max >= 15:
                out_lo, out_hi = 0, 0
            elif side_max > 0:
                out_lo = 0
                out_hi = 15 if 15 >= side_max else 0
                out = rear_sig if rear_sig >= side_max else 0
            else:
                out_lo, out_hi = 0, 15
                out = rear_sig
        else:
            out_lo = out_hi = out

    if c.get("powered_prop") == "true":
        out = max(out, 1)
        out_hi = max(out_hi, out)

    c["approx_output"] = int(out)
    c["approx_output_lower"] = int(min(out_lo, out_hi))
    c["approx_output_upper"] = int(max(out_lo, out_hi))
    c["truth"] = {
        "mode": mode,
        "rear_signal": rear_sig,
        "side_max": side_max,
        "formula": (
            f"max(0, rear({rear_sig})-side({side_max}))"
            if mode == "subtract"
            else f"rear({rear_sig}) if rear>=side({side_max}) else 0"
        ),
    }


def analyze_comparators(
    nodes: list[dict[str, Any]],
    at,
    by_pos: dict,
    strength: dict | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in nodes:
        if n["kind"] != "comparator":
            continue
        pos = n["pos"]
        facing = n.get("facing")
        mode = (n.get("mode") or "compare").lower()
        if "sub" in mode:
            mode = "subtract"
        else:
            mode = "compare"
        powered = n.get("powered")
        entry: dict[str, Any] = {
            "pos": list(pos),
            "facing": facing,
            "mode": mode,
            "powered_prop": powered,
            "rear": None,
            "rear_kind": None,
            "rear_container": False,
            "rear_signal": 0,
            "side_inputs": [],
            "side_containers": [],
            "front": None,
            "front_kind": None,
            "approx_output": 0,
            "approx_output_lower": 0,
            "approx_output_upper": 0,
            "notes": [],
            "caps": [
                "无容器 NBT：满度用启发档（默认 8≈半满），非真实物品数",
                "侧向非粉尘的软充能未完整建模",
            ],
        }
        if not facing or facing not in _FACING_DELTA:
            entry["notes"].append("缺少 facing，比较器分析降级")
            out.append(entry)
            continue
        d_out = _FACING_DELTA[facing]
        d_in = _FACING_DELTA[_OPPOSITE[facing]]
        rear = (pos[0] + d_in[0], pos[1] + d_in[1], pos[2] + d_in[2])
        front = (pos[0] + d_out[0], pos[1] + d_out[1], pos[2] + d_out[2])
        entry["rear"] = list(rear)
        entry["front"] = list(front)
        rear_node = by_pos.get(rear)
        front_node = by_pos.get(front)
        rear_name = at(*rear) if callable(at) else None
        front_name = at(*front) if callable(at) else None
        try:
            rear_name = at(*rear)
            front_name = at(*front)
        except Exception:
            pass
        entry["rear_kind"] = rear_node["kind"] if rear_node else rear_name
        entry["front_kind"] = front_node["kind"] if front_node else front_name

        rear_container = False
        if rear_node and rear_node["kind"] in _CONTAINER_KINDS:
            rear_container = True
        elif rear_name and (
            rear_name in _CONTAINER_KINDS
            or str(rear_name).endswith("_shulker_box")
            or "chest" in str(rear_name)
        ):
            rear_container = True
        entry["rear_container"] = rear_container

        side_containers = []
        for name in _HORIZ:
            d = _FACING_DELTA[name]
            sp = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
            sn = by_pos.get(sp)
            sn_name = None
            try:
                sn_name = at(*sp)
            except Exception:
                sn_name = None
            kind = sn["kind"] if sn else sn_name
            if kind and (
                kind in _CONTAINER_KINDS
                or (isinstance(kind, str) and (kind.endswith("_shulker_box") or "chest" in kind))
            ):
                side_containers.append({"dir": name, "kind": kind, "pos": list(sp)})
        if side_containers and not rear_container:
            entry["notes"].append(
                "背面无容器但水平邻接有容器——可能朝向与经典读容器不一致，按邻接启发读信"
            )
            # treat as container-backed for fill heuristic
            entry["rear_container"] = True
            entry["notes"].append("将邻接容器视为读信源（启发）")
        entry["side_containers"] = side_containers

        # rear signal seeds
        rear_signal = 0
        if rear_container or side_containers:
            rear_signal = (
                _CONTAINER_FILL_IF_POWERED
                if powered == "true"
                else _CONTAINER_FILL_DEFAULT
            )
            entry["notes"].append(
                f"容器满度未知，rear 信号启发={rear_signal}"
                + ("（powered 抬到满）" if powered == "true" else "（默认半满≈8）")
            )
        if rear_node:
            rk = rear_node["kind"]
            if rk == "redstone_wire":
                # leave to strength pass; seed 0
                entry["notes"].append("背面为粉尘：rear 信号取强度传播结果")
            elif rk in (
                "redstone_block",
                "redstone_torch",
                "repeater",
                "lever",
                "button",
                "pressure_plate",
            ):
                rear_signal = max(rear_signal, 15)
            elif rk == "comparator":
                rear_signal = max(rear_signal, 1)
        entry["rear_signal"] = rear_signal

        # side inputs (horizontal, not facing/rear axis)
        side_dust = []
        for name in _HORIZ:
            if name == facing or name == _OPPOSITE[facing]:
                continue
            d = _FACING_DELTA[name]
            sp = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
            sn = by_pos.get(sp)
            if not sn:
                continue
            if sn["kind"] == "redstone_wire":
                side_dust.append({"dir": name, "pos": list(sp), "kind": "redstone_wire"})
            elif sn["kind"] in (
                "repeater",
                "comparator",
                "redstone_block",
                "redstone_torch",
            ):
                sig = 15 if sn["kind"] in ("redstone_block", "redstone_torch") else 0
                side_dust.append(
                    {"dir": name, "pos": list(sp), "kind": sn["kind"], "signal": sig}
                )
        entry["side_inputs"] = side_dust

        recompute_comparator_output(entry, strength)
        out.append(entry)
    return out




def _schematic_power_diff(dust_nodes, strength: dict) -> dict:
    """Compare schematic baked power Property vs our computed strength."""
    diffs = []
    agree = 0
    have = 0
    for n in dust_nodes:
        sp = n.get("wire_power")
        if sp is None or sp == "":
            continue
        try:
            sp_i = int(sp)
        except ValueError:
            continue
        have += 1
        comp = int(strength.get(n["pos"], 0))
        if sp_i == comp:
            agree += 1
        else:
            diffs.append({"pos": list(n["pos"]), "schematic": sp_i, "computed": comp})
    diffs.sort(key=lambda d: -abs(d["schematic"] - d["computed"]))
    return {
        "with_power_prop": have,
        "agree": agree,
        "disagree": have - agree,
        "top_diffs": diffs[:8],
    }


def estimate_dust_strength(
    nodes: list[dict[str, Any]],
    graph: dict[str, Any],
    voxels=None,
    palette: list[str] | None = None,
) -> dict[str, Any]:
    """Strength on dust with opaque strong/weak powering."""
    by_pos = {n["pos"]: n for n in nodes}
    dust_set = {n["pos"] for n in nodes if n["kind"] == "redstone_wire"}

    empty = {
        "dust_count": len(dust_set),
        "powered_dust": 0,
        "unpowered_dust": len(dust_set),
        "max_strength": 0,
        "strength_hist": {},
        "strength_by_pos": {},
        "source_kinds": [],
        "sample_top": [],
        "opaque_strong_count": 0,
        "opaque_weak_count": 0,
        "opaque_strong_sample": [],
        "comparators": [],
        "limits": _STRENGTH_LIMITS,
    }
    if not dust_set and voxels is None:
        return empty

    at = None
    opaque: set[tuple[int, int, int]] = set()
    if voxels is not None and palette is not None:
        at, opaque, _shape = _build_grid(voxels, palette)
    else:
        def at(x, y, z):  # type: ignore
            return None

    # dust adjacency from shape arms (not raw 6-neigh)
    dust_nodes = [n for n in nodes if n["kind"] == "redstone_wire"]
    dust_graph = build_dust_adjacency(dust_nodes)
    dust_nei: dict[tuple, set[tuple]] = dust_graph["adjacency"]

    strength: dict[tuple, int] = {p: 0 for p in dust_set}
    strong: dict[tuple, int] = {}  # opaque -> strong level
    weak: dict[tuple, int] = {}  # opaque -> weak level
    sources: list[dict[str, Any]] = []

    def bump(mp: dict[tuple, int], pos: tuple, level: int) -> None:
        if pos not in opaque:
            return
        level = max(0, min(15, int(level)))
        if level > mp.get(pos, 0):
            mp[pos] = level

    def inject_dust(pos: tuple, level: int, why: str) -> None:
        if pos not in dust_set:
            return
        level = max(0, min(15, int(level)))
        if level > strength[pos]:
            strength[pos] = level
            sources.append({"dust": list(pos), "level": level, "via": why})

    comparators = analyze_comparators(nodes, at, by_pos, strength=None) if at else []

    # --- seed component sources ---
    for n in nodes:
        pos, kind = n["pos"], n["kind"]
        facing = n.get("facing")

        if kind == "redstone_block":
            for d in _FACING_DELTA.values():
                q = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
                bump(strong, q, 15)
                inject_dust(q, 15, "redstone_block_adj_dust")
        elif kind == "redstone_torch":
            # strong to block above; dust adjacent
            above = (pos[0], pos[1] + 1, pos[2])
            bump(strong, above, 15)
            for d in _FACING_DELTA.values():
                inject_dust((pos[0] + d[0], pos[1] + d[1], pos[2] + d[2]), 15, "redstone_torch")
        elif kind == "pressure_plate":
            # strongly powers the block beneath
            below = (pos[0], pos[1] - 1, pos[2])
            bump(strong, below, 15)
            for d in _FACING_DELTA.values():
                inject_dust((pos[0] + d[0], pos[1] + d[1], pos[2] + d[2]), 15, "pressure_plate")
        elif kind in ("lever", "button"):
            # face/facing: strongly power attachment block opposite to facing when known
            face = n.get("face")  # floor/wall/ceiling for lever
            facing = n.get("facing")
            attached = None
            if face == "floor" or kind == "button" and face == "floor":
                attached = (pos[0], pos[1] - 1, pos[2])
            elif face == "ceiling":
                attached = (pos[0], pos[1] + 1, pos[2])
            elif facing and facing in _FACING_DELTA:
                # wall: attachment is opposite to facing
                d = _FACING_DELTA[_OPPOSITE[facing]]
                attached = (pos[0] + d[0], pos[1] + d[1], pos[2] + d[2])
            if attached:
                bump(strong, attached, 15)
            for d in _FACING_DELTA.values():
                inject_dust((pos[0] + d[0], pos[1] + d[1], pos[2] + d[2]), 15, kind)
        elif kind == "daylight_detector":
            below = (pos[0], pos[1] - 1, pos[2])
            bump(strong, below, 15)
            for d in _FACING_DELTA.values():
                inject_dust((pos[0] + d[0], pos[1] + d[1], pos[2] + d[2]), 15, "daylight_detector")
        elif kind == "repeater" and facing:
            d_out = _FACING_DELTA[facing]
            d_in = _FACING_DELTA[_OPPOSITE[facing]]
            rear = (pos[0] + d_in[0], pos[1] + d_in[1], pos[2] + d_in[2])
            out_p = (pos[0] + d_out[0], pos[1] + d_out[1], pos[2] + d_out[2])
            rear_ok = rear in dust_set or (
                rear in by_pos and by_pos[rear]["kind"] in (
                    "repeater", "comparator", "redstone_torch", "redstone_block",
                    "lever", "button", "pressure_plate", "observer",
                )
            ) or n.get("powered") == "true"
            if rear_ok:
                inject_dust(out_p, 15, f"repeater_out:{facing}")
                bump(strong, out_p, 15)  # hard-power opaque in front
        elif kind == "observer" and facing:
            d_back = _FACING_DELTA[_OPPOSITE[facing]]
            back = (pos[0] + d_back[0], pos[1] + d_back[1], pos[2] + d_back[2])
            inject_dust(back, 15, "observer_out_pulse_approx")
            bump(strong, back, 15)

    # comparators from detailed analysis
    for c in comparators:
        facing = c.get("facing")
        approx = int(c.get("approx_output") or 0)
        if approx <= 0 or not facing:
            continue
        front = tuple(c["front"]) if c.get("front") else None
        if not front:
            continue
        inject_dust(front, approx, f"comparator_{c.get('mode')}_out")
        bump(strong, front, approx)

    # --- iterative relax: dust weak→opaque; strong opaque→dust; dust−1 ---
    def dust_propagate() -> bool:
        changed = False
        heap: list[tuple[int, tuple]] = []
        for p, s in strength.items():
            if s > 0:
                heappush(heap, (-s, p))
        while heap:
            neg_s, p = heappop(heap)
            s = -neg_s
            if s != strength[p]:
                continue
            # weak-power opaque under/beside this dust
            x, y, z = p
            below = (x, y - 1, z)
            if below in opaque:
                old = weak.get(below, 0)
                if s > old:
                    weak[below] = s
                    changed = True
            for name in _HORIZ:
                d = _FACING_DELTA[name]
                side = (x + d[0], y + d[1], z + d[2])
                if side in opaque:
                    old = weak.get(side, 0)
                    if s > old:
                        weak[side] = s
                        changed = True
            if s <= 1:
                continue
            nxt = s - 1
            for q in dust_nei.get(p, ()):
                if nxt > strength[q]:
                    strength[q] = nxt
                    sources.append({"dust": list(q), "level": nxt, "via": "dust_decay"})
                    heappush(heap, (-nxt, q))
                    changed = True
        return changed

    def strong_to_dust() -> bool:
        changed = False
        for pos, lvl in list(strong.items()):
            if lvl <= 0:
                continue
            x, y, z = pos
            for d in _FACING_DELTA.values():
                q = (x + d[0], y + d[1], z + d[2])
                if q in dust_set and lvl > strength[q]:
                    strength[q] = lvl
                    sources.append({"dust": list(q), "level": lvl, "via": "strong_opaque"})
                    changed = True
        return changed

    def refine_repeaters_comparators() -> bool:
        changed = False
        for n in nodes:
            kind = n["kind"]
            facing = n.get("facing")
            if kind not in ("repeater", "comparator") or not facing:
                continue
            d_out = _FACING_DELTA[facing]
            d_in = _FACING_DELTA[_OPPOSITE[facing]]
            rear = (n["pos"][0] + d_in[0], n["pos"][1] + d_in[1], n["pos"][2] + d_in[2])
            out_p = (n["pos"][0] + d_out[0], n["pos"][1] + d_out[1], n["pos"][2] + d_out[2])
            rear_s = strength.get(rear, 0)
            if rear_s <= 0 and rear in strong:
                rear_s = strong[rear]
            if rear_s <= 0 and rear in by_pos:
                if by_pos[rear]["kind"] in ("redstone_torch", "redstone_block", "lever", "button"):
                    rear_s = 15
            # container rear for comparator
            if kind == "comparator" and rear_s <= 0:
                for c in comparators:
                    if tuple(c.get("pos") or ()) == n["pos"]:
                        if c.get("rear_container") or c.get("side_containers"):
                            rear_s = 15
                        break
            if rear_s <= 0:
                continue
            out_level = 15 if kind == "repeater" else min(15, rear_s)  # comparator maintain approx
            # subtract refinement if sides have dust strength
            if kind == "comparator":
                for c in comparators:
                    if tuple(c.get("pos") or ()) == n["pos"] and c.get("mode") == "subtract":
                        side_max = 0
                        for si in c.get("side_inputs") or []:
                            sp = tuple(si["pos"])
                            side_max = max(side_max, strength.get(sp, 0))
                            if si.get("kind") in ("redstone_block", "redstone_torch"):
                                side_max = 15
                        out_level = max(0, rear_s - side_max)
                        break
            if out_p in dust_set and out_level > strength.get(out_p, 0):
                strength[out_p] = out_level
                sources.append({"dust": list(out_p), "level": out_level, "via": f"{kind}_refined"})
                changed = True
            if out_p in opaque and out_level > strong.get(out_p, 0):
                strong[out_p] = out_level
                changed = True
        return changed

    for _ in range(12):
        ch = False
        ch |= dust_propagate()
        ch |= strong_to_dust()
        ch |= refine_repeaters_comparators()
        # update comparator outputs from known dust strengths
        for c in comparators:
            recompute_comparator_output(c, strength)
        if not ch:
            break

    # weak must not feed dust — explicit no-op (documented)
    weak_only = {p: w for p, w in weak.items() if w > 0 and strong.get(p, 0) == 0}

    hist = Counter(strength.values()) if strength else Counter()
    powered = sum(1 for v in strength.values() if v > 0)
    sample = sorted(
        ({"pos": list(p), "strength": s} for p, s in strength.items() if s > 0),
        key=lambda r: -r["strength"],
    )[:12]

    src_compact = []
    seen_via = Counter()
    for s in sources:
        seen_via[s["via"].split(":")[0]] += 1
    for via, cnt in seen_via.most_common():
        src_compact.append({"via": via, "injections": cnt})

    strong_sample = sorted(
        ({"pos": list(p), "strong": s, "block": at(*p) if at else "?"} for p, s in strong.items() if s > 0),
        key=lambda r: -r["strong"],
    )[:10]

    return {
        "dust_count": len(dust_set),
        "powered_dust": powered,
        "unpowered_dust": len(dust_set) - powered,
        "max_strength": max(strength.values()) if strength else 0,
        "strength_hist": {str(k): int(v) for k, v in sorted(hist.items(), reverse=True)},
        "strength_by_pos": {f"{x},{y},{z}": s for (x, y, z), s in strength.items() if s > 0},
        "source_kinds": src_compact,
        "sample_top": sample,
        "opaque_strong_count": sum(1 for v in strong.values() if v > 0),
        "opaque_weak_count": len(weak_only),
        "opaque_strong_sample": strong_sample,
        "comparators": comparators,
        "dust_connectivity": {
            "shape_hist": dust_graph.get("shape_hist"),
            "edge_count": dust_graph.get("edge_count"),
            "soft_edge_count": dust_graph.get("soft_edge_count"),
            "inferred_arm_nodes": dust_graph.get("inferred_arm_nodes"),
            "samples": dust_graph.get("samples"),
            "limits": dust_graph.get("limits"),
            "schematic_vs_computed": _schematic_power_diff(dust_nodes, strength),
        },
        "limits": _STRENGTH_LIMITS,
    }
