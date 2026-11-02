# -*- coding: utf-8 -*-
"""Material bill-of-materials for generated voxels / litematic (Nova-inspired).

Reimplements the *idea* of a builder-facing material list (counts + 箱盒组个 +
CSV/TXT). Does not copy Litematica-Nova source. Aligns with Java 26.3 export
defaults used by this project.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from src.app.block_zh_cn import short_name, zh_name
from src.app.sample_runner import count_blocks, load_voxel_npz
from src.utils import load_palette

# Nested Chinese builder units (common projection convention)
STACK = 64          # 组
SHULKER = 27 * STACK  # 盒 = 1728
CHEST = 27 * SHULKER  # 箱 = 46656

# Blocks that are not placeable inventory items (count in structure note only)
_NON_ITEM_SHORT = {
    "air",
    "cave_air",
    "void_air",
    "piston_head",
    "moving_piston",
    "fire",
    "soul_fire",
    "water",
    "lava",
    "bubble_column",
    "light",
    "barrier",
    "structure_void",
}


@dataclass(frozen=True)
class StackBreakdown:
    chests: int
    boxes: int
    stacks: int
    ones: int
    total: int

    def format_zh(self) -> str:
        parts: list[str] = []
        if self.chests:
            parts.append(f"{self.chests}箱")
        if self.boxes:
            parts.append(f"{self.boxes}盒")
        if self.stacks:
            parts.append(f"{self.stacks}组")
        if self.ones or not parts:
            parts.append(f"{self.ones}个")
        return "".join(parts)


def breakdown_count(n: int, stack_size: int = STACK) -> StackBreakdown:
    """Split n into 箱/盒/组/个. Uses SHULKER/CHEST nesting; group size = stack_size."""
    n = max(0, int(n))
    stack_size = max(1, int(stack_size))
    box = 27 * stack_size
    chest = 27 * box
    chests, rem = divmod(n, chest)
    boxes, rem = divmod(rem, box)
    stacks, ones = divmod(rem, stack_size)
    return StackBreakdown(chests, boxes, stacks, ones, n)


def stack_size_for(short: str) -> int:
    """Best-effort max stack; architecture blocks default to 64."""
    s = short.lower()
    if s.endswith("_boat") or s.endswith("_minecart") or s in {
        "saddle", "elytra", "shield", "totem_of_undying",
    }:
        return 1
    if s.endswith("_bucket") or s in {"egg", "snowball", "ender_pearl"}:
        return 16
    if s in {"toast",}:  # placeholder
        return 64
    return STACK


def is_countable_item(full_name: str) -> bool:
    short = short_name(full_name).lower()
    if short in _NON_ITEM_SHORT:
        return False
    if short.endswith("_sapling"):
        return True
    return True


@dataclass
class BomRow:
    block_id: int
    name: str
    short: str
    zh: str
    count: int
    stack_size: int
    breakdown: StackBreakdown
    countable: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.block_id,
            "name": self.name,
            "short": self.short,
            "zh": self.zh,
            "count": self.count,
            "stack_size": self.stack_size,
            "箱": self.breakdown.chests,
            "盒": self.breakdown.boxes,
            "组": self.breakdown.stacks,
            "个": self.breakdown.ones,
            "箱盒组个": self.breakdown.format_zh(),
            "countable": self.countable,
        }


def build_bom(
    voxels: np.ndarray,
    palette: dict[int, str],
) -> list[BomRow]:
    rows_raw = count_blocks(voxels, palette)
    out: list[BomRow] = []
    for r in rows_raw:
        name = str(r["name"])
        short = str(r["short"])
        cnt = int(r["count"])
        countable = is_countable_item(name)
        ss = stack_size_for(short) if countable else STACK
        bd = breakdown_count(cnt, ss)
        out.append(
            BomRow(
                block_id=int(r["id"]),
                name=name,
                short=short,
                zh=zh_name(name),
                count=cnt,
                stack_size=ss,
                breakdown=bd,
                countable=countable,
            )
        )
    return out


def bom_totals(rows: Iterable[BomRow]) -> dict[str, int]:
    rows = list(rows)
    return {
        "unique_blocks": len(rows),
        "total_blocks": sum(r.count for r in rows),
        "countable_blocks": sum(r.count for r in rows if r.countable),
        "non_item_blocks": sum(r.count for r in rows if not r.countable),
    }


def format_bom_markdown(
    rows: list[BomRow],
    *,
    title: str = "材料清单",
    source: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    totals = bom_totals(rows)
    lines: list[str] = [f"# {title}", ""]
    if source:
        lines.append(f"- 来源：`{source}`")
    lines.append(f"- 种类：{totals['unique_blocks']}")
    lines.append(f"- 非空气方块：{totals['total_blocks']}")
    if totals["non_item_blocks"]:
        lines.append(f"- 非物品/不计料提示：{totals['non_item_blocks']}（见 countable=false）")
    lines.append("- 拆分约定：1组=64，1盒=27组=1728，1箱=27盒=46656")
    lines.append("- 目标版本对齐：导出默认 Java **26.3**（与 Nova 材料映射同代）")
    if extra:
        for k, v in extra.items():
            lines.append(f"- {k}：{v}")
    lines.extend(["", "| 中文名 | 英文 id | 数量 | 箱盒组个 | 可计料 |", "|---|---|---:|---|---|"])
    for r in rows:
        flag = "是" if r.countable else "否"
        lines.append(
            f"| {r.zh} | `{r.short}` | {r.count} | {r.breakdown.format_zh()} | {flag} |"
        )
    lines.append("")
    lines.append("> 完整图标材料表 / 按层 GUI 请用 [Litematica-Nova](https://github.com/LitematicaViewer/Litematica-Nova) 打开 `.litematic`。")
    lines.append("")
    return "\n".join(lines)


def format_bom_txt(rows: list[BomRow], *, source: str | None = None) -> str:
    totals = bom_totals(rows)
    lines = [
        "材料清单 (BOM)",
        f"source={source or ''}",
        f"unique={totals['unique_blocks']} total={totals['total_blocks']}",
        "unit: 箱=46656 盒=1728 组=64 个=1",
        "-" * 48,
    ]
    for r in rows:
        lines.append(f"{r.zh}\t{r.short}\t{r.count}\t{r.breakdown.format_zh()}")
    lines.append("")
    return "\n".join(lines)


def write_bom_csv(rows: list[BomRow], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "zh", "short", "name", "id", "count",
        "箱", "盒", "组", "个", "箱盒组个", "stack_size", "countable",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            d = r.as_dict()
            w.writerow({k: d.get(k) for k in fieldnames})
    return path


def write_bom_bundle(
    rows: list[BomRow],
    out_dir: Path,
    *,
    stem: str,
    source: str | None = None,
    extra: dict[str, Any] | None = None,
    write_csv: bool = True,
    write_json: bool = True,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    md = out_dir / f"{stem}_BOM.md"
    md.write_text(format_bom_markdown(rows, source=source, extra=extra), encoding="utf-8")
    paths["md"] = md
    txt = out_dir / f"{stem}_BOM.txt"
    txt.write_text(format_bom_txt(rows, source=source), encoding="utf-8")
    paths["txt"] = txt
    if write_csv:
        paths["csv"] = write_bom_csv(rows, out_dir / f"{stem}_BOM.csv")
    if write_json:
        payload = {
            "source": source,
            "totals": bom_totals(rows),
            "units": {"组": STACK, "盒": SHULKER, "箱": CHEST},
            "rows": [r.as_dict() for r in rows],
            "extra": extra or {},
        }
        jp = out_dir / f"{stem}_BOM.json"
        jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        paths["json"] = jp
    return paths


def load_voxels_any(path: Path) -> tuple[np.ndarray, dict | None]:
    """Load voxels from .npz / .npy / .litematic. Returns (voxels, meta_or_none)."""
    path = Path(path)
    if path.suffix.lower() == ".litematic":
        from src.data.litematic import load_litematic

        voxels, names, meta = load_litematic(path)
        return np.asarray(voxels, dtype=np.int16), {
            "litematic_names": list(names),
            "meta": meta,
        }
    if path.suffix.lower() == ".npy":
        return np.asarray(np.load(path), dtype=np.int16), None
    return load_voxel_npz(path), None



def write_export_sidecars(
    voxels: np.ndarray,
    palette: dict[int, str],
    litematic_path: Path | str,
    *,
    with_bom: bool = True,
    with_layers: bool = False,
    source: str | None = None,
    extra: dict[str, Any] | None = None,
    materials_subdir: str = "materials",
) -> dict[str, Any]:
    """Write BOM (+ optional Y-layer previews) next to an exported .litematic.

    Layout (same as CLI ``export_litematic.py --materials``)::

        <litematic_dir>/materials/<stem>/<stem>_BOM.md|.txt|.csv|.json
        <litematic_dir>/materials/<stem>/layers/   # if with_layers

    Returns a dict with keys: mat_dir, bom_paths, layers, skipped.
    Safe no-op when with_bom is False (returns skipped=True).
    """
    result: dict[str, Any] = {
        "mat_dir": None,
        "bom_paths": {},
        "layers": None,
        "skipped": not with_bom,
    }
    if not with_bom:
        return result

    lit = Path(litematic_path)
    stem = lit.stem if lit.suffix.lower() == ".litematic" else lit.stem
    mat_dir = lit.parent / materials_subdir / stem
    mat_dir.mkdir(parents=True, exist_ok=True)
    result["mat_dir"] = mat_dir

    rows = build_bom(voxels, palette)
    extra_payload = dict(extra or {})
    extra_payload.setdefault("litematic", str(lit))
    paths = write_bom_bundle(
        rows,
        mat_dir,
        stem=stem,
        source=source or str(lit),
        extra=extra_payload,
    )
    result["bom_paths"] = {k: str(v) for k, v in paths.items()}
    result["totals"] = bom_totals(rows)

    if with_layers:
        from src.app.layer_preview import write_layer_previews

        layer_info = write_layer_previews(
            voxels, palette, mat_dir / "layers", stem=stem
        )
        result["layers"] = layer_info

    return result


def bom_from_path(
    path: Path,
    palette: dict[int, str] | None = None,
    palette_path: Path | None = None,
) -> tuple[list[BomRow], dict[str, Any]]:
    path = Path(path)
    voxels, meta = load_voxels_any(path)
    info: dict[str, Any] = {"source": str(path), "shape": list(voxels.shape)}
    if meta and "litematic_names" in meta:
        # Remap: litematic voxels are indices into file palette names
        names: list[str] = list(meta["litematic_names"])
        file_palette = {i: n for i, n in enumerate(names)}
        rows = build_bom(voxels, file_palette)
        info["palette_source"] = "litematic"
        m = meta.get("meta") if isinstance(meta, dict) else None
        if isinstance(m, dict):
            info["meta"] = {
                "name": m.get("name"),
                "author": m.get("author"),
                "size": m.get("size"),
            }
        return rows, info

    if palette is None:
        from src.utils import load_config

        root = Path(__file__).resolve().parents[2]
        cfg = load_config(root / "configs/default.yaml")
        pp = Path(palette_path) if palette_path else root / cfg["data"]["palette_path"]
        palette = load_palette(pp)
        info["palette_path"] = str(pp)
    rows = build_bom(voxels, palette)
    info["palette_source"] = "project"
    return rows, info