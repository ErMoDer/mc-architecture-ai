# -*- coding: utf-8 -*-
"""A/B scaffold materials: before (single wall/floor mush) vs role materials."""
from __future__ import annotations

import json
import shutil
from collections import Counter
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
    ("rustic", "flat", 2, 201),  # lakeside emphasis
    ("fantasy", "flat", 2, 301),
]


def _top_blocks(vox: np.ndarray, palette: dict[int, str], k: int = 6) -> list[dict]:
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
    out = root / "outputs" / "design" / ("scaffold_materials_" + stamp)
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
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "roof_score": float(m.get("roof_score") or 0),
                "non_air": int(m.get("non_air") or 0),
                "unique_blocks": uniq,
                "reference_id": meta.get("reference_id"),
                "role_names": role_names,
                "top_blocks": tops,
                "materials_source": mats.get("source"),
                "look_actions_head": (meta.get("look_harden") or {}).get("actions", [])[:8],
            }
            for cand in (saved.get("preview_path"), meta.get("preview_path")):
                if cand and Path(cand).is_file():
                    dest = out / "previews" / (stem + ".png")
                    shutil.copy2(cand, dest)
                    row["preview"] = str(dest.relative_to(out)).replace("\\", "/")
                    if style in ("rustic", "fantasy", "medieval", "modern") or i == 0:
                        shutil.copy2(cand, out / "attach_previews" / (stem + ".png"))
                    break
            mcf = meta.get("mcfunction_path") or meta.get("mcfunction")
            if mcf and Path(mcf).is_file():
                shutil.copy2(mcf, out / "mcfunction" / Path(mcf).name)
            rows.append(row)
            print(stem, "ok", ok, "uniq", uniq, "roles", role_names, "tops", [t["name"] for t in tops[:4]])

    ok_n = sum(1 for r in rows if r["structure_ok"])
    rustic = [r for r in rows if r["style"] == "rustic"]
    fantasy = [r for r in rows if r["style"] == "fantasy"]
    report = {
        "out_dir": str(out),
        "n": len(rows),
        "structure_ok": "%d/%d" % (ok_n, len(rows)),
        "rustic_ok": "%d/%d" % (sum(1 for r in rustic if r["structure_ok"]), len(rustic)),
        "fantasy_ok": "%d/%d" % (sum(1 for r in fantasy if r["structure_ok"]), len(fantasy)),
        "rows": rows,
    }
    (out / "REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Scaffold materials polish",
        "",
        "- Time (Asia/Shanghai): %s" % stamp,
        "- Out: `%s`" % str(out).replace("\\\\", "/"),
        "- Training: **none**",
        "",
        "## What changed",
        "",
        "1. New `src/app/scaffold_materials.py`: role palettes foundation/wall/roof/floor/accent/window_frame.",
        "2. Resolve from reference top_blocks/remap_targets when available; else style fallbacks.",
        "3. `scaffold_from_occupancy` / `rule_scaffold` paint by role (roof≠wall, foundation band, corner accents).",
        "4. `look_harden` accepts `role_materials`, force-keeps those ids in palette limit, uses foundation/roof/accent in facade.",
        "",
        "## Smoke",
        "",
        "- structure_ok: **%d / %d**" % (ok_n, len(rows)),
        "- rustic: **%d / %d**; fantasy: **%d / %d**" % (
            sum(1 for r in rustic if r["structure_ok"]), len(rustic),
            sum(1 for r in fantasy if r["structure_ok"]), len(fantasy),
        ),
        "",
        "## Samples",
        "",
        "| stem | style | ok | uniq | roof | roles | top blocks |",
        "|---|---|:---:|---:|---:|---|---|",
    ]
    for r in rows:
        roles = r.get("role_names") or {}
        role_s = "%s/%s/%s" % (roles.get("wall", "?"), roles.get("roof", "?"), roles.get("foundation", "?"))
        tops = ", ".join(t["name"] for t in (r.get("top_blocks") or [])[:4])
        lines.append(
            "| `%s` | %s | %s | %d | %.3f | %s | %s |"
            % (r["stem"], r["style"], r["structure_ok"], r["unique_blocks"], r["roof_score"], role_s, tops)
        )
    lines.extend([
        "",
        "## Residual",
        "",
        "- Stairs/slabs still approximate full blocks when used as roof (palette may lack stair id for some woods).",
        "- Reference remap can still inject wool-heavy rustic tents (white_wool wall) — intentional for that ref.",
        "- No VAE train; materials only on scaffold path.",
        "",
        "Previews: `previews/`, `attach_previews/`.",
        "",
    ])
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    notes = Path(__file__).resolve().parents[1]  # unused
    (out / "NOTES.md").write_text(
        "\n".join([
            "# Visual NOTES — scaffold materials",
            "",
            "Before: scaffold painted shell+roof with one wall_id; floors with floor_id; look_harden majority-vote often collapsed to 1–2 mush blocks.",
            "",
            "After: distinct foundation / wall / roof / floor / accent on scaffold; look_harden keeps those roles.",
            "",
            "Expect: darker roof than walls on medieval/european/chinese/fantasy; cobble/stone footing; log corner accents on rustic/medieval; modern concrete/glass family.",
            "",
            "Inspect attach_previews PNGs for style hand-feel.",
            "",
        ]),
        encoding="utf-8",
    )
    print("OUT", out)
    print("structure_ok", report["structure_ok"])


if __name__ == "__main__":
    main()
