# -*- coding: utf-8 -*-
"""Supplement fetch for weak styles: styles-only, no difficulty, more pages."""
from __future__ import annotations
import json, sys, time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts._fetch_style_houses_curated import (
    CAPS, _is_house, _style_of, _edge, _override_feature_style, _now,
)
from src.data.mcblock_api import list_buildings, get_building, download_projection, save_manifest
from src.app.reference_features import extract_reference_features, INDEX_DIR_DEFAULT

WEAK = ["chinese", "industrial", "rustic", "european", "modern"]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "outputs/design/_tmp_supp"
OUT.mkdir(parents=True, exist_ok=True)
raw = ROOT / "data/raw/mcblock"
index_dir = ROOT / INDEX_DIR_DEFAULT
manifest_path = raw / "manifest.json"
existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
seen = {r.get("id") for r in existing if r.get("id")}
man_idx = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
indexed_ids = {it.get("id") for it in (man_idx.get("items") or [])}

added = Counter()
rejected = Counter()
new_rows = []
log = []

for style in WEAK:
    cap = 12
    print(f"=== supplement {style} cap={cap}", flush=True)
    for sort in ("recommended", "latest"):
        if added[style] >= cap:
            break
        try:
            items = list_buildings(
                limit=40, max_pages=4, sort=sort,
                styles=[style], difficulties=None,
                max_blocks=8000, max_width=96, max_depth=96,
                search_q=None, sleep_s=0.4,
            )
        except Exception as e:
            print(f"  FAIL {style} {sort}: {e}", flush=True)
            rejected[f"list_fail:{style}"] += 1
            continue
        print(f"  listed {len(items)} style={style} sort={sort}", flush=True)
        for it in items:
            if added[style] >= cap:
                break
            bid = it.get("id")
            if not bid or bid in seen:
                rejected["seen"] += 1
                continue
            if _edge(it) > 96 or int(it.get("blockCount") or 0) > 8000:
                rejected["too_large"] += 1
                continue
            ok, reason = _is_house(it)
            if not ok:
                rejected[reason] += 1
                continue
            got = _style_of(it)
            raw_styles = [str(x).lower() for x in (it.get("styles") or [])]
            if got != style and style not in raw_styles:
                rejected[f"style_mismatch:{got}"] += 1
                continue
            try:
                detail = get_building(bid)
                time.sleep(0.4)
            except Exception as e:
                rejected["detail_fail"] += 1
                continue
            ok2, reason2 = _is_house(it, detail)
            if not ok2:
                rejected[reason2] += 1
                continue
            try:
                path = download_projection(detail, raw)
                time.sleep(0.35)
            except Exception as e:
                rejected["download_fail"] += 1
                continue
            if path is None:
                rejected["no_projection"] += 1
                continue
            row = {
                "id": bid,
                "name": detail.get("name") or it.get("name"),
                "tags": detail.get("tags") or it.get("tags"),
                "styles": it.get("styles") or detail.get("styles"),
                "difficulty": detail.get("difficulty") or it.get("difficulty"),
                "primaryType": it.get("primaryType") or detail.get("primaryType"),
                "width": detail.get("width") or it.get("width"),
                "height": detail.get("height") or it.get("height"),
                "depth": detail.get("depth") or it.get("depth"),
                "blockCount": detail.get("blockCount") or it.get("blockCount"),
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "curated_style_house": True,
                "keep_reason": reason2,
                "target_style": style,
                "fetched_at": _now(),
                "supplement_no_diff": True,
            }
            existing.append(row)
            seen.add(bid)
            new_rows.append(row)
            added[style] += 1
            print(f"  + {style} {row.get('name')} [{reason2}]", flush=True)

save_manifest(existing, manifest_path)

# ingest + embed
ingested = []
for r in new_rows:
    style = r["target_style"]
    path = ROOT / r["file"]
    try:
        feat = extract_reference_features(
            path, skeleton_size=32, index_dir=index_dir, write=True, embed_block2vec=True,
        )
        fid = feat["id"]
        _override_feature_style(fid, style, "flat", index_dir)
        ingested.append({"id": fid, "style": style, "name": r.get("name")})
        print(f"ingest OK {style} {fid}", flush=True)
    except Exception as e:
        print(f"ingest FAIL {path.name}: {e}", flush=True)

rep = {
    "added_by_style": dict(added),
    "rejected": dict(rejected.most_common(30)),
    "new_rows": len(new_rows),
    "ingested": ingested,
}
(OUT / "supplement_weak.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
print("DONE", rep["added_by_style"], "ingested", len(ingested))
