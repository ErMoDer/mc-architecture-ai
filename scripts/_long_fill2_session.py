# -*- coding: utf-8 -*-
"""Long fill2 finish: Hack337 house retag + light euro/modern/rustic MCBlock topup + smoke. No VAE. No industrial loft spin."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
sys.path.insert(0, str(ROOT))

from src.app.reference_features import INDEX_DIR_DEFAULT, extract_reference_features
from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest

TZ = timezone(timedelta(hours=8))
INDEX_DIR = Path(INDEX_DIR_DEFAULT)

FARM_TOKENS = (
    "farm", "xpfarm", "xp farm", "breeder", "trading", "smelter", "smoker", "kelp",
    "iron_farm", "iron farm", "mob_farm", "mob farm", "spawner", "raid_farm",
    "gold_farm", "afk", "duper", "sorter", "vth", "villager", "刷", "经验",
)
HOUSE_KW = (
    "house", "home", "cottage", "villa", "cabin", "residence", "apartment",
    "condo", "loft", "mansion", "bungalow", "manor", "chalet", "townhouse",
    "住宅", "小屋", "别墅", "farmhouse",
)

STYLE_HINTS = {
    "european": ("european", "euro", "victorian", "baroque", "chateau", "georgian", "tudor", "french manor", "pie manor", "piemanor"),
    "modern": ("modern", "contemporary", "minimalist", "bauhaus", "glass house"),
    "rustic": ("rustic", "cottage", "cabin", "farmhouse", "chalet", "countryside", "log cabin"),
    "western": ("western", "saloon", "wild west", "ranch house"),
}


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _src(it: dict) -> str:
    sp = (it.get("source_path") or it.get("id") or "").replace("\\", "/").lower()
    if "hack337" in sp or "h337" in sp:
        return "hack337"
    if "mcblock" in sp:
        return "mcblock"
    return "other"


def _blob(it: dict) -> str:
    parts = [
        str(it.get("name") or ""),
        str(it.get("source_path") or ""),
        str(it.get("id") or ""),
        str(it.get("displayName") or ""),
    ]
    return " ".join(parts).replace("%20", " ").lower()


def is_farmish(blob: str) -> bool:
    if "farmhouse" in blob or "farm house" in blob:
        return False
    return any(t in blob for t in FARM_TOKENS)


def style_counts(index_dir: Path) -> dict:
    idx = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    items = idx.get("items") or []
    out = {}
    for sty in ["industrial", "european", "modern", "rustic", "chinese", "medieval", "fantasy", "western", "unknown"]:
        mapped = [it for it in items if (it.get("mapped_style") or "unknown") == sty]
        mcb = [it for it in mapped if _src(it) == "mcblock"]
        mcb_ok = []
        for it in mcb:
            b = _blob(it)
            if it.get("exclude_from_residential"):
                continue
            if is_farmish(b) and not any(h in b for h in ("house", "home", "loft", "cottage", "villa", "cabin")):
                continue
            mcb_ok.append(it)
        h337 = [it for it in mapped if _src(it) == "hack337"]
        out[sty] = {
            "mapped": len(mapped),
            "mcblock": len(mcb),
            "mcblock_resid_ok": len(mcb_ok),
            "hack337": len(h337),
        }
    out["_index_n"] = len(items)
    return out


def override_style(fid: str, style: str, index_dir: Path, note: str) -> None:
    feat_path = index_dir / f"{fid}.json"
    if feat_path.exists():
        data = json.loads(feat_path.read_text(encoding="utf-8"))
        data["mapped_style"] = style
        data["long_fill2_retag"] = note
        feat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    man = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    for it in man.get("items") or []:
        if it.get("id") == fid:
            it["mapped_style"] = style
            it["long_fill2_retag"] = note
            break
    (index_dir / "index.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")


def hack337_house_retag(index_dir: Path) -> dict:
    """Retag already-ingested Hack337 houses mislabeled as chinese/industrial/unknown. No download."""
    idx = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    retagged = []
    skipped = Counter()
    for it in idx.get("items") or []:
        if _src(it) != "hack337":
            continue
        blob = _blob(it)
        if is_farmish(blob):
            skipped["farmish"] += 1
            continue
        # must look residential
        if not any(h in blob for h in HOUSE_KW + ("saloon", "manor", "shell", "mansion", "cottage", "cabin")):
            skipped["no_house_kw"] += 1
            continue
        ms = it.get("mapped_style") or "unknown"
        chosen = None
        for sty, kws in STYLE_HINTS.items():
            if any(k in blob for k in kws):
                chosen = sty
                break
        if not chosen:
            skipped["no_style_hint"] += 1
            continue
        if ms == chosen:
            skipped["already_correct"] += 1
            continue
        # only fix obvious mislabels
        if ms not in ("chinese", "industrial", "unknown", "unk", ""):
            skipped[f"keep_{ms}"] += 1
            continue
        # skip bath-only / shell-only industrial if modern but name is only bath? keep modern shells as modern
        fid = it.get("id")
        if not fid:
            skipped["no_id"] += 1
            continue
        note = f"long_fill2 hack337 {ms}->{chosen}"
        override_style(fid, chosen, index_dir, note)
        retagged.append({"id": fid, "from": ms, "to": chosen, "blob": blob[:80]})
    return {"retagged_n": len(retagged), "retagged": retagged, "skipped": dict(skipped)}


def light_mcblock_topup(styles: list[str], index_dir: Path, report_dir: Path, per_style_cap: int = 4) -> dict:
    """One short house-only discovery pass; stop early when exhausted. No industrial loft."""
    man_path = ROOT / "data" / "raw" / "mcblock" / "manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else []
    known = {it.get("id") for it in man if it.get("id")}
    idx = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    existing = {it.get("id") for it in (idx.get("items") or [])}
    for it in idx.get("items") or []:
        sp = (it.get("source_path") or "").replace("\\", "/")
        stem = Path(sp).stem
        if "__" in stem:
            existing.add(stem.split("__")[-1])

    results = {}
    for style in styles:
        added, skipped, failed = [], Counter(), []
        print(f"topup style={style}", flush=True)
        try:
            items = list_buildings(
                limit=30,
                max_pages=3,
                sort="recommended",
                styles=[style] if style != "western" else None,
                difficulties=None,
                max_blocks=80000,
                max_width=48,
                max_depth=48,
                search_q="house" if style != "western" else "saloon house",
                sleep_s=0.4,
            )
        except Exception as e:
            failed.append({"phase": "list", "error": str(e)})
            results[style] = {"added_n": 0, "skipped": dict(skipped), "failed": failed, "exhausted": True}
            continue
        for it in items:
            if len(added) >= per_style_cap:
                break
            bid = it.get("id")
            if not bid or bid in known or bid in existing:
                skipped["already"] += 1
                continue
            # detail merge
            detail = None
            try:
                detail = get_building(bid)
            except Exception as e:
                failed.append({"id": bid, "error": f"detail:{e}"})
                continue
            pt = (detail.get("primaryType") or it.get("primaryType") or "").strip()
            if pt in {"vehicle_transport", "sculpture_figure", "plant_nature", "landscape_component", "public_production"}:
                skipped[f"reject_primary:{pt}"] += 1
                continue
            blob = " ".join(
                str(x) for x in [
                    it.get("name"), detail.get("name"), detail.get("description"),
                    " ".join(str(t) for t in (detail.get("tags") or [])),
                    " ".join(str(s) for s in (detail.get("styles") or [])),
                    pt,
                ] if x
            ).lower()
            if is_farmish(blob):
                skipped["farmish"] += 1
                continue
            if pt != "residential" and not any(h in blob for h in HOUSE_KW):
                skipped["no_house"] += 1
                continue
            # size guard
            w = detail.get("width") or it.get("width") or 0
            d = detail.get("depth") or it.get("depth") or 0
            blocks = detail.get("blockCount") or it.get("blockCount") or 0
            try:
                if int(w or 0) > 48 or int(d or 0) > 48 or int(blocks or 0) > 80000:
                    skipped["too_big"] += 1
                    continue
            except Exception:
                pass
            row = {**it, **{k: detail.get(k) for k in ("primaryType", "styles", "tags", "name", "description", "projectionFileUrl", "downloadUrl", "width", "height", "depth", "blockCount") if detail.get(k) is not None}}
            try:
                dest = download_projection(row, ROOT / "data" / "raw" / "mcblock")
            except Exception as e:
                failed.append({"id": bid, "error": f"dl:{e}"})
                continue
            if not dest or not Path(dest).exists():
                failed.append({"id": bid, "error": "no_file"})
                continue
            try:
                feat = extract_reference_features(dest, skeleton_size=32, index_dir=index_dir, write=True, embed_block2vec=False)
                fid = feat.get("id")
                target = style if style != "western" else "western"
                override_style(fid, target, index_dir, "long_fill2 mcblock topup")
                feat_path = index_dir / f"{fid}.json"
                if feat_path.exists():
                    data = json.loads(feat_path.read_text(encoding="utf-8"))
                    data["mapped_terrain"] = data.get("mapped_terrain") or "flat"
                    feat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                man.append({"id": bid, "name": row.get("name"), "styles": row.get("styles") or [style], "file": str(Path(dest).relative_to(ROOT)), "_topup": "long_fill2"})
                man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
                added.append({"id": bid, "fid": fid, "name": row.get("name")})
                known.add(bid)
                existing.add(fid)
            except Exception as e:
                failed.append({"id": bid, "error": f"ingest:{e}"})
        exhausted = len(added) == 0
        results[style] = {
            "added_n": len(added),
            "added": added,
            "skipped": dict(skipped),
            "failed": failed[:8],
            "exhausted": exhausted,
            "listed": len(items),
        }
        print(f"  {style} added={len(added)} skipped={dict(skipped)}", flush=True)
    (report_dir / "mcblock_topup.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def paste_smoke(report_dir: Path) -> dict:
    out = {}
    pairs = [
        ("item_filter_stub", "sample_seuropean_tflat_000.npz", "欧式_物品过滤桩"),
        ("lectern_book_signal", "sample_smodern_tflat_000.npz", "现代_讲台书信号桩"),
    ]
    base = ROOT / "outputs/design/full_style_v4_20261020_112642/npz"
    for tid, npz_name, cname in pairs:
        npz = base / npz_name
        paste_dir = report_dir / f"paste_{tid}"
        paste_dir.mkdir(parents=True, exist_ok=True)
        if not npz.exists():
            # fallback any european/modern npz
            cands = list((ROOT / "outputs/design").glob(f"**/npz/{npz_name}"))
            npz = cands[0] if cands else npz
        cmd = [
            str(ROOT / ".venv/Scripts/python.exe"),
            str(ROOT / "scripts/paste_redstone_into_design.py"),
            "--npz", str(npz),
            "--template", tid,
            "--out-dir", str(paste_dir),
            "--companion",
            "--companion-name", cname,
        ]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, encoding="utf-8", errors="replace")
        (paste_dir / "console.txt").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
        out[tid] = {"rc": r.returncode, "ok": r.returncode == 0, "npz": str(npz), "companion": cname, "dir": str(paste_dir)}
        print("paste", tid, "rc", r.returncode, flush=True)
    return out


def index_top(style: str, index_dir: Path, n: int = 5) -> list:
    idx = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    rows = []
    for it in idx.get("items") or []:
        if (it.get("mapped_style") or "") != style:
            continue
        if it.get("exclude_from_residential"):
            continue
        rows.append({
            "id": it.get("id"),
            "src": _src(it),
            "name": (it.get("name") or it.get("source_path") or "")[:60],
        })
    return rows[:n]


def main() -> None:
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    report_dir = ROOT / "outputs" / "design" / f"long_fill2_{stamp}"
    report_dir.mkdir(parents=True, exist_ok=True)

    before = style_counts(INDEX_DIR)
    (report_dir / "before_counts.json").write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
    print("before", before, flush=True)

    print("=== hack337 retag ===", flush=True)
    retag = hack337_house_retag(INDEX_DIR)
    (report_dir / "hack337_retag.json").write_text(json.dumps(retag, ensure_ascii=False, indent=2), encoding="utf-8")
    print("retag_n", retag["retagged_n"], flush=True)

    print("=== light mcblock topup (no industrial) ===", flush=True)
    topup = light_mcblock_topup(["european", "modern", "rustic"], INDEX_DIR, report_dir, per_style_cap=3)

    after = style_counts(INDEX_DIR)
    (report_dir / "after_counts.json").write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== smoke paste ===", flush=True)
    paste = paste_smoke(report_dir)

    cat = json.loads((ROOT / "data/redstone_templates/catalog.json").read_text(encoding="utf-8"))
    cat_ids = [t["id"] for t in cat["templates"]]
    new_rs = [
        "item_filter_stub",
        "torch_tower_elevator_frag",
        "hopper_clock_xor_alt",
        "lectern_book_signal",
        "target_block_signal",
        "brewing_stand_hopper_stub",
    ]

    smoke_ret = {s: index_top(s, INDEX_DIR, 5) for s in ["european", "modern", "rustic", "western", "industrial"]}

    lines = []
    lines.append("# Long fill2 COUNTS\n\n")
    lines.append(f"Finished: {_now()} (Asia/Shanghai)\n\n")
    lines.append("## Styles (before → after)\n\n")
    lines.append("| style | before mapped | after mapped | before mcblock | after mcblock | before ok | after ok | before h337 | after h337 |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    for s in ["industrial", "european", "modern", "rustic", "western", "chinese", "medieval", "fantasy", "unknown"]:
        b = before.get(s, {})
        a = after.get(s, {})
        lines.append(
            f"| {s} | {b.get('mapped')} | {a.get('mapped')} | {b.get('mcblock')} | {a.get('mcblock')} | "
            f"{b.get('mcblock_resid_ok')} | {a.get('mcblock_resid_ok')} | {b.get('hack337')} | {a.get('hack337')} |\n"
        )
    lines.append(f"\n## Hack337 retag (already ingested, no re-download)\n- retagged_n: **{retag['retagged_n']}**\n")
    lines.append(f"- skipped: `{json.dumps(retag.get('skipped', {}), ensure_ascii=False)}`\n")
    for r in retag.get("retagged") or []:
        lines.append(f"- `{r['id']}`: {r['from']} → {r['to']}\n")
    lines.append("\n## MCBlock light topup (house-only, no industrial loft)\n")
    for sty, res in topup.items():
        lines.append(
            f"- **{sty}**: added={res.get('added_n')} exhausted={res.get('exhausted')} "
            f"listed={res.get('listed')} skipped=`{json.dumps(res.get('skipped', {}), ensure_ascii=False)}`\n"
        )
    lines.append(f"\n## Redstone\n- catalog **28 → {len(cat_ids)}**\n- new: {new_rs}\n")
    lines.append("\n## Smoke\n")
    for tid, info in paste.items():
        lines.append(f"- paste `{tid}`: ok={info.get('ok')} → `{info.get('dir')}`\n")
    lines.append("\n## Residuals\n")
    lines.append("- Industrial loft MCBlock still exhausted; intentionally not retried this session.\n")
    lines.append("- Hack337 western/non-MCBlock: retag only (already ingested). Villager/farm names left untouched.\n")
    lines.append("- MCBlock euro/modern/rustic topup stopped when added_n=0 or cap; no infinite SSL/400 loops.\n")
    lines.append("- No VAE train; early-tech companion Chinese names untouched.\n")
    (report_dir / "COUNTS.md").write_text("".join(lines), encoding="utf-8")

    summary = {
        "finished_at": _now(),
        "report_dir": str(report_dir),
        "before": before,
        "after": after,
        "hack337_retag": retag,
        "mcblock_topup": topup,
        "redstone": {"before": 28, "after": len(cat_ids), "new_ids": new_rs, "all_ids": cat_ids},
        "paste": paste,
        "smoke_retrieval": smoke_ret,
        "residuals": [
            "Industrial loft not retried (exhausted prior session).",
            "Hack337 retag is keyword-based; files kept on disk.",
            "No VAE train; early-tech companion names untouched.",
        ],
    }
    (report_dir / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "smoke_retrieval.json").write_text(json.dumps(smoke_ret, ensure_ascii=False, indent=2), encoding="utf-8")

    # docs append
    rs_doc = ROOT / "docs" / "redstone_templates.md"
    txt = rs_doc.read_text(encoding="utf-8")
    if "item_filter_stub" not in txt:
        txt += (
            "\n\n## Long fill2 stubs (2026-10-20)\n\n"
            f"Catalog **28 → {len(cat_ids)}**. New indoor teaching stubs: "
            + ", ".join(f"`{i}`" for i in new_rs)
            + f". Report: `{report_dir.relative_to(ROOT).as_posix()}/`.\n"
        )
        rs_doc.write_text(txt, encoding="utf-8")

    lh = ROOT / "docs" / "look_harden.md"
    txt = lh.read_text(encoding="utf-8")
    marker = report_dir.name
    if marker not in txt:
        txt += (
            f"\n\n## Long fill2 ({marker})\n\n"
            "No facade knob / VAE changes. "
            f"Hack337 house retag n={retag['retagged_n']}; "
            f"european mapped {before['european']['mapped']}→{after['european']['mapped']}; "
            f"modern {before['modern']['mapped']}→{after['modern']['mapped']}; "
            f"rustic {before['rustic']['mapped']}→{after['rustic']['mapped']}; "
            f"western {before.get('western',{}).get('mapped')}→{after.get('western',{}).get('mapped')}. "
            f"RS catalog 28→{len(cat_ids)}. See `{report_dir.relative_to(ROOT).as_posix()}/COUNTS.md`.\n"
        )
        lh.write_text(txt, encoding="utf-8")

    print("DONE", report_dir, flush=True)
    print("templates", len(cat_ids), flush=True)
    print("retag", retag["retagged_n"], flush=True)


if __name__ == "__main__":
    main()
