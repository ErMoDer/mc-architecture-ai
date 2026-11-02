# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("src/app/structure_constraints.py")
text = path.read_text(encoding="utf-8")

HELPER = r'''
def _enclosed_air_metrics(solid: np.ndarray) -> dict[str, Any]:
    """Largest enclosed air cavity (air not reachable from the volume border)."""
    solid = np.asarray(solid, dtype=bool)
    sx, sy, sz = solid.shape
    air = ~solid
    if not air.any():
        return {
            "max_enclosed_air_cc": 0,
            "enclosed_air_total": 0,
            "enclosed_air_ccs": 0,
            "exterior_air_cells": 0,
        }
    exterior = np.zeros(solid.shape, dtype=bool)
    q: deque[tuple[int, int, int]] = deque()
    for x in range(sx):
        for y in range(sy):
            for z in (0, sz - 1):
                if air[x, y, z] and not exterior[x, y, z]:
                    exterior[x, y, z] = True
                    q.append((x, y, z))
        for z in range(sz):
            for y in (0, sy - 1):
                if air[x, y, z] and not exterior[x, y, z]:
                    exterior[x, y, z] = True
                    q.append((x, y, z))
    for y in range(sy):
        for z in range(sz):
            for x in (0, sx - 1):
                if air[x, y, z] and not exterior[x, y, z]:
                    exterior[x, y, z] = True
                    q.append((x, y, z))
    neigh = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    while q:
        x, y, z = q.popleft()
        for dx, dy, dz in neigh:
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz:
                if air[nx, ny, nz] and not exterior[nx, ny, nz]:
                    exterior[nx, ny, nz] = True
                    q.append((nx, ny, nz))
    enclosed = air & (~exterior)
    if not enclosed.any():
        return {
            "max_enclosed_air_cc": 0,
            "enclosed_air_total": 0,
            "enclosed_air_ccs": 0,
            "exterior_air_cells": int(exterior.sum()),
        }
    n_cc, sizes, _ = _connected_components(enclosed)
    return {
        "max_enclosed_air_cc": int(sizes[0]) if sizes else 0,
        "enclosed_air_total": int(enclosed.sum()),
        "enclosed_air_ccs": int(n_cc),
        "exterior_air_cells": int(exterior.sum()),
    }


def _floor_cover_metrics(solid: np.ndarray) -> dict[str, Any]:
    """Mean footprint fill at detected floor Y peaks (1.0 = solid slab)."""
    floors = _floor_metrics(solid)
    peaks = list(floors.get("y_peaks") or [])
    fp, fp_n = _footprint(solid)
    if fp_n <= 0 or not peaks:
        return {"floor_cover_mean": 0.0, "floor_cover_per_y": {}, "floor_ys_cover": []}
    per: dict[str, float] = {}
    scores: list[float] = []
    for y in peaks:
        y = int(y)
        if y < 0 or y >= solid.shape[1]:
            continue
        filled = int((solid[:, y, :] & fp).sum())
        cov = float(filled) / float(fp_n)
        per[str(y)] = round(cov, 4)
        scores.append(cov)
    return {
        "floor_cover_mean": float(sum(scores) / len(scores)) if scores else 0.0,
        "floor_cover_per_y": per,
        "floor_ys_cover": [int(y) for y in peaks],
    }


'''

if "def _enclosed_air_metrics" not in text:
    anchor = "def _roof_score(solid: np.ndarray) -> dict[str, float]:"
    if anchor not in text:
        raise SystemExit("roof_score missing")
    text = text.replace(anchor, HELPER + anchor, 1)
    print("inserted helpers")
else:
    print("helpers exist")

