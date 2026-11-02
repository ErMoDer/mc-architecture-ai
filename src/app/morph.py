# -*- coding: utf-8 -*-
"""纯 numpy 形态学工具（无 scipy 依赖）。

项目 venv 未装 scipy，且历史上 scipy 可选导入曾静默降级导致功能失效。
为避免类似问题，所有形态学操作统一用本模块的 numpy 实现。

提供：膨胀 / 腐蚀 / 闭运算 / 二维补洞 / 凸包 / 26 邻域最大连通分量比例。
坐标约定：False = 空气，True = 实体。
"""
from __future__ import annotations

from collections import deque

import numpy as np


def _shift(mask: np.ndarray, axis: int, delta: int) -> np.ndarray:
    """沿 axis 平移 delta 格，越界部分补 False。"""
    out = np.zeros_like(mask, dtype=bool)
    src = [slice(None)] * mask.ndim
    dst = [slice(None)] * mask.ndim
    if delta < 0:
        src[axis] = slice(-delta, None)
        dst[axis] = slice(None, delta)
    else:
        src[axis] = slice(None, -delta)
        dst[axis] = slice(delta, None)
    out[tuple(dst)] = mask[tuple(src)]
    return out


def dilate(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    out = np.asarray(mask, dtype=bool).copy()
    for _ in range(max(0, iterations)):
        cur = out.copy()
        for axis in range(cur.ndim):
            for delta in (-1, 1):
                out |= _shift(cur, axis, delta)
    return out


def dilate_horizontal(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """只在水平面（axis 0/2）膨胀，封门窗但不压低层高。"""
    out = np.asarray(mask, dtype=bool).copy()
    axes = (0, 2) if out.ndim == 3 else tuple(range(out.ndim))
    for _ in range(max(0, iterations)):
        cur = out.copy()
        for axis in axes:
            for delta in (-1, 1):
                out |= _shift(cur, axis, delta)
    return out


def erode(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    out = np.asarray(mask, dtype=bool).copy()
    for _ in range(max(0, iterations)):
        cur = out.copy()
        for axis in range(cur.ndim):
            for delta in (-1, 1):
                out &= _shift(cur, axis, delta)
    return out


def closing(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
    """闭运算：先膨胀后腐蚀，用于桥接窄缝（门洞/窗缝/断开的线稿）。

    结果并回原掩码，保证不会把原本的薄墙/细线腐蚀掉（离散边界效应）。
    """
    base = np.asarray(mask, dtype=bool).copy()
    if iterations <= 0:
        return base
    return erode(dilate(base, iterations), iterations) | base


def fill_holes(mask2d: np.ndarray) -> np.ndarray:
    """二维补洞：从边界做 4 邻域 flood fill，填不连通外部的空白。"""
    solid = np.asarray(mask2d, dtype=bool)
    air = ~solid
    reach = np.zeros_like(solid)
    q: deque[tuple[int, int]] = deque()
    h, w = solid.shape

    def _push(i: int, j: int) -> None:
        if air[i, j] and not reach[i, j]:
            reach[i, j] = True
            q.append((i, j))

    for i in range(h):
        _push(i, 0)
        _push(i, w - 1)
    for j in range(w):
        _push(0, j)
        _push(h - 1, j)
    while q:
        i, j = q.popleft()
        if i > 0:
            _push(i - 1, j)
        if i + 1 < h:
            _push(i + 1, j)
        if j > 0:
            _push(i, j - 1)
        if j + 1 < w:
            _push(i, j + 1)
    return solid | (air & ~reach)


def _convex_points(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Andrew monotone chain 凸包；退化（点数 < 3 或共线）返回空列表。"""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    poly = lower[:-1] + upper[:-1]
    return poly if len(poly) >= 3 else []


def convex_fill(mask2d: np.ndarray) -> np.ndarray | None:
    """用前景点凸包围出的实心区域；退化时返回 None。"""
    solid = np.asarray(mask2d, dtype=bool)
    ys, xs = np.where(solid)
    poly = _convex_points([(float(x), float(y)) for y, x in zip(ys, xs)])
    if not poly:
        return None
    h, w = solid.shape
    xs_grid, ys_grid = np.meshgrid(np.arange(w), np.arange(h))
    inside = np.zeros((h, w), dtype=bool)
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        if y1 == y2:
            continue
        # 射线法：水平射线从左向右数交点
        cond = (y1 > ys_grid) != (y2 > ys_grid)
        with np.errstate(divide="ignore", invalid="ignore"):
            xcut = x1 + (ys_grid - y1) * (x2 - x1) / (y2 - y1)
        inside ^= cond & (xs_grid < xcut)
    return inside


def _neighbor_count6(solid: np.ndarray) -> np.ndarray:
    """每格在 6 邻域内的实体邻居数量（越界的邻居不计）。"""
    nb = np.zeros(solid.shape, dtype=np.int16)
    nb[1:, :, :] += solid[:-1, :, :]
    nb[:-1, :, :] += solid[1:, :, :]
    nb[:, 1:, :] += solid[:, :-1, :]
    nb[:, :-1, :] += solid[:, 1:, :]
    nb[:, :, 1:] += solid[:, :, :-1]
    nb[:, :, :-1] += solid[:, :, 1:]
    return nb


def _largest_component_mask(solid: np.ndarray) -> np.ndarray:
    """26 邻域最大连通分量掩码。"""
    seen = np.zeros_like(solid)
    shape = solid.shape
    best_cells: list[tuple[int, int, int]] = []
    for start in np.argwhere(solid):
        s = (int(start[0]), int(start[1]), int(start[2]))
        if seen[s]:
            continue
        seen[s] = True
        q: deque[tuple[int, int, int]] = deque([s])
        cells: list[tuple[int, int, int]] = []
        while q:
            x, y, z = q.popleft()
            cells.append((x, y, z))
            for dx in (-1, 0, 1):
                nx = x + dx
                if nx < 0 or nx >= shape[0]:
                    continue
                for dy in (-1, 0, 1):
                    ny = y + dy
                    if ny < 0 or ny >= shape[1]:
                        continue
                    for dz in (-1, 0, 1):
                        nz = z + dz
                        if nz < 0 or nz >= shape[2]:
                            continue
                        if solid[nx, ny, nz] and not seen[nx, ny, nz]:
                            seen[nx, ny, nz] = True
                            q.append((nx, ny, nz))
        if len(cells) > len(best_cells):
            best_cells = cells
    out = np.zeros_like(solid)
    for x, y, z in best_cells:
        out[x, y, z] = True
    return out


def prune_strays(
    voxels: np.ndarray,
    *,
    protect_ids: set[int] | None = None,
    spike_max_neighbors: int = 1,
    drop_islands: bool = True,
) -> tuple[np.ndarray, dict[str, int]]:
    """删除视觉上「乱放」的零散方块（纯 numpy，无 scipy）。

    三类判定，任一成立即删：
    1. 完全孤立：6 邻域实体邻居数 == 0。
    2. 悬空钉刺：6 邻域邻居数 <= spike_max_neighbors，且上下都无实体
       （不是竖直构件的端头，如烟囱/旗杆/屋檐悬挑都靠上下延续豁免）。
    3. 孤岛簇：不属于 26 邻域最大连通分量的整块碎片。

    保护材质用于豁免第 2 条：门/玻璃/楼梯/水等本就是稀疏薄片。
    第 1/3 条不豁免——孤零零一格或连不上主体的碎片必然是多余的。

    返回 (净化后的体素, 统计字典)。
    """
    out = np.asarray(voxels, dtype=np.int16).copy()
    solid = out > 0
    stats = {"isolated": 0, "spike": 0, "island": 0, "total": 0}
    if not solid.any():
        return out, stats

    prot = set(int(x) for x in (protect_ids or set()) if int(x) > 0)

    drop = np.zeros_like(solid)

    # 1) 完全孤立：无条件删除，保护材质也不豁免（孤零零一格必然多余）
    nb = _neighbor_count6(solid)
    hit = solid & (nb == 0)
    stats["isolated"] = int(hit.sum())
    drop |= hit

    above = np.zeros_like(solid)
    above[:, :-1, :] = solid[:, 1:, :]
    below = np.zeros_like(solid)
    below[:, 1:, :] = solid[:, :-1, :]
    # y=0 视为落地，避免把整个基座底面误判成悬空
    below[:, 0, :] = True

    # 2) 悬空钉刺：邻居极少且上下都不延续
    hit = solid & ~above & ~below & (nb <= int(spike_max_neighbors))
    if prot:
        for pid in prot:
            hit &= out != int(pid)
    stats["spike"] = int(hit.sum())
    drop |= hit

    # 3) 孤岛簇（26 邻域连不上主体）：无条件删除
    if drop_islands:
        largest = _largest_component_mask(solid)
        hit = solid & ~largest
        stats["island"] = int(hit.sum())
        drop |= hit

    n = int(drop.sum())
    if n:
        out[drop] = 0
    stats["total"] = n
    return out, stats


def regularize_form(
    voxels: np.ndarray,
    *,
    protect_ids: set[int] | None = None,
    envelope_pct: float = 8.0,
) -> tuple[np.ndarray, dict[str, int]]:
    """规整建筑外形（纯 numpy，无 scipy）：墙面压平 + 屋顶坡面吸附。

    墙面：四个立面各自取表面深度图的外包络（浅侧 envelope_pct 分位 /
    深侧 100-envelope_pct 分位），只削包络之外的凸出块；墙体与凹陷
    （窗洞）不动，保护材质豁免。

    屋顶：墙顶取边界柱顶面高度的 30 分位；屋脊沿外接矩形长轴；
    按到屋脊距离分带取柱顶中位数并单调化，得到目标坡面；
    高于目标的削低、低于目标的抬升——只动当前柱顶，绝不碰柱顶以下
    （保住室内空间）。抬升部分用原屋顶众数材质。

    返回 (规整后的体素, 统计字典)。
    """
    out = np.asarray(voxels, dtype=np.int16).copy()
    solid = out > 0
    stats = {"flatten": 0, "roof_removed": 0, "roof_added": 0}
    if not solid.any():
        return out, stats
    prot = set(int(x) for x in (protect_ids or set()) if int(x) > 0)
    X, Y, Z = out.shape

    # --- 墙面压平 ---
    for axis, sign in ((0, -1), (0, +1), (2, -1), (2, +1)):
        u_ax = 2 if axis == 0 else 0
        U = out.shape[u_ax]
        depth = np.full((U, Y), -1, dtype=np.int16)
        for u in range(U):
            for y in range(Y):
                line = solid[:, y, u] if axis == 0 else solid[u, y, :]
                idx = np.flatnonzero(line)
                if idx.size:
                    depth[u, y] = idx.min() if sign < 0 else idx.max()
        vals = depth[depth >= 0]
        if vals.size == 0:
            continue
        env = int(np.percentile(vals, envelope_pct)) if sign < 0 \
            else int(np.percentile(vals, 100.0 - envelope_pct))
        for u in range(U):
            for y in range(Y):
                d = int(depth[u, y])
                if d < 0:
                    continue
                if sign < 0 and d < env:
                    rng = range(d, env)
                elif sign > 0 and d > env:
                    rng = range(env + 1, d + 1)
                else:
                    continue
                for a in rng:
                    if axis == 0:
                        bid = int(out[a, y, u])
                        if bid > 0 and bid not in prot:
                            out[a, y, u] = 0
                            stats["flatten"] += 1
                    else:
                        bid = int(out[u, y, a])
                        if bid > 0 and bid not in prot:
                            out[u, y, a] = 0
                            stats["flatten"] += 1
        solid = out > 0

    # --- 屋顶坡面吸附 ---
    tops = np.full((X, Z), -1, dtype=np.int16)
    for x in range(X):
        for z in range(Z):
            ys = np.flatnonzero(solid[x, :, z])
            if ys.size:
                tops[x, z] = ys.max()
    fp = tops >= 0
    if not fp.any():
        return out, stats
    b = fp
    inner = np.zeros_like(fp)
    inner[1:, :] |= b[:-1, :] & b[1:, :]
    inner[:-1, :] |= b[:-1, :] & b[1:, :]
    inner[:, 1:] |= b[:, :-1] & b[:, 1:]
    inner[:, :-1] |= b[:, :-1] & b[:, 1:]
    edge = fp & ~inner
    if not edge.any():
        edge = fp
    wall_top = int(np.percentile(tops[edge], 30))
    above = np.zeros_like(solid)
    above[:, wall_top + 1:, :] = solid[:, wall_top + 1:, :]
    ids = out[above]
    ids = ids[ids > 0]
    if ids.size == 0:
        return out, stats
    roof_mat = int(np.bincount(ids).argmax())
    xs, zs = np.where(fp)
    x0, x1, z0, z1 = int(xs.min()), int(xs.max()), int(zs.min()), int(zs.max())
    ridge_along_x = (x1 - x0) >= (z1 - z0)
    cx = (x0 + x1) / 2.0
    cz = (z0 + z1) / 2.0
    band_h: dict[int, list[int]] = {}
    for x, z in np.argwhere(fp):
        dcol = abs(x - cx) if ridge_along_x else abs(z - cz)
        t = int(tops[x, z])
        if t > wall_top:
            band_h.setdefault(int(round(dcol)), []).append(t)
    if not band_h:
        return out, stats
    target = {k: int(np.median(v)) for k, v in band_h.items()}
    keys = sorted(target)
    for i in range(1, len(keys)):
        if target[keys[i]] > target[keys[i - 1]]:
            target[keys[i]] = target[keys[i - 1]]
    ridge_h = target[keys[0]]
    for x, z in np.argwhere(fp):
        dcol = abs(x - cx) if ridge_along_x else abs(z - cz)
        kf = min(dcol, float(keys[-1]))
        k0, k1 = int(np.floor(kf)), int(np.ceil(kf))
        h0 = target.get(k0, ridge_h)
        h1 = target.get(k1, h0)
        th = int(round(h0 + (h1 - h0) * (kf - k0)))
        th = max(wall_top, min(th, Y - 1))
        cur = int(tops[x, z])
        if cur > th:
            for y in range(th + 1, cur + 1):
                if out[x, y, z] > 0:
                    out[x, y, z] = 0
                    stats["roof_removed"] += 1
        elif wall_top <= cur < th:
            for y in range(cur + 1, th + 1):
                out[x, y, z] = roof_mat
                stats["roof_added"] += 1
    return out, stats


def largest_component_ratio(mask: np.ndarray) -> float:
    """最大连通分量（26 邻域）占全部实体的比例；空掩码返回 0。"""
    solid = np.asarray(mask, dtype=bool)
    total = int(solid.sum())
    if total == 0:
        return 0.0
    seen = np.zeros_like(solid)
    shape = solid.shape
    best = 0
    for start in np.argwhere(solid):
        x0, y0, z0 = int(start[0]), int(start[1]), int(start[2])
        if seen[x0, y0, z0]:
            continue
        seen[x0, y0, z0] = True
        q: deque[tuple[int, int, int]] = deque([(x0, y0, z0)])
        size = 0
        while q:
            cx, cy, cz = q.popleft()
            size += 1
            for dx in (-1, 0, 1):
                nx = cx + dx
                if nx < 0 or nx >= shape[0]:
                    continue
                for dy in (-1, 0, 1):
                    ny = cy + dy
                    if ny < 0 or ny >= shape[1]:
                        continue
                    for dz in (-1, 0, 1):
                        nz = cz + dz
                        if nz < 0 or nz >= shape[2]:
                            continue
                        if solid[nx, ny, nz] and not seen[nx, ny, nz]:
                            seen[nx, ny, nz] = True
                            q.append((nx, ny, nz))
        best = max(best, size)
    return best / total
