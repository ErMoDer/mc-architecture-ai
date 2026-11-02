from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# 极简自定义体素格式，便于手工造样本、不依赖 schematic 解析先跑通训练。
# 文件：*.vox.json
# {
#   "size": 32,
#   "blocks": [["minecraft:stone", x, y, z], ...]
# }


def load_vox_json(path: Path, size: int, name_to_id: dict[str, int]) -> np.ndarray:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    src_size = int(data.get("size", size))
    voxels = np.zeros((size, size, size), dtype=np.int16)
    ox = (size - src_size) // 2
    oy = (size - src_size) // 2
    oz = (size - src_size) // 2

    for item in data.get("blocks", []):
        name, x, y, z = item[0], int(item[1]), int(item[2]), int(item[3])
        if name not in name_to_id:
            raise KeyError(f"{path.name}: 方块 {name} 不在 palette 中，请先加入 data/palette.json")
        xx, yy, zz = x + ox, y + oy, z + oz
        if 0 <= xx < size and 0 <= yy < size and 0 <= zz < size:
            voxels[xx, yy, zz] = name_to_id[name]
    return voxels


def save_npz_npz(path: Path, voxels: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, voxels=voxels.astype(np.int16))


def voxels_to_block_list(
    voxels: np.ndarray, id_to_name: dict[int, str], skip_air: bool = True
) -> list[tuple[str, int, int, int]]:
    blocks: list[tuple[str, int, int, int]] = []
    d, h, w = voxels.shape
    for x in range(d):
        for y in range(h):
            for z in range(w):
                bid = int(voxels[x, y, z])
                name = id_to_name.get(bid, "minecraft:stone")
                if skip_air and name.endswith(":air"):
                    continue
                blocks.append((name, x, y, z))
    return blocks
