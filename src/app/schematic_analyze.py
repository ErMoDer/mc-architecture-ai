# -*- coding: utf-8 -*-
"""Phase 1: analyze a .litematic — structure, art/style, redstone inventory.

Rule/graph heuristics only. No tick simulation, no ML, no fit_to_cube by default.
"""
from __future__ import annotations

import json
from collections import Counter, deque
from pathlib import Path
from typing import Any

import numpy as np

from src.data.litematic import load_litematic, load_litematic_detailed
from src.data.labels import KNOWN_STYLES
from src.app.redstone_analyze import analyze_redstone, redstone_to_markdown_sections

# ---------------------------------------------------------------------------
# Block helpers
# ---------------------------------------------------------------------------

_AIR = frozenset({"air", "cave_air", "void_air", "structure_void"})

_STRUCT_FAMILIES: list[tuple[str, tuple[str, ...]]] = [
    ("stairs", ("_stairs",)),
    ("slabs", ("_slab",)),
    ("walls", ("_wall",)),
    ("fences", ("_fence", "fence_gate")),
    ("doors", ("_door",)),
    ("trapdoors", ("_trapdoor",)),
    ("glass", ("glass",)),
    ("logs", ("_log", "_wood", "_stem", "hyphae")),
    ("planks", ("_planks",)),
    ("stone_bricks", ("stone_bricks", "stone_brick")),
    ("deepslate", ("deepslate",)),
    ("terracotta", ("terracotta",)),
    ("concrete", ("concrete",)),
    ("wool", ("wool", "carpet")),
    ("leaves", ("_leaves",)),
    ("lanterns", ("lantern", "campfire", "candle")),
    ("copper", ("copper",)),
    ("nether", ("nether", "blackstone", "basalt", "crimson", "warped", "soul_")),
]

_PALETTE_BUCKETS: list[tuple[str, tuple[str, ...]]] = [
    ("wood", ("_planks", "_log", "_wood", "_stem", "hyphae", "bamboo", "stripped_")),
    ("stone", ("stone", "cobble", "andesite", "diorite", "granite", "calcite", "tuff", "brick")),
    ("deepslate", ("deepslate",)),
    ("terracotta", ("terracotta",)),
    ("concrete", ("concrete",)),
    ("wool", ("wool", "carpet")),
    ("glass", ("glass",)),
    ("nether", ("nether", "blackstone", "basalt", "crimson", "warped", "soul_sand", "soul_soil", "magma")),
    ("copper", ("copper",)),
    ("prismarine", ("prismarine", "sea_lantern")),
    ("sandstone", ("sandstone", "red_sand")),
    ("sand", ("sand",)),
    ("snow_ice", ("snow", "ice", "packed_ice", "blue_ice", "powder_snow")),
    ("leaves", ("_leaves", "moss", "azalea")),
    ("metal", ("iron_", "gold_", "chain", "anvil", "hopper", "cauldron")),
]

_STYLE_MATERIAL_HINTS: dict[str, dict[str, float]] = {
    "medieval": {"stone": 0.35, "wood": 0.2, "stone_bricks_family": 0.25, "deepslate": 0.1},
    "fantasy": {"stone": 0.15, "wood": 0.15, "glass": 0.1, "leaves": 0.1, "wool": 0.1},
    "modern": {"concrete": 0.35, "glass": 0.25, "metal": 0.15, "wool": 0.05, "deepslate": 0.1},
    "european": {"stone": 0.3, "stone_bricks_family": 0.2, "glass": 0.1, "wood": 0.1},
    "chinese": {"wood": 0.35, "leaves": 0.1, "stone": 0.1},
    "japanese": {"wood": 0.35, "leaves": 0.15, "stone": 0.1},
    "rustic": {"wood": 0.45, "leaves": 0.1, "stone": 0.1, "wool": 0.05},
    "industrial": {"metal": 0.3, "concrete": 0.2, "copper": 0.15, "stone": 0.1},
    "desert": {"sandstone": 0.45, "terracotta": 0.25, "sand": 0.1},
    "scifi": {"concrete": 0.2, "glass": 0.2, "metal": 0.2, "copper": 0.15},
    "western": {"wood": 0.35, "sandstone": 0.15, "terracotta": 0.1},
}


