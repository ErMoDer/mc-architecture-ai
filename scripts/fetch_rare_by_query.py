# -*- coding: utf-8 -*-
"""Keyword-search MCBlock for rare terrains; merge into manifest without wiping."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest

# Unicode escapes so PowerShell re-encoding cannot corrupt CJK.
SEARCH_QUERIES: dict[str, list[str]] = {
    "snow": ["\u96ea", "\u51b0", "\u96ea\u5c4b", "\u96ea\u539f", "\u51b0\u5c4b", "\u51b0\u539f"],
    "water": [
        "\u7802\u5934", "\u6865", "\u706f\u5854", "\u6e2f\u53e3", "\u8239",
        "\u6c34\u4e0a", "\u6e14", "\u6e2f\u6e7e", "\u6728\u6865",
    ],
    "mountain": [
        "\u5c71\u5e84", "\u60ac\u5d16", "\u5c71\u6d1e", "\u5c71\u8170", "\u5c71\u9876",
        "\u6d1e\u7a9f", "\u5c71\u5be8", "\u5d16",
    ],
    "desert": ["\u6c99\u6f20", "\u7eff\u6d32", "\u6c99\u4e18"],
    "nether": ["\u4e0b\u754c", "\u5730\u72f1"],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/raw/mcblock")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--max-blocks", type=int, default=8000)
    parser.add_argument("--max-edge", type=int, default=96)
    parser.add_argument("--sleep", type=float, default=0.45)
    parser.add_argument("--terrains", default="snow,water,mountain,desert,nether")
    parser.add_argument("--sort", default="recommended")
    parser.add_argument("--also-latest", action="store_true")
    args = parser.parse_args()

    want = {t.strip() for t in args.terrains.split(",") if t.strip()}
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"

    existing: list[dict] = []
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_id = {r.get("id"): r for r in existing if r.get("id")}
    print(f"existing manifest={len(existing)} ids={len(by_id)}", flush=True)
    print("queries:", {k: SEARCH_QUERIES[k] for k in sorted(want)}, flush=True)

    sorts = [args.sort]
    if args.also_latest and "latest" not in sorts:
        sorts.append("latest")

    candidates: list[tuple[dict, list[str], str]] = []
    seen_cand: set[str] = set()

    for terrain in sorted(want):
        for query in SEARCH_QUERIES.get(terrain, []):
            for sort in sorts:
                print(f"search terrain={terrain} q={query!r} sort={sort}", flush=True)
                try:
                    items = list_buildings(
                        limit=args.limit,
                        max_pages=args.max_pages,
                        sort=sort,
                        difficulties=["beginner", "intermediate"],
                        max_blocks=args.max_blocks,
                        max_width=args.max_edge,
                        max_depth=args.max_edge,
                        search_q=query,
                        sleep_s=args.sleep,
                    )
                except Exception as e:
                    print(f"  FAIL list: {e}", flush=True)
                    continue
                kept = 0
                for it in items:
                    bid = it.get("id")
                    if not bid or bid in seen_cand:
                        continue
                    edge = max(
                        int(it.get("width") or 0),
                        int(it.get("height") or 0),
                        int(it.get("depth") or 0),
                    )
                    if edge > args.max_edge or int(it.get("blockCount") or 0) > args.max_blocks:
                        continue
                    seen_cand.add(bid)
                    candidates.append((it, [terrain], query))
                    kept += 1
                print(f"  listed={len(items)} kept_new_ids={kept}", flush=True)
                time.sleep(args.sleep)

    print(f"unique candidates={len(candidates)}", flush=True)
    print("cand_by_terrain", dict(Counter(t for _, hs, _ in candidates for t in hs)), flush=True)

    new_rows = []
    ok = skip_have = fail = 0
    for i, (it, hits, query) in enumerate(candidates, 1):
        bid = it["id"]
        if bid in by_id:
            row = by_id[bid]
            old_hits = set(row.get("rare_terrain_hits") or [])
            merged_hits = sorted(old_hits | set(hits))
            if merged_hits != sorted(old_hits):
                row["rare_terrain_hits"] = merged_hits
            skip_have += 1
            continue
        try:
            detail = get_building(bid)
            time.sleep(args.sleep)
            tags = detail.get("tags")
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = [tags]
            path = download_projection(detail, out_dir)
            time.sleep(args.sleep)
            if path is None:
                print(f"[{i}/{len(candidates)}] SKIP no projection {it.get('name')}", flush=True)
                fail += 1
                continue
            row = {
                "id": bid,
                "name": detail.get("name") or it.get("name"),
                "tags": tags,
                "styles": it.get("styles"),
                "difficulty": detail.get("difficulty") or it.get("difficulty"),
                "primaryType": it.get("primaryType"),
                "width": detail.get("width") or it.get("width"),
                "height": detail.get("height") or it.get("height"),
                "depth": detail.get("depth") or it.get("depth"),
                "blockCount": detail.get("blockCount") or it.get("blockCount"),
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "projectionFileUrl": detail.get("projectionFileUrl"),
                "rare_terrain_hits": hits,
                "search_q": query,
            }
            by_id[bid] = row
            new_rows.append(row)
            ok += 1
            print(
                f"[{i}/{len(candidates)}] OK {row['name']} hits={hits} q={query!r} -> {path.name}",
                flush=True,
            )
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(candidates)}] FAIL {it.get('name')}: {e}", flush=True)

    merged = list(by_id.values())
    save_manifest(merged, manifest_path)
    hit_c = Counter()
    for r in merged:
        for h in r.get("rare_terrain_hits") or []:
            hit_c[h] += 1
    print(
        f"done: new_ok={ok} already_have={skip_have} fail={fail} "
        f"manifest_total={len(merged)} rare_hits={dict(hit_c)} -> {manifest_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
