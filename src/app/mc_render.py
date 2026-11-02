"""MC-style voxel renderer: exposed cube faces, orbit LOD, pick metadata."""
from __future__ import annotations

from typing import Any

import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from src.app.mc_colors import rgba_for_id

_FACE_SPECS: list[tuple[np.ndarray, float, tuple[int, int, int]]] = [
    (np.array([[0, 1, 0], [1, 1, 0], [1, 1, 1], [0, 1, 1]], dtype=np.float32), 1.0, (0, 1, 0)),
    (np.array([[0, 0, 0], [0, 0, 1], [1, 0, 1], [1, 0, 0]], dtype=np.float32), 0.45, (0, -1, 0)),
    (np.array([[1, 0, 0], [1, 0, 1], [1, 1, 1], [1, 1, 0]], dtype=np.float32), 0.72, (1, 0, 0)),
    (np.array([[0, 0, 0], [0, 1, 0], [0, 1, 1], [0, 0, 1]], dtype=np.float32), 0.62, (-1, 0, 0)),
    (np.array([[0, 0, 1], [0, 1, 1], [1, 1, 1], [1, 0, 1]], dtype=np.float32), 0.78, (0, 0, 1)),
    (np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=np.float32), 0.55, (0, 0, -1)),
]


def downsample_voxels(voxels: np.ndarray, factor: int = 2) -> np.ndarray:
    if factor <= 1:
        return voxels
    d, h, w = voxels.shape
    nd, nh, nw = d // factor, h // factor, w // factor
    if nd < 1 or nh < 1 or nw < 1:
        return voxels
    trimmed = voxels[: nd * factor, : nh * factor, : nw * factor]
    reshaped = trimmed.reshape(nd, factor, nh, factor, nw, factor)
    blocks = reshaped.transpose(0, 2, 4, 1, 3, 5).reshape(nd, nh, nw, factor ** 3)
    out = np.zeros((nd, nh, nw), dtype=voxels.dtype)
    for ix in range(nd):
        for iy in range(nh):
            for iz in range(nw):
                block = blocks[ix, iy, iz]
                solid = block[block > 0]
                if solid.size:
                    ids, counts = np.unique(solid, return_counts=True)
                    out[ix, iy, iz] = ids[counts.argmax()]
    return out


def build_exposed_faces(
    voxels: np.ndarray,
    palette: dict[int, str],
    *,
    highlight_id: int | None = None,
    highlight_pos: tuple[int, int, int] | None = None,
    max_faces: int = 120_000,
    collect_meta: bool = False,
) -> tuple[list[np.ndarray], list[tuple[float, float, float, float]], list[dict[str, Any]]]:
    solid = voxels > 0
    if not solid.any():
        return [], [], []

    faces: list[np.ndarray] = []
    colors: list[tuple[float, float, float, float]] = []
    metas: list[dict[str, Any]] = []

    unique_ids = [int(i) for i in np.unique(voxels[solid])]
    base_colors = {bid: rgba_for_id(bid, palette) for bid in unique_ids}
    remapped_local = [v[:, [0, 2, 1]] for v, _, _ in _FACE_SPECS]

    for fi, (_verts_local, shade, normal) in enumerate(_FACE_SPECS):
        dx, dy, dz = normal
        if dx == 1:
            neigh = np.zeros_like(solid)
            neigh[:-1] = solid[1:]
        elif dx == -1:
            neigh = np.zeros_like(solid)
            neigh[1:] = solid[:-1]
        elif dy == 1:
            neigh = np.zeros_like(solid)
            neigh[:, :-1] = solid[:, 1:]
        elif dy == -1:
            neigh = np.zeros_like(solid)
            neigh[:, 1:] = solid[:, :-1]
        elif dz == 1:
            neigh = np.zeros_like(solid)
            neigh[:, :, :-1] = solid[:, :, 1:]
        else:
            neigh = np.zeros_like(solid)
            neigh[:, :, 1:] = solid[:, :, :-1]

        exposed = solid & ~neigh
        xs, ys, zs = np.where(exposed)
        if xs.size == 0:
            continue
        rem = remapped_local[fi]
        for x, y, z in zip(xs.tolist(), ys.tolist(), zs.tolist()):
            bid = int(voxels[x, y, z])
            r, g, b, a = base_colors[bid]
            if highlight_id is not None and bid == highlight_id:
                r = min(r * 1.25 + 0.1, 1)
                g = min(g * 1.25 + 0.1, 1)
                b = min(b * 1.25 + 0.1, 1)
                a = min(a + 0.1, 1.0)
            if highlight_pos is not None and (x, y, z) == highlight_pos:
                # UX P1: stronger selected-block flash (yellow-white lift)
                r = min(r * 0.55 + 0.55, 1)
                g = min(g * 0.45 + 0.65, 1)
                b = min(b * 0.35 + 0.15, 1)
                a = 1.0
            origin = np.array([x, z, y], dtype=np.float32)
            faces.append(origin + rem)
            colors.append((r * shade, g * shade, b * shade, a))
            if collect_meta:
                metas.append({"voxel": (x, y, z), "normal": normal, "bid": bid})
            if len(faces) >= max_faces:
                return faces, colors, metas
    return faces, colors, metas


