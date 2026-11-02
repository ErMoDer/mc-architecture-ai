# -*- coding: utf-8 -*-
from pathlib import Path
import ast

GS = Path(r"E:\ai agent\mc-architecture-ai\src\app\gen_strategy.py")
src = GS.read_text(encoding="utf-8")

old = '''def rule_scaffold_voxels(
    *,
    style: str,
    size: int = 32,
    seed: int = 0,
    wall_id: int = 1,
    floor_id: int = 1,
    roof_id: int | None = None,
    foundation_id: int | None = None,
    accent_id: int | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Procedural box house: footprint + shell + floors + pitched roof hint."""
    rng = np.random.default_rng(int(seed))
    sx = sy = sz = int(size)
    out = np.zeros((sx, sy, sz), dtype=np.int16)
    roof_id = int(wall_id if roof_id is None else roof_id)
    foundation_id = int(wall_id if foundation_id is None else foundation_id)
    accent_id = int(wall_id if accent_id is None else accent_id)

    bw = int(rng.integers(max(8, size // 3), max(9, min(size - 4, 18))))
    bd = int(rng.integers(max(8, size // 3), max(9, min(size - 4, 18))))
    bh = int(rng.integers(7, max(8, min(size - 4, 14))))
    x0 = (sx - bw) // 2
    z0 = (sz - bd) // 2
    y0 = 0
    x1, z1, y1 = x0 + bw, z0 + bd, y0 + bh

    floor_ys = _normalize_story_floors(
        None, y0=y0, y_roof=y1, spacing=6, min_gap=4, max_stories=3
    )

    build_box = np.zeros((sx, sz), dtype=bool)
    build_box[x0:x1, z0:z1] = True
    for y in floor_ys:
        if y >= sy or y >= y1:
            continue
        depth = 2 if y == y0 else 1
        ring = _ring_floor_mask(build_box, depth=depth, keep_cross=False)
        out[:, y, :][ring] = int(floor_id)

    for y in range(y0, min(y1 + 1, sy)):
        block = int(foundation_id) if y == y0 else int(wall_id)
        out[x0:x1, y, z0] = block
        out[x0:x1, y, z1 - 1] = block
        out[x0, y, z0:z1] = block
        out[x1 - 1, y, z0:z1] = block
        # corner accents
        if y > y0 and int(accent_id) != int(wall_id):
            for cx, cz in ((x0, z0), (x0, z1 - 1), (x1 - 1, z0), (x1 - 1, z1 - 1)):
                out[cx, y, cz] = int(accent_id)

    # Roof deck at y1 + broad low gable (plateau near ridge; match pitched harden)
    out[x0:x1, y1, z0:z1] = int(roof_id)
    half = max(1, min(bw, bd) // 2)
    rise = min(3, max(2, half // 3))
    plateau = max(2, int(0.72 * half))
    cx = (x0 + x1 - 1) / 2.0
    cz = (z0 + z1 - 1) / 2.0
    ridge_along_x = bw >= bd
    for x in range(x0, x1):
        for z in range(z0, z1):
            dist = abs(float(z) - cz) if ridge_along_x else abs(float(x) - cx)
            if dist <= plateau:
                h = min(sy - 1, y1 + rise)
            else:
                t = (dist - plateau) / max(1e-6, (half - plateau))
                h = min(sy - 1, y1 + max(0, int(round(rise * (1.0 - t)))))
            for yy in range(y1 + 1, h + 1):
                out[x, yy, z] = int(roof_id)

    door_x = (x0 + x1) // 2
    for yy in range(y0 + 1, min(y0 + 3, sy)):
        out[door_x, yy, z1 - 1] = 0

    stats = {
        "bbox": [x0, y0, z0, x1, y1, z1],
        "floor_ys": floor_ys,
        "bw": bw,
        "bd": bd,
        "bh": bh,
        "style": style,
        "role_ids": {
            "wall": int(wall_id),
            "floor": int(floor_id),
            "roof": int(roof_id),
            "foundation": int(foundation_id),
            "accent": int(accent_id),
        },
    }
    return out, stats
'''

