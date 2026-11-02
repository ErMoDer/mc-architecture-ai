# -*- coding: utf-8 -*-
"""Long autonomous residential + RS stub fill. LOCAL_ONLY. No VAE train."""
from __future__ import annotations

import json
import time
import traceback
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
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
    "item_sorter", "crop", "wheat_farm", "carrot_and_wheat", "经验塔", "刷怪",
    "刷怪塔", "经验农场", "刷铁", "刷金",
)

HOUSE_KW = [
    "house", "home", "loft", "cottage", "villa", "cabin", "residence",
    "apartment", "condo", "workshop house", "warehouse house", "warehouse home",
    "factory house", "brick house", "townhouse", "mansion", "bungalow",
    "住宅", "小屋", "别墅", "厂房", "工业风", "工作室", "改造", "工业风住宅",
    "warehouse", "workshop", "factory loft", "brick loft",
]
REJECT_KW = [
    "pyramid", "challenge", "mcbuildchallenge", "xp farm", "xpfarm", "duper",
    "kelp farm", "statue", "sculpture", "arena", "parkour", "iron farm",
    "mob farm", "breeder", "trading hall", "smelter", "spawner", "afk farm",
    "super smelter", "raid farm", "gold farm", "villager", "刷怪", "经验塔",
]
REJECT_PRIMARY = {
    "vehicle_transport", "sculpture_figure", "plant_nature",
    "landscape_component", "interior_sample", "public_production",
}

