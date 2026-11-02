"""把 data/raw 转为统一尺寸 .npz。

支持：
- *.vox.json（合成/手工）
- *.litematic（MCBlock / Litematica）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.io_vox import load_vox_json, save_npz_npz
from src.data.litematic import fit_to_cube, load_litematic
from src.utils import load_config, load_palette, save_palette


def _ensure_palette(names: list[str], palette: dict[int, str]) -> dict[str, int]:
    name_to_id = {v: k for k, v in palette.items()}
    if "minecraft:air" not in name_to_id:
        name_to_id["minecraft:air"] = 0
        palette[0] = "minecraft:air"
    for name in names:
        if name not in name_to_id:
            nid = max(palette) + 1 if palette else 1
            palette[nid] = name
            name_to_id[name] = nid
    return name_to_id


def _remap(voxels, src_palette: list[str], name_to_id: dict[str, int]):
    import numpy as np

    out = np.zeros_like(voxels, dtype=np.int16)
    for i, name in enumerate(src_palette):
        out[voxels == i] = name_to_id[name]
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--size", type=int, default=None)
    parser.add_argument("--raw", default="data/raw")
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--from-mcblock",
        action="store_true",
        help="只处理 data/raw/mcblock 下的投影",
    )
    parser.add_argument("--max-edge-skip", type=int, default=96, help="原始任一边超过则跳过")
    args = parser.parse_args()

    cfg = load_config(ROOT / args.config)
    size = args.size or int(cfg["data"]["size"])
    raw_dir = ROOT / ("data/raw/mcblock" if args.from_mcblock else args.raw)
    out_dir = ROOT / (args.out or cfg["data"]["processed_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    palette_path = ROOT / cfg["data"]["palette_path"]
    palette = load_palette(palette_path)
    name_to_id = {v: k for k, v in palette.items()}

    vox_files = sorted(raw_dir.rglob("*.vox.json"))
    lit_files = sorted(raw_dir.rglob("*.litematic"))
    if not vox_files and not lit_files:
        raise SystemExit(
            f"{raw_dir} 没有 .vox.json / .litematic。\n"
            "合成数据：python scripts/make_demo_data.py\n"
            "MCBlock：python scripts/fetch_mcblock.py"
        )

    meta_rows = []
    n_ok = 0

    for src in vox_files:
        voxels = load_vox_json(src, size=size, name_to_id=name_to_id)
        stem = src.name.removesuffix(".vox.json") if src.name.endswith(".vox.json") else src.stem
        dst = out_dir / f"{stem}.npz"
        save_npz_npz(dst, voxels)
        n_ok += 1
        print(f"OK json {src.name} non_air={(voxels > 0).sum()}")

    for src in lit_files:
        try:
            voxels_idx, src_pal, meta = load_litematic(src)
            sx, sy, sz = meta["size"]
            if max(sx, sy, sz) > args.max_edge_skip:
                print(f"SKIP 太大 {src.name} size={meta['size']}")
                continue
            name_to_id = _ensure_palette(src_pal, palette)
            remapped = _remap(voxels_idx, src_pal, name_to_id)
            air_id = name_to_id["minecraft:air"]
            cube = fit_to_cube(remapped, size=size, air_id=air_id)
            stem = src.stem
            dst = out_dir / f"{stem}.npz"
            save_npz_npz(dst, cube)
            row = {
                "file": str(dst.relative_to(ROOT)),
                "source": str(src.relative_to(ROOT)),
                "name": meta.get("name"),
                "orig_size": meta["size"],
                "non_air": int((cube != air_id).sum()),
            }
            # 若有 MCBlock manifest，附带标签
            man = src.parent / "manifest.json"
            if man.exists():
                try:
                    for m in json.loads(man.read_text(encoding="utf-8")):
                        if Path(m.get("file", "")).name == src.name or src.name.startswith(
                            str(m.get("name", ""))[:20]
                        ):
                            row["labels"] = {
                                "styles": m.get("styles"),
                                "difficulty": m.get("difficulty"),
                                "tags": m.get("tags"),
                                "primaryType": m.get("primaryType"),
                                "name": m.get("name"),
                                "rare_terrain_hits": m.get("rare_terrain_hits") or [],
                            }
                            break
                except Exception:
                    pass
            meta_rows.append(row)
            n_ok += 1
            print(
                f"OK lit {src.name} {meta['size']} -> {size}^3 non_air={row['non_air']}"
            )
        except Exception as e:
            print(f"FAIL {src.name}: {e}")

    save_palette(palette, palette_path)
    if meta_rows:
        (out_dir / "meta.json").write_text(
            json.dumps(meta_rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"done: {n_ok} -> {out_dir}  size={size}  classes={max(palette)+1}")
    print("next: python scripts/train.py")


if __name__ == "__main__":
    main()