new = '''def rule_scaffold_voxels(
    *,
    style: str,
    size: int = 32,
    seed: int = 0,
    wall_id: int = 1,
    floor_id: int = 1,
    roof_id: int | None = None,
    foundation_id: int | None = None,
    accent_id: int | None = None,
    stairs_id: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Procedural box house: shell + ring floors + skin_gable or flat_eave + partitions."""
    rng = np.random.default_rng(int(seed))
    sx = sy = sz = int(size)
    out = np.zeros((sx, sy, sz), dtype=np.int16)
    roof_id = int(wall_id if roof_id is None else roof_id)
    foundation_id = int(wall_id if foundation_id is None else foundation_id)
    accent_id = int(wall_id if accent_id is None else accent_id)
    style_l = (style or "").strip().lower()

    bw = int(rng.integers(max(8, size // 3), max(9, min(size - 4, 18))))
    bd = int(rng.integers(max(8, size // 3), max(9, min(size - 4, 18))))
    bh = int(rng.integers(7, max(8, min(size - 4, 14))))
    x0 = (sx - bw) // 2
    z0 = (sz - bd) // 2
    y0 = 0
    x1, z1, y1 = x0 + bw, z0 + bd, y0 + bh

    floor_ys = _normalize_story_floors(
        None, y0=y0, y_roof=y1, spacing=6, min_gap=4, max_stories=3
    )

    build_box = np.zeros((sx, sz), dtype=bool)
    build_box[x0:x1, z0:z1] = True
    peri = _perimeter_mask(build_box)
    for y in floor_ys:
        if y >= sy or y >= y1:
            continue
        depth = 2 if y == y0 else 1
        ring = _ring_floor_mask(build_box, depth=depth, keep_cross=False)
        out[:, y, :][ring] = int(floor_id)

    for y in range(y0, min(y1 + 1, sy)):
        block = int(foundation_id) if y == y0 else int(wall_id)
        out[x0:x1, y, z0] = block
        out[x0:x1, y, z1 - 1] = block
        out[x0, y, z0:z1] = block
        out[x1 - 1, y, z0:z1] = block
        if y > y0 and int(accent_id) != int(wall_id):
            for cx, cz in ((x0, z0), (x0, z1 - 1), (x1 - 1, z0), (x1 - 1, z1 - 1)):
                out[cx, y, cz] = int(accent_id)

    pitched = style_l in (
        "european", "rustic", "western", "chinese", "japanese", "medieval", "fantasy",
    )
    if pitched:
        rise = min(4, max(2, min(bw, bd) // 3))
        plateau = 0.40 if style_l in ("european", "rustic", "western") else 0.55
        oh = 2 if style_l in ("european", "rustic", "chinese", "western") else 1
        # clear any solid deck first — skin_gable owns the silhouette
        out[x0:x1, y1:sy, z0:z1] = 0
        # restore peri walls up to eave
        for y in range(y0 + 1, min(y1 + 1, sy)):
            out[x0:x1, y, z0] = int(wall_id)
            out[x0:x1, y, z1 - 1] = int(wall_id)
            out[x0, y, z0:z1] = int(wall_id)
            out[x1 - 1, y, z0:z1] = int(wall_id)
            if y > y0 and int(accent_id) != int(wall_id):
                for cx, cz in ((x0, z0), (x0, z1 - 1), (x1 - 1, z0), (x1 - 1, z1 - 1)):
                    out[cx, y, cz] = int(accent_id)
        roof_count, rinfo = _place_skin_gable_roof(
            out,
            roof_fp=build_box,
            peri=peri,
            eave_y=int(y1),
            roof_id=int(roof_id),
            rise=int(rise),
            plateau_frac=float(plateau),
            overhang=int(oh),
            wall_id=int(wall_id),
            clear_attic=True,
            stairs_id=int(stairs_id or 0),
        )
        roof_mode = str(rinfo.get("roof_mode") or "skin_gable")
        roof_stairs = int(rinfo.get("roof_stairs") or 0)
    else:
        # industrial / modern: flat deck + 1-cell eave lip
        out[x0:x1, y1, z0:z1] = int(roof_id)
        oh_n = 0
        for x in range(x0, x1):
            for z in (z0 - 1, z1):
                if 0 <= z < sz and out[x, y1, z] == 0:
                    out[x, y1, z] = int(roof_id)
                    oh_n += 1
        for z in range(z0, z1):
            for x in (x0 - 1, x1):
                if 0 <= x < sx and out[x, y1, z] == 0:
                    out[x, y1, z] = int(roof_id)
                    oh_n += 1
        roof_count = int(bw * bd) + oh_n
        roof_mode = "flat_eave_deck"
        roof_stairs = 0

    door_x = (x0 + x1) // 2
    for yy in range(y0 + 1, min(y0 + 3, sy)):
        out[door_x, yy, z1 - 1] = 0

    part = _place_interior_partitions(
        out,
        build_fp=build_box,
        peri=peri,
        y0=int(y0),
        y1=int(y1),
        wall_id=int(wall_id),
        style=style_l,
    )

    stats = {
        "bbox": [x0, y0, z0, x1, y1, z1],
        "floor_ys": floor_ys,
        "bw": bw,
        "bd": bd,
        "bh": bh,
        "style": style,
        "roof": int(roof_count),
        "roof_mode": roof_mode,
        "roof_stairs": int(roof_stairs),
        "partition_mode": part.get("mode"),
        "partition_cells": int(part.get("partition_cells") or 0),
        "rooms_est": int(part.get("rooms_est") or 1),
        "role_ids": {
            "wall": int(wall_id),
            "floor": int(floor_id),
            "roof": int(roof_id),
            "foundation": int(foundation_id),
            "accent": int(accent_id),
        },
    }
    return out, stats
'''

if old not in src:
    raise SystemExit("rule_scaffold block not found exactly")
src = src.replace(old, new, 1)
GS.write_text(src, encoding="utf-8")
ast.parse(src)
print("rule_scaffold patched, lines", len(src.splitlines()))