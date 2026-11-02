# -*- coding: utf-8 -*-
"""Phase B: multi-room partitions + stair skin gable + rules + smoke helper."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
GS = ROOT / "src" / "app" / "gen_strategy.py"
RULES = ROOT / "docs" / "mc-knowledge" / "builds" / "look_harden_rules.json"
SHAPE = ROOT / "docs" / "mc-knowledge" / "builds" / "shape-language.md"


NEW_PARTITIONS = r'''
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

    When the eroded interior is large enough, prefer cross or T so the hollow core
    reads as multiple rooms instead of one box with a single mid wall.
    """
    sx, sy, sz = out.shape
    y0, y1 = int(y0), int(y1)
    info: dict[str, Any] = {"partition_cells": 0, "door_cells": 0, "mode": "none", "rooms_est": 1}
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

    # Size / style policy (Phase B knowledge: avoid single-box interiors)
    area = int(interior.sum())
    large = min(wx, wz) >= 7 and max(wx, wz) >= 11 and area >= 48
    huge = min(wx, wz) >= 9 and max(wx, wz) >= 14 and area >= 80
    simple = style_l in ("modern", "industrial", "scifi")

    mid_z = _best_z()
    mid_x = _best_x()
    primary_along_x = wx >= wz  # wall parallel to X (const z)

    if simple:
        # One mid wall only — open loft / workshop feel
        if primary_along_x:
            coords = _line_z(mid_z)
            _paint_wall_line(coords, len(coords) // 2)
            info["mode"] = "mid_z"
        else:
            coords = _line_x(mid_x)
            _paint_wall_line(coords, len(coords) // 2)
            info["mode"] = "mid_x"
        info["rooms_est"] = 2
    elif huge:
        # Full cross: both axes with doorways → ~4 rooms
        cz = _line_z(mid_z)
        cx = _line_x(mid_x)
        _paint_wall_line(cz, len(cz) // 2)
        _paint_wall_line(cx, len(cx) // 2)
        info["mode"] = "cross_split"
        info["rooms_est"] = 4
    elif large:
        # T-split: primary mid + one stub wing with doorway on primary only
        if primary_along_x:
            coords = _line_z(mid_z)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            stub_len = max(3, wz // 2)
            stub: list[tuple[int, int]] = []
            # Prefer stub toward the larger half
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
        # Medium: mid + short L stub (legacy)
        if primary_along_x:
            coords = _line_z(mid_z)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            info["mode"] = "mid_z"
            if max(wx, wz) >= 10:
                ax = coords[door_idx][0] if coords else mid_x
                stub_len = max(2, wz // 3)
                stub = [(ax, z) for z in range(mid_z + 1, min(maxz, mid_z + stub_len) + 1) if interior[ax, z]]
                if len(stub) >= 2:
                    _paint_wall_line(stub, door_idx=len(stub))
                    info["mode"] = "L_split"
            info["rooms_est"] = 3 if info["mode"] == "L_split" else 2
        else:
            coords = _line_x(mid_x)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            info["mode"] = "mid_x"
            if max(wx, wz) >= 10:
                az = coords[door_idx][1] if coords else mid_z
                stub_len = max(2, wx // 3)
                stub = [(x, az) for x in range(mid_x + 1, min(maxx, mid_x + stub_len) + 1) if interior[x, az]]
                if len(stub) >= 2:
                    _paint_wall_line(stub, door_idx=len(stub))
                    info["mode"] = "L_split"
            info["rooms_est"] = 3 if info["mode"] == "L_split" else 2

    info["partition_cells"] = int(cells)
    info["door_cells"] = int(door_cells)
    return info
'''.lstrip('\n')


def replace_function(src: str, func_name: str, new_body: str) -> str:
    """Replace def func_name(...) ... until next top-level def."""
    pat = re.compile(rf"^def {re.escape(func_name)}\(", re.M)
    m = pat.search(src)
    if not m:
        raise SystemExit(f"function {func_name} not found")
    start = m.start()
    # find next def at column 0 after start
    m2 = re.search(r"^def ", src[m.end():], re.M)
    if not m2:
        raise SystemExit(f"no next def after {func_name}")
    end = m.end() + m2.start()
    return src[:start] + new_body.rstrip() + "\n\n\n" + src[end:]


def patch_skin_gable(src: str) -> str:
    """Add stairs_id to _place_skin_gable_roof signature and place stairs on slope peri."""
    old_sig = '''def _place_skin_gable_roof(
    out: np.ndarray,
    *,
    roof_fp: np.ndarray,
    peri: np.ndarray,
    eave_y: int,
    roof_id: int,
    rise: int,
    plateau_frac: float = 0.35,
    overhang: int = 1,
    wall_id: int | None = None,
    clear_attic: bool = True,
) -> tuple[int, dict[str, Any]]:'''
    new_sig = '''def _place_skin_gable_roof(
    out: np.ndarray,
    *,
    roof_fp: np.ndarray,
    peri: np.ndarray,
    eave_y: int,
    roof_id: int,
    rise: int,
    plateau_frac: float = 0.35,
    overhang: int = 1,
    wall_id: int | None = None,
    clear_attic: bool = True,
    stairs_id: int = 0,
) -> tuple[int, dict[str, Any]]:'''
    if old_sig not in src:
        raise SystemExit("skin_gable sig not found")
    src = src.replace(old_sig, new_sig, 1)

    # After skin placement loop, before overhang section — inject stairs on peri slope
    marker = "    # 4) overhang eave ring"
    if marker not in src:
        raise SystemExit("overhang marker not found")
    stairs_block = '''    # 3b) stairs on outer slope (peri, below peak) for readable gable silhouette
    stair_n = 0
    sid = int(stairs_id or 0)
    if sid > 0:
        for x, z in zip(xs.tolist(), zs.tolist()):
            if not peri[x, z]:
                continue
            h_off = int(rise_map[x, z])
            peak = int(min(sy - 1, eave_y + h_off))
            if peak <= eave_y:
                continue
            # only on sloping face (not flat ridge plateau)
            if h_off >= int(ginfo.get("rise") or rise):
                continue
            out[x, peak, z] = sid
            stair_n += 1
        if stair_n:
            roof_count += 0  # stairs replace skin cells already counted
    info_stairs = {"roof_stairs": int(stair_n)}

    # 4) overhang eave ring'''
    src = src.replace(marker, stairs_block, 1)

    # Merge stairs into info dict near return
    old_info = '''    info = {
        "roof_mode": "skin_gable",
        "eave_y": eave_y,
        "overhang": oh,
        "overhang_cells": oh_n,
        **ginfo,
    }
    return roof_count, info'''
    new_info = '''    info = {
        "roof_mode": "skin_gable",
        "eave_y": eave_y,
        "overhang": oh,
        "overhang_cells": oh_n,
        "roof_stairs": int(stair_n) if "stair_n" in dir() else int(locals().get("stair_n", 0) or 0),
        **ginfo,
    }
    # stair_n always defined above when stairs path ran; ensure key
    if "stair_n" in locals():
        info["roof_stairs"] = int(stair_n)
    return roof_count, info'''
    # cleaner version:
    new_info = '''    info = {
        "roof_mode": "skin_gable",
        "eave_y": eave_y,
        "overhang": oh,
        "overhang_cells": oh_n,
        "roof_stairs": int(stair_n),
        **ginfo,
    }
    return roof_count, info'''
    if old_info not in src:
        raise SystemExit("info return block not found")
    src = src.replace(old_info, new_info, 1)
    return src


def patch_scaffold_stairs_call(src: str) -> str:
    """Pass stairs_id into skin gable from optional param; add stairs_id to scaffold_from_occupancy."""
    old = '''def scaffold_from_occupancy(
    occupancy: np.ndarray,
    *,
    wall_id: int,
    floor_id: int,
    floor_ys: list[int] | None = None,
    shell_thickness: int = 1,
    style: str | None = None,
    roof_id: int | None = None,
    foundation_id: int | None = None,
    accent_id: int | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:'''
    new = '''def scaffold_from_occupancy(
    occupancy: np.ndarray,
    *,
    wall_id: int,
    floor_id: int,
    floor_ys: list[int] | None = None,
    shell_thickness: int = 1,
    style: str | None = None,
    roof_id: int | None = None,
    foundation_id: int | None = None,
    accent_id: int | None = None,
    stairs_id: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:'''
    if old not in src:
        raise SystemExit("scaffold_from_occupancy sig not found")
    src = src.replace(old, new, 1)

    # In want_skin_gable call, add stairs_id=
    old_call = '''            roof_count, rinfo = _place_skin_gable_roof(
                out,
                roof_fp=use_roof_fp,
                peri=peri,
                eave_y=int(roof_deck_y),
                roof_id=int(roof_id),
                rise=int(max_rise),
                plateau_frac=float(plateau),
                overhang=int(oh),
                wall_id=int(wall_id),
                clear_attic=True,
            )'''
    new_call = '''            roof_count, rinfo = _place_skin_gable_roof(
                out,
                roof_fp=use_roof_fp,
                peri=peri,
                eave_y=int(roof_deck_y),
                roof_id=int(roof_id),
                rise=int(max_rise),
                plateau_frac=float(plateau),
                overhang=int(oh),
                wall_id=int(wall_id),
                clear_attic=True,
                stairs_id=int(stairs_id or 0),
            )'''
    if old_call not in src:
        raise SystemExit("skin_gable call not found")
    src = src.replace(old_call, new_call, 1)
    # track stairs in stats
    src = src.replace(
        'stats["gable_rise"] = int(rinfo.get("rise") or max_rise)\n            stats["sparse_interior_posts"] = False',
        'stats["gable_rise"] = int(rinfo.get("rise") or max_rise)\n'
        '            stats["roof_stairs"] = int(rinfo.get("roof_stairs") or 0)\n'
        '            stats["sparse_interior_posts"] = False',
        1,
    )
    return src


def add_stairs_helper_and_wire(src: str) -> str:
    """Add _resolve_stairs_from_palette and pass into scaffold_from_occupancy calls."""
    helper = '''
def _resolve_stairs_from_palette(
    palette: dict[int, str],
    *,
    roof_id: int,
    wall_id: int,
    style: str | None = None,
) -> int:
    """Map roof/wall role to a *_stairs block for gable slope accents."""
    name_to_id = {str(v): int(k) for k, v in palette.items()}
    # also short names without minecraft:
    for k, v in list(name_to_id.items()):
        short = k.split(":")[-1]
        name_to_id.setdefault(short, v)

    def _pick(cands: list[str]) -> int:
        for c in cands:
            for key in (c, f"minecraft:{c}"):
                if key in name_to_id and int(name_to_id[key]) > 0:
                    return int(name_to_id[key])
        return 0

    roof_name = str(palette.get(int(roof_id), "")).split(":")[-1]
    wall_name = str(palette.get(int(wall_id), "")).split(":")[-1]
    cands: list[str] = []
    for base in (roof_name, wall_name):
        if base.endswith("_planks"):
            cands.append(base.replace("_planks", "_stairs"))
        if base.endswith("_bricks"):
            cands.append(base[:-1] + "_stairs" if base.endswith("s") else base + "_stairs")
            cands.append(base.replace("_bricks", "_brick_stairs"))
        if base.endswith("_block"):
            cands.append(base.replace("_block", "_stairs"))
    style_l = (style or "").strip().lower()
    if style_l in ("european", "medieval", "rustic", "western"):
        cands += ["dark_oak_stairs", "spruce_stairs", "oak_stairs", "brick_stairs", "stone_brick_stairs"]
    elif style_l in ("chinese", "japanese", "fantasy"):
        cands += ["dark_oak_stairs", "spruce_stairs", "mangrove_stairs", "oak_stairs"]
    else:
        cands += ["oak_stairs", "spruce_stairs", "stone_brick_stairs", "cobblestone_stairs"]
    return _pick(cands)


'''
    # insert before scaffold_from_occupancy
    if "_resolve_stairs_from_palette" not in src:
        src = src.replace(
            "\ndef scaffold_from_occupancy(\n",
            "\n" + helper + "def scaffold_from_occupancy(\n",
            1,
        )

    # Wire call sites that have palette + mat_info
    # Pattern after corner_id assignment
    old = '''                vox, sc_stats = scaffold_from_occupancy(
                    occ,
                    wall_id=wall_id,
                    floor_id=floor_id,
                    floor_ys=floor_ys or None,
                    style=style,
                    roof_id=roof_id,
                    foundation_id=foundation_id,
                    accent_id=corner_id,
                )'''
    new = '''                stairs_id = _resolve_stairs_from_palette(
                    palette, roof_id=int(roof_id), wall_id=int(wall_id), style=style
                )
                vox, sc_stats = scaffold_from_occupancy(
                    occ,
                    wall_id=wall_id,
                    floor_id=floor_id,
                    floor_ys=floor_ys or None,
                    style=style,
                    roof_id=roof_id,
                    foundation_id=foundation_id,
                    accent_id=corner_id,
                    stairs_id=int(stairs_id),
                )'''
    if old not in src:
        raise SystemExit("scaffold call site not found for stairs wire")
    src = src.replace(old, new, 1)
    return src


def patch_rules() -> None:
    data = json.loads(RULES.read_text(encoding="utf-8"))
    data["version"] = 3
    data["updated"] = "2026-10-21"
    data["id"] = "look_harden_rules_v3"
    data["defaults"]["wall_pier_spacing"] = 8
    data["defaults"]["partition_policy"] = "size_adaptive"
    data["defaults"]["roof_prefer_skin_gable"] = True
    data["defaults"]["roof_slope_stairs"] = True
    data["partition_modes"] = {
        "modern": "mid_only",
        "industrial": "mid_only",
        "european": "T_or_cross",
        "rustic": "T_or_cross",
        "chinese": "T_or_cross",
        "western": "T_or_L",
        "medieval": "T_or_cross",
        "fantasy": "T_or_cross",
    }
    data["notes"]["partition_policy"] = (
        "Phase B: large hollow interiors use T/cross splits with doorways; "
        "industrial/modern stay mid-only open plans. Implemented in gen_strategy._place_interior_partitions."
    )
    data["notes"]["roof_slope_stairs"] = (
        "Pitched styles place *_stairs on peri slope below ridge (skin_gable); "
        "industrial/modern keep flat_eave_deck. Avoid solid attic fill."
    )
    data["notes"]["wall_pier_spacing"] = (
        "Default 8; rustic uses 12 via _STYLE_FACADE to avoid pier forests. "
        "STYLE_ROLE_FALLBACKS / DENY still gate materials."
    )
    RULES.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("rules updated to v3")


def patch_shape_language() -> None:
    text = SHAPE.read_text(encoding="utf-8")
    note = """

## Phase B additive (2026-10-21)

- **Rooms**: Prefer T-split or cross partitions when the eroded interior is large; mid-only for industrial/modern lofts. Always leave a 2-high doorway so `room_air` stays connected.
- **Roof**: Residential pitched styles → hollow `skin_gable` + optional slope stairs; never solid attic fill. Industrial/modern → `flat_eave` lip only.
- **Piers**: Facade accents at wide spacing (≈8–12); load path = corners + wall piers, not random interior columns.
"""
    if "Phase B additive" not in text:
        SHAPE.write_text(text.rstrip() + note, encoding="utf-8")
        print("shape-language.md appended")
    else:
        print("shape-language already has Phase B note")


def main() -> None:
    src = GS.read_text(encoding="utf-8")
    src = replace_function(src, "_place_interior_partitions", NEW_PARTITIONS)
    src = patch_skin_gable(src)
    src = patch_scaffold_stairs_call(src)
    src = add_stairs_helper_and_wire(src)
    # init stair_n = 0 before stairs block in case — already set in injected block
    # Ensure stair_n defined even if we somehow skip — the injected block defines stair_n = 0
    GS.write_text(src, encoding="utf-8")
    import ast
    ast.parse(src)
    print("gen_strategy.py AST OK, lines", len(src.splitlines()))
    patch_rules()
    patch_shape_language()


if __name__ == "__main__":
    main()