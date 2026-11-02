# -*- coding: utf-8 -*-
"""Export latest pool_scaffold npz to companion schematics with 新池_ Chinese names."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.app.gen_strategy import project_root
from src.data.export_litematic_util import export_voxels_to_companion, resolve_schematics_dir
from src.utils import load_config, load_palette

ROOT = project_root()

NAME_MAP = {
    "sample_sindustrial_tflat_000": "新池_工业住宅_v26.3",
    "sample_seuropean_tflat_000": "新池_欧式住宅_v26.3",
    "sample_srustic_tflat_000": "新池_田园住宅_v26.3",
    "sample_schinese_tflat_000": "新池_中式住宅_v26.3",
    "sample_smodern_tflat_000": "新池_现代住宅_v26.3",
    "sample_swestern_tflat_000": "新池_西部住宅_v26.3",
    "sample_smedieval_tflat_000": "新池_中世纪住宅_v26.3",
    "sample_sfantasy_tflat_000": "新池_幻想住宅_v26.3",
}

EARLY_TECH_PREFIXES = (
    "超级熔炉",
    "小型铁矿",
    "简易铁矿",
    "大型刷怪经验塔",
    "鸡舍",
)


def _latest_pool_dir() -> Path:
    design = ROOT / "outputs" / "design"
    rid = design / "_latest_pool_scaffold.txt"
    if rid.is_file():
        name = rid.read_text(encoding="utf-8").strip()
        p = design / name
        if p.is_dir():
            return p
    cands = sorted(design.glob("pool_scaffold_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        raise FileNotFoundError("no pool_scaffold_* under outputs/design")
    return cands[0]


def main() -> None:
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    run_dir = _latest_pool_dir()
    npz_dir = run_dir / "npz"
    out_dir = resolve_schematics_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    print("RUN", run_dir)
    print("SCHEM", out_dir)

    early_before = {}
    for p in out_dir.glob("*.litematic"):
        if any(p.name.startswith(pref) for pref in EARLY_TECH_PREFIXES):
            early_before[p.name] = p.stat().st_size

    written = []
    skipped = []
    for stem, cn in NAME_MAP.items():
        src = npz_dir / (stem + ".npz")
        if not src.is_file():
            src2 = npz_dir / (stem + ".npz.npz")
            src = src2 if src2.is_file() else src
        if not src.is_file():
            skipped.append(stem)
            print("MISS", stem)
            continue
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
        from src.app.materials_bom import write_export_sidecars

        write_export_sidecars(
            voxels,
            palette,
            path,
            with_bom=True,
            with_layers=False,
            source=str(src),
            extra={"target_version": info.get("target_version"), "style_batch": run_dir.name},
        )
        written.append({"cn": cn, "path": str(path), "size": path.stat().st_size, "non_air": info.get("non_air")})
        print("OK", cn, "->", path.name, "non_air", info.get("non_air"))

    early_after = {}
    for p in out_dir.glob("*.litematic"):
        if any(p.name.startswith(pref) for pref in EARLY_TECH_PREFIXES):
            early_after[p.name] = p.stat().st_size
    missing = sorted(set(early_before) - set(early_after))
    changed = [k for k in early_before if k in early_after and early_before[k] != early_after[k]]
    print("EARLY_TECH_OK", missing == [] and changed == [], "count", len(early_after))
    if missing or changed:
        print("MISSING", missing, "CHANGED", changed)
    print("WRITTEN", len(written), "SKIPPED", skipped)
    for w in written:
        print(" ", w["cn"], w["size"])


if __name__ == "__main__":
    main()
