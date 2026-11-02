from __future__ import annotations

from pathlib import Path

import numpy as np

from .io_vox import voxels_to_block_list


def export_mcfunction(
    voxels: np.ndarray,
    id_to_name: dict[int, str],
    out_path: Path,
    origin: tuple[int, int, int] = (0, 64, 0),
) -> int:
    """导出为 /setblock 命令文件，可在游戏里 `/function` 或逐条执行。"""
    ox, oy, oz = origin
    blocks = voxels_to_block_list(voxels, id_to_name, skip_air=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"setblock {ox + x} {oy + y} {oz + z} {name}"
        for name, x, y, z in blocks
    ]
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)
