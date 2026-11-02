# -*- coding: utf-8 -*-
"""Load vanilla block textures from local Minecraft install at runtime.

Does NOT vendor asset dumps into git. Looks for client jars under common
PCL / launcher paths, extracts `assets/minecraft/textures/block/*.png` into
a project-local cache (`outputs/cache/block_textures/`), and exposes:

- average RGBA for voxel face coloring (upgrade over hard-coded palette)
- PIL images for hotbar icons

Graceful FALLBACK when jar/assets missing — callers keep using mc_colors.
"""
from __future__ import annotations

import json
import os
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CACHE_DIR = _PROJECT_ROOT / "outputs" / "cache" / "block_textures"
_META_PATH = _CACHE_DIR / "_source.json"

_TEXTURE_ALIAS: dict[str, str] = {
    "grass_block": "grass_block_top",
    "dirt_path": "dirt_path_top",
    "oak_log": "oak_log",
    "spruce_log": "spruce_log",
    "stripped_oak_log": "stripped_oak_log",
    "glass_pane": "glass",
    "oak_stairs": "oak_planks",
    "oak_slab": "oak_planks",
    "oak_fence": "oak_planks",
    "oak_fence_gate": "oak_planks",
    "oak_door": "oak_door_bottom",
    "oak_trapdoor": "oak_trapdoor",
    "spruce_stairs": "spruce_planks",
    "spruce_slab": "spruce_planks",
    "spruce_fence": "spruce_planks",
    "spruce_door": "spruce_door_bottom",
    "dark_oak_stairs": "dark_oak_planks",
    "dark_oak_slab": "dark_oak_planks",
    "dark_oak_fence": "dark_oak_planks",
    "dark_oak_door": "dark_oak_door_bottom",
    "birch_stairs": "birch_planks",
    "birch_slab": "birch_planks",
    "stone_brick_stairs": "stone_bricks",
    "stone_brick_slab": "stone_bricks",
    "cobblestone_stairs": "cobblestone",
    "cobblestone_slab": "cobblestone",
    "cobblestone_wall": "cobblestone",
    "sandstone_stairs": "sandstone",
    "sandstone_wall": "sandstone",
    "smooth_sandstone": "sandstone_top",
    "smooth_stone_slab": "smooth_stone",
    "crafting_table": "crafting_table_front",
    "furnace": "furnace_front",
    "chest": "oak_planks",
    "barrel": "barrel_side",
}

_WOODISH = (
    "oak", "spruce", "birch", "jungle", "acacia", "dark_oak",
    "mangrove", "cherry", "bamboo", "crimson", "warped", "pale_oak",
)


def short_name(full: str) -> str:
    if ":" in full:
        return full.split(":", 1)[1]
    return full


def _candidate_jars() -> list[Path]:
    out: list[Path] = []
    env_jar = os.environ.get("MC_ASSETS_JAR") or os.environ.get("MC_CLIENT_JAR")
    if env_jar:
        out.append(Path(env_jar))
    env_dir = os.environ.get("MC_TEXTURES_DIR")
    if env_dir:
        out.append(Path(env_dir))

    home = Path.home()
    desktop_candidates = [
        home / "Desktop" / "PCL 下载" / ".minecraft",
        home / "Desktop" / "PCL" / ".minecraft",
        home / "AppData" / "Roaming" / ".minecraft",
    ]
    desk = home / "Desktop"
    if desk.is_dir():
        try:
            for child in desk.iterdir():
                if "PCL" in child.name.upper():
                    mc = child / ".minecraft"
                    if mc.is_dir():
                        desktop_candidates.append(mc)
        except OSError:
            pass

    seen: set[str] = set()
    for mc_root in desktop_candidates:
        key = str(mc_root)
        if key in seen:
            continue
        seen.add(key)
        if not mc_root.is_dir():
            continue
        versions = mc_root / "versions"
        jars: list[Path] = []
        if versions.is_dir():
            try:
                for ver_dir in versions.iterdir():
                    if not ver_dir.is_dir():
                        continue
                    jar = ver_dir / f"{ver_dir.name}.jar"
                    if jar.is_file() and jar.stat().st_size > 1_000_000:
                        jars.append(jar)
                    for alt in ver_dir.glob("*.jar"):
                        if alt.is_file() and alt.stat().st_size > 1_000_000:
                            jars.append(alt)
            except OSError:
                pass

        def _rank(p: Path) -> tuple[int, int]:
            n = p.name.lower()
            score = 0
            if "fabric" in n:
                score += 30
            if "26." in n or "1.21" in n:
                score += 20
            if "1.20" in n:
                score += 10
            try:
                sz = p.stat().st_size
            except OSError:
                sz = 0
            return (-score, -sz)

        jars = sorted(set(jars), key=_rank)
        out.extend(jars)
        block_dir = mc_root / "assets" / "minecraft" / "textures" / "block"
        if block_dir.is_dir():
            out.append(block_dir)

    local = _PROJECT_ROOT / "data" / "mc_block_textures"
    if local.is_dir():
        out.append(local)
    return out


