# -*- coding: utf-8 -*-
"""Export full_style_v4 npz to companion schematics with Chinese architecture names."""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

from src.data.export_litematic_util import export_voxels_to_companion, resolve_schematics_dir
from src.utils import load_config, load_palette
from src.app.gen_strategy import project_root

ROOT = project_root()
NPZ_DIR = ROOT / "outputs" / "design" / "full_style_v4_20261020_112642" / "npz"

# stem (without .npz) -> Chinese base name (without .litematic)
NAME_MAP = {
    "sample_schinese_tflat_000": "中式_000_v26.3",
    "sample_seuropean_tflat_000": "欧式_000_v26.3",
    "sample_smedieval_tflat_000": "中世纪_000_v26.3",
    "sample_smodern_tflat_000": "现代_000_v26.3",
    "sample_sindustrial_tflat_000": "工业_000_v26.3",
    "sample_srustic_tflat_000": "田园_000_v26.3",
    "sample_srustic_tflat_001": "田园_001_v26.3",
    "sample_sfantasy_tflat_000": "奇幻_000_v26.3",
    "sample_sfantasy_tflat_001": "奇幻_001_v26.3",
}

# Early-tech / redstone names that must NOT be deleted or overwritten by this export
# (we only overwrite the architecture chinese stems above).
EARLY_TECH_PREFIXES = (
    "超级熔炉_",
    "小型铁矿_",
    "简易铁矿_",
    "大型刷怪经验塔_",
    "鸡舍_二_红石参考_",
)

def main() -> None:
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    out_dir = resolve_schematics_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot early-tech files (existence + size) before export
    early_before = {}
    for p in out_dir.glob("*.litematic"):
        if any(p.name.startswith(pref) for pref in EARLY_TECH_PREFIXES):
            early_before[p.name] = p.stat().st_size

    written = []
    for stem, cn in NAME_MAP.items():
        src = NPZ_DIR / (stem + ".npz")
        if not src.is_file():
            # try .npz.npz
            src2 = NPZ_DIR / (stem + ".npz.npz")
            src = src2 if src2.is_file() else src
        if not src.is_file():
            raise FileNotFoundError(src)
        with np.load(src) as data:
            key = "voxels" if "voxels" in data.files else data.files[0]
            voxels = np.asarray(data[key])
        info = export_voxels_to_companion(
            voxels,
            palette,
            name=cn,
            author="mc-architecture-ai",
            out_dir=out_dir,
            verify=True,
            target_version="26.3",
        )
        path = Path(info["path"])
        # materials BOM
        from src.app.materials_bom import write_export_sidecars
        side = write_export_sidecars(
            voxels,
            palette,
            path,
            with_bom=True,
            with_layers=False,
            source=str(src),
            extra={"target_version": info.get("target_version"), "style_batch": "full_style_v4"},
        )
        written.append({
            "cn": cn,
            "path": str(path),
            "size": path.stat().st_size,
            "non_air": info.get("non_air"),
            "bom": (side.get("bom_paths") or {}).get("md"),
        })
        print("OK", cn, "->", path.name, "non_air", info.get("non_air"))

    # Remove stale English architecture demo names if present (do not touch early-tech)
    stale_globs = [
        "ai_sample_schinese_*",
        "ai_sample_seuropean_*",
        "ai_sample_smedieval_*",
        "ai_sample_smodern_*",
        "ai_sample_sindustrial_*",
        "ai_sample_srustic_*",
        "ai_sample_sfantasy_*",
    ]
    removed = []
    for g in stale_globs:
        for p in out_dir.glob(g):
            if p.suffix == ".litematic" or p.is_dir():
                # also materials folders named after english stems
                pass
            if p.is_file() and p.suffix == ".litematic":
                p.unlink()
                removed.append(p.name)
            elif p.is_dir() and p.parent.name == "materials":
                shutil.rmtree(p)
                removed.append(str(p))

    # Verify early-tech untouched
    early_after = {}
    for p in out_dir.glob("*.litematic"):
        if any(p.name.startswith(pref) for pref in EARLY_TECH_PREFIXES):
            early_after[p.name] = p.stat().st_size

    missing = sorted(set(early_before) - set(early_after))
    changed = [k for k in early_before if k in early_after and early_before[k] != early_after[k]]
    print("EARLY_TECH_OK", missing == [] and changed == [], "count", len(early_after))
    if missing or changed:
        print("MISSING", missing, "CHANGED", changed)
    print("WRITTEN", len(written))
    for w in written:
        print(" ", w["cn"], w["size"])
    if removed:
        print("REMOVED_STALE", removed)

if __name__ == "__main__":
    main()