INDUSTRIAL_QUERIES = [
    "industrial house",
    "brick house",
    "workshop",
    "warehouse",
    "factory house",
    "industrial apartment",
    "loft",
    "工业风住宅",
    "厂房改造",
    "工业风小屋",
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
        styles = src.get("styles") or []
        if isinstance(styles, list):
            parts.extend(str(s) for s in styles)
    return " ".join(parts).lower()


def is_house(it, detail=None):
    pt = (it.get("primaryType") or (detail or {}).get("primaryType") or "").strip()
    if pt in REJECT_PRIMARY:
        return False, f"reject_primary:{pt}"
    blob = _blob(it, detail)
    for kw in REJECT_KW:
        if kw in blob:
            return False, f"reject_kw:{kw}"
    for kw in FARM_TOKENS:
        if kw in blob and "farmhouse" not in blob and "farm house" not in blob:
            if kw == "farm" and any(h in blob for h in ("house", "home", "loft", "cottage")):
                if "farmhouse" not in blob and "farm house" not in blob:
                    if " farm" in blob or blob.endswith("farm") or "farm " in blob:
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
    return ((it.get("id") or "") + " " + (it.get("source_path") or "") + " " + (it.get("name") or "")).replace("\\", "/").lower()


def is_farmish_path(it: dict, *, allow_chinese_tower: bool = False) -> tuple[bool, str]:
    blob = _path_blob(it)
    house_hits = [h for h in ("house", "home", "loft", "apartment", "cottage", "villa", "小屋", "住宅", "别墅", "farmhouse", "pagoda", "庙", "庭院", "四合院") if h in blob]
    # strong machine/farm tokens
    strong = [
        "xpfarm", "xp_farm", "xp farm", "iron_farm", "iron farm", "mob_farm", "mob farm",
        "gold_farm", "goldfarm", "bone_meal", "bonemeal", "kelp", "smelter", "spawner",
        "raid_farm", "afk", "duper", "breeder", "trading_hall", "trading hall",
        "刷怪", "经验塔", "经验农场", "刷铁", "刷金", "autosmelter", "super_smelter",
        "wheat_farm", "carrot_and_wheat", "crop_farm", "chicken_farm", "slime_farm",
        " Melon_Farm".lower(), "mushroom_farm", "cobblestone_farm", "stonefarm",
        "string_farm", "shulker", "kill_chamber",
    ]
    for t in strong:
        if t in blob:
            return True, t
    # bare farm (not farmhouse)
    if "farm" in blob and "farmhouse" not in blob and "farm house" not in blob and "farmhouse" not in blob:
        if not house_hits:
            return True, "farm"
        # farm + house but strong already handled; keep farmhouse-like
        if "farmhouse" in blob or "farm house" in blob:
            return False, ""
        # "Farm" alone in chinese mapped hack dumps usually production
        if not any(h in blob for h in ("house", "home", "cottage", "villa", "loft")):
            return True, "farm"
    # towers: for chinese keep pagoda-like; for others demote bare tower arenas
    if not allow_chinese_tower:
        if ("tower" in blob or "塔" in blob) and not house_hits:
            if any(x in blob for x in ("xp", "spawn", "arena", "parkour", "statue", "sw_tower", "twins")):
                return True, "towerish"
    # statue/arena/parkour
    for t in ("statue", "sculpture", "arena", "parkour", "challenge"):
        if t in blob and not house_hits:
            return True, t
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
                    if k in (
                        "exclude_from_residential",
                        "exclude_reason",
                        "retag_note",
                        "previous_mapped_style",
                        "residential_loft_topup",
                        "long_fill_tag",
                    ):
                        it[k] = v
            break
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")


def count_style(index_dir: Path, style: str) -> dict:
    man = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    items = man.get("items") or []
    st = [it for it in items if (it.get("mapped_style") or "").lower() == style]
    mc = [it for it in st if "mcblock" in (it.get("source_path") or "").replace("\\", "/").lower()]
    ok = [it for it in mc if not it.get("exclude_from_residential")]
    return {
        "mapped": len(st),
        "mcblock": len(mc),
        "mcblock_resid_ok": len(ok),
        "excluded_in_style": sum(1 for it in st if it.get("exclude_from_residential")),
    }


def demote_style_farms(index_dir: Path, style: str, *, allow_chinese_tower: bool = False) -> dict:
    man = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    items = man.get("items") or []
    demoted = []
    kept = []
    for it in items:
        if (it.get("mapped_style") or "").lower() != style:
            continue
        if it.get("exclude_from_residential"):
            kept.append(it["id"])
            continue
        bad, tok = is_farmish_path(it, allow_chinese_tower=allow_chinese_tower)
        if bad:
            demoted.append({"id": it["id"], "token": tok, "was": style})
            _override_feature(
                it["id"],
                mapped_style="unknown",
                extra={
                    "exclude_from_residential": True,
                    "exclude_reason": "public_production",
                    "retag_note": f"long_fill_demote_from_{style}:{tok}",
                    "previous_mapped_style": style,
                },
                index_dir=index_dir,
            )
        else:
            kept.append(it["id"])
    return {"demoted": demoted, "kept_ids": kept, "demoted_n": len(demoted), "kept_n": len(kept)}


def merge_detail(it: dict, sleep_s: float) -> dict:
    """Always get_building to fill projectionFileUrl / primaryType."""
    bid = it.get("id")
    if not bid:
        return it
    url = it.get("projectionFileUrl") or it.get("downloadUrl")
    if url and it.get("primaryType") and it.get("styles"):
        # still refresh if missing residential signals for borderline
        pass
    try:
        detail = get_building(bid)
        time.sleep(sleep_s)
    except Exception as e:
        it["_detail_error"] = str(e)
        return it
    for k in (
        "primaryType",
        "styles",
        "tags",
        "name",
        "description",
        "projectionFileUrl",
        "downloadUrl",
        "width",
        "height",
        "depth",
        "blockCount",
    ):
        if detail.get(k) is not None:
            it[k] = detail[k]
    it["_detail_merged"] = True
    return it


def try_add(
    it,
    *,
    target_style: str,
    added,
    skipped,
    failed,
    known_ids,
    existing_ids,
    man,
    out_dir,
    index_dir,
    sleep_s: float,
    max_edge: int,
    max_blocks: int,
    embed: bool,
    tag: str,
):
    bid = it.get("id")
    if not bid:
        return
    if bid in known_ids or bid in existing_ids:
        # also check feature ids that use name__idprefix
        skipped["already"] += 1
        return
    # always detail-merge before size/house checks when list is thin
    it = merge_detail(it, sleep_s)
    if bid in known_ids:
        skipped["already"] += 1
        return
    w, h, d = it.get("width") or 0, it.get("height") or 0, it.get("depth") or 0
    bc = it.get("blockCount") or 0
    if max(int(w or 0), int(h or 0), int(d or 0)) > max_edge or (bc and int(bc) > max_blocks):
        skipped["too_big"] += 1
        return
    ok, reason = is_house(it)
    if not ok:
        skipped[f"reject:{reason}"] += 1
        return
    styles_l = [str(x).lower() for x in (it.get("styles") or [])]
    if styles_l and target_style not in styles_l and target_style != "any":
        # allow residential primary with strong house evidence even if multi-tagged
        if not (reason.startswith("house_kw") or reason.startswith("primary")):
            skipped["style_mismatch"] += 1
            return
        # if industrial target, require industrial OR loft/warehouse house_kw
        if target_style == "industrial":
            loftish = any(k in _blob(it) for k in ("loft", "warehouse", "workshop", "factory", "industrial", "工业", "厂房", "砖"))
            if "industrial" not in styles_l and not loftish and reason != "primary:residential":
                skipped["not_industrialish"] += 1
                return
    url = it.get("projectionFileUrl") or it.get("downloadUrl")
    if not url:
        skipped["no_url_after_detail"] += 1
        return
    try:
        dest = download_projection(it, out_dir)
        time.sleep(sleep_s)
    except Exception as e:
        failed.append({"id": bid, "error": f"dl:{e}"})
        return
    if not dest or not dest.exists():
        failed.append({"id": bid, "error": "no_file"})
        return
    # dedupe by dest stem vs existing feature ids
    stem_hint = dest.stem
    row = {
        "id": bid,
        "name": it.get("name"),
        "styles": it.get("styles") or [target_style],
        "primaryType": it.get("primaryType"),
        "width": w,
        "height": h,
        "depth": d,
        "blockCount": bc,
        "file": str(dest.relative_to(ROOT)).replace("/", "\\"),
        "projectionFileUrl": url,
        "_picked_style": target_style,
        "_keep_reason": reason,
        "_long_fill": True,
        "_tag": tag,
    }
    man.append(row)
    known_ids.add(bid)
    try:
        feat = extract_reference_features(
            dest,
            skeleton_size=32,
            index_dir=index_dir,
            write=True,
            embed_block2vec=bool(embed),
        )
        fid = feat["id"]
        if fid in existing_ids and not feat:
            skipped["already_feat"] += 1
            return
        _override_feature(
            fid,
            mapped_style=target_style,
            extra={"residential_loft_topup": True, "long_fill_tag": tag},
            index_dir=index_dir,
        )
        existing_ids.add(fid)
        existing_ids.add(bid)
        added.append({"id": fid, "bid": bid, "name": it.get("name"), "reason": reason, "file": row["file"], "style": target_style})
        print(f"  ADD {target_style} {fid} ({it.get('name')}) [{reason}]", flush=True)
    except Exception as e:
        failed.append({"id": bid, "error": f"ingest:{e}"})
        print(f"  INGEST FAIL {dest.name}: {e}", flush=True)


def discover_and_add(
    *,
    target_style: str,
    queries: list[str],
    cap: int,
    max_pages: int,
    limit: int,
    sleep_s: float,
    max_edge: int,
    max_blocks: int,
    embed: bool,
    tag: str,
    index_dir: Path,
    out_dir: Path,
    man_path: Path,
    use_style_filter: bool = True,
):
    added = []
    skipped = Counter()
    failed = []
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else []
    known_ids = {it.get("id") for it in man if it.get("id")}
    idx = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    existing_ids = {it.get("id") for it in (idx.get("items") or [])}
    # also add mcblock id prefixes from source paths
    for it in idx.get("items") or []:
        sp = (it.get("source_path") or "").replace("\\", "/")
        if "__" in sp:
            # name__xxxxxxxx.litematic
            stem = Path(sp).stem
            if "__" in stem:
                existing_ids.add(stem.split("__")[-1])

    def _run_batch(items):
        for it in items:
            if len(added) >= cap:
                break
            try_add(
                it,
                target_style=target_style,
                added=added,
                skipped=skipped,
                failed=failed,
                known_ids=known_ids,
                existing_ids=existing_ids,
                man=man,
                out_dir=out_dir,
                index_dir=index_dir,
                sleep_s=sleep_s,
                max_edge=max_edge,
                max_blocks=max_blocks,
                embed=embed,
                tag=tag,
            )

    for sort in ("recommended", "latest"):
        if len(added) >= cap:
            break
        styles = [target_style] if use_style_filter else None
        print(f"discover style={target_style if use_style_filter else None} sort={sort}", flush=True)
        try:
            items = list_buildings(
                limit=limit,
                max_pages=max_pages,
                sort=sort,
                styles=styles,
                difficulties=None,
                max_blocks=None,
                max_width=None,
                max_depth=None,
                search_q=None,
                sleep_s=sleep_s,
            )
        except Exception as e:
            failed.append({"phase": "list_style", "sort": sort, "error": str(e)})
            print(f"  FAIL list: {e}", flush=True)
            time.sleep(1.2)
            continue
        print(f"  got {len(items)} raw", flush=True)
        _run_batch(items)

    for q in queries:
        if len(added) >= cap:
            break
        print(f"discover q={q!r}", flush=True)
        try:
            items = list_buildings(
                limit=min(30, limit),
                max_pages=2,
                sort="recommended",
                styles=[target_style] if use_style_filter else None,
                difficulties=None,
                max_blocks=None,
                max_width=None,
                max_depth=None,
                search_q=q,
                sleep_s=sleep_s,
            )
        except Exception as e:
            failed.append({"phase": "list_q", "q": q, "error": str(e)})
            print(f"  FAIL q: {e}", flush=True)
            continue
        print(f"  got {len(items)} for q", flush=True)
        _run_batch(items)

    save_manifest(man, man_path)
    return {
        "added": added,
        "added_n": len(added),
        "skipped": dict(skipped),
        "failed": failed[:40],
        "failed_n": len(failed),
    }


def retrieval_smoke(index_dir: Path, styles: list[str], k: int = 5) -> dict:
    from src.app import gen_strategy

    out = {}
    for style in styles:
        try:
            # try common APIs
            hits = None
            if hasattr(gen_strategy, "retrieve_style_references"):
                hits = gen_strategy.retrieve_style_references(style=style, top_k=k, index_dir=index_dir)
            elif hasattr(gen_strategy, "find_similar_references"):
                hits = gen_strategy.find_similar_references(style=style, top_k=k)
            else:
                # fallback: scan index ranked by prefer residential + mcblock
                man = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
                items = [
                    it
                    for it in (man.get("items") or [])
                    if (it.get("mapped_style") or "").lower() == style and not it.get("exclude_from_residential")
                ]
                items.sort(
                    key=lambda it: (
                        0 if "mcblock" in (it.get("source_path") or "").lower() else 1,
                        -(it.get("block2vec_norm") or it.get("score") or 0),
                    )
                )
                hits = items[:k]
            rows = []
            for h in hits or []:
                if isinstance(h, dict):
                    rows.append(
                        {
                            "id": h.get("id"),
                            "score": h.get("score") or h.get("sim"),
                            "mcblock": "mcblock" in (h.get("source_path") or h.get("id") or "").lower()
                            or "__" in (h.get("id") or ""),
                            "exclude": bool(h.get("exclude_from_residential")),
                        }
                    )
                else:
                    rows.append({"id": str(h)})
            out[style] = rows
        except Exception as e:
            out[style] = {"error": str(e), "trace": traceback.format_exc()[-500:]}
    return out


def main():
    ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    report_dir = ROOT / "outputs" / "design" / f"long_fill_{ts}"
    report_dir.mkdir(parents=True, exist_ok=True)
    index_dir = ROOT / INDEX_DIR_DEFAULT
    out_dir = ROOT / "data" / "raw" / "mcblock"
    out_dir.mkdir(parents=True, exist_ok=True)
    man_path = out_dir / "manifest.json"

    before = {
        s: count_style(index_dir, s)
        for s in ["industrial", "european", "modern", "rustic", "chinese", "medieval", "fantasy"]
    }
    from src.app.redstone_templates import canonical_templates, bootstrap_templates

    rs_before = len(canonical_templates())
    bootstrap_templates(force=True)
    rs_after_boot = len(json.loads((ROOT / "data/redstone_templates/catalog.json").read_text(encoding="utf-8"))["templates"])

    print("=== A1 chinese quality demote ===", flush=True)
    cn_demote = demote_style_farms(index_dir, "chinese", allow_chinese_tower=True)
    # also demote obvious towers that are XP/arena even with allow flag — reinstate stronger pass
    # second pass: demote towerish without house for chinese if token is english tower+farm already handled
    print(f"  chinese demoted {cn_demote['demoted_n']}", flush=True)

    print("=== A2 industrial residential detail-merge pulls ===", flush=True)
    ind_before = count_style(index_dir, "industrial")
    ind_fetch = discover_and_add(
        target_style="industrial",
        queries=INDUSTRIAL_QUERIES,
        cap=14,
        max_pages=5,
        limit=40,
        sleep_s=0.55,
        max_edge=96,
        max_blocks=12000,
        embed=True,
        tag="long_fill_industrial",
        index_dir=index_dir,
        out_dir=out_dir,
        man_path=man_path,
        use_style_filter=True,
    )
    ind_after = count_style(index_dir, "industrial")

    print("=== A3 european careful house ingest ===", flush=True)
    eu_fetch = discover_and_add(
        target_style="european",
        queries=["european house", "villa", "townhouse", "欧式别墅", "欧式小屋"],
        cap=6,
        max_pages=3,
        limit=30,
        sleep_s=0.5,
        max_edge=96,
        max_blocks=10000,
        embed=True,
        tag="long_fill_european",
        index_dir=index_dir,
        out_dir=out_dir,
        man_path=man_path,
        use_style_filter=True,
    )

    print("=== A4 modern careful house ingest ===", flush=True)
    mo_fetch = discover_and_add(
        target_style="modern",
        queries=["modern house", "modern villa", "contemporary house", "现代别墅", "现代住宅"],
        cap=6,
        max_pages=3,
        limit=30,
        sleep_s=0.5,
        max_edge=96,
        max_blocks=10000,
        embed=True,
        tag="long_fill_modern",
        index_dir=index_dir,
        out_dir=out_dir,
        man_path=man_path,
        use_style_filter=True,
    )

    after = {
        s: count_style(index_dir, s)
        for s in ["industrial", "european", "modern", "rustic", "chinese", "medieval", "fantasy"]
    }

    print("=== retrieval smoke ===", flush=True)
    # Prefer gen_strategy retrieval if available
    smoke = {}
    try:
        from src.app.gen_strategy import similar_scaffold_candidates

        for style in ["industrial", "european", "modern", "rustic"]:
            try:
                cands = similar_scaffold_candidates(style=style, top_k=5, index_dir=str(index_dir))
                smoke[style] = [
                    {
                        "id": c.get("id") if isinstance(c, dict) else str(c),
                        "score": (c.get("score") if isinstance(c, dict) else None),
                        "mcblock": "mcblock" in str(c).lower() or (isinstance(c, dict) and "mcblock" in (c.get("source_path") or "").lower()),
                    }
                    for c in (cands or [])[:5]
                ]
            except Exception as e:
                smoke[style] = {"error": str(e)}
    except Exception:
        smoke = retrieval_smoke(index_dir, ["industrial", "european", "modern", "rustic"])

    # also dump top mcblock resid from index for industrial
    man = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    ind_ids = [
        it["id"]
        for it in man["items"]
        if (it.get("mapped_style") or "").lower() == "industrial"
        and "mcblock" in (it.get("source_path") or "").lower()
        and not it.get("exclude_from_residential")
    ]

    print("=== B redstone paste smoke ===", flush=True)
    paste_dir = report_dir / "paste_trapped_chest"
    paste_dir.mkdir(parents=True, exist_ok=True)
    paste_ok = False
    paste_err = None
    # find a sample npz
    sample_npz = None
    for cand in [
        ROOT / "outputs/design/full_style_v4_20261020_112642/npz/sample_seuropean_tflat_000.npz",
        ROOT / "outputs/design/full_style_v4_20261020_112642/npz/sample_sindustrial_tflat_000.npz",
    ]:
        if cand.exists():
            sample_npz = cand
            break
    if sample_npz is None:
        # search
        hits = list((ROOT / "outputs/design").glob("**/sample_s*european*.npz"))
        if hits:
            sample_npz = hits[0]
    if sample_npz and sample_npz.exists():
        try:
            from src.app.redstone_templates import paste_redstone_into_design

            res = paste_redstone_into_design(
                npz_path=sample_npz,
                template_id="trapped_chest_signal",
                out_dir=paste_dir,
                collision="air_only",
            )
            paste_ok = True
            print(f"  paste ok -> {paste_dir}", flush=True)
        except TypeError:
            # CLI fallback
            import subprocess

            cmd = [
                str(ROOT / ".venv/Scripts/python.exe"),
                str(ROOT / "scripts/paste_redstone_into_design.py"),
                "--npz",
                str(sample_npz),
                "--template",
                "trapped_chest_signal",
                "--out-dir",
                str(paste_dir),
                "--companion",
                "--companion-name",
                "欧式_陷阱箱信号桩",
            ]
            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
            paste_ok = r.returncode == 0
            paste_err = (r.stdout or "")[-800:] + "\n" + (r.stderr or "")[-800:]
            print(paste_err, flush=True)
        except Exception as e:
            paste_err = str(e)
            print(f"  paste fail: {e}", flush=True)
            # CLI fallback
            import subprocess

            cmd = [
                str(ROOT / ".venv/Scripts/python.exe"),
                str(ROOT / "scripts/paste_redstone_into_design.py"),
                "--npz",
                str(sample_npz),
                "--template",
                "trapped_chest_signal",
                "--out-dir",
                str(paste_dir),
                "--companion",
                "--companion-name",
                "欧式_陷阱箱信号桩",
            ]
            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
            paste_ok = r.returncode == 0
            paste_err = (r.stdout or "")[-800:] + "\n" + (r.stderr or "")[-800:]
    else:
        paste_err = "no sample npz found"

    # optional similar_scaffold sample
    sample_dir = report_dir / "industrial_sample"
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_note = None
    try:
        import subprocess

        cmd = [
            str(ROOT / ".venv/Scripts/python.exe"),
            str(ROOT / "scripts/sample.py"),
            "--style",
            "industrial",
            "--n",
            "1",
            "--out-dir",
            str(sample_dir),
            "--structure-constrain",
            "--gen-strategy",
            "similar_scaffold",
        ]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        sample_note = {"rc": r.returncode, "tail": ((r.stdout or "") + (r.stderr or ""))[-1200:]}
        (sample_dir / "console.txt").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    except Exception as e:
        sample_note = {"error": str(e)}

    new_rs_ids = [
        "note_block_alert",
        "dropper_dispenser_pulse",
        "water_stream_item_tiny",
        "trapped_chest_signal",
        "daylight_sensor_lamp_stub",
        "pressure_plate_iron_door",
    ]
    cat_ids = [t["id"] for t in json.loads((ROOT / "data/redstone_templates/catalog.json").read_text(encoding="utf-8"))["templates"]]

    counts_md = []
    counts_md.append(f"# Long fill COUNTS\n")
    counts_md.append(f"Finished: {_now()} (Asia/Shanghai)\n")
    counts_md.append("\n## Styles (mapped / mcblock / mcblock_resid_ok)\n")
    counts_md.append("| style | before mapped | after mapped | before mcblock | after mcblock | before ok | after ok |\n")
    counts_md.append("|---|---:|---:|---:|---:|---:|---:|\n")
    for s in ["industrial", "european", "modern", "rustic", "chinese", "medieval", "fantasy"]:
        b, a = before[s], after[s]
        counts_md.append(
            f"| {s} | {b['mapped']} | {a['mapped']} | {b['mcblock']} | {a['mcblock']} | {b['mcblock_resid_ok']} | {a['mcblock_resid_ok']} |\n"
        )
    counts_md.append(f"\n## Chinese demote\n- demoted_n: **{cn_demote['demoted_n']}** (exclude_from_residential / mapped→unknown)\n")
    counts_md.append(f"\n## Industrial fetch\n- added_n: **{ind_fetch['added_n']}**\n- skipped: `{json.dumps(ind_fetch['skipped'], ensure_ascii=False)}`\n")
    counts_md.append(f"\n## European fetch\n- added_n: **{eu_fetch['added_n']}**\n")
    counts_md.append(f"\n## Modern fetch\n- added_n: **{mo_fetch['added_n']}**\n")
    counts_md.append(f"\n## Redstone templates\n- before: **{rs_before}**\n- after catalog: **{len(cat_ids)}**\n- new ids: `{new_rs_ids}`\n")
    counts_md.append(f"\n## Paste smoke\n- ok: {paste_ok}\n- dir: `{paste_dir}`\n")
    (report_dir / "COUNTS.md").write_text("".join(counts_md), encoding="utf-8")

    summary = {
        "finished_at": _now(),
        "before": before,
        "after": after,
        "chinese_demote": {"demoted_n": cn_demote["demoted_n"], "sample": cn_demote["demoted"][:30]},
        "industrial_fetch": ind_fetch,
        "european_fetch": eu_fetch,
        "modern_fetch": mo_fetch,
        "industrial_mcblock_ids": ind_ids,
        "redstone": {
            "before": rs_before,
            "after": len(cat_ids),
            "new_ids": new_rs_ids,
            "all_ids": cat_ids,
        },
        "smoke_retrieval": smoke,
        "paste": {"ok": paste_ok, "dir": str(paste_dir), "err": paste_err},
        "sample": sample_note,
        "residuals": [
            "No VAE train (by design).",
            "Did not overwrite companion early-tech Chinese furnace/iron/XP names.",
            "look_harden facade knobs untouched.",
            "Industrial loft search_q historically empty; relied on style listing + detail merge.",
            "Chinese demote is path/name heuristic; pagoda/temple kept via allow_chinese_tower + house keywords.",
        ],
    }
    (report_dir / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "smoke_retrieval.json").write_text(json.dumps(smoke, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "COUNTS.md").write_text("".join(counts_md), encoding="utf-8")

    # append docs
    rs_doc = ROOT / "docs" / "redstone_templates.md"
    if rs_doc.exists():
        extra = (
            f"\n\n## Long fill stubs (2026-10-20)\n\n"
            f"Catalog **{rs_before} → {len(cat_ids)}**. New house-usable teaching stubs: "
            + ", ".join(f"`{i}`" for i in new_rs_ids)
            + f". Report: `outputs/design/long_fill_{ts}/`.\n"
        )
        txt = rs_doc.read_text(encoding="utf-8")
        if "note_block_alert" not in txt:
            rs_doc.write_text(txt + extra, encoding="utf-8")

    lh = ROOT / "docs" / "look_harden.md"
    if lh.exists():
        extra = (
            f"\n\n## Long fill residential refs (2026-10-20)\n\n"
            f"No facade knob changes. Industrial mcblock resid "
            f"{before['industrial']['mcblock']}→{after['industrial']['mcblock']}; "
            f"chinese farmish demoted {cn_demote['demoted_n']}. "
            f"See `outputs/design/long_fill_{ts}/COUNTS.md`.\n"
        )
        txt = lh.read_text(encoding="utf-8")
        if f"long_fill_{ts}" not in txt:
            lh.write_text(txt + extra, encoding="utf-8")

    print("DONE", report_dir, flush=True)
    print("industrial mcblock", before["industrial"]["mcblock"], "->", after["industrial"]["mcblock"], flush=True)
    print("templates", rs_before, "->", len(cat_ids), flush=True)


if __name__ == "__main__":
    main()