def _short(name: str) -> str:
    n = str(name).strip()
    if n.startswith("minecraft:"):
        n = n[len("minecraft:") :]
    return n


def _is_air(name: str) -> bool:
    return _short(name) in _AIR


def _family_match(short: str, needles: tuple[str, ...]) -> bool:
    for n in needles:
        if short == n:
            return True
        if n.startswith("_"):
            if short.endswith(n):
                return True
            continue
        if n in short:
            return True
    return False


def _air_ids(palette: list[str]) -> set[int]:
    return {i for i, n in enumerate(palette) if _is_air(n)}


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def _connected_components_solid(solid: np.ndarray) -> tuple[int, int, list[int]]:
    sx, sy, sz = solid.shape
    visited = np.zeros(solid.shape, dtype=np.uint8)
    sizes: list[int] = []
    neighbors = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    xs, ys, zs = np.where(solid)
    for i in range(xs.size):
        x0, y0, z0 = int(xs[i]), int(ys[i]), int(zs[i])
        if visited[x0, y0, z0]:
            continue
        q: deque[tuple[int, int, int]] = deque()
        q.append((x0, y0, z0))
        visited[x0, y0, z0] = 1
        count = 0
        while q:
            x, y, z = q.popleft()
            count += 1
            for dx, dy, dz in neighbors:
                nx, ny, nz = x + dx, y + dy, z + dz
                if 0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz:
                    if solid[nx, ny, nz] and not visited[nx, ny, nz]:
                        visited[nx, ny, nz] = 1
                        q.append((nx, ny, nz))
        sizes.append(count)
    sizes.sort(reverse=True)
    largest = sizes[0] if sizes else 0
    return len(sizes), largest, sizes[:20]


def _hollow_score(solid: np.ndarray) -> dict[str, Any]:
    sx, sy, sz = solid.shape
    if sx < 3 or sy < 3 or sz < 3:
        return {
            "hollow_score": 0.0,
            "exterior_solid_frac": float(solid.mean()) if solid.size else 0.0,
            "interior_solid_frac": float(solid.mean()) if solid.size else 0.0,
            "interior_air_frac": float((~solid).mean()) if solid.size else 0.0,
            "exterior_layer_solid_count": int(solid.sum()),
            "note": "体量过小，无法估计空心度",
        }
    interior = solid[1:-1, 1:-1, 1:-1]
    shell = solid.copy()
    shell[1:-1, 1:-1, 1:-1] = False
    interior_air_frac = float((~interior).mean()) if interior.size else 0.0
    interior_solid_frac = float(interior.mean()) if interior.size else 0.0
    exterior_solid_frac = float(shell.mean()) if shell.size else 0.0
    hollow_score = float(np.clip(interior_air_frac, 0.0, 1.0))
    return {
        "hollow_score": round(hollow_score, 4),
        "exterior_layer_solid_count": int(shell.sum()),
        "exterior_solid_frac": round(exterior_solid_frac, 4),
        "interior_solid_frac": round(interior_solid_frac, 4),
        "interior_air_frac": round(interior_air_frac, 4),
        "note": "hollow_score≈收缩1格后内部空气占比；高≈偏空心，低≈实心堆砌。启发式，非精确墙厚。",
    }


