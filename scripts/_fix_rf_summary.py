# -*- coding: utf-8 -*-
import json, shutil
from pathlib import Path

out = Path(r"E:\ai agent\mc-architecture-ai\outputs\design\rustic_fantasy_samples_20261019_162846")
# When run on Windows machine path; if on box, adjust
import os
if not out.exists():
    out = Path("outputs/design/rustic_fantasy_samples_20261019_162846")

r = json.loads((out / "REPORT.json").read_text(encoding="utf-8"))
c = r["counts"]
lines = [
    "# Rustic / Fantasy specialty-pool samples",
    "",
    "- Time (Asia/Shanghai): %s -> %s" % (r["started_at"], r["finished_at"]),
    "- Strategy: **similar_scaffold** (look_harden ON, vae_fill OFF)",
    "- Pool: `outputs/design/rustic_fantasy_pool_20261019_160540/`",
    "- Output: `%s`" % str(out).replace("\\", "/"),
    "- Training: **none**; `checkpoints/cond_last.pt` not overwritten",
    "",
    "## Counts",
    "",
    "| rustic | fantasy | total | structure_ok | mcblock refs |",
    "|---:|---:|---:|---:|---:|",
    "| %s | %s | %s | %s | %s |" % (c["rustic"], c["fantasy"], c["total"], c["structure_ok"], c["mcblock_refs"]),
    "",
    "## Samples",
    "",
    "| stem | STYLE | terrain | structure_ok | non_air | roof | hollow | ref used | mcblock | preview |",
    "|---|---|---|:---:|---:|---:|---:|---|:---:|---|",
]
for s in r["samples"]:
    m = s.get("structure_metrics") or {}
    roof = m.get("roof_score")
    hollow = m.get("hollow_score")
    roof_s = ("%.3f" % roof) if roof is not None else "-"
    holl_s = ("%.3f" % hollow) if hollow is not None else "-"
    lines.append(
        "| `%s` | %s | %s | %s | %s | %s | %s | `%s` | %s | %s |"
        % (
            s["stem"], s["style"], s["terrain"], s["structure_ok"], s["non_air"],
            roof_s, holl_s, s["reference_id"], s["is_mcblock"], s["preview"],
        )
    )
lines += [
    "",
    "## Ref check",
    "",
    "- All **11/11** refs are `data/raw/mcblock/...` (no european fallback, no Hack337).",
    "- Rustic unique refs (specialty pool, only 3 mcblock houses):",
]
for rid in sorted({s["reference_id"] for s in r["samples"] if s["style"] == "rustic"}):
    lines.append("  - `%s`" % rid)
lines.append("- Fantasy unique refs:")
for rid in sorted({s["reference_id"] for s in r["samples"] if s["style"] == "fantasy"}):
    lines.append("  - `%s`" % rid)
lines += [
    "",
    "## Structure notes",
    "",
    "- Fantasy: **6/6** structure_ok under SCAFFOLD_THRESHOLDS.",
    "- Rustic: **1/5** ok. Failures are low roof_score on lakeside-house skeletons after scaffold; white camping tent passes.",
    "- Duplicate rustic stems 003/004 re-cycle the same 3 refs (i % len(refs)).",
    "- structure_ok is not look quality — inspect PNGs.",
    "",
    "## How to open",
    "",
    "- PNG previews: `previews/*.png`",
    "- Quick attach: `attach_previews/`",
    "- Load `.npz` in `scripts/viewer_app.py`",
    "- `.mcfunction` under `mcfunction/` for in-game setblock paste",
    "",
]
(out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
att = out / "attach_previews"
att.mkdir(exist_ok=True)
for name in [
    "sample_srustic_tflat_002.png",
    "sample_srustic_tflat_001.png",
    "sample_sfantasy_tflat_000.png",
    "sample_sfantasy_tflat_001.png",
    "sample_sfantasy_tflat_003.png",
]:
    src = out / "previews" / name
    if src.exists():
        shutil.copy2(src, att / name)
print("rewrote", out / "SUMMARY.md")
print("european?", any("意式" in (s["reference_id"] or "") for s in r["samples"]))
print("mcblock", c["mcblock_refs"], "/", c["total"])
