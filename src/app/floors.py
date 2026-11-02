"""多楼层与房间规划：自动识别楼板，插入隔墙、门洞与楼梯。

    python -m src.app.floors <sample.npz>
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def _interior_air(solid: np.ndarray) -> np.ndarray:
    """统一入口：装修 / 楼层规划 / 蓝图共用 src.app.interior 的实现。"""
    from src.app.interior import interior_air

    return interior_air(solid)


def detect_floors(solid: np.ndarray, interior: np.ndarray) -> list[int]:
    """楼板层：水平板（上下都是空气）且上方确实有室内空间。"""
    h = solid.shape[1]
    up = np.zeros_like(solid)
    down = np.zeros_like(solid)
    up[:, :-1, :] = solid[:, 1:, :]
    down[:, 1:, :] = solid[:, :-1, :]
    plate = solid & ~up & ~down

    nz = np.argwhere(solid)
    if nz.size == 0:
        return []
    lo, hi = nz.min(axis=0), nz.max(axis=0)
    foot = max(1, (hi[0] - lo[0] + 1) * (hi[2] - lo[2] + 1))

    floors: list[int] = []
    for y in range(1, h - 1):
        if plate[:, y, :].sum() < 0.18 * foot:
            continue
        above = interior[:, y + 1:y + 4, :].sum()
        if above >= 6:
            floors.append(y)
    return floors


_TERRAIN_HINTS = ("dirt", "grass_block", "grass_path", "sand", "gravel", "water",
                  "snow", "podzol", "mycelium", "clay", "farmland")


def _dominant(voxels: np.ndarray, *, skip_bottom: int = 3,
              palette: dict[int, str] | None = None) -> int:
    """主材质：跳过底部地基/地形层，并排除地形类方块。"""
    upper = voxels[:, skip_bottom:, :]
    solid = upper[upper > 0]
    if solid.size == 0:
        solid = voxels[voxels > 0]
    if solid.size == 0:
        return 0
    ids, counts = np.unique(solid, return_counts=True)
    if palette:
        keep = [
            (bid, c) for bid, c in zip(ids, counts)
            if not any(h in str(palette.get(int(bid), "")).split(":", 1)[-1]
                       for h in _TERRAIN_HINTS)
        ]
        if keep:
            return int(max(keep, key=lambda kv: kv[1])[0])
    return int(np.bincount(solid).argmax())


def _stairs_material(palette: dict[int, str], wall_id: int) -> int:
    wall_short = str(palette.get(wall_id, "")).split(":", 1)[-1]
    root = wall_short.split("_")[0]
    stairs = [b for b, n in palette.items() if b > 0 and "stairs" in n]
    if not stairs:
        return 0
    for b in stairs:
        if root and root in palette[b]:
            return int(b)
    return int(stairs[0])


def plan_interior(
    voxels: np.ndarray,
    palette: dict[int, str],
    *,
    rooms_per_floor: int = 2,
    wall_material: int | None = None,
) -> tuple[np.ndarray, dict]:
    """插入隔墙/门洞与楼梯；只动室内，外壳与家具不碰。"""
    arr = np.asarray(voxels).copy()
    solid = arr > 0
    interior = _interior_air(solid)
    floors = detect_floors(solid, interior)
    if int(interior.sum()) < 10:
        raise ValueError("室内几乎没有封闭空间（实心体量），无法规划房间")

    wall = int(wall_material or _dominant(arr, palette=palette))
    stair = _stairs_material(palette, wall)
    tread = stair or wall

    nz = np.argwhere(solid)
    top = int(nz[:, 1].max())

    bands: list[tuple[int, int]] = []
    for i, fy in enumerate(floors):
        y_end = floors[i + 1] if i + 1 < len(floors) else top + 1
        if y_end - fy >= 3:
            bands.append((fy + 1, y_end))
    if not bands:  # 单层：整栋室内当一个分区处理
        ys = np.where(interior.any(axis=(0, 2)))[0]
        bands = [(int(ys.min()), int(ys.max()) + 1)]

    added_wall = 0
    added_stair = 0
    rooms_total = 0

    for band_lo, band_hi in bands:
        mask = interior[:, band_lo:band_hi, :]
        flat = mask.any(axis=1)  # (x, z) 室内投影
        if flat.sum() < 10:
            continue

        xs = np.where(flat.any(axis=1))[0]
        zs = np.where(flat.any(axis=0))[0]
        x_ext = xs[-1] - xs[0] + 1
        z_ext = zs[-1] - zs[0] + 1
        parts = max(2, int(rooms_per_floor))
        if x_ext < 5 and z_ext < 5:
            continue

        split_x = x_ext >= z_ext
        span = x_ext if split_x else z_ext
        for k in range(1, parts):
            cut = (xs[0] if split_x else zs[0]) + int(round(span * k / parts))
            centre = (zs[0] + zs[-1]) / 2 if split_x else (xs[0] + xs[-1]) / 2
            for y in range(band_lo, band_hi):
                level = mask[:, y - band_lo, :]
                for j in range(span):
                    if split_x:
                        x, z = cut, (zs[0] + j)
                    else:
                        x, z = (xs[0] + j), cut
                    if not (0 <= x < level.shape[0] and 0 <= z < level.shape[1]):
                        continue
                    if not level[x, z]:
                        continue
                    if abs((z if split_x else x) - centre) <= 1:  # 门洞
                        continue
                    if arr[x, y, z] == 0:
                        arr[x, y, z] = wall
                        added_wall += 1
        rooms_total += parts

    # 楼梯：每两层之间在室内角落开洞并铺一段踏步
    for idx in range(len(floors) - 1):
        lo, hi = floors[idx], floors[idx + 1]
        mask = interior[:, lo + 1:hi, :]
        if not mask.any():
            continue
        flat = mask.any(axis=1)
        xs = np.where(flat.any(axis=1))[0]
        zs = np.where(flat.any(axis=0))[0]
        if len(xs) < 4 or len(zs) < 3:
            continue
        x0, z0 = int(xs[0]), int(zs[0])
        # 上层的楼板开 2×2 洞口
        arr[x0:x0 + 2, hi, z0:z0 + 2] = 0
        steps = min(hi - lo - 1, len(xs) - 1)
        for k in range(max(0, steps)):
            x = min(x0 + k, xs[-1])
            y = lo + 1 + k
            if y >= hi:
                break
            if arr[x, y, z0] == 0:
                arr[x, y, z0] = tread
                added_stair += 1

    info = {
        "floors": floors,
        "single": not floors,
        "walls": added_wall,
        "stairs": added_stair,
        "rooms": rooms_total,
        "wall_material": palette.get(wall, str(wall)),
        "stair_material": palette.get(tread, str(tread)),
    }
    return arr, info


def summary(info: dict) -> str:
    if not info.get("floors"):
        if not info.get("walls"):
            return "没有可分割的室内空间"
        return f"单层分区：隔墙 {info['walls']} 格 · 房间约 {info['rooms']} 间（无楼梯）"
    floors = "、".join(f"y={y}" for y in info["floors"])
    return (
        f"楼板 {len(info['floors'])} 层（{floors}）· 隔墙 {info['walls']} 格"
        f" · 楼梯 {info['stairs']} 格 · 房间约 {info['rooms']} 间"
    )


def _load_npz(path: str) -> np.ndarray:
    with np.load(path) as z:
        for key in ("voxels", "arr_0", "data"):
            if key in z:
                return z[key].astype(np.int16)
    raise KeyError(f"{path} 里没有 voxels")


def _main(argv: list[str] | None = None) -> int:  # pragma: no cover - 手动调试
    from src.app.sample_runner import project_root
    from src.utils import load_palette

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("用法: python -m src.app.floors <sample.npz>")
        return 2
    palette = load_palette(project_root() / "data" / "palette.json")
    vox = _load_npz(args[0])
    out, info = plan_interior(vox, palette)
    print(summary(info))
    print(f"wall={info['wall_material']} stair={info['stair_material']}")
    print(f"non_air {int((vox > 0).sum())} → {int((out > 0).sum())}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
