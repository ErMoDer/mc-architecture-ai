# -*- coding: utf-8 -*-
"""Regen similar_scaffold after block/structure cognition pass; compare vs shell_hollow."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

import src.app.look_harden as _lh
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

STYLES = [
    ("industrial", "flat", 1, 601),
    ("european", "flat", 1, 602),
    ("rustic", "flat", 1, 603),
    ("chinese", "flat", 1, 604),
    ("modern", "flat", 1, 605),
    ("western", "flat", 1, 606),
    ("medieval", "flat", 1, 607),
    ("fantasy", "flat", 1, 608),
]

CN_MAP = {
    "industrial": "知构_工业住宅_v26.3",
    "european": "知构_欧式住宅_v26.3",
    "rustic": "知构_田园住宅_v26.3",
    "chinese": "知构_中式住宅_v26.3",
    "modern": "知构_现代住宅_v26.3",
    "western": "知构_西部住宅_v26.3",
    "medieval": "知构_中世纪住宅_v26.3",
    "fantasy": "知构_幻想住宅_v26.3",
}

EARLY_TECH_PREFIXES = (
    "超级熔炉",
    "小型铁矿",
    "简易铁农场",
    "大型刷怪经验塔",
    "鸡舍",
)

FOCUS = ("european", "industrial", "rustic")


def _render_iso(vox, palette, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from src.app.mc_render import render_mc_voxels

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="3d")
    render_mc_voxels(ax, fig, vox, palette, performance=True)
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _baseline_shell(root: Path) -> Path | None:
    design = root / "outputs" / "design"
    rid = design / "_latest_shell_hollow.txt"
    if rid.is_file():
        p = design / rid.read_text(encoding="utf-8").strip()
        if p.is_dir():
            return p
    cands = sorted(design.glob("shell_hollow_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def _metrics_from_npz(npz_path: Path) -> dict:
    with np.load(npz_path) as data:
        key = "voxels" if "voxels" in data.files else data.files[0]
        vox = np.asarray(data[key])
    m = compute_structure_metrics(vox)
    rep = check_structure(vox, SCAFFOLD_THRESHOLDS)
    return {
        "non_air": int(m.get("non_air") or 0),
        "hollow_score": float(m.get("hollow_score") or 0),
        "max_enclosed_air_cc": int(m.get("max_enclosed_air_cc") or 0),
        "floor_cover_mean": float(m.get("floor_cover_mean") or 0),
        "floor_interior_cover": float(m.get("floor_interior_cover") or 0),
        "interior_room_air": int(m.get("interior_room_air") or 0),
        "roof_score": float(m.get("roof_score") or 0),
        "structure_ok": bool(rep.ok),
        "reasons": list(rep.reasons),
    }


def main() -> None:
    root = project_root()
    cfg = load_config(root / "configs/default.yaml")
    palette = load_palette(root / cfg["data"]["palette_path"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = root / "outputs" / "design" / ("block_struct_" + stamp)
    for sub in ("previews", "attach_previews", "npz", "mcfunction", "raw_by_case"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    baseline_dir = _baseline_shell(root)
    before: dict[str, dict] = {}
    if baseline_dir is not None:
        rep_path = baseline_dir / "report.json"
        if rep_path.is_file():
            old = json.loads(rep_path.read_text(encoding="utf-8"))
            for row in old.get("rows") or []:
                style = row.get("style")
                stem = row.get("stem")
                npz = baseline_dir / "npz" / (stem + ".npz")
                if not npz.is_file():
                    npz = baseline_dir / "npz" / (stem + ".npz.npz")
                if npz.is_file():
                    before[style] = _metrics_from_npz(npz)
                elif style:
                    # fall back to report numbers
                    before[style] = {
                        "non_air": int(row.get("non_air") or 0),
                        "hollow_score": float(row.get("hollow_score") or 0),
                        "max_enclosed_air_cc": int(row.get("max_enclosed_air_cc") or 0),
                        "floor_cover_mean": float(row.get("floor_cover_mean") or 0),
                        "floor_interior_cover": float(row.get("floor_interior_cover") or 0),
                        "interior_room_air": int(row.get("interior_room_air") or 0),
                        "roof_score": float(row.get("roof_score") or 0),
                        "structure_ok": bool(row.get("structure_ok")),
                        "reasons": list(row.get("reasons") or []),
                    }
        print("BASELINE", baseline_dir)

    rows = []
    for style, terrain, num, seed0 in STYLES:
        metas = generate_similar_scaffold(
            style=style,
            terrain=terrain,
            num=num,
            out_dir=out / "raw_by_case" / style,
            seed=seed0,
            top_k_refs=3,
            vae_fill=False,
            look_harden_enable=True,
        )
        for i, meta in enumerate(metas):
            vox = meta["voxels"]
            m = compute_structure_metrics(vox)
            st = meta.get("structure") or {}
            ok = bool(st.get("ok")) if isinstance(st, dict) else check_structure(vox, SCAFFOLD_THRESHOLDS).ok
            reasons = list((st.get("reasons") if isinstance(st, dict) else None) or [])
            _lh._PALETTE_REF = palette
            win = window_opening_count(vox)
            glass_by_name = 0
            for bid in np.unique(vox[vox > 0]):
                name = str(palette.get(int(bid), ""))
                if "glass" in name.lower() or name.endswith("_pane"):
                    glass_by_name += int((vox == bid).sum())

            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            npz_path = out / "npz" / (stem + ".npz")
            save_voxels_pair(vox, palette, npz_path)
            prev = out / "previews" / (stem + ".png")
            _render_iso(vox, palette, prev)
            shutil.copy2(prev, out / "attach_previews" / (stem + ".png"))

            sc = meta.get("scaffold") or {}
            mats = meta.get("materials") or {}
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "reasons": reasons,
                "non_air": int(m.get("non_air") or 0),
                "hollow_score": round(float(m.get("hollow_score") or 0), 4),
                "max_enclosed_air_cc": int(m.get("max_enclosed_air_cc") or 0),
                "enclosed_air_total": int(m.get("enclosed_air_total") or 0),
                "floor_cover_mean": round(float(m.get("floor_cover_mean") or 0), 4),
                "floor_interior_cover": round(float(m.get("floor_interior_cover") or 0), 4),
                "interior_room_air": int(m.get("interior_room_air") or 0),
                "roof_score": round(float(m.get("roof_score") or 0), 4),
                "glass_cells": max(int(win.get("glass_cells", 0)), glass_by_name),
                "scaffold_floor_ys": sc.get("floor_ys"),
                "scaffold_roof_mode": sc.get("roof_mode"),
                "scaffold_floor_mode": sc.get("floor_mode"),
                "load_path": sc.get("load_path"),
                "role_names": mats.get("role_names") or {},
                "preview": str(prev.relative_to(out)).replace("\\", "/"),
            }
            if style in before:
                b = before[style]
                row["before"] = {
                    "non_air": b["non_air"],
                    "max_enclosed_air_cc": b["max_enclosed_air_cc"],
                    "floor_cover_mean": round(b["floor_cover_mean"], 4),
                    "floor_interior_cover": round(b.get("floor_interior_cover") or 0, 4),
                    "interior_room_air": int(b.get("interior_room_air") or 0),
                    "hollow_score": round(b["hollow_score"], 4),
                    "structure_ok": b["structure_ok"],
                }
                row["delta_non_air"] = row["non_air"] - b["non_air"]
                row["delta_room_air"] = row["interior_room_air"] - int(b.get("interior_room_air") or 0)
                row["delta_interior_cover"] = round(
                    row["floor_interior_cover"] - float(b.get("floor_interior_cover") or 0), 4
                )
            rows.append(row)
            print(
                "OK",
                style,
                "solids",
                row["non_air"],
                "room",
                row["interior_room_air"],
                "icov",
                row["floor_interior_cover"],
                "roof",
                row["roof_score"],
                "ok",
                ok,
                "roles",
                row["role_names"],
            )

    schem_dir = resolve_schematics_dir()
    schem_dir.mkdir(parents=True, exist_ok=True)
    early_before = {
        p.name: p.stat().st_size
        for p in schem_dir.glob("*.litematic")
        if any(p.name.startswith(pref) for pref in EARLY_TECH_PREFIXES)
    }
    exported = []
    for row in rows:
        style = row["style"]
        cn = CN_MAP[style]
        src = out / "npz" / (row["stem"] + ".npz")
        with np.load(src) as data:
            key = "voxels" if "voxels" in data.files else data.files[0]
            voxels = np.asarray(data[key])
        info = export_voxels_to_companion(
            voxels,
            palette,
            name=cn,
            author="mc-architecture-ai",
            out_dir=schem_dir,
            verify=True,
            target_version="26.3",
        )
        path = Path(info["path"])
        from src.app.materials_bom import write_export_sidecars

        write_export_sidecars(
            voxels,
            palette,
            path,
            with_bom=True,
            with_layers=False,
            source=str(src),
            extra={"target_version": info.get("target_version"), "style_batch": out.name},
        )
        exported.append({"cn": cn, "path": str(path), "non_air": info.get("non_air")})
        print("EXPORT", cn, "->", path.name)

    early_after = {
        p.name: p.stat().st_size
        for p in schem_dir.glob("*.litematic")
        if any(p.name.startswith(pref) for pref in EARLY_TECH_PREFIXES)
    }
    early_ok = early_before == early_after

    lines = [
        "# block_struct batch (block roles + no cross beams + load path)",
        "",
        "- out: `%s`" % str(out).replace("\\", "/"),
        "- baseline: `%s`" % (str(baseline_dir).replace("\\", "/") if baseline_dir else "none"),
        "- structure_ok: **%d/%d**" % (sum(1 for r in rows if r["structure_ok"]), len(rows)),
        "- early-tech untouched: **%s**" % early_ok,
        "",
        "## Focus vs shell_hollow (euro / industrial / rustic)",
        "",
        "| style | solids before→after | room_air before→after | interior_cover before→after | ok |",
        "|---|---|---|---|---|",
    ]
    for style in FOCUS:
        row = next((r for r in rows if r["style"] == style), None)
        if not row:
            continue
        b = row.get("before") or {}
        lines.append(
            "| %s | %s→**%s** | %s→**%s** | %s→**%s** | %s |"
            % (
                style,
                b.get("non_air", "?"),
                row["non_air"],
                b.get("interior_room_air", "?"),
                row["interior_room_air"],
                b.get("floor_interior_cover", "?"),
                row["floor_interior_cover"],
                row["structure_ok"],
            )
        )
    lines.extend(
        [
            "",
            "## All styles",
            "",
            "| style | ok | solids | room_air | int_cover | roof | load | wall/floor/roof |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        rn = row.get("role_names") or {}
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s/%s/%s |"
            % (
                row["style"],
                row["structure_ok"],
                row["non_air"],
                row["interior_room_air"],
                row["floor_interior_cover"],
                row["roof_score"],
                row.get("load_path"),
                rn.get("wall", "?"),
                rn.get("floor", "?"),
                rn.get("roof", "?"),
            )
        )
    lines.extend(["", "## Schematics", ""])
    for e in exported:
        lines.append("- `%s`" % e["cn"])
    lines.extend(
        [
            "",
            "## Notes",
            "- Ring floors **without** X-cross; corner load posts; style role palettes.",
            "- Preview: browse sample dir + Y-slice slider to inspect interior.",
            "",
        ]
    )
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    report = {
        "out_dir": str(out),
        "baseline": str(baseline_dir) if baseline_dir else None,
        "rows": rows,
        "exported": exported,
        "early_tech_untouched": early_ok,
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "outputs" / "design" / "_latest_block_struct.txt").write_text(out.name, encoding="utf-8")
    print("DONE", out)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
