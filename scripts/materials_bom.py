# -*- coding: utf-8 -*-
"""CLI: material BOM (+ optional Y-layer previews) for npz / litematic samples.

Inspired by Litematica-Nova material + layer ideas; reimplemented locally.
See docs/nova-borrow.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.layer_preview import write_layer_previews
from src.app.materials_bom import bom_from_path, load_voxels_any, write_bom_bundle
from src.utils import load_config, load_palette


def _collect_inputs(path: Path, latest: int | None) -> list[Path]:
    path = Path(path)
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(path)
    pats = (
        "*.npz",
        "*.litematic",
        "*.npy",
    )
    files: list[Path] = []
    for pat in pats:
        files.extend(path.glob(pat))
        files.extend(path.glob("**/" + pat))
    # de-dupe, prefer shallower
    uniq: dict[str, Path] = {}
    for p in files:
        if p.suffix.lower() == ".npz" and p.name.endswith(".npz.npz"):
            continue
        key = str(p.resolve())
        uniq[key] = p
    files = list(uniq.values())
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if latest is not None and latest > 0:
        files = files[:latest]
    return sorted(files, key=lambda p: p.name)


def _stem_of(path: Path) -> str:
    name = path.name
    if name.endswith(".npz.npz"):
        return name[: -len(".npz.npz")]
    return path.stem


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Material BOM + optional Y-layer previews (Nova-inspired)"
    )
    ap.add_argument("--input", required=True, help="sample .npz / .litematic / dir")
    ap.add_argument("--out-dir", default=None, help="output directory (default: beside input or --run-dir)")
    ap.add_argument("--run-dir", default=None, help="optional parent run folder")
    ap.add_argument("--palette", default=None)
    ap.add_argument("--latest", type=int, default=0, help="when input is dir, N newest (0=all)")
    ap.add_argument("--csv", action="store_true", default=True, help="write CSV (default on)")
    ap.add_argument("--no-csv", action="store_true", help="skip CSV")
    ap.add_argument("--layers", action="store_true", help="write Y-slice PNGs + HTML")
    ap.add_argument("--layer-scale", type=int, default=12)
    ap.add_argument("--max-layers", type=int, default=64)
    args = ap.parse_args()

    cfg = load_config(ROOT / "configs/default.yaml")
    palette_path = Path(args.palette) if args.palette else ROOT / cfg["data"]["palette_path"]
    palette = load_palette(palette_path)

    latest = None if args.latest == 0 else args.latest
    inputs = _collect_inputs(Path(args.input), latest)
    if not inputs:
        raise SystemExit(f"no inputs under {args.input}")

    if args.run_dir:
        base_out = Path(args.run_dir)
    elif args.out_dir:
        base_out = Path(args.out_dir)
    else:
        # beside first input
        p0 = inputs[0]
        base_out = p0.parent / "materials" if p0.is_file() else Path(args.input) / "materials"
    base_out.mkdir(parents=True, exist_ok=True)

    summary: list[dict] = []
    for src in inputs:
        stem = _stem_of(src)
        sample_out = base_out / stem
        sample_out.mkdir(parents=True, exist_ok=True)
        rows, info = bom_from_path(src, palette=palette, palette_path=palette_path)
        paths = write_bom_bundle(
            rows,
            sample_out,
            stem=stem,
            source=str(src),
            extra={"palette_source": info.get("palette_source"), "shape": info.get("shape")},
            write_csv=not args.no_csv,
        )
        layer_info = None
        if args.layers:
            voxels, meta = load_voxels_any(src)
            use_pal = palette
            if meta and "litematic_names" in meta:
                use_pal = {i: n for i, n in enumerate(meta["litematic_names"])}
            layer_info = write_layer_previews(
                voxels,
                use_pal,
                sample_out / "layers",
                stem=stem,
                scale=args.layer_scale,
                max_layers=args.max_layers,
            )
        entry = {
            "source": str(src),
            "stem": stem,
            "out": str(sample_out),
            "bom": {k: str(v) for k, v in paths.items()},
            "totals": {
                "unique": len(rows),
                "blocks": sum(r.count for r in rows),
            },
            "layers": layer_info,
        }
        summary.append(entry)
        print(
            f"OK {src.name}: unique={entry['totals']['unique']} "
            f"blocks={entry['totals']['blocks']} -> {sample_out}"
        )

    (base_out / "BOM_INDEX.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"done. index={base_out / 'BOM_INDEX.json'}")


if __name__ == "__main__":
    main()