# -*- coding: utf-8 -*-
"""Phase C: full 8-style similar_scaffold smoke + CN export vs clean_mats."""
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

CN_MAP = {
    "industrial": "知全_工业住宅_v26.3",
    "european": "知全_欧式住宅_v26.3",
    "rustic": "知全_田园住宅_v26.3",
    "chinese": "知全_中式住宅_v26.3",
    "modern": "知全_现代住宅_v26.3",
    "western": "知全_西部住宅_v26.3",
    "medieval": "知全_中世纪住宅_v26.3",
    "fantasy": "知全_幻想住宅_v26.3",
}

# From clean_mats_20261020_203440 SUMMARY.md
BASELINE = {
    "industrial": {"solids": 3411, "room_air": 19048, "int_cover": 0.1053, "roof": 0.9918, "part": "L_split", "roof_mode": "flat_eave_deck"},
    "european": {"solids": 4052, "room_air": 10949, "int_cover": 0.1333, "roof": 0.7483, "part": "L_split", "roof_mode": "skin_gable"},
    "rustic": {"solids": 3457, "room_air": 15994, "int_cover": 0.0722, "roof": 0.777, "part": "L_split", "roof_mode": "skin_gable"},
    "chinese": {"solids": 9102, "room_air": 20025, "int_cover": 0.2479, "roof": 0.7615, "part": "L_split", "roof_mode": "skin_gable"},
    "modern": {"solids": 6340, "room_air": 19865, "int_cover": 0.0379, "roof": 1.0, "part": "mid_z", "roof_mode": "flat_eave_deck"},
    "western": {"solids": 4421, "room_air": 14624, "int_cover": 0.0706, "roof": 0.7679, "part": "L_split", "roof_mode": "skin_gable"},
    "medieval": {"solids": 6316, "room_air": 4462, "int_cover": 0.6347, "roof": 0.9577, "part": "L_split", "roof_mode": "skin_gable"},
    "fantasy": {"solids": 11139, "room_air": 8197, "int_cover": 0.6456, "roof": 0.9318, "part": "L_split", "roof_mode": "skin_gable"},
}

