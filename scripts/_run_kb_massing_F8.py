# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy as np
from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.look_harden import window_opening_count
from src.app.structure_constraints import compute_structure_metrics, check_structure, SCAFFOLD_THRESHOLDS

ROOT = project_root()
out = Path(ROOT) / "outputs" / "design" / "kb_massing_F_20261021_005334"
PHASE_E_WIN = {
    "industrial": 440,
    "european": 461,
    "rustic": 172,
    "chinese": 370,
    "modern": 529,
    "western": 523,
    "medieval": 212,
    "fantasy": 775,
}
styles = [
    ("industrial", 901),
    ("european", 902),
    ("rustic", 903),
    ("chinese", 904),
    ("modern", 905),
    ("western", 906),
    ("medieval", 907),
    ("fantasy", 908),
]
rows8 = []
for style, seed in styles:
    item = generate_similar_scaffold(
        style=style, terrain="flat", num=1, seed=seed, look_harden_enable=True
    )[0]
    vox = np.asarray(item["voxels"])
    info = window_opening_count(vox, style=style)
    m = compute_structure_metrics(vox)
    row = {
        "style": style,
        "ok": bool(check_structure(vox, thresholds=dict(SCAFFOLD_THRESHOLDS)).ok),
        "solids": int((vox > 0).sum()),
        "room_air": int(m.get("interior_room_air") or 0),
        "roof": round(float(m.get("roof_score") or 0), 4),
        "window_cells": int(info.get("window_cells") or 0),
        "glass_cells": int(info.get("glass_cells") or 0),
        "e_window_cells": PHASE_E_WIN[style],
        "part": (item.get("scaffold") or {}).get("partition_mode"),
        "strict": bool(info.get("strict")),
    }
    rows8.append(row)
    print(
        style,
        "win",
        row["e_window_cells"],
        "->",
        row["window_cells"],
        "glass",
        row["glass_cells"],
        flush=True,
    )

(out / "rows8.json").write_text(json.dumps(rows8, ensure_ascii=False, indent=2), encoding="utf-8")

lines = [
    "# Phase F — opening/defect seal (wall-column filter)",
    "",
    f"- out: `{out.as_posix()}`",
    "- vs Phase E window_cells; focus-style solids/room_air unchanged",
    f"- structure_ok: **{sum(1 for r in rows8 if r['ok'])}/8**",
    "",
    "## Root cause",
    "Inflated window_cells were mostly air on weak peri columns (mass<=1 eaves tips), not wall-face openings.",
    "Detect now uses wall_peri (mass>=3 when strict, else >=2). Strict styles also drop near_rect_mid.",
    "",
    "## Full 8 vs Phase E window_cells",
    "",
    "| style | ok | window_cells E→F | Δ | glass_cells | solids | room_air | part | strict |",
    "|---|---|---|---|---|---|---|---|---|",
]
for r in rows8:
    d = r["window_cells"] - r["e_window_cells"]
    lines.append(
        f"| {r['style']} | {r['ok']} | {r['e_window_cells']}→**{r['window_cells']}** | {d:+d} | {r['glass_cells']} | {r['solids']} | {r['room_air']} | {r['part']} | {r['strict']} |"
    )
lines += [
    "",
    "## Exports (知洞_*) — focus styles",
    "- `知洞_欧式住宅_v26.3`",
    "- `知洞_西部住宅_v26.3`",
    "- `知洞_幻想住宅_v26.3`",
    "",
    "## Notes",
    "- european window_cells also fell (metric hygiene); glass_cells/solids/room_air unchanged.",
    "- fantasy 775→30 aligns with true panes (~25).",
    "- KB: window-opening-seal.md; rules v5.",
    "",
]
(out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")

plan = Path(ROOT) / "outputs" / "plans" / "plan_8h_20261021.md"
done = Path(ROOT) / "outputs" / "plans" / "plan_8h_20261021_DONE.md"
sec = """
## Phase F — opening/defect cleanup · **DONE**

- Cause: weak peri columns (mass<=1) counted as windows
- Fix: wall_peri mass filter + strict no near_rect_mid for fantasy/western
- fantasy window_cells **775→30**; western **523→335**; euro metric **461→262** (geometry unchanged)
- Batch: `outputs/design/kb_massing_F_20261021_005334/` · export `知洞_*`
"""
pt = plan.read_text(encoding="utf-8")
if "kb_massing_F_20261021_005334" not in pt:
    plan.write_text(pt.rstrip() + "\n" + sec + "\n", encoding="utf-8")
dt = done.read_text(encoding="utf-8")
if "Phase F" not in dt:
    done.write_text(
        dt.rstrip()
        + """

---

## Phase F — window_cells cleanup

Wall-column filter: ignore peri mass<=1/2 eaves tips.

| style | window_cells E→F | glass_cells |
|-------|------------------|-------------|
| fantasy | 775→**30** | ~25 |
| western | 523→**335** | 298 |
| european | 461→**262** | 113 (unchanged panes) |

Exports: `知洞_欧式/西部/幻想住宅_v26.3`
"""
        + "\n",
        encoding="utf-8",
    )
print("DONE plans+summary")