# -*- coding: utf-8 -*-
"""Smoke: similar_scaffold retrieval with vs without Block2Vec blend."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _brief(feat: dict) -> dict:
    src = (feat.get("source_path") or "").replace("\\", "/")
    return {
        "id": feat.get("id"),
        "mapped_style": feat.get("mapped_style"),
        "source_path": src,
        "score": round(float(feat.get("_retrieve_score") or 0), 4),
        "base": round(float(feat.get("_retrieve_base") or feat.get("_retrieve_score") or 0), 4),
        "b2v_sim": None if feat.get("_b2v_sim") is None else round(float(feat["_b2v_sim"]), 4),
        "is_mcblock": "mcblock" in src.lower(),
        "is_hack337": "hack337" in src.lower() or "challenge" in src.lower(),
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--styles", default="european,medieval,modern,chinese")
    ap.add_argument("--top-k", type=int, default=3)
    args = ap.parse_args()

    from src.app.gen_strategy import retrieve_style_refs

    out = Path(args.out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)

    styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    report = {
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "top_k": args.top_k,
        "styles": {},
    }
    all_mc_ok = True
    for style in styles:
        without = retrieve_style_refs(style, "flat", top_k=args.top_k, use_block2vec=False)
        with_b2v = retrieve_style_refs(style, "flat", top_k=args.top_k, use_block2vec=True)
        w_briefs = [_brief(f) for f in without]
        b_briefs = [_brief(f) for f in with_b2v]
        mc_top = all(x["is_mcblock"] for x in b_briefs) if b_briefs else False
        hack_top = any(x["is_hack337"] for x in b_briefs)
        if not mc_top or hack_top:
            all_mc_ok = False
        report["styles"][style] = {
            "without_b2v": w_briefs,
            "with_b2v": b_briefs,
            "mcblock_all_top": mc_top,
            "hack337_in_top": hack_top,
            "order_changed": [x["id"] for x in w_briefs] != [x["id"] for x in b_briefs],
        }
        print("===", style)
        print(" without:", [(x["id"][:28], x["score"], "mc" if x["is_mcblock"] else "other") for x in w_briefs])
        print(" with   :", [(x["id"][:28], x["score"], x["b2v_sim"], "mc" if x["is_mcblock"] else "other") for x in b_briefs])

    report["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    report["mcblock_wins_all_styles"] = all_mc_ok
    (out / "smoke_retrieval.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("mcblock_wins_all_styles", all_mc_ok)
    print("wrote", out / "smoke_retrieval.json")


if __name__ == "__main__":
    main()