# -*- coding: utf-8 -*-
"""Phase 2: structure constraints for 32^3 voxel samples (hollow / floors / roof).

Not a second model — heuristics around ConditionalVoxelVAE sampling.
Docs: docs/structure_constraints.md
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

DEFAULT_THRESHOLDS: dict[str, float] = {
    "min_non_air": 120,
    "max_non_air_frac": 0.72,  # relative to volume; absolute max_non_air optional
    "max_non_air": 0,  # 0 = use frac only
    "min_hollow_score": 0.32,
    "min_exterior_solid_frac": 0.06,
    "min_largest_cc_frac": 0.40,
    "min_floors": 1,
    "min_roof_score": 0.30,
    "min_footprint": 20,
}

# similar_scaffold / rule_scaffold: thin perimeter shells + sparse roofs fail VAE-era cuts
# (e.g. exterior 0.02-0.05, roof ~0.20) even when the footprint/shell is visually sane.
# Roof cover uses elevated footprint (see _elevated_footprint); min_roof stays 0.18.
SCAFFOLD_THRESHOLDS: dict[str, float] = {
    **DEFAULT_THRESHOLDS,
    "min_exterior_solid_frac": 0.0,  # volume-box faces; centered scaffolds often 0
    "min_roof_score": 0.18,
    "min_hollow_score": 0.30,
    "min_largest_cc_frac": 0.35,
    "min_non_air": 80,
    # Door/window openings connect rooms to outside, so enclosed-CC is advisory only.
    "min_max_enclosed_air_cc": 0,
    "max_floor_cover_mean": 0.0,  # prefer floor_interior_cover
    "max_floor_interior_cover": 0.70,
    "min_interior_room_air": 80,
}


@dataclass
class StructureReport:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    repairs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _solid_mask(voxels: np.ndarray) -> np.ndarray:
    return np.asarray(voxels) > 0


def _connected_components(solid: np.ndarray) -> tuple[int, list[int], np.ndarray]:
    sx, sy, sz = solid.shape
    labels = np.zeros(solid.shape, dtype=np.int32)
    sizes: list[int] = []
    neigh = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    xs, ys, zs = np.where(solid)
    cid = 0
    visited = np.zeros(solid.shape, dtype=np.uint8)
    for i in range(xs.size):
        x0, y0, z0 = int(xs[i]), int(ys[i]), int(zs[i])
        if visited[x0, y0, z0]:
            continue
        cid += 1
        q: deque[tuple[int, int, int]] = deque()
        q.append((x0, y0, z0))
        visited[x0, y0, z0] = 1
        count = 0
        while q:
            x, y, z = q.popleft()
            labels[x, y, z] = cid
            count += 1
            for dx, dy, dz in neigh:
                nx, ny, nz = x + dx, y + dy, z + dz
                if 0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz:
                    if solid[nx, ny, nz] and not visited[nx, ny, nz]:
                        visited[nx, ny, nz] = 1
                        q.append((nx, ny, nz))
        sizes.append(count)
    sizes.sort(reverse=True)
    return cid, sizes, labels


def _hollow_metrics(solid: np.ndarray) -> dict[str, float]:
    sx, sy, sz = solid.shape
    if min(sx, sy, sz) < 3:
        m = float(solid.mean()) if solid.size else 0.0
        return {
            "hollow_score": 0.0,
            "exterior_solid_frac": m,
            "interior_air_frac": float((~solid).mean()) if solid.size else 0.0,
            "interior_solid_frac": m,
        }
    interior = solid[1:-1, 1:-1, 1:-1]
    shell = solid.copy()
    shell[1:-1, 1:-1, 1:-1] = False
    interior_air = float((~interior).mean()) if interior.size else 0.0
    return {
        "hollow_score": float(np.clip(interior_air, 0.0, 1.0)),
        "exterior_solid_frac": float(shell.mean()) if shell.size else 0.0,
        "interior_air_frac": interior_air,
        "interior_solid_frac": float(interior.mean()) if interior.size else 0.0,
    }


def _floor_metrics(solid: np.ndarray) -> dict[str, Any]:
    per_y = solid.sum(axis=(0, 2)).astype(np.int64)
    total = int(per_y.sum())
    if total == 0:
        return {"floor_guess": 0, "y_peaks": [], "per_y_max": 0}
    thresh = max(3, int(0.08 * float(per_y.max())))
    peaks: list[int] = []
    for y in range(len(per_y)):
        v = int(per_y[y])
        if v < thresh:
            continue
        left = int(per_y[y - 1]) if y > 0 else 0
        right = int(per_y[y + 1]) if y + 1 < len(per_y) else 0
        if v >= left and v >= right:
            peaks.append(y)
    merged: list[int] = []
    for y in peaks:
        if merged and y - merged[-1] <= 2:
            if per_y[y] > per_y[merged[-1]]:
                merged[-1] = y
        else:
            merged.append(y)
    return {
        "floor_guess": max(1, len(merged)) if merged else 1,
        "y_peaks": merged,
        "per_y_max": int(per_y.max()),
        "per_y": per_y.tolist(),
    }


def _footprint(solid: np.ndarray) -> tuple[np.ndarray, int]:
    fp = solid.any(axis=1)
    return fp, int(fp.sum())


def _elevated_footprint(solid: np.ndarray) -> tuple[np.ndarray, int]:
    """Footprint for roof cover: columns with mass above the ground band.

    Full-box ground slabs (common after scaffold floors) inflate `_footprint` to
    ~32x32 and make sparse-but-real roofs look like cover~0.02. Prefer columns
    that rise above the foundation band.
    """
    fp_all, fp_all_n = _footprint(solid)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    if ys.size == 0:
        return fp_all, fp_all_n
    y_min, y_max = int(ys.min()), int(ys.max())
    height = max(1, y_max - y_min + 1)
    band = max(1, min(3, height // 4))
    y_cut = y_min + band
    if y_cut > y_max:
        return fp_all, fp_all_n
    elev = solid[:, y_cut : y_max + 1, :].any(axis=1)
    # Drop lone ground stubs: need at least 2 solids in the column span
    xs, zs = np.where(elev)
    for x, z in zip(xs.tolist(), zs.tolist()):
        if int(solid[x, y_min : y_max + 1, z].sum()) < 2:
            elev[x, z] = False
    elev_n = int(elev.sum())
    # Fallback if elevated mask collapsed (very flat pads)
    if elev_n < max(8, int(0.05 * max(1, fp_all_n))):
        return fp_all, fp_all_n
    return elev, elev_n



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
    """Floor fill metrics.

    floor_cover_mean: solids / full footprint at y_peaks (includes walls; ~0.6-0.8 normal for ring).
    floor_interior_cover: solids / interior (fp minus perimeter) — this is the slab-blob signal.
    """
    floors = _floor_metrics(solid)
    peaks = list(floors.get("y_peaks") or [])
    fp, fp_n = _footprint(solid)
    if fp_n <= 0 or not peaks:
        return {
            "floor_cover_mean": 0.0,
            "floor_interior_cover": 0.0,
            "floor_cover_per_y": {},
            "floor_ys_cover": [],
            "interior_room_air": 0,
        }
    # perimeter of footprint
    peri = np.zeros_like(fp)
    h, w = fp.shape
    xs, zs = np.where(fp)
    for x, z in zip(xs.tolist(), zs.tolist()):
        if x == 0 or z == 0 or x == h - 1 or z == w - 1:
            peri[x, z] = True
            continue
        if not (fp[x - 1, z] and fp[x + 1, z] and fp[x, z - 1] and fp[x, z + 1]):
            peri[x, z] = True
    inner = fp & (~peri)
    inner_n = int(inner.sum())
    per: dict[str, float] = {}
    scores: list[float] = []
    inner_scores: list[float] = []
    ys_all = np.where(solid.any(axis=(0, 2)))[0]
    y_top = int(ys_all.max()) if ys_all.size else -1
    for y in peaks:
        y = int(y)
        if y < 0 or y >= solid.shape[1]:
            continue
        # Roof deck / cap is supposed to be solid — exclude from floor-slab score
        if y_top >= 0 and y >= y_top - 1:
            continue
        filled = int((solid[:, y, :] & fp).sum())
        cov = float(filled) / float(fp_n)
        per[str(y)] = round(cov, 4)
        scores.append(cov)
        if inner_n > 0:
            inner_filled = int((solid[:, y, :] & inner).sum())
            inner_scores.append(float(inner_filled) / float(inner_n))
    # Room air: air over interior footprint between ground+1 and top-1 (door-tolerant)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    room_air = 0
    if ys.size and inner_n > 0:
        y0, y1 = int(ys.min()), int(ys.max())
        for y in range(y0 + 1, y1):
            room_air += int(((~solid[:, y, :]) & inner).sum())
    return {
        "floor_cover_mean": float(sum(scores) / len(scores)) if scores else 0.0,
        "floor_interior_cover": float(sum(inner_scores) / len(inner_scores)) if inner_scores else 0.0,
        "floor_cover_per_y": per,
        "floor_ys_cover": [int(y) for y in peaks],
        "interior_room_air": int(room_air),
    }


def _roof_score(solid: np.ndarray) -> dict[str, float]:
    ys = np.where(solid.any(axis=(0, 2)))[0]
    if ys.size == 0:
        return {"roof_score": 0.0, "top_y": -1, "top_band_frac": 0.0}
    y_min, y_max = int(ys.min()), int(ys.max())
    height = max(1, y_max - y_min + 1)
    band = max(1, height // 5)
    top = solid[:, y_max - band + 1 : y_max + 1, :]
    mid_lo = y_min + height // 3
    mid_hi = y_min + (2 * height) // 3
    mid = solid[:, mid_lo:mid_hi, :] if mid_hi > mid_lo else solid[:, y_min : y_max + 1, :]
    top_frac = float(top.mean()) if top.size else 0.0
    mid_frac = float(mid.mean()) if mid.size else 0.0
    top_slice = solid[:, y_max, :]
    fp_all, fp_all_n = _footprint(solid)
    fp_elev, fp_n = _elevated_footprint(solid)
    cover = float((top_slice & fp_elev).sum() / max(1, fp_n))
    cover_all = float((top_slice & fp_all).sum() / max(1, fp_all_n))
    # Prefer cover vs elevated fp; also reward top_band vs mid
    score = 0.45 * cover + 0.35 * min(1.0, top_frac * 4) + 0.2 * float(top_frac >= mid_frac * 0.5)
    # Mild boost when elevated cover is strong but volume-box top_frac is diluted by empty sky
    if cover >= 0.35 and cover_all < cover * 0.5:
        score = max(score, 0.40 * cover + 0.40 * min(1.0, cover * 1.2) + 0.2)
    return {
        "roof_score": float(np.clip(score, 0.0, 1.0)),
        "top_y": float(y_max),
        "top_band_frac": top_frac,
        "top_footprint_cover": cover,
        "top_footprint_cover_all": cover_all,
        "elevated_footprint": float(fp_n),
        "mid_frac": mid_frac,
    }


def compute_structure_metrics(voxels: np.ndarray) -> dict[str, Any]:
    vox = np.asarray(voxels)
    solid = _solid_mask(vox)
    non_air = int(solid.sum())
    n_cc, sizes, _labels = _connected_components(solid)
    largest = sizes[0] if sizes else 0
    hollow = _hollow_metrics(solid)
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


def check_structure(
    voxels: np.ndarray,
    thresholds: dict[str, float] | None = None,
) -> StructureReport:
    th = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    m = compute_structure_metrics(voxels)
    reasons: list[str] = []
    if m["non_air"] < th["min_non_air"]:
        reasons.append("non_air过少 %s<%s" % (m["non_air"], th["min_non_air"]))
    vol = int(np.prod(m["shape"])) if m.get("shape") else 0
    max_abs = int(th.get("max_non_air") or 0)
    max_frac = float(th.get("max_non_air_frac") or 0.72)
    max_allowed = max_abs if max_abs > 0 else int(max_frac * max(1, vol))
    m["max_non_air_allowed"] = max_allowed
    if m["non_air"] > max_allowed:
        reasons.append("non_air过多 %s>%s" % (m["non_air"], max_allowed))
    if m["hollow_score"] < th["min_hollow_score"]:
        reasons.append(
            "空心不足 hollow=%.2f<%s" % (m["hollow_score"], th["min_hollow_score"])
        )
    if m["exterior_solid_frac"] < th["min_exterior_solid_frac"]:
        reasons.append(
            "外壳稀 exterior=%.2f<%s"
            % (m["exterior_solid_frac"], th["min_exterior_solid_frac"])
        )
    if m["largest_cc_frac"] < th["min_largest_cc_frac"]:
        reasons.append(
            "主体连通弱 cc_frac=%.2f<%s"
            % (m["largest_cc_frac"], th["min_largest_cc_frac"])
        )
    if m["floor_guess"] < th["min_floors"]:
        reasons.append("楼层线索不足 floors=%s" % m["floor_guess"])
    if m["roof_score"] < th["min_roof_score"]:
        reasons.append(
            "屋顶线索弱 roof=%.2f<%s" % (m["roof_score"], th["min_roof_score"])
        )
    if m["footprint"] < th["min_footprint"]:
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
    max_fic = float(th.get("max_floor_interior_cover") or 0)
    if max_fic > 0 and float(m.get("floor_interior_cover") or 0) > max_fic:
        reasons.append(
            "室内楼板过满 interior_cover=%.2f>%s"
            % (float(m.get("floor_interior_cover") or 0), max_fic)
        )
    min_room = float(th.get("min_interior_room_air") or 0)
    if min_room > 0 and float(m.get("interior_room_air") or 0) < min_room:
        reasons.append(
            "室内开放空气不足 room_air=%s<%s"
            % (int(m.get("interior_room_air") or 0), int(min_room))
        )
    return StructureReport(ok=len(reasons) == 0, reasons=reasons, metrics=m)


def _mode_solid_id(voxels: np.ndarray, mask: np.ndarray | None = None) -> int:
    flat = voxels[mask] if mask is not None else voxels.ravel()
    flat = flat[flat > 0]
    if flat.size == 0:
        return 1
    vals, counts = np.unique(flat, return_counts=True)
    return int(vals[int(np.argmax(counts))])


def repair_structure(
    voxels: np.ndarray,
    *,
    keep_largest_cc: bool = True,
    carve_interior: bool = True,
    enforce_floors: bool = True,
    enforce_roof: bool = True,
    thicken_shell: bool = True,
) -> tuple[np.ndarray, list[str]]:
    out = np.asarray(voxels, dtype=np.int16).copy()
    repairs: list[str] = []
    solid = out > 0
    if not solid.any():
        return out, ["empty_skip"]

    if keep_largest_cc:
        n_cc, sizes, labels = _connected_components(solid)
        if n_cc > 1 and sizes:
            best_label = 1
            best_count = 0
            for lab in range(1, n_cc + 1):
                c = int((labels == lab).sum())
                if c > best_count:
                    best_count = c
                    best_label = lab
            drop = (labels > 0) & (labels != best_label)
            n_drop = int(drop.sum())
            if n_drop:
                out[drop] = 0
                repairs.append("drop_float_cc:%d" % n_drop)
                solid = out > 0

    fill_id = _mode_solid_id(out)
    sx, sy, sz = out.shape
    fp, _ = _footprint(solid)

    if carve_interior and min(sx, sy, sz) >= 5:
        carved = 0
        for x in range(2, sx - 2):
            for y in range(2, sy - 2):
                for z in range(2, sz - 2):
                    if out[x, y, z] == 0:
                        continue
                    if not (
                        out[x - 1, y, z]
                        and out[x + 1, y, z]
                        and out[x, y - 1, z]
                        and out[x, y + 1, z]
                        and out[x, y, z - 1]
                        and out[x, y, z + 1]
                    ):
                        continue
                    block = out[x - 1 : x + 2, y - 1 : y + 2, z - 1 : z + 2]
                    if int((block > 0).sum()) >= 18:
                        out[x, y, z] = 0
                        carved += 1
        if carved:
            repairs.append("carve_interior:%d" % carved)
            solid = out > 0
            fp, _ = _footprint(solid)
        # second lighter carve pass for stubborn cores
        carved2 = 0
        for x in range(2, sx - 2):
            for y in range(2, sy - 2):
                for z in range(2, sz - 2):
                    if out[x, y, z] == 0:
                        continue
                    block = out[x - 1 : x + 2, y - 1 : y + 2, z - 1 : z + 2]
                    if int((block > 0).sum()) >= 22:
                        out[x, y, z] = 0
                        carved2 += 1
        if carved2:
            repairs.append("carve_interior2:%d" % carved2)
            solid = out > 0
            fp, _ = _footprint(solid)

    if enforce_floors:
        floors = _floor_metrics(solid)
        peaks = list(floors["y_peaks"])
        ys = np.where(solid.any(axis=(0, 2)))[0]
        if ys.size:
            y0 = int(ys.min())
            y1 = int(ys.max())
            if not peaks:
                peaks = list(range(y0, y1 + 1, 5))
            if y0 not in peaks:
                peaks = [y0] + peaks
            added = 0
            # only plate cells that already have solid in the same column nearby
            for y in peaks:
                if y < 0 or y >= sy:
                    continue
                xs, zs = np.where(fp)
                for x, z in zip(xs.tolist(), zs.tolist()):
                    if out[x, y, z] != 0:
                        continue
                    col = out[x, :, z]
                    if int((col > 0).sum()) < 2:
                        continue
                    # prefer bridging gaps: solid within 2 below or above
                    lo = max(0, y - 2)
                    hi = min(sy, y + 3)
                    if int((col[lo:hi] > 0).sum()) == 0:
                        continue
                    out[x, y, z] = fill_id
                    added += 1
            if added:
                repairs.append("floors:%d@y=%s" % (added, peaks))
                solid = out > 0

    if enforce_roof:
        solid = out > 0
        fp, _ = _footprint(solid)
        ys = np.where(solid.any(axis=(0, 2)))[0]
        if ys.size and fp.any():
            top_y = int(ys.max())
            roof_y = top_y
            added = 0
            xs, zs = np.where(fp)
            # roof: only close columns that already have height
            for x, z in zip(xs.tolist(), zs.tolist()):
                if out[x, roof_y, z] != 0:
                    continue
                if int((out[x, :roof_y + 1, z] > 0).sum()) < 3:
                    continue
                out[x, roof_y, z] = fill_id
                added += 1
            if thicken_shell and roof_y > int(ys.min()) + 2:
                # only perimeter, and only fill gaps (do not grow solid cubes)
                for x, z in zip(xs.tolist(), zs.tolist()):
                    edge = False
                    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, nz = x + dx, z + dz
                        if not (0 <= nx < sx and 0 <= nz < sz) or not fp[nx, nz]:
                            edge = True
                            break
                    if not edge:
                        continue
                    for y in range(int(ys.min()), roof_y + 1):
                        if out[x, y, z] != 0:
                            continue
                        # fill only if neighbors on wall already solid (continuity)
                        nsolid = 0
                        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0)):
                            nx, ny, nz = x + dx, y + dy, z + dz
                            if 0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz and out[nx, ny, nz]:
                                nsolid += 1
                        if nsolid >= 2:
                            out[x, y, z] = fill_id
                            added += 1
            if added:
                repairs.append("roof_shell:%d@y=%d" % (added, roof_y))


    # density trim: keep carving deepest interior until under soft cap
    vol = int(out.size)
    cap = int(0.68 * vol)
    if int((out > 0).sum()) > cap and min(out.shape) >= 5:
        trimmed = 0
        sx, sy, sz = out.shape
        # priority: cells with highest solid neighborhood
        coords = []
        for x in range(1, sx - 1):
            for y in range(1, sy - 1):
                for z in range(1, sz - 1):
                    if out[x, y, z] == 0:
                        continue
                    block = out[x - 1 : x + 2, y - 1 : y + 2, z - 1 : z + 2]
                    coords.append((int((block > 0).sum()), x, y, z))
        coords.sort(reverse=True)
        for score, x, y, z in coords:
            if int((out > 0).sum()) <= cap:
                break
            if score < 12:
                break
            out[x, y, z] = 0
            trimmed += 1
        if trimmed:
            repairs.append("density_trim:%d" % trimmed)

    return out, repairs


def apply_structure_constraints(
    voxels: np.ndarray,
    *,
    mode: str = "repair",
    thresholds: dict[str, float] | None = None,
) -> tuple[np.ndarray, StructureReport]:
    mode = (mode or "repair").lower()
    report = check_structure(voxels, thresholds)
    if mode in ("check", "reject"):
        return np.asarray(voxels), report
    fixed, repairs = repair_structure(voxels)
    report2 = check_structure(fixed, thresholds)
    report2.repairs = repairs
    return fixed, report2


def summarize_metrics_list(reports: list[StructureReport]) -> dict[str, Any]:
    if not reports:
        return {"n": 0}
    oks = sum(1 for r in reports if r.ok)
    keys = ["hollow_score", "roof_score", "largest_cc_frac", "non_air", "floor_guess"]
    avg: dict[str, float] = {}
    for k in keys:
        vals = [float(r.metrics.get(k, 0)) for r in reports]
        avg[k] = float(sum(vals) / max(1, len(vals)))
    return {"n": len(reports), "pass_rate": oks / len(reports), "pass": oks, "avg": avg}