def _floor_guess(solid: np.ndarray) -> dict[str, Any]:
    per_y = solid.sum(axis=(0, 2)).astype(np.int64)
    total = int(per_y.sum())
    if total == 0:
        return {"floor_guess": 0, "y_peaks": [], "y_histogram": [], "note": "无实心方块"}
    thresh = max(3, int(0.08 * per_y.max()))
    peaks: list[int] = []
    for y in range(len(per_y)):
        v = int(per_y[y])
        if v < thresh:
            continue
        left = int(per_y[y - 1]) if y > 0 else 0
        right = int(per_y[y + 1]) if y + 1 < len(per_y) else 0
        if v >= left and v >= right:
            peaks.append(y)
    merged: list[int] = []
    for y in peaks:
        if merged and y - merged[-1] <= 2:
            if per_y[y] > per_y[merged[-1]]:
                merged[-1] = y
        else:
            merged.append(y)
    floor_guess = max(1, len(merged)) if merged else 1
    hist = [{"y": int(i), "solid": int(per_y[i])} for i in range(len(per_y)) if per_y[i] > 0]
    return {
        "floor_guess": int(floor_guess),
        "y_peaks": merged,
        "y_histogram": hist[:64],
        "note": "按 Y 向实心峰值粗估楼层，含屋顶/地基误判；仅供参考。",
    }


def _axis_symmetry(solid: np.ndarray) -> dict[str, float]:
    def score(arr: np.ndarray, axis: int) -> float:
        flipped = np.flip(arr, axis=axis)
        inter = np.logical_and(arr, flipped).sum()
        union = np.logical_or(arr, flipped).sum()
        if union == 0:
            return 0.0
        return float(inter) / float(union)

    return {
        "symmetry_x": round(score(solid, 0), 4),
        "symmetry_z": round(score(solid, 2), 4),
        "symmetry_y": round(score(solid, 1), 4),
    }


