# -*- coding: utf-8 -*-
"""Phase 4 CLI: 红石原理模板匹配与粘贴（非 VAE 发明）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.redstone_templates import (
    TEMPLATES_DIR,
    bootstrap_templates,
    load_all_templates,
    match_templates_to_analyze,
    replicate_redstone_from_litematic,
)
from src.app.schematic_analyze import analyze_litematic


def cmd_bootstrap(args: argparse.Namespace) -> None:
    root = bootstrap_templates(force=bool(args.force))
    tpls = load_all_templates()
    print("templates_dir=", root)
    print("count=", len(tpls))
    for t in tpls:
        print(" -", t["id"], "matches=", t.get("matches"), "|", t.get("label_zh"))


def cmd_list(args: argparse.Namespace) -> None:
    bootstrap_templates()
    for t in load_all_templates():
        print("%s  %s  matches=%s" % (t["id"], t.get("label_zh"), ",".join(t.get("matches") or [])))


def cmd_match(args: argparse.Namespace) -> None:
    bootstrap_templates()
    analyze = analyze_litematic(args.litematic)
    matches = match_templates_to_analyze(analyze)
    print("reference patterns → templates:")
    if not matches:
        print("  (none)")
    for m in matches:
        print(
            "  %s (%s) → %s [%s] score=%.2f"
            % (m.pattern_id, m.pattern_confidence, m.template_id, m.template_label, m.score)
        )


def cmd_replicate(args: argparse.Namespace) -> None:
    summary = replicate_redstone_from_litematic(
        args.litematic,
        out_dir=args.out_dir,
        max_templates=int(args.max_templates),
    )
    print("litematic=", summary.get("litematic"))
    print("report=", summary.get("report"))
    print("matches=")
    for m in summary.get("matches") or []:
        print(" ", m.get("pattern_id"), "→", m.get("template_id"), "score=", m.get("score"))


def main() -> None:
    ap = argparse.ArgumentParser(description="红石模板库：匹配 D9 模式并粘贴原理骨架")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p0 = sub.add_parser("bootstrap", help="写出/刷新 data/redstone_templates")
    p0.add_argument("--force", action="store_true")
    p0.set_defaults(func=cmd_bootstrap)

    p1 = sub.add_parser("list", help="列出模板")
    p1.set_defaults(func=cmd_list)

    p2 = sub.add_parser("match", help="只分析匹配，不写 schematic")
    p2.add_argument("litematic")
    p2.set_defaults(func=cmd_match)

    p3 = sub.add_parser("replicate", help="分析→匹配→粘贴 litematic + 中文报告")
    p3.add_argument("litematic")
    p3.add_argument("--out-dir", default=None)
    p3.add_argument("--max-templates", type=int, default=8)
    p3.set_defaults(func=cmd_replicate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()