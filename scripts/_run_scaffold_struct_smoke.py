# -*- coding: utf-8 -*-
"""Smoke scaffold shell/floor/roof structure harden."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.sample_runner import save_voxels_pair
from src.app.structure_constraints import SCAFFOLD_THRESHOLDS, check_structure, compute_structure_metrics
from src.utils import load_config, load_palette

# before from probe (same seeds) prior to this patch
BEFORE = {
    "european": {"roof": 1.0, "hollow": 0.748, "floors": 7},
    "chinese": {"roof": 1.0, "hollow": 0.583, "floors": 8},
    "medieval": {"roof": 0.586, "hollow": 0.611, "floors": 8},
    "modern": {"roof": 1.0, "hollow": 0.656, "floors": 7},
    "rustic": {"roof": 1.0, "hollow": 0.591, "floors": 8},
    "fantasy": {"roof": 0.555, "hollow": 0.674, "floors": 7},
    "industrial": {"roof": 1.0, "hollow": 0.592, "floors": 8},
}

STYLES = [
    ("european", "flat", 1, 102),
    ("chinese", "flat", 1, 101),
    ("medieval", "flat", 1, 103),
    ("modern", "flat", 1, 104),
    ("rustic", "flat", 1, 201),
    ("fantasy", "flat", 1, 301),
    ("industrial", "flat", 1, 401),
]


def render_iso(vox, palette, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from src.app.mc_render import render_mc_voxels
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="3d")
    render_mc_voxels(ax, fig, vox, palette, performance=True)
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    root = project_root()
    cfg = load_config(root / "configs/default.yaml")
    palette = load_palette(root / cfg["data"]["palette_path"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = root / "outputs" / "design" / ("scaffold_struct_" + stamp)
    for sub in ("previews", "attach_previews", "npz", "raw_by_case"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    rows = []
    for style, terrain, num, seed0 in STYLES:
        metas = generate_similar_scaffold(
            style=style, terrain=terrain, num=num,
            out_dir=out / "raw_by_case" / style, seed=seed0,
            top_k_refs=3, vae_fill=False, look_harden_enable=True,
        )
        for i, meta in enumerate(metas):
            vox = meta["voxels"]
            st = meta.get("structure") or {}
            m = (st.get("metrics") if isinstance(st, dict) else None) or compute_structure_metrics(vox)
            ok = bool(st.get("ok")) if isinstance(st, dict) else check_structure(vox, SCAFFOLD_THRESHOLDS).ok
            sc = meta.get("scaffold") or {}
            b = BEFORE.get(style) or {}
            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            save_voxels_pair(vox, palette, out / "npz" / (stem + ".npz"))
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "roof_after": float(m.get("roof_score") or 0),
                "roof_before": b.get("roof"),
                "hollow_after": float(m.get("hollow_score") or 0),
                "hollow_before": b.get("hollow"),
                "floor_guess_after": m.get("floor_guess"),
                "floor_guess_before": b.get("floors"),
                "largest_cc_frac": float(m.get("largest_cc_frac") or 0),
                "top_footprint_cover": float(m.get("top_footprint_cover") or 0),
                "scaffold_floor_ys": sc.get("floor_ys"),
                "scaffold_roof_mode": sc.get("roof_mode"),
                "shell_seal": sc.get("shell_seal"),
                "shell": sc.get("shell"),
                "floors_cells": sc.get("floors"),
                "roof_cells": sc.get("roof"),
            }
            png = out / "previews" / (stem + ".png")
            try:
                render_iso(vox, palette, png)
                shutil.copy2(png, out / "attach_previews" / (stem + ".png"))
                row["preview"] = "previews/" + stem + ".png"
            except Exception as e:
                row["preview_error"] = str(e)
            rows.append(row)
            print(
                stem, "ok", ok, "roof", round(row["roof_after"], 3), "was", b.get("roof"),
                "floors", sc.get("floor_ys"), sc.get("roof_mode"),
            )

    ok_n = sum(1 for r in rows if r["structure_ok"])
    flat = [r for r in rows if r["style"] in ("european", "chinese", "rustic")]
    report = {
        "out_dir": str(out),
        "n": len(rows),
        "structure_ok": "%d/%d" % (ok_n, len(rows)),
        "flat_deck_roof_near_1": all(r["roof_after"] >= 0.95 for r in flat),
        "before_ref": "same-seed probe before scaffold_struct patch",
        "rows": rows,
    }
    (out / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# scaffold_struct smoke",
        "",
        "- out: `%s`" % out.as_posix(),
        "- structure_ok: **%d/%d**" % (ok_n, len(rows)),
        "- euro/chinese/rustic roof~1: **%s**" % report["flat_deck_roof_near_1"],
        "",
        "| style | ok | roof before | roof after | hollow Δ | floor_ys | roof_mode |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        hb = r.get("hollow_before")
        ha = r["hollow_after"]
        hd = None if hb is None else round(ha - float(hb), 3)
        lines.append(
            "| %s | %s | %s | %.3f | %s | %s | %s |"
            % (r["style"], r["structure_ok"], r.get("roof_before"), r["roof_after"], hd, r.get("scaffold_floor_ys"), r.get("scaffold_roof_mode"))
        )
    lines += [
        "",
        "## Changes",
        "- Normalize story floors (sp≈5); seal peri shell; medieval/fantasy deck+gable; pitched plateau.",
        "- Facade polish / glass_dens / rustic pier=12 / flat-deck preserve / roof≠wall untouched.",
        "",
        "Previews: `previews/` + `attach_previews/`.",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "NOTES.md").write_text(
        "# NOTES\n\n- Code: `gen_strategy._normalize_story_floors`, `_seal_shell_columns`, scaffold gable; `look_harden` pitched plateau.\n- No VAE train.\n",
        encoding="utf-8",
    )
    print("DONE", out, "ok", ok_n, "/", len(rows))


if __name__ == "__main__":
    main()
