#!/usr/bin/env python3
"""CLI for saved design schemes.

Examples:
  python scripts/scheme.py list
  python scripts/scheme.py create "庄园" --from-npz outputs/samples/sample_000.npz --style medieval
  python scripts/scheme.py save zhuangyuan --from-npz path/to/edit.npz
  python scripts/scheme.py load zhuangyuan
  python scripts/scheme.py import-litematic zhuangyuan path/to/new.litematic --mode overlay
  python scripts/scheme.py apply-edit zhuangyuan --replace 12 45
  python scripts/scheme.py export zhuangyuan --litematic
  python scripts/scheme.py snapshot zhuangyuan
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app.sample_runner import load_voxel_npz
from src.app.schemes import (
    apply_block_replace,
    create_scheme,
    export_scheme_litematic,
    export_scheme_npz,
    import_litematic,
    list_schemes,
    load_scheme,
    save_scheme,
    snapshot_current,
    stamp_version,
)


def cmd_list(_args: argparse.Namespace) -> int:
    rows = list_schemes()
    if not rows:
        print("(no schemes yet — create one with: scheme.py create \"庄园\")")
        return 0
    for m in rows:
        print(
            f"{m.get('slug'):<24}  name={m.get('name')}  "
            f"non_air={m.get('non_air')}  ver={m.get('version')}  "
            f"updated={m.get('updated')}"
        )
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    kwargs = dict(
        name=args.name,
        style=args.style,
        terrain=args.terrain,
        notes=args.notes or "",
        slug=args.slug,
    )
    if args.from_npz:
        kwargs["from_npz"] = args.from_npz
    if args.from_litematic:
        kwargs["from_litematic"] = args.from_litematic
    result = create_scheme(**kwargs)
    print(json.dumps({
        "ok": True,
        "slug": result["slug"],
        "dir": str(result["dir"]),
        "non_air": result["non_air"],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_save(args: argparse.Namespace) -> int:
    if args.from_npz:
        voxels = load_voxel_npz(args.from_npz)
    else:
        # re-save current (notes/meta only) — still snapshots if forced
        data = load_scheme(args.slug)
        voxels = data["voxels"]
    result = save_scheme(
        args.slug,
        voxels,
        notes=args.notes,
        style=args.style,
        terrain=args.terrain,
        bump_version=bool(args.bump_version),
    )
    print(json.dumps({
        "ok": True,
        "slug": result["slug"],
        "non_air": result["non_air"],
        "npz": str(result["npz"]),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    data = load_scheme(args.slug)
    meta = data["meta"]
    print(json.dumps({
        "ok": True,
        "slug": data["slug"],
        "npz_path": str(data["npz_path"]),
        "dir": str(data["dir"]),
        "shape": list(data["voxels"].shape),
        "non_air": int((data["voxels"] > 0).sum()),
        "meta": meta,
    }, ensure_ascii=False, indent=2))
    if args.copy_to:
        dest = Path(args.copy_to)
        export_scheme_npz(args.slug, dest)
        print(f"copied -> {dest}")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    result = import_litematic(args.slug, args.litematic, mode=args.mode)
    print(json.dumps({
        "ok": True,
        "slug": result["slug"],
        "mode": result["mode"],
        "non_air": result["non_air"],
        "ref": str(result["ref"]),
        "version": result["meta"].get("version"),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_apply_edit(args: argparse.Namespace) -> int:
    if not args.replace or len(args.replace) != 2:
        print("--replace needs SOURCE_ID TARGET_ID", file=sys.stderr)
        return 2
    src, tgt = int(args.replace[0]), int(args.replace[1])
    result = apply_block_replace(args.slug, src, tgt)
    print(json.dumps({
        "ok": True,
        "slug": result["slug"],
        "replaced": result["replaced"],
        "non_air": result["non_air"],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    out: dict = {"ok": True, "slug": args.slug}
    if args.npz:
        dest = Path(args.npz)
        export_scheme_npz(args.slug, dest)
        out["npz"] = str(dest)
    if args.litematic or not args.npz:
        info = export_scheme_litematic(
            args.slug,
            out_dir=args.out_dir,
            name=args.name,
            target_version=args.version,
        )
        out["litematic"] = {k: (str(v) if hasattr(v, "__fspath__") else v) for k, v in info.items()}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    p = snapshot_current(args.slug, reason=args.reason or "manual")
    if args.version:
        vp = stamp_version(args.slug, label=args.reason or "snapshot")
        print(json.dumps({"ok": True, "history": str(p), "version": str(vp)}, ensure_ascii=False))
    else:
        print(json.dumps({"ok": True, "history": str(p)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Saved design schemes for mc-architecture-ai")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="List schemes")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("create", help="Create a named scheme")
    sp.add_argument("name")
    sp.add_argument("--slug")
    sp.add_argument("--from-npz")
    sp.add_argument("--from-litematic")
    sp.add_argument("--style", default="medieval")
    sp.add_argument("--terrain", default="flat")
    sp.add_argument("--notes", default="")
    sp.set_defaults(func=cmd_create)

    sp = sub.add_parser("save", help="Save voxels into an existing scheme")
    sp.add_argument("slug")
    sp.add_argument("--from-npz", help="npz to write as current (default: re-touch meta)")
    sp.add_argument("--notes")
    sp.add_argument("--style")
    sp.add_argument("--terrain")
    sp.add_argument("--bump-version", action="store_true")
    sp.set_defaults(func=cmd_save)

    sp = sub.add_parser("load", help="Show / optionally copy scheme voxels")
    sp.add_argument("slug")
    sp.add_argument("--copy-to", help="Copy current.npz to this path")
    sp.set_defaults(func=cmd_load)

    sp = sub.add_parser("import-litematic", help="Import a litematic into a scheme")
    sp.add_argument("slug")
    sp.add_argument("litematic")
    sp.add_argument(
        "--mode",
        choices=["replace", "overlay", "merge"],
        default="overlay",
        help="replace=overwrite; overlay=incoming non-air wins; merge=same as overlay for solids",
    )
    sp.set_defaults(func=cmd_import)

    sp = sub.add_parser("apply-edit", help="Replace one block id with another in scheme")
    sp.add_argument("slug")
    sp.add_argument("--replace", nargs=2, metavar=("SRC", "TGT"))
    sp.set_defaults(func=cmd_apply_edit)

    sp = sub.add_parser("export", help="Export scheme as litematic and/or npz")
    sp.add_argument("slug")
    sp.add_argument("--litematic", action="store_true", help="Write .litematic (default if no --npz)")
    sp.add_argument("--npz", help="Also/copy write npz to this path")
    sp.add_argument("--out-dir", help="Litematic output directory")
    sp.add_argument("--name", help="Export basename")
    sp.add_argument("--version", help="Target MC version id for remap")
    sp.set_defaults(func=cmd_export)

    sp = sub.add_parser("snapshot", help="Snapshot current into history/")
    sp.add_argument("slug")
    sp.add_argument("--reason", default="manual")
    sp.add_argument("--version", action="store_true", help="Also stamp versions/vNNN")
    sp.set_defaults(func=cmd_snapshot)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
