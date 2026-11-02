# -*- coding: utf-8 -*-
"""Ingest Hack337/Minecraft-Schematics (MIT). LOCAL_ONLY — do not git push blobs."""
from __future__ import annotations
import argparse, json, re, sys, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data.io_vox import save_npz_npz
from src.data.litematic import fit_to_cube, load_litematic
from src.utils import load_config, load_palette, save_palette

def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

def safe_stem(name: str) -> str:
    stem = Path(unquote(name)).stem
    stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem)
    return (stem[:100] or "build").strip("_") or "build"

def ensure_palette(names, palette):
    name_to_id = {v: k for k, v in palette.items()}
    if "minecraft:air" not in name_to_id:
        name_to_id["minecraft:air"] = 0
        palette[0] = "minecraft:air"
    for name in names:
        n = name if ":" in name else f"minecraft:{name}"
        if n not in name_to_id:
            nid = max(palette) + 1 if palette else 1
            palette[nid] = n
            name_to_id[n] = nid
    return name_to_id

def load_blueprint_voxels(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    w, h, d = [int(x) for x in (data.get("size") or [0, 0, 0])]
    pal_map = data.get("palette") or {}
    chars = sorted(c for c in pal_map if c != ".")
    names = ["minecraft:air"]
    char_to_idx = {".": 0}
    for ch in chars:
        block = str(pal_map[ch])
        if not block.startswith("minecraft:"):
            block = f"minecraft:{block}"
        char_to_idx[ch] = len(names)
        names.append(block)
    voxels = np.zeros((w, h, d), dtype=np.int32)
    for y, layer in enumerate((data.get("layers") or [])[:h]):
        for z, row in enumerate(layer[:d]):
            row = row if isinstance(row, str) else "".join(row)
            for x, ch in enumerate(row[:w]):
                if ch != "." and ch in char_to_idx:
                    voxels[x, y, z] = char_to_idx[ch]
    return voxels, names, {"name": path.stem, "size": (w, h, d), "source": str(path)}

def remap(voxels, src_palette, name_to_id):
    out = np.zeros_like(voxels, dtype=np.int16)
    for i, name in enumerate(src_palette):
        n = name if ":" in name else f"minecraft:{name}"
        out[voxels == i] = name_to_id.get(n, name_to_id["minecraft:air"])
    return out

def load_maps(raw_dir: Path):
    smap, qmap = {}, {}
    sp = raw_dir / "schematics_mapping.json"
    if sp.exists():
        for row in json.loads(sp.read_text(encoding="utf-8")):
            if not isinstance(row, dict):
                continue
            stem = Path(unquote(str(row.get("file") or ""))).stem
            smap[stem] = row
            if "_" in stem: smap[stem.split("_")[0]] = row
            if "-" in stem: smap[stem.split("-")[0]] = row
    bp = raw_dir / "blueprints_mapping.jsonl"
    if bp.exists():
        with bp.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try: row = json.loads(line)
                except json.JSONDecodeError: continue
                fn = str(row.get("filename") or "")
                qmap[fn] = qmap[Path(fn).name] = qmap[Path(fn).stem] = row
    return smap, qmap

def guess_tags(text: str):
    t = text.lower(); tags = []
    for tag, keys in [
        ("house", ("house","home","cabin","cottage","villa","hut")),
        ("farm", ("farm","crop","wheat","carrot","animal")),
        ("tower", ("tower","windmill","spire")),
        ("shop", ("shop","store","market","trading")),
        ("redstone", ("redstone","duper","xp","shulker","hopper")),
        ("castle", ("castle","fort","keep","wall")),
        ("starter", ("starter","simple","survival")),
    ]:
        if any(k in t for k in keys): tags.append(tag)
    return tags or ["build"]

def guess_style(text: str):
    t = text.lower(); styles = []
    for sty, keys in [
        ("japanese", ("japanese","torii","zen","sakura")),
        ("chinese", ("chinese","pagoda")),
        ("modern", ("modern","concrete")),
        ("industrial", ("industrial","factory")),
        ("medieval", ("medieval","castle","keep")),
        ("rustic", ("rustic","cabin","spruce","cozy")),
        ("fantasy", ("fantasy","dragon","wizard")),
        ("desert", ("desert","sandstone")),
    ]:
        if any(k in t for k in keys): styles.append(sty)
    return styles or ["unknown"]

def prepare_blueprints(raw_dir, out_dir, size, palette, max_edge_skip):
    out_dir.mkdir(parents=True, exist_ok=True)
    smap, qmap = load_maps(raw_dir)
    rows, stats = [], Counter()
    files = sorted((raw_dir / "blueprints").glob("*.json"))
    for i, src in enumerate(files, 1):
        try:
            vox, spal, meta = load_blueprint_voxels(src)
            sx, sy, sz = meta["size"]
            if max(sx, sy, sz) > max_edge_skip:
                stats["skip_too_large"] += 1
                continue
            n2i = ensure_palette(spal, palette)
            cube = fit_to_cube(remap(vox, spal, n2i), size=size, air_id=n2i["minecraft:air"])
            stem = "h337_" + safe_stem(src.name)
            dst = out_dir / f"{stem}.npz"
            save_npz_npz(dst, cube)
            q = qmap.get(src.name) or qmap.get(src.stem) or {}
            sm = smap.get(src.stem) or smap.get(src.stem.split("_")[0]) or smap.get(src.stem.split("-")[0]) or {}
            title = str(sm.get("name") or q.get("short_name_en") or src.stem)
            query = str(q.get("short_name_en") or "")
            desc = str(sm.get("description") or "")
            blob = f"{title} {query} {desc}"
            tags, styles = guess_tags(blob), guess_style(blob)
            rows.append({
                "file": str(dst.relative_to(ROOT)).replace("\\", "/"),
                "source": str(src.relative_to(ROOT)).replace("\\", "/"),
                "name": title, "orig_size": [sx, sy, sz],
                "non_air": int((cube != n2i["minecraft:air"]).sum()),
                "dataset": "hack337",
                "labels": {
                    "styles": styles, "tags": tags, "primaryType": tags[0],
                    "name": title, "query_en": query, "description": desc[:500],
                    "rare_terrain_hits": [],
                },
            })
            stats["ok"] += 1
            if i % 50 == 0 or i == len(files):
                print(f"[{i}/{len(files)}] OK {src.name} {meta['size']} -> {size}^3")
        except Exception as e:
            stats["fail"] += 1
            print(f"FAIL {src.name}: {e}")
    return rows, stats

def prepare_litematics(raw_dir, out_dir, size, palette, max_edge_skip):
    """Convert schematics/*.litematic with NO blueprint counterpart into npz."""
    out_dir.mkdir(parents=True, exist_ok=True)
    bp_stems = {p.stem.lower() for p in (raw_dir / "blueprints").glob("*.json")}
    smap, qmap = load_maps(raw_dir)
    rows, stats = [], Counter()
    files = sorted((raw_dir / "schematics").glob("*.litematic"))
    todo = [f for f in files if f.stem.lower() not in bp_stems]
    print(f"litematic-only candidates: {len(todo)} / {len(files)}")
    for i, src in enumerate(todo, 1):
        try:
            vox, spal, meta = load_litematic(src)
            sx, sy, sz = meta["size"]
            if max(sx, sy, sz) > max_edge_skip:
                stats["skip_too_large"] += 1
                continue
            n2i = ensure_palette(spal, palette)
            cube = fit_to_cube(remap(vox, spal, n2i), size=size, air_id=n2i["minecraft:air"])
            stem = "h337l_" + safe_stem(src.name)
            dst = out_dir / f"{stem}.npz"
            save_npz_npz(dst, cube)
            q = qmap.get(src.name) or qmap.get(src.stem) or {}
            sm = smap.get(src.stem) or smap.get(src.stem.split("_")[0]) or smap.get(src.stem.split("-")[0]) or {}
            title = str(sm.get("name") or q.get("short_name_en") or src.stem)
            blob = f"{title} {q.get('short_name_en') or ''} {sm.get('description') or ''}"
            tags, styles = guess_tags(blob), guess_style(blob)
            rows.append({
                "file": str(dst.relative_to(ROOT)).replace("\\", "/"),
                "source": str(src.relative_to(ROOT)).replace("\\", "/"),
                "name": title, "orig_size": [sx, sy, sz],
                "non_air": int((cube != n2i["minecraft:air"]).sum()),
                "dataset": "hack337",
                "labels": {
                    "styles": styles, "tags": tags, "primaryType": tags[0],
                    "name": title, "query_en": str(q.get("short_name_en") or ""),
                    "description": str(sm.get("description") or "")[:500],
                    "rare_terrain_hits": [],
                },
            })
            stats["ok"] += 1
            if i % 50 == 0 or i == len(todo):
                print(f"[{i}/{len(todo)}] OK {src.name}")
        except Exception as e:
            stats["fail"] += 1
            if stats["fail"] <= 10:
                print(f"FAIL {src.name}: {e}")
    return rows, stats


def batch_feature_ingest(raw_dir, index_dir, max_edge, max_items):
    from src.app.reference_features import extract_reference_features
    stats = Counter()
    for src in sorted((raw_dir / "schematics").glob("*.litematic")):
        if max_items is not None and stats["ok"] >= max_items:
            break
        try:
            _v, _p, meta = load_litematic(src)
            sx, sy, sz = meta["size"]
            if max(sx, sy, sz) > max_edge:
                stats["skip_too_large"] += 1
                continue
            extract_reference_features(src, skeleton_size=32, index_dir=index_dir, write=True)
            stats["ok"] += 1
            if stats["ok"] % 25 == 0:
                print(f"feature ok={stats['ok']} skip={stats['skip_too_large']}")
        except Exception as e:
            stats["fail"] += 1
            if stats["fail"] <= 10:
                print(f"FAIL feature {src.name}: {e}")
    return stats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/hack337")
    ap.add_argument("--out", default="data/processed/hack337")
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--max-edge-skip", type=int, default=96)
    ap.add_argument("--feature-ingest", action="store_true")
    ap.add_argument("--litematic-npz", action="store_true",
                    help="also convert litematic-only schematics to npz")
    ap.add_argument("--feature-max-edge", type=int, default=64)
    ap.add_argument("--feature-max", type=int, default=None)
    ap.add_argument("--index-dir", default="data/feature_index")
    args = ap.parse_args()
    cfg = load_config(ROOT / args.config)
    size = args.size or int(cfg["data"]["size"])
    raw_dir, out_dir = ROOT / args.raw, ROOT / args.out
    if not (raw_dir / "blueprints").exists():
        raise SystemExit(f"missing {raw_dir}/blueprints")
    palette_path = ROOT / cfg["data"]["palette_path"]
    palette = load_palette(palette_path)
    t0 = time.time()
    print(f"prepare blueprints -> {out_dir} size={size}")
    meta, st = prepare_blueprints(raw_dir, out_dir, size, palette, args.max_edge_skip)
    if args.litematic_npz:
        print("prepare litematic-only schematics -> npz")
        meta_l, st_l = prepare_litematics(raw_dir, out_dir, size, palette, args.max_edge_skip)
        meta += meta_l
        st = st + Counter({f"litematic_{k}": v for k, v in st_l.items()})
    save_palette(palette, palette_path)
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    tags = [{"stem": Path(r["file"]).stem, "name": r.get("name"), "tags": r["labels"]["tags"],
             "styles": r["labels"]["styles"], "query_en": r["labels"].get("query_en"),
             "orig_size": r["orig_size"], "non_air": r["non_air"]} for r in meta]
    (out_dir / "tags.json").write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")
    st_feat = Counter()
    if args.feature_ingest:
        print("batch feature_index...")
        st_feat = batch_feature_ingest(raw_dir, ROOT / args.index_dir, args.feature_max_edge, args.feature_max)
    schem_n = len(list((raw_dir / "schematics").glob("*.schem")))
    report = {
        "blueprints": dict(st), "feature_index": dict(st_feat),
        "npz_written": len(meta), "palette_classes": max(palette) + 1 if palette else 0,
        "elapsed_s": round(time.time() - t0, 1), "size": size,
        "max_edge_skip": args.max_edge_skip, "schem_skipped": schem_n,
        "license": "MIT (upstream README license: mit)",
        "dataset": "Hack337/Minecraft-Schematics",
        "url": "https://huggingface.co/datasets/Hack337/Minecraft-Schematics",
        "ingested_at": now(),
    }
    card = {
        "dataset": report["dataset"], "url": report["url"], "license": report["license"],
        "local_path": "data/raw/hack337", "processed_path": "data/processed/hack337",
        "ingested_at": report["ingested_at"],
        "notes": [
            "Blueprints -> 32^3 npz for VAE",
            ".schem not parsed; use blueprint/litematic",
            "dataset_openai.jsonl is chat FT only",
            "LOCAL_ONLY: do not commit/push raw blobs",
        ],
        "report": report,
    }
    (raw_dir / "INGEST_STATUS.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "SOURCE.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "INGEST_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== done ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
