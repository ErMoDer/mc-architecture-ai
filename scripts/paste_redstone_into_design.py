# -*- coding: utf-8 -*-
"""Paste a hand redstone template into an architectural design npz.

Not VAE circuit invention — templates from data/redstone_templates only.

Example:
  .venv\\Scripts\\python.exe scripts\\paste_redstone_into_design.py ^
    --npz outputs/design/full_style_v4_20261020_112642/npz/sample_seuropean_tflat_000.npz ^
    --template auto:door ^
    --companion --companion-name 欧式_红石门控
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.redstone_templates import (
    bootstrap_templates,
    load_all_templates,
    paste_redstone_into_design,
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="将红石原理模板嵌入建筑设计 npz（非 VAE 发明电路）"
    )
    ap.add_argument(
        "--npz",
        default=None,
        help="建筑 sample_*.npz（32³ 调色板体素）；--list 时可省略",
    )
    ap.add_argument(
        "--template",
        default="auto",
        help="模板 id，或 auto / auto:door / auto:io / auto:clock（默认 auto→杠杆灯）",
    )
    ap.add_argument("--out-dir", default=None, help="输出目录（默认 outputs/design/rs_paste_<ts>）")
    ap.add_argument(
        "--origin",
        default=None,
        help="手动原点 x,y,z（省略则室内楼板启发式）",
    )
    ap.add_argument(
        "--collision",
        default="air_only",
        choices=("air_only", "overwrite"),
        help="air_only=只写入空气（默认，不凿墙）；overwrite=覆盖 bbox 内方块",
    )
    ap.add_argument(
        "--near-door",
        action="store_true",
        help="强制优先靠门放置",
    )
    ap.add_argument(
        "--no-litematic",
        action="store_true",
        help="不写带 Properties 的合并 litematic",
    )
    ap.add_argument("--export-name", default=None, help="输出 litematic 文件名（无后缀）")
    ap.add_argument(
        "--companion",
        action="store_true",
        help="额外导出到 companion schematics（不删其它投影）",
    )
    ap.add_argument(
        "--companion-name",
        default=None,
        help="companion 文件中文名（默认 欧式_红石门控 / 建筑_红石粘贴）",
    )
    ap.add_argument("--list", action="store_true", help="列出模板后退出")
    args = ap.parse_args()

    if args.list:
        bootstrap_templates()
        for t in load_all_templates():
            print("%s\t%s" % (t["id"], t.get("label_zh")))
        return

    if not args.npz:
        raise SystemExit("--npz is required unless --list")

    origin = None
    if args.origin:
        parts = [int(x.strip()) for x in args.origin.split(",")]
        if len(parts) != 3:
            raise SystemExit("--origin needs x,y,z")
        origin = (parts[0], parts[1], parts[2])

    prefer = True if args.near_door else None
    summary = paste_redstone_into_design(
        args.npz,
        template_id=args.template,
        out_dir=args.out_dir,
        origin=origin,
        collision_mode=args.collision,
        prefer_near_door=prefer,
        export_litematic=not args.no_litematic,
        export_name=args.export_name,
        companion_export=bool(args.companion),
        companion_name=args.companion_name,
    )
    print("out_dir=", summary.get("out_dir"))
    print("template=", summary.get("template_id"), summary.get("label_zh"))
    print("origin=", summary.get("origin"))
    print(
        "placed=",
        (summary.get("paste") or {}).get("placed"),
        "skipped_solid=",
        (summary.get("paste") or {}).get("skipped_solid"),
    )
    sb = summary.get("structure_before") or {}
    sa = summary.get("structure_after") or {}
    print("structure_ok before/after=", sb.get("ok"), sa.get("ok"))
    print("litematic=", summary.get("litematic"))
    print("report=", summary.get("report"))
    if summary.get("companion"):
        print("companion=", json.dumps(summary["companion"], ensure_ascii=False))


if __name__ == "__main__":
    main()