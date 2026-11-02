"""Voxel pick + edit helpers for the matplotlib viewer (MCBlock-like mini tools).

Phase A additions: undo/redo stack, brush/box fill, copy/cut/paste clipboard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from mpl_toolkits.mplot3d import proj3d


TOOL_SELECT = "select"
TOOL_BREAK = "break"
TOOL_PLACE = "place"
TOOL_PAINT = "paint"
TOOL_MOVE = "move"
TOOL_COPY = "copy"
TOOL_CUT = "cut"
TOOL_PASTE = "paste"

TOOL_LABELS = {
    TOOL_SELECT: "Select",
    TOOL_BREAK: "Break",
    TOOL_PLACE: "Place",
    TOOL_PAINT: "Paint",
    TOOL_MOVE: "Move",
    TOOL_COPY: "Copy",
    TOOL_CUT: "Cut",
    TOOL_PASTE: "Paste",
}

BrushShape = Literal["cube", "sphere"]


# ---------------------------------------------------------------------------
# Undo / redo
# ---------------------------------------------------------------------------

class UndoStack:
    """Snapshot stack for voxel grids. Depth defaults to 32 (>=20)."""

    def __init__(self, max_depth: int = 32) -> None:
        self.max_depth = max(1, int(max_depth))
        self._undo: list[np.ndarray] = []
        self._redo: list[np.ndarray] = []

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def push(self, voxels: np.ndarray) -> None:
        """Push a *pre-edit* snapshot. Clears redo."""
        self._undo.append(np.array(voxels, copy=True))
        if len(self._undo) > self.max_depth:
            overflow = len(self._undo) - self.max_depth
            del self._undo[:overflow]
        self._redo.clear()

    def undo(self, current: np.ndarray) -> np.ndarray | None:
        if not self._undo:
            return None
        self._redo.append(np.array(current, copy=True))
        return self._undo.pop()

    def redo(self, current: np.ndarray) -> np.ndarray | None:
        if not self._redo:
            return None
        self._undo.append(np.array(current, copy=True))
        return self._redo.pop()

    @property
    def undo_len(self) -> int:
        return len(self._undo)

    @property
    def redo_len(self) -> int:
        return len(self._redo)


# ---------------------------------------------------------------------------
# Pick / bounds
# ---------------------------------------------------------------------------

def pick_nearest_face(
    ax: Any,
    display_xy: tuple[float, float],
    face_meta: list[dict[str, Any]],
    *,
    max_px: float = 28.0,
) -> dict[str, Any] | None:
    """Pick exposed face whose projected center is nearest to display_xy (pixels)."""
    if not face_meta:
        return None
    mx, my = display_xy
    best = None
    best_d2 = max_px * max_px
    try:
        transf = ax.get_proj()
    except Exception:
        return None
    for meta in face_meta:
        x, y, z = meta["voxel"]
        dx, dy, dz = meta["normal"]
        # face center in plot coords (X=x, Y=z, Z=y)
        cx = x + 0.5 + 0.5 * dx
        cy = z + 0.5 + 0.5 * dz
        cz = y + 0.5 + 0.5 * dy
        try:
            px, py, _ = proj3d.proj_transform(cx, cy, cz, transf)
            disp = ax.transData.transform((px, py))
            d2 = (disp[0] - mx) ** 2 + (disp[1] - my) ** 2
        except Exception:
            continue
        if d2 < best_d2:
            best_d2 = d2
            best = meta
    return best


def in_bounds(voxels: np.ndarray, pos: tuple[int, int, int]) -> bool:
    x, y, z = pos
    sx, sy, sz = voxels.shape
    return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz


def place_pos_from_face(meta: dict[str, Any]) -> tuple[int, int, int]:
    x, y, z = meta["voxel"]
    dx, dy, dz = meta["normal"]
    return (x + dx, y + dy, z + dz)


# ---------------------------------------------------------------------------
# Single-cell ops
# ---------------------------------------------------------------------------

def apply_break(voxels: np.ndarray, pos: tuple[int, int, int]) -> bool:
    if not in_bounds(voxels, pos):
        return False
    x, y, z = pos
    if voxels[x, y, z] == 0:
        return False
    voxels[x, y, z] = 0
    return True


def apply_place(voxels: np.ndarray, pos: tuple[int, int, int], block_id: int) -> bool:
    if block_id <= 0 or not in_bounds(voxels, pos):
        return False
    x, y, z = pos
    if voxels[x, y, z] != 0:
        return False
    voxels[x, y, z] = int(block_id)
    return True


def apply_paint(voxels: np.ndarray, pos: tuple[int, int, int], block_id: int) -> bool:
    if block_id <= 0 or not in_bounds(voxels, pos):
        return False
    x, y, z = pos
    if voxels[x, y, z] == 0:
        return False
    if int(voxels[x, y, z]) == int(block_id):
        return False
    voxels[x, y, z] = int(block_id)
    return True


def apply_move(
    voxels: np.ndarray,
    src: tuple[int, int, int],
    dst: tuple[int, int, int],
) -> bool:
    if not in_bounds(voxels, src) or not in_bounds(voxels, dst):
        return False
    sx, sy, sz = src
    dx, dy, dz = dst
    bid = int(voxels[sx, sy, sz])
    if bid <= 0:
        return False
    if voxels[dx, dy, dz] != 0 and (dx, dy, dz) != (sx, sy, sz):
        return False
    voxels[sx, sy, sz] = 0
    voxels[dx, dy, dz] = bid
    return True


def nudge(
    voxels: np.ndarray,
    pos: tuple[int, int, int],
    delta: tuple[int, int, int],
) -> tuple[int, int, int] | None:
    nx = pos[0] + delta[0]
    ny = pos[1] + delta[1]
    nz = pos[2] + delta[2]
    if apply_move(voxels, pos, (nx, ny, nz)):
        return (nx, ny, nz)
    return None


# ---------------------------------------------------------------------------
# Brush / box fill
# ---------------------------------------------------------------------------

def brush_offsets(
    radius: int,
    *,
    shape: BrushShape = "cube",
) -> list[tuple[int, int, int]]:
    """Offsets around center for a brush. radius 0 => single cell; 1 => 3x3x3 cube."""
    r = max(0, int(radius))
    out: list[tuple[int, int, int]] = []
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if shape == "sphere":
                    if dx * dx + dy * dy + dz * dz > r * r + 1e-9:
                        continue
                out.append((dx, dy, dz))
    return out


def iter_box(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
) -> list[tuple[int, int, int]]:
    x0, x1 = sorted((int(a[0]), int(b[0])))
    y0, y1 = sorted((int(a[1]), int(b[1])))
    z0, z1 = sorted((int(a[2]), int(b[2])))
    cells: list[tuple[int, int, int]] = []
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            for z in range(z0, z1 + 1):
                cells.append((x, y, z))
    return cells


def apply_break_brush(
    voxels: np.ndarray,
    center: tuple[int, int, int],
    radius: int = 0,
    *,
    shape: BrushShape = "cube",
) -> int:
    n = 0
    for dx, dy, dz in brush_offsets(radius, shape=shape):
        pos = (center[0] + dx, center[1] + dy, center[2] + dz)
        if apply_break(voxels, pos):
            n += 1
    return n


def apply_place_brush(
    voxels: np.ndarray,
    center: tuple[int, int, int],
    block_id: int,
    radius: int = 0,
    *,
    shape: BrushShape = "cube",
) -> int:
    n = 0
    for dx, dy, dz in brush_offsets(radius, shape=shape):
        pos = (center[0] + dx, center[1] + dy, center[2] + dz)
        if apply_place(voxels, pos, block_id):
            n += 1
    return n


def apply_paint_brush(
    voxels: np.ndarray,
    center: tuple[int, int, int],
    block_id: int,
    radius: int = 0,
    *,
    shape: BrushShape = "cube",
) -> int:
    n = 0
    for dx, dy, dz in brush_offsets(radius, shape=shape):
        pos = (center[0] + dx, center[1] + dy, center[2] + dz)
        if apply_paint(voxels, pos, block_id):
            n += 1
    return n


def apply_box_fill(
    voxels: np.ndarray,
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    block_id: int,
    *,
    mode: Literal["place", "paint", "break"] = "place",
) -> int:
    """Fill axis-aligned box from corner a to b inclusive."""
    n = 0
    for pos in iter_box(a, b):
        if mode == "break":
            if apply_break(voxels, pos):
                n += 1
        elif mode == "paint":
            if apply_paint(voxels, pos, block_id):
                n += 1
        else:
            if apply_place(voxels, pos, block_id):
                n += 1
    return n


# ---------------------------------------------------------------------------
# Clipboard (copy / cut / paste region)
# ---------------------------------------------------------------------------

@dataclass
class VoxelClipboard:
    """Dense sub-volume clipboard. origin is inclusive min corner when copied."""

    data: np.ndarray | None = None  # (sx, sy, sz) int ids; 0 = empty in paste overlay
    size: tuple[int, int, int] | None = None
    anchor: tuple[int, int, int] | None = None  # min corner in source when copied
    non_air: int = 0

    def clear(self) -> None:
        self.data = None
        self.size = None
        self.anchor = None
        self.non_air = 0

    def empty(self) -> bool:
        return self.data is None or self.size is None


def _bbox_from_selection(
    a: tuple[int, int, int],
    b: tuple[int, int, int] | None = None,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if b is None:
        return a, a
    x0, x1 = sorted((int(a[0]), int(b[0])))
    y0, y1 = sorted((int(a[1]), int(b[1])))
    z0, z1 = sorted((int(a[2]), int(b[2])))
    return (x0, y0, z0), (x1, y1, z1)


def copy_region(
    voxels: np.ndarray,
    a: tuple[int, int, int],
    b: tuple[int, int, int] | None = None,
) -> VoxelClipboard:
    """Copy inclusive AABB (or single cell) into a clipboard buffer."""
    (x0, y0, z0), (x1, y1, z1) = _bbox_from_selection(a, b)
    sx, sy, sz = voxels.shape
    x0c, x1c = max(0, x0), min(sx - 1, x1)
    y0c, y1c = max(0, y0), min(sy - 1, y1)
    z0c, z1c = max(0, z0), min(sz - 1, z1)
    if x0c > x1c or y0c > y1c or z0c > z1c:
        return VoxelClipboard()
    chunk = np.array(voxels[x0c : x1c + 1, y0c : y1c + 1, z0c : z1c + 1], copy=True)
    return VoxelClipboard(
        data=chunk,
        size=tuple(int(v) for v in chunk.shape),  # type: ignore[arg-type]
        anchor=(x0c, y0c, z0c),
        non_air=int((chunk > 0).sum()),
    )


def cut_region(
    voxels: np.ndarray,
    a: tuple[int, int, int],
    b: tuple[int, int, int] | None = None,
) -> VoxelClipboard:
    """Copy then clear the source region (air = 0)."""
    clip = copy_region(voxels, a, b)
    if clip.empty() or clip.data is None or clip.anchor is None or clip.size is None:
        return clip
    ax, ay, az = clip.anchor
    sx, sy, sz = clip.size
    voxels[ax : ax + sx, ay : ay + sy, az : az + sz] = 0
    return clip


def paste_region(
    voxels: np.ndarray,
    clipboard: VoxelClipboard,
    dest: tuple[int, int, int],
    *,
    mode: Literal["overlay", "replace"] = "overlay",
) -> int:
    """Paste clipboard with dest as the min-corner of the paste.

    overlay: only write non-air from clipboard (skip zeros).
    replace: write entire chunk including air (clears dest volume).
    Returns number of cells written (changed or forced).
    """
    if clipboard.empty() or clipboard.data is None or clipboard.size is None:
        return 0
    sx, sy, sz = clipboard.size
    dx, dy, dz = int(dest[0]), int(dest[1]), int(dest[2])
    vx, vy, vz = voxels.shape
    n = 0
    for i in range(sx):
        for j in range(sy):
            for k in range(sz):
                x, y, z = dx + i, dy + j, dz + k
                if not (0 <= x < vx and 0 <= y < vy and 0 <= z < vz):
                    continue
                bid = int(clipboard.data[i, j, k])
                if mode == "overlay" and bid <= 0:
                    continue
                if int(voxels[x, y, z]) != bid:
                    voxels[x, y, z] = bid
                    n += 1
                elif mode == "replace":
                    n += 1
    return n


# Radius presets used by UI (label -> radius)
BRUSH_PRESETS = {
    "1": 0,
    "小": 0,
    "中": 1,
    "大": 2,
}