def _is_jar(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".jar"


def _is_texture_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if (path / "oak_planks.png").exists() or (path / "stone.png").exists():
        return True
    return any(path.glob("*.png"))


def discover_texture_source() -> dict[str, Any]:
    for cand in _candidate_jars():
        try:
            if _is_jar(cand):
                with zipfile.ZipFile(cand) as zf:
                    names = zf.namelist()
                    n_tex = sum(
                        1
                        for n in names
                        if n.startswith("assets/minecraft/textures/block/") and n.endswith(".png")
                    )
                    if n_tex > 50:
                        return {
                            "ok": True,
                            "kind": "jar",
                            "path": str(cand),
                            "count": n_tex,
                            "note": f"jar:{cand.name} ({n_tex} block pngs)",
                        }
            elif _is_texture_dir(cand):
                n_tex = len(list(cand.glob("*.png")))
                return {
                    "ok": True,
                    "kind": "dir",
                    "path": str(cand),
                    "count": n_tex,
                    "note": f"dir:{cand.name} ({n_tex} pngs)",
                }
        except Exception:
            continue
    return {
        "ok": False,
        "kind": "none",
        "path": "",
        "count": 0,
        "note": "FALLBACK: no Minecraft jar/textures found",
    }


def _ensure_cache_from_jar(jar: Path, stems: list[str] | None = None) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"source": str(jar), "kind": "jar"}
    _META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    prefix = "assets/minecraft/textures/block/"
    with zipfile.ZipFile(jar) as zf:
        names = [
            n
            for n in zf.namelist()
            if n.startswith(prefix) and n.endswith(".png") and n.count("/") == 4
        ]
        if stems:
            want = {f"{prefix}{s}.png" for s in stems}
            filtered = [n for n in names if n in want]
            if filtered:
                names = filtered
        for n in names:
            dest = _CACHE_DIR / Path(n).name
            if dest.exists() and dest.stat().st_size > 0:
                continue
            dest.write_bytes(zf.read(n))
    return _CACHE_DIR


def _ensure_cache_from_dir(src: Path) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"source": str(src), "kind": "dir"}
    _META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    for png in src.glob("*.png"):
        dest = _CACHE_DIR / png.name
        if dest.exists():
            continue
        try:
            dest.write_bytes(png.read_bytes())
        except OSError:
            pass
    return _CACHE_DIR


_SOURCE: dict[str, Any] | None = None
_READY = False


