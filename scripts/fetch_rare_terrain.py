"""按名称关键词捞稀有地形建筑，合并进既有 mcblock manifest（不覆盖）。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.mcblock_api import download_projection, get_building, list_buildings, save_manifest

# 稀有地形名称关键词（命中任一即保留下载）
KEYWORD_GROUPS: dict[str, list[str]] = {
    "water": [
        "码头", "水上", "湖畔", "泳池", "港口", "帆船", "小船", "渡船", "渔船",
        "桥梁", "石桥", "木桥", "吊桥", "dock", "pier", "boat", "bridge", "harbor",
        "湖", "河", "船", "桥", "喷泉", "渔", "灯塔", "lighthouse", "运河",
        "漂流", "水车", "堰", "水驿", "水上别墅",
    ],
    "snow": [
        "雪景", "雪人", "雪屋", "snow", "冰屋", "冰原", "冰雪", "frost",
        "雪地", "雪峰", "雪原", "冬日", "冰雕", "雪球", "雪原小屋",
        "雪",  # 短词：站点雪景样本极少，放宽
    ],
    "mountain": [
        "吊脚", "悬崖", "山顶", "山腰", "山地", "mountain", "cliff", "slope",
        "山庄", "山寨", "峭壁", "高地", "山坡", "山丘", "洞穴", "cave", "峡谷",
        "火山", "观景台", "山顶小屋",
        "山",  # 短词放宽：山庄/白山/火山等
    ],
    "nether": ["下界", "地狱", "nether"],
    "desert": ["沙漠", "desert", "绿洲", "oasis"],
}


def _hit(text: str, kws: list[str]) -> str | None:
    t = text or ""
    tl = t.lower()
    for kw in kws:
        if kw.lower() in tl or kw in t:
            return kw
    return None


def classify_name(name: str) -> list[str]:
    hits = []
    for terrain, kws in KEYWORD_GROUPS.items():
        if _hit(name, kws):
            hits.append(terrain)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/raw/mcblock")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--max-blocks", type=int, default=4000)
    parser.add_argument("--max-edge", type=int, default=64)
    parser.add_argument("--sleep", type=float, default=0.55)
    parser.add_argument(
        "--terrains",
        default="water,snow,mountain,nether,desert",
        help="只捞这些地形关键词组",
    )
    parser.add_argument("--styles", default="", help="可选额外 styles 逗号分隔")
    parser.add_argument("--sort", default="recommended")
    args = parser.parse_args()

    want = {t.strip() for t in args.terrains.split(",") if t.strip()}
    groups = {k: v for k, v in KEYWORD_GROUPS.items() if k in want}
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"

    existing: list[dict] = []
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    have_ids = {r.get("id") for r in existing if r.get("id")}
    print(f"existing manifest={len(existing)} ids={len(have_ids)}")

    styles = [s for s in args.styles.split(",") if s] or None
    print(f"listing pages={args.max_pages} terrains={sorted(want)} styles={styles}")
    items = list_buildings(
        limit=args.limit,
        max_pages=args.max_pages,
        sort=args.sort,
        styles=styles,
        difficulties=["beginner", "intermediate"],
        max_blocks=args.max_blocks,
        max_width=args.max_edge,
        max_depth=args.max_edge,
        sleep_s=args.sleep,
    )
    # 尺寸再过滤
    items = [
        it
        for it in items
        if max(int(it.get("width") or 0), int(it.get("height") or 0), int(it.get("depth") or 0))
        <= args.max_edge
        and int(it.get("blockCount") or 0) <= args.max_blocks
    ]

    candidates = []
    for it in items:
        name = it.get("name") or ""
        hits = [t for t in classify_name(name) if t in want]
        if hits:
            candidates.append((it, hits))
    print(f"listed={len(items)} keyword_candidates={len(candidates)}")
    from collections import Counter
    print("candidate_by_terrain", dict(Counter(t for _, hs in candidates for t in hs)))

    new_rows = []
    ok = skip_have = fail = 0
    for i, (it, hits) in enumerate(candidates, 1):
        bid = it["id"]
        if bid in have_ids:
            skip_have += 1
            continue
        try:
            detail = get_building(bid)
            time.sleep(args.sleep)
            # tags 再兜一层（名称未命中但 tags 命中的情况已在 list 过滤外；这里补强）
            tags = detail.get("tags")
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = [tags]
            tag_blob = " ".join(map(str, tags or []))
            extra = classify_name(tag_blob)
            hits = sorted(set(hits) | {t for t in extra if t in want})
            path = download_projection(detail, out_dir)
            time.sleep(args.sleep)
            if path is None:
                print(f"[{i}/{len(candidates)}] SKIP no projection {it.get('name')}")
                fail += 1
                continue
            row = {
                "id": bid,
                "name": detail.get("name") or it.get("name"),
                "tags": tags,
                "styles": it.get("styles"),
                "difficulty": detail.get("difficulty") or it.get("difficulty"),
                "primaryType": it.get("primaryType"),
                "width": detail.get("width") or it.get("width"),
                "height": detail.get("height") or it.get("height"),
                "depth": detail.get("depth") or it.get("depth"),
                "blockCount": detail.get("blockCount") or it.get("blockCount"),
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "projectionFileUrl": detail.get("projectionFileUrl"),
                "rare_terrain_hits": hits,
            }
            new_rows.append(row)
            have_ids.add(bid)
            ok += 1
            print(f"[{i}/{len(candidates)}] OK {row['name']} hits={hits} -> {path.name}")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(candidates)}] FAIL {it.get('name')}: {e}")

    merged = existing + new_rows
    save_manifest(merged, manifest_path)
    print(
        f"done: new_ok={ok} already_have={skip_have} fail={fail} "
        f"manifest_total={len(merged)} -> {manifest_path}"
    )


if __name__ == "__main__":
    main()
