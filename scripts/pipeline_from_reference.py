# -*- coding: utf-8 -*-
"""One-command pipeline: Phase1 analyze → Phase3 similar → Phase4 redstone templates.

Example:
  .venv\\Scripts\\python.exe scripts\\pipeline_from_reference.py data\\raw\\mcblock\\鸡舍_二__6b7d9b9d.litematic
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.schematic_analyze import analyze_litematic, report_to_markdown
from src.app.reference_features import (
    extract_reference_features,
    generate_similar_from_feature,
    load_feature,
)
from src.app.redstone_templates import (
    bootstrap_templates,
    replicate_redstone_from_litematic,
)


def _stem_id(path: Path) -> str:
    return path.stem


def run_pipeline(
    litematic: Path,
    *,
    out_dir: Path,
    num: int = 3,
    seed: int | None = 7,
    temperature: float = 1.0,
    skip_similar: bool = False,
    skip_redstone: bool = False,
    skip_analyze: bool = False,
    skeleton_strength: float = 0.45,
    no_skeleton: bool = False,
    no_material_remap: bool = False,
    structure_mode: str = "repair",
    max_templates: int = 8,
    checkpoint: str | None = None,
) -> dict:
    root = ROOT
    if not litematic.is_absolute():
        litematic = root / litematic
    if not litematic.exists():
        raise FileNotFoundError(litematic)

    stem = _stem_id(litematic)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    analyze_dir = out_dir / "01_analyze"
    feature_dir = out_dir / "02_features"
    similar_dir = out_dir / "03_similar"
    redstone_dir = out_dir / "04_redstone_templates"
    analyze_dir.mkdir(exist_ok=True)
    feature_dir.mkdir(exist_ok=True)

    started = datetime.now().astimezone().isoformat(timespec="seconds")
    steps: list[dict] = []
    result: dict = {
        "reference": str(litematic.relative_to(root)) if str(litematic).startswith(str(root)) else str(litematic),
        "stem": stem,
        "out_dir": str(out_dir.relative_to(root)),
        "started_at": started,
        "steps": steps,
        "ok": True,
        "errors": [],
    }

    # ----- Phase 1 -----
    analyze = None
    if not skip_analyze:
        try:
            analyze = analyze_litematic(litematic)
            md_path = analyze_dir / f"{stem}_report.md"
            js_path = analyze_dir / f"{stem}_report.json"
            md_path.write_text(report_to_markdown(analyze), encoding="utf-8")
            js_path.write_text(json.dumps(analyze, ensure_ascii=False, indent=2), encoding="utf-8")
            steps.append(
                {
                    "phase": 1,
                    "name": "analyze",
                    "ok": True,
                    "markdown": str(md_path.relative_to(root)),
                    "json": str(js_path.relative_to(root)),
                    "redstone_patterns": [
                        p.get("id")
                        for p in ((analyze.get("redstone") or {}).get("common_patterns") or {}).get("patterns")
                        or []
                    ],
                }
            )
        except Exception as ex:
            result["ok"] = False
            result["errors"].append({"phase": 1, "error": str(ex), "trace": traceback.format_exc()})
            steps.append({"phase": 1, "name": "analyze", "ok": False, "error": str(ex)})
            _write_manifest(out_dir, result)
            return result
    else:
        steps.append({"phase": 1, "name": "analyze", "ok": True, "skipped": True})

    # ----- Phase 3 ingest -----
    feature = None
    try:
        feature = extract_reference_features(
            litematic,
            skeleton_size=32,
            index_dir=feature_dir,
            write=True,
        )
        # also mirror into global index for reuse
        try:
            extract_reference_features(
                litematic,
                skeleton_size=32,
                index_dir=root / "data" / "feature_index",
                write=True,
            )
        except Exception:
            pass
        steps.append(
            {
                "phase": 3,
                "name": "ingest",
                "ok": True,
                "feature_id": feature.get("id"),
                "mapped_style": (feature.get("style") or {}).get("mapped_style"),
                "mapped_terrain": (feature.get("style") or {}).get("mapped_terrain"),
                "feature_json": (feature.get("_paths") or {}).get("feature_json"),
            }
        )
    except Exception as ex:
        result["ok"] = False
        result["errors"].append({"phase": 3, "step": "ingest", "error": str(ex)})
        steps.append({"phase": 3, "name": "ingest", "ok": False, "error": str(ex)})
        _write_manifest(out_dir, result)
        return result

    # ----- Phase 3 similar -----
    if not skip_similar:
        try:
            similar_dir.mkdir(exist_ok=True)
            variants = generate_similar_from_feature(
                feature,
                num=int(num),
                temperature=float(temperature),
                checkpoint=checkpoint,
                out_dir=similar_dir,
                seed=seed,
                structure_constrain=True,
                structure_mode=structure_mode,
                use_skeleton=not no_skeleton,
                skeleton_strength=float(skeleton_strength),
                material_remap=not no_material_remap,
            )
            steps.append(
                {
                    "phase": 3,
                    "name": "similar",
                    "ok": True,
                    "num": len(variants),
                    "out_dir": str(similar_dir.relative_to(root)),
                    "files": [Path(v["npz_path"]).name for v in variants],
                    "style": feature["style"].get("mapped_style"),
                    "terrain": feature["style"].get("mapped_terrain"),
                }
            )
        except Exception as ex:
            result["ok"] = False
            result["errors"].append({"phase": 3, "step": "similar", "error": str(ex), "trace": traceback.format_exc()})
            steps.append({"phase": 3, "name": "similar", "ok": False, "error": str(ex)})
    else:
        steps.append({"phase": 3, "name": "similar", "ok": True, "skipped": True})

    # ----- Phase 4 redstone -----
    if not skip_redstone:
        try:
            bootstrap_templates()
            redstone_dir.mkdir(exist_ok=True)
            rs = replicate_redstone_from_litematic(
                litematic,
                out_dir=redstone_dir,
                max_templates=int(max_templates),
            )
            steps.append(
                {
                    "phase": 4,
                    "name": "redstone_templates",
                    "ok": True,
                    "litematic": rs.get("litematic"),
                    "report": rs.get("report"),
                    "matches": [
                        {"pattern": m.get("pattern_id"), "template": m.get("template_id")}
                        for m in (rs.get("matches") or [])
                    ],
                }
            )
        except Exception as ex:
            result["ok"] = False
            result["errors"].append({"phase": 4, "error": str(ex), "trace": traceback.format_exc()})
            steps.append({"phase": 4, "name": "redstone_templates", "ok": False, "error": str(ex)})
    else:
        steps.append({"phase": 4, "name": "redstone_templates", "ok": True, "skipped": True})

    result["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _write_manifest(out_dir, result)
    return result


def _write_manifest(out_dir: Path, result: dict) -> None:
    root = ROOT
    out_dir = Path(out_dir)
    (out_dir / "pipeline_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# 参考流水线报告（Phase1 → 3 → 4）",
        "",
        f"- **参考**: `{result.get('reference')}`",
        f"- **输出目录**: `{result.get('out_dir')}`",
        f"- **开始**: {result.get('started_at')}",
        f"- **结束**: {result.get('finished_at', '（未完成）')}",
        f"- **总成功**: {'是' if result.get('ok') else '否（见错误）'}",
        "",
        "## 步骤",
        "",
    ]
    for s in result.get("steps") or []:
        status = "跳过" if s.get("skipped") else ("OK" if s.get("ok") else "失败")
        lines.append(f"### Phase {s.get('phase')}: {s.get('name')} — **{status}**")
        lines.append("")
        if s.get("error"):
            lines.append(f"- 错误: `{s['error']}`")
        if s.get("markdown"):
            lines.append(f"- 分析报告: `{s['markdown']}`")
        if s.get("redstone_patterns") is not None:
            lines.append(f"- D9 模式: `{s.get('redstone_patterns')}`")
        if s.get("feature_id"):
            lines.append(
                f"- 特征 id: `{s['feature_id']}` → style/terrain "
                f"`{s.get('mapped_style')}` / `{s.get('mapped_terrain')}`"
            )
        if s.get("files"):
            lines.append(f"- 相似变体: {', '.join('`'+f+'`' for f in s['files'])}")
        if s.get("matches") is not None:
            if s["matches"]:
                for m in s["matches"]:
                    lines.append(f"- 模板: `{m.get('pattern')}` → `{m.get('template')}`")
            else:
                lines.append("- （无红石模板匹配）")
        if s.get("litematic"):
            lines.append(f"- 红石模板 schematic: `{s['litematic']}`")
        if s.get("report"):
            lines.append(f"- 红石复刻说明: `{s['report']}`")
        lines.append("")
    if result.get("errors"):
        lines += ["## 错误", ""]
        for e in result["errors"]:
            lines.append(f"- Phase {e.get('phase')}: {e.get('error')}")
        lines.append("")
    lines += [
        "## 局限",
        "",
        "- 相似变体 ≠ 复制参考；红石为原理模板条带，需游戏内微调",
        "- 不重训 VAE；保持 32³；无 Apex/UI 改动",
        "",
    ]
    (out_dir / "pipeline_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="一键流水线：分析 → 相似生成 → 红石模板复刻"
    )
    ap.add_argument("litematic", help="参考 .litematic 路径")
    ap.add_argument(
        "--out-dir",
        default=None,
        help="输出根目录（默认 outputs/pipeline/<stem>）",
    )
    ap.add_argument("--num", type=int, default=3, help="相似变体数量")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--checkpoint", default=None, help="条件 VAE 权重（默认 cond_last.pt）")
    ap.add_argument("--skip-analyze", action="store_true")
    ap.add_argument("--skip-similar", action="store_true")
    ap.add_argument("--skip-redstone", action="store_true")
    ap.add_argument("--skeleton-strength", type=float, default=0.45)
    ap.add_argument("--no-skeleton", action="store_true")
    ap.add_argument("--no-material-remap", action="store_true")
    ap.add_argument(
        "--structure-mode",
        default="repair",
        choices=("repair", "reject", "reject_then_repair"),
    )
    ap.add_argument("--max-templates", type=int, default=8)
    args = ap.parse_args()

    lit = Path(args.litematic)
    stem = lit.stem
    out_dir = Path(args.out_dir) if args.out_dir else Path("outputs/pipeline") / stem

    print("pipeline start:", lit)
    print("out_dir:", out_dir)
    result = run_pipeline(
        lit,
        out_dir=out_dir,
        num=args.num,
        seed=args.seed,
        temperature=args.temperature,
        skip_similar=args.skip_similar,
        skip_redstone=args.skip_redstone,
        skip_analyze=args.skip_analyze,
        skeleton_strength=args.skeleton_strength,
        no_skeleton=args.no_skeleton,
        no_material_remap=args.no_material_remap,
        structure_mode=args.structure_mode,
        max_templates=args.max_templates,
        checkpoint=args.checkpoint,
    )
    print("pipeline ok=", result.get("ok"))
    for s in result.get("steps") or []:
        flag = "SKIP" if s.get("skipped") else ("OK" if s.get("ok") else "FAIL")
        print(f"  [{flag}] phase{s.get('phase')} {s.get('name')}", end="")
        if s.get("error"):
            print(" ::", s["error"])
        else:
            print()
    print("manifest:", out_dir / "pipeline_manifest.json")
    print("report:", out_dir / "pipeline_report.md")
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()