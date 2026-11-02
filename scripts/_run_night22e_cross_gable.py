# -*- coding: utf-8 -*-
"""Night-22e: lightweight intersecting / cross-gable smoke + optional 夜坡_* export."""
from __future__ import annotations

import json
import sys
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

SMOKE_STYLES = [
    ("industrial", "flat", 1, 901),
    ("european", "flat", 1, 902),
    ("chinese", "flat", 1, 904),
]
FULL_STYLES = [
    ("industrial", "flat", 1, 901),
    ("european", "flat", 1, 902),
    ("rustic", "flat", 1, 903),
    ("chinese", "flat", 1, 904),
    ("modern", "flat", 1, 905),
    ("western", "flat", 1, 906),
    ("medieval", "flat", 1, 907),
    ("fantasy", "flat", 1, 908),
]
G_ROWS = ROOT / "outputs" / "design" / "kb_massing_G_20261021_005529" / "rows.json"
N22D_LATEST = ROOT / "outputs" / "design" / "_latest_night22d.txt"
CN = {
    "industrial": "夜坡_工业住宅_v26.3",
    "european": "夜坡_欧式住宅_v26.3",
    "rustic": "夜坡_田园住宅_v26.3",
    "chinese": "夜坡_中式住宅_v26.3",
    "modern": "夜坡_现代住宅_v26.3",
    "western": "夜坡_西部住宅_v26.3",
    "medieval": "夜坡_中世纪住宅_v26.3",
    "fantasy": "夜坡_奇幻住宅_v26.3",
}
EARLY = ("熔炉高炉", "小黑窑", "早期农舍", "早期刷怪笼", "早期")


def _load_map(path: Path) -> dict:
    if not path.is_file():
        return {}
    return {r["style"]: r for r in json.loads(path.read_text(encoding="utf-8"))}


def run(styles, *, export: bool, tag: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "outputs" / "design" / f"night22e_{tag}_{stamp}"
    npz_dir = out / "npz"
    npz_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    schem = Path(resolve_schematics_dir())

    gmap = _load_map(G_ROWS)
    dmap = {}
    if N22D_LATEST.is_file():
        dpath = ROOT / "outputs" / "design" / N22D_LATEST.read_text(encoding="utf-8").strip() / "rows.json"
        dmap = _load_map(dpath)

    rows = []
    for style, terrain, n, seed in styles:
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
        lit = None
        if export:
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
            "roof_mode": sc.get("roof_mode"),
            "roof_stairs": int(sc.get("roof_stairs") or 0),
            "anti_box": sc.get("anti_box"),
            "upper_setback": sc.get("upper_setback"),
            "porch": sc.get("porch"),
            "cross_gable": bool(sc.get("cross_gable")),
            "cross_raised": int(sc.get("cross_raised") or 0),
            "ridge_reinforce": int(sc.get("ridge_reinforce") or 0),
            "cn": cn,
            "litematic": lit,
            "npz": str(path),
            "g_solids": (gmap.get(style) or {}).get("solids"),
            "g_room_air": (gmap.get(style) or {}).get("room_air"),
            "g_roof": (gmap.get(style) or {}).get("roof"),
            "d_roof": (dmap.get(style) or {}).get("roof"),
            "d_room_air": (dmap.get(style) or {}).get("room_air"),
            "d_stairs": (dmap.get(style) or {}).get("roof_stairs"),
        }
        rows.append(row)
        print(
            f"  ok={row['ok']} anti={row['anti_box']} cross={row['cross_gable']}"
            f"({row['cross_raised']}) mode={row['roof_mode']} "
            f"stairs={row['roof_stairs']} roof={row['roof']}"
            f"(G{row['g_roof']}/D{row['d_roof']}) "
            f"room={row['room_air']}(G{row['g_room_air']}/D{row['d_room_air']})",
            flush=True,
        )

    ok_n = sum(1 for r in rows if r["ok"])
    lines = [
        f"# Night-22e cross-gable ({tag})",
        "",
        f"- out: `{out.as_posix()}`",
        f"- structure_ok: **{ok_n}/{len(rows)}**",
        f"- export: **{export}**",
        "",
        "| style | ok | anti | cross | mode | roof | G | D | room | Groom | Droom | stairs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| {style} | {ok} | {ab} | {cg}/{cr} | {rm} | {rf} | {grf} | {drf} | {ra} | {gra} | {dra} | {st} |".format(
                style=r["style"],
                ok=r["ok"],
                ab=r.get("anti_box"),
                cg=r.get("cross_gable"),
                cr=r.get("cross_raised"),
                rm=r.get("roof_mode"),
                rf=r["roof"],
                grf=r.get("g_roof"),
                drf=r.get("d_roof"),
                ra=r["room_air"],
                gra=r.get("g_room_air"),
                dra=r.get("d_room_air"),
                st=r["roof_stairs"],
            )
        )
    if export:
        lines += ["", "## Schematics (夜坡_*)", ""]
        for r in rows:
            lines.append(f"- `{r['cn']}` → `{r['litematic']}`")
        early_n = sum(
            1 for p in schem.glob("*.litematic") if any(p.stem.startswith(e) for e in EARLY)
        )
        missing = [r["cn"] for r in rows if not (schem / f"{r['cn']}.litematic").is_file()]
        lines += [
            "",
            f"- early-tech files seen: **{early_n}** (untouched)",
            f"- schematics missing: **{missing or 'none'}**",
        ]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "outputs" / "design" / f"_latest_night22e_{tag}.txt").write_text(out.name, encoding="utf-8")
    print("NIGHT22E_DONE", out)
    print("\n".join(lines))
    return out


def main() -> None:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "smoke").strip().lower()
    if mode == "full":
        run(FULL_STYLES, export=True, tag="full")
    else:
        run(SMOKE_STYLES, export=False, tag="smoke")


if __name__ == "__main__":
    main()
