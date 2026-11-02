# -*- coding: utf-8 -*-
"""Smoke rustic wall pier spacing widen."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import src.app.look_harden as _lh
from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.look_harden import style_facade_rules
from src.app.sample_runner import save_voxels_pair
from src.app.structure_constraints import SCAFFOLD_THRESHOLDS, check_structure, compute_structure_metrics
from src.utils import load_config, load_palette

# before from full_style_review_20261019_190438 / door_wall
BEFORE_PIER = {"rustic": [322, 306], "european": 124, "modern": 0}

STYLES = [
    ("rustic", "flat", 2, 201),
    ("european", "flat", 1, 102),
    ("modern", "flat", 1, 104),
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
    out = root / "outputs" / "design" / ("rustic_pier_" + stamp)
    for sub in ("previews", "attach_previews", "npz", "mcfunction", "raw_by_case"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    rows = []
    rustic_idx = 0
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
            pier = cols = sp = 0
            for a in (meta.get("look_harden") or {}).get("actions") or []:
                s = str(a)
                if s.startswith("wall_piers:"):
                    # wall_piers:%d cols=%d sp=%d
                    parts = s.split(":", 1)[1].split()
                    pier = int(parts[0])
                    for tok in parts[1:]:
                        if tok.startswith("cols="):
                            cols = int(tok.split("=", 1)[1])
                        if tok.startswith("sp="):
                            sp = int(tok.split("=", 1)[1])
            rules = style_facade_rules(style)
            before = BEFORE_PIER.get(style)
            if style == "rustic" and isinstance(before, list):
                before_v = before[min(rustic_idx, len(before) - 1)]
                rustic_idx += 1
            else:
                before_v = before
            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            save_voxels_pair(vox, palette, out / "npz" / (stem + ".npz"))
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "roof_score": float(m.get("roof_score") or 0),
                "pier_after": pier,
                "pier_cols": cols,
                "pier_sp": sp or rules.get("wall_pier_spacing"),
                "pier_before_review": before_v,
                "wall_pier_spacing_rule": rules.get("wall_pier_spacing"),
                "place_wall_piers": rules.get("place_wall_piers"),
            }
            png = out / "previews" / (stem + ".png")
            try:
                render_iso(vox, palette, png)
                shutil.copy2(png, out / "attach_previews" / (stem + ".png"))
                row["preview"] = "previews/" + stem + ".png"
            except Exception as e:
                row["preview_error"] = str(e)
            rows.append(row)
            print(stem, "ok", ok, "roof", round(row["roof_score"], 3), "pier", pier, "before", before_v, "sp", row["pier_sp"])

    ok_n = sum(1 for r in rows if r["structure_ok"])
    rustic_rows = [r for r in rows if r["style"] == "rustic"]
    report = {
        "out_dir": str(out),
        "n": len(rows),
        "structure_ok": "%d/%d" % (ok_n, len(rows)),
        "rustic_roof_near_1": all(r["roof_score"] >= 0.95 for r in rustic_rows),
        "param_change": {"rustic.wall_pier_spacing": "4 -> 10"},
        "before_ref": "full_style_review_20261019_190438 / door_wall_20261019_190033",
        "rows": rows,
    }
    (out / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# rustic_pier smoke",
        "",
        "- out: `%s`" % out.as_posix(),
        "- structure_ok: **%d/%d**" % (ok_n, len(rows)),
        "- rustic `wall_pier_spacing` **4 → 10**",
        "",
        "| style | ok | roof | pier before | pier after | sp | cols |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| %s | %s | %.3f | %s | %d | %s | %s |"
            % (r["style"], r["structure_ok"], r["roof_score"], r.get("pier_before_review"), r["pier_after"], r["pier_sp"], r["pier_cols"])
        )
    lines += ["", "Previews: `previews/` + `attach_previews/`.", ""]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "NOTES.md").write_text(
        "# NOTES\n\n- Only rustic pier spacing widened.\n- glass_dens modern/industrial, doors/windows/eaves/flat-deck untouched.\n- No VAE training.\n",
        encoding="utf-8",
    )
    print("DONE", out, "ok", ok_n, "/", len(rows))


if __name__ == "__main__":
    main()
