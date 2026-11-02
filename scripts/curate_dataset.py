"""从 mixed_v2 清洗出可训练的建筑数据集 mixed_v3。

筛选：真三维 / 有封闭室内 / 非实心 / 主体连通 / 剔除载具雕像像素画。
补标：对 style=unknown 的样本按方块构成推断风格，让条件信号真正生效。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
from collections import Counter

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.app.morph import dilate, largest_component_ratio  # noqa: E402

# 非建筑名称关键词（载具/雕像/像素画/自然物/食物/武器/生物/机械）
_NOT_BUILDING = re.compile(
    r"car\b|truck|bus\b|plane|aircraft|airship|helicopter|drone|jet|boat|ship|"
    r"train|locomotive|wagon|bike|motorcycle|tank|mech|warthog|"
    r"statue|figure|sculpture|pixel|pixelart|art\b|logo|banner|flag|poster|"
    r"tree|bush|flower|garden|plant|leaves|cactus|mushroom|"
    r"food|pumpkin|melon|apple|cake|bread|pizza|burger|"
    r"sword|axe|bow\b|pickaxe|gun|cannon|arrow|"
    r"animal|horse|dog|cat\b|creeper|zombie|enderman|villager|skin|head\b|"
    r"machine|generator|robot|frame|scaffold",
    re.I,
)

# 风格推断用的方块族（按 minecraft 方块名子串匹配）
_STYLE_BLOCKS: dict[str, tuple[str, ...]] = {
    "modern": (
        "white_concrete", "light_gray_concrete", "gray_concrete", "black_concrete",
        "quartz", "smooth_stone", "glass", "iron_block", "sea_lantern",
        "polished_andesite", "polished_diorite", "smooth_quartz",
    ),
    "medieval": (
        "oak_log", "oak_planks", "spruce_log", "spruce_planks", "cobblestone",
        "mossy_cobblestone", "stone_bricks", "dark_oak", "hay_block",
        "barrel", "stripped_", "bookshelf",
    ),
    "fantasy": (
        "purpur", "amethyst", "glowstone", "prismarine", "end_stone",
        "magenta", "purple", "nether_brick", "crying_obsidian", "shroomlight",
    ),
    "japanese": (
        "dark_oak_log", "bamboo", "cherry", "white_concrete", "blackstone",
        "stripped_dark_oak", "deepslate_tiles",
    ),
    "desert": (
        "sandstone", "terracotta", "smooth_sandstone", "red_sandstone",
        "cut_sandstone", "sand", "chiseled_sandstone",
    ),
    "rustic": (
        "oak_planks", "spruce_planks", "cobblestone", "hay_block",
        "dirt", "coarse_dirt", "oak_log", "spruce_log", "grass_block",
    ),
    "chinese": (
        "red_terracotta", "red_concrete", "dark_prismarine", "lantern",
        "quartz", "blackstone", "red_nether_brick",
    ),
    "industrial": (
        "iron_block", "stone_bricks", "furnace", "hopper", "chain",
        "copper", "gray_concrete", "light_gray_concrete", "rail",
    ),
    "european": (
        "stone_bricks", "brick", "white_concrete", "quartz", "oak_planks",
        "cobblestone", "polished",
    ),
    "scifi": (
        "white_concrete", "light_blue_concrete", "sea_lantern", "quartz",
        "glass", "cyan_concrete", "blue_concrete",
    ),
}

_STYLE_MIN_SCORE = 0.18  # 该族方块占比至少这么多才判定
_STYLE_MIN_MARGIN = 0.04


def load_voxels(p: pathlib.Path) -> np.ndarray:
    f = np.load(p)
    return f["voxels"] if "voxels" in f else f[f.files[0]]


def enclosed_air(solid: np.ndarray, max_iter: int = 24, seal: bool = True) -> int:
    """6 邻接从边界扩散得到的“室外空气”，其余空气即封闭室内。

    seal=True 时先把墙体加厚 1 格再判断，避免门洞/单格缺口让室内空气“漏”出去，
    导致有门有窗的正常房屋被误判为没有室内。
    """
    sealed = dilate(solid) if seal else solid
    air = ~sealed
    out = np.zeros_like(air)
    out[0, :, :] = air[0, :, :]
    out[-1, :, :] = air[-1, :, :]
    out[:, 0, :] = air[:, 0, :]
    out[:, -1, :] = air[:, -1, :]
    out[:, :, 0] = air[:, :, 0]
    out[:, :, -1] = air[:, :, -1]
    for _ in range(max_iter):
        nxt = out | (dilate(out) & air)
        if np.array_equal(nxt, out):
            break
        out = nxt
    # 统计时用原始空气（不是加厚后的），避免室内被削薄导致误判
    return int((~solid & ~out).sum())


def guess_style_by_blocks(vox: np.ndarray, name_by_id: dict[int, str]) -> tuple[str, float, float]:
    solid = vox[vox > 0]
    if solid.size == 0:
        return "unknown", 0.0, 0.0
    total = float(solid.size)
    ids, counts = np.unique(solid, return_counts=True)
    names = [name_by_id.get(int(i), "") for i in ids]
    scores: dict[str, float] = {}
    for style, pats in _STYLE_BLOCKS.items():
        hit = 0.0
        for nm, c in zip(names, counts):
            if any(p in nm for p in pats):
                hit += float(c)
        scores[style] = hit / total
    best = max(scores, key=scores.get)
    best_v = scores[best]
    rest = max((v for k, v in scores.items() if k != best), default=0.0)
    if best_v >= _STYLE_MIN_SCORE and (best_v - rest) >= _STYLE_MIN_MARGIN:
        return best, best_v, rest
    return "unknown", best_v, rest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/processed/mixed_v2")
    ap.add_argument("--out", default="data/processed/mixed_v3")
    ap.add_argument("--palette", default="data/palette.json")
    ap.add_argument("--vocab", default="data/label_vocab.json")
    ap.add_argument("--min-dim", type=int, default=5, help="三维最小边长；更小视为平面/薄片")
    ap.add_argument("--min-blocks", type=int, default=300)
    ap.add_argument("--max-fill", type=float, default=0.90, help="包围盒填充率上限，剔除实心块")
    ap.add_argument("--min-enclosed", type=int, default=30, help="封闭室内空气体素数下限")
    ap.add_argument("--min-cc", type=float, default=0.55, help="最大连通体占比下限")
    ap.add_argument("--min-height", type=int, default=5)
    ap.add_argument("--cap-per-style", type=int, default=1300)
    args = ap.parse_args()

    src = ROOT / args.src
    out = ROOT / args.out
    raw_pal = json.load(open(ROOT / args.palette, encoding="utf-8"))
    name_by_id = {int(k): str(v) for k, v in raw_pal.items()}
    vocab = json.load(open(ROOT / args.vocab, encoding="utf-8"))

    samples = json.load(open(src / "labels.json", encoding="utf-8"))["samples"]
    out.mkdir(parents=True, exist_ok=True)
    kept: list[dict] = []
    drop = Counter()
    relabeled = 0

    for row in samples:
        p = ROOT / row["file"]
        if not p.exists():
            drop["missing"] += 1
            continue
        stem = row["stem"]
        name_blob = f"{stem} {row.get('display_name') or ''} " + " ".join(row.get("tags") or [])
        if _NOT_BUILDING.search(name_blob):
            drop["non_building_name"] += 1
            continue
        try:
            vox = load_voxels(p)
        except Exception:
            drop["load_error"] += 1
            continue
        solid = vox > 0
        n = int(solid.sum())
        if n < args.min_blocks:
            drop["too_sparse"] += 1
            continue
        dims = []
        for ax in (0, 1, 2):
            idx = np.where(solid.any(axis=tuple(i for i in (0, 1, 2) if i != ax)))[0]
            dims.append(int(idx[-1] - idx[0] + 1))
        dims.sort()
        if dims[0] < args.min_dim:
            drop["planar_or_thin"] += 1
            continue
        sy = int(np.where(solid.any(axis=(0, 2)))[0][-1] - np.where(solid.any(axis=(0, 2)))[0][0] + 1)
        if sy < args.min_height:
            drop["too_flat_height"] += 1
            continue
        bbox = dims[0] * dims[1] * dims[2]
        if n / bbox > args.max_fill:
            drop["solid_blob"] += 1
            continue
        if largest_component_ratio(solid) < args.min_cc:
            drop["fragmented"] += 1
            continue
        if enclosed_air(solid) < args.min_enclosed:
            drop["no_interior"] += 1
            continue

        style = row.get("style") or "unknown"
        score = margin = 0.0
        if style == "unknown":
            style, score, margin = guess_style_by_blocks(vox, name_by_id)
            relabeled += 1
        if style not in vocab["style_to_id"]:
            style = "unknown"

        dst = out / p.name
        if not dst.exists():
            shutil.copy2(p, dst)
        kept.append({
            "file": str(dst.relative_to(ROOT)).replace("\\", "/"),
            "stem": stem,
            "style": style,
            "terrain": row.get("terrain") or "flat",
            "style_id": int(vocab["style_to_id"][style]),
            "terrain_id": int(vocab["terrain_to_id"].get(row.get("terrain") or "flat", 0)),
            "reason": f"curated:{row.get('reason', '')}",
            "raw_styles": row.get("raw_styles") or [],
            "tags": row.get("tags") or [],
            "primaryType": row.get("primaryType"),
            "display_name": row.get("display_name"),
            "style_score": round(score, 3),
            "style_margin": round(margin, 3),
        })

    # 按风格限流，避免单一风格压倒
    by_style = Counter(r["style"] for r in kept)
    capped: list[dict] = []
    seen: Counter = Counter()
    dropped_cap = 0
    for r in kept:
        s = r["style"]
        if seen[s] >= args.cap_per_style:
            dropped_cap += 1
            continue
        seen[s] += 1
        capped.append(r)

    # 清掉 out 目录里不在 cap 列表的多余 npz
    keep_names = {pathlib.Path(r["file"]).name for r in capped}
    for f in out.glob("*.npz"):
        if f.name not in keep_names:
            f.unlink()

    payload = {
        "samples": capped,
        "meta": {
            "source": str(args.src),
            "kept": len(capped),
            "dropped": dict(drop),
            "dropped_by_cap": dropped_cap,
            "relabel_attempts": relabeled,
            "style_counts_before_cap": dict(by_style),
            "style_counts": dict(Counter(r["style"] for r in capped)),
            "terrain_counts": dict(Counter(r["terrain"] for r in capped)),
        },
    }
    json.dump(payload, open(out / "labels.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(payload["meta"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
