# -*- coding: utf-8 -*-
"""Phase E: full 8-style smoke under D partitions; export 知新_*."""
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
    "industrial": "知新_工业住宅_v26.3",
    "european": "知新_欧式住宅_v26.3",
    "rustic": "知新_田园住宅_v26.3",
    "chinese": "知新_中式住宅_v26.3",
    "modern": "知新_现代住宅_v26.3",
    "western": "知新_西部住宅_v26.3",
    "medieval": "知新_中世纪住宅_v26.3",
    "fantasy": "知新_幻想住宅_v26.3",
}

EARLY = ("超级熔炉", "小型铁矿", "简易铁农场", "大型刷怪经验塔", "鸡舍")


def _glass(vox) -> int:
    try:
        info = window_opening_count(vox)
        if isinstance(info, dict):
            for k in ("window_openings", "openings", "count", "n_windows", "windows"):
                if k in info:
                    return int(info[k])
            for k, v in info.items():
                if "window" in str(k) and isinstance(v, (int, float, np.integer)):
                    return int(v)
            return int(info.get("n") or 0)
        return int(info)
    except Exception:
        return -1


def run_styles(styles, out_dir: Path, cn_map: dict, tag: str) -> list[dict]:
    npz_dir = out_dir / "npz"
    npz_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    rows = []
    for style, terrain, n, seed in styles:
        print(f"=== [{tag}] {style} ===", flush=True)
        try:
            item = generate_similar_scaffold(
                style=style, terrain=terrain, num=n, seed=seed, look_harden_enable=True
            )[0]
            vox = np.asarray(item["voxels"], dtype=np.int16)
            sc = item.get("scaffold") or {}
            path = npz_dir / f"sample_s{style}_t{terrain}_000.npz"
            save_voxels_pair(vox, palette, path)
            rep = check_structure(vox, thresholds=dict(SCAFFOLD_THRESHOLDS))
            m = compute_structure_metrics(vox)
            cn = cn_map[style]
            lit = None
            try:
                lit = str(export_voxels_to_companion(vox, palette, name=cn).get("path"))
                print("exported", lit, flush=True)
            except Exception as exc:
                print("export fail", exc, flush=True)
            row = {
                "style": style,
                "ok": bool(rep.ok),
                "solids": int((vox > 0).sum()),
                "room_air": int(m.get("interior_room_air") or 0),
                "int_cover": round(float(m.get("floor_interior_cover") or 0), 4),
                "roof": round(float(m.get("roof_score") or 0), 4),
                "glass": _glass(vox),
                "part": sc.get("partition_mode"),
                "policy": sc.get("partition_policy"),
                "partition_cells": int(sc.get("partition_cells") or 0),
                "rooms_est": int(sc.get("rooms_est") or 1),
                "roof_mode": sc.get("roof_mode"),
                "roof_stairs": int(sc.get("roof_stairs") or 0),
                "litematic": lit,
                "cn": cn,
                "npz": str(path),
            }
            rows.append(row)
            print(
                f"  ok={row['ok']} part={row['part']} glass={row['glass']} "
                f"solids={row['solids']} room={row['room_air']}",
                flush=True,
            )
        except Exception as exc:
            rows.append({"style": style, "ok": False, "error": str(exc)})
            print("FAIL", style, exc, flush=True)
    return rows


def write_summary(out_dir: Path, rows: list[dict], title: str, note_lines: list[str]) -> None:
    schem = Path(resolve_schematics_dir())
    early_n = 0
    if schem.is_dir():
        early_n = sum(1 for p in schem.glob("*.litematic") if any(p.stem.startswith(e) for e in EARLY))
    ok_n = sum(1 for r in rows if r.get("ok"))
    lines = [
        f"# {title}",
        "",
        f"- out: `{out_dir.as_posix()}`",
        f"- structure_ok: **{ok_n}/{len(rows)}**",
        f"- early-tech untouched (files seen): **{early_n}**",
        f"- schematics_dir: `{schem}`",
        "",
        "| style | ok | solids | room_air | int_cover | roof | glass | part | policy | rooms | roof_mode | stairs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r.get("error"):
            lines.append(f"| {r['style']} | False | ERR {r['error']} | | | | | | | | | |")
            continue
        lines.append(
            "| {style} | {ok} | {s} | {ra} | {ic} | {rf} | {g} | {p} | {pol} | {re} | {rm} | {st} |".format(
                style=r["style"],
                ok=r.get("ok"),
                s=r.get("solids"),
                ra=r.get("room_air"),
                ic=r.get("int_cover"),
                rf=r.get("roof"),
                g=r.get("glass"),
                p=r.get("part"),
                pol=r.get("policy"),
                re=r.get("rooms_est"),
                rm=r.get("roof_mode"),
                st=r.get("roof_stairs"),
            )
        )
    lines += ["", "## Schematics", ""]
    for r in rows:
        if r.get("litematic"):
            lines.append(f"- `{r.get('cn')}` → `{r['litematic']}`")
    lines += ["", "## Notes", ""] + [f"- {n}" for n in note_lines] + [""]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "outputs" / "design" / f"kb_massing_E_{stamp}"
    rows = run_styles(STYLES, out_dir, CN_MAP, "E1")
    write_summary(
        out_dir,
        rows,
        "Phase E1 — full 8-style (D partition policy)",
        [
            "D tiers: mild=chinese/medieval/fantasy; strong=euro/rustic/western; open=industrial/modern.",
            "Export prefix 知新_*.",
        ],
    )
    (ROOT / "outputs" / "design" / "_latest_kb_massing_E.txt").write_text(out_dir.name, encoding="utf-8")
    # Persist path for E2
    (out_dir / "batch_name.txt").write_text(out_dir.name, encoding="utf-8")
    print("E1_DONE", out_dir)
    # Print glass compare
    by = {r["style"]: r for r in rows if r.get("ok")}
    if "fantasy" in by and "european" in by:
        print(
            "GLASS_COMPARE fantasy",
            by["fantasy"]["glass"],
            "european",
            by["european"]["glass"],
            "ratio",
            round(by["fantasy"]["glass"] / max(1, by["european"]["glass"]), 2),
        )


if __name__ == "__main__":
    main()