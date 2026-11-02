"""风格 / 地形标签：推断规则、词表、读写。"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

# ---- 风格：优先用 MCBlock styles；无则 unknown ----
KNOWN_STYLES = [
    "unknown",
    "medieval",
    "fantasy",
    "modern",
    "european",
    "chinese",
    "rustic",
    "japanese",
    "industrial",
    "desert",
    "scifi",
    "western",
]

# 多风格时按此优先级取一个主风格
STYLE_PRIORITY = [
    "chinese",
    "japanese",
    "desert",
    "western",
    "industrial",
    "scifi",
    "european",
    "rustic",
    "modern",
    "medieval",
    "fantasy",
]

# ---- 地形：数据无显式字段，按文件名 / 显示名 / tags / primaryType 推断 ----
TERRAIN_NAMES = [
    "flat",      # 默认平地建筑
    "water",     # 船 / 码头 / 水上 / 湖畔 / 泳池
    "nature",    # 自然景观 / 植物 / 喷泉景观件
    "nether",    # 下界 / 地狱门
    "snow",      # 雪景
    "desert",    # 沙漠
    "mountain",  # 山 / 吊脚 / 悬崖 / 山庄
    "other",
]

# 关键词（中英），按优先级从高到低匹配；同时扫 stem、显示名、tags
_TERRAIN_NAME_RULES: list[tuple[str, list[str]]] = [
    ("nether", ["下界", "地狱", "nether", "hellgate"]),
    ("snow", [
        "雪屋", "雪地", "雪景", "snow", "ice cottage",
        "冰川", "冰原", "积雪", "frost", "雪山",
        "雪原", "冰雪", "冰屋", "雪",
    ]),
    ("desert", ["沙漠", "desert", "绿洲", "oasis"]),
    ("water", [
        "砂头", "水上", "船坞", "泳池", "港口",
        "渔村", "小舟", "帆船", "海盗",
        "石桥", "木桥", "桥梁", "dock", "pier", "boat", "bridge", "harbor",
        "灯塔", "lighthouse", "渡轮", "漂浮", "水城", "水屋",
        "桥", "船", "港", "渔", "温泉",
    ]),
    ("mountain", [
        # Strong only — bare "山"/cave/slope removed (too many FPs via rare search + substring)
        "悬崖", "峭壁", "山地", "山腰", "山顶",
        "mountain", "cliff", "peak", "alpine",
        "山上", "山间", "山中", "山里", "半山", "山谷", "山崖", "山麓", "依山",
        "山庄", "山寨", "山脚", "山峰", "山坡",
        "峡谷", "登山", "观景台", "山巅", "山洞",
        "崖壁", "山岭", "高山",
    ]),
]

_NATURE_TAGS = {"自然", "植物", "nature", "plant"}
_NATURE_TYPES = {"landscape_component", "plant_nature", "sculpture_figure"}

# tags / primaryType 对地形的补充信号
_TERRAIN_TAG_HINTS: dict[str, set[str]] = {
    "water": {"水", "桥", "船", "砂头", "港口", "渔", "港", "泳", "water", "boat", "bridge", "dock"},
    "snow": {"雪", "冰", "snow", "ice", "冰雪"},
    "mountain": {"山地", "山峰", "山庄", "悬崖", "mountain", "cliff", "peak", "alpine"},
    "nether": {"下界", "地狱", "nether"},
    "desert": {"沙漠", "desert"},
}


def pick_style(styles: list[str] | None) -> str:
    if not styles:
        return "unknown"
    cleaned = [str(s).strip().lower() for s in styles if s]
    if not cleaned:
        return "unknown"
    for pref in STYLE_PRIORITY:
        if pref in cleaned:
            return pref
    return cleaned[0] if cleaned[0] in KNOWN_STYLES else "unknown"


def _match_rules(blob: str) -> tuple[str, str] | None:
    if not blob:
        return None
    blob_l = blob.lower()
    for terrain, kws in _TERRAIN_NAME_RULES:
        for kw in kws:
            if kw.lower() in blob_l or kw in blob:
                return terrain, f"text:{kw}"
    return None


def _strong_mountain_evidence(stem: str, display_name: str | None, tags: list[str]) -> bool:
    """True if stem/name/tags contain a strong mountain keyword (not bare shan)."""
    blobs = [stem or "", display_name or "", " ".join(str(t) for t in tags)]
    mountain_kws: list[str] = []
    for terr, kws in _TERRAIN_NAME_RULES:
        if terr == "mountain":
            mountain_kws = kws
            break
    for blob in blobs:
        if not blob:
            continue
        bl = blob.lower()
        for kw in mountain_kws:
            if kw.lower() in bl or kw in blob:
                return True
    return False


def infer_terrain(
    *,
    stem: str,
    tags: list[str] | None,
    primary_type: str | None,
    styles: list[str] | None = None,
    display_name: str | None = None,
    rare_terrain_hits: list[str] | None = None,
) -> tuple[str, str]:
    """Return (terrain, reason).

    Order: filename/name text -> tags -> style:desert -> rare_hit (advisory) -> nature/other -> flat.
    mountain rare_hit requires strong text evidence (MCBlock mountain search over-tagged flats).
    """
    tags = tags or []
    tag_set = {str(t).strip() for t in tags}
    styles = [str(s).lower() for s in (styles or [])]
    rare = [str(x).strip().lower() for x in (rare_terrain_hits or []) if x]

    # 1) filename / display name
    for blob, src in ((stem or "", "filename"), (display_name or "", "name")):
        hit = _match_rules(blob)
        if hit:
            terrain, reason = hit
            return terrain, f"{src}:{reason.split(':', 1)[-1]}"

    # 2) tags
    tag_blob = " ".join(sorted(tag_set))
    hit = _match_rules(tag_blob)
    if hit:
        terrain, reason = hit
        return terrain, f"tags:{reason.split(':', 1)[-1]}"

    for terrain, hints in _TERRAIN_TAG_HINTS.items():
        inter = tag_set & hints
        if inter:
            return terrain, f"tag_hint:{sorted(inter)[0]}"

    if "desert" in styles:
        return "desert", "style:desert"

    # 3) rare_terrain_hits BEFORE nature default (keeps snow/nether search tags)
    if rare:
        t0 = rare[0]
        if t0 in set(TERRAIN_NAMES):
            if t0 == "mountain":
                if _strong_mountain_evidence(stem, display_name, list(tags)):
                    return "mountain", "rare_hit+text:mountain"
                # ignore weak mountain rare_hit
            else:
                return t0, f"rare_hit:{t0}"

    pt = (primary_type or "").strip()
    if pt in _NATURE_TYPES or (tag_set & _NATURE_TAGS):
        if pt == "vehicle_transport":
            return "other", "primaryType:vehicle_transport"
        return "nature", f"nature_signal:pt={pt or '-'} tags={sorted(tag_set & _NATURE_TAGS)}"

    if pt == "vehicle_transport":
        return "other", "primaryType:vehicle_transport"

    return "flat", "default:flat"


def build_vocab(style_counts: Counter, terrain_counts: Counter) -> dict[str, Any]:
    # 固定顺序：先预定义，再补遗漏
    styles = list(KNOWN_STYLES)
    for s in style_counts:
        if s not in styles:
            styles.append(s)
    terrains = list(TERRAIN_NAMES)
    for t in terrain_counts:
        if t not in terrains:
            terrains.append(t)
    return {
        "styles": styles,
        "terrains": terrains,
        "style_to_id": {n: i for i, n in enumerate(styles)},
        "terrain_to_id": {n: i for i, n in enumerate(terrains)},
        "style_counts": dict(style_counts),
        "terrain_counts": dict(terrain_counts),
    }


def load_vocab(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_labels_map(path: str | Path) -> dict[str, dict[str, Any]]:
    """key = npz 文件名（含.npz）或 stem。"""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict) and "samples" in raw:
        items = raw["samples"]
    elif isinstance(raw, list):
        items = raw
    else:
        items = raw
    out: dict[str, dict[str, Any]] = {}
    if isinstance(items, dict):
        for k, v in items.items():
            out[str(k)] = v
            out[Path(str(k)).stem] = v
            out[Path(str(k)).name] = v
    else:
        for row in items:
            key = row.get("file") or row.get("npz") or row.get("stem")
            if not key:
                continue
            name = Path(str(key)).name
            out[name] = row
            out[Path(name).stem] = row
    return out


def resolve_style_id(vocab: dict[str, Any], name_or_id: str | int) -> int:
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        return int(name_or_id)
    key = str(name_or_id).strip().lower()
    m = vocab["style_to_id"]
    if key not in m:
        raise KeyError(f"未知 style={name_or_id!r}，可选：{list(m)}")
    return int(m[key])


def resolve_terrain_id(vocab: dict[str, Any], name_or_id: str | int) -> int:
    if isinstance(name_or_id, int) or (isinstance(name_or_id, str) and name_or_id.isdigit()):
        return int(name_or_id)
    key = str(name_or_id).strip().lower()
    m = vocab["terrain_to_id"]
    if key not in m:
        raise KeyError(f"未知 terrain={name_or_id!r}，可选：{list(m)}")
    return int(m[key])
