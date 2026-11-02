"""从 MCBlock 建筑库拉取投影（.litematic），供路线 A 训练。

用法示例：
  python scripts/fetch_mcblock.py --max-pages 3 --max-blocks 3000 --max-edge 64
  python scripts/fetch_mcblock.py --styles medieval,chinese --difficulties beginner
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/raw/mcblock")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--max-blocks", type=int, default=4000)
    parser.add_argument("--max-edge", type=int, default=64, help="宽/高/深任一边上限")
    parser.add_argument("--styles", default="", help="逗号分隔，如 medieval,chinese,japanese")
    parser.add_argument("--difficulties", default="beginner,intermediate")
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    styles = [s for s in args.styles.split(",") if s] or None
    difficulties = [s for s in args.difficulties.split(",") if s] or None

    print("拉取列表…")
    items = list_buildings(
        limit=args.limit,
        max_pages=args.max_pages,
        styles=styles,
        difficulties=difficulties,
        max_blocks=args.max_blocks,
        max_width=args.max_edge,
        max_depth=args.max_edge,
        sleep_s=args.sleep,
    )
    # 本地再按高度过滤（discovery 未必支持 maxHeight）
    items = [
        it
        for it in items
        if max(int(it.get("width") or 0), int(it.get("height") or 0), int(it.get("depth") or 0))
        <= args.max_edge
        and int(it.get("blockCount") or 0) <= args.max_blocks
    ]
    print(f"候选 {len(items)} 座（已按尺寸/方块数过滤）")

    rows = []
    ok = 0
    for i, it in enumerate(items, 1):
        bid = it["id"]
        try:
            detail = get_building(bid)
            path = download_projection(detail, out_dir)
            time.sleep(args.sleep)
            if path is None:
                print(f"[{i}/{len(items)}] SKIP 无投影 {it.get('name')}")
                continue
            row = {
                "id": bid,
                "name": detail.get("name") or it.get("name"),
                "tags": detail.get("tags"),
                "styles": it.get("styles"),
                "difficulty": detail.get("difficulty") or it.get("difficulty"),
                "primaryType": it.get("primaryType"),
                "width": detail.get("width") or it.get("width"),
                "height": detail.get("height") or it.get("height"),
                "depth": detail.get("depth") or it.get("depth"),
                "blockCount": detail.get("blockCount") or it.get("blockCount"),
                "file": str(path.relative_to(ROOT)),
                "projectionFileUrl": detail.get("projectionFileUrl"),
            }
            # tags 可能是 JSON 字符串
            if isinstance(row["tags"], str):
                try:
                    row["tags"] = json.loads(row["tags"])
                except json.JSONDecodeError:
                    pass
            rows.append(row)
            ok += 1
            print(f"[{i}/{len(items)}] OK {row['name']} → {path.name}")
        except Exception as e:
            print(f"[{i}/{len(items)}] FAIL {it.get('name')}: {e}")

    manifest = out_dir / "manifest.json"
    # merge with existing so multi-style / rare runs do not wipe prior tags
    existing: list[dict] = []
    if manifest.exists():
        try:
            existing = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    by_id = {r.get("id"): r for r in existing if r.get("id")}
    for r in rows:
        if r.get("id"):
            by_id[r["id"]] = r
    merged = list(by_id.values())
    save_manifest(merged, manifest)
    print(f"完成：本次成功 {ok}/{len(items)}，清单合计 {len(merged)} -> {manifest}")
    print("下一步：python scripts/prepare_data.py --from-mcblock")


if __name__ == "__main__":
    main()
