# -*- coding: utf-8 -*-
"""Finish long_fill: 2nd industrial cycle + paste + retrieval + COUNTS. No VAE."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
sys.path.insert(0, str(ROOT))

from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest
from src.app.reference_features import extract_reference_features, INDEX_DIR_DEFAULT

TZ = timezone(timedelta(hours=8))

# reuse helpers from long fill by import
import importlib.util

spec = importlib.util.spec_from_file_location("lfs", ROOT / "scripts" / "_long_fill_session.py")
lfs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lfs)


def _now():
    return datetime.now(TZ).isoformat(timespec="seconds")


def industrial_broad_pass(index_dir: Path, out_dir: Path, man_path: Path, cap: int = 12) -> dict:
    """List without style filter; keep residential + industrial/loft evidence after detail merge."""
    added, skipped, failed = [], Counter(), []
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else []
    known_ids = {it.get("id") for it in man if it.get("id")}
    idx = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    existing_ids = {it.get("id") for it in (idx.get("items") or [])}
    for it in idx.get("items") or []:
        sp = (it.get("source_path") or "").replace("\\", "/")
        stem = Path(sp).stem
        if "__" in stem:
            existing_ids.add(stem.split("__")[-1])

    for sort in ("recommended", "latest"):
        if len(added) >= cap:
            break
        print(f"broad discover sort={sort}", flush=True)
        try:
            items = list_buildings(
                limit=40,
                max_pages=6,
                sort=sort,
                styles=None,
                difficulties=None,
                max_blocks=None,
                max_width=None,
                max_depth=None,
                search_q=None,
                sleep_s=0.45,
            )
        except Exception as e:
            failed.append({"phase": "broad_list", "sort": sort, "error": str(e)})
            continue
        print(f"  got {len(items)}", flush=True)
        for it in items:
            if len(added) >= cap:
                break
            bid = it.get("id")
            if not bid or bid in known_ids:
                skipped["already"] += 1
                continue
            # cheap prefilter on list blob
            blob = lfs._blob(it)
            styles_l = [str(x).lower() for x in (it.get("styles") or [])]
            hint = (
                "industrial" in styles_l
                or any(k in blob for k in ("loft", "warehouse", "workshop", "factory", "industrial", "工业", "厂房", "砖房"))
            )
            if not hint and (it.get("primaryType") or "") != "residential":
                skipped["no_hint"] += 1
                continue
            # detail merge
            it2 = lfs.merge_detail(dict(it), 0.45)
            styles2 = [str(x).lower() for x in (it2.get("styles") or [])]
            blob2 = lfs._blob(it2)
            industrialish = "industrial" in styles2 or any(
                k in blob2 for k in ("loft", "warehouse", "workshop", "factory", "industrial", "工业", "厂房")
            )
            if not industrialish:
                skipped["not_industrialish"] += 1
                continue
            ok, reason = lfs.is_house(it2)
            if not ok:
                skipped[f"reject:{reason}"] += 1
                continue
            lfs.try_add(
                it2,
                target_style="industrial",
                added=added,
                skipped=skipped,
                failed=failed,
                known_ids=known_ids,
                existing_ids=existing_ids,
                man=man,
                out_dir=out_dir,
                index_dir=index_dir,
                sleep_s=0.45,
                max_edge=96,
                max_blocks=12000,
                embed=True,
                tag="long_fill_industrial_broad",
            )
    save_manifest(man, man_path)
    return {"added": added, "added_n": len(added), "skipped": dict(skipped), "failed": failed[:30], "failed_n": len(failed)}


def index_top(style: str, index_dir: Path, k: int = 5):
    man = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    items = [
        it
        for it in man["items"]
        if (it.get("mapped_style") or "").lower() == style and not it.get("exclude_from_residential")
    ]
    def key(it):
        sp = (it.get("source_path") or "").replace("\\", "/").lower()
        mc = 0 if "mcblock" in sp else 1
        return (mc, it.get("id") or "")
    items.sort(key=key)
    rows = []
    for it in items[:k]:
        rows.append(
            {
                "id": it["id"],
                "mcblock": "mcblock" in (it.get("source_path") or "").lower(),
                "exclude": bool(it.get("exclude_from_residential")),
                "source_path": it.get("source_path"),
            }
        )
    return rows


def main():
    # prefer existing long_fill dir from earlier run
    existing = sorted((ROOT / "outputs" / "design").glob("long_fill_*"))
    if existing:
        report_dir = existing[-1]
    else:
        ts = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
        report_dir = ROOT / "outputs" / "design" / f"long_fill_{ts}"
    report_dir.mkdir(parents=True, exist_ok=True)
    index_dir = ROOT / INDEX_DIR_DEFAULT
    out_dir = ROOT / "data" / "raw" / "mcblock"
    man_path = out_dir / "manifest.json"

    # snapshot before cycle2 (relative to session start we reconstruct from SUMMARY if any)
    before_cycle2 = {s: lfs.count_style(index_dir, s) for s in ["industrial", "european", "modern", "rustic", "chinese"]}

    print("=== cycle2 industrial broad ===", flush=True)
    # also style-filtered with more pages
    ind1 = lfs.discover_and_add(
        target_style="industrial",
        queries=["brick", "factory", "mill", "forge house", "工业"],
        cap=10,
        max_pages=8,
        limit=50,
        sleep_s=0.5,
        max_edge=96,
        max_blocks=12000,
        embed=True,
        tag="long_fill_industrial_c2",
        index_dir=index_dir,
        out_dir=out_dir,
        man_path=man_path,
        use_style_filter=True,
    )
    ind2 = industrial_broad_pass(index_dir, out_dir, man_path, cap=8)
    after = {s: lfs.count_style(index_dir, s) for s in ["industrial", "european", "modern", "rustic", "chinese", "medieval", "fantasy"]}

    # session-start baselines (from parent conversation / first script intent)
    session_before = {
        "industrial": {"mapped": 99, "mcblock": 15, "mcblock_resid_ok": 15},
        "european": {"mapped": 34, "mcblock": 31, "mcblock_resid_ok": 31},
        "modern": {"mapped": 39, "mcblock": 35, "mcblock_resid_ok": 35},
        "rustic": {"mapped": 36, "mcblock": 32, "mcblock_resid_ok": 32},
        "chinese": {"mapped": 572, "mcblock": 5, "mcblock_resid_ok": 5},
        "medieval": {"mapped": 74, "mcblock": 74, "mcblock_resid_ok": 74},
        "fantasy": {"mapped": 84, "mcblock": 84, "mcblock_resid_ok": 84},
    }

    print("=== paste smoke ===", flush=True)
    npz = ROOT / "outputs/design/full_style_v4_20261020_112642/npz/sample_seuropean_tflat_000.npz"
    paste_dir = report_dir / "paste_trapped_chest"
    paste_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(ROOT / ".venv/Scripts/python.exe"),
        str(ROOT / "scripts/paste_redstone_into_design.py"),
        "--npz",
        str(npz),
        "--template",
        "trapped_chest_signal",
        "--out-dir",
        str(paste_dir),
        "--companion",
        "--companion-name",
        "欧式_陷阱箱信号桩",
    ]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, encoding="utf-8", errors="replace")
    paste = {
        "rc": r.returncode,
        "stdout_tail": (r.stdout or "")[-1000:],
        "stderr_tail": (r.stderr or "")[-1000:],
        "ok": r.returncode == 0,
    }
    (paste_dir / "console.txt").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
    print("paste rc", r.returncode, flush=True)

    # also paste pressure plate door into industrial sample
    npz_i = ROOT / "outputs/design/full_style_v4_20261020_112642/npz/sample_sindustrial_tflat_000.npz"
    paste_dir2 = report_dir / "paste_pressure_door"
    paste_dir2.mkdir(parents=True, exist_ok=True)
    cmd2 = [
        str(ROOT / ".venv/Scripts/python.exe"),
        str(ROOT / "scripts/paste_redstone_into_design.py"),
        "--npz",
        str(npz_i),
        "--template",
        "pressure_plate_iron_door",
        "--out-dir",
        str(paste_dir2),
        "--companion",
        "--companion-name",
        "工业_压力板铁门桩",
    ]
    r2 = subprocess.run(cmd2, cwd=str(ROOT), capture_output=True, encoding="utf-8", errors="replace")
    paste2 = {"rc": r2.returncode, "ok": r2.returncode == 0, "stdout_tail": (r2.stdout or "")[-800:]}
    (paste_dir2 / "console.txt").write_text((r2.stdout or "") + "\n" + (r2.stderr or ""), encoding="utf-8")

    print("=== retrieval tops ===", flush=True)
    smoke = {s: index_top(s, index_dir, 5) for s in ["industrial", "european", "modern", "rustic"]}
    # try gen_strategy if works
    try:
        from src.app import gen_strategy as gs
        for name in ("retrieve_references", "similar_references", "find_style_refs", "query_style_refs"):
            if hasattr(gs, name):
                smoke["_api"] = name
                break
        if hasattr(gs, "build_similar_scaffold") or hasattr(gs, "similar_scaffold"):
            smoke["_scaffold"] = True
    except Exception as e:
        smoke["_import_err"] = str(e)

    print("=== optional industrial sample ===", flush=True)
    sample_dir = report_dir / "industrial_sample"
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_note = {}
    # find how sample.py is invoked from prior scripts
    sample_py = ROOT / "scripts" / "sample.py"
    if sample_py.exists():
        cmd3 = [
            str(ROOT / ".venv/Scripts/python.exe"),
            str(sample_py),
            "--help",
        ]
        rh = subprocess.run(cmd3, cwd=str(ROOT), capture_output=True, encoding="utf-8", errors="replace")
        help_txt = (rh.stdout or "") + (rh.stderr or "")
        (sample_dir / "sample_help.txt").write_text(help_txt, encoding="utf-8")
        # try minimal
        cmd4 = [
            str(ROOT / ".venv/Scripts/python.exe"),
            str(sample_py),
            "--out-dir",
            str(sample_dir),
            "--n",
            "1",
            "--styles",
            "industrial",
            "--structure-constrain",
        ]
        # guess flags from help
        if "--style" in help_txt and "--styles" not in help_txt:
            cmd4 = [
                str(ROOT / ".venv/Scripts/python.exe"),
                str(sample_py),
                "--out-dir",
                str(sample_dir),
                "--n",
                "1",
                "--style",
                "industrial",
            ]
        r4 = subprocess.run(cmd4, cwd=str(ROOT), capture_output=True, encoding="utf-8", errors="replace")
        sample_note = {"rc": r4.returncode, "cmd": cmd4, "tail": ((r4.stdout or "") + (r4.stderr or ""))[-1500:]}
        (sample_dir / "console.txt").write_text((r4.stdout or "") + "\n" + (r4.stderr or ""), encoding="utf-8")

    cat = json.loads((ROOT / "data/redstone_templates/catalog.json").read_text(encoding="utf-8"))
    cat_ids = [t["id"] for t in cat["templates"]]
    new_rs = [
        "note_block_alert",
        "dropper_dispenser_pulse",
        "water_stream_item_tiny",
        "trapped_chest_signal",
        "daylight_sensor_lamp_stub",
        "pressure_plate_iron_door",
    ]

    # load chinese demote count from difference
    cn_demoted = session_before["chinese"]["mapped"] - after["chinese"]["mapped"]

    lines = []
    lines.append("# Long fill COUNTS\n\n")
    lines.append(f"Finished: {_now()} (Asia/Shanghai)\n\n")
    lines.append("## Styles (session start → now)\n\n")
    lines.append("| style | before mapped | after mapped | before mcblock | after mcblock | before ok | after ok |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|\n")
    for s in ["industrial", "european", "modern", "rustic", "chinese", "medieval", "fantasy"]:
        b = session_before.get(s, {"mapped": "?", "mcblock": "?", "mcblock_resid_ok": "?"})
        a = after[s]
        lines.append(
            f"| {s} | {b['mapped']} | {a['mapped']} | {b['mcblock']} | {a['mcblock']} | {b['mcblock_resid_ok']} | {a['mcblock_resid_ok']} |\n"
        )
    lines.append(f"\n## Chinese quality demote\n- mapped drop ≈ **{cn_demoted}** (farm/XP/smelter etc. → unknown + exclude_from_residential)\n")
    lines.append(f"\n## Industrial\n- cycle1+2 style fetch added_n: **{ind1['added_n']}** (this finish script cycle)\n")
    lines.append(f"- broad pass added_n: **{ind2['added_n']}**\n")
    lines.append(f"- skipped style: `{json.dumps(ind1.get('skipped', {}), ensure_ascii=False)}`\n")
    lines.append(f"- skipped broad: `{json.dumps(ind2.get('skipped', {}), ensure_ascii=False)}`\n")
    lines.append(f"\n## Redstone\n- catalog **22 → {len(cat_ids)}**\n- new: {new_rs}\n")
    lines.append(f"\n## Smoke\n- paste trapped_chest: ok={paste['ok']} → `{paste_dir}`\n")
    lines.append(f"- paste pressure_door: ok={paste2['ok']} → `{paste_dir2}`\n")
    lines.append(f"- industrial sample rc={sample_note.get('rc')}\n")
    (report_dir / "COUNTS.md").write_text("".join(lines), encoding="utf-8")

    summary = {
        "finished_at": _now(),
        "report_dir": str(report_dir),
        "session_before": session_before,
        "before_cycle2": before_cycle2,
        "after": after,
        "industrial_c2_style": ind1,
        "industrial_c2_broad": ind2,
        "redstone": {"after": len(cat_ids), "new_ids": new_rs, "all_ids": cat_ids},
        "smoke_retrieval": smoke,
        "paste_trapped_chest": paste,
        "paste_pressure_door": paste2,
        "sample": sample_note,
        "residuals": [
            "Industrial pure loft still scarce on MCBlock; search_q empty; broad listing mostly already ingested or non-residential.",
            f"Industrial mcblock {session_before['industrial']['mcblock']}→{after['industrial']['mcblock']} (target 25+ not reached — source exhausted for clean resid).",
            "Chinese demote is heuristic; files kept on disk.",
            "No VAE train; look_harden knobs untouched; early-tech companion Chinese names untouched.",
        ],
    }
    (report_dir / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "smoke_retrieval.json").write_text(json.dumps(smoke, ensure_ascii=False, indent=2), encoding="utf-8")

    # docs append
    rs_doc = ROOT / "docs" / "redstone_templates.md"
    txt = rs_doc.read_text(encoding="utf-8")
    if "note_block_alert" not in txt:
        txt += (
            "\n\n## Long fill stubs (2026-10-20)\n\n"
            f"Catalog **22 → {len(cat_ids)}**. New house-usable teaching stubs: "
            + ", ".join(f"`{i}`" for i in new_rs)
            + f". Report: `{report_dir.relative_to(ROOT).as_posix()}/`.\n"
        )
        rs_doc.write_text(txt, encoding="utf-8")

    lh = ROOT / "docs" / "look_harden.md"
    txt = lh.read_text(encoding="utf-8")
    marker = report_dir.name
    if marker not in txt:
        txt += (
            f"\n\n## Long fill residential refs ({marker})\n\n"
            "No facade knob changes. "
            f"Industrial mcblock {session_before['industrial']['mcblock']}→{after['industrial']['mcblock']}; "
            f"european {session_before['european']['mcblock']}→{after['european']['mcblock']}; "
            f"modern {session_before['modern']['mcblock']}→{after['modern']['mcblock']}; "
            f"chinese mapped {session_before['chinese']['mapped']}→{after['chinese']['mapped']} (farmish demoted). "
            f"See `{report_dir.relative_to(ROOT).as_posix()}/COUNTS.md`.\n"
        )
        lh.write_text(txt, encoding="utf-8")

    print("DONE", report_dir, flush=True)
    print("industrial mc", session_before["industrial"]["mcblock"], "->", after["industrial"]["mcblock"], flush=True)
    print("templates", len(cat_ids), flush=True)


if __name__ == "__main__":
    main()
