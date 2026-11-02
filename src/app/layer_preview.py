# -*- coding: utf-8 -*-
"""Y-layer construction previews for voxel samples (Nova-inspired 2D slices).

Writes one top-down PNG per Y and an optional HTML grid. Uses project mc_colors;
does not copy Litematica-Nova UI/code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from src.app.mc_colors import rgba_for_id
from src.app.sample_runner import load_voxel_npz


def _rgba_u8(block_id: int, palette: dict[int, str]) -> tuple[int, int, int, int]:
    if int(block_id) <= 0:
        return (0, 0, 0, 0)
    r, g, b, a = rgba_for_id(int(block_id), palette)
    return (
        int(max(0, min(255, round(r * 255)))),
        int(max(0, min(255, round(g * 255)))),
        int(max(0, min(255, round(b * 255)))),
        int(max(0, min(255, round(a * 255)))),
    )


def slice_y_to_rgba(
    voxels: np.ndarray,
    y: int,
    palette: dict[int, str],
    *,
    bg: tuple[int, int, int, int] = (30, 34, 40, 255),
) -> np.ndarray:
    """Return HxW RGBA uint8 for a single Y slice (top-down, x right, z down)."""
    # voxels shaped (X, Y, Z)
    plane = voxels[:, int(y), :]  # (X, Z)
    x_size, z_size = plane.shape
    out = np.zeros((z_size, x_size, 4), dtype=np.uint8)
    out[:, :] = bg
    for x in range(x_size):
        for z in range(z_size):
            bid = int(plane[x, z])
            if bid <= 0:
                continue
            out[z, x] = _rgba_u8(bid, palette)
    return out


def render_layer_png(
    voxels: np.ndarray,
    y: int,
    palette: dict[int, str],
    path: Path,
    *,
    scale: int = 12,
    label: bool = True,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba = slice_y_to_rgba(voxels, y, palette)
    h, w, _ = rgba.shape
    img = Image.fromarray(rgba, mode="RGBA")
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.NEAREST)
    if label:
        draw = ImageDraw.Draw(img)
        text = f"Y={y}"
        # shadow + text
        draw.text((4, 4), text, fill=(0, 0, 0, 200))
        draw.text((3, 3), text, fill=(255, 255, 255, 230))
        non_air = int((voxels[:, y, :] > 0).sum())
        draw.text((4, 18), f"blocks={non_air}", fill=(0, 0, 0, 200))
        draw.text((3, 17), f"blocks={non_air}", fill=(200, 220, 255, 230))
    img.save(path)
    return path


def occupied_y_range(voxels: np.ndarray) -> tuple[int, int] | None:
    """Inclusive (ymin, ymax) that contain any non-air, or None if empty."""
    mask = voxels > 0
    if not mask.any():
        return None
    ys = np.where(mask.any(axis=(0, 2)))[0]
    return int(ys.min()), int(ys.max())


def write_layer_previews(
    voxels: np.ndarray,
    palette: dict[int, str],
    out_dir: Path,
    *,
    stem: str = "layer",
    scale: int = 12,
    only_occupied: bool = True,
    write_html: bool = True,
    max_layers: int = 64,
) -> dict[str, Any]:
    """Write PNG per Y (+ optional HTML index). Returns manifest dict."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    size_y = int(voxels.shape[1])
    if only_occupied:
        yr = occupied_y_range(voxels)
        if yr is None:
            return {"layers": [], "html": None, "out_dir": str(out_dir)}
        y0, y1 = yr
    else:
        y0, y1 = 0, size_y - 1

    ys = list(range(y0, y1 + 1))
    if len(ys) > max_layers:
        # keep evenly spaced including ends
        idx = np.linspace(0, len(ys) - 1, max_layers, dtype=int)
        ys = [ys[i] for i in sorted(set(idx.tolist()))]

    layers: list[dict[str, Any]] = []
    for y in ys:
        fname = f"{stem}_y{y:02d}.png"
        p = render_layer_png(voxels, y, palette, out_dir / fname, scale=scale)
        non_air = int((voxels[:, y, :] > 0).sum())
        layers.append({"y": y, "path": str(p), "file": fname, "non_air": non_air})

    html_path = None
    if write_html and layers:
        html_path = out_dir / f"{stem}_layers.html"
        cards = []
        for L in layers:
            cards.append(
                f'<figure><img src="{L["file"]}" alt="Y={L["y"]}"/>'
                f"<figcaption>Y={L['y']} · {L['non_air']} blocks</figcaption></figure>"
            )
        html = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
            f"<title>{stem} layers</title>"
            "<style>body{font-family:sans-serif;background:#1e2228;color:#eee}"
            "main{display:flex;flex-wrap:wrap;gap:12px;padding:12px}"
            "figure{margin:0;background:#2a3038;padding:8px;border-radius:8px}"
            "img{image-rendering:pixelated;max-width:320px}"
            "figcaption{text-align:center;margin-top:6px;font-size:13px}</style>"
            f"</head><body><h1>{stem} — Y layers</h1><main>"
            + "\n".join(cards)
            + "</main><p style='padding:12px;opacity:.7'>Nova-inspired layer view · open .litematic in Litematica-Nova for interactive slices.</p></body></html>"
        )
        html_path.write_text(html, encoding="utf-8")

    return {
        "layers": layers,
        "html": str(html_path) if html_path else None,
        "out_dir": str(out_dir),
        "y_range": [y0, y1],
        "count": len(layers),
    }


def layers_from_path(
    path: Path,
    palette: dict[int, str],
    out_dir: Path,
    **kwargs: Any,
) -> dict[str, Any]:
    from src.app.materials_bom import load_voxels_any

    voxels, meta = load_voxels_any(path)
    # If litematic, rebuild palette from file names
    if meta and "litematic_names" in meta:
        names = list(meta["litematic_names"])
        palette = {i: n for i, n in enumerate(names)}
    stem = Path(path).stem
    if stem.endswith(".npz"):
        stem = Path(stem).stem
    info = write_layer_previews(voxels, palette, out_dir, stem=stem, **kwargs)
    info["source"] = str(path)
    return info