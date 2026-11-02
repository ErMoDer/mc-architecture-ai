# -*- coding: utf-8 -*-
"""Smoke: load TransformerBlock2Vec, embed one schematic, optional similar."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--litematic", default=None, help="reference .litematic; default: first small under data/")
    ap.add_argument("--similar", action="store_true", help="also run generate_similar_from_feature")
    ap.add_argument("--num", type=int, default=1)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    import numpy as np
    import torch
    from src.models.block2vec import load_block2vec
    from src.app.block2vec_embed import embed_litematic, search_index
    from src.app.reference_features import extract_reference_features, generate_similar_from_feature

    out_dir = ROOT / "outputs" / "block2vec_smoke"
    out_dir.mkdir(parents=True, exist_ok=True)

    lit = args.litematic
    if not lit:
        cands = sorted((ROOT / "data").rglob("*.litematic"), key=lambda p: p.stat().st_size)
        if not cands:
            raise SystemExit("no .litematic found under data/")
        lit = str(cands[0])
    lit_path = Path(lit)
    if not lit_path.is_absolute():
        lit_path = ROOT / lit_path

    report = {
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cuda": bool(torch.cuda.is_available()),
        "litematic": str(lit_path),
    }

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_block2vec(device=device)
    report["model_device"] = str(next(model.parameters()).device)
    report["model_dtype"] = str(next(model.parameters()).dtype)

    emb = embed_litematic(lit_path, device=device)
    report["embed"] = {
        "dim": emb["dim"],
        "n_chunks": emb["n_chunks"],
        "size": emb.get("size"),
        "backend": emb["backend"],
        "token_map": emb["token_map"],
        "norm": float(np.linalg.norm(emb["vector"])),
        "preview": [round(float(x), 5) for x in emb["vector"][:8]],
    }

    feat = extract_reference_features(lit_path, write=True, embed_block2vec=True)
    report["feature_id"] = feat.get("id")
    report["block2vec"] = feat.get("block2vec")
    hits = search_index(emb["vector"], top_k=5)
    report["search_top"] = hits

    if args.similar:
        sim_dir = out_dir / "similar"
        variants = generate_similar_from_feature(
            feat, num=int(args.num), seed=args.seed, out_dir=sim_dir
        )
        report["similar"] = {
            "out_dir": str(sim_dir.relative_to(ROOT)),
            "files": [Path(v["npz_path"]).name for v in variants],
        }

    report["ok"] = bool((feat.get("block2vec") or {}).get("ok") and emb["dim"] == 144)
    (out_dir / "smoke_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Block2Vec smoke\n",
        "- cuda: %s\n" % report["cuda"],
        "- litematic: `%s`\n" % lit_path,
        "- dim=%s chunks=%s norm=%.4f\n" % (emb["dim"], emb["n_chunks"], report["embed"]["norm"]),
        "- feature_id: `%s`\n" % feat.get("id"),
        "- neighbors:\n",
    ]
    for h in hits:
        lines.append("  - %.4f `%s`\n" % (h["score"], h["id"]))
    if args.similar:
        lines.append("- similar out: `%s`\n" % report["similar"]["out_dir"])
    (out_dir / "smoke_report.md").write_text("".join(lines), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "feature_id": report["feature_id"], "embed": report["embed"], "search_top": hits[:3]}, ensure_ascii=False, indent=2))
    print("report=", out_dir / "smoke_report.md")


if __name__ == "__main__":
    main()
