# -*- coding: utf-8 -*-
"""Patch block cognition + structure: no cross beams, load path, knowledge, preview slice."""
from __future__ import annotations

from pathlib import Path
import shutil
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
bak_dir = ROOT / "_xfer" / ("bak_block_struct_%s" % stamp)
bak_dir.mkdir(parents=True, exist_ok=True)


def backup(rel: str) -> None:
    src = ROOT / rel
    dst = bak_dir / rel.replace("\\", "/").replace("/", "__")
    shutil.copy2(src, dst)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    backup(rel)
    (ROOT / rel).write_text(text, encoding="utf-8")
    print("WROTE", rel, "chars", len(text))


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit("MISSING %s\n---OLD HEAD---\n%s" % (label, old[:200]))
    return text.replace(old, new, 1)


def patch_gen_strategy() -> None:
    gs = read("src/app/gen_strategy.py")
    gs = must_replace(
        gs,
        "keep_cross: bool = True,\n) -> np.ndarray:\n    \"\"\"Walkable ring (+ optional cross corridor) leaving a large open room in the middle.",
        "keep_cross: bool = False,\n) -> np.ndarray:\n    \"\"\"Walkable ring (+ optional cross corridor) leaving a large open room in the middle.",
        "keep_cross default",
    )
    old = (
        "    # Cross corridor only when the open room is already large (else it fills the hole)\n"
        "    if keep_cross and open_n >= 16 and max_d >= 3:\n"
        "        cx = int(round(float(xs.mean())))\n"
        "        cz = int(round(float(zs.mean())))\n"
        "        for x, z in zip(xs.tolist(), zs.tolist()):\n"
        "            if abs(x - cx) <= 0 or abs(z - cz) <= 0:\n"
        "                ring[x, z] = True\n"
        "        ring &= fp"
    )
    new = (
        "    # Cross corridor OFF by default: X-beams read as scaffolds, not house floors.\n"
        "    # If explicitly enabled, only on very large open cores.\n"
        "    if keep_cross and open_n >= 48 and max_d >= 5:\n"
        "        cx = int(round(float(xs.mean())))\n"
        "        cz = int(round(float(zs.mean())))\n"
        "        for x, z in zip(xs.tolist(), zs.tolist()):\n"
        "            if abs(x - cx) <= 0 or abs(z - cz) <= 0:\n"
        "                ring[x, z] = True\n"
        "        ring &= fp"
    )
    gs = must_replace(gs, old, new, "cross gate")
    gs = gs.replace(
        "use_fp = _ring_floor_mask(use_fp, depth=depth, keep_cross=True)",
        "use_fp = _ring_floor_mask(use_fp, depth=depth, keep_cross=False)",
    )
    gs = gs.replace(
        "ring = _ring_floor_mask(build_box, depth=depth, keep_cross=True)",
        "ring = _ring_floor_mask(build_box, depth=depth, keep_cross=False)",
    )
    old_a = (
        "    # Corner accents on wall height (not roof / foundation)\n"
        "    if build_fp.any() and int(accent_id) > 0 and int(accent_id) != int(wall_id):\n"
        "        xs_c, zs_c = np.where(peri)\n"
        "        # approximate corners: fewer than 4 neighbors in peri 4-neigh\n"
        "        accent_n = 0\n"
        "        for x, z in zip(xs_c.tolist(), zs_c.tolist()):\n"
        "            n4 = 0\n"
        "            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):\n"
        "                xx, zz = x + dx, z + dz\n"
        "                if 0 <= xx < sx and 0 <= zz < sz and peri[xx, zz]:\n"
        "                    n4 += 1\n"
        "            if n4 > 2:\n"
        "                continue\n"
        "            for y in range(y_foundation + 1, min(roof_deck_y, sy - 1) + 1):\n"
        "                if out[x, y, z] == int(wall_id):\n"
        "                    out[x, y, z] = int(accent_id)\n"
        "                    accent_n += 1\n"
        "        stats[\"accent\"] = int(accent_n)"
    )
    new_a = (
        "    # Load-bearing corner posts only (bbox corners snapped to peri).\n"
        "    if build_fp.any() and int(accent_id) > 0 and int(accent_id) != int(wall_id):\n"
        "        xs_c, zs_c = np.where(peri)\n"
        "        accent_n = 0\n"
        "        if xs_c.size:\n"
        "            minx, maxx = int(xs_c.min()), int(xs_c.max())\n"
        "            minz, maxz = int(zs_c.min()), int(zs_c.max())\n"
        "            peri_set = set(zip(xs_c.tolist(), zs_c.tolist()))\n"
        "            corners = [(minx, minz), (minx, maxz), (maxx, minz), (maxx, maxz)]\n"
        "            snapped = []\n"
        "            for cx0, cz0 in corners:\n"
        "                if (cx0, cz0) in peri_set:\n"
        "                    snapped.append((cx0, cz0))\n"
        "                    continue\n"
        "                best, best_d = None, 10**9\n"
        "                for x, z in peri_set:\n"
        "                    d = abs(x - cx0) + abs(z - cz0)\n"
        "                    if d < best_d:\n"
        "                        best_d, best = d, (x, z)\n"
        "                if best is not None and best_d <= 2:\n"
        "                    snapped.append(best)\n"
        "            snapped = list(dict.fromkeys(snapped))\n"
        "            for x, z in snapped:\n"
        "                for y in range(y_foundation + 1, min(roof_deck_y, sy - 1) + 1):\n"
        "                    cur = int(out[x, y, z])\n"
        "                    if cur == int(wall_id) or cur == 0:\n"
        "                        if cur == 0 and not peri[x, z]:\n"
        "                            continue\n"
        "                        out[x, y, z] = int(accent_id)\n"
        "                        accent_n += 1\n"
        "        stats[\"accent\"] = int(accent_n)\n"
        "        stats[\"load_path\"] = \"corner_posts\""
    )
    gs = must_replace(gs, old_a, new_a, "corner accents")
    # pass load_bearing in role_mats
    old_rm = (
        "            role_mats = {\n"
        "                \"wall\": int(wall_id),\n"
        "                \"floor\": int(floor_id),\n"
        "                \"roof\": int(mat_info.get(\"roof_id\") or wall_id),\n"
        "                \"foundation\": int(mat_info.get(\"foundation_id\") or wall_id),\n"
        "                \"accent\": int(mat_info.get(\"accent_id\") or wall_id),\n"
        "                \"window_frame\": int(mat_info.get(\"window_frame_id\") or mat_info.get(\"accent_id\") or wall_id),\n"
        "            }"
    )
    new_rm = (
        "            role_mats = {\n"
        "                \"wall\": int(wall_id),\n"
        "                \"floor\": int(floor_id),\n"
        "                \"roof\": int(mat_info.get(\"roof_id\") or wall_id),\n"
        "                \"foundation\": int(mat_info.get(\"foundation_id\") or wall_id),\n"
        "                \"accent\": int(mat_info.get(\"accent_id\") or wall_id),\n"
        "                \"window_frame\": int(mat_info.get(\"window_frame_id\") or mat_info.get(\"accent_id\") or wall_id),\n"
        "                \"load_bearing\": int(mat_info.get(\"load_bearing_id\") or mat_info.get(\"accent_id\") or wall_id),\n"
        "            }"
    )
    if old_rm in gs:
        gs = must_replace(gs, old_rm, new_rm, "role_mats load")
    else:
        print("WARN role_mats block not exact; skipping")
    write("src/app/gen_strategy.py", gs)


