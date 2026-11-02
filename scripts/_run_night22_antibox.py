# -*- coding: utf-8 -*-
"""Night-22 Phase 1 anti-box smoke + 知齐_* export (F detector + D partitions)."""
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
]
G_ROWS = ROOT / "outputs" / "design" / "kb_massing_G_20261021_005529" / "rows.json"
CN = {
    "industrial": "夜改_工业住宅_v26.3",
    "european": "夜改_欧式住宅_v26.3",
    "rustic": "夜改_田园住宅_v26.3",
    "chinese": "夜改_中式住宅_v26.3",
}
EARLY = ("超级熔炉", "小型铁矿", "简易铁农场", "大型刷怪经验塔", "鸡舍")


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "outputs" / "design" / f"night22_{stamp}"
    npz_dir = out / "npz"
    npz_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    schem = Path(resolve_schematics_dir())

    gmap = {}
    if G_ROWS.is_file():
        for _gr in json.loads(G_ROWS.read_text(encoding="utf-8")):
            gmap[_gr["style"]] = _gr
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
            "anti_box": sc.get("anti_box"),
            "upper_setback": sc.get("upper_setback"),
            "cn": cn,
            "litematic": lit,
            "npz": str(path),
            "g_solids": (gmap.get(style) or {}).get("solids"),
            "g_room_air": (gmap.get(style) or {}).get("room_air"),
            "g_roof": (gmap.get(style) or {}).get("roof"),
            "g_stairs": (gmap.get(style) or {}).get("roof_stairs"),
        }
        rows.append(row)
        print(
            f"  ok={row['ok']} anti={row['anti_box']} setback={row['upper_setback']} "
            f"stairs={row['roof_stairs']} solids={row['solids']}(G{row['g_solids']}) "
            f"room={row['room_air']}(G{row['g_room_air']}) roof={row['roof']}(G{row['g_roof']})",
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
        "# Night-22 — canonical 8-style pack (D partitions + F window detector)",
        "",
        f"- out: `{out.as_posix()}`",
        f"- structure_ok: **{ok_n}/4**",
        f"- early-tech files seen: **{early_n}** (untouched)",
        f"- schematics missing: **{missing or 'none'}**",
        "",
        "| style | ok | anti | setback | solids | Gsol | room_air | Groom | roof | Groof | stairs | Gst | part |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| {style} | {ok} | {ab} | {ub} | {s} | {gs} | {ra} | {gra} | {rf} | {grf} | {st} | {gst} | {p} |".format(
                style=r["style"],
                ok=r["ok"],
                ab=r.get("anti_box"),
                ub=r.get("upper_setback"),
                s=r["solids"],
                gs=r.get("g_solids"),
                ra=r["room_air"],
                gra=r.get("g_room_air"),
                rf=r["roof"],
                grf=r.get("g_roof"),
                st=r["roof_stairs"],
                gst=r.get("g_stairs"),
                p=r["part"],
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
    (ROOT / "outputs" / "design" / "_latest_night22.txt").write_text(out.name, encoding="utf-8")
    print("NIGHT22_DONE", out)
    print("\n".join(lines))


if __name__ == "__main__":
    main()