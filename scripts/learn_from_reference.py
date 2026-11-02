# -*- coding: utf-8 -*-
"""Phase 3 CLI: 从参考 .litematic 提取特征索引，并生成相似变体（非复制）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.reference_features import (
    INDEX_DIR_DEFAULT,
    extract_reference_features,
    generate_similar_from_feature,
    list_index,
    load_feature,
)


def cmd_ingest(args: argparse.Namespace) -> None:
    feat = extract_reference_features(
        args.litematic,
        skeleton_size=int(args.skeleton_size),
        index_dir=args.index_dir,
        write=True,
        embed_block2vec=not args.no_block2vec,
    )
    print("ingested id=", feat["id"])
    print("  style/terrain=", feat["style"].get("mapped_style"), "/", feat["style"].get("mapped_terrain"))
    print("  hollow=", (feat.get("massing") or {}).get("hollow_score"), "floors=", (feat.get("massing") or {}).get("floor_guess"))
    print("  patterns=", (feat.get("redstone") or {}).get("pattern_ids"))
    print("  skeleton occ=", (feat.get("skeleton") or {}).get("occupancy_frac"))
    print("  json=", feat.get("_paths", {}).get("feature_json"))



def cmd_ingest_batch(args: argparse.Namespace) -> None:
    """Batch-ingest all .litematic under a directory into feature_index."""
    from src.data.litematic import load_litematic

    root_dir = Path(args.dir)
    if not root_dir.is_absolute():
        root_dir = ROOT / root_dir
    files = sorted(root_dir.rglob("*.litematic"))
    if not files:
        raise SystemExit(f"no .litematic under {root_dir}")
    ok = skip = fail = 0
    for src in files:
        if args.max_items is not None and ok >= int(args.max_items):
            break
        try:
            size_txt = ""
            if args.max_edge:
                _v, _p, meta = load_litematic(src)
                sx, sy, sz = meta["size"]
                size_txt = str(meta["size"])
                if max(sx, sy, sz) > int(args.max_edge):
                    skip += 1
                    continue
            feat = extract_reference_features(
                src,
                skeleton_size=int(args.skeleton_size),
                index_dir=args.index_dir,
                write=True,
                embed_block2vec=bool(args.embed_block2vec),
            )
            ok += 1
            print("ok", feat["id"], feat["style"].get("mapped_style"), size_txt)
        except Exception as e:
            fail += 1
            print("FAIL", src.name, e)
    print(f"done ok={ok} skip={skip} fail={fail}")


def cmd_list(args: argparse.Namespace) -> None:
    items = list_index(args.index_dir)
    if not items:
        print("(empty index)")
        return
    for it in items:
        print(
            "%s  style=%s terrain=%s  src=%s"
            % (it.get("id"), it.get("mapped_style"), it.get("mapped_terrain"), it.get("source_path"))
        )


def cmd_similar(args: argparse.Namespace) -> None:
    if args.feature:
        feat = load_feature(args.feature, index_dir=args.index_dir)
    elif args.litematic:
        feat = extract_reference_features(
            args.litematic,
            skeleton_size=int(args.skeleton_size),
            index_dir=args.index_dir,
            write=True,
        )
    else:
        raise SystemExit("需要 --feature <id|json> 或 --litematic <path>")

    out_dir = args.out_dir
    if not out_dir:
        out_dir = str(Path("outputs/similar") / feat["id"])

    results = generate_similar_from_feature(
        feat,
        num=int(args.num),
        temperature=float(args.temperature),
        checkpoint=args.checkpoint,
        out_dir=out_dir,
        seed=args.seed,
        structure_constrain=not args.no_structure,
        structure_mode=args.structure_mode,
        use_skeleton=not args.no_skeleton,
        skeleton_strength=float(args.skeleton_strength),
        material_remap=not args.no_material_remap,
    )
    print("reference=", feat["id"], "style=", feat["style"].get("mapped_style"), "terrain=", feat["style"].get("mapped_terrain"))
    for m in results:
        st = m.get("structure_final") or m.get("structure") or {}
        print(
            "%s non_air=%s struct_ok=%s skel=%s remap=%s"
            % (
                Path(m["npz_path"]).name,
                m.get("non_air"),
                st.get("ok"),
                m.get("skeleton_guidance"),
                (m.get("material_remap") or {}).get("remapped"),
            )
        )
    print("out_dir=", ROOT / out_dir)


def cmd_embed(args: argparse.Namespace) -> None:
    """Compute / refresh Block2Vec embedding for a litematic or feature id."""
    from src.app.block2vec_embed import attach_embedding_to_feature

    if args.litematic:
        feat = extract_reference_features(
            args.litematic,
            skeleton_size=int(args.skeleton_size),
            index_dir=args.index_dir,
            write=True,
            embed_block2vec=True,
        )
        b2v = feat.get("block2vec") or {}
        print("id=", feat["id"], "block2vec_ok=", b2v.get("ok"), "chunks=", b2v.get("n_chunks"), "dim=", b2v.get("dim"))
        for n in (b2v.get("neighbors") or [])[:5]:
            print("  neighbor", round(n["score"], 4), n["id"], n.get("mapped_style"))
        return
    if args.feature:
        feat = load_feature(args.feature, index_dir=args.index_dir)
        src = feat.get("source_path")
        if not src:
            raise SystemExit("feature has no source_path")
        attach_embedding_to_feature(feat, src, index_dir=args.index_dir)
        root = ROOT
        index_dir = Path(args.index_dir)
        if not index_dir.is_absolute():
            index_dir = root / index_dir
        path = index_dir / ("%s.json" % feat["id"])
        path.write_text(json.dumps(feat, ensure_ascii=False, indent=2), encoding="utf-8")
        b2v = feat.get("block2vec") or {}
        print("refreshed", feat["id"], b2v)
        return
    raise SystemExit("need --litematic or --feature")


def cmd_search(args: argparse.Namespace) -> None:
    """Nearest neighbors in feature_index by Block2Vec cosine."""
    from src.app.block2vec_embed import embed_litematic, load_embedding, search_index

    if args.litematic:
        emb = embed_litematic(args.litematic)
        vec = emb["vector"]
        print("query chunks=", emb["n_chunks"], "size=", emb.get("size"))
    elif args.feature:
        feat = load_feature(args.feature, index_dir=args.index_dir)
        root = ROOT
        index_dir = Path(args.index_dir)
        if not index_dir.is_absolute():
            index_dir = root / index_dir
        vec = load_embedding(index_dir, feat["id"])
        if vec is None:
            raise SystemExit("no block2vec embedding for %s; run embed first" % feat["id"])
    else:
        raise SystemExit("need --litematic or --feature")
    hits = search_index(vec, args.index_dir, top_k=int(args.top_k))
    if not hits:
        print("(no embeddings in index yet)")
        return
    for h in hits:
        print("%.4f  %s  style=%s  %s" % (h["score"], h["id"], h.get("mapped_style"), h.get("source_path")))



def main() -> None:
    ap = argparse.ArgumentParser(description="参考 litematic → 特征索引 → 相似变体生成")
    ap.add_argument("--index-dir", default=INDEX_DIR_DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_in = sub.add_parser("ingest", help="分析并写入特征 JSON + 32^3 骨架")
    p_in.add_argument("litematic", help="参考 .litematic 路径")
    p_in.add_argument("--skeleton-size", type=int, default=32)
    p_in.add_argument("--no-block2vec", action="store_true", help="skip Block2Vec embedding")
    p_in.set_defaults(func=cmd_ingest)

    
    p_inb = sub.add_parser("ingest-batch", help="batch ingest dir of .litematic")
    p_inb.add_argument("dir", help="directory with .litematic")
    p_inb.add_argument("--skeleton-size", type=int, default=32)
    p_inb.add_argument("--max-edge", type=int, default=64, help="skip if any edge larger; 0=no limit")
    p_inb.add_argument("--max-items", type=int, default=None)
    p_inb.add_argument("--embed-block2vec", action="store_true", help="also compute Block2Vec (slower)")
    p_inb.set_defaults(func=cmd_ingest_batch)

    p_ls = sub.add_parser("list", help="列出特征索引")
    p_ls.set_defaults(func=cmd_list)

    p_sim = sub.add_parser("similar", help="按参考特征生成相似变体")
    p_sim.add_argument("--litematic", default=None, help="若未 ingest，可直接给参考并自动入库")
    p_sim.add_argument("--feature", default=None, help="特征 id 或 json 路径")
    p_sim.add_argument("--num", type=int, default=3)
    p_sim.add_argument("--temperature", type=float, default=1.0)
    p_sim.add_argument("--checkpoint", default=None)
    p_sim.add_argument("--out-dir", default=None)
    p_sim.add_argument("--seed", type=int, default=None)
    p_sim.add_argument("--skeleton-size", type=int, default=32)
    p_sim.add_argument("--skeleton-strength", type=float, default=0.45)
    p_sim.add_argument("--no-skeleton", action="store_true")
    p_sim.add_argument("--no-material-remap", action="store_true")
    p_sim.add_argument("--no-structure", action="store_true")
    p_sim.add_argument(
        "--structure-mode",
        default="repair",
        choices=("repair", "reject", "reject_then_repair"),
    )
    p_sim.set_defaults(func=cmd_similar)

    p_emb = sub.add_parser("embed", help="compute/refresh TransformerBlock2Vec 144-d embedding")
    p_emb.add_argument("--litematic", default=None)
    p_emb.add_argument("--feature", default=None)
    p_emb.add_argument("--skeleton-size", type=int, default=32)
    p_emb.set_defaults(func=cmd_embed)

    p_se = sub.add_parser("search", help="Block2Vec cosine search over feature_index")
    p_se.add_argument("--litematic", default=None)
    p_se.add_argument("--feature", default=None)
    p_se.add_argument("--top-k", type=int, default=8)
    p_se.set_defaults(func=cmd_search)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()