# -*- coding: utf-8 -*-
"""Phase D: style-aware milder partitions for chinese/medieval/fantasy."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
GS = ROOT / "src" / "app" / "gen_strategy.py"

NEW = r'''
def _place_interior_partitions(
    out: np.ndarray,
    *,
    build_fp: np.ndarray,
    peri: np.ndarray,
    y0: int,
    y1: int,
    wall_id: int,
    style: str | None = None,
) -> dict[str, Any]:
    """Room splits: mid / L / T / cross with doorways; keep large connected room_air.

    Phase D — style-aware aggressiveness:
    - industrial/modern: mid only (open loft)
    - chinese/medieval/fantasy: mid or short L only; cap wall height (~1 story)
      so cross_split no longer eats hundreds of room_air cells
    - european/rustic/western: keep T/cross when cavity is large enough
    """
    sx, sy, sz = out.shape
    y0, y1 = int(y0), int(y1)
    info: dict[str, Any] = {
        "partition_cells": 0,
        "door_cells": 0,
        "mode": "none",
        "rooms_est": 1,
        "policy": "none",
    }
    if y1 <= y0 + 3 or not build_fp.any():
        return info
    interior = build_fp & ~peri
    if interior.any():
        thick = _dilate_mask(peri, 1)
        interior = interior & ~thick
    xs, zs = np.where(interior)
    if xs.size < 20:
        return info
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    if min(wx, wz) < 5:
        return info
    style_l = (style or "").strip().lower()
    cells = 0
    door_cells = 0
    y_lo = y0 + 1
    y_hi = min(y1 - 1, sy - 1)
    if y_hi <= y_lo:
        return info

    # Style tiers (Phase D)
    simple = style_l in ("modern", "industrial", "scifi")
    conservative = style_l in ("chinese", "medieval", "fantasy", "japanese")
    cross_friendly = style_l in ("european", "rustic", "western")
    if conservative:
        # One clear story of partition (~4–5 cells) — enough to read rooms, not a solid shaft
        y_hi = min(y_hi, y_lo + 4)
        info["policy"] = "conservative_mid_L"
    elif simple:
        info["policy"] = "open_mid"
    elif cross_friendly:
        info["policy"] = "cross_ok"
    else:
        info["policy"] = "default_L"

    door_h = 2
    door_y0 = y_lo
    door_y1 = min(y_lo + door_h - 1, y_hi)

    def _paint_wall_line(coords: list[tuple[int, int]], door_idx: int) -> None:
        nonlocal cells, door_cells
        n = len(coords)
        if n < 3:
            return
        for i, (x, z) in enumerate(coords):
            is_door = abs(i - door_idx) <= 0
            for y in range(y_lo, y_hi + 1):
                if is_door and door_y0 <= y <= door_y1:
                    if out[x, y, z] != 0 and out[x, y, z] != int(wall_id):
                        continue
                    out[x, y, z] = 0
                    door_cells += 1
                    continue
                cur = int(out[x, y, z])
                if cur == 0:
                    out[x, y, z] = int(wall_id)
                    cells += 1

    def _line_z(mid_z: int) -> list[tuple[int, int]]:
        return [(int(x), mid_z) for x in range(minx, maxx + 1) if interior[x, mid_z]]

    def _line_x(mid_x: int) -> list[tuple[int, int]]:
        return [(mid_x, int(z)) for z in range(minz, maxz + 1) if interior[mid_x, z]]

    def _best_z() -> int:
        mid_z = int(round((minz + maxz) / 2.0))
        best_z, best_n = mid_z, -1
        for zz in range(minz, maxz + 1):
            n = int(interior[:, zz].sum()) if 0 <= zz < sz else 0
            if n > best_n:
                best_n, best_z = n, zz
        return best_z

    def _best_x() -> int:
        mid_x = int(round((minx + maxx) / 2.0))
        best_x, best_n = mid_x, -1
        for xx in range(minx, maxx + 1):
            n = int(interior[xx, :].sum()) if 0 <= xx < sx else 0
            if n > best_n:
                best_n, best_x = n, xx
        return best_x

    def _do_mid_or_L(*, stub_frac: float = 0.33, stub_cap: int = 6, force_L: bool = False) -> None:
        nonlocal cells  # painted via closure
        if primary_along_x:
            coords = _line_z(mid_z)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            info["mode"] = "mid_z"
            want_L = force_L or max(wx, wz) >= 10
            if want_L and coords:
                ax = coords[door_idx][0]
                stub_len = max(2, min(stub_cap, int(wz * stub_frac)))
                stub = [
                    (ax, z)
                    for z in range(mid_z + 1, min(maxz, mid_z + stub_len) + 1)
                    if interior[ax, z]
                ]
                if len(stub) >= 2:
                    _paint_wall_line(stub, door_idx=len(stub))  # no door on stub tip
                    info["mode"] = "L_split"
            info["rooms_est"] = 3 if info["mode"] == "L_split" else 2
        else:
            coords = _line_x(mid_x)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            info["mode"] = "mid_x"
            want_L = force_L or max(wx, wz) >= 10
            if want_L and coords:
                az = coords[door_idx][1]
                stub_len = max(2, min(stub_cap, int(wx * stub_frac)))
                stub = [
                    (x, az)
                    for x in range(mid_x + 1, min(maxx, mid_x + stub_len) + 1)
                    if interior[x, az]
                ]
                if len(stub) >= 2:
                    _paint_wall_line(stub, door_idx=len(stub))
                    info["mode"] = "L_split"
            info["rooms_est"] = 3 if info["mode"] == "L_split" else 2

    area = int(interior.sum())
    # Cross-friendly needs a real cavity; raise bars vs Phase B to avoid densifying sparse refs
    large = min(wx, wz) >= 7 and max(wx, wz) >= 11 and area >= 48
    huge = min(wx, wz) >= 9 and max(wx, wz) >= 14 and area >= 80

    mid_z = _best_z()
    mid_x = _best_x()
    primary_along_x = wx >= wz

    if simple:
        if primary_along_x:
            coords = _line_z(mid_z)
            _paint_wall_line(coords, len(coords) // 2)
            info["mode"] = "mid_z"
        else:
            coords = _line_x(mid_x)
            _paint_wall_line(coords, len(coords) // 2)
            info["mode"] = "mid_x"
        info["rooms_est"] = 2
    elif conservative:
        # Never cross/T. Short L only when footprint is wide enough.
        _do_mid_or_L(stub_frac=0.25, stub_cap=4, force_L=(max(wx, wz) >= 12 and area >= 60))
    elif cross_friendly and huge:
        cz = _line_z(mid_z)
        cx = _line_x(mid_x)
        _paint_wall_line(cz, len(cz) // 2)
        _paint_wall_line(cx, len(cx) // 2)
        info["mode"] = "cross_split"
        info["rooms_est"] = 4
    elif cross_friendly and large:
        # T-split
        if primary_along_x:
            coords = _line_z(mid_z)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            stub_len = max(3, wz // 2)
            stub: list[tuple[int, int]] = []
            z_hi_span = maxz - mid_z
            z_lo_span = mid_z - minz
            if z_hi_span >= z_lo_span:
                z_range = range(mid_z + 1, min(maxz, mid_z + stub_len) + 1)
            else:
                z_range = range(max(minz, mid_z - stub_len), mid_z)
            ax = coords[door_idx][0] if coords else mid_x
            for z in z_range:
                if interior[ax, z]:
                    stub.append((ax, z))
            if len(stub) >= 3:
                _paint_wall_line(stub, door_idx=len(stub) // 2)
                info["mode"] = "T_split"
                info["rooms_est"] = 3
            else:
                info["mode"] = "mid_z"
                info["rooms_est"] = 2
        else:
            coords = _line_x(mid_x)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            stub_len = max(3, wx // 2)
            stub = []
            x_hi_span = maxx - mid_x
            x_lo_span = mid_x - minx
            if x_hi_span >= x_lo_span:
                x_range = range(mid_x + 1, min(maxx, mid_x + stub_len) + 1)
            else:
                x_range = range(max(minx, mid_x - stub_len), mid_x)
            az = coords[door_idx][1] if coords else mid_z
            for x in x_range:
                if interior[x, az]:
                    stub.append((x, az))
            if len(stub) >= 3:
                _paint_wall_line(stub, door_idx=len(stub) // 2)
                info["mode"] = "T_split"
                info["rooms_est"] = 3
            else:
                info["mode"] = "mid_x"
                info["rooms_est"] = 2
    else:
        # default / small cross-friendly: mid + short L
        _do_mid_or_L(stub_frac=0.33, stub_cap=6, force_L=False)

    info["partition_cells"] = int(cells)
    info["door_cells"] = int(door_cells)
    info["y_span"] = int(y_hi - y_lo + 1)
    return info
'''.lstrip("\n")


def replace_function(src: str, func_name: str, new_body: str) -> str:
    pat = re.compile(rf"^def {re.escape(func_name)}\(", re.M)
    m = pat.search(src)
    if not m:
        raise SystemExit(f"missing {func_name}")
    m2 = re.search(r"^def ", src[m.end() :], re.M)
    if not m2:
        raise SystemExit("no next def")
    end = m.end() + m2.start()
    return src[: m.start()] + new_body.rstrip() + "\n\n\n" + src[end:]


def main() -> None:
    src = GS.read_text(encoding="utf-8")
    src = replace_function(src, "_place_interior_partitions", NEW)
    GS.write_text(src, encoding="utf-8")
    ast.parse(src)
    print("gen_strategy patched, lines", len(src.splitlines()))

    # rules JSON
    rules_path = ROOT / "docs" / "mc-knowledge" / "builds" / "look_harden_rules.json"
    data = json.loads(rules_path.read_text(encoding="utf-8"))
    data["version"] = 4
    data["updated"] = "2026-10-21"
    data["id"] = "look_harden_rules_v4"
    data["partition_modes"] = {
        "modern": "mid_only",
        "industrial": "mid_only",
        "european": "T_or_cross",
        "rustic": "T_or_cross",
        "western": "T_or_cross",
        "chinese": "mid_or_short_L_story_cap",
        "medieval": "mid_or_short_L_story_cap",
        "fantasy": "mid_or_short_L_story_cap",
        "japanese": "mid_or_short_L_story_cap",
    }
    data["notes"]["partition_policy"] = (
        "Phase D: chinese/medieval/fantasy/japanese use mid or short L with ~1-story "
        "height cap (no cross) to protect room_air; european/rustic/western keep T/cross "
        "when cavity is large. industrial/modern mid-only."
    )
    rules_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("rules -> v4")

    # short actionable KB doc
    kb = ROOT / "docs" / "mc-knowledge" / "builds" / "partition-style-policy.md"
    kb.write_text(
        """# Interior partition style policy (Phase D)

Actionable knobs for `gen_strategy._place_interior_partitions` / `look_harden_rules.json` `partition_modes`.

## Why

Full-height `cross_split` on dense / tall styles (chinese, medieval, fantasy) added hundreds of solids and cut `interior_room_air` almost 1:1 (Phase C regression). European/rustic still benefit from stronger splits.

## Policy

| Tier | Styles | Max mode | Height |
|------|--------|----------|--------|
| open | industrial, modern | mid wall + door | full to eave-1 |
| mild | chinese, medieval, fantasy, japanese | mid or **short L** (stub ≤4) | **~1 story** (y_lo..y_lo+4) |
| strong | european, rustic, western | T or cross when cavity large | full to eave-1 |

## Requirements

- Always punch a 2-high doorway on the primary wall.
- Never fuse partitions into the outer shell (erode interior before placing).
- Prefer raising `room_air` over maximizing room count on mild tier.

## Wired

- Code: `src/app/gen_strategy.py` → `_place_interior_partitions`
- JSON: `look_harden_rules.json` v4 `partition_modes` + notes.partition_policy
""",
        encoding="utf-8",
    )
    print("wrote", kb.name)


if __name__ == "__main__":
    main()