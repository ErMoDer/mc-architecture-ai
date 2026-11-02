# -*- coding: utf-8 -*-
"""A/B: look_harden strong keep-windows vs + facade (door/roof/eaves/banding/pillars)."""
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
    _glass_ids_from_palette,
    _short,
)
from src.app.sample_runner import generate_samples
from src.app.structure_constraints import (
    check_structure,
    summarize_metrics_list,
    StructureReport,
    _footprint,
)
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


def count_doors(vox, palette):
    n = 0
    for bid, name in palette.items():
        s = _short(name)
        if s.endswith("_door") and "trapdoor" not in s:
            n += int((vox == int(bid)).sum())
    return n


def shell_metrics(vox, palette, floor_ys=None):
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
    m["glass_cells_peri"] = win.get("glass_cells", 0)
    gids = _glass_ids_from_palette(palette)
    m["glass_total"] = int(sum(int((vox == g).sum()) for g in gids)) if gids else 0
    m["door_blocks"] = count_doors(vox, palette)
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


def save_npz(vox, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dest, voxels=np.asarray(vox, dtype=np.int16))


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = ROOT / "outputs" / "design" / ("look_harden_facade_%s" % ts)
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

        before_dir = out_root / ("%s_before" % key)  # keep_windows, no facade
        after_dir = out_root / ("%s_after" % key)  # keep_windows + facade
        before_dir.mkdir(exist_ok=True)
        after_dir.mkdir(exist_ok=True)

        before_shell, after_shell = [], []
        before_reports, after_reports = [], []
        before_uniques, after_uniques = [], []
        before_tops, after_tops = [], []

        for i, meta in enumerate(results):
            vox = np.asarray(meta["voxels"], dtype=np.int16)

            vb, rb = look_harden(
                vox,
                palette,
                style=style,
                geometry_mode="strong",
                preserve_windows=True,
                facade_detail=False,
            )
            va, ra = look_harden(
                vox,
                palette,
                style=style,
                geometry_mode="strong",
                preserve_windows=True,
                facade_detail=True,
            )

            save_npz(vb, before_dir / ("sample_%03d.npz" % i))
            save_npz(va, after_dir / ("sample_%03d.npz" % i))

            fys_b = (rb.palette_stats.get("shell_floors") or {}).get("floor_ys")
            fys_a = (ra.palette_stats.get("shell_floors") or {}).get("floor_ys")
            mb, _ = shell_metrics(vb, palette, floor_ys=fys_b)
            ma, _ = shell_metrics(va, palette, floor_ys=fys_a)

            # pull facade stats from report
            sf_a = ra.palette_stats.get("shell_floors") or {}
            ma["door_cells_rep"] = int(sf_a.get("door_cells", 0))
            ma["eave_cells"] = int(sf_a.get("eave_cells", 0))
            ma["banding_cells"] = int(sf_a.get("banding_cells", 0))
            ma["pillar_cells"] = int(sf_a.get("pillar_cells", 0))
            ma["roof_mode"] = str(sf_a.get("roof_mode") or "")
            mb["door_cells_rep"] = 0
            mb["eave_cells"] = 0
            mb["banding_cells"] = 0
            mb["pillar_cells"] = 0
            mb["roof_mode"] = ""

            before_shell.append(mb)
            after_shell.append(ma)
            before_reports.append(StructureReport(ok=rb.ok, metrics=mb, reasons=[]))
            after_reports.append(StructureReport(ok=ra.ok, metrics=ma, reasons=[]))
            before_uniques.append(rb.uniqu_after)
            after_uniques.append(ra.uniqu_after)
            before_tops.append(top_blocks(vb, palette))
            after_tops.append(top_blocks(va, palette))

            export_voxels_to_companion(
                vb, palette, name="%s_before_%03d" % (key, i), out_dir=lite_dir
            )
            export_voxels_to_companion(
                va, palette, name="%s_after_%03d" % (key, i), out_dir=lite_dir
            )

            notes_rows.append(
                {
                    "case": key,
                    "i": i,
                    "before_glass_total": mb["glass_total"],
                    "after_glass_total": ma["glass_total"],
                    "before_door_blocks": mb["door_blocks"],
                    "after_door_blocks": ma["door_blocks"],
                    "after_door_cells_rep": ma["door_cells_rep"],
                    "after_eave": ma["eave_cells"],
                    "after_band": ma["banding_cells"],
                    "after_pillar": ma["pillar_cells"],
                    "after_roof": ma["roof_mode"],
                    "before_flat": mb["floor_flatness"],
                    "after_flat": ma["floor_flatness"],
                    "before_hollow": mb.get("hollow_score"),
                    "after_hollow": ma.get("hollow_score"),
                    "before_unique": rb.uniqu_after,
                    "after_unique": ra.uniqu_after,
                    "before_actions": rb.actions,
                    "after_actions": ra.actions,
                }
            )

        def pack(reports, uniques, tops, shells):
            s = summarize_metrics_list(reports)
            s["avg_unique"] = float(sum(uniques) / max(1, len(uniques)))
            s["top_blocks"] = tops
            s["avg_wall_holes"] = float(
                sum(x["wall_hole_count"] for x in shells) / max(1, len(shells))
            )
            s["avg_floor_flatness"] = float(
                sum(x["floor_flatness"] for x in shells) / max(1, len(shells))
            )
            s["avg_glass_total"] = float(
                sum(x["glass_total"] for x in shells) / max(1, len(shells))
            )
            s["avg_door_blocks"] = float(
                sum(x["door_blocks"] for x in shells) / max(1, len(shells))
            )
            s["avg_eave"] = float(
                sum(x.get("eave_cells", 0) for x in shells) / max(1, len(shells))
            )
            s["avg_band"] = float(
                sum(x.get("banding_cells", 0) for x in shells) / max(1, len(shells))
            )
            s["avg_pillar"] = float(
                sum(x.get("pillar_cells", 0) for x in shells) / max(1, len(shells))
            )
            roofs = [x.get("roof_mode") or "" for x in shells]
            s["roof_modes"] = roofs
            return s

        compare[key] = {
            "before_no_facade": pack(
                before_reports, before_uniques, before_tops, before_shell
            ),
            "after_facade": pack(
                after_reports, after_uniques, after_tops, after_shell
            ),
            "seed": seed,
        }

    (out_root / "compare.json").write_text(
        json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_root / "per_sample.json").write_text(
        json.dumps(notes_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = []
    lines.append("# Look Harden 立面加强（门洞 / 屋顶 / 檐口 / 节奏）A/B")
    lines.append("")
    lines.append("- 时间（Asia/Shanghai）：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("- 目录：`%s`" % out_root)
    lines.append("- 原则：**不重训、仍 32³**；默认 strong + **preserve_windows=True**；本轮默认再开 **facade_detail=True**")
    lines.append("")
    lines.append("## 改动")
    lines.append("")
    lines.append("| 项 | 说明 |")
    lines.append("|----|------|")
    lines.append("| 门洞 | 最长立面中部 1–2 宽 × 2 高；palette 有门则放门方块 |")
    lines.append("| 屋顶 | industrial/modern/scifi/desert → 平顶；medieval 等 → 简易双坡 |")
    lines.append("| 檐口 | 屋顶/屋檐高度向外 1 格挑檐 |")
    lines.append("| 立面节奏 | 各楼层周界束带 + 四角柱 |")
    lines.append("| 保留 | 材质 top-K、preserve_windows / 玻璃窗口 |")
    lines.append("| 关闭 | `facade_detail=False`（A/B before） |")
    lines.append("")
    lines.append("## 指标")
    lines.append("")
    for key, block in compare.items():
        b, a = block["before_no_facade"], block["after_facade"]
        lines.append("### %s（seed=%s）" % (key, block["seed"]))
        lines.append("")
        lines.append("| | before(无立面) | **after(立面)** |")
        lines.append("|--|--|--|")
        lines.append("| glass_total | %.1f | **%.1f** |" % (b["avg_glass_total"], a["avg_glass_total"]))
        lines.append("| door_blocks | %.1f | **%.1f** |" % (b["avg_door_blocks"], a["avg_door_blocks"]))
        lines.append("| eave_cells | %.1f | **%.1f** |" % (b["avg_eave"], a["avg_eave"]))
        lines.append("| banding | %.1f | **%.1f** |" % (b["avg_band"], a["avg_band"]))
        lines.append("| pillars | %.1f | **%.1f** |" % (b["avg_pillar"], a["avg_pillar"]))
        lines.append("| roof_modes | %s | **%s** |" % (b["roof_modes"], a["roof_modes"]))
        lines.append("| floor_flatness | %.3f | %.3f |" % (b["avg_floor_flatness"], a["avg_floor_flatness"]))
        lines.append("| hollow | %.3f | %.3f |" % (b["avg"]["hollow_score"], a["avg"]["hollow_score"]))
        lines.append("| unique | %.1f | %.1f |" % (b["avg_unique"], a["avg_unique"]))
        lines.append("| pass_rate | %.2f | %.2f |" % (b["pass_rate"], a["pass_rate"]))
        lines.append("")
    lines.append("投影：`%s`" % lite_dir)
    lines.append("")
    lines.append("## 限制")
    lines.append("")
    lines.append("- 门洞/坡顶/檐口是启发式，不是可玩红石或原版门实体逻辑")
    lines.append("- 挑檐会外扩 footprint，周界 window 统计可能偏低；请看 glass_total")
    lines.append("- 坡顶可能影响顶层附近碎窗；材质仍靠 top-K，未重训 VAE")
    lines.append("- 未升 64³")
    lines.append("")

    (out_root / "LOOK_HARDEN_FACADE.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    # docs pointer
    docs = ROOT / "docs" / "look_harden.md"
    docs.write_text(
        "\n".join(
            [
                "# Look Harden（观感后处理）",
                "",
                "采样后、结构约束之后收紧壳/楼层/材质；**不重训、仍 32³**。",
                "",
                "- 实现：`src/app/look_harden.py`",
                "- 结构约束：`docs/structure_constraints.md`",
                "- 材质 A/B：`outputs/design/look_harden_20261018_211701/LOOK_HARDEN.md`",
                "- 壳+楼层加强 A/B：`outputs/design/look_harden_shell_floors_*/LOOK_HARDEN_SHELL_FLOORS.md`",
                "- 保留窗洞 A/B：`outputs/design/look_harden_keep_windows_*/LOOK_HARDEN_KEEP_WINDOWS.md`",
                "- **立面（门/屋顶/檐口/节奏）A/B**：最新一次 `outputs/design/look_harden_facade_*/LOOK_HARDEN_FACADE.md`",
                "- CLI：`--structure-constrain` 默认开观感；`--no-look-harden` 可关",
                "- 几何：默认 `geometry_mode=\"strong\"`",
                "- **窗洞**：默认 `preserve_windows=True`；全填墙：`preserve_windows=False`",
                "- **立面**：默认 `facade_detail=True`（门洞、平顶/坡顶、檐口、束带、角柱）；关闭：`facade_detail=False`",
                "- `sample_runner.generate_samples(..., preserve_windows=True, place_window_glass=True)`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("OUT", out_root)
    print(
        json.dumps(
            {
                k: {
                    "before_glass": v["before_no_facade"]["avg_glass_total"],
                    "after_glass": v["after_facade"]["avg_glass_total"],
                    "before_door": v["before_no_facade"]["avg_door_blocks"],
                    "after_door": v["after_facade"]["avg_door_blocks"],
                    "after_eave": v["after_facade"]["avg_eave"],
                    "after_band": v["after_facade"]["avg_band"],
                    "after_pillar": v["after_facade"]["avg_pillar"],
                    "roofs": v["after_facade"]["roof_modes"],
                    "before_flat": v["before_no_facade"]["avg_floor_flatness"],
                    "after_flat": v["after_facade"]["avg_floor_flatness"],
                }
                for k, v in compare.items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
