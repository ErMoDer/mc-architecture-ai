# -*- coding: utf-8 -*-
"""Phase F smoke: fantasy/western opening seal vs E; euro control; export 知洞_*."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np

from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.look_harden import window_opening_count
from src.app.sample_runner import save_voxels_pair
from src.app.structure_constraints import (
    SCAFFOLD_THRESHOLDS,
    check_structure,
    compute_structure_metrics,
)
from src.data.export_litematic_util import export_voxels_to_companion, resolve_schematics_dir
from src.utils import load_config, load_palette

ROOT = project_root()

# Phase E after dens (from E SUMMARY / e2)
PHASE_E = {
    "european": {"window_cells": 461, "glass_cells": 113, "solids": 4055, "room_air": 10949, "roof": 0.7483},
    "western": {"window_cells": 523, "glass_cells": None, "solids": 4445, "room_air": 14624, "roof": 0.7664},
    "fantasy": {"window_cells": 775, "glass_cells": 31, "solids": 10880, "room_air": 8462, "roof": 0.9318},
}

STYLES = [
    ("european", "flat", 902),
    ("western", "flat", 906),
    ("fantasy", "flat", 908),
]

CN = {
    "european": "知洞_欧式住宅_v26.3",
    "western": "知洞_西部住宅_v26.3",
    "fantasy": "知洞_幻想住宅_v26.3",
}


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "outputs" / "design" / f"kb_massing_F_{stamp}"
    npz_dir = out / "npz"
    npz_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])

    rows = []
    for style, terrain, seed in STYLES:
        print(f"=== {style} ===", flush=True)
        item = generate_similar_scaffold(
            style=style, terrain=terrain, num=1, seed=seed, look_harden_enable=True
        )[0]
        vox = np.asarray(item["voxels"], dtype=np.int16)
        save_voxels_pair(vox, palette, npz_dir / f"sample_s{style}_t{terrain}_000.npz")
        info = window_opening_count(vox, style=style)
        m = compute_structure_metrics(vox)
        # also measure with style=None for european fairness note
        info_n = window_opening_count(vox, style=None)
        e = PHASE_E[style]
        row = {
            "style": style,
            "ok": bool(check_structure(vox, thresholds=dict(SCAFFOLD_THRESHOLDS)).ok),
            "solids": int((vox > 0).sum()),
            "room_air": int(m.get("interior_room_air") or 0),
            "int_cover": round(float(m.get("floor_interior_cover") or 0), 4),
            "roof": round(float(m.get("roof_score") or 0), 4),
            "window_cells": int(info.get("window_cells") or 0),
            "glass_cells": int(info.get("glass_cells") or 0),
            "defect_cells": int(info.get("defect_cells") or 0),
            "window_components": int(info.get("window_components") or 0),
            "strict": bool(info.get("strict")),
            "window_cells_nonstrict_metric": int(info_n.get("window_cells") or 0),
            "part": (item.get("scaffold") or {}).get("partition_mode"),
            "e_window_cells": e["window_cells"],
            "e_glass_cells": e.get("glass_cells"),
            "e_solids": e["solids"],
            "e_room_air": e["room_air"],
            "e_roof": e["roof"],
            "cn": CN[style],
        }
        # Export if improved (window_cells down) or always for the three
        improved = row["window_cells"] < e["window_cells"] - 20 or style == "european"
        # Always export the three for this batch tag
        lit = export_voxels_to_companion(vox, palette, name=CN[style])
        row["litematic"] = str(lit.get("path"))
        row["improved"] = row["window_cells"] < e["window_cells"]
        rows.append(row)
        print(
            f"  win {e['window_cells']}->{row['window_cells']} "
            f"glass {e.get('glass_cells')}->{row['glass_cells']} "
            f"solids {e['solids']}->{row['solids']} "
            f"room {e['room_air']}->{row['room_air']} "
            f"roof {e['roof']}->{row['roof']} strict={row['strict']}",
            flush=True,
        )

    # Decide if full 8 needed: if fantasy & western improved meaningfully
    fan = next(r for r in rows if r["style"] == "fantasy")
    west = next(r for r in rows if r["style"] == "western")
    euro = next(r for r in rows if r["style"] == "european")
    meaningful = (
        (fan["e_window_cells"] - fan["window_cells"]) >= 50
        and (west["e_window_cells"] - west["window_cells"]) >= 30
        and euro["window_cells"] <= euro["e_window_cells"] + 30
    )

    lines = [
        "# Phase F — opening/defect seal (fantasy & western)",
        "",
        f"- out: `{out.as_posix()}`",
        f"- vs Phase E: `kb_massing_E_20261021_004704`",
        f"- structure_ok: **{sum(1 for r in rows if r['ok'])}/3**",
        f"- meaningful_drop: **{meaningful}**",
        "",
        "| style | ok | window_cells E→F | glass_cells E→F | solids E→F | room_air E→F | roof E→F | part |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        eg = r["e_glass_cells"] if r["e_glass_cells"] is not None else "?"
        lines.append(
            "| {s} | {ok} | {ew}→**{w}** ({dw:+d}) | {eg}→**{g}** | {es}→**{sol}** ({ds:+d}) | {er}→**{ra}** ({dr:+d}) | {erf}→**{rf}** | {p} |".format(
                s=r["style"],
                ok=r["ok"],
                ew=r["e_window_cells"],
                w=r["window_cells"],
                dw=r["window_cells"] - r["e_window_cells"],
                eg=eg,
                g=r["glass_cells"],
                es=r["e_solids"],
                sol=r["solids"],
                ds=r["solids"] - r["e_solids"],
                er=r["e_room_air"],
                ra=r["room_air"],
                dr=r["room_air"] - r["e_room_air"],
                erf=r["e_roof"],
                rf=r["roof"],
                p=r["part"],
            )
        )
    lines += [
        "",
        "## Schematics (知洞_*)",
        "",
    ]
    for r in rows:
        lines.append(f"- `{r['cn']}` → `{r.get('litematic')}`")
    lines += [
        "",
        "## Notes",
        "- Strict openings: fantasy/western keep only rect mid ≤2×2 or repeating rect; seal near_rect_mid.",
        "- Metrics always split window_cells (openings kept) vs glass_cells (panes).",
        "- european control should not worsen.",
        f"- KB: `docs/mc-knowledge/builds/window-opening-seal.md`; rules v5.",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "outputs" / "design" / "_latest_kb_massing_F.txt").write_text(out.name, encoding="utf-8")
    print("DONE", out)
    print("\n".join(lines))


if __name__ == "__main__":
    main()