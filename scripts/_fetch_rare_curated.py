# -*- coding: utf-8 -*-
"""Curated scarce-terrain MCBlock top-up: STRICT queries + mountain strong filter."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.labels import _strong_mountain_evidence
from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest

_QPATHS = [
    Path(__file__).with_name("_fetch_rare_curated_queries.json"),
    ROOT / "outputs" / "rare_curated_queries.json",
]


def _load_queries() -> dict[str, list[str]]:
    for p in _QPATHS:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    raise SystemExit("missing queries json next to script")


DEFAULT_CAPS = {"mountain": 25, "nether": 22, "desert": 22, "snow": 22}


def _name_blobs(it: dict, detail: dict | None) -> tuple[str, str | None, list[str]]:
    display = None
    tags: list[str] = []
    stem_bits = []
    for src in (it, detail or {}):
        for k in ("name", "displayName", "title", "buildingName"):
            v = src.get(k)
            if v:
                stem_bits.append(str(v))
                if display is None:
                    display = str(v)
        t = src.get("tags") or src.get("tagList") or []
        if isinstance(t, list):
            tags.extend(str(x) for x in t)
        elif isinstance(t, str):
            tags.append(t)
    return " ".join(stem_bits), display, tags


def main() -> None:
    STRICT_QUERIES = _load_queries()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw/mcblock")
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--max-blocks", type=int, default=8000)
    ap.add_argument("--max-edge", type=int, default=96)
    ap.add_argument("--sleep", type=float, default=0.45)
    ap.add_argument("--terrains", default="mountain,nether,desert,snow")
    ap.add_argument("--sort", default="recommended")
    ap.add_argument("--also-latest", action="store_true")
    args = ap.parse_args()

    want = [t.strip() for t in args.terrains.split(",") if t.strip()]
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir = ROOT / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"

    existing: list[dict] = []
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_id = {r.get("id"): r for r in existing if r.get("id")}
    print(f"existing manifest={len(existing)}", flush=True)
    print("queries:", {k: STRICT_QUERIES[k] for k in want if k in STRICT_QUERIES}, flush=True)

    caps = dict(DEFAULT_CAPS)
    new_by_terrain: Counter[str] = Counter()
    rejected_mountain: list[dict] = []
    candidates: list[tuple[dict, str, str]] = []
    seen: set[str] = set()
    sorts = [args.sort]
    if args.also_latest and "latest" not in sorts:
        sorts.append("latest")

    for terrain in want:
        for query in STRICT_QUERIES.get(terrain, []):
            for sort in sorts:
                print(f"search t={terrain} q={query!r} sort={sort}", flush=True)
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
                    if not bid or bid in seen or bid in by_id:
                        continue
                    edge = max(
                        int(it.get("width") or 0),
                        int(it.get("height") or 0),
                        int(it.get("depth") or 0),
                    )
                    if edge > args.max_edge or int(it.get("blockCount") or 0) > args.max_blocks:
                        continue
                    seen.add(bid)
                    candidates.append((it, terrain, query))
                    kept += 1
                print(f"  listed={len(items)} new_ids={kept}", flush=True)
                time.sleep(args.sleep)

    print(f"candidates={len(candidates)}", flush=True)
    ok = skip = fail = 0
    new_rows: list[dict] = []

    for i, (it, terrain, query) in enumerate(candidates, 1):
        if new_by_terrain[terrain] >= caps.get(terrain, 15):
            skip += 1
            continue
        bid = it["id"]
        try:
            detail = get_building(bid)
        except Exception as e:
            print(f"[{i}] detail FAIL {bid}: {e}", flush=True)
            fail += 1
            continue
        stem, display, tags = _name_blobs(it, detail if isinstance(detail, dict) else {})
        if terrain == "mountain":
            if not _strong_mountain_evidence(stem, display, tags):
                rejected_mountain.append(
                    {
                        "id": bid,
                        "name": display or stem,
                        "query": query,
                        "tags": tags[:12],
                    }
                )
                print(f"[{i}] REJECT mountain weak: {display or stem!r}", flush=True)
                skip += 1
                continue
        try:
            building = dict(detail) if isinstance(detail, dict) else dict(it)
            building.setdefault("id", bid)
            building.setdefault("name", display or it.get("name") or bid)
            path = download_projection(building, out_dir)
        except Exception as e:
            print(f"[{i}] DL FAIL {bid}: {e}", flush=True)
            fail += 1
            continue
        if path is None:
            skip += 1
            continue
        try:
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
        except Exception:
            rel = str(path)
        row = {
            "id": bid,
            "name": display or it.get("name"),
            "file": rel,
            "rare_terrain_hits": [terrain],
            "search_q": query,
            "curated": True,
            "width": it.get("width") or building.get("width"),
            "height": it.get("height") or building.get("height"),
            "depth": it.get("depth") or building.get("depth"),
            "blockCount": it.get("blockCount") or building.get("blockCount"),
        }
        by_id[bid] = row
        new_rows.append(row)
        new_by_terrain[terrain] += 1
        ok += 1
        print(f"[{i}] OK {row.get('name')} t={terrain} q={query!r}", flush=True)
        time.sleep(args.sleep)

    no_id = [r for r in existing if not r.get("id")]
    merged = no_id + list(by_id.values())
    save_manifest(merged, manifest_path)

    summary = {
        "new_ok": ok,
        "skip": skip,
        "fail": fail,
        "new_by_terrain": dict(new_by_terrain),
        "rejected_mountain_n": len(rejected_mountain),
        "rejected_mountain_sample": rejected_mountain[:30],
        "new_names": [
            {
                "terrain": (r.get("rare_terrain_hits") or [None])[0],
                "name": r.get("name"),
                "q": r.get("search_q"),
            }
            for r in new_rows
        ],
        "manifest_total": len(merged),
        "queries": {k: STRICT_QUERIES[k] for k in want if k in STRICT_QUERIES},
        "caps": caps,
        "max_edge": args.max_edge,
        "max_blocks": args.max_blocks,
    }
    (report_dir / "fetch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("SUMMARY", json.dumps(summary["new_by_terrain"], ensure_ascii=False), "ok", ok, flush=True)


if __name__ == "__main__":
    main()
