# -*- coding: utf-8 -*-
"""Smoke: medieval/fantasy pitch roof vs full_style_v3 + fantasy_glass dens (LOCAL_ONLY)."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

import src.app.look_harden as _lh
from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.look_harden import style_facade_rules, window_opening_count
from src.app.sample_runner import save_voxels_pair
from src.app.structure_constraints import (
    SCAFFOLD_THRESHOLDS,
    check_structure,
    compute_structure_metrics,
)
from src.utils import load_config, load_palette

# Same seeds as full_style_v3 / fantasy_glass_dens
STYLES = [
    ("medieval", "flat", 1, 103),
    ("fantasy", "flat", 2, 301),
    ("european", "flat", 1, 102),
    ("rustic", "flat", 1, 201),
]

# Baseline roofs / dens from full_style_v3 + fantasy_glass_dens settle
BEFORE = {
    ("medieval", 0): {"roof": 0.750, "glass": 348, "piers": 174, "cover": 0.445},
    ("fantasy", 0): {"roof": 0.770, "glass": 230, "piers": 81, "cover": 0.490},
    ("fantasy", 1): {"roof": 0.718, "glass": 144, "piers": 56, "cover": 0.374},
    ("european", 0): {"roof": 1.000, "glass": 256, "piers": 109, "cover": 1.0},
    ("rustic", 0): {"roof": 1.000, "glass": 168, "piers": 88, "cover": 1.0},
}


def _interesting(actions: list) -> list[str]:
    keys = (
        "roof_pitched",
        "roof_flat",
        "front_door",
        "wall_piers",
        "window_rhythm",
        "eave_strip",
        "cornice",
        "facade_stats",
    )
    return [str(a) for a in (actions or []) if any(k in str(a) for k in keys)]


def _parse_token(a: str, key: str) -> int:
    if key + "=" not in a:
        return 0
    try:
        return int(a.split(key + "=")[1].split()[0].split("door")[0].rstrip(","))
    except Exception:
        return 0


def _render_iso(vox, palette, path: Path) -> None:
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
    out = root / "outputs" / "design" / ("pitch_roof_" + stamp)
    for sub in ("previews", "attach_previews", "npz", "mcfunction", "raw_by_case"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    knobs = {
        "fantasy_glass": {
            k: style_facade_rules("fantasy")[k]
            for k in (
                "window_spacing",
                "max_window_bands",
                "window_from_corner",
                "wall_pier_spacing",
            )
        },
        "european": {
            k: style_facade_rules("european")[k]
            for k in ("window_spacing", "max_window_bands", "window_from_corner")
        },
        "rustic_wall_pier_spacing": style_facade_rules("rustic")["wall_pier_spacing"],
        "pitch_fix": {
            "medieval_fantasy_plateau_frac": 0.72,
            "medieval_fantasy_rise_cap": 3,
            "look_harden_path": "harden_roof_silhouette pitched branch",
            "scaffold_path": "scaffold_from_occupancy low_pitch_deck+gable",
        },
    }

    rows = []
    for style, terrain, num, seed0 in STYLES:
        metas = generate_similar_scaffold(
            style=style,
            terrain=terrain,
            num=num,
            out_dir=out / "raw_by_case" / style,
            seed=seed0,
            top_k_refs=3,
            vae_fill=False,
            look_harden_enable=True,
        )
        for i, meta in enumerate(metas):
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
            _lh._PALETTE_REF = palette
            win = window_opening_count(vox)
            glass_by_name = 0
            for bid in np.unique(vox[vox > 0]):
                name = str(palette.get(int(bid), ""))
                if "glass" in name.lower() or name.endswith("_pane"):
                    glass_by_name += int((vox == bid).sum())
            win["glass_cells"] = max(int(win.get("glass_cells", 0)), glass_by_name)

            lh = meta.get("look_harden") or {}
            acts = lh.get("actions") or []
            pier_n = 0
            for a in acts:
                s = str(a)
                if s.startswith("wall_piers:"):
                    try:
                        pier_n = int(s.split(":")[1].split()[0])
                    except Exception:
                        pass

            before = BEFORE.get((style, i), {})
            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            saved = save_voxels_pair(vox, palette, out / "npz" / (stem + ".npz"))
            roof = float(m.get("roof_score") or 0)
            cover = float(m.get("top_footprint_cover") or 0)
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "roof_score": roof,
                "roof_before": before.get("roof"),
                "top_footprint_cover": cover,
                "cover_before": before.get("cover"),
                "glass_cells": int(win.get("glass_cells", 0)),
                "glass_before": before.get("glass"),
                "wall_pier_cells": pier_n,
                "piers_before": before.get("piers"),
                "look_actions": _interesting(acts),
                "reference_id": meta.get("reference_id"),
                "scaffold_roof_mode": (meta.get("scaffold") or {}).get("roof_mode"),
            }
            png = out / "previews" / (stem + ".png")
            try:
                _render_iso(vox, palette, png)
                shutil.copy2(png, out / "attach_previews" / (stem + ".png"))
                row["preview"] = "previews/" + stem + ".png"
            except Exception as e:
                row["preview_error"] = str(e)
            mcf = meta.get("mcfunction_path") or meta.get("mcfunction")
            if mcf and Path(mcf).is_file():
                shutil.copy2(mcf, out / "mcfunction" / Path(mcf).name)
            mcf2 = saved.get("mcfunction_path")
            if mcf2 and Path(mcf2).is_file():
                dest = out / "mcfunction" / Path(mcf2).name
                if not dest.exists():
                    shutil.copy2(mcf2, dest)
            rows.append(row)
            print(
                stem,
                "ok",
                ok,
                "roof",
                round(roof, 3),
                "was",
                before.get("roof"),
                "cover",
                round(cover, 3),
                "glass",
                row["glass_cells"],
                "was",
                before.get("glass"),
                "piers",
                pier_n,
                "was",
                before.get("piers"),
            )

    ok_n = sum(1 for r in rows if r["structure_ok"])
    pitched = [r for r in rows if r["style"] in ("medieval", "fantasy")]
    flat_ctrl = [r for r in rows if r["style"] in ("european", "rustic")]
    roof_improved = all(
        (r["roof_score"] > (r.get("roof_before") or 0) + 0.02)
        or (r["roof_score"] >= 0.85)
        for r in pitched
    )
    flat_ok = all(r["roof_score"] >= 0.99 for r in flat_ctrl) and all(
        r["structure_ok"] for r in flat_ctrl
    )

    report = {
        "out_dir": str(out),
        "vs": "full_style_v3_20261020_085033 + fantasy_glass_dens_20261020_090033",
        "n": len(rows),
        "structure_ok": "%d/%d" % (ok_n, len(rows)),
        "pitched_roof_improved": roof_improved,
        "flat_controls_roof_1": flat_ok,
        "knobs": knobs,
        "rows": rows,
    }
    (out / "REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# pitch_roof batch",
        "",
        "- out: `%s`" % out.as_posix(),
        "- vs: `full_style_v3` roofs + `fantasy_glass_dens` glass/piers",
        "- structure_ok: **%d/%d**" % (ok_n, len(rows)),
        "- pitched improved: **%s**" % roof_improved,
        "- flat controls roof~1: **%s**" % flat_ok,
        "",
        "## Change",
        "- look_harden pitched (medieval/fantasy only): plateau **0.32→0.72** of half, rise cap **3**",
        "- scaffold `low_pitch_deck+gable`: same plateau/rise sync",
        "- fantasy glass dens knobs **unchanged** (sp4/bands3/c2, pier=5)",
        "- euro/rustic flat-deck path **unchanged**",
        "",
        "| style | ok | roof before->after | cover before->after | glass | piers |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| %s | %s | %s -> %.3f | %s -> %.3f | %s -> %d | %s -> %d |"
            % (
                r["style"],
                r["structure_ok"],
                r.get("roof_before") if r.get("roof_before") is not None else "?",
                r["roof_score"],
                r.get("cover_before") if r.get("cover_before") is not None else "?",
                r["top_footprint_cover"],
                r.get("glass_before") if r.get("glass_before") is not None else "?",
                r["glass_cells"],
                r.get("piers_before") if r.get("piers_before") is not None else "?",
                r["wall_pier_cells"],
            )
        )
    lines += [
        "",
        "## Aim / residuals",
        "- medieval/fantasy roof_score above ~0.75 stall, toward ~0.85-1.0 if geometry allows",
        "- european glass ~256, rustic roof 1.0, fantasy glass/piers dens band held",
        "- if still short of 1.0: honest — further needs larger redesign / detection change",
        "",
        "Previews: `previews/` and `attach_previews/`.",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "NOTES.md").write_text(
        "\n".join(
            [
                "# NOTES",
                "",
                "- LOCAL_ONLY: pitched roof geometry for medieval/fantasy only.",
                "- No VAE train / no facade dens knob revert.",
                "- Docs: `docs/look_harden.md` § pitch_roof.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("DONE", out, "ok", ok_n, "/", len(rows), "pitched_improved", roof_improved, "flat_ok", flat_ok)


if __name__ == "__main__":
    main()