def apply_mc_scene(
    ax: Any,
    fig: Any,
    size: int,
    *,
    elev: float | None = None,
    azim: float | None = None,
    preserve_view: bool = False,
) -> None:
    sky = "#87CEEB"
    fig.patch.set_facecolor(sky)
    ax.set_facecolor(sky)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor((0.6, 0.7, 0.8, 0.3))
    ax.yaxis.pane.set_edgecolor((0.6, 0.7, 0.8, 0.3))
    ax.zaxis.pane.set_edgecolor((0.6, 0.7, 0.8, 0.3))
    ax.grid(False)
    ax.set_xlim(0, size)
    ax.set_ylim(0, size)
    ax.set_zlim(0, size)
    try:
        ax.set_box_aspect((1, 1, 1))
    except Exception:
        pass
    if not preserve_view:
        ax.view_init(elev=28 if elev is None else elev, azim=-60 if azim is None else azim)
    elif elev is not None and azim is not None:
        ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X")
    ax.set_ylabel("Z")
    ax.set_zlabel("Y")


def render_mc_voxels(
    ax: Any,
    fig: Any,
    voxels: np.ndarray,
    palette: dict[int, str],
    *,
    highlight_id: int | None = None,
    highlight_pos: tuple[int, int, int] | None = None,
    performance: bool = False,
    orbit_lod: bool = False,
    preserve_view: bool = True,
    draw_edges: bool = False,
    collect_meta: bool = False,
) -> dict[str, Any]:
    cur_elev = getattr(ax, "elev", 28)
    cur_azim = getattr(ax, "azim", -60)

    ax.clear()
    non_air = int((voxels > 0).sum())
    work = voxels
    downsampled = False
    factor = 1

    lod = bool(performance or orbit_lod)
    threshold = 1500 if orbit_lod else (2000 if performance else 10000)
    if non_air > threshold or (lod and non_air > 800):
        factor = 2 if non_air < 25000 else 3
        if orbit_lod and non_air > 4000:
            factor = max(factor, 3)
        work = downsample_voxels(voxels, factor)
        downsampled = True
        non_air_ds = int((work > 0).sum())
    else:
        non_air_ds = non_air

    max_faces = 20_000 if orbit_lod else (40_000 if performance else 120_000)
    hp = None if downsampled else highlight_pos
    need_meta = collect_meta and not downsampled
    faces, colors, metas = build_exposed_faces(
        work,
        palette,
        highlight_id=highlight_id,
        highlight_pos=hp,
        max_faces=max_faces,
        collect_meta=need_meta,
    )

    size = work.shape[0]
    apply_mc_scene(
        ax,
        fig,
        size,
        elev=cur_elev,
        azim=cur_azim,
        preserve_view=preserve_view,
    )

    edge = (0.12, 0.12, 0.12, 0.2) if (draw_edges and not lod) else "none"
    lw = 0.12 if (draw_edges and not lod) else 0.0
    if faces:
        coll = Poly3DCollection(
            faces,
            facecolors=colors,
            edgecolors=edge,
            linewidths=lw,
        )
        ax.add_collection3d(coll)

    mode = "OrbitLOD" if orbit_lod else ("Perf" if performance else "MC")
    extra = f" downsample {factor}x" if downsampled else ""
    title = f"{mode} cubes | blocks={non_air} faces={len(faces)}{extra}"
    if highlight_id is not None:
        title += f" | hi={highlight_id}"
    if highlight_pos is not None:
        title += f" | sel={highlight_pos}"
    ax.set_title(title)

    return {
        "non_air": non_air,
        "faces": len(faces),
        "downsampled": downsampled,
        "factor": factor,
        "display_non_air": non_air_ds,
        "face_meta": metas,
        "display_shape": work.shape,
    }
