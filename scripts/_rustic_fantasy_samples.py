# -*- coding: utf-8 -*-
"""Generate rustic + fantasy look samples via similar_scaffold (no train)."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.gen_strategy import generate_similar_scaffold, retrieve_style_refs
from src.app.mc_render import render_mc_voxels
from src.app.structure_constraints import SCAFFOLD_THRESHOLDS, check_structure
from src.utils import load_config, load_palette


def _save_preview(vox, palette, path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="3d")
    render_mc_voxels(ax, fig, vox, palette, performance=True)
    ax.set_title(title, fontsize=9)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def _is_mcblock_path(p: str | None) -> bool:
    s = (p or "").replace("\\", "/").lower()
    return "raw/mcblock" in s or "/mcblock/" in s


def main() -> None:
    started = datetime.now()
    ts = started.strftime("%Y%m%d_%H%M%S")
    out_root = ROOT / "outputs" / "design" / ("rustic_fantasy_samples_%s" % ts)
    for sub in ("npz", "mcfunction", "previews", "attach_previews"):
        (out_root / sub).mkdir(parents=True, exist_ok=True)

    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])

    # 5 each on flat; fantasy also gets 1 nature for variety (total fantasy 6, rustic 5)
    cases = [
        ("rustic", "flat", 201, 5, 3),
        ("fantasy", "flat", 301, 5, 5),
        ("fantasy", "nature", 401, 1, 3),
    ]

    rows = []
    for style, terrain, seed, num, top_k in cases:
        key = "%s_%s" % (style, terrain)
        print("===", key, "num=%s top_k=%s" % (num, top_k), flush=True)
        refs = retrieve_style_refs(style, terrain, top_k=top_k)
        print("  refs:", [r.get("id") for r in refs], flush=True)

        case_dir = out_root / "raw_by_case" / key
        results = generate_similar_scaffold(
            style=style,
            terrain=terrain,
            num=num,
            seed=seed,
            out_dir=case_dir,
            vae_fill=False,
            look_harden_enable=True,
            preserve_windows=True,
            top_k_refs=top_k,
        )

        for i, meta in enumerate(results):
            vox = np.asarray(meta["voxels"], dtype=np.int16)
            st = check_structure(vox, thresholds=dict(SCAFFOLD_THRESHOLDS)).to_dict()
            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            npz_src = Path(meta["npz_path"])
            npz_dst = out_root / "npz" / (stem + ".npz")
            shutil.copy2(npz_src, npz_dst)
            mcf_src = meta.get("mcfunction_path")
            if mcf_src and Path(mcf_src).exists():
                mcf_dst = out_root / "mcfunction" / (stem + ".mcfunction")
                shutil.copy2(mcf_src, mcf_dst)
            else:
                # regenerate export if missing
                from src.data.export_mcfunction import export_mcfunction

                mcf_dst = out_root / "mcfunction" / (stem + ".mcfunction")
                export_mcfunction(vox, palette, mcf_dst)
                mcf_src = str(mcf_dst)

            prev = out_root / "previews" / (stem + ".png")
            title = "%s | ref=%s" % (stem, meta.get("reference_id") or "?")
            _save_preview(vox, palette, prev, title)

            # attach first rustic/fantasy flat samples
            if style in ("rustic", "fantasy") and terrain == "flat" and i < 2:
                shutil.copy2(prev, out_root / "attach_previews" / (stem + ".png"))

            ref_id = meta.get("reference_id")
            ref_feat = next((r for r in refs if r.get("id") == ref_id), None)
            src_path = ""
            if ref_feat:
                src_path = (
                    ref_feat.get("source_path")
                    or ref_feat.get("path")
                    or ref_feat.get("npz_path")
                    or ""
                )
            row = {
                "stem": stem,
                "style": style,
                "terrain": terrain,
                "seed": seed + i,
                "non_air": int((vox > 0).sum()),
                "structure_ok": bool(st.get("ok")),
                "structure_metrics": st.get("metrics"),
                "reference_id": ref_id,
                "reference_ids": meta.get("reference_ids"),
                "reference_source": src_path,
                "is_mcblock": _is_mcblock_path(str(src_path)),
                "strategy": meta.get("strategy") or "similar_scaffold",
                "npz": str(npz_dst.relative_to(out_root)).replace("\\", "/"),
                "preview": str(prev.relative_to(out_root)).replace("\\", "/"),
                "mcfunction": str(Path(mcf_src).name) if mcf_src else None,
            }
            rows.append(row)
            print(
                "  %s ok=%s non_air=%s ref=%s mcblock=%s"
                % (stem, row["structure_ok"], row["non_air"], ref_id, row["is_mcblock"]),
                flush=True,
            )

    finished = datetime.now()
    report = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "out_dir": str(out_root),
        "strategy": "similar_scaffold",
        "look_harden": True,
        "vae_fill": False,
        "checkpoint_note": "not used for scaffold massing; cond_last untouched",
        "pool_note": "outputs/design/rustic_fantasy_pool_20261019_160540",
        "counts": {
            "total": len(rows),
            "rustic": sum(1 for r in rows if r["style"] == "rustic"),
            "fantasy": sum(1 for r in rows if r["style"] == "fantasy"),
            "structure_ok": sum(1 for r in rows if r["structure_ok"]),
            "mcblock_refs": sum(1 for r in rows if r["is_mcblock"]),
        },
        "samples": rows,
    }
    (out_root / "REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Rustic / Fantasy specialty-pool samples",
        "",
        "- Time (Asia/Shanghai): %s → %s" % (started.isoformat(), finished.isoformat()),
        "- Strategy: **similar_scaffold** (look_harden ON, vae_fill OFF)",
        "- Pool: `outputs/design/rustic_fantasy_pool_20261019_160540/`",
        "- Output: `%s`" % str(out_root).replace("\\", "/"),
        "- Training: **none**; `checkpoints/cond_last.pt` not overwritten",
        "",
        "## Counts",
        "",
        "| rustic | fantasy | total | structure_ok | mcblock refs |",
        "|---:|---:|---:|---:|---:|",
        "| %s | %s | %s | %s | %s |"
        % (
            report["counts"]["rustic"],
            report["counts"]["fantasy"],
            report["counts"]["total"],
            report["counts"]["structure_ok"],
            report["counts"]["mcblock_refs"],
        ),
        "",
        "## Samples",
        "",
        "| stem | STYLE | terrain | structure_ok | non_air | ref used | mcblock | preview |",
        "|---|---|---|:---:|---:|---|:---:|---|",
    ]
    for r in rows:
        lines.append(
            "| `%s` | %s | %s | %s | %s | `%s` | %s | %s |"
            % (
                r["stem"],
                r["style"],
                r["terrain"],
                r["structure_ok"],
                r["non_air"],
                r["reference_id"],
                r["is_mcblock"],
                r["preview"],
            )
        )
    lines += [
        "",
        "## How to open",
        "",
        "- PNG previews: `previews/*.png`",
        "- Quick attach: `attach_previews/` (first 2 flat rustic + fantasy)",
        "- Load `.npz` in `scripts/viewer_app.py`",
        "- `.mcfunction` for in-game setblock paste",
        "",
        "## Ref check",
        "",
        "- Expect rustic refs from mcblock 湖畔*/白色野营帐篷 (not european 意式别墅).",
        "- Expect fantasy refs from mcblock 精灵*/高等精灵之塔 etc.",
        "- All samples below should show `mcblock=True`.",
        "",
    ]
    (out_root / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print("DONE", out_root, flush=True)
    print("counts", report["counts"], flush=True)


if __name__ == "__main__":
    main()
