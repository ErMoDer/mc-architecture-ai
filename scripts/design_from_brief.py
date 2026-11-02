"""无 UI：截图 + 文字 → DesignSpec → 条件生成。

示例：
  python scripts/design_from_brief.py --text "雪山旁的中世纪石堡" --image shot.png
  python scripts/design_from_brief.py --text "海边现代玻璃别墅" --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.design_brief import (
    format_spec_for_ui,
    generate_from_design,
    infer_design_spec,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="MC design from screenshot + text brief")
    parser.add_argument("--text", "-t", default="", help="自然语言要求（中文可）")
    parser.add_argument("--image", "-i", default=None, help="截图 PNG/JPG 路径")
    parser.add_argument("--num", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--checkpoint", default=None, help="默认 checkpoints/cond_last.pt")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--style", default=None, help="覆盖推断的 style")
    parser.add_argument("--terrain", default=None, help="覆盖推断的 terrain")
    parser.add_argument("--dry-run", action="store_true", help="只推断不生成")
    parser.add_argument("--no-api", action="store_true", help="强制启发式，不调 API")
    parser.add_argument(
        "--strategy",
        default="similar_scaffold",
        choices=("similar_scaffold", "rule_scaffold", "vae_look"),
        help="generation strategy (default similar_scaffold)",
    )
    parser.add_argument(
        "--vae-fill",
        action="store_true",
        help="similar_scaffold only: sparse VAE materials inside scaffold",
    )
    parser.add_argument("--json", action="store_true", help="打印 DesignSpec JSON")
    args = parser.parse_args()

    spec = infer_design_spec(
        text_brief=args.text,
        image_path=args.image,
        prefer_api=not args.no_api,
    )
    if args.style:
        spec.style = args.style.strip().lower()
    if args.terrain:
        spec.terrain = args.terrain.strip().lower()

    if args.json:
        print(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_spec_for_ui(spec))
        print()

    if args.dry_run:
        print("[dry-run] 跳过生成")
        return

    results = generate_from_design(
        spec,
        num=args.num,
        temperature=args.temperature,
        checkpoint=args.checkpoint,
        out_dir=args.out_dir,
        strategy=args.strategy,
        vae_fill=bool(args.vae_fill),
    )
    for r in results:
        print(
            f"ok {r['npz_path'].name} non_air={r['non_air']} "
            f"style={r.get('style')} terrain={r.get('terrain')}"
        )


if __name__ == "__main__":
    main()
