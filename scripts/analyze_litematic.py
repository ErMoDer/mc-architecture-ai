#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI: analyze a .litematic into markdown (+ optional JSON) report.

Example:
  .\\.venv\\Scripts\\python.exe scripts/analyze_litematic.py data/raw/mcblock/foo.litematic
  .\\.venv\\Scripts\\python.exe scripts/analyze_litematic.py foo.litematic --out reports/a.md --json reports/a.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.schematic_analyze import analyze_litematic, report_to_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1: analyze .litematic (structure/style/redstone)")
    parser.add_argument("path", type=str, help="Path to .litematic")
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Markdown output path (default: outputs/analyze/<stem>_report.md)",
    )
    parser.add_argument(
        "--json",
        dest="json_out",
        type=str,
        default=None,
        help="Optional JSON output path (default: alongside md as <stem>_report.json if omitted? "
        "Only written when this flag is set, OR use --write-json)",
    )
    parser.add_argument(
        "--write-json",
        action="store_true",
        help="Also write JSON next to the markdown (outputs/analyze/<stem>_report.json)",
    )
    args = parser.parse_args()

    src = Path(args.path)
    if not src.is_file():
        # allow relative to ROOT
        alt = ROOT / args.path
        if alt.is_file():
            src = alt
        else:
            raise SystemExit(f"file not found: {args.path}")

    if args.out:
        out_md = Path(args.out)
        if not out_md.is_absolute():
            out_md = ROOT / out_md
    else:
        out_md = ROOT / "outputs" / "analyze" / f"{src.stem}_report.md"

    out_md.parent.mkdir(parents=True, exist_ok=True)

    result = analyze_litematic(src)
    md = report_to_markdown(result)
    out_md.write_text(md, encoding="utf-8")
    print(f"wrote {out_md}")

    json_path: Path | None = None
    if args.json_out:
        json_path = Path(args.json_out)
        if not json_path.is_absolute():
            json_path = ROOT / json_path
    elif args.write_json:
        json_path = out_md.with_suffix(".json")
        if json_path.name.endswith("_report.json") is False:
            json_path = out_md.parent / f"{src.stem}_report.json"

    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {json_path}")

    ov = result.get("overview") or {}
    size = ov.get("size") or {}
    print(
        f"summary: size={size.get('x')}x{size.get('y')}x{size.get('z')} "
        f"non_air={ov.get('non_air')} unique={ov.get('unique_block_types')} "
        f"redstone={result.get('redstone', {}).get('total_redstone_blocks', 0)}"
    )


if __name__ == "__main__":
    main()