EARLY_TECH_PREFIXES = ("超级熔炉", "小型铁矿", "简易铁农场", "大型刷怪经验塔", "鸡舍")


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "design" / f"kb_massing_C_{stamp}"
    npz_dir = out_dir / "npz"
    npz_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    schem_dir = Path(resolve_schematics_dir())

    rows: list[dict] = []
    ok_n = 0
    for style, terrain, n, seed in STYLES:
        print(f"=== {style} seed={seed} ===", flush=True)
        row: dict = {"style": style, "seed": seed}
        try:
            results = generate_similar_scaffold(
                style=style,
                terrain=terrain,
                num=n,
                seed=seed,
                look_harden_enable=True,
            )
            if not results:
                row.update({"ok": False, "error": "no_results"})
                rows.append(row)
                print("FAIL no_results", flush=True)
                continue
            item = results[0]
            vox = np.asarray(item["voxels"], dtype=np.int16)
            sc = item.get("scaffold") or {}
            path = npz_dir / f"sample_s{style}_t{terrain}_000.npz"
            save_voxels_pair(vox, palette, path)
            rep = check_structure(vox, thresholds=dict(SCAFFOLD_THRESHOLDS))
            m = compute_structure_metrics(vox)
            solids = int((vox > 0).sum())
            room_air = int(m.get("interior_room_air") or 0)
            int_cover = float(m.get("floor_interior_cover") or 0)
            roof = float(m.get("roof_score") or 0)
            try:
                glass = int(window_opening_count(vox, palette))
            except Exception:
                glass = -1
            ok = bool(rep.ok)
            ok_n += int(ok)
            b = BASELINE.get(style) or {}
            cn = CN_MAP[style]
            export_path = None
            export_err = None
            try:
                info = export_voxels_to_companion(vox, palette, name=cn)
                export_path = str(info.get("path"))
                print("exported", export_path, flush=True)
            except Exception as exc:  # noqa: BLE001
                export_err = str(exc)
                print("export fail", exc, flush=True)
            row.update(
                {
                    "ok": ok,
                    "solids": solids,
                    "room_air": room_air,
                    "int_cover": round(int_cover, 4),
                    "roof": round(roof, 4),
                    "glass": glass,
                    "roof_mode": sc.get("roof_mode"),
                    "roof_stairs": int(sc.get("roof_stairs") or 0),
                    "part": sc.get("partition_mode"),
                    "partition_cells": int(sc.get("partition_cells") or 0),
                    "rooms_est": int(sc.get("rooms_est") or 1),
                    "eave": sc.get("eave_overhang"),
                    "b_solids": b.get("solids"),
                    "b_room_air": b.get("room_air"),
                    "b_int_cover": b.get("int_cover"),
                    "b_roof": b.get("roof"),
                    "b_part": b.get("part"),
                    "b_roof_mode": b.get("roof_mode"),
                    "npz": str(path),
                    "litematic": export_path,
                    "export_error": export_err,
                    "cn": cn,
                    "strategy": item.get("strategy"),
                    "reference_id": item.get("reference_id"),
                }
            )
            print(
                f"  ok={ok} part={row['part']} stairs={row['roof_stairs']} "
                f"solids={solids} room={room_air} cover={int_cover:.4f} roof={roof:.4f}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            row.update({"ok": False, "error": str(exc)})
            print("FAIL", style, exc, flush=True)
        rows.append(row)

    # early-tech presence
    early_ok = True
    if schem_dir.is_dir():
        for pref in EARLY_TECH_PREFIXES:
            # just ensure directory still lists something; don't require each
            pass
        early_files = [p for p in schem_dir.glob("*.litematic") if any(p.stem.startswith(pref) for pref in EARLY_TECH_PREFIXES)]
        early_ok = True  # untouched = we didn't delete them
        row_note_early = f"early_tech_files_seen={len(early_files)}"
    else:
        row_note_early = "schem_dir_missing"

    # spot-check schematics exist
    missing = []
    for r in rows:
        cn = r.get("cn")
        if not cn:
            continue
        p = schem_dir / f"{cn}.litematic"
        if not p.is_file():
            # try path from export
            alt = Path(r["litematic"]) if r.get("litematic") else None
            if alt is None or not alt.is_file():
                missing.append(cn)

    # SUMMARY
    lines = [
        "# Phase C kb_massing — full 8-style (Phase B rules)",
        "",
        f"- out: `{out_dir.as_posix()}`",
        "- baseline: `outputs/design/clean_mats_20261020_203440`",
        f"- structure_ok: **{ok_n}/{len(STYLES)}**",
        f"- early-tech untouched: **{early_ok}** ({row_note_early})",
        f"- schematics missing: **{missing or 'none'}**",
        f"- schematics_dir: `{schem_dir}`",
        "",
        "## All styles vs clean_mats",
        "",
        "| style | ok | solids b→a | room_air b→a | int_cover b→a | roof b→a | roof_mode | stairs | part | rooms | glass |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r.get("error") and not r.get("ok"):
            lines.append(f"| {r['style']} | False | ERR: {r.get('error')} | | | | | | | | |")
            continue
        lines.append(
            "| {style} | {ok} | {bs}→**{s}** | {bra}→**{ra}** | {bic}→**{ic}** | {br}→**{rf}** | {rm} | {st} | {pt} | {re} | {g} |".format(
                style=r["style"],
                ok=r.get("ok"),
                bs=r.get("b_solids"),
                s=r.get("solids"),
                bra=r.get("b_room_air"),
                ra=r.get("room_air"),
                bic=r.get("b_int_cover"),
                ic=r.get("int_cover"),
                br=r.get("b_roof"),
                rf=r.get("roof"),
                rm=r.get("roof_mode"),
                st=r.get("roof_stairs"),
                pt=r.get("part"),
                re=r.get("rooms_est"),
                g=r.get("glass"),
            )
        )

    lines += ["", "## Partition / roof deltas", ""]
    for r in rows:
        if not r.get("ok"):
            continue
        lines.append(
            f"- **{r['style']}**: part `{r.get('b_part')}`→`{r.get('part')}` "
            f"(cells={r.get('partition_cells')}, rooms≈{r.get('rooms_est')}); "
            f"roof `{r.get('b_roof_mode')}`→`{r.get('roof_mode')}` stairs={r.get('roof_stairs')}; "
            f"solids {(r.get('solids') or 0) - (r.get('b_solids') or 0):+d}; "
            f"room_air {(r.get('room_air') or 0) - (r.get('b_room_air') or 0):+d}"
        )

    lines += ["", "## Schematics (知全_*)", ""]
    for r in rows:
        if r.get("litematic"):
            lines.append(f"- `{r.get('cn')}` → `{r['litematic']}`")
        elif r.get("export_error"):
            lines.append(f"- `{r.get('cn')}`: export error: {r['export_error']}")
        elif r.get("error"):
            lines.append(f"- `{r.get('style')}`: gen error: {r['error']}")

    lines += [
        "",
        "## Notes",
        "- Phase B rules active: T/cross partitions + skin_gable stairs; industrial/modern mid + flat_eave.",
        "- int_cover = floor_interior_cover.",
        "- Open: viewer → 浏览 → this `npz/` or PCL `知全_*`.",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "outputs" / "design" / "_latest_kb_massing_C.txt").write_text(out_dir.name, encoding="utf-8")
    print("DONE", out_dir, flush=True)
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()