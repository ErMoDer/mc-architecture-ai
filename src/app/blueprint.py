# -*- coding: utf-8 -*-
"""图纸/草图识别：平面图（线稿或剪影）→ 体素建筑壳。

流程：读图 → 灰度 → Otsu 二值化 → 裁内容 → 缩放到 32×32 占地 →
线稿先尝试自动闭合（闭运算桥接缺口 + 凸包兜底），闭合失败则直接当墙线；
剪影取外轮廓当墙、内部当室内 → 拉高成墙 + 底板 + 檐口。

形态学操作全部来自 src.app.morph（纯 numpy，无 scipy 依赖）。

    python -m src.app.blueprint <平面图.png> [--height 10] [--style medieval]
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np

from src.app.morph import closing, convex_fill, dilate, fill_holes

GRID = 32

# 各风格壳材质（墙/地板/檐口/屋顶板）
SHELL_MATS = {
    "medieval": ("minecraft:stone_bricks", "minecraft:oak_planks", "minecraft:oak_stairs", "minecraft:spruce_stairs"),
    "modern": ("minecraft:white_concrete", "minecraft:smooth_stone_slab", "minecraft:quartz_stairs", "minecraft:light_gray_concrete"),
    "chinese": ("minecraft:bricks", "minecraft:dark_oak_planks", "minecraft:dark_oak_stairs", "minecraft:dark_oak_stairs"),
    "desert": ("minecraft:sandstone", "minecraft:cut_sandstone", "minecraft:sandstone_stairs", "minecraft:smooth_sandstone"),
    "rustic": ("minecraft:mossy_cobblestone", "minecraft:spruce_planks", "minecraft:spruce_stairs", "minecraft:spruce_stairs"),
}


def _otsu(gray: np.ndarray) -> int:
    hist = np.bincount(gray.ravel().astype(np.int32), minlength=256).astype(np.float64)
    total = gray.size
    sum_all = float((hist * np.arange(256)).sum())
    sum_b = 0.0
    w_b = 0.0
    best_t, best_var = 0, -1.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0 or w_b == total:
            continue
        sum_b += hist[t] * t
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / (total - w_b)
        var = w_b * (total - w_b) * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return best_t


def read_footprint(image_path: str | Path) -> tuple[np.ndarray, str]:
    """读图返回 (32×32 bool 前景掩码, 模式 'line'|'solid')。"""
    from PIL import Image

    im = Image.open(image_path).convert("L")
    im = im.resize((64, 64))
    gray = np.asarray(im, dtype=np.uint8)
    t = _otsu(gray)
    dark = gray <= t
    if dark.mean() > 0.5:
        dark = ~dark

    ys, xs = np.where(dark)
    if len(xs) == 0:
        raise ValueError("图片里没有识别出深色内容")
    dark = dark[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]

    h, w = dark.shape
    scale = 28.0 / max(h, w)
    nh, nw = max(2, int(round(h * scale))), max(2, int(round(w * scale)))
    sim = Image.fromarray((dark * 255).astype(np.uint8)).resize((nw, nh), Image.NEAREST)
    small = np.asarray(sim) > 127
    foot = np.zeros((GRID, GRID), dtype=bool)
    oy, ox = (GRID - nh) // 2, (GRID - nw) // 2
    foot[oy: oy + nh, ox: ox + nw] = small

    mode = "line" if foot.mean() < 0.30 else "solid"
    return foot, mode


def _outline(solid2d: np.ndarray) -> np.ndarray:
    """二维外轮廓：与空气相邻的前景点（直接在 0/1 两轴上做 1 次腐蚀后取差）。"""
    out = np.zeros_like(solid2d)
    for axis in (0, 1):
        for shift in (-1, 1):
            moved = np.zeros_like(solid2d)
            src = [slice(None)] * 2
            dst = [slice(None)] * 2
            if shift < 0:
                src[axis] = slice(1, None)
                dst[axis] = slice(0, -1)
            else:
                src[axis] = slice(0, -1)
                dst[axis] = slice(1, None)
            moved[tuple(dst)] = solid2d[tuple(src)]
            out |= solid2d & ~moved
    return out


def _line_shell(foot: np.ndarray) -> tuple[np.ndarray | None, str]:
    """线稿 → (围出的实心区域, 闭合方式)；open 表示闭合失败。

    三级策略：
    1) 原图补洞即形成闭环（_fill_holes 能把线稿内部空白补齐）
    2) 逐步闭运算桥接 2~8 格缺口（closing 1~4 次 + 补洞）
    3) 兜底：前景点凸包（即使缺口再大也能围出壳）
    """
    hull = fill_holes(foot)
    if hull.sum() >= 24 and hull.sum() > foot.sum() * 1.6:
        return hull, "closed"
    for k in range(1, 5):
        hull = fill_holes(closing(foot, k))
        if hull.sum() >= 24 and hull.sum() > foot.sum() * 1.6:
            return hull, "bridged"
    hull = convex_fill(foot)
    if hull is not None and hull.sum() >= 24:
        return hull, "hull"
    return None, "open"


def build_from_footprint(
    foot: np.ndarray,
    mode: str,
    palette: dict[int, str],
    *,
    height: int = 10,
    style: str = "medieval",
    info: dict | None = None,
) -> np.ndarray:
    """把 32×32 占地掩码拉成体素建筑壳（含底板、墙、檐口、平屋顶）。"""
    name_to_id = {v: k for k, v in palette.items()}
    wall_name, floor_name, eave_name, roof_name = SHELL_MATS.get(style, SHELL_MATS["medieval"])

    close_mode = ""
    if mode == "line":
        shell, close_mode = _line_shell(foot)
        if shell is not None:
            wall2d = _outline(shell)
            inner2d = shell & ~wall2d
            filled = shell
        else:
            wall2d = dilate(foot, 1)
            inner2d = np.zeros_like(foot)
            filled = dilate(wall2d, 1)
    else:
        wall2d = _outline(foot)
        inner2d = foot & ~wall2d
        filled = foot
    if info is not None:
        info["close"] = close_mode
        info["interior"] = int(inner2d.sum())

    vox = np.zeros((GRID, GRID, GRID), dtype=np.int16)
    wall_id = name_to_id.get(wall_name, 1)
    floor_id = name_to_id.get(floor_name, 1)
    eave_id = name_to_id.get(eave_name, 1)
    roof_id = name_to_id.get(roof_name, 1)

    height = int(max(4, min(height, GRID - 4)))
    eave = dilate(wall2d, 1)

    vox[np.index_exp[:, 0, :]] = np.where(filled, floor_id, vox[np.index_exp[:, 0, :]])
    vox[np.index_exp[:, 1:height, :]] = np.where(wall2d[:, None, :], wall_id, vox[np.index_exp[:, 1:height, :]])
    vox[np.index_exp[:, height, :]] = np.where(eave, eave_id, vox[np.index_exp[:, height, :]])
    vox[np.index_exp[:, height + 1, :]] = np.where(filled, roof_id, vox[np.index_exp[:, height + 1, :]])

    # 门：南侧墙中点开 2 高洞口
    xs = np.where(wall2d.any(axis=1))[0]
    zs = np.where(wall2d.any(axis=0))[0]
    if len(xs) and len(zs):
        cx = (xs.min() + xs.max()) // 2
        vox[cx, 1:3, zs.max()] = 0
    return vox


def build_from_image(
    image_path: str | Path,
    palette: dict[int, str],
    *,
    height: int = 10,
    style: str = "medieval",
) -> tuple[np.ndarray, dict]:
    foot, mode = read_footprint(image_path)
    info = {"mode": mode, "fill": float(foot.mean()), "height": height, "style": style}
    vox = build_from_footprint(foot, mode, palette, height=height, style=style, info=info)
    info["non_air"] = int((vox > 0).sum())
    return vox, info


def _main(argv: Iterable[str] | None = None) -> int:
    import json
    import sys

    root = Path(__file__).resolve().parents[2]
    palette = {int(k): v for k, v in json.loads((root / "data/palette.json").read_text(encoding="utf-8")).items()}

    args = list(sys.argv[1:] if argv is None else argv)
    height, style = 10, "medieval"
    for flag, attr in (("--height", "height"), ("--style", "style")):
        if flag in args:
            i = args.index(flag)
            if attr == "height":
                height = int(args[i + 1])
            else:
                style = args[i + 1]
            del args[i: i + 2]
    if not args:
        print("用法: python -m src.app.blueprint <平面图.png> [--height 10] [--style medieval]")
        return 2
    for raw in args:
        vox, info = build_from_image(raw, palette, height=height, style=style)
        extra = f" 闭合={info['close']} 室内={info['interior']}" if info["mode"] == "line" else ""
        print(f"{Path(raw).name}: mode={info['mode']} 占地={info['fill']:.0%} "
              f"height={info['height']} non_air={info['non_air']}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
