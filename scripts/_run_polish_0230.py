# -*- coding: utf-8 -*-
"""2:30 polish smoke: modern strict openings vs G; euro/chinese controls; optional 知抛_ export."""
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

# Phase G baselines (same seeds)
G = {
    "modern": {"window_cells": 529, "glass_cells": 224, "solids": 6340, "room_air": 19865, "roof": None, "seed": 905},
    "european": {"window_cells": 262, "glass_cells": 113, "solids": 4055, "room_air": 10949, "roof": None, "seed": 902},
    "chinese": {"window_cells": 362, "glass_cells": 325, "solids": 8333, "room_air": 20789, "roof": None, "seed": 904},
}

STYLES = [
    ("modern", "flat", 905),
    ("european", "flat", 902),
    ("chinese", "flat", 904),
]

CN = {
    "modern": "知抛_现代住宅_v26.3",
    "european": "知抛_欧式住宅_v26.3",
    "chinese": "知抛_中式住宅_v26.3",
}


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "outputs" / "design" / f"polish_0230_{stamp}"
    npz_dir = out / "npz"
    npz_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    schem = Path(resolve_schematics_dir())

    rows = []
    for style, terrain, seed in STYLES:
        print(f"=== {style} ===", flush=True)
        item = generate_similar_scaffold(
            style=style, terrain=terrain, num=1, seed=seed, look_harden_enable=True
        )[0]
        vox = np.asarray(item["voxels"], dtype=np.int16)
        path = npz_dir / f"sample_s{style}_t{terrain}_000.npz"
        save_voxels_pair(vox, palette, path)
        info = window_opening_count(vox, style=style)
        m = compute_structure_metrics(vox)
        g = G[style]
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
            "strict": bool(info.get("strict")),
            "part": (item.get("scaffold") or {}).get("partition_mode"),
            "roof_mode": (item.get("scaffold") or {}).get("roof_mode"),
            "g_window_cells": g["window_cells"],
            "g_glass_cells": g["glass_cells"],
            "g_solids": g["solids"],
            "npz": str(path),
        }
        # export decision per style: modern must drop window_cells clearly; controls must not regress badly
        better = False
        if style == "modern":
            better = row["ok"] and row["window_cells"] < g["window_cells"] - 100 and row["glass_cells"] <= g["glass_cells"] + 40
        else:
            # control: keep ok; window_cells not exploding; glass within ~30%
            better = row["ok"] and row["window_cells"] <= int(g["window_cells"] * 1.15) + 20
        row["export_ok"] = bool(better)
        rows.append(row)
        print(
            f"  ok={row['ok']} strict={row['strict']} win={row['window_cells']}(G{g['window_cells']}) "
            f"glass={row['glass_cells']}(G{g['glass_cells']}) solids={row['solids']} roof={row['roof']} export={better}",
            flush=True,
        )

    # Export only if modern clearly better AND controls ok
    modern = next(r for r in rows if r["style"] == "modern")
    controls_ok = all(r["export_ok"] for r in rows if r["style"] != "modern")
    do_export = bool(modern["export_ok"] and controls_ok)
    exported = []
    if do_export:
        for r in rows:
            if not r["export_ok"]:
                continue
            style = r["style"]
            vox = np.load(r["npz"])["voxels"]
            cn = CN[style]
            lit = str(export_voxels_to_companion(vox, palette, name=cn).get("path"))
            r["cn"] = cn
            r["litematic"] = lit
            exported.append(lit)
            print("exported", lit, flush=True)
    else:
        print("NO_EXPORT: modern or controls not clearly better", flush=True)

    summary = {
        "stamp": stamp,
        "out": str(out),
        "do_export": do_export,
        "exported": exported,
        "schematics_dir": str(schem),
        "rows": rows,
        "note": "2:30 Asia/Shanghai polish — modern strict_window_openings",
    }
    (out / "rows.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# polish_0230_{stamp}",
        "",
        f"- do_export: **{do_export}**",
        f"- exported: {exported or 'none'}",
        "",
        "| style | ok | strict | solids | room_air | roof | window_cells | G_win | glass | G_glass | export |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['style']} | {r['ok']} | {r['strict']} | {r['solids']} | {r['room_air']} | {r['roof']} | "
            f"{r['window_cells']} | {r['g_window_cells']} | {r['glass_cells']} | {r['g_glass_cells']} | {r['export_ok']} |"
        )
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("OUT", out, flush=True)


if __name__ == "__main__":
    main()