def _structural_families(counts: Counter[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for fam, needles in _STRUCT_FAMILIES:
        total = 0
        for name, c in counts.items():
            if fam == "doors" and "trapdoor" in name:
                continue
            if fam == "lanterns" and "redstone" in name:
                continue
            if fam == "fences":
                if name.endswith("_fence") or "fence_gate" in name:
                    total += c
                continue
            if _family_match(name, needles):
                total += c
        out[fam] = int(total)
    return out


# ---------------------------------------------------------------------------
# Style / materials
# ---------------------------------------------------------------------------


def _palette_buckets(counts: Counter[str]) -> dict[str, int]:
    bucket_counts: dict[str, int] = {b: 0 for b, _ in _PALETTE_BUCKETS}
    for name, c in counts.items():
        for b, needles in _PALETTE_BUCKETS:
            if _family_match(name, needles):
                # sand vs sandstone: sandstone needles checked before sand if ordered —
                # sandstone bucket before sand in list; "sand" in "sandstone" would false-hit sand
                if b == "sand" and "sandstone" in name:
                    continue
                if b == "stone" and any(
                    x in name for x in ("redstone", "grindstone", "lodestone", "glowstone", "deepslate")
                ):
                    continue
                bucket_counts[b] += c
                break
    return bucket_counts


def _guess_styles(
    bucket_counts: dict[str, int],
    family_counts: dict[str, int],
    stem: str,
) -> list[dict[str, Any]]:
    total = sum(bucket_counts.values()) or 1
    shares = {k: v / total for k, v in bucket_counts.items()}
    fam_total = sum(family_counts.values()) or 1
    shares["stone_bricks_family"] = family_counts.get("stone_bricks", 0) / fam_total

    scores: dict[str, float] = {s: 0.0 for s in KNOWN_STYLES if s != "unknown"}
    for style, weights in _STYLE_MATERIAL_HINTS.items():
        s = 0.0
        wsum = 0.0
        for bucket, w in weights.items():
            s += shares.get(bucket, 0.0) * w
            wsum += w
        scores[style] = s / wsum if wsum else 0.0

    blob = stem.lower()
    file_hints = [
        ("chinese", ["中式", "中国", "飞檐", "chinese"]),
        ("japanese", ["日式", "和风", "japanese"]),
        ("desert", ["沙漠", "desert"]),
        ("western", ["西部", "western"]),
        ("industrial", ["工业", "industrial"]),
        ("scifi", ["科幻", "scifi", "sci-fi"]),
        ("european", ["欧式", "城堡", "european", "castle"]),
        ("rustic", ["温馨", "田园", "木屋", "rustic", "cottage"]),
        ("modern", ["现代", "modern"]),
        ("fantasy", ["奇幻", "魔法", "fantasy", "wizard", "魔女"]),
        ("medieval", ["中世纪", "medieval", "要塞"]),
    ]
    for style, kws in file_hints:
        for kw in kws:
            if kw.lower() in blob or kw in stem:
                scores[style] = scores.get(style, 0.0) + 0.25
                break

    if shares.get("wood", 0) > 0.35 and shares.get("concrete", 0) < 0.05:
        scores["rustic"] = scores.get("rustic", 0.0) + 0.12
    if shares.get("sandstone", 0) > 0.25:
        scores["desert"] = scores.get("desert", 0.0) + 0.15
    if shares.get("nether", 0) > 0.2:
        scores["fantasy"] = scores.get("fantasy", 0.0) + 0.08

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    raw_top = ranked[0][1] if ranked else 0.0
    out: list[dict[str, Any]] = []
    for style, raw in ranked[:5]:
        if raw <= 0.02:
            continue
        conf = float(np.clip(raw / max(raw_top, 1e-6) * min(0.85, 0.35 + raw), 0.05, 0.85))
        out.append({"style": style, "confidence": round(conf, 3), "raw_score": round(raw, 4)})
    if not out:
        out.append({"style": "unknown", "confidence": 0.2, "raw_score": 0.0})
    out[0]["note"] = "材质占比启发式猜测，非标注真值；勿当作确定风格。"
    return out


# ---------------------------------------------------------------------------
# Knowledge index
# ---------------------------------------------------------------------------


def _kb_hits(result: dict[str, Any], kb_root: Path | None = None) -> list[dict[str, str]]:
    root = kb_root or Path(__file__).resolve().parents[2] / "docs" / "mc-knowledge"
    index_path = root / "index.json"
    if not index_path.is_file():
        return []
    try:
        entries = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(entries, list):
        return []

    keywords: list[str] = []
    rs = result.get("redstone") or {}
    if rs.get("total_redstone_blocks", 0) > 0:
        keywords.extend(["redstone", "circuit", "components"])
        inv = rs.get("inventory_nonzero") or {}
        if inv.get("observer"):
            keywords.append("observer")
        if inv.get("piston") or inv.get("sticky_piston"):
            keywords.append("piston")
        for h in rs.get("pattern_hints") or []:
            if h.get("id") == "observer_clock_like":
                keywords.append("clock")
    guesses = (result.get("style") or {}).get("guesses") or []
    style0 = guesses[0].get("style") if guesses else None
    if style0 == "desert":
        keywords.extend(["desert", "sandstone", "build"])
    if style0 in ("rustic", "medieval", "european"):
        keywords.extend(["build", "shape", "wood"])
    buckets = (result.get("style") or {}).get("palette_buckets") or {}
    if buckets.get("copper", 0) > 0:
        keywords.append("copper")
    if buckets.get("wood", 0) > max(buckets.get("stone", 0), 1):
        keywords.append("wood")
    families = (result.get("structure") or {}).get("families") or {}
    if families.get("stairs") or families.get("slabs") or families.get("walls"):
        keywords.extend(["stairs", "slabs", "walls", "build"])
    if buckets.get("nether", 0) > 0:
        keywords.append("nether")

    keywords = list(dict.fromkeys(keywords))
    if not keywords:
        keywords = ["build", "block"]

    scored: list[tuple[int, dict]] = []
    for e in entries:
        blob = " ".join(
            [
                str(e.get("id", "")),
                str(e.get("title", "")),
                str(e.get("path", "")),
                " ".join(e.get("tags") or []),
                str(e.get("summary", "")),
            ]
        ).lower()
        score = sum(1 for kw in keywords if kw.lower() in blob)
        tags = [str(t).lower() for t in (e.get("tags") or [])]
        for kw in keywords:
            if kw.lower() in tags:
                score += 1
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    out: list[dict[str, str]] = []
    for score, e in scored[:5]:
        out.append(
            {
                "path": f"docs/mc-knowledge/{e.get('path', '')}",
                "title": str(e.get("title", "")),
                "tags": ", ".join(e.get("tags") or []),
                "score": str(score),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_litematic(path: str | Path, *, kb_root: Path | None = None) -> dict[str, Any]:
    """Load full-region .litematic and return structured analysis dict."""
    path = Path(path)
    props_list = None
    try:
        voxels, palette, props_list, meta = load_litematic_detailed(path)
    except Exception:
        voxels, palette, meta = load_litematic(path)
        props_list = None
    sx, sy, sz = (int(voxels.shape[0]), int(voxels.shape[1]), int(voxels.shape[2]))
    air_ids = _air_ids(palette)
    if air_ids:
        solid = ~np.isin(voxels, list(air_ids))
    else:
        solid = voxels != 0

    volume = sx * sy * sz
    non_air = int(solid.sum())
    density = float(non_air) / float(volume) if volume else 0.0

    counts: Counter[str] = Counter()
    for pid in np.unique(voxels):
        pid_i = int(pid)
        name = _short(palette[pid_i]) if 0 <= pid_i < len(palette) else f"unknown_{pid_i}"
        if name in _AIR:
            continue
        counts[name] += int((voxels == pid_i).sum())

    unique_blocks = len(counts)
    top_n = counts.most_common(25)

    n_comp, largest, sizes = _connected_components_solid(solid)
    hollow = _hollow_score(solid)
    floors = _floor_guess(solid)
    sym = _axis_symmetry(solid)
    families = _structural_families(counts)

    buckets = _palette_buckets(counts)
    guesses = _guess_styles(buckets, families, path.stem)

    redstone = analyze_redstone(
        voxels, palette, props_list,
        project_root=Path(__file__).resolve().parents[2],
    )

    result: dict[str, Any] = {
        "overview": {
            "file": path.name,
            "source": str(path),
            "schematic_name": meta.get("name"),
            "author": meta.get("author"),
            "region": meta.get("region"),
            "size": {"x": sx, "y": sy, "z": sz},
            "volume": volume,
            "non_air": non_air,
            "unique_block_types": unique_blocks,
            "density": round(density, 4),
            "palette_len": len(palette),
        },
        "structure": {
            "solid_ratio": round(density, 4),
            "air_ratio": round(1.0 - density, 4),
            "hollow": hollow,
            "floors": floors,
            "components": {
                "count": n_comp,
                "largest": largest,
                "sizes_top": sizes,
                "largest_frac_of_solid": round(largest / non_air, 4) if non_air else 0.0,
            },
            "families": families,
            "symmetry": sym,
            "limits": "结构项均为体素启发式，不能识别房间语义、承重或真实楼层划分。",
        },
        "style": {
            "top_blocks": [{"block": b, "count": c} for b, c in top_n],
            "palette_buckets": buckets,
            "guesses": guesses,
            "limits": "风格为材质占比+文件名弱提示的猜测，附 confidence，非数据集标注。",
        },
        "redstone": redstone,
        "knowledge_hits": [],
        "phase": 1,
        "disclaimer": "Phase 1：只做读懂报告（规则/图），无训练、无 tick 模拟、无自动复刻。",
    }
    result["knowledge_hits"] = _kb_hits(result, kb_root=kb_root)
    return result


def report_to_markdown(result: dict[str, Any]) -> str:
    """Chinese human-readable markdown report."""
    ov = result.get("overview") or {}
    st = result.get("structure") or {}
    style = result.get("style") or {}
    rs = result.get("redstone") or {}
    size = ov.get("size") or {}
    lines: list[str] = []
    lines.append(f"# 投影分析报告：{ov.get('file', '')}")
    lines.append("")
    lines.append(f"> {result.get('disclaimer', '')}")
    lines.append("")
    lines.append("## A. 概览")
    lines.append("")
    lines.append(f"- **文件**: `{ov.get('file')}`")
    if ov.get("schematic_name"):
        lines.append(f"- **原理图名**: {ov.get('schematic_name')}")
    if ov.get("author"):
        lines.append(f"- **作者**: {ov.get('author')}")
    lines.append(
        f"- **区域尺寸 (X,Y,Z)**: {size.get('x')} × {size.get('y')} × {size.get('z')} "
        f"（体积 {ov.get('volume')}）"
    )
    lines.append(f"- **非空气方块**: {ov.get('non_air')}")
    lines.append(f"- **方块种类（去空气）**: {ov.get('unique_block_types')}")
    lines.append(f"- **包围盒密度**: {ov.get('density')} （非空气/体积）")
    lines.append(f"- **调色板长度**: {ov.get('palette_len')}")
    lines.append("")

    lines.append("## B. 结构")
    lines.append("")
    lines.append(f"- **实心占比**: {st.get('solid_ratio')}；**空气占比**: {st.get('air_ratio')}")
    hollow = st.get("hollow") or {}
    lines.append(
        f"- **空心启发分 hollow_score**: {hollow.get('hollow_score')} "
        f"（内部空气占比≈{hollow.get('interior_air_frac')}；"
        f"壳层实心数={hollow.get('exterior_layer_solid_count')}）"
    )
    lines.append(f"  - _{hollow.get('note', '')}_")
    floors = st.get("floors") or {}
    lines.append(f"- **粗估楼层数**: {floors.get('floor_guess')}（Y 峰值 {floors.get('y_peaks')}）")
    lines.append(f"  - _{floors.get('note', '')}_")
    comp = st.get("components") or {}
    lines.append(
        f"- **实心连通分量 (6-邻接)**: {comp.get('count')} 个；"
        f"最大 {comp.get('largest')} "
        f"（占实心 {comp.get('largest_frac_of_solid')}）"
    )
    if comp.get("sizes_top"):
        lines.append(f"  - 分量大小 Top: {comp.get('sizes_top')}")
    fam = st.get("families") or {}
    lines.append("- **结构族计数**（按方块名子串）:")
    any_fam = False
    for k, v in sorted(fam.items(), key=lambda x: -x[1]):
        if v:
            any_fam = True
            lines.append(f"  - `{k}`: {v}")
    if not any_fam:
        lines.append("  - （无明显楼梯/台阶/门等结构族）")
    sym = st.get("symmetry") or {}
    lines.append(
        f"- **轴向对称分 (IoU)**: X={sym.get('symmetry_x')}, "
        f"Z={sym.get('symmetry_z')}, Y={sym.get('symmetry_y')}"
    )
    lines.append(f"- **局限**: {st.get('limits', '')}")
    lines.append("")

    lines.append("## C. 美术 / 材质风格")
    lines.append("")
    lines.append("- **Top 方块**（排除空气）:")
    lines.append("")
    lines.append("| 方块 | 数量 |")
    lines.append("|------|------|")
    for row in (style.get("top_blocks") or [])[:15]:
        lines.append(f"| `{row['block']}` | {row['count']} |")
    lines.append("")
    lines.append("- **材质桶**:")
    buckets = style.get("palette_buckets") or {}
    for k, v in sorted(buckets.items(), key=lambda x: -x[1]):
        if v:
            lines.append(f"  - `{k}`: {v}")
    lines.append("- **风格猜测**（含置信度，非定论）:")
    for g in style.get("guesses") or []:
        lines.append(
            f"  - **{g.get('style')}** — confidence={g.get('confidence')} "
            f"（raw={g.get('raw_score')}）"
        )
        if g.get("note"):
            lines.append(f"    - _{g['note']}_")
    lines.append(f"- **局限**: {style.get('limits', '')}")
    lines.append("")

    lines.extend(redstone_to_markdown_sections(rs))

    lines.append("## E. 知识库挂接")
    lines.append("")
    hits = result.get("knowledge_hits") or []
    if not hits:
        lines.append("- （未命中或 `docs/mc-knowledge/index.json` 不可用）")
    else:
        lines.append("- 关键词弱匹配到的相关文档（最多 5 条）:")
        for h in hits:
            lines.append(
                f"  - [{h.get('title')}]({h.get('path')}) — tags: {h.get('tags')} (score={h.get('score')})"
            )
    lines.append("")
    lines.append("---")
    lines.append(f"_phase={result.get('phase', 1)}_")
    lines.append("")
    return "\n".join(lines)
