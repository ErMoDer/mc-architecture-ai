# -*- coding: utf-8 -*-
"""A/B: look_harden strong fill-all vs keep-windows (preserve perimeter openings)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.look_harden import (
    look_harden,
    wall_hole_count,
    floor_flatness_score,
    window_opening_count,
    _perimeter_mask,
)
from src.app.sample_runner import generate_samples
from src.app.structure_constraints import check_structure, summarize_metrics_list, StructureReport, _footprint
from src.data.export_litematic_util import export_voxels_to_companion
from src.utils import load_config, load_palette


def top_blocks(vox, palette, k=5):
    ids, cts = np.unique(vox[vox > 0], return_counts=True)
    order = np.argsort(-cts)
    out = []
    for i in order[:k]:
        bid = int(ids[i])
        name = palette.get(bid, str(bid))
        if ":" in name:
            name = name.split(":", 1)[1]
        out.append([name, int(cts[i])])
    return out


def shell_metrics(vox, floor_ys=None):
    rep = check_structure(vox)
    m = dict(rep.metrics)
    ys = np.where((vox > 0).any(axis=(0, 2)))[0]
    y0 = int(ys.min()) if ys.size else 0
    y1 = int(ys.max()) if ys.size else 0
    m["wall_hole_count"] = wall_hole_count(vox, y0, y1)
    flat = floor_flatness_score(vox, floor_ys=floor_ys)
    m["floor_flatness"] = flat.get("floor_flatness", 0.0)
    m["floor_ys_flat"] = flat.get("floor_ys", [])
    win = window_opening_count(vox, y0, y1, floor_ys=floor_ys)
    m["window_cells"] = win.get("window_cells", 0)
    m["window_components"] = win.get("window_components", 0)
    m["glass_cells"] = win.get("glass_cells", 0)
    # raw perimeter air (any opening, window or not)
    solid = vox > 0
    if solid.any():
        fp, _ = _footprint(solid)
        peri = _perimeter_mask(fp)
        air = 0
        px, pz = np.where(peri)
        for x, z in zip(px.tolist(), pz.tolist()):
            for y in range(y0, y1 + 1):
                if vox[x, y, z] == 0:
                    air += 1
        m["perimeter_air"] = int(air)
    else:
        m["perimeter_air"] = 0
    return m, rep


def punch_demo_windows(vox: np.ndarray, floor_ys: list[int], n: int = 4) -> tuple[np.ndarray, int]:
    """Carve a few clean mid-wall 1x2 / 2x2 openings so A/B is measurable."""
    out = np.asarray(vox, dtype=np.int16).copy()
    solid = out > 0
    if not solid.any():
        return out, 0
    fp, _ = _footprint(solid)
    peri = _perimeter_mask(fp)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    y0, y1 = int(ys.min()), int(ys.max())
    peaks = sorted(int(y) for y in floor_ys if y0 < int(y) < y1) or [y0]
    # candidate mid-story Y bands: floor+2 .. next_floor-2
    bands: list[int] = []
    seq = [y0] + peaks + [y1]
    seq = sorted(set(seq))
    for a, b in zip(seq, seq[1:]):
        for y in range(a + 2, b - 1):
            bands.append(y)
    if not bands:
        bands = [max(y0 + 2, (y0 + y1) // 2)]

    px, pz = np.where(peri)
    peri_cols = list(zip(px.tolist(), pz.tolist()))
    # prefer face centers
    if not peri_cols:
        return out, 0
    xs = [c[0] for c in peri_cols]
    zs = [c[1] for c in peri_cols]
    minx, maxx, minz, maxz = min(xs), max(xs), min(zs), max(zs)
    faces = {
        "x0": [(x, z) for x, z in peri_cols if x == minx],
        "x1": [(x, z) for x, z in peri_cols if x == maxx],
        "z0": [(x, z) for x, z in peri_cols if z == minz],
        "z1": [(x, z) for x, z in peri_cols if z == maxz],
    }
    punched = 0
    face_names = ["x0", "x1", "z0", "z1"]
    for i in range(n):
        face = face_names[i % 4]
        cols = faces.get(face) or peri_cols
        if len(cols) < 3:
            continue
        # pick a mid column (skip corners)
        col = cols[len(cols) // 2 + (i % 3) - 1]
        x, z = col
        y_base = bands[i % len(bands)]
        h = 1 + (i % 2)  # 1 or 2
        w = 1 + ((i // 2) % 2)  # 1 or 2
        # carve along face tangent
        if face in ("x0", "x1"):
            deltas = [(0, dz) for dz in range(-(w // 2), -(w // 2) + w)]
        else:
            deltas = [(dx, 0) for dx in range(-(w // 2), -(w // 2) + w)]
        for dx, dz in deltas:
            cx, cz = x + dx, z + dz
            if not (0 <= cx < out.shape[0] and 0 <= cz < out.shape[2]):
                continue
            if not peri[cx, cz]:
                continue
            for dy in range(h):
                cy = y_base + dy
                if cy <= y0 or cy >= y1:
                    continue
                if cy in peaks:
                    continue
                if out[cx, cy, cz] != 0:
                    out[cx, cy, cz] = 0
                    punched += 1
    return out, punched


def save_npz(vox, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dest, voxels=np.asarray(vox, dtype=np.int16))


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = ROOT / "outputs" / "design" / ("look_harden_keep_windows_%s" % ts)
    out_root.mkdir(parents=True, exist_ok=True)
    lite_dir = out_root / "litematic"
    lite_dir.mkdir(exist_ok=True)

    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])

    cases = [
        ("industrial", "flat", 42),
        ("medieval", "flat", 43),
    ]

    compare = {}
    notes_rows = []

    for style, terrain, seed in cases:
        key = "%s_%s" % (style, terrain)
        base_dir = out_root / ("%s_base" % key)
        results = generate_samples(
            num=3,
            seed=seed,
            style=style,
            terrain=terrain,
            structure_constrain=True,
            structure_mode="repair",
            look_harden_enable=False,
            out_dir=base_dir,
        )

        fill_dir = out_root / ("%s_fill_all" % key)
        keep_dir = out_root / ("%s_keep_windows" % key)
        fill_dir.mkdir(exist_ok=True)
        keep_dir.mkdir(exist_ok=True)

        fill_shell, keep_shell = [], []
        fill_reports, keep_reports = [], []
        fill_uniques, keep_uniques = [], []
        fill_tops, keep_tops = [], []
        base_shell = []

        for i, meta in enumerate(results):
            vox0 = np.asarray(meta["voxels"], dtype=np.int16)
            # estimate floors from structure peaks for demo punches
            m0, _ = shell_metrics(vox0)
            floor_guess = []
            # use structure floor peaks if present
            try:
                from src.app.structure_constraints import _floor_metrics
                floor_guess = list(_floor_metrics(vox0 > 0).get("y_peaks") or [])
            except Exception:
                floor_guess = []
            vox, n_punch = punch_demo_windows(vox0, floor_guess, n=4)
            mb0, _ = shell_metrics(vox)
            mb0["demo_punched"] = n_punch
            base_shell.append(mb0)
            save_npz(vox, base_dir / ("sample_%03d_punched.npz" % i))

            # A: strong fill-all (legacy shell closes everything)
            va, ra = look_harden(
                vox, palette, style=style, geometry_mode="strong", preserve_windows=False
            )
            # B: keep windows (default)
            vb, rb = look_harden(
                vox, palette, style=style, geometry_mode="strong", preserve_windows=True
            )

            save_npz(va, fill_dir / ("sample_%03d.npz" % i))
            save_npz(vb, keep_dir / ("sample_%03d.npz" % i))

            fys_a = (ra.palette_stats.get("shell_floors") or {}).get("floor_ys")
            fys_b = (rb.palette_stats.get("shell_floors") or {}).get("floor_ys")
            ma, _ = shell_metrics(va, floor_ys=fys_a)
            mb, _ = shell_metrics(vb, floor_ys=fys_b)
            fill_shell.append(ma)
            keep_shell.append(mb)
            fill_reports.append(StructureReport(ok=ra.ok, metrics=ma, reasons=[]))
            keep_reports.append(StructureReport(ok=rb.ok, metrics=mb, reasons=[]))
            fill_uniques.append(ra.uniqu_after)
            keep_uniques.append(rb.uniqu_after)
            fill_tops.append(top_blocks(va, palette))
            keep_tops.append(top_blocks(vb, palette))

            export_voxels_to_companion(
                va, palette, name="%s_fill_all_%03d" % (key, i), out_dir=lite_dir
            )
            export_voxels_to_companion(
                vb, palette, name="%s_keep_windows_%03d" % (key, i), out_dir=lite_dir
            )

            notes_rows.append({
                "case": key,
                "i": i,
                "demo_punched": n_punch,
                "base_perimeter_air": mb0["perimeter_air"],
                "base_window_cells": mb0["window_cells"],
                "base_window_comp": mb0["window_components"],
                "fill_perimeter_air": ma["perimeter_air"],
                "keep_perimeter_air": mb["perimeter_air"],
                "fill_window_cells": ma["window_cells"],
                "keep_window_cells": mb["window_cells"],
                "fill_window_comp": ma["window_components"],
                "keep_window_comp": mb["window_components"],
                "fill_glass": ma["glass_cells"],
                "keep_glass": mb["glass_cells"],
                "fill_holes": ma["wall_hole_count"],
                "keep_holes": mb["wall_hole_count"],
                "fill_flat": ma["floor_flatness"],
                "keep_flat": mb["floor_flatness"],
                "fill_hollow": ma.get("hollow_score"),
                "keep_hollow": mb.get("hollow_score"),
                "fill_unique": ra.uniqu_after,
                "keep_unique": rb.uniqu_after,
                "keep_actions": rb.actions,
                "fill_actions": ra.actions,
            })

        def pack(reports, uniques, tops, shells):
            s = summarize_metrics_list(reports)
            s["avg_unique"] = float(sum(uniques) / max(1, len(uniques)))
            s["top_blocks"] = tops
            s["avg_wall_holes"] = float(sum(x["wall_hole_count"] for x in shells) / max(1, len(shells)))
            s["avg_floor_flatness"] = float(sum(x["floor_flatness"] for x in shells) / max(1, len(shells)))
            s["avg_window_cells"] = float(sum(x["window_cells"] for x in shells) / max(1, len(shells)))
            s["avg_window_comp"] = float(sum(x["window_components"] for x in shells) / max(1, len(shells)))
            s["avg_glass"] = float(sum(x["glass_cells"] for x in shells) / max(1, len(shells)))
            s["avg_perimeter_air"] = float(sum(x["perimeter_air"] for x in shells) / max(1, len(shells)))
            return s

        base_pack = {
            "avg_perimeter_air": float(sum(x["perimeter_air"] for x in base_shell) / max(1, len(base_shell))),
            "avg_window_cells": float(sum(x["window_cells"] for x in base_shell) / max(1, len(base_shell))),
            "avg_window_comp": float(sum(x["window_components"] for x in base_shell) / max(1, len(base_shell))),
            "avg_punched": float(sum(x.get("demo_punched", 0) for x in base_shell) / max(1, len(base_shell))),
            "avg_hollow": float(sum(float(x.get("hollow_score", 0)) for x in base_shell) / max(1, len(base_shell))),
            "avg_flat": float(sum(x["floor_flatness"] for x in base_shell) / max(1, len(base_shell))),
        }
        fpack = pack(fill_reports, fill_uniques, fill_tops, fill_shell)
        kpack = pack(keep_reports, keep_uniques, keep_tops, keep_shell)
        compare[key] = {
            "base_punched": base_pack,
            "fill_all": fpack,
            "keep_windows": kpack,
            "seed": seed,
        }

    (out_root / "compare.json").write_text(
        json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_root / "per_sample.json").write_text(
        json.dumps(notes_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = []
    lines.append("# Look Harden：壳加强但保留窗洞 A/B")
    lines.append("")
    lines.append("- 时间（Asia/Shanghai）：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("- 目录：`%s`" % out_root)
    lines.append("- 原则：**不重训、保持 32³**；strong 壳/楼层保留；默认 **preserve_windows=True**")
    lines.append("")
    lines.append("## 改动")
    lines.append("")
    lines.append("| 项 | 说明 |")
    lines.append("|----|------|")
    lines.append("| 窗洞识别 | 周界连通空气块：高 1–2 × 宽 1–3、近似矩形、楼层中段；已有玻璃；多面重复 |")
    lines.append("| 破洞 | 不规则/贴楼板/过大 → 仍用墙填 |")
    lines.append("| 默认 | `preserve_windows=True`；可选 `place_window_glass`（白名单有玻璃则镶玻璃） |")
    lines.append("| 关闭 | `preserve_windows=False` = 旧 strong 全填（A/B 对照） |")
    lines.append("| Demo | 基线先挖 4 个标准窗洞，便于对比 |")
    lines.append("")
    lines.append("## 指标")
    lines.append("")
    for key, block in compare.items():
        base, f, k = block["base_punched"], block["fill_all"], block["keep_windows"]
        lines.append("### %s（seed=%s）" % (key, block["seed"]))
        lines.append("")
        lines.append("| | base(挖窗后) | fill_all | **keep_windows** |")
        lines.append("|--|--|--|--|")
        lines.append("| window_cells 均 | %.1f | %.1f | **%.1f** |" % (base["avg_window_cells"], f["avg_window_cells"], k["avg_window_cells"]))
        lines.append("| window_comp 均 | %.1f | %.1f | **%.1f** |" % (base["avg_window_comp"], f["avg_window_comp"], k["avg_window_comp"]))
        lines.append("| glass_cells 均 | — | %.1f | **%.1f** |" % (f["avg_glass"], k["avg_glass"]))
        lines.append("| perimeter_air 均 | %.1f | %.1f | %.1f |" % (base["avg_perimeter_air"], f["avg_perimeter_air"], k["avg_perimeter_air"]))
        lines.append("| wall_holes 均 | — | %.1f | %.1f |" % (f["avg_wall_holes"], k["avg_wall_holes"]))
        lines.append("| floor_flatness 均 | %.3f | %.3f | %.3f |" % (base["avg_flat"], f["avg_floor_flatness"], k["avg_floor_flatness"]))
        lines.append("| hollow 均 | %.3f | %.3f | %.3f |" % (base["avg_hollow"], f["avg"]["hollow_score"], k["avg"]["hollow_score"]))
        lines.append("| unique 均 | — | %.1f | %.1f |" % (f["avg_unique"], k["avg_unique"]))
        lines.append("| pass_rate | — | %.2f | %.2f |" % (f["pass_rate"], k["pass_rate"]))
        lines.append("")
    lines.append("投影：`%s`" % lite_dir)
    lines.append("")
    lines.append("## 限制")
    lines.append("")
    lines.append("- 窗洞启发式，不是建筑学开窗；斜窗/落地窗/角窗可能误判")
    lines.append("- 镶玻璃依赖 palette/风格白名单里有 glass")
    lines.append("- 未改 VAE / 未升分辨率")
    lines.append("")

    md = "\n".join(lines)
    (out_root / "LOOK_HARDEN_KEEP_WINDOWS.md").write_text(md, encoding="utf-8")

    # refresh docs pointer
    docs = ROOT / "docs" / "look_harden.md"
    docs.write_text(
        "# Look Harden（观感硬化）\n\n"
        "后处理：结构约束之后收紧壳/楼层/材质；**不重训、保持 32³**。\n\n"
        "- 实现：`src/app/look_harden.py`\n"
        "- 结构约束：`docs/structure_constraints.md`\n"
        "- 材质 A/B：`outputs/design/look_harden_20261018_211701/LOOK_HARDEN.md`\n"
        "- 壳+楼层加强 A/B：`outputs/design/look_harden_shell_floors_*/LOOK_HARDEN_SHELL_FLOORS.md`\n"
        "- **保留窗洞 A/B**：见最近一次 `outputs/design/look_harden_keep_windows_*/LOOK_HARDEN_KEEP_WINDOWS.md`\n"
        "- CLI：`--structure-constrain` 默认开观感；`--no-look-harden` 可关\n"
        "- 几何：默认 `geometry_mode=\"strong\"`\n"
        "- **窗洞**：默认 `preserve_windows=True`（只填不规则破洞，保留 1–2×1–3 矩形/玻璃/重复开洞；"
        "可选镶玻璃）。对照全填：`preserve_windows=False`\n",
        encoding="utf-8",
    )
    print("OUT", out_root)
    print(json.dumps({
        k: {
            "base_win": v["base_punched"]["avg_window_cells"],
            "fill_win": v["fill_all"]["avg_window_cells"],
            "keep_win": v["keep_windows"]["avg_window_cells"],
            "fill_glass": v["fill_all"]["avg_glass"],
            "keep_glass": v["keep_windows"]["avg_glass"],
            "fill_air": v["fill_all"]["avg_perimeter_air"],
            "keep_air": v["keep_windows"]["avg_perimeter_air"],
            "fill_flat": v["fill_all"]["avg_floor_flatness"],
            "keep_flat": v["keep_windows"]["avg_floor_flatness"],
        }
        for k, v in compare.items()
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
