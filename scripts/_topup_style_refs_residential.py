# -*- coding: utf-8 -*-
"""Top-up thin residential style refs (MCBlock style-only discovery) + no VAE.
Avoids difficulty+q combos that 400 the discovery API.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest
from src.app.reference_features import extract_reference_features, INDEX_DIR_DEFAULT
from src.data.labels import pick_style

TZ = timezone(timedelta(hours=8))

HOUSE_KW = [
    "house", "home", "cottage", "villa", "cabin", "residence", "townhouse",
    "mansion", "bungalow", "farmhouse", "manor", "dwelling", "apartment",
    "condo", "loft", "chalet", "barn", "siheyuan",
    "\u4f4f\u5b85", "\u5c0f\u5c4b", "\u522b\u5885", "\u6c11\u5c45", "\u519c\u820d",
    "\u6728\u5c4b", "\u77f3\u5c4b", "\u7530\u56ed", "\u4e61\u6751", "\u5b85",
]
REJECT_KW = [
    "pyramid", "challenge", "mcbuildchallenge", "xp farm", "xpfarm", "duper",
    "kelp farm", "statue", "sculpture", "arena", "parkour", "railgun",
    "nether portal", "vending", "stash", "item sorter",
]
REJECT_PRIMARY = {
    "vehicle_transport", "sculpture_figure", "plant_nature",
    "landscape_component", "interior_sample",
}
CAPS = {"rustic": 12, "european": 10, "modern": 10, "western": 6}


def _blob(it, detail=None) -> str:
    parts = []
    for src in (it, detail or {}):
        for k in ("name", "displayName", "title", "buildingName", "description"):
            v = src.get(k)
            if v:
                parts.append(str(v))
        tags = src.get("tags") or src.get("tagList") or []
        if isinstance(tags, list):
            parts.extend(str(t) for t in tags)
        pt = src.get("primaryType")
        if pt:
            parts.append(str(pt))
    return " ".join(parts).lower()


def is_house(it, detail=None):
    pt = (it.get("primaryType") or (detail or {}).get("primaryType") or "").strip()
    if pt in REJECT_PRIMARY:
        return False, f"reject_primary:{pt}"
    blob = _blob(it, detail)
    for kw in REJECT_KW:
        if kw in blob:
            return False, f"reject_kw:{kw}"
    if pt == "residential":
        return True, "primary:residential"
    for kw in HOUSE_KW:
        if kw.lower() in blob or kw in blob:
            return True, f"house_kw:{kw}"
    return False, "no_house_evidence"


def _override_feature_style(fid: str, style: str, terrain: str, index_dir: Path) -> None:
    feat_path = index_dir / f"{fid}.json"
    if feat_path.exists():
        data = json.loads(feat_path.read_text(encoding="utf-8"))
        data["mapped_style"] = style
        data["mapped_terrain"] = terrain
        feat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    man_path = index_dir / "index.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    for it in man.get("items") or []:
        if it.get("id") == fid:
            it["mapped_style"] = style
            it["mapped_terrain"] = terrain
            break
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")


def load_manifest(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--styles", default="rustic,european,modern")
    ap.add_argument("--max-pages", type=int, default=4)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--sleep", type=float, default=0.55)
    ap.add_argument("--embed-block2vec", action="store_true")
    ap.add_argument("--max-edge", type=int, default=128)
    ap.add_argument("--max-blocks", type=int, default=16000)
    args = ap.parse_args()

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    out_dir = ROOT / "data" / "raw" / "mcblock"
    out_dir.mkdir(parents=True, exist_ok=True)
    man_path = out_dir / "manifest.json"
    index_dir = ROOT / INDEX_DIR_DEFAULT

    idx = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    existing_ids = {it.get("id") for it in (idx.get("items") or [])}
    man = load_manifest(man_path)
    known_ids = {it.get("id") for it in man if it.get("id")}
    # also stems
    known_files = {Path(it.get("file") or "").stem for it in man}

    styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    added_by_style = Counter()
    fetch_rows = []
    skipped = Counter()
    failed = []

    for style in styles:
        cap = CAPS.get(style, 8)
        for sort in ("recommended", "latest"):
            if added_by_style[style] >= cap:
                break
            print(f"discover style={style} sort={sort} (no q/diff)", flush=True)
            try:
                items = list_buildings(
                    limit=args.limit,
                    max_pages=args.max_pages,
                    sort=sort,
                    styles=[style],
                    difficulties=None,
                    max_blocks=None,
                    max_width=None,
                    max_depth=None,
                    search_q=None,
                    sleep_s=args.sleep,
                )
            except Exception as e:
                print(f"  FAIL list: {e}", flush=True)
                failed.append({"style": style, "sort": sort, "error": str(e)})
                time.sleep(1.5)
                continue
            print(f"  got {len(items)} raw", flush=True)
            for it in items:
                if added_by_style[style] >= cap:
                    break
                bid = it.get("id")
                if not bid:
                    continue
                if bid in known_ids:
                    skipped["already_manifest"] += 1
                    continue
                # size gate
                w, h, d = it.get("width") or 0, it.get("height") or 0, it.get("depth") or 0
                bc = it.get("blockCount") or 0
                if max(w, h, d) > args.max_edge or (bc and bc > args.max_blocks):
                    skipped["too_big"] += 1
                    continue
                ok, reason = is_house(it)
                if not ok:
                    # detail fetch for borderline
                    try:
                        detail = get_building(bid)
                        time.sleep(args.sleep)
                    except Exception:
                        skipped[f"reject:{reason}"] += 1
                        continue
                    ok, reason = is_house(it, detail)
                    if not ok:
                        skipped[f"reject:{reason}"] += 1
                        continue
                    it = {**it, **{k: detail.get(k) for k in ("primaryType", "styles", "tags", "name", "description") if detail.get(k) is not None}}
                # map western stays western; rustic/euro/modern force target
                target = style
                try:
                    dest = download_projection(it, out_dir)
                    time.sleep(args.sleep)
                except Exception as e:
                    failed.append({"id": bid, "error": f"dl:{e}"})
                    print(f"  DL FAIL {it.get('name')}: {e}", flush=True)
                    continue
                if not dest or not dest.exists():
                    failed.append({"id": bid, "error": "no_file"})
                    continue
                row = {
                    "id": bid,
                    "name": it.get("name"),
                    "styles": it.get("styles") or [style],
                    "primaryType": it.get("primaryType"),
                    "width": w, "height": h, "depth": d,
                    "blockCount": bc,
                    "file": str(dest.relative_to(ROOT)).replace("/", "\\"),
                    "projectionFileUrl": it.get("projectionFileUrl") or it.get("downloadUrl"),
                    "_picked_style": target,
                    "_keep_reason": reason,
                    "_topup": True,
                }
                man.append(row)
                known_ids.add(bid)
                fetch_rows.append(row)
                # ingest
                try:
                    feat = extract_reference_features(
                        dest, skeleton_size=32, index_dir=index_dir, write=True,
                        embed_block2vec=bool(args.embed_block2vec),
                    )
                    fid = feat["id"]
                    _override_feature_style(fid, target, "flat", index_dir)
                    existing_ids.add(fid)
                    added_by_style[target] += 1
                    print(f"  ADD {target} {fid} ({it.get('name')}) [{reason}]", flush=True)
                except Exception as e:
                    failed.append({"id": bid, "error": f"ingest:{e}"})
                    print(f"  INGEST FAIL {dest.name}: {e}", flush=True)

    save_manifest(man, man_path)

    # also ingest the 1-2 known missing residential from manifest
    for it in man:
        styles_l = it.get("styles") or []
        for st in styles:
            if st not in styles_l:
                continue
            ok, reason = is_house(it)
            if not ok:
                continue
            fp = it.get("file")
            if not fp:
                continue
            path = ROOT / fp
            if not path.exists():
                continue
            fid = path.stem
            if fid in existing_ids:
                continue
            if added_by_style[st] >= CAPS.get(st, 8) + 3:
                continue
            try:
                feat = extract_reference_features(
                    path, skeleton_size=32, index_dir=index_dir, write=True,
                    embed_block2vec=bool(args.embed_block2vec),
                )
                fid = feat["id"]
                _override_feature_style(fid, st, "flat", index_dir)
                existing_ids.add(fid)
                added_by_style[st] += 1
                fetch_rows.append({**it, "_picked_style": st, "_keep_reason": f"manifest_missing:{reason}"})
                print(f"  REINGEST {st} {fid}", flush=True)
            except Exception as e:
                failed.append({"file": str(path), "error": str(e)})

    # after counts
    idx2 = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    items = idx2.get("items") or []
    c = Counter(it.get("mapped_style") or "unknown" for it in items)
    mc = Counter(
        it.get("mapped_style") or "unknown"
        for it in items
        if "mcblock" in str(it.get("source_path") or "").replace("\\", "/").lower()
    )
    report = {
        "at": datetime.now(TZ).isoformat(timespec="seconds"),
        "fetch_new_rows": len(fetch_rows),
        "fetch_added_by_style": dict(added_by_style),
        "skipped": dict(skipped),
        "failed": failed[:40],
        "feature_index_n": len(items),
        "mapped_style": dict(c.most_common()),
        "mcblock_mapped_style": dict(mc.most_common()),
        "rows": [
            {"id": r.get("id"), "name": r.get("name"), "style": r.get("_picked_style"), "reason": r.get("_keep_reason")}
            for r in fetch_rows
        ],
    }
    (report_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("fetch_new_rows", "fetch_added_by_style", "feature_index_n", "mcblock_mapped_style")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
