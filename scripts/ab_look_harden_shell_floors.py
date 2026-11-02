# -*- coding: utf-8 -*-
"""A/B: look_harden basic (current/legacy shell) vs strong (shell+floors harden)."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.look_harden import look_harden, wall_hole_count, floor_flatness_score
from src.app.sample_runner import generate_samples
from src.app.structure_constraints import check_structure, summarize_metrics_list, StructureReport
from src.data.export_litematic_util import export_voxels_to_companion
from src.utils import load_config, load_palette


def floor_spacing_stats(floor_ys):
    ys = sorted(int(y) for y in (floor_ys or []))
    if len(ys) < 2:
        return {"n_floors": len(ys), "gap_mean": 0.0, "gap_std": 0.0, "regularity": 0.0}
    gaps = [ys[i+1]-ys[i] for i in range(len(ys)-1)]
    mean = float(sum(gaps)/len(gaps))
    var = float(sum((g-mean)**2 for g in gaps)/len(gaps))
    std = var ** 0.5
    # regularity: 1 when all gaps equal
    reg = float(max(0.0, 1.0 - (std / max(mean, 1.0))))
    return {"n_floors": len(ys), "gap_mean": mean, "gap_std": std, "regularity": reg, "gaps": gaps, "ys": ys}

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
    # Prefer explicit floor Ys from look_harden; else peaks with >=0.35 cover only
    flat = floor_flatness_score(vox, floor_ys=floor_ys)
    per = flat.get("per_floor") or {}
    if floor_ys is None and per:
        kept = {k: v for k, v in per.items() if float(v) >= 0.35}
        if kept:
            flat = {
                "floor_flatness": float(sum(kept.values()) / len(kept)),
                "per_floor": kept,
                "floor_ys": [int(k) for k in kept],
            }
    m["floor_flatness"] = flat.get("floor_flatness", 0.0)
    m["floor_ys_flat"] = flat.get("floor_ys", [])
    return m, rep

def save_npz(vox, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(dest, voxels=np.asarray(vox, dtype=np.int16))

def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = ROOT / "outputs" / "design" / ("look_harden_shell_floors_%s" % ts)
    out_root.mkdir(parents=True, exist_ok=True)
    lite_dir = out_root / "litematic"
    lite_dir.mkdir(exist_ok=True)

    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])

    cases = [
        ("industrial", "flat", 42),
        ("medieval", "flat", 43),
    ]
    seeds_extra = [42, 43, 44]  # 3 seeds each style via num=3 with fixed seed

    compare = {}
    notes_rows = []

    for style, terrain, seed in cases:
        key = "%s_%s" % (style, terrain)
        # structure-only samples (no look_harden) — shared base
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

        before_dir = out_root / ("%s_before" % key)
        after_dir = out_root / ("%s_after" % key)
        before_dir.mkdir(exist_ok=True)
        after_dir.mkdir(exist_ok=True)

        before_reports = []
        after_reports = []
        before_uniques = []
        after_uniques = []
        before_tops = []
        after_tops = []
        before_shell = []
        after_shell = []

        base_shell = []
        for i, meta in enumerate(results):
            vox = np.asarray(meta["voxels"], dtype=np.int16)
            mb0, _ = shell_metrics(vox)
            base_shell.append(mb0)
            # before = legacy basic geometry
            vb, rb = look_harden(vox, palette, style=style, geometry_mode="basic")
            # after = strong shell/floors
            va, ra = look_harden(vox, palette, style=style, geometry_mode="strong")

            save_npz(vb, before_dir / ("sample_%03d.npz" % i))
            save_npz(va, after_dir / ("sample_%03d.npz" % i))

            fys_b = (rb.palette_stats.get("shell_floors") or {}).get("floor_ys")
            fys_a = (ra.palette_stats.get("shell_floors") or {}).get("floor_ys")
            mb, _ = shell_metrics(vb, floor_ys=fys_b)
            ma, _ = shell_metrics(va, floor_ys=fys_a)
            before_shell.append(mb)
            after_shell.append(ma)
            before_reports.append(
                StructureReport(ok=rb.ok, metrics=mb, reasons=[])
            )
            after_reports.append(
                StructureReport(ok=ra.ok, metrics=ma, reasons=[])
            )
            before_uniques.append(rb.uniqu_after)
            after_uniques.append(ra.uniqu_after)
            before_tops.append(top_blocks(vb, palette))
            after_tops.append(top_blocks(va, palette))

            # export first sample each side
            export_voxels_to_companion(
                vb, palette,
                name="%s_before_%03d" % (key, i),
                out_dir=lite_dir,
            )
            export_voxels_to_companion(
                va, palette,
                name="%s_after_%03d" % (key, i),
                out_dir=lite_dir,
            )


            sb = floor_spacing_stats(fys_b or mb.get("floor_ys_flat"))
            sa = floor_spacing_stats(fys_a or ma.get("floor_ys_flat"))
            notes_rows.append({
                "case": key, "i": i,
                "base_holes": mb0["wall_hole_count"],
                "base_flat": mb0["floor_flatness"],
                "base_hollow": mb0.get("hollow_score"),
                "before_holes": mb["wall_hole_count"],
                "after_holes": ma["wall_hole_count"],
                "before_flat": mb["floor_flatness"],
                "after_flat": ma["floor_flatness"],
                "before_hollow": mb.get("hollow_score"),
                "after_hollow": ma.get("hollow_score"),
                "before_floors": mb.get("floor_guess"),
                "after_floors": ma.get("floor_guess"),
                "before_floor_reg": sb["regularity"],
                "after_floor_reg": sa["regularity"],
                "before_floor_ys": sb.get("ys"),
                "after_floor_ys": sa.get("ys"),
                "before_unique": rb.uniqu_after,
                "after_unique": ra.uniqu_after,
                "after_actions": ra.actions,
            })

        def pack(reports, uniques, tops, shells):
            s = summarize_metrics_list(reports)
            s["avg_unique"] = float(sum(uniques) / max(1, len(uniques)))
            s["top_blocks"] = tops
            s["avg_wall_holes"] = float(sum(x["wall_hole_count"] for x in shells) / max(1, len(shells)))
            s["avg_floor_flatness"] = float(sum(x["floor_flatness"] for x in shells) / max(1, len(shells)))
            return s

        base_pack = {
            "avg_wall_holes": float(sum(x["wall_hole_count"] for x in base_shell) / max(1, len(base_shell))),
            "avg_floor_flatness": float(sum(x["floor_flatness"] for x in base_shell) / max(1, len(base_shell))),
            "avg_hollow": float(sum(float(x.get("hollow_score", 0)) for x in base_shell) / max(1, len(base_shell))),
            "avg_floor_guess": float(sum(float(x.get("floor_guess", 0)) for x in base_shell) / max(1, len(base_shell))),
        }
        bpack = pack(before_reports, before_uniques, before_tops, before_shell)
        apack = pack(after_reports, after_uniques, after_tops, after_shell)
        # attach floor regularity from notes for this case
        case_notes = [n for n in notes_rows if n["case"] == key]
        bpack["avg_floor_reg"] = float(sum(n["before_floor_reg"] for n in case_notes)/max(1,len(case_notes)))
        apack["avg_floor_reg"] = float(sum(n["after_floor_reg"] for n in case_notes)/max(1,len(case_notes)))
        compare[key] = {
            "base_structure_only": base_pack,
            "before": bpack,
            "after": apack,
            "seed": seed,
        }

    (out_root / "compare.json").write_text(
        json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_root / "per_sample.json").write_text(
        json.dumps(notes_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # LOOK notes markdown
    lines = []
    lines.append("# Look Harden：壳 + 楼层加强 A/B")
    lines.append("")
    lines.append("- 时间（Asia/Shanghai）：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("- 目录：`%s`" % out_root)
    lines.append("- 原则：**不重训、不升 64³**；材质 top-K 不变；只加强壳连续性 / 规则楼板 / 屋顶修补")
    lines.append("")
    lines.append("## 改动")
    lines.append("")
    lines.append("| 项 | 说明 |")
    lines.append("|----|------|")
    lines.append("| 外墙 | 足迹周界实心填充；双 pass 补洞（上下贯通或邻接≥2） |")
    lines.append("| 楼板 | 规则 Y 间距（默认 4）铺满活跃柱；过近楼层合并 |")
    lines.append("| 屋顶 | 封顶 + 单格凹陷修补 + 孤悬檐口修剪 |")
    lines.append("| 材质 | 仍走 top-K / 风格白名单，未放松 |")
    lines.append("| 默认 | `structure_constrain` 时 `look_harden` 仍默认开，几何模式 **strong** |")
    lines.append("| A/B | before = 旧 `basic` 壳楼层；after = 新 `strong` |")
    lines.append("")
    lines.append("## 指标（同 seed、先结构 repair，再分别 basic/strong）")
    lines.append("")
    for key, block in compare.items():
        base, b, a = block["base_structure_only"], block["before"], block["after"]
        lines.append("### %s（seed=%s）" % (key, block["seed"]))
        lines.append("")
        lines.append("| | base(仅结构) | before(basic壳) | after(strong壳+楼) |")
        lines.append("|--|--|--|--|")
        lines.append("| wall_holes 均 | %.0f | %.1f | **%.1f** |" % (base["avg_wall_holes"], b["avg_wall_holes"], a["avg_wall_holes"]))
        lines.append("| floor_flatness 均 | %.3f | %.3f | **%.3f** |" % (base["avg_floor_flatness"], b["avg_floor_flatness"], a["avg_floor_flatness"]))
        lines.append("| hollow 均 | %.3f | %.3f | %.3f |" % (base["avg_hollow"], b["avg"]["hollow_score"], a["avg"]["hollow_score"]))
        lines.append("| floor_guess 均 | %.1f | %.1f | %.1f |" % (base["avg_floor_guess"], b["avg"]["floor_guess"], a["avg"]["floor_guess"]))
        lines.append("| floor_reg 均(间距规则) | — | %.3f | **%.3f** |" % (b.get("avg_floor_reg", 0), a.get("avg_floor_reg", 0)))
        lines.append("| unique 方块均 | — | %.1f | %.1f |" % (b["avg_unique"], a["avg_unique"]))
        lines.append("| pass_rate | — | %.2f | %.2f |" % (b["pass_rate"], a["pass_rate"]))
        lines.append("")
    lines.append("投影：`%s`" % (lite_dir))
    lines.append("")
    lines.append("## 限制")
    lines.append("")
    lines.append("- 仍是启发式外壳，不是可玩刷怪塔/真实建筑学")
    lines.append("- 规则楼板可能偏「层层蛋糕」；复杂坡屋顶会被压平")
    lines.append("- 壳洞按足迹周界统计，开窗洞也会被填实")
    lines.append("- 未改 VAE / 未升分辨率")
    lines.append("")
    md = "\n".join(lines)
    (out_root / "LOOK_HARDEN_SHELL_FLOORS.md").write_text(md, encoding="utf-8")
    # also refresh docs/look_harden.md pointer
    docs = ROOT / "docs" / "look_harden.md"
    docs.write_text(
        "# Look Harden（观感硬化）\n\n"
        "后处理模块：在结构约束之后收紧壳/楼层/材质；**不重训、不升 32³**。\n\n"
        "- 实现：`src/app/look_harden.py`\n"
        "- 结构约束文档：`docs/structure_constraints.md`（文末 Look harden 节）\n"
        "- 材质 A/B：`outputs/design/look_harden_20261018_211701/LOOK_HARDEN.md`\n"
        "- **壳+楼层加强 A/B**：见最近一次 `outputs/design/look_harden_shell_floors_*/LOOK_HARDEN_SHELL_FLOORS.md`\n"
        "- CLI：生成带 `--structure-constrain` 时默认开观感；`--no-look-harden` 可关\n"
        "- 几何模式：默认 `strong`（壳连续性/规则楼板/屋顶修补）；A/B 可用 `geometry_mode=\"basic\"` 对照旧行为\n",
        encoding="utf-8",
    )
    print("OUT", out_root)
    print(json.dumps({k: {
        "base_holes": v["base_structure_only"]["avg_wall_holes"],
        "before_holes": v["before"]["avg_wall_holes"],
        "after_holes": v["after"]["avg_wall_holes"],
        "base_flat": v["base_structure_only"]["avg_floor_flatness"],
        "before_flat": v["before"]["avg_floor_flatness"],
        "after_flat": v["after"]["avg_floor_flatness"],
        "before_hollow": v["before"]["avg"]["hollow_score"],
        "after_hollow": v["after"]["avg"]["hollow_score"],
    } for k, v in compare.items()}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
