"""从 meta.json + processed npz 推断 style/terrain，写出词表与标签文件。"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.labels import (
    build_vocab,
    infer_terrain,
    pick_style,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processed", default="data/processed")
    parser.add_argument("--vocab-out", default="data/label_vocab.json")
    parser.add_argument("--labels-out", default="data/processed/labels.json")
    args = parser.parse_args()

    processed = ROOT / args.processed
    meta_path = processed / "meta.json"
    meta_by_file: dict[str, dict] = {}
    if meta_path.exists():
        rows = json.loads(meta_path.read_text(encoding="utf-8"))
        for row in rows:
            name = Path(row["file"]).name
            meta_by_file[name] = row
            meta_by_file[Path(name).stem] = row

    npz_files = sorted(processed.glob("*.npz"))
    if not npz_files:
        raise SystemExit(f"无数据：{processed}\\*.npz")

    style_counts: Counter = Counter()
    terrain_counts: Counter = Counter()
    reason_counts: Counter = Counter()
    samples: list[dict] = []

    for npz in npz_files:
        stem = npz.stem
        row = meta_by_file.get(npz.name) or meta_by_file.get(stem) or {}
        lab = row.get("labels") or {}
        styles = lab.get("styles") or []
        tags = lab.get("tags") or []
        primary = lab.get("primaryType")
        display_name = row.get("name") or lab.get("name")
        style = pick_style(styles)
        rare_hits = lab.get("rare_terrain_hits") or row.get("rare_terrain_hits") or []
        terrain, reason = infer_terrain(
            stem=stem,
            tags=tags,
            primary_type=primary,
            styles=styles,
            display_name=display_name,
            rare_terrain_hits=rare_hits,
        )
        style_counts[style] += 1
        terrain_counts[terrain] += 1
        reason_counts[reason.split(":")[0]] += 1
        samples.append(
            {
                "file": str(npz.relative_to(ROOT)).replace("\\", "/"),
                "stem": stem,
                "style": style,
                "terrain": terrain,
                "style_id": None,  # filled after vocab
                "terrain_id": None,
                "reason": reason,
                "raw_styles": styles,
                "tags": tags,
                "primaryType": primary,
                "display_name": display_name,
            }
        )

    vocab = build_vocab(style_counts, terrain_counts)
    for s in samples:
        s["style_id"] = vocab["style_to_id"][s["style"]]
        s["terrain_id"] = vocab["terrain_to_id"][s["terrain"]]

    vocab_path = ROOT / args.vocab_out
    labels_path = ROOT / args.labels_out
    vocab_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.parent.mkdir(parents=True, exist_ok=True)

    vocab_out = {
        **vocab,
        "num_styles": len(vocab["styles"]),
        "num_terrains": len(vocab["terrains"]),
        "rules_note": "see docs/conditioning.md",
    }
    vocab_path.write_text(json.dumps(vocab_out, ensure_ascii=False, indent=2), encoding="utf-8")
    labels_path.write_text(
        json.dumps({"samples": samples, "vocab": str(vocab_path.relative_to(ROOT)).replace("\\", "/")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"samples={len(samples)}")
    print("style_counts:", dict(style_counts.most_common()))
    print("terrain_counts:", dict(terrain_counts.most_common()))
    print("reason_family:", dict(reason_counts.most_common()))
    print(f"wrote {vocab_path}")
    print(f"wrote {labels_path}")
    rare = [t for t, c in terrain_counts.items() if c < 3]
    if rare:
        print(f"note: rare terrains (<3) kept for interpretability: {rare}")


if __name__ == "__main__":
    main()
