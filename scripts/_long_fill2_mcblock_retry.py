# -*- coding: utf-8 -*-
"""Retry MCBlock topup without search_q (styles+house q returns 0). Cap 3/style. No industrial."""
from __future__ import annotations
import json, time
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
sys.path.insert(0, str(ROOT))

from src.data.mcblock_api import download_projection, get_building, list_buildings
from src.app.reference_features import extract_reference_features, INDEX_DIR_DEFAULT

INDEX_DIR = Path(INDEX_DIR_DEFAULT)
REPORT = ROOT / "outputs/design/long_fill2_20261020_135822"

FARM = ("farm", "xpfarm", "breeder", "trading", "smelter", "spawner", "kelp", "afk", "duper", "sorter", "villager", "刷", "经验", "iron farm", "mob farm")
HOUSE = ("house", "home", "cottage", "villa", "cabin", "residence", "apartment", "loft", "mansion", "bungalow", "manor", "chalet", "住宅", "小屋", "别墅", "公寓", "木屋", "民居")
REJECT_PRIMARY = {"vehicle_transport", "sculpture_figure", "plant_nature", "landscape_component", "public_production", "interior_sample"}


def blob(it, detail=None):
    parts = []
    for src in (it, detail or {}):
        for k in ("name", "displayName", "title", "description"):
            if src.get(k):
                parts.append(str(src[k]))
        for k in ("tags", "tagList", "styles"):
            v = src.get(k) or []
            if isinstance(v, list):
                parts.extend(str(x) for x in v)
        if src.get("primaryType"):
            parts.append(str(src["primaryType"]))
    return " ".join(parts).lower()


def override_style(fid, style):
    feat_path = INDEX_DIR / f"{fid}.json"
    if feat_path.exists():
        data = json.loads(feat_path.read_text(encoding="utf-8"))
        data["mapped_style"] = style
        data["mapped_terrain"] = data.get("mapped_terrain") or "flat"
        data["long_fill2_retag"] = "long_fill2 mcblock topup retry"
        feat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    man = json.loads((INDEX_DIR / "index.json").read_text(encoding="utf-8"))
    for it in man.get("items") or []:
        if it.get("id") == fid:
            it["mapped_style"] = style
            break
    (INDEX_DIR / "index.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    man_path = ROOT / "data/raw/mcblock/manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else []
    known = {it.get("id") for it in man if it.get("id")}
    idx = json.loads((INDEX_DIR / "index.json").read_text(encoding="utf-8"))
    existing = set()
    for it in idx.get("items") or []:
        existing.add(it.get("id"))
        sp = (it.get("source_path") or "").replace("\\", "/")
        stem = Path(sp).stem
        if "__" in stem:
            existing.add(stem.split("__")[-1])

    out = {}
    for style in ("european", "modern", "rustic"):
        added, skipped, failed = [], Counter(), []
        print(f"retry {style}", flush=True)
        items = list_buildings(
            limit=30, max_pages=3, sort="recommended", styles=[style],
            difficulties=None, max_blocks=80000, max_width=48, max_depth=48,
            search_q=None, sleep_s=0.4,
        )
        print(f"  listed {len(items)}", flush=True)
        for it in items:
            if len(added) >= 3:
                break
            bid = it.get("id")
            if not bid or bid in known or bid in existing:
                skipped["already"] += 1
                continue
            try:
                detail = get_building(bid)
                time.sleep(0.25)
            except Exception as e:
                failed.append({"id": bid, "error": f"detail:{e}"})
                continue
            pt = (detail.get("primaryType") or it.get("primaryType") or "").strip()
            if pt in REJECT_PRIMARY:
                skipped[f"reject_primary:{pt}"] += 1
                continue
            b = blob(it, detail)
            if any(t in b for t in FARM) and "farmhouse" not in b and "farm house" not in b:
                skipped["farmish"] += 1
                continue
            if pt != "residential" and not any(h in b for h in HOUSE):
                skipped["no_house"] += 1
                continue
            w = int(detail.get("width") or it.get("width") or 0)
            d = int(detail.get("depth") or it.get("depth") or 0)
            bc = int(detail.get("blockCount") or it.get("blockCount") or 0)
            if w > 48 or d > 48 or bc > 80000:
                skipped["too_big"] += 1
                continue
            row = {**it, **{k: detail.get(k) for k in ("primaryType", "styles", "tags", "name", "description", "projectionFileUrl", "downloadUrl", "width", "height", "depth", "blockCount") if detail.get(k) is not None}}
            try:
                dest = download_projection(row, ROOT / "data/raw/mcblock")
                time.sleep(0.3)
            except Exception as e:
                failed.append({"id": bid, "error": f"dl:{e}"})
                continue
            if not dest or not Path(dest).exists():
                failed.append({"id": bid, "error": "no_file"})
                continue
            try:
                feat = extract_reference_features(dest, skeleton_size=32, index_dir=INDEX_DIR, write=True, embed_block2vec=False)
                fid = feat["id"]
                override_style(fid, style)
                man.append({"id": bid, "name": row.get("name"), "styles": row.get("styles") or [style], "file": str(Path(dest).relative_to(ROOT)), "_topup": "long_fill2_retry"})
                known.add(bid)
                existing.add(fid)
                added.append({"id": bid, "fid": fid, "name": row.get("name")})
                print(f"  ADD {style} {fid} {row.get('name')}", flush=True)
            except Exception as e:
                failed.append({"id": bid, "error": f"ingest:{e}"})
        man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
        out[style] = {"added_n": len(added), "added": added, "skipped": dict(skipped), "failed": failed[:10], "listed": len(items), "exhausted": len(added) == 0}
    (REPORT / "mcblock_topup_retry.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: {"added_n": v["added_n"], "skipped": v["skipped"], "listed": v["listed"]} for k, v in out.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
