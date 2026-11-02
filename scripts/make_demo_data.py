"""生成一批合成小屋，用来验证训练链路（无需外部数据集）。"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils import load_palette, save_palette


def house(size: int, rng: random.Random) -> list[list]:
    blocks: list[list] = []
    w = rng.randint(max(6, size // 4), max(7, size // 2))
    d = rng.randint(max(6, size // 4), max(7, size // 2))
    h = rng.randint(4, max(5, size // 3))
    x0 = (size - w) // 2
    z0 = (size - d) // 2
    y0 = 0

    wall = rng.choice(["minecraft:oak_planks", "minecraft:cobblestone", "minecraft:bricks"])
    roof = "minecraft:oak_stairs"
    floor = "minecraft:oak_planks"

    for x in range(x0, x0 + w):
        for z in range(z0, z0 + d):
            blocks.append([floor, x, y0, z])

    for y in range(y0 + 1, y0 + h):
        for x in range(x0, x0 + w):
            for z in range(z0, z0 + d):
                edge = x in (x0, x0 + w - 1) or z in (z0, z0 + d - 1)
                if edge:
                    # 简单门洞
                    if y < y0 + 3 and x == x0 + w // 2 and z == z0:
                        continue
                    # 窗户
                    if y == y0 + 2 and (
                        (x == x0 and z == z0 + d // 2) or (x == x0 + w - 1 and z == z0 + d // 2)
                    ):
                        blocks.append(["minecraft:glass", x, y, z])
                    else:
                        blocks.append([wall, x, y, z])

    roof_y = y0 + h
    for x in range(x0 - 1, x0 + w + 1):
        for z in range(z0 - 1, z0 + d + 1):
            if 0 <= x < size and 0 <= z < size and roof_y < size:
                blocks.append([roof if (x + z) % 2 == 0 else "minecraft:oak_slab", x, roof_y, z])

    # 四角立柱
    for x, z in [(x0, z0), (x0 + w - 1, z0), (x0, z0 + d - 1), (x0 + w - 1, z0 + d - 1)]:
        for y in range(y0, min(y0 + h, size)):
            blocks.append(["minecraft:oak_log", x, y, z])
    return blocks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=64)
    parser.add_argument("--size", type=int, default=32)
    parser.add_argument("--out", type=str, default="data/raw")
    args = parser.parse_args()

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    palette_path = ROOT / "data" / "palette.json"
    palette = load_palette(palette_path)
    # 保证 demo 用到的方块都在
    needed = [
        "minecraft:air",
        "minecraft:oak_planks",
        "minecraft:cobblestone",
        "minecraft:bricks",
        "minecraft:oak_log",
        "minecraft:glass",
        "minecraft:oak_stairs",
        "minecraft:oak_slab",
    ]
    name_to_id = {v: k for k, v in palette.items()}
    for name in needed:
        if name not in name_to_id:
            nid = max(palette) + 1
            palette[nid] = name
            name_to_id[name] = nid
    save_palette(palette, palette_path)

    rng = random.Random(42)
    for i in range(args.count):
        payload = {"size": args.size, "blocks": house(args.size, rng)}
        path = out / f"demo_house_{i:04d}.vox.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"已生成 {args.count} 个合成小屋 → {out}")
    print("下一步：python scripts/prepare_data.py --size", args.size)


if __name__ == "__main__":
    main()
