# -*- coding: utf-8 -*-
"""Curated style-correct HOUSE fetch + feature_index ingest (MCBlock only). LOCAL_ONLY. No train."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.labels import pick_style
from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest
from src.app.reference_features import extract_reference_features, INDEX_DIR_DEFAULT

TARGET_STYLES = ["european", "medieval", "modern", "chinese", "japanese", "industrial", "rustic", "fantasy"]

STYLE_QUERIES = {
    "european": ["european house", "victorian house", "townhouse", "european villa", "georgian house", "row house", "french house", "german house"],
    "medieval": ["medieval house", "medieval cottage", "stone house", "timber house", "half timbered house", "castle house", "nordic house"],
    "modern": ["modern house", "modern villa", "apartment", "concrete house", "minimalist house", "contemporary house", "glass house"],
    "chinese": ["chinese house", "siheyuan", "chinese villa", "chinese courtyard", "chinese pavilion house", "中式建筑", "中式小屋", "四合院", "中式别墅"],
    "japanese": ["japanese house", "minka"],
    "industrial": ["industrial house", "warehouse loft", "brick factory house", "loft house", "industrial loft", "brick warehouse home"],
    "rustic": ["rustic house", "cabin", "log cabin", "farmhouse", "cottage", "chalet", "barn house", "mountain cabin", "田园", "农舍", "木屋", "乡村小屋"],
    "fantasy": ["fantasy house", "elf house", "wizard tower house", "fairy cottage", "mushroom house", "mage house", "奇幻", "精灵小屋", "魔法小屋"],
}

HOUSE_KW = [
    "house", "home", "cottage", "villa", "cabin", "residence", "townhouse",
    "mansion", "bungalow", "farmhouse", "manor", "dwelling", "apartment",
    "condo", "loft", "siheyuan",
]
# CJK house words as unicode escapes
HOUSE_KW += [
    "\u4f4f\u5b85", "\u5c0f\u5c4b", "\u522b\u5885", "\u6c11\u5c45", "\u6c11\u5bbf",
    "\u519c\u820d", "\u6728\u5c4b", "\u77f3\u5c4b", "\u5b85", "\u56db\u5408\u9662",
]

# rustic / fantasy residential extras
HOUSE_KW += [
    "cabin", "barn", "log cabin", "chalet",
    "\u7530\u56ed", "\u4e61\u6751", "\u6728\u5c4b", "\u519c\u820d",
    "elf", "wizard", "mage", "fairy", "mushroom house",
    "\u5947\u5e7b", "\u7cbe\u7075", "\u9b54\u6cd5",
]

REJECT_KW = [
    "pyramid", "challenge", "mcbuildchallenge", "buildchallenge",
    "xp farm", "xpfarm", "duper", "duping", "farm machine",
    "vending", "railgun", "portal room", "nether portal",
    "kelp farm", "super kelp", "stash", "converter",
    "statue", "sculpture", "decorative wall", "wall only",
    "arena", "minigame", "parkour", "spiral door", "pyramidbase",
    "dropper", "item sorter only",
]

REJECT_PRIMARY = {
    "vehicle_transport", "sculpture_figure", "plant_nature",
    "landscape_component", "interior_sample",
}

CAPS = {
    "european": 18, "medieval": 18, "modern": 18,
    "chinese": 20, "japanese": 12, "industrial": 18,
    "rustic": 18, "fantasy": 15,
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _blob(it, detail=None) -> str:
    parts = []
    for src in (it, detail or {}):
        for k in ("name", "displayName", "title", "buildingName"):
            v = src.get(k)
            if v:
                parts.append(str(v))
        tags = src.get("tags") or src.get("tagList") or []
        if isinstance(tags, list):
            parts.extend(str(t) for t in tags)
        elif isinstance(tags, str):
            parts.append(tags)
        pt = src.get("primaryType")
        if pt:
            parts.append(str(pt))
    return " ".join(parts).lower()


def _is_house(it, detail=None):
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


def _style_of(it, detail=None) -> str:
    styles = []
    for src in (it, detail or {}):
        s = src.get("styles") or []
        if isinstance(s, list):
            styles.extend(s)
        elif s:
            styles.append(s)
    return pick_style(styles)


def _edge(it) -> int:
    return max(int(it.get("width") or 0), int(it.get("height") or 0), int(it.get("depth") or 0))


def _override_feature_style(feat_id, style, terrain, index_dir: Path) -> None:
    feat_path = index_dir / f"{feat_id}.json"
    if not feat_path.exists():
        return
    feat = json.loads(feat_path.read_text(encoding="utf-8"))
    st = feat.setdefault("style", {})
    st["mapped_style"] = style
    if terrain:
        st["mapped_terrain"] = terrain
    try:
        from src.data.labels import load_vocab, resolve_style_id, resolve_terrain_id
        vocab = load_vocab(ROOT / "data" / "label_vocab.json")
        st["style_id"] = resolve_style_id(vocab, style)
        if terrain:
            st["terrain_id"] = resolve_terrain_id(vocab, terrain)
    except Exception:
        pass
    st["style_source"] = "mcblock_manifest_override"
    feat_path.write_text(json.dumps(feat, ensure_ascii=False, indent=2), encoding="utf-8")
    man_path = index_dir / "index.json"
    if man_path.exists():
        man = json.loads(man_path.read_text(encoding="utf-8"))
        for it in man.get("items") or []:
            if it.get("id") == feat_id:
                it["mapped_style"] = style
                if terrain:
                    it["mapped_terrain"] = terrain
        man["updated_at"] = _now()
        man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_new(args, report):
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else []
    by_id = {r.get("id"): r for r in existing if r.get("id")}
    print(f"existing manifest={len(existing)}", flush=True)

    want = [s.strip() for s in args.styles.split(",") if s.strip()]
    new_rows = []
    rejected = Counter()
    added_by_style = Counter()
    seen = set(by_id.keys())

    for style in want:
        cap = CAPS.get(style, 12)
        queries = list(STYLE_QUERIES.get(style, [style + " house"]))
        # MCBlock: styles=[rustic|fantasy] works; combining English search_q often returns empty.
        if style in ("rustic", "fantasy"):
            query_list = [None] + queries
        else:
            query_list = queries + [None]
        for query in query_list:
            if added_by_style[style] >= cap:
                break
            for sort in ("recommended", "latest"):
                if added_by_style[style] >= cap:
                    break
                print(f"search style={style} q={query!r} sort={sort}", flush=True)
                try:
                    items = list_buildings(
                        limit=args.limit, max_pages=args.max_pages, sort=sort,
                        styles=[style], difficulties=["beginner", "intermediate"],
                        max_blocks=args.max_blocks, max_width=args.max_edge,
                        max_depth=args.max_edge, search_q=query, sleep_s=args.sleep,
                    )
                except Exception as e:
                    print(f"  FAIL list: {e}", flush=True)
                    rejected[f"list_fail:{style}"] += 1
                    continue
                for it in items:
                    if added_by_style[style] >= cap:
                        break
                    bid = it.get("id")
                    if not bid or bid in seen:
                        continue
                    if _edge(it) > args.max_edge or int(it.get("blockCount") or 0) > args.max_blocks:
                        rejected["too_large"] += 1
                        continue
                    ok, reason = _is_house(it)
                    if not ok:
                        rejected[reason] += 1
                        continue
                    got_style = _style_of(it)
                    if got_style != style:
                        raw = [str(x).lower() for x in (it.get("styles") or [])]
                        if style not in raw:
                            rejected[f"style_mismatch:{got_style}"] += 1
                            continue
                    try:
                        detail = get_building(bid)
                        time.sleep(args.sleep)
                    except Exception as e:
                        rejected["detail_fail"] += 1
                        print(f"  detail fail {bid}: {e}", flush=True)
                        continue
                    ok2, reason2 = _is_house(it, detail)
                    if not ok2:
                        rejected[reason2] += 1
                        continue
                    try:
                        path = download_projection(detail, out_dir)
                        time.sleep(args.sleep)
                    except Exception as e:
                        rejected["download_fail"] += 1
                        print(f"  download fail {bid}: {e}", flush=True)
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
                    }
                    existing.append(row)
                    by_id[bid] = row
                    seen.add(bid)
                    new_rows.append(row)
                    added_by_style[style] += 1
                    print(f"  + {style} {row.get('name')} [{reason2}] -> {path.name}", flush=True)

    save_manifest(existing, manifest_path)
    report["fetch_new_rows"] = len(new_rows)
    report["fetch_added_by_style"] = dict(added_by_style)
    report["fetch_rejected"] = dict(rejected.most_common(40))
    report["manifest_total"] = len(existing)
    return new_rows


def _manifest_houses_for_styles(styles):
    man = ROOT / "data" / "raw" / "mcblock" / "manifest.json"
    if not man.exists():
        return []
    rows = json.loads(man.read_text(encoding="utf-8"))
    out = []
    for r in rows:
        st = pick_style(r.get("styles") or [])
        if st not in styles:
            continue
        ok, reason = _is_house(r)
        if not ok:
            continue
        fp = r.get("file")
        path = ROOT / fp if fp else None
        if path is None or not path.exists():
            bid = str(r.get("id") or "")
            cand = list((ROOT / "data" / "raw" / "mcblock").glob(f"*__{bid[:8]}*")) if bid else []
            if not cand:
                continue
            path = cand[0]
        r = dict(r)
        r["file"] = str(path.relative_to(ROOT)).replace("\\", "/")
        r["_keep_reason"] = reason
        r["_picked_style"] = st
        out.append(r)
    return out


def ingest_to_index(rows, args, report):
    index_dir = ROOT / (args.index_dir or INDEX_DIR_DEFAULT)
    index_dir.mkdir(parents=True, exist_ok=True)
    man_path = index_dir / "index.json"
    existing_ids = set()
    if man_path.exists():
        existing_ids = {it.get("id") for it in (json.loads(man_path.read_text(encoding="utf-8")).get("items") or [])}

    by_style_before = Counter()
    if man_path.exists():
        for it in json.loads(man_path.read_text(encoding="utf-8")).get("items") or []:
            by_style_before[it.get("mapped_style") or "unknown"] += 1

    ingested = []
    skipped = Counter()
    failed = []
    per_style_cap = {s: CAPS.get(s, 12) for s in TARGET_STYLES}
    if args.reingest_existing:
        per_style_cap = {s: max(40, CAPS.get(s, 12)) for s in TARGET_STYLES}

    style_added = Counter()
    for r in rows:
        style = r.get("_picked_style") or r.get("target_style") or pick_style(r.get("styles") or [])
        if style not in per_style_cap:
            skipped["style_not_target"] += 1
            continue
        if style_added[style] >= per_style_cap[style]:
            skipped[f"cap:{style}"] += 1
            continue
        fp = r.get("file")
        if not fp:
            skipped["no_file"] += 1
            continue
        path = ROOT / fp
        if not path.exists():
            skipped["missing_file"] += 1
            continue
        fid = path.stem
        if fid in existing_ids and not args.force_reingest:
            if args.fix_style_existing and "mcblock" in str(path).replace("\\", "/"):
                _override_feature_style(fid, style, "flat", index_dir)
                skipped["already_indexed_style_fixed"] += 1
            else:
                skipped["already_indexed"] += 1
            continue
        try:
            feat = extract_reference_features(
                path, skeleton_size=32, index_dir=index_dir, write=True,
                embed_block2vec=bool(args.embed_block2vec),
            )
            fid = feat["id"]
            _override_feature_style(fid, style, "flat", index_dir)
            ingested.append({
                "id": fid, "style": style, "name": r.get("name"),
                "source": str(path.relative_to(ROOT)).replace("\\", "/"),
                "reason": r.get("_keep_reason") or r.get("keep_reason"),
            })
            style_added[style] += 1
            existing_ids.add(fid)
            print(f"ingest OK {style} {fid}", flush=True)
        except Exception as e:
            failed.append({"file": str(path), "error": str(e)})
            print(f"ingest FAIL {path.name}: {e}", flush=True)

    by_style_after = Counter()
    if man_path.exists():
        for it in json.loads(man_path.read_text(encoding="utf-8")).get("items") or []:
            by_style_after[it.get("mapped_style") or "unknown"] += 1

    report["index_style_before"] = dict(by_style_before)
    report["index_style_after"] = dict(by_style_after)
    report["index_ingested"] = ingested
    report["index_ingested_by_style"] = dict(style_added)
    report["index_skipped"] = dict(skipped)
    report["index_failed"] = failed
    return report


def convert_new_to_processed(new_rows, report):
    from src.data.io_vox import save_npz_npz
    from src.data.litematic import fit_to_cube, load_litematic
    from src.utils import load_config, load_palette, save_palette

    if not new_rows:
        report["processed_added"] = 0
        report["palette_grew"] = False
        return

    cfg = load_config(ROOT / "configs" / "default.yaml")
    size = int(cfg["data"]["size"])
    out_dir = ROOT / cfg["data"]["processed_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    palette_path = ROOT / cfg["data"]["palette_path"]
    palette_before = dict(load_palette(palette_path))
    palette = dict(palette_before)
    name_to_id = {v: k for k, v in palette.items()}
    if "minecraft:air" not in name_to_id:
        name_to_id["minecraft:air"] = 0
        palette[0] = "minecraft:air"

    meta_path = out_dir / "meta.json"
    meta_rows = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else []
    by_file = {Path(m["file"]).name: m for m in meta_rows if m.get("file")}

    added = 0
    for r in new_rows:
        src = ROOT / r["file"]
        if not src.exists():
            continue
        try:
            voxels_idx, src_pal, meta = load_litematic(src)
            sx, sy, sz = meta["size"]
            if max(sx, sy, sz) > 96:
                continue
            for name in src_pal:
                if name not in name_to_id:
                    nid = max(palette) + 1 if palette else 1
                    palette[nid] = name
                    name_to_id[name] = nid
            remapped = np.zeros_like(voxels_idx, dtype=np.int16)
            for i, name in enumerate(src_pal):
                remapped[voxels_idx == i] = name_to_id[name]
            air_id = name_to_id["minecraft:air"]
            cube = fit_to_cube(remapped, size=size, air_id=air_id)
            stem = src.stem
            if stem.startswith("h337_"):
                continue
            dst = out_dir / f"{stem}.npz"
            save_npz_npz(dst, cube)
            row = {
                "file": str(dst.relative_to(ROOT)).replace("\\", "/"),
                "source": str(src.relative_to(ROOT)).replace("\\", "/"),
                "name": meta.get("name") or r.get("name"),
                "orig_size": list(meta["size"]),
                "non_air": int((cube != air_id).sum()),
                "labels": {
                    "styles": r.get("styles"),
                    "difficulty": r.get("difficulty"),
                    "tags": r.get("tags"),
                    "primaryType": r.get("primaryType"),
                    "name": r.get("name"),
                    "rare_terrain_hits": [],
                    "curated_style_house": True,
                },
            }
            by_file[dst.name] = row
            added += 1
            print(f"processed + {dst.name}", flush=True)
        except Exception as e:
            print(f"processed FAIL {src.name}: {e}", flush=True)

    meta_path.write_text(json.dumps(list(by_file.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    save_palette(palette, palette_path)
    report["processed_added"] = added
    report["palette_before_n"] = len(palette_before)
    report["palette_after_n"] = len(palette)
    report["palette_grew"] = len(palette) > len(palette_before)
    report["note_palette"] = "Palette may grow on ingest; do not continue-train."


def count_label_styles():
    lab = ROOT / "data" / "processed" / "labels.json"
    if not lab.exists():
        return {}
    data = json.loads(lab.read_text(encoding="utf-8"))
    c = Counter()
    for r in data.get("samples") or []:
        if isinstance(r, dict):
            c[r.get("style") or "unknown"] += 1
    return dict(c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw/mcblock")
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--styles", default="european,medieval,modern,chinese,japanese,industrial")
    ap.add_argument("--max-pages", type=int, default=2)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--max-blocks", type=int, default=8000)
    ap.add_argument("--max-edge", type=int, default=96)
    ap.add_argument("--sleep", type=float, default=0.4)
    ap.add_argument("--index-dir", default=INDEX_DIR_DEFAULT)
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--skip-processed", action="store_true")
    ap.add_argument("--reingest-existing", action="store_true")
    ap.add_argument("--fix-style-existing", action="store_true", default=True)
    ap.add_argument("--force-reingest", action="store_true")
    ap.add_argument("--embed-block2vec", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args()

    report_dir = ROOT / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {"started_at": _now(), "local_only": True, "no_train": True}
    report["labels_style_before"] = count_label_styles()
    idx = ROOT / args.index_dir / "index.json"
    if idx.exists():
        items = json.loads(idx.read_text(encoding="utf-8")).get("items") or []
        report["index_n_before"] = len(items)
        report["index_style_before_snapshot"] = dict(Counter(it.get("mapped_style") or "unknown" for it in items))

    new_rows = []
    if not args.skip_fetch and not args.no_fetch:
        new_rows = fetch_new(args, report)
    else:
        report["fetch_skipped"] = True

    rows_for_index = list(new_rows)
    if args.reingest_existing:
        styles = [s.strip() for s in args.styles.split(",") if s.strip()]
        existing_houses = _manifest_houses_for_styles(styles)
        report["existing_manifest_houses"] = len(existing_houses)
        rows_for_index = list(new_rows) + existing_houses

    ingest_to_index(rows_for_index, args, report)

    if not args.skip_processed:
        convert_new_to_processed(new_rows, report)
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_labels.py")],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        report["build_labels_rc"] = r.returncode
        report["build_labels_out"] = (r.stdout or "")[-2000:]
        report["build_labels_err"] = (r.stderr or "")[-1000:]
    report["labels_style_after"] = count_label_styles()
    report["finished_at"] = _now()
    (report_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REPORT", report_dir / "report.json", flush=True)
    print("fetch_new", report.get("fetch_new_rows"), "index_ingested", len(report.get("index_ingested") or []), flush=True)


if __name__ == "__main__":
    main()
