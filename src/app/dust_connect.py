# -*- coding: utf-8 -*-
"""Redstone dust shape / arm connectivity (Java-ish heuristics)."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

_HORIZ = ("east", "west", "south", "north")
_DELTA = {
    "east": (1, 0, 0),
    "west": (-1, 0, 0),
    "south": (0, 0, 1),
    "north": (0, 0, -1),
}
_OPP = {"east": "west", "west": "east", "south": "north", "north": "south"}

_CONN_NONE = frozenset({"none", "", "0"})
_CONN_ON = frozenset({"side", "up"})


def _arm(props: dict[str, str] | None, direction: str) -> str:
    if not props:
        return ""
    return str(props.get(direction, "none") or "none").lower()


def dust_props_from_node(n: dict[str, Any]) -> dict[str, str]:
    """Normalize dust connection props from a redstone node."""
    return {
        "east": str(n.get("wire_east") or n.get("east") or "none"),
        "west": str(n.get("wire_west") or n.get("west") or "none"),
        "south": str(n.get("wire_south") or n.get("south") or "none"),
        "north": str(n.get("wire_north") or n.get("north") or "none"),
        "power": str(n.get("wire_power") or n.get("power") or ""),
    }


def infer_arms_from_neighbors(
    pos: tuple[int, int, int],
    dust_set: set[tuple[int, int, int]],
) -> dict[str, str]:
    """When Properties missing: arm toward any orthogonal dust (incl. up-step)."""
    x, y, z = pos
    arms = {d: "none" for d in _HORIZ}
    for d, (dx, dy, dz) in _DELTA.items():
        same = (x + dx, y, z + dz)
        up = (x + dx, y + 1, z + dz)
        down = (x + dx, y - 1, z + dz)
        if same in dust_set:
            arms[d] = "side"
        elif up in dust_set:
            arms[d] = "up"
        elif down in dust_set:
            # neighbor dust one below: our wire may connect down their up
            arms[d] = "side"
    return arms


def resolve_dust_arms(
    n: dict[str, Any],
    dust_set: set[tuple[int, int, int]],
) -> dict[str, str]:
    props = dust_props_from_node(n)
    has_any = any(_arm(props, d) not in _CONN_NONE for d in _HORIZ)
    # also treat explicit all-none with power field as "has props"
    has_props = any(k in (n or {}) for k in (
        "wire_east", "wire_west", "wire_south", "wire_north", "east", "west", "south", "north",
    )) or has_any or props.get("power") != ""
    if has_props and (has_any or props.get("power") != ""):
        # trust props; if all none but power set, still use props (dot)
        return {d: _arm(props, d) or "none" for d in _HORIZ} | {"power": props.get("power", "")}
    inferred = infer_arms_from_neighbors(n["pos"], dust_set)
    inferred["power"] = props.get("power", "")
    inferred["_inferred"] = "1"
    return inferred


def shape_name(arms: dict[str, str]) -> str:
    active = [d for d in _HORIZ if arms.get(d, "none") not in _CONN_NONE]
    n = len(active)
    if n == 0:
        return "dot"
    if n == 1:
        return "end"
    if n == 2:
        a, b = active
        if _OPP[a] == b:
            return "line"
        return "corner"
    if n == 3:
        return "T"
    return "cross"


def dust_connected(
    a_pos: tuple[int, int, int],
    a_arms: dict[str, str],
    b_pos: tuple[int, int, int],
    b_arms: dict[str, str],
) -> tuple[bool, str]:
    """Whether two dust cells share a connection along an arm."""
    ax, ay, az = a_pos
    bx, by, bz = b_pos
    dx, dy, dz = bx - ax, by - ay, bz - az

    # same-level cardinal
    if dy == 0 and abs(dx) + abs(dz) == 1:
        if dx == 1:
            d_ab, d_ba = "east", "west"
        elif dx == -1:
            d_ab, d_ba = "west", "east"
        elif dz == 1:
            d_ab, d_ba = "south", "north"
        else:
            d_ab, d_ba = "north", "south"
        a_on = a_arms.get(d_ab, "none") not in _CONN_NONE
        b_on = b_arms.get(d_ba, "none") not in _CONN_NONE
        if a_on and b_on:
            return True, d_ab
        # one-sided props (stale schematic): allow if either side claims connection
        # and the other is dust — soft heuristic
        if a_on or b_on:
            return True, d_ab + "_soft"
        return False, ""

    # vertical step: B is up-east etc. from A
    if abs(dx) + abs(dz) == 1 and dy == 1:
        if dx == 1:
            d_ab = "east"
        elif dx == -1:
            d_ab = "west"
        elif dz == 1:
            d_ab = "south"
        else:
            d_ab = "north"
        # A must have up toward B; B typically has side/none toward A at lower
        if a_arms.get(d_ab) == "up":
            return True, d_ab + "_up"
        if a_arms.get(d_ab) not in _CONN_NONE and b_arms.get(_OPP[d_ab], "none") not in _CONN_NONE:
            return True, d_ab + "_step"
        return False, ""

    if abs(dx) + abs(dz) == 1 and dy == -1:
        # B below A → symmetric of above
        return dust_connected(b_pos, b_arms, a_pos, a_arms)

    return False, ""


def build_dust_adjacency(
    dust_nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    dust_set = {n["pos"] for n in dust_nodes}
    arms_by: dict[tuple, dict[str, str]] = {}
    from collections import Counter
    shape_hist: Counter[str] = Counter()
    inferred_n = 0

    for n in dust_nodes:
        arms = resolve_dust_arms(n, dust_set)
        arms_by[n["pos"]] = arms
        sn = shape_name(arms)
        shape_hist[sn] += 1
        if arms.get("_inferred") == "1":
            inferred_n += 1

    nei: dict[tuple, set[tuple]] = defaultdict(set)
    edges = []
    soft_edges = 0
    for i, a in enumerate(dust_nodes):
        for b in dust_nodes[i + 1 :]:
            ok, how = dust_connected(a["pos"], arms_by[a["pos"]], b["pos"], arms_by[b["pos"]])
            if ok:
                nei[a["pos"]].add(b["pos"])
                nei[b["pos"]].add(a["pos"])
                edges.append({"a": list(a["pos"]), "b": list(b["pos"]), "via": how})
                if "soft" in how:
                    soft_edges += 1

    samples = []
    for n in dust_nodes[:20]:
        arms = arms_by[n["pos"]]
        samples.append({
            "pos": list(n["pos"]),
            "shape": shape_name(arms),
            "arms": {d: arms.get(d, "none") for d in _HORIZ},
            "schematic_power": arms.get("power") or None,
            "inferred": arms.get("_inferred") == "1",
            "degree": len(nei.get(n["pos"], ())),
        })

    return {
        "adjacency": nei,
        "arms_by_pos": arms_by,
        "shape_hist": dict(shape_hist),
        "edge_count": len(edges),
        "soft_edge_count": soft_edges,
        "inferred_arm_nodes": inferred_n,
        "samples": samples,
        "limits": [
            "优先使用 litematic 中 redstone_wire 的 east/south/north/west（none|side|up）",
            "仅沿双方（或单侧 soft）伸出的臂传播强度；不沿 none 方向串电",
            "垂直：本格方向为 up 时可连到邻柱上方粉尘",
            "缺 Properties 时按邻格粉尘推断臂，形状可能偏「更连通」",
        ],
    }
