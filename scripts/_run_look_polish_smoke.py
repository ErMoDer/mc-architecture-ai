# -*- coding: utf-8 -*-
"""Smoke look-polish: similar_scaffold samples after roof/material fixes."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.structure_constraints import SCAFFOLD_THRESHOLDS, check_structure, compute_structure_metrics
from src.app.sample_runner import save_voxels_pair
from src.utils import load_config, load_palette


STYLES = [
    ("chinese", "flat", 1, 101),
    ("european", "flat", 1, 102),
    ("medieval", "flat", 1, 103),
    ("modern", "flat", 1, 104),
    ("rustic", "flat", 2, 201),
    ("fantasy", "flat", 2, 301),
]


def _top_blocks(vox, palette, k=6):
    solid = vox[vox > 0]
    if solid.size == 0:
        return []
    ids, cts = np.unique(solid, return_counts=True)
    order = np.argsort(-cts)
    out = []
    for i in order[:k]:
        bid = int(ids[i])
        name = str(palette.get(bid, bid))
        if ":" in name:
            name = name.split(":", 1)[1]
        out.append({"id": bid, "name": name, "count": int(cts[i])})
    return out


def main() -> None:
    root = project_root()
    cfg = load_config(root / "configs/default.yaml")
    palette = load_palette(root / cfg["data"]["palette_path"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = root / "outputs" / "design" / ("look_polish_" + stamp)
    for sub in ("previews", "attach_previews", "npz", "mcfunction", "raw_by_case"):
        (out / sub).mkdir(parents=True, exist_ok=True)

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
            m = (st.get("metrics") if isinstance(st, dict) else None) or compute_structure_metrics(vox)
            ok = bool(st.get("ok")) if isinstance(st, dict) else check_structure(vox, SCAFFOLD_THRESHOLDS).ok
            mats = meta.get("materials") or {}
            role_names = mats.get("role_names") or {}
            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            saved = save_voxels_pair(vox, palette, out / "npz" / (stem + ".npz"))
            tops = _top_blocks(vox, palette)
            uniq = int(len(np.unique(vox[vox > 0]))) if (vox > 0).any() else 0
            wall = role_names.get("wall")
            roof = role_names.get("roof")
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "roof_score": float(m.get("roof_score") or 0),
                "top_footprint_cover": float(m.get("top_footprint_cover") or 0),
                "non_air": int(m.get("non_air") or 0),
                "unique_blocks": uniq,
                "reference_id": meta.get("reference_id"),
                "role_names": role_names,
                "roof_ne_wall": wall != roof,
                "materials_source": mats.get("source"),
                "style_denied_refs": mats.get("style_denied_refs"),
                "roof_forced_distinct": mats.get("roof_forced_distinct"),
                "scaffold": meta.get("scaffold"),
                "top_blocks": tops,
                "reasons": st.get("reasons") if isinstance(st, dict) else [],
                "look_actions_head": (meta.get("look_harden") or {}).get("actions", [])[:8],
            }
            for cand in (saved.get("preview_path"), meta.get("preview_path")):
                if cand and Path(cand).is_file():
                    dest = out / "previews" / (stem + ".png")
                    shutil.copy2(cand, dest)
                    row["preview"] = str(dest.relative_to(out)).replace("\\", "/")
                    shutil.copy2(cand, out / "attach_previews" / (stem + ".png"))
                    break
            mcf = meta.get("mcfunction_path") or meta.get("mcfunction")
            if mcf and Path(mcf).is_file():
                shutil.copy2(mcf, out / "mcfunction" / Path(mcf).name)
            rows.append(row)
            print(
                stem, "ok", ok, "roof", round(row["roof_score"], 3),
                "roof!=wall", row["roof_ne_wall"],
                "roles", role_names, "denied", mats.get("style_denied_refs"),
            )

    ok_n = sum(1 for r in rows if r["structure_ok"])
    euro = [r for r in rows if r["style"] == "european"]
    rustic = [r for r in rows if r["style"] == "rustic"]
    fantasy = [r for r in rows if r["style"] == "fantasy"]
    junk_walls = []
    for r in rows:
        w = (r.get("role_names") or {}).get("wall") or ""
        if r["style"] == "european" and "acacia" in w:
            junk_walls.append(r["stem"] + ":acacia")
        if r["style"] == "chinese" and ("mud" in w):
            junk_walls.append(r["stem"] + ":mud")
    roof_same = [r["stem"] for r in rows if not r.get("roof_ne_wall")]

    report = {
        "out_dir": str(out),
        "n": len(rows),
        "structure_ok": "%d/%d" % (ok_n, len(rows)),
        "european_ok": "%d/%d" % (sum(1 for r in euro if r["structure_ok"]), len(euro)),
        "european_roof": [round(r["roof_score"], 4) for r in euro],
        "rustic_ok": "%d/%d" % (sum(1 for r in rustic if r["structure_ok"]), len(rustic)),
        "fantasy_ok": "%d/%d" % (sum(1 for r in fantasy if r["structure_ok"]), len(fantasy)),
        "junk_walls": junk_walls,
        "roof_eq_wall": roof_same,
        "rows": rows,
    }
    (out / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Look polish (roof deck + junk materials + roof≠wall)",
        "",
        "- Time (Asia/Shanghai): %s" % stamp,
        "- Out: `%s`" % out,
        "- Training: **none**",
        "",
        "## What changed",
        "",
        "1. **Sparse/euro roof**: `_fill_footprint_holes` + solid deck over filled footprint; european sparse uses max_rise≤1 and broad plateau (no needle tip).",
        "2. **Junk material filter**: expanded skip list + `_STYLE_ROLE_DENY` (acacia-as-european-wall, mud_bricks-as-chinese-wall → style fallback).",
        "3. **Roof≠wall**: re-diversify after `prefer_full_cube` remap; hard-force style roof if still equal.",
        "",
        "## Smoke",
        "",
        "- structure_ok: **%d / %d**" % (ok_n, len(rows)),
        "- european: **%s** roof=%s" % (report["european_ok"], report["european_roof"]),
        "- rustic: **%s**; fantasy: **%s**" % (report["rustic_ok"], report["fantasy_ok"]),
        "- junk walls left: %s" % (junk_walls or "none"),
        "- roof==wall left: %s" % (roof_same or "none"),
        "",
        "## Samples",
        "",
        "| stem | style | ok | roof | roof≠wall | roles (wall/roof/foundation) | top blocks |",
        "|---|---|:---:|---:|:---:|---|---|",
    ]
    for r in rows:
        rn = r.get("role_names") or {}
        roles = "%s/%s/%s" % (rn.get("wall"), rn.get("roof"), rn.get("foundation"))
        tops = ", ".join(t["name"] for t in (r.get("top_blocks") or [])[:4])
        lines.append(
            "| `%s` | %s | %s | %.3f | %s | %s | %s |"
            % (r["stem"], r["style"], r["structure_ok"], r["roof_score"], r["roof_ne_wall"], roles, tops)
        )
    lines += [
        "",
        "## Residual",
        "",
        "- Specialty refs can still carry odd accents; deny list is style×role not absolute.",
        "- Very huge hollow footprints after fill may thicken floors — watch modern glass boxes.",
        "- No VAE continue-train.",
        "",
        "Previews: `previews/`, `attach_previews/`.",
        "",
    ]
    notes = [
        "# NOTES — visual rules changed",
        "",
        "- Roof deck paints filled footprint at roof_deck_y before pitch.",
        "- European/sparse: low rise + plateau_r≈0.78 so top_y cover stays high.",
        "- Style deny rejects Victorian acacia / chinese mud_bricks for house walls → bricks/planks fallbacks.",
        "- After stair→cube remap, roof must differ from wall (dark_oak/spruce/stone_bricks…).",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "NOTES.md").write_text("\n".join(notes), encoding="utf-8")
    print("OUT", out)
    print("OK", report["structure_ok"], "euro", report["european_ok"], report["european_roof"])
    print("junk", junk_walls, "roof_eq", roof_same)


if __name__ == "__main__":
    main()
