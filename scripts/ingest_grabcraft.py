# -*- coding: utf-8 -*-
"""Ingest GrabCraft blueprints (mattismegevand/minecraft_builds, MIT).

Input : data/raw/grabcraft/structures.npz (converted from parquet, see RAW_META.json)
Output: data/processed/grabcraft/*.npz (32^3, project palette ids) + meta/tags/report.

GrabCraft material names are human-readable ("Oak Wood Plank", "White Stained
Clay", "Torch (Facing Up)"); map_grabcraft_name() normalizes them to canonical
minecraft: ids. Unmapped names -> air (stats printed at end).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.data.io_vox import save_npz_npz
from src.data.litematic import fit_to_cube
from src.utils import load_config, load_palette, save_palette
from ingest_hack337 import ensure_palette, guess_style, guess_tags, safe_stem

# ---------------------------------------------------------------- name mapping

_TREE = ("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove",
          "cherry", "crimson", "warped")

_DOUBLE_SLAB = {
    "double_stone_slab": "smooth_stone",
    "smooth_double_stone_slab": "smooth_stone",
    "double_stone_brick_slab": "stone_bricks",
    "double_spruce_wood_slab": "spruce_planks",
    "double_oak_wood_slab": "oak_planks",
    "double_birch_wood_slab": "birch_planks",
    "double_jungle_wood_slab": "jungle_planks",
    "double_acacia_wood_slab": "acacia_planks",
    "double_dark_oak_wood_slab": "dark_oak_planks",
    "double_quartz_slab": "quartz_block",
    "double_cobblestone_slab": "cobblestone",
    "double_brick_slab": "bricks",
    "double_sandstone_slab": "sandstone",
    "double_red_sandstone_slab": "red_sandstone",
    "double_nether_brick_slab": "nether_bricks",
    "double_purpur_slab": "purpur_block",
    "double_wooden_slab": "oak_planks",
}

_OVERRIDES = {
    "grass": "grass_block",
    "clay": "clay",
    "hardened_clay": "terracotta",
    "moss_stone": "mossy_cobblestone",
    "mossy_stone_bricks": "mossy_stone_bricks",
    "nether_brick": "nether_bricks",
    "block_of_coal": "coal_block",
    "iron_bars": "iron_bars",
    "still_water": "water",
    "water": "water",
    "still_lava": "lava",
    "lava": "lava",
    "snow": "snow",
    "snow_block": "snow_block",
    "snow_one_layer": "snow",
    "wooden_slab": "oak_slab",
    "wooden_stairs": "oak_stairs",
    "wooden_trapdoor": "oak_trapdoor",
    "wooden_fence": "oak_fence",
    "wooden_door": "oak_door",
    "cobblestone_upper": "cobblestone_slab",
    "bricks_upper": "brick_slab",
    "stone_wooden_slab": "stone_slab",
    "stone_brick_monster_egg": "stone_bricks",
    "cobblestone_monster_egg": "cobblestone",
    "stone_monster_egg": "stone",
    "chiseled_quartz_block": "chiseled_quartz_block",
    "pillar_quartz_block": "quartz_pillar",
    "hay_bale": "hay_block",
    "bone_block": "bone_block",
    "redstone_lamp": "redstone_lamp",
    "redstone_lamp_active": "redstone_lamp",
    "sea_lantern": "sea_lantern",
    "lapis_lazuli_block": "lapis_block",
    "slime_block": "slime_block",
    "end_stone": "end_stone",
    "end_bricks": "end_stone_bricks",
    "mycelium": "mycelium",
    "coarse_dirt": "coarse_dirt",
    "podzol": "podzol",
    "soul_sand": "soul_sand",
    "cobweb": "cobweb",
    "dandelion": "dandelion",
    "poppy": "poppy",
    "dead_bush": "dead_bush",
    "tall_grass": "tall_grass",
    "large_fern": "large_fern",
    "farmland": "farmland",
    "carrots": "carrots",
    "wheat": "wheat",
    "potatoes": "potatoes",
    "beetroots": "beetroots",
    "pumpkin": "pumpkin",
    "carved_pumpkin": "carved_pumpkin",
    "jack_olantern": "jack_o_lantern",
    "jack_o_lantern": "jack_o_lantern",
    "melon": "melon",
    "cactus": "cactus",
    "sugar_cane": "sugar_cane",
    "brown_mushroom": "brown_mushroom",
    "red_mushroom": "red_mushroom",
    "mushroom_stem": "mushroom_stem",
    "sponge": "sponge",
    "wet_sponge": "wet_sponge",
    "dispenser": "dispenser",
    "dropper": "dropper",
    "hopper": "hopper",
    "chest": "chest",
    "trapped_chest": "trapped_chest",
    "ender_chest": "ender_chest",
    "furnace": "furnace",
    "crafting_table": "crafting_table",
    "workbench": "crafting_table",
    "enchantment_table": "enchanting_table",
    "enchanting_table": "enchanting_table",
    "anvil": "anvil",
    "beacon": "beacon",
    "brewing_stand": "brewing_stand",
    "cauldron": "cauldron",
    "flower_pot": "flower_pot",
    "sign": "oak_sign",
    "wall_sign": "oak_sign",
    "ladder": "ladder",
    "rail": "rail",
    "powered_rail": "powered_rail",
    "detector_rail": "detector_rail",
    "activator_rail": "activator_rail",
    "lever": "lever",
    "stone_button": "stone_button",
    "wooden_button": "oak_button",
    "oak_button": "oak_button",
    "stone_pressure_plate": "stone_pressure_plate",
    "wooden_pressure_plate": "oak_pressure_plate",
    "weighted_pressure_plate_light": "light_weighted_pressure_plate",
    "weighted_pressure_plate_heavy": "heavy_weighted_pressure_plate",
    "tripwire_hook": "tripwire_hook",
    "redstone_torch": "redstone_torch",
    "redstone_wire": "redstone_wire",
    "repeater": "repeater",
    "comparator": "comparator",
    "piston": "piston",
    "sticky_piston": "sticky_piston",
    "observer": "observer",
    "tnt": "tnt",
    "note_block": "note_block",
    "jukebox": "jukebox",
    "barrier": "barrier",
    "command_block": "command_block",
    "structure_block": "structure_block",
    "end_rod": "end_rod",
    "chorus_plant": "chorus_plant",
    "chorus_flower": "chorus_flower",
    "dragon_egg": "dragon_egg",
    "skull": "skeleton_skull",
    "head": "skeleton_skull",
    "banner": "white_banner",
    "flag": "white_banner",
    "bed": "red_bed",
    "cake": "cake",
    "item_frame": "item_frame",
    "painting": "painting",
    "armor_stand": "armor_stand",
    "end_gateway": "end_gateway",
    "end_portal": "end_portal",
    "end_portal_frame": "end_portal_frame",
    "nether_portal": "nether_portal",
    "fire": "fire",
    "lava_cauldron": "lava_cauldron",
    "water_cauldron": "water_cauldron",
    "bell": "bell",
    "lantern": "lantern",
    "campfire": "campfire",
    "barrel": "barrel",
    "smoker": "smoker",
    "blast_furnace": "blast_furnace",
    "cartography_table": "cartography_table",
    "fletching_table": "fletching_table",
    "smithing_table": "smithing_table",
    "loom": "loom",
    "stonecutter": "stonecutter",
    "grindstone": "grindstone",
    "lectern": "lectern",
    "composter": "composter",
    "beehive": "beehive",
    "bee_nest": "bee_nest",
    "honey_block": "honey_block",
    "honeycomb_block": "honeycomb_block",
    "chain": "chain",
    "lightning_rod": "lightning_rod",
    "candle": "candle",
    "amethyst_block": "amethyst_block",
    "copper_block": "copper_block",
    "raw_iron_block": "raw_iron_block",
    "raw_gold_block": "raw_gold_block",
    "diamond_block": "diamond_block",
    "emerald_block": "emerald_block",
    "redstone_block": "redstone_block",
    "netherite_block": "netherite_block",
    "glow_lichen": "glow_lichen",
    "moss_block": "moss_block",
    "moss_carpet": "moss_carpet",
    "dripstone_block": "dripstone_block",
    "pointed_dripstone": "pointed_dripstone",
    "magma_block": "magma_block",
    "blackstone": "blackstone",
    "polished_blackstone": "polished_blackstone",
    "polished_blackstone_bricks": "polished_blackstone_bricks",
    "cracked_polished_blackstone_bricks": "cracked_polished_blackstone_bricks",
    "gilded_blackstone": "gilded_blackstone",
    "basalt": "basalt",
    "polished_basalt": "polished_basalt",
    "smooth_basalt": "smooth_basalt",
    "nether_wart_block": "nether_wart_block",
    "warped_wart_block": "warped_wart_block",
    "shroomlight": "shroomlight",
    "crimson_nylium": "crimson_nylium",
    "warped_nylium": "warped_nylium",
    "crying_obsidian": "crying_obsidian",
    "respawn_anchor": "respawn_anchor",
    "lodestone": "lodestone",
    "target": "target",
    "ancient_debris": "ancient_debris",
    "nether_gold_ore": "nether_gold_ore",
    "nether_quartz_ore": "nether_quartz_ore",
    "coal_ore": "coal_ore",
    "iron_ore": "iron_ore",
    "gold_ore": "gold_ore",
    "diamond_ore": "diamond_ore",
    "emerald_ore": "emerald_ore",
    "lapis_ore": "lapis_ore",
    "redstone_ore": "redstone_ore",
    "copper_ore": "copper_ore",
    "bookshelf": "bookshelf",
    "chiseled_stone_bricks": "chiseled_stone_bricks",
    "cracked_stone_bricks": "cracked_stone_bricks",
    "chiseled_sandstone": "chiseled_sandstone",
    "chiseled_red_sandstone": "chiseled_red_sandstone",
    "cut_sandstone": "cut_sandstone",
    "cut_red_sandstone": "cut_red_sandstone",
    "smooth_sandstone": "smooth_sandstone",
    "smooth_red_sandstone": "smooth_red_sandstone",
    "smooth_stone": "smooth_stone",
    "smooth_quartz": "smooth_quartz",
    "polished_andesite": "polished_andesite",
    "polished_diorite": "polished_diorite",
    "polished_granite": "polished_granite",
    "andesite": "andesite",
    "diorite": "diorite",
    "granite": "granite",
    "obsidian": "obsidian",
    "bedrock": "bedrock",
    "glowstone": "glowstone",
    "gravel": "gravel",
    "sand": "sand",
    "red_sand": "red_sand",
    "ice": "ice",
    "packed_ice": "packed_ice",
    "blue_ice": "blue_ice",
    "frosted_ice": "frosted_ice",
    "prismarine": "prismarine",
    "prismarine_bricks": "prismarine_bricks",
    "dark_prismarine": "dark_prismarine",
    "netherrack": "netherrack",
    "purpur_block": "purpur_block",
    "purpur_pillar": "purpur_pillar",
    "terracotta": "terracotta",
    "vine": "vine",
    "vines": "vine",
    "lily_pad": "lily_pad",
    "torch": "torch",
    "ladder": "ladder",
    "glass": "glass",
    "glass_pane": "glass_pane",
    "iron_block": "iron_block",
    "gold_block": "gold_block",
    "bricks": "bricks",
    "stone": "stone",
    "dirt": "dirt",
    "cobblestone": "cobblestone",
    "sandstone": "sandstone",
    "red_sandstone": "red_sandstone",
    "quartz_block": "quartz_block",
    "stone_bricks": "stone_bricks",
    "cobblestone_wall": "cobblestone_wall",
    "mossy_cobblestone_wall": "mossy_cobblestone_wall",
    "nether_brick_fence": "nether_brick_fence",
    "end_stone_bricks": "end_stone_bricks",
}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return re.sub(r"_+", "_", s)


def map_grabcraft_name(raw: str) -> str | None:
    """GrabCraft display name -> minecraft id (no namespace). None => drop."""
    s = raw.strip()
    # "(Jungle Wood, Upper)" style slab entries
    m = re.match(r"^\((\w+)\s+wood,\s*(upper|bottom)\)$", s, re.I)
    if m:
        return f"{m.group(1).lower()}_slab"
    # drop a leading "(...)" qualifier group, e.g. "(Stone) Wooden Slab (Upper)"
    s = re.sub(r"^\([^)]*\)\s*", "", s)
    # cut variant suffixes: " (...)", ", Facing ...", ", Upside-down" etc.
    base = re.split(r"\s*\(|,\s*(?:facing|upside|normal|axis|only|no |check|inactive|active|open|closed|hinge|water|oriented)",
                    s, flags=re.I)[0]
    slug = _slug(base)
    if not slug:
        return None
    if slug in _DOUBLE_SLAB:
        return _DOUBLE_SLAB[slug]
    if slug in _OVERRIDES:
        return _OVERRIDES[slug]
    # word-level normalisation
    slug = slug.replace("stained_clay", "terracotta")
    slug = re.sub(r"_wood_plank$", "_planks", slug)
    slug = re.sub(r"_wood_planks$", "_planks", slug)
    slug = re.sub(r"_wood_stairs$", "_stairs", slug)
    slug = re.sub(r"_wood_slab$", "_slab", slug)
    slug = re.sub(r"_wood_fence$", "_fence", slug)
    slug = re.sub(r"_wood_trapdoor$", "_trapdoor", slug)
    slug = re.sub(r"_wood_door$", "_door", slug)
    slug = re.sub(r"_wood_button$", "_button", slug)
    slug = re.sub(r"_wood_pressure_plate$", "_pressure_plate", slug)
    slug = re.sub(r"_wood_leaves.*$", "_leaves", slug)
    for t in _TREE:
        if slug == f"{t}_wood":
            return f"{t}_log"
        if slug == f"{t}_wood_bark" or slug == f"{t}_bark":
            return f"{t}_wood"
    if slug.endswith("_upper") or slug.endswith("_bottom"):
        slug = slug.rsplit("_", 1)[0]
    return slug or None


# ---------------------------------------------------------------- ingest

def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_voxels(d, i0, i1, mat_names, mapped_ids, air_local=0):
    """Build (X,Y,Z) local-palette voxel grid for one structure."""
    xs = d["x"][i0:i1].astype(np.int32)
    ys = d["y"][i0:i1].astype(np.int32)
    zs = d["z"][i0:i1].astype(np.int32)
    ms = d["mat_idx"][i0:i1]
    x0, y0, z0 = xs.min(), ys.min(), zs.min()
    sx, sy, sz = xs.max() - x0 + 1, ys.max() - y0 + 1, zs.max() - z0 + 1
    vox = np.zeros((sx, sy, sz), dtype=np.int32)
    vox[xs - x0, ys - y0, zs - z0] = [mapped_ids.get(mat_names[m], 0) for m in ms]
    return vox, (int(sx), int(sy), int(sz))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/grabcraft/structures.npz")
    ap.add_argument("--out", default="data/processed/grabcraft")
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--max-edge-skip", type=int, default=96)
    ap.add_argument("--min-edge", type=int, default=6)
    ap.add_argument("--min-non-air", type=int, default=200)
    ap.add_argument("--max-items", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config(ROOT / args.config)
    size = args.size or int(cfg["data"]["size"])
    raw_path, out_dir = ROOT / args.raw, ROOT / args.out
    if not raw_path.exists():
        raise SystemExit(f"missing {raw_path} (run parquet conversion first)")
    out_dir.mkdir(parents=True, exist_ok=True)
    palette_path = ROOT / cfg["data"]["palette_path"]
    palette = load_palette(palette_path)

    d = {k: v for k, v in np.load(raw_path, allow_pickle=False).items()}  # eager: npz members decompress per access
    structure_names = [str(s) for s in d["structure_names"]]
    mat_names = [str(s) for s in d["mat_names"]]
    offsets = d["offsets"]

    # map every unique material once
    mapped_ids: dict[str, int] = {}
    unmapped: Counter[str] = Counter()
    name_to_id = None
    for m in mat_names:
        mc = map_grabcraft_name(m)
        if mc is None:
            unmapped[m] += 0  # counted later with weights
            continue
        full = f"minecraft:{mc}"
        name_to_id = ensure_palette([full], palette)
        mapped_ids[m] = name_to_id[full]
    name_to_id = ensure_palette([], palette)
    air_id = name_to_id["minecraft:air"]
    print(f"materials: {len(mat_names)} unique -> {len(mapped_ids)} mapped, "
          f"{len(mat_names) - len(mapped_ids)} dropped")

    t0 = time.time()
    rows, stats = [], Counter()
    dropped_mats: Counter[str] = Counter()
    n_struct = len(structure_names)
    for si in range(n_struct):
        if args.max_items is not None and stats["ok"] >= args.max_items:
            break
        name = structure_names[si]
        i0, i1 = int(offsets[si]), int(offsets[si + 1])
        if i1 <= i0:
            stats["skip_empty"] += 1
            continue
        try:
            vox, (sx, sy, sz) = build_voxels(d, i0, i1, mat_names, mapped_ids)
            edge = max(sx, sy, sz)
            if edge > args.max_edge_skip:
                stats["skip_too_large"] += 1
                continue
            if edge < args.min_edge:
                stats["skip_too_small"] += 1
                continue
            cube = fit_to_cube(vox, size=size, air_id=0)
            non_air = int((cube != 0).sum())
            if non_air < args.min_non_air:
                stats["skip_sparse"] += 1
                continue
            stem = "gc_" + safe_stem(name)
            dst = out_dir / f"{stem}.npz"
            save_npz_npz(dst, cube)
            blob = name.replace("-", " ")
            tags, styles = guess_tags(blob), guess_style(blob)
            rows.append({
                "file": str(dst.relative_to(ROOT)).replace("\\", "/"),
                "source": f"grabcraft:{name}",
                "name": name,
                "orig_size": [sx, sy, sz],
                "non_air": non_air,
                "dataset": "grabcraft",
                "labels": {
                    "styles": styles, "tags": tags, "primaryType": tags[0],
                    "name": name, "query_en": blob, "description": "",
                    "rare_terrain_hits": [],
                },
            })
            stats["ok"] += 1
            if stats["ok"] % 500 == 0:
                print(f"[{si + 1}/{n_struct}] ok={stats['ok']}")
        except Exception as e:
            stats["fail"] += 1
            if stats["fail"] <= 10:
                print(f"FAIL {name}: {e}")

    # stats on dropped materials (weighted by block count)
    used = Counter()
    for m in mat_names:
        if m not in mapped_ids:
            used[m] = 0
    ms_all = d["mat_idx"]
    for mi, m in enumerate(mat_names):
        if m not in mapped_ids:
            dropped_mats[m] += int((ms_all == mi).sum())

    save_palette(palette, palette_path)
    (out_dir / "meta.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tags = [{"stem": Path(r["file"]).stem, "name": r["name"], "tags": r["labels"]["tags"],
             "styles": r["labels"]["styles"], "orig_size": r["orig_size"],
             "non_air": r["non_air"]} for r in rows]
    (out_dir / "tags.json").write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "structures_total": n_struct, "npz_written": len(rows),
        "stats": dict(stats),
        "materials": {"unique": len(mat_names), "mapped": len(mapped_ids),
                      "dropped_unique": len(dropped_mats),
                      "dropped_blocks": sum(dropped_mats.values()),
                      "top_dropped": dropped_mats.most_common(30)},
        "palette_classes": max(palette) + 1 if palette else 0,
        "size": size, "max_edge_skip": args.max_edge_skip,
        "elapsed_s": round(time.time() - t0, 1),
        "dataset": "mattismegevand/minecraft_builds (grabcraft.com)",
        "license": "MIT",
        "url": "https://huggingface.co/datasets/mattismegevand/minecraft_builds",
        "ingested_at": now(),
    }
    card = {
        "dataset": report["dataset"], "url": report["url"], "license": "MIT",
        "local_path": "data/raw/grabcraft", "processed_path": "data/processed/grabcraft",
        "ingested_at": report["ingested_at"],
        "notes": [
            "parquet -> structures.npz (offline conversion)",
            "GrabCraft display names mapped to canonical minecraft ids",
            "unmapped materials -> air (see report.top_dropped)",
            "LOCAL_ONLY: do not commit/push raw blobs",
        ],
        "report": report,
    }
    (out_dir / "SOURCE.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "INGEST_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== done ===")
    print(json.dumps({k: v for k, v in report.items() if k != "materials"}, ensure_ascii=False, indent=2))
    print("dropped materials (unique):", len(dropped_mats), "blocks:", sum(dropped_mats.values()))
    for m, c in dropped_mats.most_common(15):
        print(f"  drop {c:>7}  {m}")


if __name__ == "__main__":
    main()
