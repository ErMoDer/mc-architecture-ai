# -*- coding: utf-8 -*-
"""Phase G: full 8-style batch + 知齐_* export (F detector + D partitions)."""
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
STYLES = [
    ("industrial", "flat", 1, 901),
    ("european", "flat", 1, 902),
    ("rustic", "flat", 1, 903),
    ("chinese", "flat", 1, 904),
    ("modern", "flat", 1, 905),
    ("western", "flat", 1, 906),
    ("medieval", "flat", 1, 907),
    ("fantasy", "flat", 1, 908),
]
CN = {
    "industrial": "知齐_工业住宅_v26.3",
    "european": "知齐_欧式住宅_v26.3",
    "rustic": "知齐_田园住宅_v26.3",
    "chinese": "知齐_中式住宅_v26.3",
    "modern": "知齐_现代住宅_v26.3",
    "western": "知齐_西部住宅_v26.3",
    "medieval": "知齐_中世纪住宅_v26.3",
    "fantasy": "知齐_幻想住宅_v26.3",
}
EARLY = ("超级熔炉", "小型铁矿", "简易铁农场", "大型刷怪经验塔", "鸡舍")


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "outputs" / "design" / f"kb_massing_G_{stamp}"
    npz_dir = out / "npz"
    npz_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    schem = Path(resolve_schematics_dir())

    rows = []
    for style, terrain, n, seed in STYLES:
        print(f"=== {style} ===", flush=True)
        item = generate_similar_scaffold(
            style=style, terrain=terrain, num=n, seed=seed, look_harden_enable=True
        )[0]
        vox = np.asarray(item["voxels"], dtype=np.int16)
        sc = item.get("scaffold") or {}
        path = npz_dir / f"sample_s{style}_t{terrain}_000.npz"
        save_voxels_pair(vox, palette, path)
        info = window_opening_count(vox, style=style)
        m = compute_structure_metrics(vox)
        cn = CN[style]
        lit = str(export_voxels_to_companion(vox, palette, name=cn).get("path"))
        print("exported", lit, flush=True)
        row = {
            "style": style,
            "ok": bool(check_structure(vox, thresholds=dict(SCAFFOLD_THRESHOLDS)).ok),
            "solids": int((vox > 0).sum()),
            "room_air": int(m.get("interior_room_air") or 0),
            "int_cover": round(float(m.get("floor_interior_cover") or 0), 4),
            "roof": round(float(m.get("roof_score") or 0), 4),
            "window_cells": int(info.get("window_cells") or 0),
            "glass_cells": int(info.get("glass_cells") or 0),
            "part": sc.get("partition_mode"),
            "policy": sc.get("partition_policy"),
            "rooms_est": int(sc.get("rooms_est") or 1),
            "roof_mode": sc.get("roof_mode"),
            "roof_stairs": int(sc.get("roof_stairs") or 0),
            "cn": cn,
            "litematic": lit,
            "npz": str(path),
        }
        rows.append(row)
        print(
            f"  ok={row['ok']} part={row['part']} win={row['window_cells']} "
            f"glass={row['glass_cells']} solids={row['solids']} room={row['room_air']}",
            flush=True,
        )

    early_n = sum(
        1
        for p in schem.glob("*.litematic")
        if any(p.stem.startswith(e) for e in EARLY)
    )
    missing = [r["cn"] for r in rows if not (schem / f"{r['cn']}.litematic").is_file()]
    ok_n = sum(1 for r in rows if r["ok"])

    lines = [
        "# Phase G — canonical 8-style pack (D partitions + F window detector)",
        "",
        f"- out: `{out.as_posix()}`",
        f"- structure_ok: **{ok_n}/8**",
        f"- early-tech files seen: **{early_n}** (untouched)",
        f"- schematics missing: **{missing or 'none'}**",
        "",
        "| style | ok | solids | room_air | int_cover | roof | window_cells | glass_cells | part | rooms | roof_mode | stairs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| {style} | {ok} | {s} | {ra} | {ic} | {rf} | {w} | {g} | {p} | {re} | {rm} | {st} |".format(
                style=r["style"],
                ok=r["ok"],
                s=r["solids"],
                ra=r["room_air"],
                ic=r["int_cover"],
                rf=r["roof"],
                w=r["window_cells"],
                g=r["glass_cells"],
                p=r["part"],
                re=r["rooms_est"],
                rm=r["roof_mode"],
                st=r["roof_stairs"],
            )
        )
    lines += ["", "## Schematics (知齐_*)", ""]
    for r in rows:
        lines.append(f"- `{r['cn']}` → `{r['litematic']}`")
    lines += [
        "",
        "## Open in viewer",
        f"- Default browse picks newest `outputs/design/*/npz` → this batch after launch.",
        f"- Or 浏览 → 选目录 → `{out.as_posix()}/npz`",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "outputs" / "design" / "_latest_kb_massing_G.txt").write_text(out.name, encoding="utf-8")
    print("G_DONE", out)
    print("\n".join(lines))


if __name__ == "__main__":
    main()