def ensure_textures(stems: list[str] | None = None) -> dict[str, Any]:
    global _SOURCE, _READY
    if _READY and _SOURCE is not None and _SOURCE.get("ok"):
        if stems and _SOURCE.get("kind") == "jar" and _SOURCE.get("path"):
            missing = [s for s in stems if not (_CACHE_DIR / f"{s}.png").exists()]
            if missing:
                try:
                    _ensure_cache_from_jar(Path(_SOURCE["path"]), missing)
                except Exception:
                    pass
        return _SOURCE

    info = discover_texture_source()
    _SOURCE = info
    if not info.get("ok"):
        _READY = True
        return info
    try:
        src = Path(info["path"])
        marker = _CACHE_DIR / ".jar_synced"
        if info["kind"] == "jar":
            warm = list(
                dict.fromkeys(
                    (stems or [])
                    + [
                        "oak_planks", "oak_log", "spruce_planks", "stone",
                        "cobblestone", "stone_bricks", "bricks", "glass",
                        "dirt", "grass_block_top", "sandstone",
                        "white_concrete", "black_concrete",
                        "crafting_table_front", "furnace_front", "barrel_side",
                    ]
                )
            )
            missing = [s for s in warm if not (_CACHE_DIR / f"{s}.png").exists()]
            if marker.exists() and not missing:
                pass  # 缓存已完整同步，跳过打开 jar（省约 1.3s 启动）
            else:
                _ensure_cache_from_jar(src, warm)
                _ensure_cache_from_jar(src, None)
                marker.write_text("ok", encoding="utf-8")
        else:
            _ensure_cache_from_dir(src)
        info["cache"] = str(_CACHE_DIR)
        info["cached_count"] = len(list(_CACHE_DIR.glob("*.png")))
        _READY = True
    except Exception as exc:  # noqa: BLE001
        info = {
            "ok": False,
            "kind": "error",
            "path": info.get("path", ""),
            "count": 0,
            "note": f"FALLBACK: extract failed ({exc})",
        }
        _SOURCE = info
        _READY = True
    return info


def texture_stem_for_block(full_or_short: str) -> str:
    name = short_name(full_or_short).lower()
    if name in _TEXTURE_ALIAS:
        return _TEXTURE_ALIAS[name]
    for suf, repl_planks in (
        ("_stairs", True),
        ("_slab", True),
        ("_wall", False),
        ("_fence_gate", True),
        ("_fence", True),
        ("_pressure_plate", True),
        ("_button", True),
    ):
        if name.endswith(suf):
            base = name[: -len(suf)]
            if repl_planks and any(w in base for w in _WOODISH):
                return base + "_planks"
            return base
    if name.endswith("_door"):
        return name + "_bottom"
    if name.endswith("_sign") or name.endswith("_hanging_sign") or name.endswith("_wall_sign"):
        base = name.replace("_hanging_sign", "").replace("_wall_sign", "").replace("_sign", "")
        if any(w in base for w in _WOODISH):
            return base + "_planks"
    return name


def _png_path(stem: str) -> Path | None:
    ensure_textures([stem])
    p = _CACHE_DIR / f"{stem}.png"
    if p.exists():
        return p
    return None


@lru_cache(maxsize=512)
def average_rgba(full_or_short: str) -> tuple[float, float, float, float] | None:
    if Image is None:
        return None
    stem = texture_stem_for_block(full_or_short)
    path = _png_path(stem) or _png_path(short_name(full_or_short).lower())
    if path is None:
        return None
    try:
        im = Image.open(path).convert("RGBA")
        im = im.resize((8, 8), Image.Resampling.BOX)
        pixels = list(im.getdata())
        rs = gs = bs = 0.0
        n = 0
        for r, g, b, a in pixels:
            if a < 16:
                continue
            rs += r
            gs += g
            bs += b
            n += 1
        if n == 0:
            return None
        alpha = 1.0
        name = short_name(full_or_short).lower()
        if "glass" in name:
            alpha = 0.38
        elif "leaves" in name:
            alpha = 0.90
        return (rs / n / 255.0, gs / n / 255.0, bs / n / 255.0, alpha)
    except Exception:
        return None


@lru_cache(maxsize=256)
def load_pil_icon(full_or_short: str, size: int = 32) -> Any | None:
    if Image is None:
        return None
    stem = texture_stem_for_block(full_or_short)
    path = _png_path(stem) or _png_path(short_name(full_or_short).lower())
    if path is None:
        return None
    try:
        im = Image.open(path).convert("RGBA")
        return im.resize((size, size), Image.Resampling.NEAREST)
    except Exception:
        return None


def texture_status_line() -> str:
    info = ensure_textures()
    if info.get("ok"):
        return f"贴图: {info.get('note', 'ok')} cache={info.get('cached_count', '?')}"
    return str(info.get("note") or "FALLBACK")


def clear_caches() -> None:
    average_rgba.cache_clear()
    load_pil_icon.cache_clear()
