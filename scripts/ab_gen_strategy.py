# -*- coding: utf-8 -*-
"""A/B: vae_look (old) vs similar_scaffold (new primary generation strategy)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.gen_strategy import generate_with_strategy, retrieve_style_refs
from src.app.mc_render import render_mc_voxels
from src.app.structure_constraints import check_structure, SCAFFOLD_THRESHOLDS
from src.utils import load_config, load_palette


def _top_blocks(vox, palette, k=5):
    ids, cts = np.unique(vox[vox > 0], return_counts=True)
    order = np.argsort(-cts)
    out = []
    for i in order[:k]:
        bid = int(ids[i])
        name = palette.get(bid, str(bid))
        if ":" in name:
            name = name.split(":", 1)[1]
        out.append([name, int(cts[i])])
    return out


def _save_preview(vox, palette, path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="3d")
    render_mc_voxels(ax, fig, vox, palette, performance=True)
    ax.set_title(title, fontsize=9)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = ROOT / "outputs" / "design" / ("gen_strategy_ab2_%s" % ts)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "A_vae_look").mkdir(exist_ok=True)
    (out_root / "B_similar_scaffold").mkdir(exist_ok=True)
    (out_root / "previews").mkdir(exist_ok=True)
    (out_root / "side_by_side").mkdir(exist_ok=True)

    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])

    # Match prior look_harden_best flat styles (4–8 pairs)
    cases = [
        ("chinese", "flat", 42),
        ("european", "flat", 43),
        ("medieval", "flat", 47),
        ("modern", "flat", 48),
        ("japanese", "flat", 46),
        ("rustic", "flat", 49),
        ("industrial", "flat", 45),
        ("fantasy", "flat", 44),
    ]

    notes = []
    audit = {
        "default_path_before": [
            "DesignSpec / CLI style+terrain",
            "ConditionalVoxelVAE.sample (cond_last)",
            "structure_constrain repair",
            "look_harden (preserve windows, facade)",
            "write npz + mcfunction (+ optional PNG preview)",
        ],
        "default_path_after": [
            "DesignSpec / CLI style+terrain + --strategy similar_scaffold",
            "retrieve 1–3 refs from data/feature_index (style/keywords/hollow)",
            "build shell+floors scaffold from 32^3 skeleton (not VAE massing)",
            "structure_constrain repair + look_harden",
            "fallback rule_scaffold if no refs",
        ],
        "related": {
            "generate_samples": "src/app/sample_runner.py",
            "design_cli": "scripts/design_from_brief.py",
            "structure_constrain": "src/app/structure_constraints.py",
            "similar_search": "scripts/learn_from_reference.py (similar/search/embed)",
            "block2vec": "src/app/block2vec_embed.py",
            "look_harden": "src/app/look_harden.py",
            "new_strategy": "src/app/gen_strategy.py",
        },
    }
    (out_root / "NOTES.md").write_text(
        "# Audit: default design/generate path (A/B round 2 post plans 1-3)\n\n"
        "## Linked plans (2026-10-19 Asia/Shanghai)\n"
        "- Plan 1 ingest: `outputs/plans/gen_quality_plans_20261019_125108/`\n"
        "- Plan 2 scaffold tune: `outputs/design/scaffold_tune_20261019_130739/`\n"
        "- Plan 3 Block2Vec: `outputs/design/block2vec_index_20261019_131142/`\n"
        "- Prior A/B baseline: `outputs/design/gen_strategy_20261019_123939/`\n"
        "- B path uses post-2 ranking + SCAFFOLD_THRESHOLDS + post-3 Block2Vec blend.\n\n"
        "## Before (vae_look)\n"
        + "\n".join("- " + x for x in audit["default_path_before"])
        + "\n\n## After (similar_scaffold primary)\n"
        + "\n".join("- " + x for x in audit["default_path_after"])
        + "\n\n## Key modules\n"
        + "\n".join("- `%s`: `%s`" % (k, v) for k, v in audit["related"].items())
        + "\n",
        encoding="utf-8",
    )

    for style, terrain, seed in cases:
        key = "%s_%s" % (style, terrain)
        print("===", key, flush=True)

        refs = retrieve_style_refs(style, terrain, top_k=3)
        ref_ids = [r.get("id") for r in refs]

        a_dir = out_root / "A_vae_look" / key
        b_dir = out_root / "B_similar_scaffold" / key

        a_res = generate_with_strategy(
            "vae_look",
            style=style,
            terrain=terrain,
            num=1,
            seed=seed,
            out_dir=a_dir,
            checkpoint=ROOT / "checkpoints" / "cond_last.pt",
            look_harden_enable=True,
        )
        b_res = generate_with_strategy(
            "similar_scaffold",
            style=style,
            terrain=terrain,
            num=1,
            seed=seed,
            out_dir=b_dir,
            vae_fill=False,
            look_harden_enable=True,
        )

        va = np.asarray(a_res[0]["voxels"], dtype=np.int16)
        vb = np.asarray(b_res[0]["voxels"], dtype=np.int16)
        sa = check_structure(va).to_dict()
        sb = check_structure(vb, thresholds=dict(SCAFFOLD_THRESHOLDS)).to_dict()

        pa = out_root / "previews" / ("A_%s.png" % key)
        pb = out_root / "previews" / ("B_%s.png" % key)
        _save_preview(va, palette, pa, "A vae_look %s" % key)
        _save_preview(vb, palette, pb, "B similar_scaffold %s" % key)

        # side-by-side
        fig, axes = plt.subplots(1, 2, figsize=(10, 5), subplot_kw={"projection": "3d"})
        render_mc_voxels(axes[0], fig, va, palette, performance=True)
        axes[0].set_title("A vae_look", fontsize=9)
        render_mc_voxels(axes[1], fig, vb, palette, performance=True)
        axes[1].set_title("B similar_scaffold", fontsize=9)
        fig.suptitle(key)
        fig.savefig(out_root / "side_by_side" / ("%s.png" % key), dpi=120, bbox_inches="tight")
        plt.close(fig)

        row = {
            "case": key,
            "style": style,
            "terrain": terrain,
            "seed": seed,
            "refs": ref_ids,
            "A": {
                "non_air": int((va > 0).sum()),
                "ok": sa.get("ok"),
                "metrics": sa.get("metrics"),
                "tops": _top_blocks(va, palette),
                "npz": str(Path(a_res[0]["npz_path"]).name),
            },
            "B": {
                "non_air": int((vb > 0).sum()),
                "ok": sb.get("ok"),
                "metrics": sb.get("metrics"),
                "tops": _top_blocks(vb, palette),
                "npz": str(Path(b_res[0]["npz_path"]).name),
                "strategy": b_res[0].get("strategy"),
                "reference_id": b_res[0].get("reference_id"),
                "scaffold": b_res[0].get("scaffold"),
            },
        }
        notes.append(row)
        print(
            "  A non_air=%s ok=%s | B non_air=%s ok=%s ref=%s"
            % (
                row["A"]["non_air"],
                row["A"]["ok"],
                row["B"]["non_air"],
                row["B"]["ok"],
                row["B"].get("reference_id"),
            ),
            flush=True,
        )

    (out_root / "COMPARE.json").write_text(
        json.dumps({"created": ts, "cases": notes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Gen strategy A/B round 2 — vae_look vs similar_scaffold (post plans 1-3)",
        "",
        "- Created: %s (Asia/Shanghai)" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "- Checkpoint for A: `checkpoints/cond_last.pt` (not overwritten)",
        "- B: `similar_scaffold` post-1/2/3 (mcblock ranking + SCAFFOLD_THRESHOLDS + Block2Vec blend; no VAE massing)",
        "- Output: `%s`" % out_root.as_posix(),
        "",
        "## How to run",
        "",
        "```bat",
        "cd /d \"E:\\ai agent\\mc-architecture-ai\"",
        ".venv\\Scripts\\python.exe scripts\\design_from_brief.py --text \"中世纪石屋\" --strategy similar_scaffold --num 2",
        ".venv\\Scripts\\python.exe scripts\\sample.py --conditional --style medieval --terrain flat --strategy similar_scaffold --num 2 --out-dir outputs/samples_scaffold",
        ".venv\\Scripts\\python.exe scripts\\ab_gen_strategy.py",
        "```",
        "",
        "## Strategy difference",
        "",
        "| | A `vae_look` | B `similar_scaffold` |",
        "|---|---|---|",
        "| Structure source | ConditionalVAE latent sample | Reference 32³ skeleton occupancy |",
        "| Materials | VAE classes + look_harden palette | Reference remap / style tokens + look_harden |",
        "| Post | structure repair + look_harden | same |",
        "| Fallback | n/a | `rule_scaffold` if no refs |",
        "",
        "## Pairs",
        "",
        "| case | A non_air | A ok | B non_air | B ok | B ref | preview |",
        "|---|---:|:---:|---:|:---:|---|---|",
    ]
    for r in notes:
        ma = (r["A"].get("metrics") or {})
        mb = (r["B"].get("metrics") or {})
        lines.append(
            "| %s | %s | %s | %s | %s | `%s` | side_by_side/%s.png |"
            % (
                r["case"],
                r["A"]["non_air"],
                r["A"]["ok"],
                r["B"]["non_air"],
                r["B"]["ok"],
                (r["B"].get("reference_id") or r["B"].get("strategy") or "")[:40],
                r["case"],
            )
        )

    lines += [
        "",
        "## Honest notes",
        "",
        "- **Structurally improved**: B should show clearer shell / floor bands / footprint from real schematics instead of VAE mush density.",
        "- **Still needs human eye**: material fidelity depends on palette coverage of reference block names; many index styles are mislabeled `chinese`.",
        "- **Refs**: post-3 Block2Vec coverage on mcblock styles; ranking demotes Hack337 challenge/farm.",
        "- **Vs prior A/B** (`gen_strategy_20261019_123939`): expect B refs to be mcblock style houses, higher structure_ok under scaffold thresholds.",
        "",
        "See also `NOTES.md` in this folder.",
        "",
    ]
    (out_root / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print("DONE", out_root, flush=True)


if __name__ == "__main__":
    main()
