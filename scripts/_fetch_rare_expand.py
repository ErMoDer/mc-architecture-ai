# -*- coding: utf-8 -*-
"""One-shot expand rare MCBlock fetch: EN+CN queries, advanced, larger edge."""
from __future__ import annotations
import json, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest

SEARCH_QUERIES = {
    "mountain": [
        "\u5c71", "mountain", "cliff", "peak", "\u60ac\u5d16", "\u5c71\u5e84", "\u5c71\u6d1e",
        "\u5c71\u8170", "\u5d16\u58c1", "fortress", "\u8981\u585e", "\u9ad8\u5730", "slope",
        "\u5c71\u9876", "\u5c71\u5be8", "\u6d1e\u7a9f", "castle mountain",
    ],
    "nether": [
        "\u4e0b\u754c", "\u5730\u72f1", "nether", "basalt", "crimson", "warped",
        "\u7194\u5ca9", "\u5730\u72f1\u5821", "nether fortress", "soul",
    ],
    "desert": [
        "\u6c99\u6f20", "desert", "\u7eff\u6d32", "oasis", "pyramid", "\u91d1\u5b57\u5854",
        "\u6c99\u4e18", "mesa", "\u6c99\u57ce", "sandstone",
    ],
    "snow": [
        "\u96ea", "snow", "ice", "\u51b0", "frost", "\u96ea\u5c4b", "\u51b0\u5c4b",
        "igloo", "\u96ea\u539f", "\u51b0\u539f", "winter", "\u51ac",
    ],
}

def main():
    out_dir = ROOT / "data/raw/mcblock"
    manifest_path = out_dir / "manifest.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    by_id = {r.get("id"): r for r in existing if r.get("id")}
    print(f"existing={len(by_id)}", flush=True)

    want = ["mountain", "nether", "desert", "snow"]
    sorts = ["recommended", "latest"]
    diffs = ["beginner", "intermediate", "advanced"]
    candidates = []
    seen = set()

    for terrain in want:
        for query in SEARCH_QUERIES[terrain]:
            for sort in sorts:
                for diff in diffs:
                    print(f"search t={terrain} q={query!r} sort={sort} diff={diff}", flush=True)
                    try:
                        items = list_buildings(
                            limit=40, max_pages=3, sort=sort,
                            difficulties=[diff],
                            max_blocks=12000, max_width=128, max_depth=128,
                            search_q=query, sleep_s=0.4,
                        )
                    except Exception as e:
                        print(f"  FAIL list: {e}", flush=True)
                        continue
                    kept = 0
                    for it in items:
                        bid = it.get("id")
                        if not bid or bid in seen:
                            continue
                        edge = max(int(it.get("width") or 0), int(it.get("height") or 0), int(it.get("depth") or 0))
                        if edge > 128 or int(it.get("blockCount") or 0) > 12000:
                            continue
                        seen.add(bid)
                        candidates.append((it, [terrain], query))
                        kept += 1
                    print(f"  listed={len(items)} new_ids={kept}", flush=True)
                    time.sleep(0.35)

    print(f"unique candidates={len(candidates)}", flush=True)
    print("cand_by_terrain", dict(Counter(t for _, hs, _ in candidates for t in hs)), flush=True)

    ok = skip = fail = 0
    new_rows = []
    for i, (it, hits, query) in enumerate(candidates, 1):
        bid = it["id"]
        if bid in by_id:
            row = by_id[bid]
            old = set(row.get("rare_terrain_hits") or [])
            merged = sorted(old | set(hits))
            if merged != sorted(old):
                row["rare_terrain_hits"] = merged
            skip += 1
            continue
        try:
            detail = get_building(bid)
            time.sleep(0.4)
            tags = detail.get("tags")
            if isinstance(tags, str):
                try: tags = json.loads(tags)
                except Exception: tags = [tags]
            path = download_projection(detail, out_dir)
            time.sleep(0.4)
            if path is None:
                print(f"[{i}] SKIP no projection {it.get('name')}", flush=True)
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
            print(f"[{i}/{len(candidates)}] OK {row['name']} hits={hits} -> {path.name}", flush=True)
        except Exception as e:
            fail += 1
            print(f"[{i}] FAIL {it.get('name')}: {e}", flush=True)

    merged = list(by_id.values())
    save_manifest(merged, manifest_path)
    hit_c = Counter()
    for r in merged:
        for h in r.get("rare_terrain_hits") or []:
            hit_c[h] += 1
    print(f"done new_ok={ok} skip={skip} fail={fail} total={len(merged)} rare_hits={dict(hit_c)}", flush=True)
    Path("outputs/fetch_rare_20261019/expand_summary.json").write_text(
        json.dumps({"new_ok": ok, "skip": skip, "fail": fail, "total": len(merged), "rare_hits": dict(hit_c), "new_names": [r.get("name") for r in new_rows]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

if __name__ == "__main__":
    main()