old_th = '''SCAFFOLD_THRESHOLDS: dict[str, float] = {
    **DEFAULT_THRESHOLDS,
    "min_exterior_solid_frac": 0.0,  # volume-box faces; centered scaffolds often 0
    "min_roof_score": 0.18,
    "min_hollow_score": 0.28,
    "min_largest_cc_frac": 0.35,
    "min_non_air": 80,
}
'''
new_th = '''SCAFFOLD_THRESHOLDS: dict[str, float] = {
    **DEFAULT_THRESHOLDS,
    "min_exterior_solid_frac": 0.0,  # volume-box faces; centered scaffolds often 0
    "min_roof_score": 0.18,
    "min_hollow_score": 0.30,
    "min_largest_cc_frac": 0.35,
    "min_non_air": 80,
    "min_max_enclosed_air_cc": 120,
    "max_floor_cover_mean": 0.72,
}
'''
if old_th in text:
    text = text.replace(old_th, new_th, 1)
    print("thresholds updated")
elif "min_max_enclosed_air_cc" in text:
    print("thresholds already ok")
else:
    raise SystemExit("thresholds block mismatch")

old_comp = '''    hollow = _hollow_metrics(solid)
    floors = _floor_metrics(solid)
    roof = _roof_score(solid)
    _fp, fp_n = _footprint(solid)
    return {
        "shape": list(vox.shape),
        "non_air": non_air,
        "n_components": n_cc,
        "largest_cc": largest,
        "largest_cc_frac": float(largest / max(1, non_air)),
        "footprint": fp_n,
        **hollow,
        "floor_guess": floors["floor_guess"],
        "y_peaks": floors["y_peaks"],
        **roof,
    }
'''
new_comp = '''    hollow = _hollow_metrics(solid)
    floors = _floor_metrics(solid)
    roof = _roof_score(solid)
    _fp, fp_n = _footprint(solid)
    enclosed = _enclosed_air_metrics(solid)
    floor_cover = _floor_cover_metrics(solid)
    return {
        "shape": list(vox.shape),
        "non_air": non_air,
        "n_components": n_cc,
        "largest_cc": largest,
        "largest_cc_frac": float(largest / max(1, non_air)),
        "footprint": fp_n,
        **hollow,
        "floor_guess": floors["floor_guess"],
        "y_peaks": floors["y_peaks"],
        **roof,
        **enclosed,
        **floor_cover,
    }
'''
if old_comp not in text:
    raise SystemExit("compute block mismatch")
text = text.replace(old_comp, new_comp, 1)
print("compute wired")

old_ret = '''    if m["footprint"] < th["min_footprint"]:
        reasons.append(
            "占地过小 footprint=%s<%s" % (m["footprint"], th["min_footprint"])
        )
    return StructureReport(ok=len(reasons) == 0, reasons=reasons, metrics=m)
'''
new_ret = '''    if m["footprint"] < th["min_footprint"]:
        reasons.append(
            "占地过小 footprint=%s<%s" % (m["footprint"], th["min_footprint"])
        )
    max_enc = float(th.get("min_max_enclosed_air_cc") or 0)
    if max_enc > 0 and float(m.get("max_enclosed_air_cc") or 0) < max_enc:
        reasons.append(
            "房间空腔过小 max_enclosed=%s<%s"
            % (int(m.get("max_enclosed_air_cc") or 0), int(max_enc))
        )
    max_fc = float(th.get("max_floor_cover_mean") or 0)
    if max_fc > 0 and float(m.get("floor_cover_mean") or 0) > max_fc:
        reasons.append(
            "楼板过满 floor_cover=%.2f>%s" % (float(m.get("floor_cover_mean") or 0), max_fc)
        )
    return StructureReport(ok=len(reasons) == 0, reasons=reasons, metrics=m)
'''
if "min_max_enclosed_air_cc" not in text[text.find("def check_structure"): text.find("def _mode_solid_id")]:
    if old_ret not in text:
        raise SystemExit("check_structure tail mismatch")
    text = text.replace(old_ret, new_ret, 1)
    print("check gates added")
else:
    print("check gates exist")

path.write_text(text, encoding="utf-8")
print("WROTE", path)