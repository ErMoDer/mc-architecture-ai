# -*- coding: utf-8 -*-
"""室内识别：给定体素建筑，找出哪些空气格子是被外墙包住的「室内」。

统一模块，装修、楼层规划、结构分析都依赖这里。
纯 numpy + 本项目 morph.py，不依赖 scipy。

算法概要：
1. 先在水平向膨胀「封住」门洞/窗缝（只膨胀 x/z，不碰 y，避免压低层高）。
2. 从体素边界做 6 邻域 flood fill 标出「与外界连通的空气」。
3. 未被标记的空气即封闭室内。
4. 对不同封口力度（1/2/3 次水平膨胀）分别跑一遍，取室内最多的那次。
5. 最后沿水平向补膨胀 1 格再与原 solid 取差，把封口吃掉的一圈空气格子还原回来。
"""
from __future__ import annotations

from collections import deque

import numpy as np

from src.app.morph import dilate, dilate_horizontal


def seal_openings(solid: np.ndarray, iterations: int = 1) -> np.ndarray:
    """临时封住门洞/窗缝，只用于识别，不改动真实体素。

    只用「水平向膨胀」且不腐蚀：
    - 闭运算会把 1 格薄墙的门洞重新打开；
    - 全向膨胀会压低层高，把薄房间整层吃掉。
    """
    if iterations <= 0:
        return solid
    return dilate_horizontal(solid, iterations)


def outside_air(solid: np.ndarray, iterations: int = 1) -> np.ndarray:
    """从体素边界 6 邻域 flood fill，返回与室外连通的空气掩码。"""
    air = ~seal_openings(solid, iterations)
    outside = np.zeros_like(solid)
    q: deque[tuple[int, int, int]] = deque()

    def _push(x: int, y: int, z: int) -> None:
        if air[x, y, z] and not outside[x, y, z]:
            outside[x, y, z] = True
            q.append((x, y, z))

    sx, sy, sz = solid.shape
    for x in range(sx):
        for y in range(sy):
            _push(x, y, 0)
            _push(x, y, sz - 1)
    for x in range(sx):
        for z in range(sz):
            _push(x, 0, z)
            _push(x, sy - 1, z)
    for y in range(sy):
        for z in range(sz):
            _push(0, y, z)
            _push(sx - 1, y, z)

    while q:
        x, y, z = q.popleft()
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz:
                _push(nx, ny, nz)
    return outside


def interior_air(voxels: np.ndarray) -> np.ndarray:
    """找出真正的室内空气格子。

    对封口力度 1/2/3 分别跑一遍，取围出室内最多的那次，
    再补回被封口吃掉的一圈空气格。
    """
    solid = voxels > 0
    best = np.zeros_like(solid)
    for it in (1, 2, 3):
        inside = (~seal_openings(solid, it)) & ~outside_air(solid, it)
        if int(inside.sum()) > int(best.sum()):
            best = inside
    if not best.any():
        return best
    return dilate(best, 1) & ~solid
