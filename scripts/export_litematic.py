"""Export sample .npz / .npz.npz to .litematic for mc-companion."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.export_litematic_util import (
    describe_schematics_target,
    export_voxels_to_companion,
    resolve_schematics_dir,
)
from src.data.mc_versions import DEFAULT_VERSION_ID, list_versions
from src.utils import load_config, load_palette


def default_out_dir() -> Path:
    return resolve_schematics_dir()


def load_sample_voxels(path: Path) -> np.ndarray:
    path = Path(path)
    if path.suffix == ".npz" or path.name.endswith(".npz.npz"):
        with np.load(path) as data:
            key = "voxels" if "voxels" in data.files else data.files[0]
            return np.asarray(data[key])
    if path.suffix == ".npy":
        return np.asarray(np.load(path))
    raise ValueError(f"unsupported sample file: {path}")


def collect_inputs(input_path: Path, latest: int | None) -> list[Path]:
    input_path = Path(input_path)
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(f"input not found: {input_path}")

    files: list[Path] = []
    for p in sorted(input_path.iterdir()):
        if not p.is_file():
            continue
        stem = p.name
        # prefer sample_XXX.npz / sample_edit_XXX.npz ; skip *.npz.npz double suffix if real sibling exists
        if (
            re.fullmatch(r"sample_\d+\.npz", stem)
            or re.fullmatch(r"sample_edit_\d+\.npz", stem)
            or re.fullmatch(r"sample_s.+_t.+_\d+\.npz", stem)
        ):
            files.append(p)
        elif stem.endswith(".npz.npz") and re.match(r"sample_", stem):
            # only if no plain .npz sibling
            plain = input_path / stem[: -len(".npz")]  # weird; better: strip .npz.npz -> base
            # sample_000.npz.npz -> sample_000.npz
            base = Path(stem[: -len(".npz")])  # sample_000.npz
            if not (input_path / base.name).exists():
                files.append(p)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if latest is not None and latest > 0:
        files = files[:latest]
    # export in name order for stable naming
    return sorted(files, key=lambda p: p.name)


def safe_stem(path: Path, prefix: str) -> str:
    stem = path.name
    if stem.endswith(".npz.npz"):
        stem = stem[: -len(".npz.npz")]
    elif stem.endswith(".npz"):
        stem = stem[: -len(".npz")]
    elif stem.endswith(".npy"):
        stem = stem[: -len(".npy")]
    else:
        stem = path.stem
    stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem).strip("_") or "sample"
    if prefix:
        return f"{prefix}_{stem}" if not stem.startswith(prefix) else stem
    return stem


def main() -> None:
    parser = argparse.ArgumentParser(description="Export samples to .litematic for companion")
    parser.add_argument(
        "--input",
        default=str(ROOT / "outputs" / "samples"),
        help="sample file or directory (default: outputs/samples)",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="output directory (default: companion SCHEMATICS_DIR, else outputs/litematic)",
    )
    parser.add_argument("--name", default="ai", help="filename prefix")
    parser.add_argument("--latest", type=int, default=4, help="when input is a dir, export N newest (0=all)")
    parser.add_argument(
        "--print-dir",
        action="store_true",
        help="print resolved companion schematics dir and exit",
    )
    parser.add_argument("--palette", default=None, help="palette.json path")
    parser.add_argument("--author", default="mc-architecture-ai")
    parser.add_argument("--no-verify", action="store_true", help="skip roundtrip verify")
    parser.add_argument(
        "--target-version",
        default=DEFAULT_VERSION_ID,
        help=(
            "Java target version for block remap/downgrade "
            f"(default: {DEFAULT_VERSION_ID}). Known: "
            + ", ".join(v.id for v in list_versions())
        ),
    )
    parser.add_argument(
        "--materials",
        action="store_true",
        help="after export, write material BOM (md/txt/csv/json) under <out>/materials/",
    )
    parser.add_argument(
        "--layers",
        action="store_true",
        help="with --materials: also write Y-slice PNG + HTML layer previews",
    )
    args = parser.parse_args()
    if getattr(args, "print_dir", False):
        info = describe_schematics_target()
        print("schematics_dir=", info["schematics_dir"])
        print("exists=", info["exists"])
        print("companion_env=", info["companion_env"])
        print("source=", info["source"])
        return


    cfg = load_config(ROOT / "configs/default.yaml")
    palette_path = Path(args.palette) if args.palette else ROOT / cfg["data"]["palette_path"]
    palette = load_palette(palette_path)

    out_dir = Path(args.out_dir) if args.out_dir else default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    latest = None if args.latest == 0 else args.latest
    inputs = collect_inputs(Path(args.input), latest)
    if not inputs:
        raise SystemExit(f"no samples found under {args.input}")

    print(f"palette={palette_path} ({len(palette)} ids)")
    print(f"out_dir={out_dir}")
    print(f"exporting {len(inputs)} file(s)")

    print(f"target_version={args.target_version} (Java)")
    for src in inputs:
        voxels = load_sample_voxels(src)
        out_name = safe_stem(src, args.name)
        info = export_voxels_to_companion(
            voxels,
            palette,
            name=out_name,
            author=args.author,
            out_dir=out_dir,
            verify=not args.no_verify,
            target_version=args.target_version,
        )
        print(
            f"OK {src.name} -> {info['path']} "
            f"target={info.get('target_version')} remap={info.get('remap_changed_pairs')} "
            f"size={info['size']} non_air={info['non_air']} "
            f"palette={info['palette_len']} bits={info['bits']} "
            f"verify_non_air={info['loaded_non_air']}"
        )

        if args.materials:
            from src.app.materials_bom import write_export_sidecars

            side = write_export_sidecars(
                voxels,
                palette,
                info["path"],
                with_bom=True,
                with_layers=args.layers,
                source=str(src),
                extra={"target_version": info.get("target_version")},
            )
            print(f"  BOM -> {(side.get('bom_paths') or {}).get('md')}")
            if args.layers and side.get("layers"):
                print(f"  layers -> {side['layers'].get('html') or side['layers'].get('out_dir')}")

    print("done. In-game: talk to Andy -> 列出投影 / 建造 <name>")


if __name__ == "__main__":
    main()