def patch_look_harden() -> None:
    lh = read("src/app/look_harden.py")
    old = (
        "        xs_p, zs_p = np.where(peri & active)\n"
        "        for x, z in zip(xs_p.tolist(), zs_p.tolist()):\n"
        "            for dx in (-1, 0, 1):\n"
        "                for dz in (-1, 0, 1):\n"
        "                    xx, zz = x + dx, z + dz\n"
        "                    if 0 <= xx < sx and 0 <= zz < sz and active[xx, zz]:\n"
        "                        ring[xx, zz] = True\n"
        "        # thin cross corridor for reachability\n"
        "        axs, azs = np.where(active)\n"
        "        if axs.size:\n"
        "            cx = int(round(float(axs.mean())))\n"
        "            cz = int(round(float(azs.mean())))\n"
        "            for x, z in zip(axs.tolist(), azs.tolist()):\n"
        "                if abs(x - cx) <= 0 or abs(z - cz) <= 0:\n"
        "                    ring[x, z] = True\n"
        "        ring &= active\n"
        "        floor_mask = ring\n"
        "        actions.append(\"hollow_floors:ring\")"
    )
    new = (
        "        xs_p, zs_p = np.where(peri & active)\n"
        "        for x, z in zip(xs_p.tolist(), zs_p.tolist()):\n"
        "            for dx in (-1, 0, 1):\n"
        "                for dz in (-1, 0, 1):\n"
        "                    xx, zz = x + dx, z + dz\n"
        "                    if 0 <= xx < sx and 0 <= zz < sz and active[xx, zz]:\n"
        "                        ring[xx, zz] = True\n"
        "        # No X-corridor: cross beams read as scaffolds through the room.\n"
        "        ring &= active\n"
        "        floor_mask = ring\n"
        "        actions.append(\"hollow_floors:ring_no_cross\")"
    )
    lh = must_replace(lh, old, new, "look_harden ring")
    old2 = (
        "    accent_id = int(fill_info.get(\"accent_id\") or wall_id)\n"
        "    if role_materials:\n"
        "        actions.append(\n"
        "            \"role_materials:wall=%s roof=%s floor=%s foundation=%s accent=%s\"\n"
        "            % (\n"
        "                fill_info.get(\"wall_name\"),\n"
        "                _short(palette.get(roof_id, \"?\")),\n"
        "                fill_info.get(\"floor_name\"),\n"
        "                _short(palette.get(foundation_id, \"?\")),\n"
        "                _short(palette.get(accent_id, \"?\")),\n"
        "            )\n"
        "        )"
    )
    new2 = (
        "    accent_id = int(fill_info.get(\"accent_id\") or wall_id)\n"
        "    load_bearing_id = int(\n"
        "        (role_materials or {}).get(\"load_bearing\")\n"
        "        or fill_info.get(\"load_bearing_id\")\n"
        "        or (fill_info.get(\"roles\") or {}).get(\"load_bearing\")\n"
        "        or accent_id\n"
        "    )\n"
        "    if role_materials:\n"
        "        actions.append(\n"
        "            \"role_materials:wall=%s roof=%s floor=%s foundation=%s accent=%s load=%s\"\n"
        "            % (\n"
        "                fill_info.get(\"wall_name\"),\n"
        "                _short(palette.get(roof_id, \"?\")),\n"
        "                fill_info.get(\"floor_name\"),\n"
        "                _short(palette.get(foundation_id, \"?\")),\n"
        "                _short(palette.get(accent_id, \"?\")),\n"
        "                _short(palette.get(load_bearing_id, \"?\")),\n"
        "            )\n"
        "        )"
    )
    lh = must_replace(lh, old2, new2, "load_bearing look")
    old3 = (
        "                role_materials={\n"
        "                    \"wall\": int(wall_id),\n"
        "                    \"floor\": int(floor_id),\n"
        "                    \"roof\": int(roof_id),\n"
        "                    \"foundation\": int(foundation_id),\n"
        "                    \"accent\": int(accent_id),\n"
        "                    \"window_frame\": int(fill_info.get(\"window_frame_id\") or accent_id),\n"
        "                },"
    )
    new3 = (
        "                role_materials={\n"
        "                    \"wall\": int(wall_id),\n"
        "                    \"floor\": int(floor_id),\n"
        "                    \"roof\": int(roof_id),\n"
        "                    \"foundation\": int(foundation_id),\n"
        "                    \"accent\": int(load_bearing_id if load_bearing_id else accent_id),\n"
        "                    \"window_frame\": int(fill_info.get(\"window_frame_id\") or accent_id),\n"
        "                    \"load_bearing\": int(load_bearing_id),\n"
        "                },"
    )
    lh = must_replace(lh, old3, new3, "role pass load")
    write("src/app/look_harden.py", lh)


