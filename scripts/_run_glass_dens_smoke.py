# -*- coding: utf-8 -*-
"""Smoke modern/industrial glass density vs prior full_style_review."""
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
from src.app.structure_constraints import SCAFFOLD_THRESHOLDS, check_structure, compute_structure_metrics
from src.utils import load_config, load_palette

# before counts from full_style_review_20261019_190438
BEFORE = {"modern": 320, "industrial": 456}

STYLES = [
    ("modern", "flat", 1, 104),
    ("industrial", "flat", 1, 401),
    ("european", "flat", 1, 102),
    ("chinese", "flat", 1, 101),
    ("rustic", "flat", 1, 201),
]


def glass_count(vox, palette) -> int:
    n = 0
    for bid in np.unique(vox[vox > 0]):
        name = str(palette.get(int(bid), ""))
        if "glass" in name.lower() or name.endswith("_pane"):
            n += int((vox == bid).sum())
    return n


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
    out = root / "outputs" / "design" / ("glass_dens_" + stamp)
    for sub in ("previews", "attach_previews", "npz", "mcfunction", "raw_by_case"):
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
            _lh._PALETTE_REF = palette
            g = glass_count(vox, palette)
            rules = style_facade_rules(style)
            rhythm = next((a for a in (meta.get("look_harden") or {}).get("actions") or [] if str(a).startswith("window_rhythm:")), "")
            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            save_voxels_pair(vox, palette, out / "npz" / (stem + ".npz"))
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "roof_score": float(m.get("roof_score") or 0),
                "glass_after": g,
                "glass_before_review": BEFORE.get(style),
                "window_spacing": rules.get("window_spacing"),
                "window_width_max": rules.get("window_width_max"),
                "max_window_bands": rules.get("max_window_bands"),
                "window_rhythm": rhythm,
                "role_names": (meta.get("materials") or {}).get("role_names") or {},
            }
            png = out / "previews" / (stem + ".png")
            try:
                render_iso(vox, palette, png)
                shutil.copy2(png, out / "attach_previews" / (stem + ".png"))
                row["preview"] = "previews/" + stem + ".png"
            except Exception as e:
                row["preview_error"] = str(e)
            rows.append(row)
            print(stem, "ok", ok, "roof", round(row["roof_score"], 3), "glass", g, "before", BEFORE.get(style), rhythm)

    ok_n = sum(1 for r in rows if r["structure_ok"])
    flat = [r for r in rows if r["style"] in ("european", "chinese", "rustic")]
    report = {
        "out_dir": str(out),
        "n": len(rows),
        "structure_ok": "%d/%d" % (ok_n, len(rows)),
        "euro_chinese_rustic_roof_near_1": all(r["roof_score"] >= 0.95 for r in flat),
        "before_ref": "outputs/design/full_style_review_20261019_190438",
        "param_changes": {
            "modern": "sp 4->6, ww 2 keep, bands 2, from_corner 3",
            "industrial": "added _STYLE_FACADE: sp=4 ww=1 bands=3 (was default sp=3 ww=2 bands=4)",
        },
        "rows": rows,
    }
    (out / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# glass_dens smoke",
        "",
        "- out: `%s`" % out.as_posix(),
        "- structure_ok: **%d/%d**" % (ok_n, len(rows)),
        "- before ref: full_style_review_20261019_190438",
        "",
        "| style | ok | roof | glass before | glass after | sp | ww | bands |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| %s | %s | %.3f | %s | %d | %s | %s | %s |"
            % (r["style"], r["structure_ok"], r["roof_score"], r.get("glass_before_review"), r["glass_after"],
               r["window_spacing"], r["window_width_max"], r["max_window_bands"])
        )
    lines += [
        "",
        "## Changes",
        "- modern: spacing 6, width 2, max_bands 2 (was sp4 ww2 bands2 → glass~320).",
        "- industrial: now in `_STYLE_FACADE` sp4 ww1 bands3 (was defaults → glass~456).",
        "",
        "Previews: `previews/` + `attach_previews/`.",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "NOTES.md").write_text(
        "# NOTES\n\n- Only modern/industrial `_STYLE_FACADE` knobs.\n- No undo of door/pier/eave/flat-deck for other styles.\n- No VAE training.\n",
        encoding="utf-8",
    )
    print("DONE", out, "ok", ok_n, "/", len(rows))


if __name__ == "__main__":
    main()
