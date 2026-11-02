# -*- coding: utf-8 -*-
"""Phase D smoke: 5 styles vs Phase C; export 知收_."""
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

# Same seeds as Phase C for fair compare
STYLES = [
    ("european", "flat", 1, 902),
    ("rustic", "flat", 1, 903),
    ("chinese", "flat", 1, 904),
    ("medieval", "flat", 1, 907),
    ("fantasy", "flat", 1, 908),
]

CN_MAP = {
    "european": "知收_欧式住宅_v26.3",
    "rustic": "知收_田园住宅_v26.3",
    "chinese": "知收_中式住宅_v26.3",
    "medieval": "知收_中世纪住宅_v26.3",
    "fantasy": "知收_幻想住宅_v26.3",
}

# Phase C rows (from kb_massing_C SUMMARY)
PHASE_C = {
    "european": {"solids": 4055, "room_air": 10949, "int_cover": 0.1346, "roof": 0.7483, "part": "cross_split", "stairs": 72},
    "rustic": {"solids": 3485, "room_air": 15992, "int_cover": 0.0784, "roof": 0.775, "part": "cross_split", "stairs": 28},
    "chinese": {"solids": 9376, "room_air": 19751, "int_cover": 0.2627, "roof": 0.7611, "part": "cross_split", "stairs": 14},
    "medieval": {"solids": 6544, "room_air": 4255, "int_cover": 0.6857, "roof": 0.9577, "part": "cross_split", "stairs": 13},
    "fantasy": {"solids": 11205, "room_air": 8134, "int_cover": 0.6469, "roof": 0.9318, "part": "cross_split", "stairs": 24},
}


def _glass_count(vox) -> int:
    try:
        info = window_opening_count(vox)
        if isinstance(info, dict):
            for k in ("window_openings", "openings", "count", "n_windows", "windows"):
                if k in info:
                    return int(info[k])
            # sum numeric values that look like counts
            for k, v in info.items():
                if "window" in k and isinstance(v, (int, float, np.integer)):
                    return int(v)
            return int(info.get("n") or 0)
        return int(info)
    except Exception:
        return -1


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "design" / f"kb_massing_D_{stamp}"
    npz_dir = out_dir / "npz"
    npz_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    schem_dir = Path(resolve_schematics_dir())

    rows = []
    ok_n = 0
    for style, terrain, n, seed in STYLES:
        print(f"=== {style} ===", flush=True)
        item = generate_similar_scaffold(
            style=style, terrain=terrain, num=n, seed=seed, look_harden_enable=True
        )[0]
        vox = np.asarray(item["voxels"], dtype=np.int16)
        sc = item.get("scaffold") or {}
        path = npz_dir / f"sample_s{style}_t{terrain}_000.npz"
        save_voxels_pair(vox, palette, path)
        rep = check_structure(vox, thresholds=dict(SCAFFOLD_THRESHOLDS))
        m = compute_structure_metrics(vox)
        ok = bool(rep.ok)
        ok_n += int(ok)
        c = PHASE_C[style]
        solids = int((vox > 0).sum())
        room_air = int(m.get("interior_room_air") or 0)
        int_cover = float(m.get("floor_interior_cover") or 0)
        roof = float(m.get("roof_score") or 0)
        glass = _glass_count(vox)
        cn = CN_MAP[style]
        lit = None
        try:
            lit = str(export_voxels_to_companion(vox, palette, name=cn).get("path"))
            print("exported", lit, flush=True)
        except Exception as exc:
            print("export fail", exc, flush=True)
        row = {
            "style": style,
            "ok": ok,
            "solids": solids,
            "room_air": room_air,
            "int_cover": round(int_cover, 4),
            "roof": round(roof, 4),
            "glass": glass,
            "part": sc.get("partition_mode"),
            "policy": sc.get("partition_policy") if "partition_policy" in sc else None,
            "partition_cells": int(sc.get("partition_cells") or 0),
            "rooms_est": int(sc.get("rooms_est") or 1),
            "roof_mode": sc.get("roof_mode"),
            "roof_stairs": int(sc.get("roof_stairs") or 0),
            "c_solids": c["solids"],
            "c_room_air": c["room_air"],
            "c_int_cover": c["int_cover"],
            "c_part": c["part"],
            "litematic": lit,
            "cn": cn,
            "npz": str(path),
        }
        # partition policy may be nested only in place fn info — check scaffold keys
        if row["policy"] is None:
            row["policy"] = sc.get("partition_policy") or sc.get("policy")
        rows.append(row)
        print(
            f"  part {c['part']}->{row['part']} cells={row['partition_cells']} "
            f"room {c['room_air']}->{room_air} ({room_air - c['room_air']:+d}) "
            f"solids {c['solids']}->{solids} ({solids - c['solids']:+d}) cover={int_cover:.4f} glass={glass}",
            flush=True,
        )

    # Also stash partition policy into scaffold stats if missing — read from regenerate note
    # Ensure policy is recorded: peek gen by checking rooms/part only

    lines = [
        "# Phase D kb_massing — style-aware milder partitions",
        "",
        f"- out: `{out_dir.as_posix()}`",
        "- vs Phase C: `outputs/design/kb_massing_C_20261021_004326`",
        f"- structure_ok: **{ok_n}/{len(STYLES)}**",
        f"- schematics_dir: `{schem_dir}`",
        "",
        "## vs Phase C (same seeds)",
        "",
        "| style | ok | part C→D | cells | solids C→D | room_air C→D | int_cover C→D | roof | stairs | glass |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| {style} | {ok} | {cp}→**{p}** | {cells} | {cs}→**{s}** ({ds:+d}) | {cr}→**{ra}** ({dra:+d}) | {cc}→**{ic}** | {rf} | {st} | {g} |".format(
                style=r["style"],
                ok=r["ok"],
                cp=r["c_part"],
                p=r["part"],
                cells=r["partition_cells"],
                cs=r["c_solids"],
                s=r["solids"],
                ds=r["solids"] - r["c_solids"],
                cr=r["c_room_air"],
                ra=r["room_air"],
                dra=r["room_air"] - r["c_room_air"],
                cc=r["c_int_cover"],
                ic=r["int_cover"],
                rf=r["roof"],
                st=r["roof_stairs"],
                g=r["glass"],
            )
        )
    lines += ["", "## Highlights", ""]
    for r in rows:
        lines.append(
            f"- **{r['style']}**: `{r['c_part']}`→`{r['part']}` rooms≈{r['rooms_est']}; "
            f"room_air {r['room_air'] - r['c_room_air']:+d}; solids {r['solids'] - r['c_solids']:+d}; "
            f"cover {r['int_cover'] - r['c_int_cover']:+.4f}"
        )
    lines += ["", "## Schematics (知收_*)", ""]
    for r in rows:
        if r.get("litematic"):
            lines.append(f"- `{r['cn']}` → `{r['litematic']}`")
    lines += [
        "",
        "## Notes",
        "- Mild tier (chinese/medieval/fantasy): mid/short L + ~1-story height cap; no cross.",
        "- Strong tier (european/rustic): keep cross/T when cavity allows.",
        "- KB: `docs/mc-knowledge/builds/partition-style-policy.md`; rules.json v4.",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "outputs" / "design" / "_latest_kb_massing_D.txt").write_text(out_dir.name, encoding="utf-8")
    print("DONE", out_dir)
    print("\n".join(lines))


if __name__ == "__main__":
    main()