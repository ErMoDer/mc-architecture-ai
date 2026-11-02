from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset

from .labels import load_labels_map


class VoxelBuildDataset(Dataset):
    """读取 prepare_data 产出的 .npz.npz（字段 voxels: int16 [D,H,W]）。

    conditional=True 时返回 (voxels, style_id, terrain_id)。
    """

    def __init__(
        self,
        processed_dir: str | Path,
        size: int = 64,
        *,
        conditional: bool = False,
        labels_path: str | Path | None = None,
    ):
        self.processed_dir = Path(processed_dir)
        self.size = size
        self.conditional = conditional
        self.files = sorted(self.processed_dir.glob("*.npz"))
        if not self.files:
            raise FileNotFoundError(
                f"未找到数据：{self.processed_dir}\\*.npz\n"
                "请先把建筑放到 data/raw，再运行：python scripts/prepare_data.py"
            )
        self._labels: dict[str, dict[str, Any]] = {}
        if conditional:
            lp = Path(labels_path) if labels_path else self.processed_dir / "labels.json"
            if not lp.is_absolute():
                # 相对项目根或 processed
                if not lp.exists():
                    alt = self.processed_dir.parent.parent / lp
                    lp = alt if alt.exists() else lp
            if not lp.exists():
                raise FileNotFoundError(
                    f"条件训练需要标签文件：{lp}\n请先运行：python scripts/build_labels.py"
                )
            self._labels = load_labels_map(lp)

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, idx: int):
        path = self.files[idx]
        arr = np.load(path)["voxels"].astype(np.int64)
        if arr.shape != (self.size, self.size, self.size):
            raise ValueError(
                f"{path.name} 尺寸 {arr.shape} != ({self.size},) * 3"
            )
        voxels = torch.from_numpy(arr)
        if not self.conditional:
            return voxels
        lab = self._labels.get(path.name) or self._labels.get(path.stem)
        if lab is None:
            # 缺标签：unknown / flat = 通常为 0
            return voxels, torch.tensor(0, dtype=torch.long), torch.tensor(0, dtype=torch.long)
        return (
            voxels,
            torch.tensor(int(lab["style_id"]), dtype=torch.long),
            torch.tensor(int(lab["terrain_id"]), dtype=torch.long),
        )
