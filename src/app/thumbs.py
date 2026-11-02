# -*- coding: utf-8 -*-
"""建筑样本缩略图：离屏渲染 + 磁盘缓存。

左侧「建筑库」卡片用。matplotlib Agg 渲染 3D 体素，PNG 缓存到
``outputs/cache/thumbs/``，键 = 文件路径 + mtime + 大小 + 尺寸。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = _PROJECT_ROOT / "outputs" / "cache" / "thumbs"


def _cache_key(npz_path: Path, size: tuple[int, int]) -> str:
    st = npz_path.stat()
    raw = f"{npz_path.resolve()}|{st.st_mtime_ns}|{st.st_size}|{size[0]}x{size[1]}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:20]


def thumb_path(npz_path: Path, size: tuple[int, int] = (240, 168)) -> Path:
    return CACHE_DIR / f"{_cache_key(Path(npz_path), size)}_{size[0]}x{size[1]}.png"


def _load_npz(path: Path) -> np.ndarray:
    with np.load(path) as z:
        for key in ("voxels", "arr_0", "data"):
            if key in z.files:
                return np.asarray(z[key])
        return np.asarray(z[z.files[0]])


def sample_stats(npz_path: Path) -> tuple[int, int]:
    """(非空气方块数, 文件字节数)；读取失败时方块数为 -1。"""
    npz_path = Path(npz_path)
    try:
        vox = _load_npz(npz_path)
        n = int((vox > 0).sum())
    except Exception:
        n = -1
    try:
        size = int(npz_path.stat().st_size)
    except OSError:
        size = 0
    return n, size


def render_thumb(
    npz_path: Path,
    palette: dict[int, str],
    *,
    size: tuple[int, int] = (240, 168),
    force: bool = False,
) -> Path | None:
    """渲染并返回缩略图路径；失败返回 None（界面回退到色块）。"""
    npz_path = Path(npz_path)
    out = thumb_path(npz_path, size)
    if out.exists() and out.stat().st_size > 0 and not force:
        return out

    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    from src.app.mc_render import downsample_voxels, render_mc_voxels

    try:
        vox = _load_npz(npz_path)
    except Exception:
        return None

    # 缩略图不需要全细节：先降采样，卡片刷新快很多
    non_air = int((vox > 0).sum())
    if non_air > 12000:
        vox = downsample_voxels(vox, 3)
    elif non_air > 3500:
        vox = downsample_voxels(vox, 2)

    try:
        fig = Figure(figsize=(size[0] / 100.0, size[1] / 100.0), dpi=100)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111, projection="3d")
        render_mc_voxels(
            ax,
            fig,
            vox,
            palette,
            performance=True,
            preserve_view=False,
        )
        ax.set_title("")
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_zlabel("")
        ax.set_axis_off()
        ax.set_position([0.02, 0.02, 0.96, 0.96])
        fig.patch.set_facecolor("#7fb2d9")
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=100, facecolor="#7fb2d9", edgecolor="none")
        fig.clear()
        return out if out.exists() else None
    except Exception:
        return None
