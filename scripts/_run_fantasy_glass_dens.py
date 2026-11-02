# -*- coding: utf-8 -*-
"""Smoke: fantasy glass dens vs full_style_v3 (LOCAL_ONLY). Controls: european, rustic."""
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

# Same seeds as full_style_v3 / euro_fan_dens
STYLES = [
    ("fantasy", "flat", 2, 301),
    ("european", "flat", 1, 102),
    ("rustic", "flat", 1, 201),
]

# Before (full_style_v3_20261020_085033 / euro_fan_dens)
V3_BEFORE = {
    ("fantasy", 0): {"glass": 374, "piers": 81},
    ("fantasy", 1): {"glass": 238, "piers": 56},
    ("european", 0): {"glass": 256, "piers": 109},
    ("rustic", 0): {"glass": 168, "piers": 88},
}


def _interesting(actions: list) -> list[str]:
    keys = (
        "front_door",
        "wall_piers",
        "window_rhythm",
        "eave_strip",
        "cornice",
        "preserve_windows",
        "facade_band",
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
    out = root / "outputs" / "design" / ("fantasy_glass_dens_" + stamp)
    for sub in ("previews", "attach_previews", "npz", "mcfunction", "raw_by_case"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    knobs = {
        "fantasy": {
            k: style_facade_rules("fantasy")[k]
            for k in (
                "window_spacing",
                "max_window_bands",
                "window_from_corner",
                "wall_pier_spacing",
            )
        },
        "unchanged_controls": {
            "european_window_spacing": style_facade_rules("european")["window_spacing"],
            "european_max_window_bands": style_facade_rules("european")["max_window_bands"],
            "european_window_from_corner": style_facade_rules("european")["window_from_corner"],
            "rustic_wall_pier_spacing": style_facade_rules("rustic")["wall_pier_spacing"],
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
            pier_cols = 0
            pier_sp = 0
            for a in acts:
                s = str(a)
                if s.startswith("wall_piers:"):
                    try:
                        pier_n = int(s.split(":")[1].split()[0])
                    except Exception:
                        pass
                    pier_cols = _parse_token(s, "cols")
                    pier_sp = _parse_token(s, "sp")

            before = V3_BEFORE.get((style, i), {})
            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            saved = save_voxels_pair(vox, palette, out / "npz" / (stem + ".npz"))
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "roof_score": float(m.get("roof_score") or 0),
                "glass_cells": int(win.get("glass_cells", 0)),
                "glass_before_v3": before.get("glass"),
                "wall_pier_cells": pier_n,
                "pier_cols": pier_cols,
                "pier_sp": pier_sp,
                "piers_before_v3": before.get("piers"),
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
                round(row["roof_score"], 3),
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
    report = {
        "out_dir": str(out),
        "vs": "full_style_v3_20261020_085033",
        "n": len(rows),
        "structure_ok": "%d/%d" % (ok_n, len(rows)),
        "knobs": knobs,
        "params": {
            "fantasy": "window_spacing=4 max_window_bands=3 window_from_corner=2; wall_pier_spacing=5 kept",
            "untouched": "european glass dens 4/3/3; rustic pier=12; modern/industrial; scaffold roofs",
        },
        "rows": rows,
    }
    (out / "REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# fantasy_glass_dens batch",
        "",
        "- out: `%s`" % out.as_posix(),
        "- vs: `full_style_v3_20261020_085033`",
        "- structure_ok: **%d/%d**" % (ok_n, len(rows)),
        "",
        "## Params",
        "- fantasy: `window_spacing=4`, `max_window_bands=3`, `window_from_corner=2`",
        "- fantasy piers: `wall_pier_spacing=5` (unchanged)",
        "- controls unchanged: european 4/3/3, rustic pier=12",
        "",
        "| style | ok | roof | glass before->after | piers before->after |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        gb = r.get("glass_before_v3")
        pb = r.get("piers_before_v3")
        lines.append(
            "| %s | %s | %.3f | %s -> %d | %s -> %d |"
            % (
                r["style"],
                r["structure_ok"],
                r["roof_score"],
                gb if gb is not None else "?",
                r["glass_cells"],
                pb if pb is not None else "?",
                r["wall_pier_cells"],
            )
        )
    lines += [
        "",
        "## Aim / residuals",
        "- fantasy glass aim denser sample ~200-280 (was 374).",
        "- fantasy piers stay ~81/56 (spacing=5).",
        "- european glass ~256, rustic pier ~88 held.",
        "- pitched roof residual (~0.72-0.77) left for follow-up; not this pass.",
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
                "- LOCAL_ONLY: tun `_STYLE_FACADE` fantasy window dens only.",
                "- No VAE train / no PR / no roof scaffold rewrite.",
                "- Docs: `docs/look_harden.md` § fantasy_glass_dens.",
                "",
            ]
        ),
        encoding="utf-8",
        )
    print("DONE", out, "ok", ok_n, "/", len(rows))


if __name__ == "__main__":
    main()
