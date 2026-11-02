"""从 checkpoint 采样，并导出 .npz + .mcfunction。支持条件与结构约束。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.sample_runner import generate_samples
from src.app.structure_constraints import check_structure, summarize_metrics_list
from src.data.export_mcfunction import export_mcfunction
from src.data.io_vox import save_npz_npz
from src.data.labels import load_vocab, resolve_style_id, resolve_terrain_id
from src.models import ConditionalVoxelVAE, VoxelVAE
from src.utils import load_config, load_palette, resolve_device, set_seed


def main() -> None:
    parser = argparse.ArgumentParser(description="VoxelVAE / ConditionalVoxelVAE 采样")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--num", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--conditional", action="store_true")
    parser.add_argument("--style", default="medieval", help="风格名或 id")
    parser.add_argument("--terrain", default="flat", help="地形名或 id")
    parser.add_argument("--vocab", default="data/label_vocab.json")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument(
        "--structure-constrain",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="启用空心壳/楼层/屋顶启发式约束（默认开启；用 --no-structure-constrain 关闭）",
    )
    parser.add_argument(
        "--structure-mode",
        default="repair",
        choices=("repair", "reject", "reject_then_repair", "check"),
        help="repair=采样后修复; reject=不合格重采; reject_then_repair=先拒再修",
    )
    parser.add_argument(
        "--structure-max-tries",
        type=int,
        default=8,
        help="每样本最多重采次数（reject 类模式）",
    )
    parser.add_argument(
        "--structure-compare",
        action="store_true",
        help="额外采同等数量无约束样本，打印通过率/指标对比",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--strategy",
        default=None,
        choices=("similar_scaffold", "rule_scaffold", "vae_look"),
        help="if set, use gen_strategy instead of raw VAE path",
    )
    parser.add_argument(
        "--vae-fill",
        action="store_true",
        help="with similar_scaffold: sparse VAE materials inside scaffold",
    )
    parser.add_argument(
        "--no-look-harden",
        action="store_true",
        help="关闭材质/壳层观感硬化（默认：开结构约束时启用）",
    )
    parser.add_argument(
        "--look-harden-top-k",
        type=int,
        default=6,
        help="每样本保留的结构材质种数上限",
    )
    args = parser.parse_args()

    cfg = load_config(ROOT / args.config)
    n = args.num or int(cfg["sample"]["num_samples"])
    temp = (
        args.temperature
        if args.temperature is not None
        else float(cfg["sample"]["temperature"])
    )
    out_dir = args.out_dir or cfg["sample"]["out_dir"]
    conditional = bool(args.conditional)
    default_ckpt = (
        "checkpoints/cond_last.pt" if conditional else cfg["sample"]["checkpoint"]
    )
    ckpt = args.checkpoint or default_ckpt

    if getattr(args, "strategy", None):
        from src.app.gen_strategy import generate_with_strategy
        results = generate_with_strategy(
            args.strategy,
            style=args.style,
            terrain=args.terrain,
            num=n,
            temperature=temp,
            checkpoint=ckpt,
            out_dir=out_dir,
            seed=args.seed,
            vae_fill=bool(getattr(args, "vae_fill", False)),
            look_harden_enable=(False if args.no_look_harden else True),
            structure_constrain=args.structure_constrain
            and args.structure_mode != "check",
            structure_mode=args.structure_mode if args.structure_mode != "check" else "repair",
        )
    else:
        results = generate_samples(
        num=n,
        temperature=temp,
        checkpoint=ckpt,
        config_path=args.config,
        out_dir=out_dir,
        seed=args.seed,
        style=args.style if conditional else None,
        terrain=args.terrain if conditional else None,
        vocab_path=args.vocab,
        structure_constrain=args.structure_constrain
        and args.structure_mode != "check",
        structure_mode=args.structure_mode if args.structure_mode != "check" else "repair",
        structure_max_tries=int(args.structure_max_tries),
        look_harden_enable=(False if args.no_look_harden else None),
        look_harden_top_k=int(args.look_harden_top_k),
    )

    # 仅做结构检查、不修复：标注已有结果的检查结论
    if args.structure_mode == "check":
        for meta in results:
            rep = check_structure(meta["voxels"])
            meta["structure"] = rep.to_dict()

    reports = []
    for meta in results:
        stem = Path(meta["npz_path"]).stem
        st = meta.get("structure") or {}
        ok = st.get("ok")
        print(
            "%s: non_air=%s structure_ok=%s repairs=%s"
            % (
                stem,
                meta.get("non_air"),
                ok,
                (st.get("repairs") or [])[:4],
            )
        )
        if st:
            from src.app.structure_constraints import StructureReport

            reports.append(
                StructureReport(
                    ok=bool(st.get("ok")),
                    reasons=list(st.get("reasons") or []),
                    metrics=dict(st.get("metrics") or {}),
                    repairs=list(st.get("repairs") or []),
                )
            )

    if reports:
        summary = summarize_metrics_list(reports)
        print("structure_summary:", json.dumps(summary, ensure_ascii=False))

    if args.structure_compare:
        cmp_dir = str(Path(out_dir) / "_unconstrained_cmp")
        raw = generate_samples(
            num=n,
            temperature=temp,
            checkpoint=ckpt,
            config_path=args.config,
            out_dir=cmp_dir,
            seed=(args.seed + 1) if args.seed is not None else None,
            style=args.style if conditional else None,
            terrain=args.terrain if conditional else None,
            vocab_path=args.vocab,
            structure_constrain=False,
        )
        raw_reps = []
        from src.app.structure_constraints import StructureReport

        for meta in raw:
            pre = meta.get("structure_pre") or meta.get("structure") or {}
            if not pre:
                r = check_structure(meta["voxels"])
                pre = r.to_dict()
            raw_reps.append(
                StructureReport(
                    ok=bool(pre.get("ok")),
                    reasons=list(pre.get("reasons") or []),
                    metrics=dict(pre.get("metrics") or {}),
                    repairs=[],
                )
            )
        print(
            "compare unconstrained:",
            json.dumps(summarize_metrics_list(raw_reps), ensure_ascii=False),
        )
        print(
            "compare constrained:  ",
            json.dumps(summarize_metrics_list(reports), ensure_ascii=False),
        )

    print("已写出到", ROOT / out_dir)


if __name__ == "__main__":
    main()
