# -*- coding: utf-8 -*-
"""Common Java redstone pattern cues for Phase-1 reports (not engine parity)."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

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
_HORIZ_F = ("east", "west", "south", "north")

PATTERN_LIMITS = [
    "常用 + 少见电路骨架（脉冲/逻辑/飞船/传送门/烧炼/滤器/讲台/合成器等）",
    "不做完整真值表、零刻/BUD 仅结构线索、不推动方块、非原版时序",
    "置信度常为 low/medium；装饰性音符盒/活板/灯易误报",
]


def _manh(a: tuple, b: tuple) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _cheb(a: tuple, b: tuple) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def _near_any(pos: tuple, pool: list[dict], radius: int = 2) -> bool:
    for n in pool:
        if _cheb(pos, n["pos"]) <= radius:
            return True
    return False


def _add(
    patterns: list[dict[str, Any]],
    *,
    id: str,
    label: str,
    confidence: str,
    score: float,
    detail: str,
    **extra: Any,
) -> None:
    patterns.append(
        {
            "id": id,
            "label": label,
            "confidence": confidence,
            "score": round(score, 3),
            "detail": detail,
            **extra,
        }
    )


def detect_common_patterns(
    nodes: list[dict[str, Any]],
    graph: dict[str, Any] | None = None,
    *,
    qc_bud: dict[str, Any] | None = None,
    clocks: dict[str, Any] | None = None,
    voxels=None,
    palette: list[str] | None = None,
) -> dict[str, Any]:
    """Recognize common redstone build patterns for Chinese reports."""
    by_pos = {n["pos"]: n for n in nodes}
    patterns: list[dict[str, Any]] = []

    doors = [n for n in nodes if n["kind"] in ("door", "iron_door")]
    trapdoors = [n for n in nodes if n["kind"] == "trapdoor"]
    gates = [n for n in nodes if n["kind"] == "fence_gate"]
    lamps = [n for n in nodes if n["kind"] in ("redstone_lamp", "copper_bulb", "note_block")]
    levers = [n for n in nodes if n["kind"] == "lever"]
    buttons = [n for n in nodes if n["kind"] == "button"]
    plates = [n for n in nodes if n["kind"] == "pressure_plate"]
    inputs = levers + buttons + plates
    dust = [n for n in nodes if n["kind"] == "redstone_wire"]
    torches = [n for n in nodes if n["kind"] == "redstone_torch"]
    reps = [n for n in nodes if n["kind"] == "repeater"]
    comps = [n for n in nodes if n["kind"] == "comparator"]
    hoppers = [n for n in nodes if n["kind"] == "hopper"]
    droppers = [n for n in nodes if n["kind"] == "dropper"]
    dispensers = [n for n in nodes if n["kind"] == "dispenser"]
    pistons = [n for n in nodes if n["kind"] in ("piston", "sticky_piston")]
    sticky = [n for n in nodes if n["kind"] == "sticky_piston"]
    observers = [n for n in nodes if n["kind"] == "observer"]
    rs_blocks = [n for n in nodes if n["kind"] == "redstone_block"]
    sculks = [n for n in nodes if n["kind"] == "sculk_sensor"]
    targets = [n for n in nodes if n["kind"] == "target"]
    bulbs = [n for n in nodes if n["kind"] == "copper_bulb"]
    notes = [n for n in nodes if n["kind"] == "note_block"]
    det_rails = [n for n in nodes if n["kind"] == "detector_rail"]
    powered_rails = [n for n in nodes if n["kind"] == "powered_rail"]
    rails = [n for n in nodes if n["kind"] in ("rail", "powered_rail", "detector_rail", "activator_rail")]
    daylights = [n for n in nodes if n["kind"] == "daylight_detector"]
    tripwires = [n for n in nodes if n["kind"] == "tripwire"]
    trapped = [n for n in nodes if n["kind"] == "trapped_chest"]
    lecterns = [n for n in nodes if n["kind"] == "lectern"]
    bookshelves = [n for n in nodes if n["kind"] == "chiseled_bookshelf"]
    crafters = [n for n in nodes if n["kind"] == "crafter"]
    brewers = [n for n in nodes if n["kind"] == "brewing_stand"]
    furnaces = [n for n in nodes if n["kind"] in ("furnace", "smoker", "blast_furnace")]
    portals = [n for n in nodes if n["kind"] == "nether_portal"]
    shulkers = [n for n in nodes if n["kind"] == "shulker_box"]
    slimes = [n for n in nodes if n["kind"] == "slime_block"]
    honeys = [n for n in nodes if n["kind"] == "honey_block"]
    trial_spawners = [n for n in nodes if n["kind"] == "trial_spawner"]
    vaults = [n for n in nodes if n["kind"] == "vault"]

    def _palette_shorts():
        if voxels is None or palette is None:
            return None, set(), set(), set()
        shorts = []
        for name in palette:
            s = str(name).replace("minecraft:", "")
            if s.startswith("block.minecraft."):
                s = s[len("block.minecraft."):]
            shorts.append(s)
        water_ids = {i for i, s in enumerate(shorts) if s in ("water", "flowing_water")}
        pane_ids = {i for i, s in enumerate(shorts) if "glass_pane" in s}
        obs_ids = {i for i, s in enumerate(shorts) if s in ("obsidian", "crying_obsidian")}
        water_pos: set = set()
        pane_pos: set = set()
        obsidian_pos: set = set()
        need = bool(water_ids or pane_ids or obs_ids)
        if not need:
            return shorts, water_pos, pane_pos, obsidian_pos
        try:
            import numpy as np
            arr = np.asarray(voxels)
            for ids, bucket in (
                (water_ids, water_pos),
                (pane_ids, pane_pos),
                (obs_ids, obsidian_pos),
            ):
                if not ids:
                    continue
                mask = np.isin(arr, list(ids))
                for x, y, z in zip(*np.where(mask)):
                    bucket.add((int(x), int(y), int(z)))
        except Exception:
            pass
        return shorts, water_pos, pane_pos, obsidian_pos


    # --- 1) Door / trapdoor / fence-gate lines ---
    # Doors often sit 2–3 格 from plate/dust through a wall; trapdoors as floors stay tight.
    power_adj = dust + torches + reps + comps
    ctrl_adj = levers + buttons + plates

    def _near_manh(pos, pool, r: int) -> bool:
        return any(_manh(pos, x["pos"]) <= r for x in pool)

    wired_doors = [
        n for n in doors
        if _near_manh(n["pos"], power_adj, 3) or _near_manh(n["pos"], ctrl_adj, 3)
    ]
    wired_td = [n for n in trapdoors if _near_manh(n["pos"], power_adj, 1)]
    wired_gates = [
        n for n in gates
        if _near_manh(n["pos"], power_adj, 2) or _near_manh(n["pos"], levers + buttons, 2)
    ]
    td_ok = len(wired_td) >= 3 and len(dust) >= 1
    if wired_doors or wired_gates or td_ok:
        conf = "high" if wired_doors else ("medium" if wired_gates or len(wired_td) >= 6 else "low")
        score = 0.45 + 0.1 * min(4, len(wired_doors)) + 0.05 * min(2, len(wired_gates))
        if td_ok and not wired_doors:
            score = min(score, 0.55)
        _add(
            patterns,
            id="door_line",
            label="门/活板/栅栏门控制线",
            confidence=conf,
            score=min(0.9, score),
            detail=(
                f"近距门 {len(wired_doors)}、活板(紧邻粉尘/逻辑) {len(wired_td)}、"
                f"栅栏门 {len(wired_gates)} —— 常见红石门线。"
            ),
            counts={
                "doors": len(wired_doors),
                "trapdoors": len(wired_td),
                "fence_gates": len(wired_gates),
            },
            sample_positions=[list(n["pos"]) for n in (wired_doors + wired_gates + wired_td)[:6]],
        )

    # --- 2) Clocks (lift from detect_clocks, plus torch-clock layout) ---
    for clk in (clocks or {}).get("clocks") or []:
        _add(
            patterns,
            id=clk.get("id") or "clock",
            label=clk.get("label") or "时钟",
            confidence=clk.get("confidence") or "low",
            score=float(clk.get("score") or 0.4),
            detail=clk.get("detail") or "来自 D4 时钟识别。",
            from_clocks=True,
        )
    # torch clock: torch next to dust that also touches the attachment / repeater pulse
    if torches and dust and not any(p["id"] == "torch_burn_clock" for p in patterns):
        torch_clockish = 0
        for t in torches:
            if _near_any(t["pos"], dust, 1) and (
                _near_any(t["pos"], reps, 2) or _near_any(t["pos"], dust, 1)
            ):
                # dust on top of / beside torch attachment often → classic torch clock skeleton
                above = (t["pos"][0], t["pos"][1] + 1, t["pos"][2])
                if above in by_pos and by_pos[above]["kind"] == "redstone_wire":
                    torch_clockish += 1
                elif _near_any(t["pos"], reps, 1):
                    torch_clockish += 1
        if torch_clockish >= 1 and len(torches) <= 6:
            _add(
                patterns,
                id="torch_clock",
                label="火把钟骨架",
                confidence="medium" if torch_clockish >= 2 else "low",
                score=0.5 if torch_clockish >= 2 else 0.35,
                detail="火把邻接粉尘（或粉尘在火把上方）且规模不大，疑似火把钟（烧毁见 tick soft-lock）。",
                torch_hits=torch_clockish,
            )

    # --- 3) Hopper lines / item elevators ---
    # hopper chain: same facing, consecutive front→back
    hop_by_pos = {n["pos"]: n for n in hoppers}
    line_lens: list[int] = []
    visited_h: set[tuple] = set()
    for h in hoppers:
        if h["pos"] in visited_h:
            continue
        fac = h.get("facing")
        if not fac or fac not in _FACING:
            continue
        d = _FACING[fac]
        # walk backward to start
        cur = h["pos"]
        while True:
            prev = (cur[0] - d[0], cur[1] - d[1], cur[2] - d[2])
            pn = hop_by_pos.get(prev)
            if not pn or pn.get("facing") != fac:
                break
            cur = prev
        # walk forward
        chain = []
        p = cur
        while p in hop_by_pos and hop_by_pos[p].get("facing") == fac:
            chain.append(p)
            visited_h.add(p)
            p = (p[0] + d[0], p[1] + d[1], p[2] + d[2])
        if len(chain) >= 3:
            line_lens.append(len(chain))
    if line_lens:
        _add(
            patterns,
            id="hopper_line",
            label="漏斗输送线",
            confidence="high" if max(line_lens) >= 4 else "medium",
            score=min(0.92, 0.5 + 0.08 * max(line_lens)),
            detail=f"同朝向漏斗链长度 {sorted(line_lens, reverse=True)[:5]}，常见物品线。",
            chain_lengths=sorted(line_lens, reverse=True)[:8],
        )
    # vertical elevator: droppers stacked facing up, or hopper down column
    up_drop = [n for n in droppers + dispensers if n.get("facing") == "up"]
    down_hop = [n for n in hoppers if n.get("facing") == "down"]
    elev = 0
    for n in up_drop:
        above = (n["pos"][0], n["pos"][1] + 1, n["pos"][2])
        if above in by_pos and by_pos[above]["kind"] in ("dropper", "dispenser", "hopper"):
            elev += 1
    for n in down_hop:
        below = (n["pos"][0], n["pos"][1] - 1, n["pos"][2])
        if below in by_pos and by_pos[below]["kind"] == "hopper":
            elev += 1
    if elev >= 2 or (len(up_drop) >= 2 and any(
        abs(a["pos"][0] - b["pos"][0]) + abs(a["pos"][2] - b["pos"][2]) == 0
        and abs(a["pos"][1] - b["pos"][1]) == 1
        for i, a in enumerate(up_drop)
        for b in up_drop[i + 1 :]
    )):
        _add(
            patterns,
            id="item_elevator",
            label="物品升降机嫌疑",
            confidence="medium",
            score=0.6,
            detail="竖向投掷器/漏斗叠放，疑似物品电梯（需观察者或时钟驱动）。",
            stack_links=elev,
            up_droppers=len(up_drop),
        )

    # --- 4) Piston doors / sticky pairs ---
    # parallel pistons same facing in a row
    by_face: dict[str, list] = defaultdict(list)
    for p in pistons:
        if p.get("facing"):
            by_face[p["facing"]].append(p)
    parallel_rows = 0
    for fac, group in by_face.items():
        if len(group) < 2:
            continue
        # group by the axis perpendicular plane
        # same facing → share coord along facing axis offset
        d = _FACING[fac]
        # project: positions sharing the "depth" along facing
        buckets: dict[tuple, list] = defaultdict(list)
        for p in group:
            pos = p["pos"]
            # key = coords orthogonal to facing
            if fac in ("east", "west"):
                key = (pos[1], pos[0])  # y + depth along facing
            elif fac in ("north", "south"):
                key = (pos[1], pos[2])
            else:
                key = (pos[0], pos[2])
            buckets[key].append(p)
        # actually cluster neighbors in orthogonal plane at same depth
        depth_groups: dict[int, list] = defaultdict(list)
        for p in group:
            pos = p["pos"]
            depth = pos[0] * abs(d[0]) + pos[1] * abs(d[1]) + pos[2] * abs(d[2])
            depth_groups[depth].append(pos)
        for positions in depth_groups.values():
            if len(positions) < 2:
                continue
            # count adjacent pairs in plane
            for i, a in enumerate(positions):
                for b in positions[i + 1 :]:
                    if _manh(a, b) == 1:
                        parallel_rows += 1
    if parallel_rows >= 2 or (len(pistons) >= 4 and parallel_rows >= 1):
        _add(
            patterns,
            id="piston_door",
            label="活塞门/排活塞",
            confidence="high" if parallel_rows >= 3 else "medium",
            score=min(0.9, 0.5 + 0.1 * parallel_rows),
            detail=f"同朝向邻接活塞对约 {parallel_rows}，常见活塞门/隐藏门骨架。",
            adjacent_pairs=parallel_rows,
            piston_count=len(pistons),
        )
    # sticky pair facing a shared cell / each other (block swapper / 1-wide door)
    sticky_pairs = 0
    for i, a in enumerate(sticky):
        fa = a.get("facing")
        if not fa:
            continue
        da = _FACING[fa]
        front = (a["pos"][0] + da[0], a["pos"][1] + da[1], a["pos"][2] + da[2])
        for b in sticky[i + 1 :]:
            fb = b.get("facing")
            if not fb:
                continue
            db = _FACING[fb]
            b_front = (b["pos"][0] + db[0], b["pos"][1] + db[1], b["pos"][2] + db[2])
            # face each other or share front cell (RSB between)
            if front == b["pos"] and b_front == a["pos"]:
                sticky_pairs += 1
            elif front == b_front:
                sticky_pairs += 1
            elif _manh(a["pos"], b["pos"]) <= 3 and fa == _OPP.get(fb):
                # opposing sticky with gap (RSB / slime)
                mid_ok = any(
                    _cheb(rs["pos"], a["pos"]) <= 2 and _cheb(rs["pos"], b["pos"]) <= 2
                    for rs in rs_blocks
                )
                if mid_ok or _manh(a["pos"], b["pos"]) <= 2:
                    sticky_pairs += 1
    if sticky_pairs >= 1:
        _add(
            patterns,
            id="sticky_piston_pair",
            label="粘性活塞对（换块/门）",
            confidence="high" if rs_blocks else "medium",
            score=0.75 if rs_blocks else 0.55,
            detail="对置粘活塞"
            + ("+红石块" if rs_blocks else "")
            + "，常见换块器/1 格活塞门/BUD 驱动架。",
            pair_hits=sticky_pairs,
        )

    # --- 5) Common QC/BUD piston uses ---
    qc = qc_bud or {}
    qc_n = int(qc.get("qc_candidate_count") or 0)
    bud_n = int(qc.get("bud_standby_suspect_count") or 0)
    if qc_n >= 1:
        _add(
            patterns,
            id="qc_piston_bank",
            label="QC/BUD 活塞组",
            confidence="high" if qc_n >= 3 else "medium",
            score=min(0.9, 0.45 + 0.08 * qc_n),
            detail=(
                f"QC 候选 {qc_n}、BUD 待机嫌疑 {bud_n}。"
                "常见于刷怪塔侧置活塞、鸡场收蛋、隐门（粗模型不推动方块时 tick 可能不伸出）。"
            ),
            qc_candidate_count=qc_n,
            bud_standby_suspect_count=bud_n,
        )

    # --- 6) Simple lamp / lever / button → output ---
    wired_lamps = [
        n for n in lamps
        if _near_manh(n["pos"], dust + torches + reps, 2)
        or _near_manh(n["pos"], levers + buttons, 4)
    ]
    if (levers or buttons or plates) and (wired_lamps or wired_doors or wired_gates):
        _add(
            patterns,
            id="simple_io",
            label="杠杆/按钮 → 灯或门",
            confidence="high" if (wired_lamps and (levers or buttons)) or wired_doors else "medium",
            score=0.7,
            detail=(
                f"输入 杠杆{len(levers)}/按钮{len(buttons)}/踏板{len(plates)}；"
                f"近距灯类 {len(wired_lamps)}、门类 {len(wired_doors)+len(wired_gates)}。"
            ),
            input_counts={"lever": len(levers), "button": len(buttons), "plate": len(plates)},
            lamp_outputs=len(wired_lamps),
        )
    elif wired_lamps and (dust or torches or reps):
        _add(
            patterns,
            id="lamp_line",
            label="红石灯/灯泡线路",
            confidence="medium",
            score=0.55,
            detail=f"近距粉尘/火把/中继器的灯类输出 {len(wired_lamps)}。",
            lamp_outputs=len(wired_lamps),
        )
    elif lamps and (levers or buttons) and reps and not dust:
        # 无粉尘时：按钮/杠杆 + 中继器 + 灯 → 简易照明线嫌疑
        _add(
            patterns,
            id="lamp_line",
            label="中继器灯线路嫌疑",
            confidence="low",
            score=0.4,
            detail=f"无粉尘但有中继器×{len(reps)}与灯×{len(lamps)}、输入开关 —— 可能墙内隐蔽布线。",
            lamp_outputs=len(lamps),
        )

    # --- 7) T-flip-flop / RS-latch coarse ---
    # RS latch: two torches cross-coupled via dust/blocks within 2
    if len(torches) >= 2:
        latch_pairs = 0
        for i, a in enumerate(torches):
            for b in torches[i + 1 :]:
                if _cheb(a["pos"], b["pos"]) <= 2 and _near_any(a["pos"], dust, 1):
                    latch_pairs += 1
        if latch_pairs >= 1 and len(pistons) == 0:
            _add(
                patterns,
                id="rs_latch",
                label="RS 锁存（火把）嫌疑",
                confidence="low",
                score=0.4,
                detail="近距火把对+粉尘，可能为 RS 锁存（亦可能为装饰火把）。",
                pairs=latch_pairs,
            )
    # TFF cheap: observer into sticky / dropper-hopper loop
    tff = 0
    for o in observers:
        if _near_any(o["pos"], sticky, 2):
            tff += 1
        if _near_any(o["pos"], droppers, 2) and _near_any(o["pos"], hoppers, 2):
            tff += 1
    if tff >= 1:
        _add(
            patterns,
            id="t_flip_flop",
            label="T 触发器嫌疑",
            confidence="low",
            score=0.4,
            detail="观察者靠近粘活塞或漏斗/投掷器环，粗线索（非验证）。",
            hits=tff,
        )
    # dropper-hopper TFF classic
    for d in droppers:
        fac = d.get("facing")
        if not fac:
            continue
        fd = _FACING[fac]
        front = (d["pos"][0] + fd[0], d["pos"][1] + fd[1], d["pos"][2] + fd[2])
        if front in by_pos and by_pos[front]["kind"] == "hopper":
            if _near_any(d["pos"], comps + observers, 2):
                _add(
                    patterns,
                    id="t_flip_flop",
                    label="投掷器-漏斗 T 触发器嫌疑",
                    confidence="medium",
                    score=0.55,
                    detail="投掷器朝向漏斗且旁有比较器/观察者，经典物品 TFF 骨架。",
                    positions=[list(d["pos"]), list(front)],
                )
                break


    # --- 8) Uncommon but recognizable cues (low/medium OK) ---

    # 8a Etho hopper clock variants: 1–2 hoppers + comparator lock/side, or 4-hopper Etho
    eth_hits = 0
    for c in comps:
        if not _near_any(c["pos"], hoppers, 1):
            continue
        # comparator locking another comparator / next to hopper clock pair
        side_lock = _near_any(c["pos"], comps, 1) and c.get("mode") in (None, "", "compare", "subtract")
        if _near_any(c["pos"], hoppers, 1):
            eth_hits += 1
            if side_lock:
                eth_hits += 1
    # classic Etho: comparator reading hopper with torch/dust feedback
    if eth_hits >= 1 and hoppers:
        conf = "medium" if eth_hits >= 2 and len(comps) >= 1 else "low"
        _add(
            patterns,
            id="etho_hopper_clock",
            label="Etho 漏斗钟变体嫌疑",
            confidence=conf,
            score=0.5 if conf == "medium" else 0.35,
            detail="比较器紧贴漏斗（可含侧锁/反馈），Etho 系可调漏斗钟骨架；与普通漏斗钟可能重叠。",
            eth_hits=eth_hits,
        )
    # 4-hopper ring / loop facing cycle
    if len(hoppers) >= 4:
        # count hoppers whose front is another hopper
        hpos = {n["pos"]: n for n in hoppers}
        cycle_links = 0
        for h in hoppers:
            fac = h.get("facing")
            if not fac or fac not in _FACING:
                continue
            d = _FACING[fac]
            front = (h["pos"][0] + d[0], h["pos"][1] + d[1], h["pos"][2] + d[2])
            if front in hpos:
                cycle_links += 1
        if cycle_links >= 3 and comps:
            _add(
                patterns,
                id="etho_hopper_clock",
                label="多漏斗环钟嫌疑",
                confidence="medium",
                score=0.55,
                detail=f"漏斗互指链约 {cycle_links} + 比较器，少见多漏斗钟/分配环。",
                cycle_links=cycle_links,
            )

    # 8b Dropper-vator (vertical dropper column + observer/clock)
    up_col = [n for n in droppers if n.get("facing") == "up"]
    if len(up_col) >= 2:
        # same xz stacked
        cols: dict[tuple, int] = defaultdict(int)
        for n in up_col:
            cols[(n["pos"][0], n["pos"][2])] += 1
        tall = max(cols.values()) if cols else 0
        if tall >= 2:
            driven = any(_near_any(n["pos"], observers + comps + dust + reps, 2) for n in up_col)
            _add(
                patterns,
                id="dropper_vator",
                label="投掷器电梯（dropper-vator）",
                confidence="medium" if driven and tall >= 3 else "low",
                score=0.55 if tall >= 3 else 0.4,
                detail=f"同柱朝上投掷器叠 {tall} 层"
                + ("，旁有观察者/粉尘/中继驱动" if driven else "（未见明显驱动，或时钟在别处）")
                + "。",
                stack=tall,
            )

    # 8c Zero-tick / BUD freerun cues
    # observer facing piston / sticky that QC-bud suspects; or TORCH spam next to piston update
    zt = 0
    for o in observers:
        if _near_any(o["pos"], pistons, 1):
            zt += 1
        # observer into dust into piston (update loop)
        if _near_any(o["pos"], dust, 1) and _near_any(o["pos"], pistons, 2):
            zt += 1
    bud_n = int((qc_bud or {}).get("bud_standby_suspect_count") or 0)
    if zt >= 1 and (bud_n >= 1 or any(p.get("kind") == "sticky_piston" for p in pistons)):
        _add(
            patterns,
            id="zero_tick_bud_freerun",
            label="零刻/BUD 自走嫌疑",
            confidence="low",
            score=0.35,
            detail="观察者贴活塞/粉尘更新环 + BUD/粘活塞线索；可能为 0-tick 或 BUD 自走（极粗，易误报）。",
            observer_piston_hits=zt,
            bud_suspects=bud_n,
        )
    elif bud_n >= 3 and observers:
        _add(
            patterns,
            id="zero_tick_bud_freerun",
            label="BUD 阵列自走嫌疑",
            confidence="low",
            score=0.3,
            detail=f"BUD 待机嫌疑 {bud_n} 且有观察者，可能更新链自激。",
            bud_suspects=bud_n,
        )

    # 8d Monostable / pulse extender / pulse limiter
    # repeater line 2–5 with different delays, or repeater + torch pulse
    if len(reps) >= 2:
        delays = [r.get("delay") for r in reps if r.get("delay")]
        # chain: repeater facing into another repeater
        chain = 0
        rpos = {n["pos"]: n for n in reps}
        for r in reps:
            fac = r.get("facing")
            if not fac:
                continue
            d = _FACING[fac]
            front = (r["pos"][0] + d[0], r["pos"][1] + d[1], r["pos"][2] + d[2])
            if front in rpos:
                chain += 1
        if chain >= 1 and len(set(str(x) for x in delays)) >= 2:
            _add(
                patterns,
                id="pulse_extender",
                label="脉冲延长/单稳态嫌疑",
                confidence="medium",
                score=0.5,
                detail=f"中继器链 {chain} 且 delay 档位多样 {delays[:8]}，常见 monostable/延长器。",
                chain=chain,
            )
        elif chain >= 2:
            _add(
                patterns,
                id="pulse_extender",
                label="中继器链脉冲处理嫌疑",
                confidence="low",
                score=0.35,
                detail=f"连续中继器链约 {chain}，可能为延长/限幅/延迟线。",
                chain=chain,
            )
    # torch + repeater classic monostable
    mono = 0
    for tch in torches:
        if _near_any(tch["pos"], reps, 1) and _near_any(tch["pos"], dust, 1):
            mono += 1
    if mono >= 1 and len(reps) >= 1:
        _add(
            patterns,
            id="monostable",
            label="火把-中继器单稳态嫌疑",
            confidence="low",
            score=0.4,
            detail="火把邻接中继器与粉尘，经典短脉冲 monostable 骨架。",
            hits=mono,
        )
    # pulse limiter: repeater locking repeater (side powered)
    lock_pairs = 0
    for r in reps:
        fac = r.get("facing")
        if not fac:
            continue
        # side neighbors are repeaters
        for side in _HORIZ_F:
            if side == fac or side == _OPP.get(fac):
                continue
            d = _FACING[side]
            sp = (r["pos"][0] + d[0], r["pos"][1] + d[1], r["pos"][2] + d[2])
            if sp in by_pos and by_pos[sp]["kind"] == "repeater":
                lock_pairs += 1
    if lock_pairs >= 1:
        _add(
            patterns,
            id="pulse_limiter",
            label="中继器锁定限幅器嫌疑",
            confidence="medium" if lock_pairs >= 2 else "low",
            score=0.5 if lock_pairs >= 2 else 0.35,
            detail=f"中继器侧向邻接另一中继器约 {lock_pairs} 对，常见脉冲限幅/锁定。",
            lock_pairs=lock_pairs,
        )

    # 8e Edge detector / falling-edge (observer or torch-dust-torch)
    if observers:
        # observer into repeater or dust — rising/falling edge detector
        edge = sum(1 for o in observers if _near_any(o["pos"], reps + dust + pistons, 1))
        if edge >= 1:
            _add(
                patterns,
                id="edge_detector",
                label="边沿检测（观察者）嫌疑",
                confidence="medium" if edge >= 2 else "low",
                score=0.5 if edge >= 2 else 0.35,
                detail=f"观察者贴中继器/粉尘/活塞 ×{edge}，常用作上升沿/方块更新检测。",
                hits=edge,
            )
    # falling edge: two torches with dust between asymmetric
    if len(torches) >= 2 and dust:
        fe = 0
        for i, a in enumerate(torches):
            for b in torches[i + 1 :]:
                if _manh(a["pos"], b["pos"]) == 2 and _near_any(a["pos"], dust, 1):
                    fe += 1
        if fe >= 1:
            _add(
                patterns,
                id="falling_edge",
                label="下降沿/双火把脉冲嫌疑",
                confidence="low",
                score=0.3,
                detail="近距双火把+粉尘，可能为下降沿或脉冲电路。",
                pairs=fe,
            )

    # 8f XOR / AND / NOR torch logic lattices
    if len(torches) >= 3 and dust:
        # dense torch-dust lattice
        torch_dust_n = sum(1 for tch in torches if _near_any(tch["pos"], dust, 1))
        if torch_dust_n >= 3:
            # check shared dust neighbors (OR/NOR bus)
            _add(
                patterns,
                id="torch_logic_lattice",
                label="火把逻辑阵（AND/OR/NOR/XOR）嫌疑",
                confidence="low",
                score=0.35,
                detail=f"{torch_dust_n} 枚火把贴粉尘，可能为火把门阵列；XOR 常需交叉/叠加布局（未验证）。",
                torch_dust=torch_dust_n,
            )
        # XOR-ish: 2 inputs torches into cross dust with output torch
        if torch_dust_n >= 4:
            _add(
                patterns,
                id="torch_xor_gate",
                label="火把 XOR/同或门嫌疑",
                confidence="low",
                score=0.3,
                detail="较密火把-粉尘阵，少见 XOR/XNOR 骨架（亦可能是灯饰）。",
            )

    # 8g Instant wire / dual-edge repeater lines
    # long repeater line all delay=1 facing same way
    if len(reps) >= 3:
        d1 = [r for r in reps if str(r.get("delay") or "1") in ("1", "1t", 1)]
        by_f: dict[str, int] = defaultdict(int)
        for r in d1:
            if r.get("facing"):
                by_f[r["facing"]] += 1
        best_f = max(by_f.values()) if by_f else 0
        if best_f >= 3:
            _add(
                patterns,
                id="instant_wire",
                label="瞬间线/同向中继器线嫌疑",
                confidence="medium" if best_f >= 4 else "low",
                score=0.5 if best_f >= 4 else 0.35,
                detail=f"同向 delay≈1 中继器 ×{best_f}，粗线索瞬间线/双沿中继线（非真 0-tick wire）。",
                count=best_f,
            )
        # dual-edge: two parallel repeater lines opposite facing
        if len(by_f) >= 2:
            vals = sorted(by_f.values(), reverse=True)
            if vals[0] >= 2 and vals[1] >= 2:
                _add(
                    patterns,
                    id="dual_edge_repeater",
                    label="双沿/对向中继器线嫌疑",
                    confidence="low",
                    score=0.35,
                    detail=f"多朝向中继器束 {dict(by_f)}，可能双沿或往返瞬间线。",
                )

    # 8h Sculk sensor lines
    if sculks:
        cal = sum(1 for n in sculks if "calibrated" in (n.get("block") or ""))
        wired = sum(1 for n in sculks if _near_any(n["pos"], dust + reps + observers + comps, 2))
        _add(
            patterns,
            id="sculk_sensor_line",
            label="幽匿感测线",
            confidence="high" if wired else "medium",
            score=0.7 if wired else 0.5,
            detail=f"幽匿感测体 {len(sculks)}"
            + (f"（含校准 {cal}）" if cal else "")
            + ("，已邻接粉尘/逻辑" if wired else "（未见紧邻布线，或无线）")
            + "。",
            count=len(sculks),
            calibrated=cal,
        )

    # 8i Target block + projectile cue
    if targets:
        wired_t = sum(1 for n in targets if _near_any(n["pos"], dust + reps + droppers + dispensers, 2))
        _add(
            patterns,
            id="target_block_line",
            label="标靶方块线路",
            confidence="medium" if wired_t or droppers or dispensers else "low",
            score=0.55 if wired_t else 0.35,
            detail=f"标靶 ×{len(targets)}"
            + ("，邻接粉尘/投掷/发射 —— 弹射物/精准线路线索" if wired_t or droppers else "（偏装饰或远程联动）")
            + "。",
            count=len(targets),
        )

    # 8j Copper bulb latch
    if bulbs:
        near_in = sum(1 for n in bulbs if _near_any(n["pos"], dust + reps + torches + levers + buttons, 2))
        _add(
            patterns,
            id="copper_bulb_latch",
            label="铜灯泡锁存/切换",
            confidence="medium" if near_in else "low",
            score=0.55 if near_in else 0.35,
            detail=f"铜灯泡 ×{len(bulbs)}"
            + ("，邻接红石控制 —— 常用作廉价 T 触发/状态灯" if near_in else "（未见紧邻控制）")
            + "。",
            count=len(bulbs),
        )

    # 8k Note block / instrument cue
    if notes:
        wired_n = sum(1 for n in notes if _near_any(n["pos"], dust + reps + observers + torches, 2))
        cluster = False
        for i, a in enumerate(notes):
            for b in notes[i + 1 :]:
                if _cheb(a["pos"], b["pos"]) <= 2:
                    cluster = True
                    break
        if wired_n or (cluster and len(notes) >= 3):
            _add(
                patterns,
                id="note_block_line",
                label="音符盒线路/乐器阵",
                confidence="medium" if wired_n else "low",
                score=0.5 if wired_n else 0.3,
                detail=f"音符盒 ×{len(notes)}"
                + ("，有红石邻接" if wired_n else "，成簇但无线 —— 可能装饰或底层布线")
                + "。",
                count=len(notes),
            )

    # 8l Minecart detector rail clocks
    if det_rails:
        loopish = len(rails) >= 4 and len(det_rails) >= 1
        near_clock = any(_near_any(n["pos"], dust + comps + hoppers + observers, 2) for n in det_rails)
        if loopish or near_clock:
            _add(
                patterns,
                id="detector_rail_clock",
                label="探测铁轨矿车钟嫌疑",
                confidence="medium" if near_clock and len(det_rails) >= 1 else "low",
                score=0.5 if near_clock else 0.3,
                detail=f"探测轨 ×{len(det_rails)}、铁轨类 ×{len(rails)}"
                + ("，邻接红石 —— 矿车钟/车站检测" if near_clock else "（环线未确认）")
                + "。",
                detector=len(det_rails),
                rails=len(rails),
            )

    # ice boat / blueprint: skip (no ice+boat entity in litematic reliably)

    # --- 9) Another batch: extenders / portal / smelt / filters / etc. ---
    shorts, water_pos, pane_pos, obsidian_pos = _palette_shorts()

    _by_face2: dict[str, list] = defaultdict(list)
    for p_ in pistons:
        if p_.get("facing"):
            _by_face2[p_["facing"]].append(p_)
    extender_hits = 0
    for fac, group in _by_face2.items():
        if len(group) < 3 or fac not in _FACING:
            continue
        d = _FACING[fac]
        coords = []
        for p_ in group:
            pos = p_["pos"]
            along = pos[0] * d[0] + pos[1] * d[1] + pos[2] * d[2]
            orth = (
                pos[0] - d[0] * along,
                pos[1] - d[1] * along,
                pos[2] - d[2] * along,
            )
            coords.append((orth, along, pos))
        buckets: dict = defaultdict(list)
        for orth, along, pos in coords:
            buckets[orth].append(along)
        for alongs in buckets.values():
            alongs = sorted(set(alongs))
            run = 1
            best_run = 1
            for i in range(1, len(alongs)):
                if alongs[i] - alongs[i - 1] == 1:
                    run += 1
                    best_run = max(best_run, run)
                else:
                    run = 1
            if best_run >= 3:
                extender_hits += 1
    if extender_hits >= 1:
        _add(
            patterns,
            id="multi_piston_extender",
            label="多活塞推杆/延长器嫌疑",
            confidence="medium",
            score=0.55,
            detail=f"同轴同朝向活塞连续≥3的列约 {extender_hits}，常见双重/三重活塞推杆。",
            columns=extender_hits,
        )

    mobile = slimes + honeys
    if mobile and pistons:
        fm = 0
        for m in mobile:
            if _near_any(m["pos"], pistons, 1) and (
                _near_any(m["pos"], observers, 2) or _near_any(m["pos"], sticky, 1)
            ):
                fm += 1
        if fm >= 1 or (len(mobile) >= 2 and any(_near_any(m["pos"], pistons, 2) for m in mobile)):
            _add(
                patterns,
                id="flying_machine",
                label="飞船/飞行器骨架",
                confidence="medium" if fm >= 1 and observers else "low",
                score=0.55 if fm >= 1 else 0.35,
                detail=f"粘液/蜂蜜块 ×{len(mobile)} 近活塞/观察者，经典飞行器骨架（不验证推进循环）。",
                mobile=len(mobile),
                hits=fm,
            )

    if portals:
        _add(
            patterns,
            id="nether_portal_cue",
            label="下界传送门",
            confidence="high",
            score=0.75,
            detail=f"原理图含下界门方块 ×{len(portals)}"
            + (f"、黑曜石邻域约 {len(obsidian_pos)}" if obsidian_pos else "")
            + "；可能兼作区块加载/门廊装饰。",
            portal=len(portals),
        )
    elif len(obsidian_pos) >= 10:
        rs_nodes = dust + reps + observers
        near_rs = False
        if rs_nodes:
            for ob in list(obsidian_pos)[:40]:
                if any(_cheb(n["pos"], ob) <= 6 for n in rs_nodes[:40]):
                    near_rs = True
                    break
        if near_rs:
            _add(
                patterns,
                id="portal_frame_cue",
                label="传送门框/黑曜石阵嫌疑",
                confidence="low",
                score=0.3,
                detail=f"黑曜石格约 {len(obsidian_pos)} 且邻近红石，可能为门框或加载器底座（无门方块）。",
            )

    if trial_spawners:
        _add(
            patterns,
            id="trial_spawner_cue",
            label="试炼刷怪笼",
            confidence="high",
            score=0.7,
            detail=f"试炼刷怪笼 ×{len(trial_spawners)}（仅提示存在，不解析机制）。",
            count=len(trial_spawners),
        )
    if vaults:
        _add(
            patterns,
            id="vault_cue",
            label="宝库",
            confidence="high",
            score=0.7,
            detail=f"宝库 ×{len(vaults)}（仅提示存在）。",
            count=len(vaults),
        )

    cookers = furnaces + brewers
    if cookers and hoppers:
        linked = sum(1 for c in cookers if _near_any(c["pos"], hoppers, 1))
        if linked >= 1:
            kinds = Counter(n["kind"] for n in cookers)
            _add(
                patterns,
                id="auto_smelt_brew_line",
                label="自动烧炼/酿造线",
                confidence="high" if linked >= 2 else "medium",
                score=0.7 if linked >= 2 else 0.5,
                detail=f"熔炉类/酿造台 ×{len(cookers)} 中 {linked} 邻接漏斗 —— 自动烧炼/酿造骨架 {dict(kinds)}。",
                linked=linked,
            )

    if hoppers and water_pos and pane_pos:
        filt = 0
        for h in hoppers:
            hp = h["pos"]
            near_w = any(_manh(hp, w) <= 2 for w in water_pos)
            near_p = any(_manh(hp, pn) <= 2 for pn in pane_pos)
            if near_w and near_p:
                filt += 1
        if filt >= 1:
            _add(
                patterns,
                id="water_stream_filter",
                label="水流物品过滤/漏斗滤器嫌疑",
                confidence="medium" if filt >= 2 else "low",
                score=0.5 if filt >= 2 else 0.35,
                detail=f"{filt} 处漏斗同时邻近水与玻璃板，常见水流线/实体挤过滤器。",
                hits=filt,
            )
    elif hoppers and water_pos:
        wh = sum(1 for h in hoppers if any(_manh(h["pos"], w) <= 1 for w in water_pos))
        if wh >= 2:
            _add(
                patterns,
                id="water_hopper_stream",
                label="水流漏斗收集线嫌疑",
                confidence="low",
                score=0.35,
                detail=f"{wh} 漏斗贴水，可能为物品流收集（缺玻璃板滤器特征）。",
                hits=wh,
            )

    if shulkers and (hoppers or droppers or pistons):
        sh_link = sum(1 for s in shulkers if _near_any(s["pos"], hoppers + droppers + pistons, 1))
        if sh_link >= 1 or (shulkers and hoppers):
            _add(
                patterns,
                id="shulker_loader",
                label="潜影盒装卸线嫌疑",
                confidence="medium" if sh_link >= 1 else "low",
                score=0.55 if sh_link >= 1 else 0.35,
                detail=f"潜影盒 ×{len(shulkers)}，{sh_link} 邻接漏斗/投掷器/活塞 —— 装载/卸载骨架。",
                shulkers=len(shulkers),
                linked=sh_link,
            )

    if daylights:
        wired_dl = sum(
            1
            for n in daylights
            if _near_any(n["pos"], dust + comps + reps + torches + hoppers, 2)
        )
        _add(
            patterns,
            id="daylight_detector_clock",
            label="日光传感器钟/昼夜控制",
            confidence="high" if wired_dl else "medium",
            score=0.7 if wired_dl else 0.45,
            detail=f"日光传感器 ×{len(daylights)}"
            + ("，已邻接红石逻辑" if wired_dl else "（未见紧邻布线）")
            + "。",
            count=len(daylights),
            wired=wired_dl,
        )

    if tripwires:
        near_out = sum(
            1
            for n in tripwires
            if _near_any(n["pos"], dust + reps + pistons + dispensers + droppers + notes, 2)
        )
        _add(
            patterns,
            id="tripwire_trap",
            label="绊线陷阱",
            confidence="high" if len(tripwires) >= 2 else "medium",
            score=0.65,
            detail=f"绊线/钩 ×{len(tripwires)}"
            + ("，邻接红石/发射机构" if near_out else "")
            + "。",
            count=len(tripwires),
        )

    if trapped:
        tw = sum(1 for n in trapped if _near_any(n["pos"], dust + reps + notes + pistons, 2))
        _add(
            patterns,
            id="trapped_chest_line",
            label="陷阱箱线路",
            confidence="high" if tw else "medium",
            score=0.65 if tw else 0.45,
            detail=f"陷阱箱 ×{len(trapped)}"
            + ("，邻接红石输出" if tw else "（可能作容器兼信号）")
            + "。",
            count=len(trapped),
        )

    if lecterns:
        lec_comp = sum(1 for n in lecterns if _near_any(n["pos"], comps, 1))
        lec_dust = sum(1 for n in lecterns if _near_any(n["pos"], dust + reps, 2))
        if lec_comp or lec_dust:
            _add(
                patterns,
                id="lectern_signal",
                label="讲台翻页红石",
                confidence="high" if lec_comp else "medium",
                score=0.7 if lec_comp else 0.45,
                detail=f"讲台 ×{len(lecterns)}，"
                + (f"{lec_comp} 贴比较器读信号" if lec_comp else "近粉尘/中继器")
                + " —— 书页输出常见。",
                count=len(lecterns),
            )

    if bookshelves:
        bs_comp = sum(1 for n in bookshelves if _near_any(n["pos"], comps, 1))
        bs_dust = sum(1 for n in bookshelves if _near_any(n["pos"], dust + reps, 1))
        if bs_comp or bs_dust:
            _add(
                patterns,
                id="chiseled_bookshelf_signal",
                label="雕纹书架信号",
                confidence="high" if bs_comp else "medium",
                score=0.65 if bs_comp else 0.4,
                detail=f"雕纹书架 ×{len(bookshelves)}，"
                + (f"{bs_comp} 贴比较器" if bs_comp else "近红石")
                + " —— 取书信号/装饰兼电路。",
                count=len(bookshelves),
            )

    if crafters:
        cr_link = sum(
            1
            for n in crafters
            if _near_any(n["pos"], hoppers + dust + reps + comps + droppers, 2)
        )
        _add(
            patterns,
            id="crafter_auto_line",
            label="合成器自动线（1.21）",
            confidence="high" if cr_link else "medium",
            score=0.7 if cr_link else 0.45,
            detail=f"合成器 ×{len(crafters)}"
            + ("，邻接漏斗/红石 —— 自动合成骨架" if cr_link else "（未见紧邻物流）")
            + "。",
            count=len(crafters),
        )

    # lodestone / allay / netherite: skip (no reliable schematic signal)
    # dedupe by id keeping highest score
    best: dict[str, dict] = {}
    for p in patterns:
        pid = p["id"]
        if pid not in best or p["score"] > best[pid]["score"]:
            best[pid] = p
    uniq = sorted(best.values(), key=lambda x: -x["score"])

    return {
        "count": len(uniq),
        "patterns": uniq,
        "by_category": {
            "doors_gates": [p for p in uniq if p["id"] in ("door_line",)],
            "clocks": [
                p for p in uniq
                if "clock" in p["id"] or p.get("from_clocks")
                or p["id"] in ("detector_rail_clock", "etho_hopper_clock")
            ],
            "transport": [
                p for p in uniq
                if p["id"] in ("hopper_line", "item_elevator", "dropper_vator")
            ],
            "pistons": [
                p for p in uniq
                if p["id"] in ("piston_door", "sticky_piston_pair", "qc_piston_bank", "zero_tick_bud_freerun")
            ],
            "io": [
                p for p in uniq
                if p["id"] in (
                    "simple_io", "lamp_line", "sculk_sensor_line", "target_block_line",
                    "note_block_line", "copper_bulb_latch",
                )
            ],
            "memory": [p for p in uniq if p["id"] in ("rs_latch", "t_flip_flop", "copper_bulb_latch")],
            "pulse_logic": [
                p for p in uniq
                if p["id"] in (
                    "pulse_extender", "monostable", "pulse_limiter", "edge_detector",
                    "falling_edge", "torch_logic_lattice", "torch_xor_gate",
                    "instant_wire", "dual_edge_repeater",
                )
            ],
            "machinery": [
                p for p in uniq
                if p["id"] in (
                    "multi_piston_extender", "flying_machine", "nether_portal_cue",
                    "portal_frame_cue", "auto_smelt_brew_line", "water_stream_filter",
                    "water_hopper_stream", "shulker_loader", "crafter_auto_line",
                    "trial_spawner_cue", "vault_cue",
                )
            ],
            "sensors_extra": [
                p for p in uniq
                if p["id"] in (
                    "daylight_detector_clock", "tripwire_trap", "trapped_chest_line",
                    "lectern_signal", "chiseled_bookshelf_signal",
                )
            ],
        },
        "limits": PATTERN_LIMITS,
    }
