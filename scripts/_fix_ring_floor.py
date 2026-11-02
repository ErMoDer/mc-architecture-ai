# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("src/app/gen_strategy.py")
text = path.read_text(encoding="utf-8")
old = '''def _ring_floor_mask(
    fp: np.ndarray,
    *,
    depth: int = 2,
    keep_cross: bool = True,
) -> np.ndarray:
    """Walkable ring (+ optional cross corridor) leaving a large open room in the middle.

    Full-footprint floor slabs every story made exteriors look like solid crates.
    """
    fp = np.asarray(fp, dtype=bool)
    if not fp.any():
        return fp.copy()
    peri = _perimeter_mask(fp)
    ring = _dilate_mask(peri, max(1, int(depth))) & fp
    # If footprint is too thin, fall back to full slab (still rare for houses).
    if int(ring.sum()) >= max(8, int(0.85 * int(fp.sum()))):
        return fp.copy()
    if keep_cross:
        xs, zs = np.where(fp)
        cx = int(round(float(xs.mean())))
        cz = int(round(float(zs.mean())))
        # 1-cell corridor through centroid so rooms stay reachable
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(x - cx) <= 0 or abs(z - cz) <= 0:
                ring[x, z] = True
        ring &= fp
    # Guarantee at least a usable walk band
    if int(ring.sum()) < max(12, int(0.18 * int(fp.sum()))):
        ring = _dilate_mask(peri, max(2, int(depth) + 1)) & fp
    return ring
'''
new = '''def _ring_floor_mask(
    fp: np.ndarray,
    *,
    depth: int = 2,
    keep_cross: bool = True,
) -> np.ndarray:
    """Walkable ring (+ optional cross corridor) leaving a large open room in the middle.

    Distance-from-perimeter band (not dilate-then-fallback-to-full), so small and
    large footprints both keep an open center instead of solid crates.
    """
    from collections import deque

    fp = np.asarray(fp, dtype=bool)
    if not fp.any():
        return fp.copy()
    h, w = fp.shape
    peri = _perimeter_mask(fp)
    dist = np.full((h, w), -1, dtype=np.int16)
    q: deque[tuple[int, int]] = deque()
    xs_p, zs_p = np.where(peri)
    for x, z in zip(xs_p.tolist(), zs_p.tolist()):
        dist[x, z] = 0
        q.append((x, z))
    while q:
        x, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, zz = x + dx, z + dz
            if 0 <= xx < h and 0 <= zz < w and fp[xx, zz] and dist[xx, zz] < 0:
                dist[xx, zz] = int(dist[x, z]) + 1
                q.append((xx, zz))
    # Cap depth so at least ~25% of footprint stays open when possible
    xs, zs = np.where(fp)
    max_d = int(dist[fp].max()) if fp.any() else 0
    d = max(1, int(depth))
    if max_d >= 2:
        # leave at least the innermost ring open
        d = min(d, max(1, max_d - 1))
    ring = fp & (dist >= 0) & (dist <= d)
    open_n = int((fp & (dist > d)).sum())
    if open_n < max(9, int(0.2 * int(fp.sum()))) and max_d >= 2:
        d = 1
        ring = fp & (dist >= 0) & (dist <= d)
        open_n = int((fp & (dist > d)).sum())
    if keep_cross and open_n >= 4:
        cx = int(round(float(xs.mean())))
        cz = int(round(float(zs.mean())))
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(x - cx) <= 0 or abs(z - cz) <= 0:
                ring[x, z] = True
        ring &= fp
    # Ultra-thin footprints: keep whatever ring we have (may be near-full)
    if int(ring.sum()) < max(8, int(0.12 * int(fp.sum()))):
        ring = _dilate_mask(peri, 1) & fp
    return ring
'''
if old not in text:
    raise SystemExit('old ring fn missing')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('ring fixed')

# quick test
import importlib
import src.app.gen_strategy as g
importlib.reload(g)
import numpy as np
fp = np.zeros((10,10), bool)
fp[2:8,2:8] = True
r = g._ring_floor_mask(fp, depth=2)
print('6x6 ring', int(r.sum()), 'open', int(fp.sum())-int(r.sum()))
fp2 = np.zeros((32,32), bool)
fp2[4:28,4:28] = True
r2 = g._ring_floor_mask(fp2, depth=2)
print('24x24 ring', int(r2.sum()), 'open', int(fp2.sum())-int(r2.sum()))