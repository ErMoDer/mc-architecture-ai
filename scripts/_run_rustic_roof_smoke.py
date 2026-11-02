# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.structure_constraints import (
    SCAFFOLD_THRESHOLDS,
    check_structure,
    compute_structure_metrics,
)
from src.app.sample_runner import save_voxels_pair
from src.utils import load_config, load_palette


def main() -> None:
    root = project_root()
    cfg = load_config(root / "configs/default.yaml")
    palette = load_palette(root / cfg["data"]["palette_path"])

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = root / "outputs" / "design" / ("rustic_roof_fix_" + stamp)
    for sub in ("previews", "attach_previews", "npz", "mcfunction", "raw_by_case"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    before = {
        "湖畔小屋第二弹__94251ef3": {"roof_score": 0.029, "structure_ok": False},
        "湖畔居所第二弹__65413d8a": {"roof_score": 0.075, "structure_ok": False},
        "白色野营帐篷__290a3ff2": {"roof_score": 0.628, "structure_ok": True},
    }

    cases = [
        ("rustic", "flat", 3, 201),
        ("fantasy", "flat", 2, 301),
    ]
    all_rows: list[dict] = []
    for style, terrain, num, seed0 in cases:
        rows = generate_similar_scaffold(
            style=style,
            terrain=terrain,
            num=num,
            out_dir=out / "raw_by_case" / style,
            seed=seed0,
            top_k_refs=3,
            vae_fill=False,
            look_harden_enable=True,
        )
        for i, meta in enumerate(rows):
            vox = meta["voxels"]
            st = meta.get("structure") or {}
            m = (st.get("metrics") if isinstance(st, dict) else None) or compute_structure_metrics(
                vox
            )
            ok = (
                bool(st.get("ok"))
                if isinstance(st, dict)
                else check_structure(vox, SCAFFOLD_THRESHOLDS).ok
            )
            rid = meta.get("reference_id") or ""
            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            saved = save_voxels_pair(vox, palette, out / "npz" / (stem + ".npz"))
            row = {
                "stem": stem,
                "style": style,
                "terrain": terrain,
                "reference_id": rid,
                "structure_ok": ok,
                "roof_score": float(m.get("roof_score") or 0),
                "top_footprint_cover": float(m.get("top_footprint_cover") or 0),
                "top_footprint_cover_all": float(m.get("top_footprint_cover_all") or 0),
                "elevated_footprint": float(m.get("elevated_footprint") or 0),
                "non_air": int(m.get("non_air") or 0),
                "top_y": float(m.get("top_y") or -1),
                "footprint": int(m.get("footprint") or 0),
                "reasons": st.get("reasons") if isinstance(st, dict) else [],
                "scaffold": meta.get("scaffold"),
                "before": before.get(rid),
                "npz": str(saved.get("npz_path") or ""),
                "preview": "",
            }
            for cand in (
                saved.get("preview_path"),
                meta.get("preview_path"),
                meta.get("preview"),
            ):
                if cand and Path(cand).is_file():
                    dest = out / "previews" / (stem + ".png")
                    shutil.copy2(cand, dest)
                    row["preview"] = str(dest.relative_to(out)).replace("\\", "/")
                    if style == "rustic" or i < 2:
                        shutil.copy2(cand, out / "attach_previews" / (stem + ".png"))
                    break
            # mcfunction copy if present
            mcf = meta.get("mcfunction_path") or meta.get("mcfunction")
            if mcf and Path(mcf).is_file():
                shutil.copy2(mcf, out / "mcfunction" / Path(mcf).name)
            all_rows.append(row)
            print(
                stem,
                "ok",
                ok,
                "roof",
                round(row["roof_score"], 3),
                "ref",
                (rid[:24] if rid else "-"),
            )

    rustic_rows = [r for r in all_rows if r["style"] == "rustic"]
    fantasy_rows = [r for r in all_rows if r["style"] == "fantasy"]
    rustic_ok = sum(1 for r in rustic_rows if r["structure_ok"])
    fantasy_ok = sum(1 for r in fantasy_rows if r["structure_ok"])

    report = {
        "started_note": "rustic roof scaffold/checker fix",
        "out_dir": str(out),
        "time_zone": "Asia/Shanghai",
        "stamp": stamp,
        "no_train": True,
        "counts": {
            "rustic": len(rustic_rows),
            "fantasy": len(fantasy_rows),
            "rustic_structure_ok": rustic_ok,
            "fantasy_structure_ok": fantasy_ok,
        },
        "samples": all_rows,
        "code_changes": [
            "src/app/gen_strategy.py: building footprint + low_pitch_deck roof + peri continuity",
            "src/app/structure_constraints.py: elevated footprint for roof cover; min_roof stays 0.18",
            "src/app/look_harden.py: rustic/western facade roof stays flat (no aggressive gable clear)",
        ],
    }
    (out / "REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Rustic roof fix — smoke",
        "",
        "- Time (Asia/Shanghai): %s" % stamp,
        "- Out: `%s`" % out.as_posix(),
        "- Training: **none**",
        "",
        "## Root cause",
        "",
        "1. `scaffold_from_occupancy` only painted the sparse top occupancy slice "
        "(4-9 voxels for lakeside), so roofs were ridges not decks.",
        "2. Tapered upper perimeter rings disconnected from the lower shell; "
        "`drop_float_cc` chopped the roof mass.",
        "3. Full-box ground floors inflated footprint to ~1024, so `roof_score` "
        "cover looked ~0.02 even with a real deck.",
        "4. Rustic `look_harden` pitched gable cleared the repair deck "
        "(clear~1300) and left a thin ridge.",
        "",
        "## Fix",
        "",
        "- Building footprint (skip ground fill) + **low_pitch_deck** roof; "
        "full peri walls every Y for continuity.",
        "- `_elevated_footprint` for roof cover denominator "
        "(threshold **unchanged** at min_roof=0.18).",
        "- Rustic/western facade silhouette keeps **flat** roof "
        "(scaffold already low-pitch).",
        "",
        "## Before → after (unique rustic refs)",
        "",
        "| ref | before roof | before ok | after roof | after ok |",
        "|---|---:|:---:|---:|:---:|",
    ]
    seen: set[str] = set()
    for r in rustic_rows:
        rid = r["reference_id"]
        if rid in seen:
            continue
        seen.add(rid)
        b = before.get(rid) or {}
        lines.append(
            "| `%s` | %.3f | %s | %.3f | %s |"
            % (
                rid,
                float(b.get("roof_score") or -1),
                b.get("structure_ok"),
                r["roof_score"],
                r["structure_ok"],
            )
        )
    lines += [
        "",
        "## Smoke counts",
        "",
        "- Rustic structure_ok: **%d / %d**" % (rustic_ok, len(rustic_rows)),
        "- Fantasy structure_ok: **%d / %d** (regression check)"
        % (fantasy_ok, len(fantasy_rows)),
        "",
        "## Samples",
        "",
        "| stem | style | ok | roof | cover | elev_fp | ref |",
        "|---|---|:---:|---:|---:|---:|---|",
    ]
    for r in all_rows:
        lines.append(
            "| `%s` | %s | %s | %.3f | %.3f | %.0f | `%s` |"
            % (
                r["stem"],
                r["style"],
                r["structure_ok"],
                r["roof_score"],
                r["top_footprint_cover"],
                r["elevated_footprint"],
                r["reference_id"],
            )
        )
    lines += ["", "## Code"]
    for c in report["code_changes"]:
        lines.append("- " + c)
    lines += ["", "Previews: `previews/`, `attach_previews/`."]
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("OUT", out)
    print("rustic", rustic_ok, "/", len(rustic_rows), "fantasy", fantasy_ok, "/", len(fantasy_rows))


if __name__ == "__main__":
    main()
