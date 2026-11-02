# -*- coding: utf-8 -*-
"""Industrial residential loft top-up + farm demote. LOCAL_ONLY. No VAE.
1) Demote farm/XP/smelter spam from industrial mapped_style -> unknown + exclude_reason=public_production
2) MCBlock fetch industrial house/loft/warehouse-home only
3) Ingest + optional block2vec embed
4) Write report under outputs/design/industrial_rs_topup_<ts>/
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest
from src.app.reference_features import extract_reference_features, INDEX_DIR_DEFAULT

TZ = timezone(timedelta(hours=8))

FARM_TOKENS = (
    "farm", "xpfarm", "xp_farm", "xp farm", "breeder", "pyramid", "trading_hall",
    "trading%20hall", "trading hall", "smelter", "smoker", "kelp", "iron_farm",
    "iron farm", "mob_farm", "mob farm", "spawner", "raid_farm", "gold_farm",
    "goldfarm", "afk", "duper", "duping", "carpet_duper", "bone%20meal",
    "bonemeal", "bone_meal", "coral_farm", "pickle_farm", "lava_farm",
    "rabbit_farm", "slime_farm", "goat_horn", "piglin_trading", "villager_breeder",
    "auto_smelter", "super_smelter", "supersmelter", "kill_chamber", "shulker_loader",
    "item_sorter", "crop", "wheat_farm", "carrot_and_wheat",
)

HOUSE_KW = [
    "house", "home", "loft", "cottage", "villa", "cabin", "residence",
    "apartment", "condo", "workshop house", "warehouse house", "warehouse home",
    "factory house", "brick house", "townhouse", "mansion", "bungalow",
    "\u4f4f\u5b85", "\u5c0f\u5c4b", "\u522b\u5885", "\u5382\u623f", "\u5de5\u4e1a\u98ce",
    "\u5de5\u4f5c\u5ba4", "\u6539\u9020", "\u5de5\u4e1a\u98ce\u4f4f\u5b85",
]
REJECT_KW = [
    "pyramid", "challenge", "mcbuildchallenge", "xp farm", "xpfarm", "duper",
    "kelp farm", "statue", "sculpture", "arena", "parkour", "iron farm",
    "mob farm", "breeder", "trading hall", "smelter", "spawner", "afk farm",
    "super smelter", "raid farm", "gold farm", "villager",
]
REJECT_PRIMARY = {
    "vehicle_transport", "sculpture_figure", "plant_nature",
    "landscape_component", "interior_sample", "public_production",
}

INDUSTRIAL_QUERIES = [
    "industrial loft",
    "warehouse loft",
    "loft house",
    "industrial house",
    "brick factory house",
    "warehouse house",
    "workshop house",
    "factory house",
    "industrial apartment",
    "\u5de5\u4e1a\u98ce\u4f4f\u5b85",
    "\u5382\u623f\u6539\u9020",
    "\u5de5\u4e1a\u98ce\u5c0f\u5c4b",
]


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


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
    # reject farm tokens even if "house" somehow appears
    for kw in FARM_TOKENS:
        if kw in blob and "farmhouse" not in blob and "farm house" not in blob:
            # farmhouse is residential
            if kw in ("farm",) and ("farmhouse" in blob or "farm house" in blob):
                continue
            if kw == "farm" and any(h in blob for h in ("house", "home", "loft", "cottage")):
                # "farm house" ok; bare "... farm" bad
                if " farm" in blob or blob.endswith("farm") or "farm " in blob:
                    if "farmhouse" not in blob and "farm house" not in blob:
                        return False, f"reject_farmish:{kw}"
            elif kw != "farm":
                return False, f"reject_farmish:{kw}"
    if pt == "residential":
        return True, "primary:residential"
    for kw in HOUSE_KW:
        if kw.lower() in blob or kw in blob:
            return True, f"house_kw:{kw}"
    return False, "no_house_evidence"


def _path_blob(it: dict) -> str:
    return ((it.get("id") or "") + " " + (it.get("source_path") or "")).replace("\\", "/").lower()


def is_farmish_industrial(it: dict) -> tuple[bool, str]:
    blob = _path_blob(it)
    # keep if clearly residential house/loft
    house_hits = [h for h in ("house", "home", "loft", "apartment", "cottage", "villa", "\u5c0f\u5c4b", "\u4f4f\u5b85", "\u522b\u5885") if h in blob]
    farm_hits = []
    for t in FARM_TOKENS:
        if t in blob:
            farm_hits.append(t)
    if farm_hits and not house_hits:
        return True, farm_hits[0]
    if farm_hits and house_hits:
        # e.g. "farm house" — keep unless strong machine token
        strong = [t for t in farm_hits if t not in ("farm", "crop")]
        if strong:
            return True, strong[0]
    return False, ""


def _override_feature(fid: str, *, mapped_style: str | None = None, extra: dict | None = None, index_dir: Path) -> None:
    feat_path = index_dir / f"{fid}.json"
    if feat_path.exists():
        data = json.loads(feat_path.read_text(encoding="utf-8"))
        if mapped_style is not None:
            data["mapped_style"] = mapped_style
        if extra:
            data.update(extra)
        feat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    man_path = index_dir / "index.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    for it in man.get("items") or []:
        if it.get("id") == fid:
            if mapped_style is not None:
                it["mapped_style"] = mapped_style
            if extra:
                for k, v in extra.items():
                    if k in ("exclude_from_residential", "exclude_reason", "retag_note"):
                        it[k] = v
            break
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")


def demote_farms(index_dir: Path) -> dict:
    man = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    items = man.get("items") or []
    demoted = []
    kept = []
    for it in items:
        if (it.get("mapped_style") or "").lower() != "industrial":
            continue
        bad, tok = is_farmish_industrial(it)
        if bad:
            demoted.append({"id": it["id"], "token": tok, "was": "industrial"})
            _override_feature(
                it["id"],
                mapped_style="unknown",
                extra={
                    "exclude_from_residential": True,
                    "exclude_reason": "public_production",
                    "retag_note": f"demoted_from_industrial:{tok}",
                    "previous_mapped_style": "industrial",
                },
                index_dir=index_dir,
            )
        else:
            kept.append(it["id"])
    return {"demoted": demoted, "kept_industrial_ids": kept, "demoted_n": len(demoted), "kept_n": len(kept)}


def count_industrial(index_dir: Path) -> dict:
    man = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    items = man.get("items") or []
    ind = [it for it in items if (it.get("mapped_style") or "").lower() == "industrial"]
    mc = [it for it in ind if "mcblock" in (it.get("source_path") or "").replace("\\", "/").lower()]
    return {
        "industrial_mapped": len(ind),
        "industrial_mcblock": len(mc),
        "mcblock_ids": [it["id"] for it in mc],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--cap", type=int, default=16)
    ap.add_argument("--sleep", type=float, default=0.55)
    ap.add_argument("--embed-block2vec", action="store_true")
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--skip-demote", action="store_true")
    ap.add_argument("--max-edge", type=int, default=96)
    ap.add_argument("--max-blocks", type=int, default=12000)
    args = ap.parse_args()

    report_dir = Path(args.report_dir)
    if not report_dir.is_absolute():
        report_dir = ROOT / report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    index_dir = ROOT / INDEX_DIR_DEFAULT
    out_dir = ROOT / "data" / "raw" / "mcblock"
    out_dir.mkdir(parents=True, exist_ok=True)
    man_path = out_dir / "manifest.json"

    before = count_industrial(index_dir)
    demote_report = {"skipped": True}
    if not args.skip_demote:
        demote_report = demote_farms(index_dir)
        print(f"demoted {demote_report['demoted_n']} farmish industrial -> unknown/public_production", flush=True)

    after_demote = count_industrial(index_dir)

    # expand BUILDING_PENALTY in gen_strategy if not already present
    # (done separately via patch)

    added = []
    skipped = Counter()
    failed = []
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else []
    known_ids = {it.get("id") for it in man if it.get("id")}
    idx = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    existing_ids = {it.get("id") for it in (idx.get("items") or [])}

    if not args.skip_fetch:
        # style-only industrial listing
        for sort in ("recommended", "latest"):
            if len(added) >= args.cap:
                break
            print(f"discover style=industrial sort={sort}", flush=True)
            try:
                items = list_buildings(
                    limit=args.limit,
                    max_pages=args.max_pages,
                    sort=sort,
                    styles=["industrial"],
                    difficulties=None,
                    max_blocks=None,
                    max_width=None,
                    max_depth=None,
                    search_q=None,
                    sleep_s=args.sleep,
                )
            except Exception as e:
                failed.append({"phase": "list_style", "sort": sort, "error": str(e)})
                print(f"  FAIL list: {e}", flush=True)
                time.sleep(1.5)
                continue
            print(f"  got {len(items)} raw", flush=True)
            for it in items:
                if len(added) >= args.cap:
                    break
                _try_add(it, added, skipped, failed, known_ids, existing_ids, man, out_dir, index_dir, args)

        # query-based loft/warehouse searches (may 400 on some APIs — best effort)
        for q in INDUSTRIAL_QUERIES:
            if len(added) >= args.cap:
                break
            print(f"discover q={q!r}", flush=True)
            try:
                items = list_buildings(
                    limit=min(30, args.limit),
                    max_pages=2,
                    sort="recommended",
                    styles=["industrial"],
                    difficulties=None,
                    max_blocks=None,
                    max_width=None,
                    max_depth=None,
                    search_q=q,
                    sleep_s=args.sleep,
                )
            except Exception as e:
                failed.append({"phase": "list_q", "q": q, "error": str(e)})
                print(f"  FAIL q list: {e}", flush=True)
                time.sleep(1.0)
                continue
            print(f"  got {len(items)} for q", flush=True)
            for it in items:
                if len(added) >= args.cap:
                    break
                _try_add(it, added, skipped, failed, known_ids, existing_ids, man, out_dir, index_dir, args)

        save_manifest(man, man_path)

    after = count_industrial(index_dir)
    report = {
        "started_at": _now(),
        "before": before,
        "after_demote": after_demote,
        "after": after,
        "demote": {
            "demoted_n": demote_report.get("demoted_n"),
            "kept_n": demote_report.get("kept_n"),
            "demoted_sample": (demote_report.get("demoted") or [])[:40],
        },
        "added": added,
        "added_n": len(added),
        "skipped": dict(skipped),
        "failed": failed[:40],
        "failed_n": len(failed),
    }
    (report_dir / "industrial_loft_topup.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("BEFORE", before)
    print("AFTER_DEMOTE", after_demote)
    print("AFTER", after)
    print("added_n", len(added))
    print("wrote", report_dir / "industrial_loft_topup.json")


def _try_add(it, added, skipped, failed, known_ids, existing_ids, man, out_dir, index_dir, args):
    bid = it.get("id")
    if not bid:
        return
    if bid in known_ids:
        skipped["already_manifest"] += 1
        return
    w, h, d = it.get("width") or 0, it.get("height") or 0, it.get("depth") or 0
    bc = it.get("blockCount") or 0
    if max(int(w or 0), int(h or 0), int(d or 0)) > args.max_edge or (bc and int(bc) > args.max_blocks):
        skipped["too_big"] += 1
        return
    ok, reason = is_house(it)
    detail = None
    if not ok:
        try:
            detail = get_building(bid)
            time.sleep(args.sleep)
        except Exception:
            skipped[f"reject:{reason}"] += 1
            return
        ok, reason = is_house(it, detail)
        if not ok:
            skipped[f"reject:{reason}"] += 1
            return
        for k in ("primaryType", "styles", "tags", "name", "description"):
            if detail.get(k) is not None:
                it[k] = detail[k]
    # prefer industrial in styles list
    styles_l = [str(x).lower() for x in (it.get("styles") or [])]
    if styles_l and "industrial" not in styles_l:
        # allow if query-forced loft and residential
        if reason.startswith("house_kw") or reason.startswith("primary"):
            pass
        else:
            skipped["not_industrial_style"] += 1
            return
    try:
        dest = download_projection(it, out_dir)
        time.sleep(args.sleep)
    except Exception as e:
        failed.append({"id": bid, "error": f"dl:{e}"})
        print(f"  DL FAIL {it.get('name')}: {e}", flush=True)
        return
    if not dest or not dest.exists():
        failed.append({"id": bid, "error": "no_file"})
        return
    row = {
        "id": bid,
        "name": it.get("name"),
        "styles": it.get("styles") or ["industrial"],
        "primaryType": it.get("primaryType"),
        "width": w,
        "height": h,
        "depth": d,
        "blockCount": bc,
        "file": str(dest.relative_to(ROOT)).replace("/", "\\"),
        "projectionFileUrl": it.get("projectionFileUrl") or it.get("downloadUrl"),
        "_picked_style": "industrial",
        "_keep_reason": reason,
        "_industrial_loft_topup": True,
    }
    man.append(row)
    known_ids.add(bid)
    try:
        feat = extract_reference_features(
            dest,
            skeleton_size=32,
            index_dir=index_dir,
            write=True,
            embed_block2vec=bool(args.embed_block2vec),
        )
        fid = feat["id"]
        _override_feature(fid, mapped_style="industrial", extra={"residential_loft_topup": True}, index_dir=index_dir)
        existing_ids.add(fid)
        added.append({"id": fid, "name": it.get("name"), "reason": reason, "file": row["file"]})
        print(f"  ADD industrial {fid} ({it.get('name')}) [{reason}]", flush=True)
    except Exception as e:
        failed.append({"id": bid, "error": f"ingest:{e}"})
        print(f"  INGEST FAIL {dest.name}: {e}", flush=True)


if __name__ == "__main__":
    main()