def patch_scaffold_materials() -> None:
    sm = read("src/app/scaffold_materials.py")
    old = (
        "    \"industrial\": {\n"
        "        \"foundation\": (\"cobbled_deepslate\", \"stone_bricks\", \"gray_concrete\", \"iron_block\"),\n"
        "        \"wall\": (\"gray_concrete\", \"stone_bricks\", \"iron_block\", \"polished_deepslate\"),\n"
        "        \"roof\": (\"black_concrete\", \"iron_block\", \"gray_concrete\", \"deepslate_bricks\"),\n"
        "        \"floor\": (\"smooth_stone\", \"gray_concrete\", \"iron_block\"),\n"
        "        \"accent\": (\"iron_block\", \"copper_block\", \"chain\", \"hopper\"),\n"
        "        \"window_frame\": (\"iron_block\", \"iron_bars\", \"gray_concrete\"),\n"
        "    },"
    )
    new = (
        "    \"industrial\": {\n"
        "        \"foundation\": (\"cobbled_deepslate\", \"stone_bricks\", \"gray_concrete\", \"iron_block\"),\n"
        "        \"wall\": (\"gray_concrete\", \"stone_bricks\", \"iron_block\", \"polished_deepslate\"),\n"
        "        \"roof\": (\"black_concrete\", \"iron_block\", \"gray_concrete\", \"deepslate_bricks\"),\n"
        "        \"floor\": (\"smooth_stone\", \"gray_concrete\", \"iron_block\"),\n"
        "        \"accent\": (\"iron_block\", \"copper_block\", \"polished_deepslate\", \"stone_bricks\"),\n"
        "        \"window_frame\": (\"iron_block\", \"gray_concrete\", \"polished_deepslate\"),\n"
        "        \"load_bearing\": (\"iron_block\", \"polished_deepslate\", \"stone_bricks\"),\n"
        "    },"
    )
    sm = must_replace(sm, old, new, "industrial")
    sm = must_replace(
        sm,
        '_ROLES = ("foundation", "wall", "roof", "floor", "accent", "window_frame")',
        '_ROLES = ("foundation", "wall", "roof", "floor", "accent", "window_frame", "load_bearing")',
        "_ROLES",
    )
    inserts = {
        "european": "        \"load_bearing\": (\"oak_log\", \"spruce_log\", \"stone_bricks\"),\n",
        "rustic": "        \"load_bearing\": (\"oak_log\", \"spruce_log\", \"stripped_oak_log\"),\n",
        "medieval": "        \"load_bearing\": (\"oak_log\", \"spruce_log\", \"stone_bricks\"),\n",
        "modern": "        \"load_bearing\": (\"iron_block\", \"quartz_block\", \"gray_concrete\"),\n",
        "chinese": "        \"load_bearing\": (\"dark_oak_log\", \"spruce_log\", \"stone_bricks\"),\n",
        "western": "        \"load_bearing\": (\"oak_log\", \"spruce_log\", \"stripped_oak_log\"),\n",
        "fantasy": "        \"load_bearing\": (\"dark_oak_log\", \"stone_bricks\", \"spruce_log\"),\n",
        "japanese": "        \"load_bearing\": (\"dark_oak_log\", \"spruce_log\", \"stripped_spruce_log\"),\n",
        "desert": "        \"load_bearing\": (\"cut_sandstone\", \"terracotta\", \"sandstone\"),\n",
        "scifi": "        \"load_bearing\": (\"iron_block\", \"quartz_block\", \"gray_concrete\"),\n",
        "unknown": "        \"load_bearing\": (\"oak_log\", \"spruce_log\", \"stone_bricks\"),\n",
    }
    for style, line in inserts.items():
        marker = "    \"%s\": {" % style
        if marker not in sm:
            print("skip missing style", style)
            continue
        start = sm.find(marker)
        end = sm.find("\n    },", start)
        block = sm[start:end]
        if "\"load_bearing\"" in block:
            print("already has load_bearing", style)
            continue
        # insert before closing of style dict (end points at newline before },)
        sm = sm[:end] + "\n" + line.rstrip("\n") + sm[end:]
        print("inserted load_bearing", style)
    old_r = (
        "    if roles[\"window_frame\"] == roles[\"wall\"]:\n"
        "        roles[\"window_frame\"] = roles[\"accent\"]\n"
        "        role_names[\"window_frame\"] = role_names[\"accent\"]\n"
        "\n"
        "    info[\"roles\"] = dict(roles)"
    )
    new_r = (
        "    if roles[\"window_frame\"] == roles[\"wall\"]:\n"
        "        roles[\"window_frame\"] = roles[\"accent\"]\n"
        "        role_names[\"window_frame\"] = role_names[\"accent\"]\n"
        "    if not roles.get(\"load_bearing\"):\n"
        "        roles[\"load_bearing\"] = int(roles.get(\"accent\") or roles[\"wall\"])\n"
        "        role_names[\"load_bearing\"] = role_names.get(\"accent\") or role_names[\"wall\"]\n"
        "    info[\"load_bearing_id\"] = int(roles[\"load_bearing\"])\n"
        "\n"
        "    info[\"roles\"] = dict(roles)"
    )
    # There may be two similar blocks (before and after diversify). Replace the last occurrence carefully.
    if old_r not in sm:
        # try the post-remap block only
        raise SystemExit("MISSING load_bearing resolve block")
    # replace only the LAST occurrence (after diversify)
    idx = sm.rfind(old_r)
    sm = sm[:idx] + new_r + sm[idx + len(old_r):]
    # Also ensure pick() handles load_bearing via fallbacks - already uses _ROLES loop
    # Ensure fallbacks always have load_bearing key when picking
    write("src/app/scaffold_materials.py", sm)


def main() -> None:
    patch_gen_strategy()
    patch_look_harden()
    patch_scaffold_materials()
    print("CORE PATCH DONE", bak_dir)


if __name__ == "__main__":
    main()
