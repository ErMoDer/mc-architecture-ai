# -*- coding: utf-8 -*-
"""Generation strategies beyond raw ConditionalVAE sample.

Primary: similar_scaffold — retrieve reference from feature_index, build
shell/floors scaffold from its 32^3 skeleton, paint materials, look_harden.
Fallback: rule_scaffold — procedural box shell + floors + roof, then look_harden.

VAE is NOT the structure source here (continue-train from ~ep900 collapses;
VAE+look_harden still looks like painted mush). Optional sparse VAE material
fill can be enabled but defaults off.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.app.look_harden import look_harden, style_token_list
from src.app.scaffold_materials import resolve_role_materials, role_ids_list
from src.app.structure_constraints import (
    SCAFFOLD_THRESHOLDS,
    apply_structure_constraints,
    check_structure,
)
from src.utils import load_config, load_palette, set_seed

STRATEGIES = ("vae_look", "similar_scaffold", "rule_scaffold")

# Path/id keywords when mapped_style is noisy (hack337 batch often labeled chinese).
_STYLE_PATH_KEYWORDS: dict[str, list[str]] = {
    "medieval": ["medieval", "castle", "manor", "cottage", "keep", "gothic", "farmhouse", "stonebrick", "stone_brick"],
    "european": ["european", "victorian", "french", "german", "dutch", "tudor", "baroque", "townhouse", "chalet"],
    "chinese": ["chinese", "zhong", "siheyuan", "pagoda", "hutong", "tingyuan", "fangzi"],
    "japanese": ["japanese", "torii", "shoji", "minka", "engawa", "tatami"],
    "modern": ["modern", "concrete", "apartment", "condo", "minimal", "glasshouse"],
    "rustic": [
        "rustic", "cabin", "barn", "log_cabin", "wooden_house", "farmhouse",
        "田园", "农舍", "木屋", "乡村",
    ],
    "fantasy": [
        "fantasy", "elf", "wizard", "mage", "dragon", "fairy",
        "mushroom", "奇幻", "精灵", "魔法",
    ],
    "industrial": ["industrial", "factory", "warehouse", "foundry", "steam"],
    "desert": ["desert", "adobe", "sahara", "sandstone", "oasis"],
    "scifi": ["scifi", "sci-fi", "futur", "space", "cyber"],
    "western": ["western", "saloon", "cowboy", "frontier"],
    "unknown": ["house", "home", "cabin"],
}

_BUILDING_BOOST = (
    "house", "home", "cabin", "cottage", "manor", "villa", "tower", "hall", "shop",
    "base", "starter", "residence", "住宅", "小屋", "别墅", "民居", "宅",
)
# Strong demote: Hack337 challenge / farm / machine spam that path-keywords can otherwise promote.
_BUILDING_PENALTY = (
    "farm", "spawner", "portal", "redstone", "xp_", "gold_farm", "crop", "wheat",
    "zombie_farm", "shulker", "sorting", "loader", "flag", "warship", "debug",
    "challenge", "mcbuildchallenge", "buildchallenge", "pyramid", "breeder",
    "drop%", "drop_", "decorative_wall", "decorative%20wall", "stash",
    "trading_hall", "trading%20hall", "villager_breeder", "mob_farm", "iron_farm",
    "afk", "xp farm", "goldfarm", "raid_farm", "guardian",
    # public_production / tech dumps mislabeled as industrial residential
    "kelp", "smelter", "supersmelter", "super_smelter", "smoker", "bonemeal",
    "bone%20meal", "bone_meal", "coral_farm", "pickle_farm", "lava_farm",
    "rabbit_farm", "slime_farm", "goat_horn", "piglin_trading", "kill_chamber",
    "carpet_duper", "item_sorter", "public_production",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _short(name: str) -> str:
    n = str(name).replace("minecraft:", "")
    if n.startswith("block.minecraft."):
        n = n[len("block.minecraft.") :]
    return n


def _resolve_material_ids(
    palette: dict[int, str],
    remap_targets: list[str] | None,
    style: str | None,
    top_blocks: list[dict[str, Any]] | None = None,
) -> tuple[int, int, dict[str, Any]]:
    """Pick wall_id / floor_id plus full role materials (compat wrapper)."""
    roles, info = resolve_role_materials(
        palette,
        style,
        top_blocks=top_blocks,
        remap_targets=remap_targets,
    )
    return int(roles["wall"]), int(roles["floor"]), info





def _dilate_mask(fp: np.ndarray, radius: int = 1) -> np.ndarray:
    """Chebyshev dilate of a 2D bool mask."""
    fp = np.asarray(fp, dtype=bool)
    if radius <= 0 or not fp.any():
        return fp.copy()
    h, w = fp.shape
    out = fp.copy()
    xs, zs = np.where(fp)
    r = int(radius)
    for x, z in zip(xs.tolist(), zs.tolist()):
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                xx, zz = x + dx, z + dz
                if 0 <= xx < h and 0 <= zz < w:
                    out[xx, zz] = True
    return out


def _ring_floor_mask(
    fp: np.ndarray,
    *,
    depth: int = 2,
    keep_cross: bool = False,
) -> np.ndarray:
    """Walkable ring (+ optional cross corridor) leaving a large open room in the middle.

    Distance-from-perimeter band (not dilate-then-fallback-to-full), so small and
    large footprints both keep an open center instead of solid crates.
    """
    from collections import deque

    fp = np.asarray(fp, dtype=bool)
    if not fp.any():
        return fp.copy()
    h, w = fp.shape
    peri = _perimeter_mask(fp)
    dist = np.full((h, w), -1, dtype=np.int16)
    q: deque[tuple[int, int]] = deque()
    xs_p, zs_p = np.where(peri)
    for x, z in zip(xs_p.tolist(), zs_p.tolist()):
        dist[x, z] = 0
        q.append((x, z))
    while q:
        x, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, zz = x + dx, z + dz
            if 0 <= xx < h and 0 <= zz < w and fp[xx, zz] and dist[xx, zz] < 0:
                dist[xx, zz] = int(dist[x, z]) + 1
                q.append((xx, zz))
    # Cap depth so at least ~25% of footprint stays open when possible
    xs, zs = np.where(fp)
    max_d = int(dist[fp].max()) if fp.any() else 0
    d = max(1, int(depth))
    if max_d >= 2:
        # leave at least the innermost ring open
        d = min(d, max(1, max_d - 1))
    ring = fp & (dist >= 0) & (dist <= d)
    open_n = int((fp & (dist > d)).sum())
    if open_n < max(9, int(0.2 * int(fp.sum()))) and max_d >= 2:
        d = 1
        ring = fp & (dist >= 0) & (dist <= d)
        open_n = int((fp & (dist > d)).sum())
    # Cross corridor OFF by default: X-beams read as scaffolds, not house floors.
    # If explicitly enabled, only on very large open cores.
    if keep_cross and open_n >= 48 and max_d >= 5:
        cx = int(round(float(xs.mean())))
        cz = int(round(float(zs.mean())))
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(x - cx) <= 0 or abs(z - cz) <= 0:
                ring[x, z] = True
        ring &= fp
    # Ultra-thin footprints: keep whatever ring we have (may be near-full)
    if int(ring.sum()) < max(8, int(0.12 * int(fp.sum()))):
        ring = _dilate_mask(peri, 1) & fp
    return ring


def _perimeter_mask(fp: np.ndarray) -> np.ndarray:
    fp = np.asarray(fp, dtype=bool)
    peri = np.zeros_like(fp)
    h, w = fp.shape
    for x in range(h):
        for z in range(w):
            if not fp[x, z]:
                continue
            if x == 0 or z == 0 or x == h - 1 or z == w - 1:
                peri[x, z] = True
                continue
            if not (fp[x - 1, z] and fp[x + 1, z] and fp[x, z - 1] and fp[x, z + 1]):
                peri[x, z] = True
    return peri


def _fill_footprint_holes(fp: np.ndarray) -> np.ndarray:
    """Fill interior holes / sparse outline rings so roof deck is coherent.

    Flood-fill from border through empty cells; remaining False = enclosed voids → True.
    Also dilate once then erode (morph close) for thin Victorian outline gaps.
    """
    fp = np.asarray(fp, dtype=bool)
    h, w = fp.shape
    if not fp.any():
        return fp.copy()
    # Morphological close (1-cell) to bridge 1-voxel gaps in outlines
    dil = fp.copy()
    xs, zs = np.where(fp)
    for x, z in zip(xs.tolist(), zs.tolist()):
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                xx, zz = x + dx, z + dz
                if 0 <= xx < h and 0 <= zz < w:
                    dil[xx, zz] = True
    # erode back
    closed = np.zeros_like(fp)
    for x in range(h):
        for z in range(w):
            if not dil[x, z]:
                continue
            ok = True
            for dx in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    xx, zz = x + dx, z + dz
                    if not (0 <= xx < h and 0 <= zz < w and dil[xx, zz]):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                closed[x, z] = True
    if int(closed.sum()) < max(8, int(0.5 * int(fp.sum()))):
        closed = dil  # fall back to dilation if erode wiped thin rings
    # Flood-fill exterior empties
    exterior = np.zeros_like(closed)
    stack = []
    for x in range(h):
        for z in (0, w - 1):
            if not closed[x, z] and not exterior[x, z]:
                stack.append((x, z))
                exterior[x, z] = True
    for z in range(w):
        for x in (0, h - 1):
            if not closed[x, z] and not exterior[x, z]:
                stack.append((x, z))
                exterior[x, z] = True
    while stack:
        x, z = stack.pop()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            xx, zz = x + dx, z + dz
            if 0 <= xx < h and 0 <= zz < w and (not closed[xx, zz]) and (not exterior[xx, zz]):
                exterior[xx, zz] = True
                stack.append((xx, zz))
    filled = closed | (~exterior & ~closed)
    # Keep original solid columns; never shrink
    filled = filled | fp
    # If fill exploded (>3x), keep closed only
    if int(filled.sum()) > max(int(3 * int(fp.sum())), int(0.85 * h * w)):
        filled = closed | fp
    return filled


def _footprint_sparse(fp: np.ndarray) -> bool:
    """True when footprint is outline-like (low fill inside bbox)."""
    fp = np.asarray(fp, dtype=bool)
    if not fp.any():
        return True
    xs, zs = np.where(fp)
    x0, x1 = int(xs.min()), int(xs.max())
    z0, z1 = int(zs.min()), int(zs.max())
    area = max(1, (x1 - x0 + 1) * (z1 - z0 + 1))
    fill = float(fp.sum()) / float(area)
    peri = _perimeter_mask(fp)
    peri_frac = float(peri.sum()) / max(1.0, float(fp.sum()))
    return fill < 0.48 or peri_frac > 0.72


def _building_footprint_from_occ(occ: np.ndarray) -> np.ndarray:
    """Building mass footprint, skipping full-box ground fill slabs common in 32^3 skeletons."""
    occ = np.asarray(occ).astype(bool)
    sx, sy, sz = occ.shape
    per_y = occ.sum(axis=(0, 2)).astype(np.int64)
    ys = np.where(per_y > 0)[0]
    if ys.size == 0:
        return np.zeros((sx, sz), dtype=bool)
    y0, y1 = int(ys.min()), int(ys.max())
    pmax = int(per_y.max())
    cut = y0
    found = False
    for y in range(y0, y1 + 1):
        if int(per_y[y]) <= max(20, int(0.55 * pmax)):
            cut = y
            found = True
            break
    if not found:
        cut = y0 + max(1, (y1 - y0) // 4)
    if cut <= y0 and y0 + 1 <= y1:
        cut = y0 + 1
    fp = occ[:, cut : y1 + 1, :].any(axis=1) if cut <= y1 else occ.any(axis=1)
    if int(fp.sum()) < 16:
        fp2 = np.zeros((sx, sz), dtype=bool)
        for x in range(sx):
            for z in range(sz):
                col = occ[x, :, z]
                if not col.any():
                    continue
                ys_c = np.where(col)[0]
                if int(ys_c.max()) - int(ys_c.min()) >= 2 or int(col.sum()) >= 3:
                    fp2[x, z] = True
        if int(fp2.sum()) >= 8:
            fp = fp2
    if int(fp.sum()) < 8:
        fp = occ.any(axis=1)
    return fp




def _force_open_room(
    out: np.ndarray,
    fp: np.ndarray,
    *,
    floor_ys: list[int],
    y_foundation: int,
    y_roof: int,
    wall_id: int,
    min_open: int = 36,
    floors_only: bool = False,
) -> int:
    """Carve a rectangular open room in the largest footprint bbox (door-tolerant hollowness).

    Narrow Victorian wings make ring floors still look slab-filled; this guarantees
    a visible hollow core between foundation and roof deck.
    """
    fp = np.asarray(fp, dtype=bool)
    if not fp.any():
        return 0
    xs, zs = np.where(fp)
    x0, x1 = int(xs.min()), int(xs.max())
    z0, z1 = int(zs.min()), int(zs.max())
    bw, bd = x1 - x0 + 1, z1 - z0 + 1
    # inset at least 2 from outer bbox; keep walls
    inset = 2 if min(bw, bd) >= 10 else 1
    ix0, ix1 = x0 + inset, x1 - inset
    iz0, iz1 = z0 + inset, z1 - inset
    if ix1 - ix0 < 3 or iz1 - iz0 < 3:
        return 0
    cleared = 0
    y_lo = int(y_foundation) + 1
    y_hi = max(y_lo + 1, int(y_roof) - 1)
    floor_set = {int(y) for y in floor_ys}
    for y in range(y_lo, min(y_hi + 1, out.shape[1])):
        for x in range(ix0, ix1 + 1):
            for z in range(iz0, iz1 + 1):
                if not fp[x, z]:
                    continue
                cur = int(out[x, y, z])
                if cur == 0:
                    continue
                # never carve perimeter shell columns
                # (bbox inset already); clear floors and leftover interior posts
                if floors_only:
                    # Keep walls/piers/roof mass; only strip floor slabs in the core
                    if cur == int(wall_id):
                        continue
                    if y in floor_set:
                        out[x, y, z] = 0
                        cleared += 1
                    continue
                if y in floor_set or cur != int(wall_id):
                    out[x, y, z] = 0
                    cleared += 1
                elif y not in floor_set and cur == int(wall_id):
                    # interior wall leftovers under sparse posts
                    out[x, y, z] = 0
                    cleared += 1
    # Ensure open volume large enough
    open_n = 0
    for y in range(y_lo, min(y_hi + 1, out.shape[1])):
        open_n += int((out[ix0:ix1 + 1, y, iz0:iz1 + 1] == 0).sum())
    if open_n < int(min_open):
        return cleared
    return cleared


def _normalize_story_floors(
    candidates: list[int] | None,
    *,
    y0: int,
    y_roof: int,
    spacing: int = 5,
    min_gap: int = 3,
    max_stories: int = 5,
) -> list[int]:
    """Regular story slabs: spacing rhythm, no roof slab, capped story count.

    Ref y_peaks are hints only — dense irregular peaks were painting a floor every
    3 cells (industrial) and thickening interiors.
    """
    y0 = int(y0)
    y_roof = int(y_roof)
    if y_roof <= y0 + 1:
        return [y0]
    sp = max(3, int(spacing))
    gap = max(2, int(min_gap))
    # Prefer even grid from foundation up to just under roof deck
    grid = list(range(y0, y_roof, sp))
    if y0 not in grid:
        grid.insert(0, y0)
    # Merge nearby ref peaks onto grid (tolerance), ignore roof-level peaks
    peaks = sorted({int(y) for y in (candidates or []) if y0 < int(y) < y_roof - 1})
    merged = list(grid)
    for p in peaks:
        if min(abs(p - g) for g in merged) >= max(gap, sp // 2):
            merged.append(p)
    merged = sorted(set(merged))
    # Enforce min gap
    out: list[int] = []
    for y in merged:
        if out and y - out[-1] < gap:
            continue
        if y >= y_roof:
            continue
        out.append(y)
    if y0 not in out:
        out = [y0] + out
    # Cap stories (keep ground + evenly subsample upper)
    if len(out) > int(max_stories):
        keep = [out[0]]
        rest = out[1:]
        n = int(max_stories) - 1
        if n <= 0:
            return [out[0]]
        idxs = [int(round(i * (len(rest) - 1) / max(1, n - 1))) for i in range(n)] if len(rest) > 1 else list(range(min(n, len(rest))))
        for i in idxs:
            if 0 <= i < len(rest) and rest[i] not in keep:
                keep.append(rest[i])
        out = sorted(set(keep))[: int(max_stories)]
        if y0 not in out:
            out = [y0] + out
    return out or [y0]


def _seal_shell_columns(
    out: np.ndarray,
    *,
    peri: np.ndarray,
    y0: int,
    y1: int,
    wall_id: int,
    foundation_id: int,
) -> int:
    """Fill air gaps on perimeter columns so the shell is continuous up to roof deck."""
    sx, sy, sz = out.shape
    added = 0
    y0 = int(y0)
    y1 = int(min(y1, sy - 1))
    if y1 <= y0:
        return 0
    px, pz = np.where(peri)
    for x, z in zip(px.tolist(), pz.tolist()):
        for y in range(y0, y1 + 1):
            if out[x, y, z] != 0:
                continue
            # Only seal if neighbors above/below (or both sides) suggest a wall hole
            below = y > y0 and out[x, y - 1, z] != 0
            above = y < y1 and out[x, y + 1, z] != 0
            side = False
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, zz = x + dx, z + dz
                if 0 <= xx < sx and 0 <= zz < sz and peri[xx, zz] and out[xx, y, zz] != 0:
                    side = True
                    break
            if below or above or side or y == y0:
                out[x, y, z] = int(foundation_id) if y <= y0 else int(wall_id)
                added += 1
    return added



def _morph_anti_box_fp(
    fp: np.ndarray,
    *,
    style: str | None = None,
    seed: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Break rectangular massing: L / T-wing / porch-notch (Phase 2).

    Pitched residential only. Industrial/modern stay box.
    Exterior cuts only — never enclosed courtyard holes (hole-fill safe).
    """
    fp0 = np.asarray(fp, dtype=bool)
    info: dict[str, Any] = {"anti_box": "none", "fp_before": int(fp0.sum()), "fp_after": int(fp0.sum())}
    if not fp0.any():
        return fp0, info
    style_l = (style or "").strip().lower()
    if style_l in ("industrial", "modern", "scifi", "desert"):
        info["anti_box"] = "skip_flat_style"
        return fp0.copy(), info
    if style_l not in (
        "european", "rustic", "western", "chinese", "japanese", "medieval", "fantasy",
    ):
        info["anti_box"] = "skip_unknown"
        return fp0.copy(), info

    xs, zs = np.where(fp0)
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    area = int(fp0.sum())
    info.update({"wx": wx, "wz": wz, "area": area})
    if min(wx, wz) < 7 or max(wx, wz) < 9 or area < 42:
        info["anti_box"] = "too_small"
        return fp0.copy(), info

    rng = np.random.default_rng(int(seed) + area * 17 + wx * 3 + wz)
    out = fp0.copy()
    huge = min(wx, wz) >= 9 and max(wx, wz) >= 13 and area >= 88
    large = min(wx, wz) >= 8 and max(wx, wz) >= 11 and area >= 64

    def _carve_corner(cut_w: int, cut_d: int, corner: int) -> None:
        nonlocal out
        if corner == 0:
            x_lo, x_hi = maxx - cut_w + 1, maxx + 1
            z_lo, z_hi = maxz - cut_d + 1, maxz + 1
        elif corner == 1:
            x_lo, x_hi = maxx - cut_w + 1, maxx + 1
            z_lo, z_hi = minz, minz + cut_d
        elif corner == 2:
            x_lo, x_hi = minx, minx + cut_w
            z_lo, z_hi = maxz - cut_d + 1, maxz + 1
        else:
            x_lo, x_hi = minx, minx + cut_w
            z_lo, z_hi = minz, minz + cut_d
        out[x_lo:x_hi, z_lo:z_hi] = False

    if huge or large:
        if style_l in ("medieval", "fantasy"):
            # Phase 3: smaller L so roof still covers most elevated mass
            lo, hi = 0.18, 0.28
        else:
            lo, hi = 0.26, 0.38
        cut_w = max(2, min(wx - 4, int(round(wx * float(rng.uniform(lo, hi))))))
        cut_d = max(2, min(wz - 4, int(round(wz * float(rng.uniform(lo, hi))))))
        corner = int(rng.integers(0, 4))
        _carve_corner(cut_w, cut_d, corner)
        mode = "L_wing"
        info.update({"cut_w": cut_w, "cut_d": cut_d, "corner": corner})
        # Phase 2: huge → second shallow cut (open-T). Skip for dense medieval/fantasy.
        if huge and style_l not in ("medieval", "fantasy"):
            stub_w = max(2, min(wx - 5, int(round(wx * 0.22))))
            stub_d = max(2, min(wz - 5, int(round(wz * 0.22))))
            # opposite corner family
            opp = (corner + 2) % 4
            # shallower than primary
            stub_w = max(2, stub_w - 1)
            stub_d = max(2, min(3, stub_d))
            before = int(out.sum())
            _carve_corner(stub_w, stub_d, opp)
            if int(out.sum()) >= max(40, int(0.50 * area)):
                mode = "T_wing"
                info.update({"stub_w": stub_w, "stub_d": stub_d, "stub_corner": opp})
            else:
                # revert stub
                out = fp0.copy()
                _carve_corner(cut_w, cut_d, corner)
                info["stub_reverted"] = True
    else:
        depth = 2 if wz >= 10 else 1
        span = max(3, min(wz - 2, int(round(wx * 0.42))))
        cx = (minx + maxx) // 2
        x_lo = max(minx + 1, cx - span // 2)
        x_hi = min(maxx, x_lo + span)
        z_lo = max(minz + 2, maxz - depth + 1)
        out[x_lo:x_hi, z_lo : maxz + 1] = False
        mode = "porch_notch"
        info.update({"notch_span": int(x_hi - x_lo), "notch_depth": depth})

    kept = int(out.sum())
    min_keep = max(36, int(0.52 * area))
    if kept < min_keep or not out.any():
        info["anti_box"] = "reverted_too_small"
        info["fp_after"] = area
        return fp0.copy(), info
    peri_n = int(_perimeter_mask(out).sum())
    if peri_n < 12:
        info["anti_box"] = "reverted_peri"
        return fp0.copy(), info
    info["anti_box"] = mode
    info["fp_after"] = kept
    return out, info


def _entry_porch_fp(
    fp: np.ndarray,
    *,
    style: str | None = None,
    seed: int = 0,
    size: int = 32,
    allow_inset: bool = True,
    mild_inset: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Low entry porch: attach outside if room, else Phase-3 inset notch into front face."""
    fp0 = np.asarray(fp, dtype=bool)
    info: dict[str, Any] = {"porch": "none"}
    style_l = (style or "").strip().lower()
    if style_l in ("industrial", "modern", "scifi") or not fp0.any():
        return np.zeros_like(fp0), info
    # Inset porch styles (phase 3): euro/rustic/western/chinese; others attach-only
    want_inset = bool(allow_inset) and style_l in ("european", "rustic", "western", "chinese")
    if style_l not in (
        "european", "rustic", "western", "chinese", "japanese", "medieval", "fantasy",
    ):
        return np.zeros_like(fp0), info
    xs, zs = np.where(fp0)
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    if min(wx, wz) < 5:
        info["porch"] = "too_narrow"
        return np.zeros_like(fp0), info
    rng = np.random.default_rng(int(seed) + 211)
    # Phase 4: chinese rarely skips (1/10); med/fantasy keep 1/4
    if style_l == "chinese" and int(rng.integers(0, 10)) == 0:
        info["porch"] = "skipped_style_rng"
        return np.zeros_like(fp0), info
    if style_l in ("medieval", "fantasy") and int(rng.integers(0, 4)) == 0:
        info["porch"] = "skipped_style_rng"
        return np.zeros_like(fp0), info

    faces = []
    if maxz <= size - 3:
        faces.append(("z", 1, size - 1 - maxz))
    if minz >= 2:
        faces.append(("z", -1, minz))
    if maxx <= size - 3:
        faces.append(("x", 1, size - 1 - maxx))
    if minx >= 2:
        faces.append(("x", -1, minx))

    porch = np.zeros_like(fp0)
    face_name = ""
    depth = 1
    if faces:
        faces.sort(key=lambda t: -t[2])
        pick = faces[int(rng.integers(0, min(2, len(faces))))]
        axis, sign, free = pick
        depth = 2 if free >= 2 else 1
        if axis == "z":
            span = max(3, min(wx - 2, int(round(wx * float(rng.uniform(0.35, 0.55))))))
            cx = (minx + maxx) // 2
            x_lo = max(0, cx - span // 2)
            x_hi = min(size, x_lo + span)
            if sign > 0:
                z_lo, z_hi = maxz + 1, min(size, maxz + 1 + depth)
            else:
                z_lo = max(0, minz - depth)
                z_hi = minz
            if z_hi > z_lo:
                porch[x_lo:x_hi, z_lo:z_hi] = True
                face_name = "+z" if sign > 0 else "-z"
        else:
            span = max(3, min(wz - 2, int(round(wz * float(rng.uniform(0.35, 0.55))))))
            cz = (minz + maxz) // 2
            z_lo = max(0, cz - span // 2)
            z_hi = min(size, z_lo + span)
            if sign > 0:
                x_lo, x_hi = maxx + 1, min(size, maxx + 1 + depth)
            else:
                x_lo = max(0, minx - depth)
                x_hi = minx
            if x_hi > x_lo:
                porch[x_lo:x_hi, z_lo:z_hi] = True
                face_name = "+x" if sign > 0 else "-x"
        dil = _dilate_mask(fp0, 1)
        porch &= ~fp0
        if int(porch.sum()) >= 4 and (porch & dil).any():
            info.update({
                "porch": "entry",
                "porch_cells": int(porch.sum()),
                "porch_face": face_name,
                "porch_depth": int(depth),
            })
            return porch, info

    # Phase 3 inset: carve shallow porch pocket into +z (or longest) face of main fp
    if not want_inset:
        info["porch"] = "no_room"
        return np.zeros_like(fp0), info
    if min(wx, wz) < 8 or max(wx, wz) < 10:
        info["porch"] = "inset_too_small"
        return np.zeros_like(fp0), info
    # Phase 4: mild_inset (western) = depth 1 + smaller span; keep more mass for roof
    if mild_inset:
        depth = 1
        span = max(3, min(wx - 5, int(round(wx * 0.28))))
        min_core = 0.78
    else:
        depth = 2 if wz >= 10 else 1
        span = max(3, min(wx - 4, int(round(wx * 0.40))))
        min_core = 0.55
    cx = (minx + maxx) // 2
    x_lo = max(minx + 1, cx - span // 2)
    x_hi = min(maxx, x_lo + span)
    z_lo = max(minz + 3, maxz - depth + 1)
    inset = np.zeros_like(fp0)
    inset[x_lo:x_hi, z_lo : maxz + 1] = True
    inset &= fp0
    if int(inset.sum()) < 4:
        info["porch"] = "inset_failed"
        return np.zeros_like(fp0), info
    # Reject if carve would leave too little core (protects western+T roof)
    core_left = int(fp0.sum()) - int(inset.sum())
    if core_left < max(36, int(min_core * int(fp0.sum()))):
        info["porch"] = "inset_too_aggressive"
        return np.zeros_like(fp0), info
    info.update({
        "porch": "inset_mild" if mild_inset else "inset",
        "porch_cells": int(inset.sum()),
        "porch_face": "+z_inset",
        "porch_depth": int(depth),
        "inset_carve": True,
        "mild_inset": bool(mild_inset),
    })
    return inset, info




def _upper_setback_fp(
    fp: np.ndarray,
    *,
    style: str | None = None,
    seed: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Optional second-storey setback: pull one long face inward by 1–2 cells."""
    fp0 = np.asarray(fp, dtype=bool)
    info: dict[str, Any] = {"setback": "none"}
    style_l = (style or "").strip().lower()
    if style_l in ("industrial", "modern", "scifi") or not fp0.any():
        return fp0.copy(), info
    if style_l not in (
        "european", "rustic", "western", "chinese", "japanese", "medieval", "fantasy",
    ):
        return fp0.copy(), info
    xs, zs = np.where(fp0)
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    if min(wx, wz) < 7 or max(wx, wz) < 10:
        info["setback"] = "too_small"
        return fp0.copy(), info
    rng = np.random.default_rng(int(seed) + 101)
    depth = 2 if max(wx, wz) >= 12 else 1
    out = fp0.copy()
    # Pull the longer face
    if wx >= wz:
        # setback +z or -z
        if int(rng.integers(0, 2)) == 0:
            out[:, max(minz, maxz - depth + 1) : maxz + 1] = False
            face = "+z"
        else:
            out[:, minz : minz + depth] = False
            face = "-z"
    else:
        if int(rng.integers(0, 2)) == 0:
            out[max(minx, maxx - depth + 1) : maxx + 1, :] = False
            face = "+x"
        else:
            out[minx : minx + depth, :] = False
            face = "-x"
    # Keep only cells that were in original AND still connected to core
    out &= fp0
    kept = int(out.sum())
    if kept < max(28, int(0.62 * int(fp0.sum()))):
        info["setback"] = "reverted"
        return fp0.copy(), info
    info.update({"setback": "face", "face": face, "depth": depth, "fp_after": kept})
    return out, info



def _gable_rise_map(
    fp: np.ndarray,
    *,
    rise: int,
    plateau_frac: float = 0.35,
    ridge_along_x: bool | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Per-column height *offset above eave* for a gable (0..rise)."""
    fp = np.asarray(fp, dtype=bool)
    hmap = np.zeros(fp.shape, dtype=np.int16)
    info: dict[str, Any] = {"rise": 0, "ridge_along_x": True, "half": 0}
    xs, zs = np.where(fp)
    if xs.size == 0:
        return hmap, info
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    if ridge_along_x is None:
        ridge_along_x = wx >= wz
    half = max(1, (wz // 2) if ridge_along_x else (wx // 2))
    rise = int(max(1, min(int(rise), half)))
    plateau = max(1, int(float(plateau_frac) * half))
    ridge_z = (minz + maxz) / 2.0
    ridge_x = (minx + maxx) / 2.0
    for x, z in zip(xs.tolist(), zs.tolist()):
        dist = abs(float(z) - ridge_z) if ridge_along_x else abs(float(x) - ridge_x)
        if dist <= plateau:
            h = rise
        else:
            span = max(1e-6, float(half - plateau))
            tnorm = min(1.0, (dist - plateau) / span)
            h = int(round(rise * (1.0 - tnorm)))
        hmap[x, z] = int(max(0, min(rise, h)))
    info.update({"rise": rise, "ridge_along_x": bool(ridge_along_x), "half": half, "plateau": plateau})
    return hmap, info


def _cross_gable_rise_map(
    fp: np.ndarray,
    *,
    rise: int,
    plateau_frac: float = 0.35,
    cross_band_frac: float = 0.42,
    cross_rise_scale: float = 0.92,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Primary gable + perpendicular cross ridge on a central band (max of both).

    Lightweight intersecting-gable silhouette without hip fill. The secondary
    ridge only raises columns inside a mid-band along the primary axis so eaves
    stay low and interior_cover is not flooded.
    """
    fp = np.asarray(fp, dtype=bool)
    primary, pinfo = _gable_rise_map(fp, rise=rise, plateau_frac=plateau_frac, ridge_along_x=None)
    info: dict[str, Any] = {
        "rise": int(pinfo.get("rise") or 0),
        "ridge_along_x": bool(pinfo.get("ridge_along_x", True)),
        "half": int(pinfo.get("half") or 0),
        "plateau": int(pinfo.get("plateau") or 0),
        "cross_gable": False,
        "cross_cells": 0,
    }
    xs, zs = np.where(fp)
    if xs.size == 0 or int(pinfo.get("rise") or 0) < 2:
        return primary, info
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    # Need enough span on both axes for a readable cross
    if min(wx, wz) < 8 or max(wx, wz) < 10:
        return primary, info

    ridge_along_x = bool(pinfo.get("ridge_along_x", True))
    # Secondary ridge is perpendicular to primary
    secondary, sinfo = _gable_rise_map(
        fp,
        rise=max(2, int(round(int(pinfo["rise"]) * float(cross_rise_scale)))),
        plateau_frac=min(0.55, float(plateau_frac) + 0.06),
        ridge_along_x=(not ridge_along_x),
    )
    # Restrict secondary to a central band along the *primary* ridge axis
    band = max(2, int(round(float(cross_band_frac) * (wx if ridge_along_x else wz))))
    if ridge_along_x:
        mid = (minx + maxx) / 2.0
        band_mask = np.zeros(fp.shape, dtype=bool)
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(float(x) - mid) <= band / 2.0 + 0.51:
                band_mask[x, z] = True
    else:
        mid = (minz + maxz) / 2.0
        band_mask = np.zeros(fp.shape, dtype=bool)
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(float(z) - mid) <= band / 2.0 + 0.51:
                band_mask[x, z] = True

    hmap = primary.copy()
    cross_n = 0
    raised = 0
    for x, z in zip(xs.tolist(), zs.tolist()):
        if not band_mask[x, z]:
            continue
        sec = int(secondary[x, z])
        if sec > int(hmap[x, z]):
            hmap[x, z] = sec
            raised += 1
        cross_n += 1
    # Require a meaningful lift; else keep pure primary
    if raised < max(6, int(0.04 * int(fp.sum()))):
        return primary, info
    info.update(
        {
            "cross_gable": True,
            "cross_cells": int(cross_n),
            "cross_raised": int(raised),
            "cross_band": int(band),
            "cross_ridge_along_x": bool(sinfo.get("ridge_along_x")),
            "cross_rise": int(sinfo.get("rise") or 0),
            "rise": max(int(pinfo.get("rise") or 0), int(sinfo.get("rise") or 0)),
        }
    )
    return hmap, info



def _reinforce_ridge_peak(
    out: np.ndarray,
    *,
    roof_fp: np.ndarray,
    eave_y: int,
    rise: int,
    roof_id: int,
    ridge_along_x: bool = True,
    style: str | None = None,
) -> int:
    """Place extra peak-row roof cells along the ridge so roof_score cover stays healthy."""
    fp = np.asarray(roof_fp, dtype=bool)
    if not fp.any() or int(rise) < 1:
        return 0
    sx, sy, sz = out.shape
    eave_y = int(eave_y)
    peak_y = int(min(sy - 1, eave_y + int(rise)))
    if peak_y <= eave_y:
        return 0
    xs, zs = np.where(fp)
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    n = 0
    style_l = (style or "").strip().lower()
    # Phase 3: wider ridge band for med/fantasy (need cover close to G)
    div = 3 if style_l in ("medieval", "fantasy") else 5
    if ridge_along_x:
        mid = (minz + maxz) / 2.0
        band = max(1, (maxz - minz + 1) // div)
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(float(z) - mid) <= band + 0.51:
                if out[x, peak_y, z] == 0:
                    out[x, peak_y, z] = int(roof_id)
                    n += 1
                if peak_y - 1 > eave_y and out[x, peak_y - 1, z] == 0:
                    out[x, peak_y - 1, z] = int(roof_id)
                    n += 1
    else:
        mid = (minx + maxx) / 2.0
        band = max(1, (maxx - minx + 1) // div)
        for x, z in zip(xs.tolist(), zs.tolist()):
            if abs(float(x) - mid) <= band + 0.51:
                if out[x, peak_y, z] == 0:
                    out[x, peak_y, z] = int(roof_id)
                    n += 1
                if peak_y - 1 > eave_y and out[x, peak_y - 1, z] == 0:
                    out[x, peak_y - 1, z] = int(roof_id)
                    n += 1
    return int(n)


def _place_skin_gable_roof(
    out: np.ndarray,
    *,
    roof_fp: np.ndarray,
    peri: np.ndarray,
    eave_y: int,
    roof_id: int,
    rise: int,
    plateau_frac: float = 0.35,
    overhang: int = 1,
    wall_id: int | None = None,
    clear_attic: bool = True,
    stairs_id: int = 0,
    cross_gable: bool = False,
    cross_band_frac: float = 0.42,
) -> tuple[int, dict[str, Any]]:
    """Hollow-friendly pitched roof: place roof *skin* only (not solid attic fill).

    - Base eave deck on footprint at eave_y
    - Roof surface at eave_y + rise_map (1-2 thick)
    - Optional overhang ring outside peri at eave_y
    - Clear interior attic under the skin so room stays open
    - Raise gable-end peri walls under the slope
    - Optional lightweight intersecting / cross gable (max of primary + band secondary)
    """
    sx, sy, sz = out.shape
    eave_y = int(eave_y)
    if eave_y < 0 or eave_y >= sy or not np.asarray(roof_fp).any():
        return 0, {"roof_mode": "none"}
    if cross_gable:
        rise_map, ginfo = _cross_gable_rise_map(
            roof_fp,
            rise=rise,
            plateau_frac=plateau_frac,
            cross_band_frac=float(cross_band_frac),
        )
    else:
        rise_map, ginfo = _gable_rise_map(roof_fp, rise=rise, plateau_frac=plateau_frac)
    roof_count = 0
    xs, zs = np.where(roof_fp)
    # 1) eave ring (not full attic slab — full deck inflated interior_cover)
    eave_ring = _dilate_mask(peri & roof_fp if peri.shape == roof_fp.shape else peri, 1) & roof_fp
    if int(eave_ring.sum()) < max(8, int(0.12 * int(roof_fp.sum()))):
        eave_ring = _dilate_mask(peri, 2) & roof_fp
    for x, z in zip(*np.where(eave_ring)):
        out[x, eave_y, z] = int(roof_id)
        roof_count += 1
    # 2) clear old mass above eave on footprint, then place skin
    for x, z in zip(xs.tolist(), zs.tolist()):
        h_off = int(rise_map[x, z])
        peak = int(min(sy - 1, eave_y + h_off))
        for yy in range(eave_y + 1, sy):
            # keep nothing above; rebuild skin
            if out[x, yy, z] != 0:
                out[x, yy, z] = 0
        # skin at peak (+ optional underlay)
        out[x, peak, z] = int(roof_id)
        roof_count += 1
        if peak - 1 > eave_y:
            out[x, peak - 1, z] = int(roof_id)
            roof_count += 1
        # gable-end wall under slope on peri only
        if peri[x, z] and wall_id is not None and peak > eave_y + 1:
            for yy in range(eave_y + 1, peak):
                if out[x, yy, z] == 0:
                    out[x, yy, z] = int(wall_id)
    # 3) clear interior attic (non-peri) between eave+1 and skin-1
    if clear_attic:
        for x, z in zip(xs.tolist(), zs.tolist()):
            if peri[x, z]:
                continue
            peak = int(min(sy - 1, eave_y + int(rise_map[x, z])))
            for yy in range(eave_y + 1, max(eave_y + 1, peak - 1)):
                # do not delete floor slabs or intentional interiors that aren't roof
                # attic should be air; floors are at known ys below eave usually
                if yy >= eave_y:
                    cur = int(out[x, yy, z])
                    if cur == int(roof_id) or cur == 0:
                        out[x, yy, z] = 0
    # 3b) stairs on slope ring (peri + 1-deep) for stepped gable silhouette
    stair_n = 0
    sid = int(stairs_id or 0)
    if sid > 0:
        rise_cap = int(ginfo.get("rise") or rise)
        slope_ring = peri.copy()
        # one cell inward from peri still on footprint → thicker stair band
        xs_p, zs_p = np.where(peri)
        for x, z in zip(xs_p.tolist(), zs_p.tolist()):
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, nz = x + dx, z + dz
                if 0 <= nx < sx and 0 <= nz < sz and roof_fp[nx, nz]:
                    slope_ring[nx, nz] = True
        for x, z in zip(*np.where(slope_ring & roof_fp)):
            h_off = int(rise_map[x, z])
            peak = int(min(sy - 1, eave_y + h_off))
            if peak <= eave_y:
                continue
            # skip flat ridge plateau; keep only sloping steps
            if h_off >= rise_cap:
                continue
            out[x, peak, z] = sid
            stair_n += 1
            # underlay step one below when room (reads as stair/slab cascade)
            if peak - 1 > eave_y and h_off + 1 < rise_cap:
                if not peri[x, z] or int(rise_map[x, z]) < rise_cap - 1:
                    out[x, peak - 1, z] = sid
                    stair_n += 1
        if stair_n:
            roof_count += 0  # stairs replace skin cells already counted
    info_stairs = {"roof_stairs": int(stair_n)}

    # 4) overhang eave ring
    oh = max(0, min(2, int(overhang)))
    oh_n = 0
    if oh > 0:
        px, pz = np.where(peri & roof_fp) if peri.shape == roof_fp.shape else np.where(peri)
        for x, z in zip(px.tolist(), pz.tolist()):
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for step in range(1, oh + 1):
                    nx, nz = x + dx * step, z + dz * step
                    if not (0 <= nx < sx and 0 <= nz < sz):
                        break
                    if roof_fp[nx, nz] if nx < roof_fp.shape[0] and nz < roof_fp.shape[1] else False:
                        break
                    if out[nx, eave_y, nz] == 0:
                        out[nx, eave_y, nz] = int(roof_id)
                        oh_n += 1
                        roof_count += 1
    mode = "skin_cross_gable" if ginfo.get("cross_gable") else "skin_gable"
    info = {
        "roof_mode": mode,
        "eave_y": eave_y,
        "overhang": oh,
        "overhang_cells": oh_n,
        "roof_stairs": int(stair_n),
        **ginfo,
    }
    return roof_count, info


def _place_interior_partitions(
    out: np.ndarray,
    *,
    build_fp: np.ndarray,
    peri: np.ndarray,
    y0: int,
    y1: int,
    wall_id: int,
    style: str | None = None,
) -> dict[str, Any]:
    """Room splits: mid / L / T / cross with doorways; keep large connected room_air.

    Phase D — style-aware aggressiveness:
    - industrial/modern: mid only (open loft)
    - chinese/medieval/fantasy: mid or short L only; cap wall height (~1 story)
      so cross_split no longer eats hundreds of room_air cells
    - european/rustic/western: keep T/cross when cavity is large enough
    """
    sx, sy, sz = out.shape
    y0, y1 = int(y0), int(y1)
    info: dict[str, Any] = {
        "partition_cells": 0,
        "door_cells": 0,
        "mode": "none",
        "rooms_est": 1,
        "policy": "none",
    }
    if y1 <= y0 + 3 or not build_fp.any():
        return info
    interior = build_fp & ~peri
    if interior.any():
        thick = _dilate_mask(peri, 1)
        interior = interior & ~thick
    xs, zs = np.where(interior)
    if xs.size < 20:
        return info
    minx, maxx = int(xs.min()), int(xs.max())
    minz, maxz = int(zs.min()), int(zs.max())
    wx, wz = maxx - minx + 1, maxz - minz + 1
    if min(wx, wz) < 5:
        return info
    style_l = (style or "").strip().lower()
    cells = 0
    door_cells = 0
    y_lo = y0 + 1
    y_hi = min(y1 - 1, sy - 1)
    if y_hi <= y_lo:
        return info

    # Style tiers (Phase D)
    simple = style_l in ("modern", "industrial", "scifi")
    conservative = style_l in ("chinese", "medieval", "fantasy", "japanese")
    cross_friendly = style_l in ("european", "rustic", "western")
    if conservative:
        # One clear story of partition (~4–5 cells) — enough to read rooms, not a solid shaft
        y_hi = min(y_hi, y_lo + 4)
        info["policy"] = "conservative_mid_L"
    elif simple:
        info["policy"] = "open_mid"
    elif cross_friendly:
        info["policy"] = "cross_ok"
    else:
        info["policy"] = "default_L"

    door_h = 2
    door_y0 = y_lo
    door_y1 = min(y_lo + door_h - 1, y_hi)

    def _paint_wall_line(coords: list[tuple[int, int]], door_idx: int) -> None:
        nonlocal cells, door_cells
        n = len(coords)
        if n < 3:
            return
        for i, (x, z) in enumerate(coords):
            is_door = abs(i - door_idx) <= 0
            for y in range(y_lo, y_hi + 1):
                if is_door and door_y0 <= y <= door_y1:
                    if out[x, y, z] != 0 and out[x, y, z] != int(wall_id):
                        continue
                    out[x, y, z] = 0
                    door_cells += 1
                    continue
                cur = int(out[x, y, z])
                if cur == 0:
                    out[x, y, z] = int(wall_id)
                    cells += 1

    def _line_z(mid_z: int) -> list[tuple[int, int]]:
        return [(int(x), mid_z) for x in range(minx, maxx + 1) if interior[x, mid_z]]

    def _line_x(mid_x: int) -> list[tuple[int, int]]:
        return [(mid_x, int(z)) for z in range(minz, maxz + 1) if interior[mid_x, z]]

    def _best_z() -> int:
        mid_z = int(round((minz + maxz) / 2.0))
        best_z, best_n = mid_z, -1
        for zz in range(minz, maxz + 1):
            n = int(interior[:, zz].sum()) if 0 <= zz < sz else 0
            if n > best_n:
                best_n, best_z = n, zz
        return best_z

    def _best_x() -> int:
        mid_x = int(round((minx + maxx) / 2.0))
        best_x, best_n = mid_x, -1
        for xx in range(minx, maxx + 1):
            n = int(interior[xx, :].sum()) if 0 <= xx < sx else 0
            if n > best_n:
                best_n, best_x = n, xx
        return best_x

    def _do_mid_or_L(*, stub_frac: float = 0.33, stub_cap: int = 6, force_L: bool = False) -> None:
        nonlocal cells  # painted via closure
        if primary_along_x:
            coords = _line_z(mid_z)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            info["mode"] = "mid_z"
            want_L = force_L or max(wx, wz) >= 10
            if want_L and coords:
                ax = coords[door_idx][0]
                stub_len = max(2, min(stub_cap, int(wz * stub_frac)))
                stub = [
                    (ax, z)
                    for z in range(mid_z + 1, min(maxz, mid_z + stub_len) + 1)
                    if interior[ax, z]
                ]
                if len(stub) >= 2:
                    _paint_wall_line(stub, door_idx=len(stub))  # no door on stub tip
                    info["mode"] = "L_split"
            info["rooms_est"] = 3 if info["mode"] == "L_split" else 2
        else:
            coords = _line_x(mid_x)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            info["mode"] = "mid_x"
            want_L = force_L or max(wx, wz) >= 10
            if want_L and coords:
                az = coords[door_idx][1]
                stub_len = max(2, min(stub_cap, int(wx * stub_frac)))
                stub = [
                    (x, az)
                    for x in range(mid_x + 1, min(maxx, mid_x + stub_len) + 1)
                    if interior[x, az]
                ]
                if len(stub) >= 2:
                    _paint_wall_line(stub, door_idx=len(stub))
                    info["mode"] = "L_split"
            info["rooms_est"] = 3 if info["mode"] == "L_split" else 2

    area = int(interior.sum())
    # Cross-friendly needs a real cavity; raise bars vs Phase B to avoid densifying sparse refs
    large = min(wx, wz) >= 7 and max(wx, wz) >= 11 and area >= 48
    huge = min(wx, wz) >= 9 and max(wx, wz) >= 14 and area >= 80

    mid_z = _best_z()
    mid_x = _best_x()
    primary_along_x = wx >= wz

    if simple:
        if primary_along_x:
            coords = _line_z(mid_z)
            _paint_wall_line(coords, len(coords) // 2)
            info["mode"] = "mid_z"
        else:
            coords = _line_x(mid_x)
            _paint_wall_line(coords, len(coords) // 2)
            info["mode"] = "mid_x"
        info["rooms_est"] = 2
    elif conservative:
        # Never cross/T. Short L only when footprint is wide enough.
        _do_mid_or_L(stub_frac=0.25, stub_cap=4, force_L=(max(wx, wz) >= 12 and area >= 60))
    elif cross_friendly and huge:
        cz = _line_z(mid_z)
        cx = _line_x(mid_x)
        _paint_wall_line(cz, len(cz) // 2)
        _paint_wall_line(cx, len(cx) // 2)
        info["mode"] = "cross_split"
        info["rooms_est"] = 4
    elif cross_friendly and large:
        # T-split
        if primary_along_x:
            coords = _line_z(mid_z)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            stub_len = max(3, wz // 2)
            stub: list[tuple[int, int]] = []
            z_hi_span = maxz - mid_z
            z_lo_span = mid_z - minz
            if z_hi_span >= z_lo_span:
                z_range = range(mid_z + 1, min(maxz, mid_z + stub_len) + 1)
            else:
                z_range = range(max(minz, mid_z - stub_len), mid_z)
            ax = coords[door_idx][0] if coords else mid_x
            for z in z_range:
                if interior[ax, z]:
                    stub.append((ax, z))
            if len(stub) >= 3:
                _paint_wall_line(stub, door_idx=len(stub) // 2)
                info["mode"] = "T_split"
                info["rooms_est"] = 3
            else:
                info["mode"] = "mid_z"
                info["rooms_est"] = 2
        else:
            coords = _line_x(mid_x)
            door_idx = len(coords) // 2
            _paint_wall_line(coords, door_idx)
            stub_len = max(3, wx // 2)
            stub = []
            x_hi_span = maxx - mid_x
            x_lo_span = mid_x - minx
            if x_hi_span >= x_lo_span:
                x_range = range(mid_x + 1, min(maxx, mid_x + stub_len) + 1)
            else:
                x_range = range(max(minx, mid_x - stub_len), mid_x)
            az = coords[door_idx][1] if coords else mid_z
            for x in x_range:
                if interior[x, az]:
                    stub.append((x, az))
            if len(stub) >= 3:
                _paint_wall_line(stub, door_idx=len(stub) // 2)
                info["mode"] = "T_split"
                info["rooms_est"] = 3
            else:
                info["mode"] = "mid_x"
                info["rooms_est"] = 2
    else:
        # default / small cross-friendly: mid + short L
        _do_mid_or_L(stub_frac=0.33, stub_cap=6, force_L=False)

    info["partition_cells"] = int(cells)
    info["door_cells"] = int(door_cells)
    info["y_span"] = int(y_hi - y_lo + 1)
    return info


def _resolve_stairs_from_palette(
    palette: dict[int, str],
    *,
    roof_id: int,
    wall_id: int,
    style: str | None = None,
) -> int:
    """Map roof/wall role to a *_stairs block for gable slope accents."""
    name_to_id = {str(v): int(k) for k, v in palette.items()}
    # also short names without minecraft:
    for k, v in list(name_to_id.items()):
        short = k.split(":")[-1]
        name_to_id.setdefault(short, v)

    def _pick(cands: list[str]) -> int:
        for c in cands:
            for key in (c, f"minecraft:{c}"):
                if key in name_to_id and int(name_to_id[key]) > 0:
                    return int(name_to_id[key])
        return 0

    roof_name = str(palette.get(int(roof_id), "")).split(":")[-1]
    wall_name = str(palette.get(int(wall_id), "")).split(":")[-1]
    cands: list[str] = []
    for base in (roof_name, wall_name):
        if base.endswith("_planks"):
            cands.append(base.replace("_planks", "_stairs"))
        if base.endswith("_bricks"):
            cands.append(base[:-1] + "_stairs" if base.endswith("s") else base + "_stairs")
            cands.append(base.replace("_bricks", "_brick_stairs"))
        if base.endswith("_block"):
            cands.append(base.replace("_block", "_stairs"))
    style_l = (style or "").strip().lower()
    if style_l in ("european", "medieval", "rustic", "western"):
        cands += ["dark_oak_stairs", "spruce_stairs", "oak_stairs", "brick_stairs", "stone_brick_stairs"]
    elif style_l in ("chinese", "japanese", "fantasy"):
        cands += ["dark_oak_stairs", "spruce_stairs", "mangrove_stairs", "oak_stairs"]
    else:
        cands += ["oak_stairs", "spruce_stairs", "stone_brick_stairs", "cobblestone_stairs"]
    return _pick(cands)


def scaffold_from_occupancy(
    occupancy: np.ndarray,
    *,
    wall_id: int,
    floor_id: int,
    floor_ys: list[int] | None = None,
    shell_thickness: int = 1,
    style: str | None = None,
    roof_id: int | None = None,
    foundation_id: int | None = None,
    accent_id: int | None = None,
    stairs_id: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Turn 32^3 occupancy into hollow shell + floor slabs + covering low-pitch roof.

    Uses a building footprint (not full ground-fill) so lakeside/irregular refs keep a
    real roof deck instead of a few peak voxels after shell extraction.
    Role materials: foundation / wall / roof / floor / accent (corners).
    """
    occ = np.asarray(occupancy).astype(bool)
    if occ.ndim != 3:
        raise ValueError("occupancy must be 3D")
    sx, sy, sz = occ.shape
    out = np.zeros((sx, sy, sz), dtype=np.int16)
    stats: dict[str, Any] = {
        "shell": 0,
        "floors": 0,
        "roof": 0,
        "floor_ys": [],
        "build_fp": 0,
        "roof_deck_y": -1,
        "roof_mode": "none",
        "foundation": 0,
        "accent": 0,
    }
    roof_id = int(wall_id if roof_id is None else roof_id)
    foundation_id = int(wall_id if foundation_id is None else foundation_id)
    accent_id = int(wall_id if accent_id is None else accent_id)
    if foundation_id == wall_id:
        foundation_id = int(floor_id) if int(floor_id) != int(wall_id) else int(wall_id)
    stats["role_ids"] = {
        "wall": int(wall_id),
        "floor": int(floor_id),
        "roof": int(roof_id),
        "foundation": int(foundation_id),
        "accent": int(accent_id),
    }

    footprint_all = occ.any(axis=1)
    build_fp = _building_footprint_from_occ(occ)
    if not build_fp.any():
        build_fp = footprint_all
    # Night-22 anti-box: L-wing / porch notch before peri (pitched styles only)
    style_l_early = (style or "").strip().lower()
    build_fp, ab_info = _morph_anti_box_fp(
        build_fp, style=style_l_early, seed=int(build_fp.sum()) + int(wall_id) * 13
    )
    stats["anti_box"] = ab_info.get("anti_box")
    stats["anti_box_fp_before"] = int(ab_info.get("fp_before") or 0)
    stats["anti_box_fp_after"] = int(ab_info.get("fp_after") or 0)
    porch_fp, porch_info = _entry_porch_fp(
        build_fp,
        style=style_l_early,
        seed=int(build_fp.sum()) + 29,
        size=int(sx),
        allow_inset=True,
        mild_inset=(style_l_early == "western"),
    )
    stats["porch"] = porch_info.get("porch")
    stats["porch_cells"] = int(porch_info.get("porch_cells") or 0)
    # Phase 3: inset porch carves into main footprint (pocket), then porch paints low mass there
    if porch_info.get("inset_carve") and porch_fp is not None and np.asarray(porch_fp).any():
        build_fp = build_fp & ~np.asarray(porch_fp, dtype=bool)
        _keep = 0.78 if porch_info.get("mild_inset") else 0.55
        if int(build_fp.sum()) < max(28, int(_keep * int(stats.get("anti_box_fp_after") or build_fp.sum() or 1))):
            # revert if too aggressive
            build_fp = build_fp | np.asarray(porch_fp, dtype=bool)
            porch_fp = np.zeros_like(build_fp)
            porch_info = {"porch": "inset_reverted"}
            stats["porch"] = "inset_reverted"
            stats["porch_cells"] = 0
    peri = _perimeter_mask(build_fp)
    stats["build_fp"] = int(build_fp.sum())

    ys_with = [int(y) for y in range(sy) if occ[:, y, :].any()]
    y_foundation = ys_with[0] if ys_with else 0

    hmap = np.full((sx, sz), -1, dtype=np.int16)
    xs_b, zs_b = np.where(build_fp)
    for x, z in zip(xs_b.tolist(), zs_b.tolist()):
        ys_c = np.where(occ[x, :, z])[0]
        if ys_c.size:
            hmap[x, z] = int(ys_c.max())
    valid_h = hmap[hmap >= 0]
    if valid_h.size:
        roof_deck_y = int(np.percentile(valid_h.astype(np.float64), 80))
        roof_peak_y = int(valid_h.max())
        roof_deck_y = int(np.clip(roof_deck_y, y_foundation + 2, sy - 1))
        if roof_peak_y - roof_deck_y > 6:
            roof_deck_y = max(roof_deck_y, roof_peak_y - 4)
    else:
        roof_deck_y = max(y_foundation + 3, (sy - 1) // 2)
        roof_peak_y = roof_deck_y
    stats["roof_deck_y"] = int(roof_deck_y)

    style_l = (style or "").strip().lower()
    # Story slabs: regularize ref peaks (avoid floor every 3 cells) and never paint roof as floor
    _max_stories = 3 if style_l in ("medieval", "fantasy") else 4
    _spacing = 7 if style_l in ("medieval", "fantasy") else 6
    floor_ys = _normalize_story_floors(
        floor_ys,
        y0=int(y_foundation),
        y_roof=int(roof_deck_y),
        spacing=_spacing,
        min_gap=4,
        max_stories=_max_stories,
    )
    stats["floor_ys"] = floor_ys
    sparse_fp = _footprint_sparse(build_fp)
    stats["sparse_fp"] = bool(sparse_fp)
    # Roof footprint: fill outline holes so Victorian/sparse euro refs get a real deck
    roof_fp = _fill_footprint_holes(build_fp) if build_fp.any() else build_fp
    stats["roof_fp"] = int(roof_fp.sum()) if roof_fp is not None else 0
    # Skin-gable rise (hollow attic). Flat styles keep 0-1 for eave deck only.
    # Night-22: slightly taller pitch for residential so stairs/slab cascade reads.
    if style_l in ("industrial", "modern", "scifi"):
        max_rise = 0
    elif style_l in ("european", "rustic", "western"):
        max_rise = 4 if not sparse_fp else 3
    elif style_l in ("chinese", "japanese"):
        max_rise = 4
    elif style_l in ("fantasy", "medieval"):
        # Phase 3: milder rise (G used ~3) so more elev cols hit peak_y
        max_rise = 3
    else:
        max_rise = 2
    stats["max_rise"] = int(max_rise)
    # Upper-storey setback footprint (shell only above mid floor)
    upper_fp, ub_info = _upper_setback_fp(
        build_fp, style=style_l, seed=int(stats.get("build_fp") or 0) + 7
    )
    stats["upper_setback"] = ub_info.get("setback")
    mid_floor_y = int(floor_ys[len(floor_ys) // 2]) if floor_ys else int(y_foundation + 4)

    for y in range(y_foundation, min(roof_deck_y, sy - 1) + 1):
        use_fp_y = upper_fp if (y > mid_floor_y and ub_info.get("setback") == "face") else build_fp
        peri_y = _perimeter_mask(use_fp_y) if use_fp_y is not build_fp else peri
        slice_fp = occ[:, y, :] & use_fp_y
        # Always paint full build perimeter so tapered upper rings stay connected
        # to the lower shell (otherwise repair drop_float_cc chops the roof).
        peri_block = int(foundation_id) if y <= y_foundation else int(wall_id)
        out[:, y, :][peri_y] = peri_block
        if y <= y_foundation:
            stats["foundation"] += int(peri.sum())
        else:
            stats["shell"] += int(peri.sum())
        floor_mask = build_fp
        if slice_fp.any():
            slice_peri = _perimeter_mask(slice_fp)
            if not slice_peri.any():
                slice_peri = peri & slice_fp
            if shell_thickness > 1:
                thick = slice_peri.copy()
                xs, zs = np.where(slice_peri)
                for x, z in zip(xs.tolist(), zs.tolist()):
                    for dx in range(-shell_thickness + 1, shell_thickness):
                        for dz in range(-shell_thickness + 1, shell_thickness):
                            xx, zz = x + dx, z + dz
                            if 0 <= xx < sx and 0 <= zz < sz and slice_fp[xx, zz]:
                                thick[xx, zz] = True
                slice_peri = thick
            out[:, y, :][slice_peri] = peri_block
            if y <= y_foundation:
                stats["foundation"] += int(slice_peri.sum())
            else:
                stats["shell"] += int(slice_peri.sum())
            floor_mask = slice_fp

        if y in floor_ys and build_fp.any():
            use_fp = floor_mask if floor_mask.any() else build_fp
            # Sparse outlines: ground slab may use filled outline, then ring-carve open room
            if (
                sparse_fp
                and y == y_foundation
                and roof_fp is not None
                and int(roof_fp.sum()) > int(use_fp.sum())
            ):
                use_fp = roof_fp
            # Hollow house: ring floors (not full footprint) so rooms stay open
            # Medieval/fantasy refs stay dense — keep ring thinner so interior_cover < 0.7
            if style_l in ("medieval", "fantasy"):
                depth = 1
            else:
                depth = 2 if y == y_foundation else 1
            use_fp = _ring_floor_mask(use_fp, depth=depth, keep_cross=False)
            # Extra carve for dense refs: keep only peri-adjacent walk band
            if style_l in ("medieval", "fantasy") and use_fp.any():
                # Phase 2: tighter peri walk-band + light thin-out to keep interior_cover <=0.7
                keep = _dilate_mask(peri_y, 1) & use_fp
                if int(keep.sum()) >= max(10, int(0.12 * int(build_fp.sum()))):
                    use_fp = keep
                inner = use_fp & ~peri_y
                xs_i, zs_i = np.where(inner)
                if xs_i.size > 8:
                    drop_n = max(1, int(0.18 * xs_i.size))
                    order = np.argsort(-(xs_i.astype(np.int32) + zs_i.astype(np.int32)))
                    for k in order[:drop_n]:
                        use_fp[int(xs_i[k]), int(zs_i[k])] = False
            out[:, y, :][use_fp] = int(floor_id)
            out[:, y, :][peri_y] = peri_block
            stats["floors"] += int(use_fp.sum())
            stats["floor_mode"] = "ring"

    if build_fp.any() and 0 <= roof_deck_y < sy:
        use_roof_fp = roof_fp if roof_fp is not None and roof_fp.any() else build_fp
        # Phase 2: roof spans FULL build_fp (setback only affects upper walls).
        # Roofing only upper_fp left wing columns in elevated_fp without y_max cover
        # and tanked roof_score vs G.
        want_skin_gable = style_l in (
            "european", "rustic", "western", "chinese", "japanese", "medieval", "fantasy",
        ) and int(max_rise) >= 2
        if want_skin_gable:
            # True eaves + pitched silhouette (skin only — do not solid-fill attic)
            # Phase 3: med/fantasy wide ridge (G-like) to close roof_score gap
            if style_l in ("european", "rustic", "western"):
                plateau = 0.38
            elif style_l in ("chinese", "japanese"):
                plateau = 0.48
            elif style_l in ("medieval", "fantasy"):
                plateau = 0.70
            else:
                plateau = 0.40
            oh = 2 if style_l in ("european", "rustic", "chinese", "western") else 1
            # Night22e: light intersecting gable for euro/chinese (+ rustic).
            # Skip industrial/modern (flat). Avoid med/fantasy (interior_cover risk).
            want_cross = style_l in ("european", "chinese", "rustic")
            cross_band = 0.40 if style_l == "european" else (0.44 if style_l == "chinese" else 0.38)
            roof_count, rinfo = _place_skin_gable_roof(
                out,
                roof_fp=use_roof_fp,
                peri=peri,
                eave_y=int(roof_deck_y),
                roof_id=int(roof_id),
                rise=int(max_rise),
                plateau_frac=float(plateau),
                overhang=int(oh),
                wall_id=int(wall_id),
                clear_attic=True,
                stairs_id=int(stairs_id or 0),
                cross_gable=bool(want_cross),
                cross_band_frac=float(cross_band),
            )
            # Phase 2 ridge reinforce: ensure peak_y solids along ridge for roof_score cover
            ridge_n = _reinforce_ridge_peak(
                out,
                roof_fp=use_roof_fp,
                eave_y=int(roof_deck_y),
                rise=int(rinfo.get("rise") or max_rise),
                roof_id=int(roof_id),
                ridge_along_x=bool(rinfo.get("ridge_along_x", True)),
                style=style_l,
            )
            # Cross ridge reinforce (perpendicular) when intersecting gable fired
            cross_ridge_n = 0
            if rinfo.get("cross_gable"):
                cross_ridge_n = _reinforce_ridge_peak(
                    out,
                    roof_fp=use_roof_fp,
                    eave_y=int(roof_deck_y),
                    rise=int(rinfo.get("cross_rise") or rinfo.get("rise") or max_rise),
                    roof_id=int(roof_id),
                    ridge_along_x=bool(rinfo.get("cross_ridge_along_x", not rinfo.get("ridge_along_x", True))),
                    style=style_l,
                )
                ridge_n += int(cross_ridge_n)
            roof_count += int(ridge_n)
            stats["roof"] = int(roof_count)
            stats["roof_mode"] = str(rinfo.get("roof_mode") or "skin_gable")
            stats["eave_overhang"] = int(rinfo.get("overhang") or 0)
            stats["gable_rise"] = int(rinfo.get("rise") or max_rise)
            stats["roof_stairs"] = int(rinfo.get("roof_stairs") or 0)
            stats["ridge_reinforce"] = int(ridge_n)
            stats["cross_gable"] = bool(rinfo.get("cross_gable"))
            stats["cross_raised"] = int(rinfo.get("cross_raised") or 0)
            stats["cross_ridge_reinforce"] = int(cross_ridge_n)
            stats["sparse_interior_posts"] = False
        else:
            # Flat / low deck (industrial, modern): coherent cover + eave ring
            xs, zs = np.where(use_roof_fp)
            roof_count = 0
            yy_deck = int(roof_deck_y)
            for x, z in zip(xs.tolist(), zs.tolist()):
                out[x, yy_deck, z] = int(roof_id)
                roof_count += 1
            # thin optional plateau bump (max_rise 0-1)
            if int(max_rise) > 0 and xs.size:
                cx = float(xs.mean()); cz = float(zs.mean())
                dists = np.sqrt((xs.astype(np.float64) - cx) ** 2 + (zs.astype(np.float64) - cz) ** 2)
                max_d = max(1.0, float(dists.max()) if dists.size else 1.0)
                for x, z, d in zip(xs.tolist(), zs.tolist(), dists.tolist()):
                    if float(d) / max_d <= 0.55:
                        yy = int(min(sy - 1, yy_deck + int(max_rise)))
                        if yy > yy_deck:
                            out[x, yy, z] = int(roof_id)
                            roof_count += 1
            # eave overhang ring for industrial/modern (visible lip, not pitch)
            oh = 1
            oh_n = 0
            px, pz = np.where(peri & use_roof_fp) if peri.shape == use_roof_fp.shape else np.where(peri)
            for x, z in zip(px.tolist(), pz.tolist()):
                for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, nz = x + dx, z + dz
                    if not (0 <= nx < sx and 0 <= nz < sz):
                        continue
                    if use_roof_fp[nx, nz]:
                        continue
                    if out[nx, yy_deck, nz] == 0:
                        out[nx, yy_deck, nz] = int(roof_id)
                        oh_n += 1
                        roof_count += 1
            # peri connect under deck (no interior posts)
            if sparse_fp:
                peri_roof = (peri & use_roof_fp) if peri.shape == use_roof_fp.shape else peri
                for x, z in zip(*np.where(peri_roof)):
                    for y in range(max(y_foundation + 1, yy_deck - 2), yy_deck):
                        if out[x, y, z] == 0:
                            out[x, y, z] = int(wall_id)
                            stats["shell"] += 1
            stats["roof"] = int(roof_count)
            stats["roof_mode"] = "flat_eave_deck"
            stats["eave_overhang"] = oh
            stats["eave_cells"] = int(oh_n)
            stats["sparse_interior_posts"] = False

    # Seal perimeter shell gaps (continuous walls under deck)
    seal_n = _seal_shell_columns(
        out,
        peri=peri,
        y0=y_foundation,
        y1=int(roof_deck_y),
        wall_id=int(wall_id),
        foundation_id=int(foundation_id),
    )
    if seal_n:
        stats["shell_seal"] = int(seal_n)
        stats["shell"] = int(stats.get("shell") or 0) + int(seal_n)

    # Simple interior partitions (1-thick + doorway); after shell/floors, under eave
    if build_fp.any():
        part = _place_interior_partitions(
            out,
            build_fp=build_fp if not sparse_fp else (roof_fp if roof_fp is not None and roof_fp.any() else build_fp),
            peri=peri,
            y0=int(y_foundation),
            y1=int(roof_deck_y),
            wall_id=int(wall_id),
            style=style_l,
        )
        stats["partition_mode"] = part.get("mode")
        stats["partition_cells"] = int(part.get("partition_cells") or 0)
        stats["partition_door_cells"] = int(part.get("door_cells") or 0)
        stats["rooms_est"] = int(part.get("rooms_est") or 1)
        stats["partition_policy"] = part.get("policy")
        stats["partition_y_span"] = int(part.get("y_span") or 0)

    # Load-bearing corner posts only (bbox corners snapped to peri).
    if build_fp.any() and int(accent_id) > 0 and int(accent_id) != int(wall_id):
        xs_c, zs_c = np.where(peri)
        accent_n = 0
        if xs_c.size:
            minx, maxx = int(xs_c.min()), int(xs_c.max())
            minz, maxz = int(zs_c.min()), int(zs_c.max())
            peri_set = set(zip(xs_c.tolist(), zs_c.tolist()))
            corners = [(minx, minz), (minx, maxz), (maxx, minz), (maxx, maxz)]
            snapped = []
            for cx0, cz0 in corners:
                if (cx0, cz0) in peri_set:
                    snapped.append((cx0, cz0))
                    continue
                best, best_d = None, 10**9
                for x, z in peri_set:
                    d = abs(x - cx0) + abs(z - cz0)
                    if d < best_d:
                        best_d, best = d, (x, z)
                if best is not None and best_d <= 2:
                    snapped.append(best)
            snapped = list(dict.fromkeys(snapped))
            for x, z in snapped:
                for y in range(y_foundation + 1, min(roof_deck_y, sy - 1) + 1):
                    cur = int(out[x, y, z])
                    if cur == int(wall_id) or cur == 0:
                        if cur == 0 and not peri[x, z]:
                            continue
                        out[x, y, z] = int(accent_id)
                        accent_n += 1
        stats["accent"] = int(accent_n)
        stats["load_path"] = "corner_posts"

    # Phase 2: low entry porch (walls + flat deck, ~3 tall) — does not eat main cavity
    if "porch_fp" in dir() or True:
        try:
            pfp = porch_fp  # set earlier in this function
        except NameError:
            pfp = None
        if pfp is not None and np.asarray(pfp).any():
            porch_h = min(3, max(2, int(roof_deck_y - y_foundation) // 3))
            y_porch_top = int(min(sy - 1, y_foundation + porch_h))
            pperi = _perimeter_mask(pfp)
            pn = 0
            for y in range(y_foundation, y_porch_top + 1):
                block = int(foundation_id) if y <= y_foundation else int(wall_id)
                if y == y_porch_top:
                    out[:, y, :][pfp] = int(roof_id)
                    pn += int(pfp.sum())
                else:
                    out[:, y, :][pperi] = block
                    if y == y_foundation:
                        # thin floor ring on porch
                        out[:, y, :][pfp] = int(floor_id)
                    pn += int(pperi.sum())
            # doorway from main into porch on shared edge
            shared = peri & _dilate_mask(pfp, 1)
            sx_s, sz_s = np.where(shared)
            if sx_s.size:
                mid = len(sx_s) // 2
                dx, dz = int(sx_s[mid]), int(sz_s[mid])
                for yy in range(y_foundation + 1, min(y_foundation + 3, y_porch_top)):
                    out[dx, yy, dz] = 0
            stats["porch_paint"] = int(pn)
            stats["porch_top_y"] = int(y_porch_top)

    return out, stats


def rule_scaffold_voxels(
    *,
    style: str,
    size: int = 32,
    seed: int = 0,
    wall_id: int = 1,
    floor_id: int = 1,
    roof_id: int | None = None,
    foundation_id: int | None = None,
    accent_id: int | None = None,
    stairs_id: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Procedural box house: shell + ring floors + skin_gable or flat_eave + partitions."""
    rng = np.random.default_rng(int(seed))
    sx = sy = sz = int(size)
    out = np.zeros((sx, sy, sz), dtype=np.int16)
    roof_id = int(wall_id if roof_id is None else roof_id)
    foundation_id = int(wall_id if foundation_id is None else foundation_id)
    accent_id = int(wall_id if accent_id is None else accent_id)
    style_l = (style or "").strip().lower()

    bw = int(rng.integers(max(8, size // 3), max(9, min(size - 4, 18))))
    bd = int(rng.integers(max(8, size // 3), max(9, min(size - 4, 18))))
    bh = int(rng.integers(7, max(8, min(size - 4, 14))))
    x0 = (sx - bw) // 2
    z0 = (sz - bd) // 2
    y0 = 0
    x1, z1, y1 = x0 + bw, z0 + bd, y0 + bh

    floor_ys = _normalize_story_floors(
        None, y0=y0, y_roof=y1, spacing=6, min_gap=4, max_stories=3
    )

    build_box = np.zeros((sx, sz), dtype=bool)
    build_box[x0:x1, z0:z1] = True
    build_box, ab_rule = _morph_anti_box_fp(build_box, style=style_l, seed=int(seed) + bw * 5 + bd)
    peri = _perimeter_mask(build_box)
    # Refresh bbox from morph (shell loops still use x0.. for rect paint — rebuild from mask)
    if build_box.any():
        xs_b, zs_b = np.where(build_box)
        x0, x1 = int(xs_b.min()), int(xs_b.max()) + 1
        z0, z1 = int(zs_b.min()), int(zs_b.max()) + 1
    for y in floor_ys:
        if y >= sy or y >= y1:
            continue
        depth = 2 if y == y0 else 1
        ring = _ring_floor_mask(build_box, depth=depth, keep_cross=False)
        out[:, y, :][ring] = int(floor_id)

    for y in range(y0, min(y1 + 1, sy)):
        block = int(foundation_id) if y == y0 else int(wall_id)
        out[:, y, :][peri] = block
        if y > y0 and int(accent_id) != int(wall_id):
            xs_c, zs_c = np.where(peri)
            if xs_c.size:
                corners = [
                    (int(xs_c.min()), int(zs_c.min())),
                    (int(xs_c.min()), int(zs_c.max())),
                    (int(xs_c.max()), int(zs_c.min())),
                    (int(xs_c.max()), int(zs_c.max())),
                ]
                peri_set = set(zip(xs_c.tolist(), zs_c.tolist()))
                for cx, cz in corners:
                    if (cx, cz) in peri_set:
                        out[cx, y, cz] = int(accent_id)

    pitched = style_l in (
        "european", "rustic", "western", "chinese", "japanese", "medieval", "fantasy",
    )
    if pitched:
        rise = min(5, max(3, min(bw, bd) // 3 + 1))
        if style_l in ("european", "rustic", "western"):
            plateau = 0.38
        elif style_l in ("chinese", "japanese"):
            plateau = 0.48
        elif style_l in ("medieval", "fantasy"):
            plateau = 0.70
        else:
            plateau = 0.52
        oh = 2 if style_l in ("european", "rustic", "chinese", "western") else 1
        # clear any solid deck first — skin_gable owns the silhouette
        out[x0:x1, y1:sy, z0:z1] = 0
        # restore peri walls up to eave
        for y in range(y0 + 1, min(y1 + 1, sy)):
            out[:, y, :][peri] = int(wall_id)
            if int(accent_id) != int(wall_id):
                xs_c, zs_c = np.where(peri)
                if xs_c.size:
                    corners = [
                        (int(xs_c.min()), int(zs_c.min())),
                        (int(xs_c.min()), int(zs_c.max())),
                        (int(xs_c.max()), int(zs_c.min())),
                        (int(xs_c.max()), int(zs_c.max())),
                    ]
                    peri_set = set(zip(xs_c.tolist(), zs_c.tolist()))
                    for cx, cz in corners:
                        if (cx, cz) in peri_set:
                            out[cx, y, cz] = int(accent_id)
        want_cross = style_l in ("european", "chinese", "rustic")
        cross_band = 0.40 if style_l == "european" else (0.44 if style_l == "chinese" else 0.38)
        roof_count, rinfo = _place_skin_gable_roof(
            out,
            roof_fp=build_box,
            peri=peri,
            eave_y=int(y1),
            roof_id=int(roof_id),
            rise=int(rise),
            plateau_frac=float(plateau),
            overhang=int(oh),
            wall_id=int(wall_id),
            clear_attic=True,
            stairs_id=int(stairs_id or 0),
            cross_gable=bool(want_cross),
            cross_band_frac=float(cross_band),
        )
        ridge_n = _reinforce_ridge_peak(
            out,
            roof_fp=build_box,
            eave_y=int(y1),
            rise=int(rinfo.get("rise") or rise),
            roof_id=int(roof_id),
            ridge_along_x=bool(rinfo.get("ridge_along_x", True)),
            style=style_l,
        )
        if rinfo.get("cross_gable"):
            ridge_n += _reinforce_ridge_peak(
                out,
                roof_fp=build_box,
                eave_y=int(y1),
                rise=int(rinfo.get("cross_rise") or rinfo.get("rise") or rise),
                roof_id=int(roof_id),
                ridge_along_x=bool(rinfo.get("cross_ridge_along_x", not rinfo.get("ridge_along_x", True))),
                style=style_l,
            )
        roof_count += int(ridge_n)
        roof_mode = str(rinfo.get("roof_mode") or "skin_gable")
        roof_stairs = int(rinfo.get("roof_stairs") or 0)
    else:
        # industrial / modern: flat deck + 1-cell eave lip
        out[x0:x1, y1, z0:z1] = int(roof_id)
        oh_n = 0
        for x in range(x0, x1):
            for z in (z0 - 1, z1):
                if 0 <= z < sz and out[x, y1, z] == 0:
                    out[x, y1, z] = int(roof_id)
                    oh_n += 1
        for z in range(z0, z1):
            for x in (x0 - 1, x1):
                if 0 <= x < sx and out[x, y1, z] == 0:
                    out[x, y1, z] = int(roof_id)
                    oh_n += 1
        roof_count = int(bw * bd) + oh_n
        roof_mode = "flat_eave_deck"
        roof_stairs = 0

    door_x = (x0 + x1) // 2
    for yy in range(y0 + 1, min(y0 + 3, sy)):
        out[door_x, yy, z1 - 1] = 0

    part = _place_interior_partitions(
        out,
        build_fp=build_box,
        peri=peri,
        y0=int(y0),
        y1=int(y1),
        wall_id=int(wall_id),
        style=style_l,
    )

    stats = {
        "bbox": [x0, y0, z0, x1, y1, z1],
        "floor_ys": floor_ys,
        "bw": bw,
        "bd": bd,
        "bh": bh,
        "style": style,
        "anti_box": ab_rule.get("anti_box"),
        "roof": int(roof_count),
        "roof_mode": roof_mode,
        "roof_stairs": int(roof_stairs),
        "partition_mode": part.get("mode"),
        "partition_cells": int(part.get("partition_cells") or 0),
        "rooms_est": int(part.get("rooms_est") or 1),
        "role_ids": {
            "wall": int(wall_id),
            "floor": int(floor_id),
            "roof": int(roof_id),
            "foundation": int(foundation_id),
            "accent": int(accent_id),
        },
    }
    return out, stats


def _score_ref(item: dict[str, Any], style: str, terrain: str) -> float:
    """Rank feature_index hits for similar_scaffold retrieval.

    Prefer mcblock + correct mapped_style houses; demote Hack337 challenge/farm/pyramid
    noise even when English path keywords match the query style.
    """
    path = (item.get("source_path") or "").replace(chr(92), "/").lower()
    blob = ((item.get("id") or "") + " " + path).lower()
    score = 0.0
    style_l = (style or "").lower()
    mapped = (item.get("mapped_style") or "").lower()
    # Hard exclude: retagged public_production / farm dumps
    if item.get("exclude_from_residential") or (item.get("exclude_reason") == "public_production"):
        return -50.0

    # Style label (MCBlock ingest sets this correctly; Hack337 often dumps chinese).
    if mapped == style_l and mapped:
        score += 4.0
    elif mapped and mapped != style_l:
        # Wrong label hurts more when it is the notorious chinese dump.
        score -= 1.0 if mapped == "chinese" and style_l != "chinese" else 0.5

    keys = _STYLE_PATH_KEYWORDS.get(style_l, [])
    if keys and any(k in blob for k in keys):
        score += 2.0  # path hint; weaker than mapped+mcblock so English spam cannot dominate

    if any(b in blob for b in _BUILDING_BOOST):
        score += 1.5
    if any(p in blob for p in _BUILDING_PENALTY):
        score -= 4.0

    # Source prior: style-correct MCBlock houses beat Hack337 path spam.
    is_mcblock = "/mcblock/" in path or path.startswith("mcblock") or "raw/mcblock" in path
    is_hack337 = "hack337" in path or "/hack337/" in path
    if is_mcblock:
        score += 4.0
        if mapped == style_l and mapped:
            score += 1.5  # synergy: curated house + correct style
    if is_hack337:
        score -= 1.5
        # Extra demote when Hack337 is chinese-mislabeled for a non-chinese query.
        if mapped == "chinese" and style_l != "chinese":
            score -= 2.0

    mt = (item.get("mapped_terrain") or "").lower()
    if terrain and mt == terrain.lower():
        score += 0.5
    return score


# Block2Vec blend weight for within-style refinement (plan 3).
# Heuristic gaps for mcblock vs challenge are ~8+ points; keep this small so
# embedding cannot re-elevate Hack337 spam over curated houses.
_B2V_BLEND_WEIGHT = 0.85


def _b2v_style_prototype(
    items: list[dict[str, Any]],
    style: str,
    index_path: Path,
    *,
    max_vecs: int = 24,
) -> np.ndarray | None:
    """Mean embedding of high-confidence same-style mcblock houses (fallback: same-style)."""
    from src.app.block2vec_embed import load_embedding

    style_l = (style or "").lower()
    preferred: list[np.ndarray] = []
    fallback: list[np.ndarray] = []
    ranked = sorted(items, key=lambda it: _score_ref(it, style, "flat"), reverse=True)
    for it in ranked:
        mapped = (it.get("mapped_style") or "").lower()
        if mapped != style_l:
            continue
        vec = load_embedding(index_path, it["id"])
        if vec is None:
            continue
        path = (it.get("source_path") or "").replace(chr(92), "/").lower()
        if "mcblock" in path:
            preferred.append(np.asarray(vec, dtype=np.float32))
        else:
            fallback.append(np.asarray(vec, dtype=np.float32))
        if len(preferred) >= max_vecs:
            break
    pool = preferred if preferred else fallback
    if not pool:
        return None
    stack = np.stack(pool[:max_vecs], axis=0)
    proto = stack.mean(axis=0)
    n = float(np.linalg.norm(proto) + 1e-8)
    return (proto / n).astype(np.float32)


def retrieve_style_refs(
    style: str,
    terrain: str = "flat",
    *,
    top_k: int = 3,
    index_dir: str | Path | None = None,
    use_block2vec: bool = True,
    b2v_weight: float | None = None,
) -> list[dict[str, Any]]:
    """Retrieve up to top_k reference feature dicts for a style/terrain.

    Ranking is still driven by plan-2 heuristics (_score_ref + hollow/size).
    When use_block2vec and embeddings exist, add a light cosine-to-prototype
    term among the already-filtered candidate pool for within-style polish.
    """
    from src.app.reference_features import INDEX_DIR_DEFAULT, list_index, load_feature

    root = project_root()
    idx_default = index_dir or INDEX_DIR_DEFAULT
    items = list_index(idx_default)
    if not items:
        return []

    ranked = sorted(items, key=lambda it: _score_ref(it, style, terrain), reverse=True)
    pool_n = max(1, int(top_k) * 5)
    picked: list[dict[str, Any]] = []
    for it in ranked:
        base = _score_ref(it, style, terrain)
        if base < 0.5 and picked:
            break
        try:
            feat = load_feature(it["id"], index_dir=idx_default)
        except Exception:
            continue
        mass = feat.get("massing") or {}
        hollow = float(mass.get("hollow_score") or 0)
        non_air = int((feat.get("overview") or {}).get("non_air") or 0)
        bonus = 0.0
        if hollow >= 0.45:
            bonus += 1.0
        if 500 <= non_air <= 12000:
            bonus += 0.5
        feat["_retrieve_score"] = base + bonus
        feat["_retrieve_base"] = base + bonus
        feat["_b2v_sim"] = None
        picked.append(feat)
        if len(picked) >= pool_n:
            break

    picked.sort(key=lambda f: float(f.get("_retrieve_score") or 0), reverse=True)

    if use_block2vec:
        try:
            from src.app.block2vec_embed import load_embedding, cosine

            idx = Path(idx_default)
            if not idx.is_absolute():
                idx = root / idx
            w = float(_B2V_BLEND_WEIGHT if b2v_weight is None else b2v_weight)
            proto = _b2v_style_prototype(items, style, idx)
            if proto is not None and w != 0.0:
                for f in picked:
                    v = load_embedding(idx, f["id"])
                    if v is None:
                        continue
                    sim = float(cosine(proto, v))
                    f["_b2v_sim"] = sim
                    # Only refine candidates that already cleared the heuristic bar.
                    if float(f.get("_retrieve_base") or 0) >= 0.5:
                        f["_retrieve_score"] = float(f.get("_retrieve_base") or 0) + w * sim
                picked.sort(key=lambda f: float(f.get("_retrieve_score") or 0), reverse=True)
        except Exception:
            pass

    return picked[: max(1, int(top_k))]

def generate_similar_scaffold(
    *,
    style: str = "medieval",
    terrain: str = "flat",
    num: int = 1,
    out_dir: str | Path | None = None,
    seed: int | None = None,
    top_k_refs: int = 3,
    vae_fill: bool = False,
    checkpoint: str | Path | None = None,
    temperature: float = 1.0,
    look_harden_enable: bool = True,
    preserve_windows: bool = True,
    index_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Primary strategy: reference skeleton scaffold (+ look_harden)."""
    from src.app.reference_features import load_skeleton
    from src.app.sample_runner import save_voxels_pair

    root = project_root()
    cfg = load_config(root / "configs/default.yaml")
    palette = load_palette(root / cfg["data"]["palette_path"])
    size = int(cfg["data"]["size"])
    if seed is not None:
        set_seed(int(seed))

    dest = Path(out_dir) if out_dir else root / "outputs" / "similar_scaffold" / ("%s_%s" % (style, terrain))
    if not dest.is_absolute():
        dest = root / dest
    dest.mkdir(parents=True, exist_ok=True)

    refs = retrieve_style_refs(style, terrain, top_k=top_k_refs, index_dir=index_dir)
    strategy_used = "similar_scaffold" if refs else "rule_scaffold"

    vae_samples = None
    if vae_fill:
        try:
            from src.app.sample_runner import generate_samples

            vae_samples = generate_samples(
                num=max(1, int(num)),
                temperature=float(temperature),
                checkpoint=checkpoint,
                out_dir=dest / "_vae_donor",
                seed=seed,
                style=style,
                terrain=terrain,
                structure_constrain=False,
                look_harden_enable=False,
            )
            vae_err = None
        except Exception as ex:
            vae_samples = None
            vae_err = str(ex)
    else:
        vae_err = "disabled"

    results: list[dict[str, Any]] = []
    n = max(1, min(int(num), 8))
    base_seed = int(seed) if seed is not None else int(cfg["seed"])

    for i in range(n):
        meta: dict[str, Any] = {
            "index": i,
            "style": style,
            "terrain": terrain,
            "strategy": strategy_used,
            "vae_fill": bool(vae_fill),
        }
        if refs:
            # 按种子轮换参考：同风格多次生成/批量生成不会总是同一座
            feat = refs[(i + int(base_seed)) % len(refs)]
            meta["reference_id"] = feat.get("id")
            meta["reference_score"] = feat.get("_retrieve_score")
            meta["reference_ids"] = [r.get("id") for r in refs]
            mats = feat.get("materials") or {}
            wall_id, floor_id, mat_info = _resolve_material_ids(
                palette,
                mats.get("remap_targets"),
                style,
                top_blocks=mats.get("top_blocks"),
            )
            roof_id = int(mat_info.get("roof_id") or wall_id)
            foundation_id = int(mat_info.get("foundation_id") or wall_id)
            accent_id = int(mat_info.get("accent_id") or wall_id)
            try:
                occ = load_skeleton(feat)
            except Exception as ex:
                wall_id, floor_id, mat_info = _resolve_material_ids(palette, None, style)
                roof_id = int(mat_info.get("roof_id") or wall_id)
                foundation_id = int(mat_info.get("foundation_id") or wall_id)
                accent_id = int(mat_info.get("accent_id") or wall_id)
                vox, sc_stats = rule_scaffold_voxels(
                    style=style,
                    size=size,
                    seed=base_seed + i,
                    wall_id=wall_id,
                    floor_id=floor_id,
                    roof_id=roof_id,
                    foundation_id=foundation_id,
                    accent_id=accent_id,
                )
                meta["strategy"] = "rule_scaffold"
                meta["scaffold_error"] = str(ex)
                meta["scaffold"] = sc_stats
                meta["materials"] = mat_info
            else:
                mass = feat.get("massing") or {}
                y_peaks = mass.get("y_peaks") or []
                ov = (feat.get("overview") or {}).get("size") or {}
                src_y = int(ov.get("y") or occ.shape[1] or size)
                floor_ys = []
                for yp in y_peaks:
                    if src_y > 1:
                        yy = int(round(float(yp) * (occ.shape[1] - 1) / max(1, src_y - 1)))
                    else:
                        yy = int(yp)
                    floor_ys.append(int(np.clip(yy, 0, occ.shape[1] - 1)))
                if not floor_ys and mass.get("floor_guess"):
                    n_f = max(2, min(6, int(mass.get("floor_guess") or 2)))
                    floor_ys = [
                        int(round(j * (occ.shape[1] - 1) / max(1, n_f - 1))) for j in range(n_f)
                    ]
                # Corner posts: load_bearing if distinct from wall, else accent (logs).
                corner_id = int(mat_info.get('load_bearing_id') or accent_id)
                if corner_id == int(wall_id):
                    corner_id = int(accent_id)
                stairs_id = _resolve_stairs_from_palette(
                    palette, roof_id=int(roof_id), wall_id=int(wall_id), style=style
                )
                vox, sc_stats = scaffold_from_occupancy(
                    occ,
                    wall_id=wall_id,
                    floor_id=floor_id,
                    floor_ys=floor_ys or None,
                    style=style,
                    roof_id=roof_id,
                    foundation_id=foundation_id,
                    accent_id=corner_id,
                    stairs_id=int(stairs_id),
                )
                meta["scaffold"] = sc_stats
                meta["materials"] = mat_info
                meta["skeleton_occ_frac"] = float(np.asarray(occ).mean())
        else:
            wall_id, floor_id, mat_info = _resolve_material_ids(palette, None, style)
            roof_id = int(mat_info.get("roof_id") or wall_id)
            foundation_id = int(mat_info.get("foundation_id") or wall_id)
            accent_id = int(mat_info.get("accent_id") or wall_id)
            stairs_id = _resolve_stairs_from_palette(
                palette, roof_id=int(roof_id), wall_id=int(wall_id), style=style
            )
            vox, sc_stats = rule_scaffold_voxels(
                style=style,
                size=size,
                seed=base_seed + i,
                wall_id=wall_id,
                floor_id=floor_id,
                roof_id=roof_id,
                foundation_id=foundation_id,
                accent_id=accent_id,
                stairs_id=int(stairs_id),
            )
            meta["scaffold"] = sc_stats
            meta["materials"] = mat_info
            meta["strategy"] = "rule_scaffold"

        if vae_fill and vae_samples:
            donor = np.asarray(vae_samples[i % len(vae_samples)]["voxels"], dtype=np.int16)
            if donor.shape == vox.shape:
                mask = (vox > 0) & (donor > 0)
                rng = np.random.default_rng(base_seed + 17 + i)
                take = mask & (rng.random(vox.shape) < 0.55)
                vox = vox.copy()
                vox[take] = donor[take]
                meta["vae_fill_cells"] = int(take.sum())
            else:
                meta["vae_fill_cells"] = 0
                meta["vae_fill_note"] = "shape_mismatch"
        meta["vae_error"] = vae_err

        # Scaffold-aware thresholds: thin shells / sparse roofs fail VAE-era exterior/roof cuts.
        th = dict(SCAFFOLD_THRESHOLDS)
        vox, rep = apply_structure_constraints(vox, mode="repair", thresholds=th)
        meta["structure_pre_look"] = rep.to_dict()
        meta["structure_thresholds"] = "scaffold"
        look_rep = None
        if look_harden_enable:
            role_mats = {
                "wall": int(wall_id),
                "floor": int(floor_id),
                "roof": int(mat_info.get("roof_id") or wall_id),
                "foundation": int(mat_info.get("foundation_id") or wall_id),
                "accent": int(mat_info.get("accent_id") or wall_id),
                "window_frame": int(mat_info.get("window_frame_id") or mat_info.get("accent_id") or wall_id),
                "load_bearing": int(mat_info.get("load_bearing_id") or mat_info.get("accent_id") or wall_id),
            }
            vox, look_rep = look_harden(
                vox,
                palette,
                style=style,
                preserve_windows=bool(preserve_windows),
                place_window_glass=True,
                role_materials=role_mats,
            )
            meta["look_harden"] = look_rep.to_dict()
            # Re-carve hollow core after look_harden (which may re-slab floors)
            try:
                sc = meta.get("scaffold") or {}
                fp = (vox > 0).any(axis=1)
                style_l = (style or "").strip().lower()
                pitched = style_l in ("medieval", "fantasy", "chinese")
                cleared = _force_open_room(
                    vox,
                    fp,
                    floor_ys=list(sc.get("floor_ys") or []),
                    y_foundation=int((sc.get("floor_ys") or [0])[0] if sc.get("floor_ys") else 0),
                    y_roof=int(sc.get("roof_deck_y") or (vox.shape[1] - 2)),
                    wall_id=int(wall_id),
                    min_open=64,
                    floors_only=bool(pitched),
                )
                if cleared:
                    meta["open_room_post_look"] = int(cleared)
                    if isinstance(meta.get("scaffold"), dict):
                        meta["scaffold"]["open_room_post_look"] = int(cleared)
            except Exception as ex:
                meta["open_room_post_look_error"] = str(ex)

        final = check_structure(vox, thresholds=th)
        meta["structure"] = final.to_dict()

        npz_path = dest / ("scaffold_s%s_t%s_%03d.npz" % (style, terrain, i))
        saved = save_voxels_pair(vox, palette, npz_path)
        meta.update(saved)
        meta["voxels"] = vox
        results.append(meta)

    man = {
        "strategy": strategy_used if refs else "rule_scaffold",
        "requested_strategy": "similar_scaffold",
        "style": style,
        "terrain": terrain,
        "num": len(results),
        "vae_fill": bool(vae_fill),
        "references": [r.get("id") for r in refs],
        "outputs": [str(Path(m["npz_path"]).name) for m in results],
    }
    (dest / "strategy_run.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def generate_rule_scaffold(
    *,
    style: str = "medieval",
    terrain: str = "flat",
    num: int = 1,
    out_dir: str | Path | None = None,
    seed: int | None = None,
    look_harden_enable: bool = True,
    preserve_windows: bool = True,
) -> list[dict[str, Any]]:
    """Procedural shell/floors scaffold without reference retrieval."""
    from src.app.sample_runner import save_voxels_pair

    root = project_root()
    cfg = load_config(root / "configs/default.yaml")
    palette = load_palette(root / cfg["data"]["palette_path"])
    size = int(cfg["data"]["size"])
    if seed is not None:
        set_seed(int(seed))
    dest = Path(out_dir) if out_dir else root / "outputs" / "rule_scaffold" / ("%s_%s" % (style, terrain))
    if not dest.is_absolute():
        dest = root / dest
    dest.mkdir(parents=True, exist_ok=True)

    base_seed = int(seed) if seed is not None else int(cfg["seed"])
    wall_id, floor_id, mat_info = _resolve_material_ids(palette, None, style)
    roof_id = int(mat_info.get("roof_id") or wall_id)
    foundation_id = int(mat_info.get("foundation_id") or wall_id)
    accent_id = int(mat_info.get("accent_id") or wall_id)
    role_mats = {
        "wall": int(wall_id),
        "floor": int(floor_id),
        "roof": roof_id,
        "foundation": foundation_id,
        "accent": accent_id,
        "window_frame": int(mat_info.get("window_frame_id") or accent_id),
    }
    results: list[dict[str, Any]] = []
    for i in range(max(1, min(int(num), 8))):
        stairs_id = _resolve_stairs_from_palette(
            palette, roof_id=int(roof_id), wall_id=int(wall_id), style=style
        )
        vox, sc_stats = rule_scaffold_voxels(
            style=style,
            size=size,
            seed=base_seed + i,
            wall_id=wall_id,
            floor_id=floor_id,
            roof_id=roof_id,
            foundation_id=foundation_id,
            accent_id=accent_id,
            stairs_id=int(stairs_id),
        )
        th = dict(SCAFFOLD_THRESHOLDS)
        vox, rep = apply_structure_constraints(vox, mode="repair", thresholds=th)
        look_rep = None
        if look_harden_enable:
            vox, look_rep = look_harden(
                vox,
                palette,
                style=style,
                preserve_windows=bool(preserve_windows),
                place_window_glass=True,
                role_materials=role_mats,
            )
        final = check_structure(vox, thresholds=th)
        npz_path = dest / ("rule_s%s_t%s_%03d.npz" % (style, terrain, i))
        saved = save_voxels_pair(vox, palette, npz_path)
        meta = {
            **saved,
            "index": i,
            "style": style,
            "terrain": terrain,
            "strategy": "rule_scaffold",
            "scaffold": sc_stats,
            "materials": mat_info,
            "structure_pre_look": rep.to_dict(),
            "structure": final.to_dict(),
            "structure_thresholds": "scaffold",
            "voxels": vox,
        }
        if look_rep is not None:
            meta["look_harden"] = look_rep.to_dict()
        results.append(meta)
    return results


def generate_with_strategy(
    strategy: str,
    *,
    style: str = "medieval",
    terrain: str = "flat",
    num: int = 1,
    out_dir: str | Path | None = None,
    seed: int | None = None,
    checkpoint: str | Path | None = None,
    temperature: float = 1.0,
    vae_fill: bool = False,
    look_harden_enable: bool = True,
    preserve_windows: bool = True,
    structure_constrain: bool = True,
    structure_mode: str = "repair",
) -> list[dict[str, Any]]:
    """Dispatch generation by strategy name."""
    s = (strategy or "similar_scaffold").strip().lower()
    if s in ("similar_scaffold", "similar", "scaffold"):
        return generate_similar_scaffold(
            style=style,
            terrain=terrain,
            num=num,
            out_dir=out_dir,
            seed=seed,
            vae_fill=vae_fill,
            checkpoint=checkpoint,
            temperature=temperature,
            look_harden_enable=look_harden_enable,
            preserve_windows=preserve_windows,
        )
    if s in ("rule_scaffold", "rule"):
        return generate_rule_scaffold(
            style=style,
            terrain=terrain,
            num=num,
            out_dir=out_dir,
            seed=seed,
            look_harden_enable=look_harden_enable,
            preserve_windows=preserve_windows,
        )
    if s in ("vae_look", "vae", "default", "cond_vae"):
        from src.app.sample_runner import generate_samples

        root = project_root()
        ckpt = checkpoint
        if ckpt is None:
            preferred = root / "checkpoints" / "cond_last.pt"
            ckpt = preferred if preferred.exists() else root / "checkpoints" / "last.pt"
        results = generate_samples(
            num=num,
            temperature=temperature,
            checkpoint=ckpt,
            out_dir=out_dir,
            seed=seed,
            style=style,
            terrain=terrain,
            structure_constrain=structure_constrain,
            structure_mode=structure_mode,
            look_harden_enable=look_harden_enable,
            preserve_windows=preserve_windows,
        )
        for r in results:
            r["strategy"] = "vae_look"
        return results
    raise ValueError("unknown strategy %r; choose from %s" % (strategy, STRATEGIES))
