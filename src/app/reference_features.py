# -*- coding: utf-8 -*-
"""Phase 3: extract reference features from .litematic analyze + 32^3 skeleton."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from src.app.schematic_analyze import analyze_litematic
from src.data.litematic import load_litematic
from src.data.labels import load_vocab, resolve_style_id, resolve_terrain_id

# reuse design brief keyword maps lightly
from src.app.design_brief import _STYLE_KEYWORDS, _heuristic_from_text

INDEX_DIR_DEFAULT = "data/feature_index"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _short(name: str) -> str:
    n = str(name).replace("minecraft:", "")
    if n.startswith("block.minecraft."):
        n = n[len("block.minecraft.") :]
    return n


def _stem_id(path: Path) -> str:
    stem = path.stem
    # keep readable id
    safe = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem)
    return safe[:120] or hashlib.sha1(stem.encode("utf-8")).hexdigest()[:12]


def downsample_occupancy(
    voxels: np.ndarray,
    target: int = 32,
) -> np.ndarray:
    """Max-pool occupancy to target^3 boolean (True=solid)."""
    v = np.asarray(voxels)
    sx, sy, sz = v.shape
    solid = v > 0 if np.issubdtype(v.dtype, np.integer) else v.astype(bool)
    out = np.zeros((target, target, target), dtype=np.bool_)
    for i in range(target):
        x0 = int(i * sx / target)
        x1 = max(x0 + 1, int((i + 1) * sx / target))
        for j in range(target):
            y0 = int(j * sy / target)
            y1 = max(y0 + 1, int((j + 1) * sy / target))
            for k in range(target):
                z0 = int(k * sz / target)
                z1 = max(z0 + 1, int((k + 1) * sz / target))
                out[i, j, k] = bool(solid[x0:x1, y0:y1, z0:z1].any())
    return out


def map_style_terrain(
    analyze: dict[str, Any],
    path: Path,
    vocab: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map analyze style guesses + filename to ConditionalVAE style/terrain ids."""
    root = project_root()
    vocab = vocab or load_vocab(root / "data/label_vocab.json")
    styles = list(vocab.get("styles") or ["medieval", "unknown"])
    terrains = list(vocab.get("terrains") or ["flat"])

    guesses = (analyze.get("style") or {}).get("guesses") or []
    guess_names = []
    for g in guesses:
        if isinstance(g, dict):
            guess_names.append(str(g.get("style") or g.get("name") or g.get("id") or ""))
        else:
            guess_names.append(str(g))

    text = path.stem + " " + " ".join(guess_names)
    overview = analyze.get("overview") or {}
    text += " " + str(overview.get("schematic_name") or "")

    style_h, terrain_h, _mats, _size, _notes = _heuristic_from_text(text)

    mapped_style = style_h
    if not mapped_style:
        for name in guess_names:
            low = name.lower()
            for sty, keys in _STYLE_KEYWORDS:
                if sty in low or any(k.lower() in low for k in keys):
                    mapped_style = sty
                    break
            if mapped_style:
                break
    if not mapped_style or mapped_style not in styles:
        # fuzzy: any guess token in styles
        for name in guess_names:
            token = re.split(r"[\s/_]+", name.lower())[0]
            if token in styles:
                mapped_style = token
                break
    # material prior: wood-heavy → rustic; stone → medieval; concrete → modern
    fam = ((analyze.get("structure") or {}).get("families")) or {}
    if (not mapped_style or mapped_style in ("unknown", "medieval")) and fam:
        logs = int(fam.get("logs") or 0) + int(fam.get("planks") or 0)
        stone = int(fam.get("stone_bricks") or 0) + int(fam.get("deepslate") or 0)
        concrete = int(fam.get("concrete") or 0)
        if logs >= stone and logs >= concrete and "rustic" in styles and logs > 50:
            mapped_style = "rustic"
        elif concrete > logs and concrete > stone and "modern" in styles:
            mapped_style = "modern"
        elif stone > logs and "medieval" in styles:
            mapped_style = "medieval"
    if not mapped_style or mapped_style not in styles:
        mapped_style = "medieval" if "medieval" in styles else styles[0]

    mapped_terrain = terrain_h if terrain_h in terrains else None
    if not mapped_terrain:
        mapped_terrain = "flat" if "flat" in terrains else terrains[0]

    return {
        "mapped_style": mapped_style,
        "mapped_terrain": mapped_terrain,
        "style_id": resolve_style_id(vocab, mapped_style),
        "terrain_id": resolve_terrain_id(vocab, mapped_terrain),
        "guess_names": guess_names,
        "map_reason": "filename+analyze.guesses+design_brief heuristics",
    }


def extract_reference_features(
    path: str | Path,
    *,
    skeleton_size: int = 32,
    index_dir: str | Path | None = None,
    write: bool = True,
    embed_block2vec: bool = True,
) -> dict[str, Any]:
    """Analyze reference + write feature JSON and skeleton npz into feature index."""
    root = project_root()
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        raise FileNotFoundError(path)

    index_dir = Path(index_dir) if index_dir else root / INDEX_DIR_DEFAULT
    if not index_dir.is_absolute():
        index_dir = root / index_dir
    index_dir.mkdir(parents=True, exist_ok=True)

    analyze = analyze_litematic(path)
    fid = _stem_id(path)
    style_map = map_style_terrain(analyze, path)

    overview = analyze.get("overview") or {}
    structure = analyze.get("structure") or {}
    style = analyze.get("style") or {}
    redstone = analyze.get("redstone") or {}

    hollow = structure.get("hollow") or {}
    floors = structure.get("floors") or {}
    top_blocks = style.get("top_blocks") or []
    # normalize top blocks
    tops = []
    for b in top_blocks[:16]:
        if isinstance(b, dict):
            name = _short(b.get("name") or b.get("block") or "")
            tops.append(
                {
                    "name": name,
                    "count": int(b.get("count") or b.get("n") or 0),
                    "frac": float(b.get("frac") or b.get("share") or 0),
                }
            )
        else:
            tops.append({"name": _short(str(b)), "count": 0, "frac": 0.0})

    patterns = (redstone.get("common_patterns") or {}).get("patterns") or []
    pattern_ids = [p.get("id") for p in patterns if isinstance(p, dict) and p.get("id")]
    pattern_labels = [p.get("label") for p in patterns if isinstance(p, dict)]

    loaded = load_litematic(path)
    voxels, palette = loaded[0], loaded[1]

    # occupancy: non-air palette entries
    air_ids = set()
    for i, name in enumerate(palette):
        s = _short(name)
        if s in ("air", "cave_air", "void_air") or s.endswith("_air"):
            air_ids.add(i)
    solid_vox = ~np.isin(np.asarray(voxels), list(air_ids) if air_ids else [0])
    # if air not found, treat 0 as air common convention
    if not air_ids:
        solid_vox = np.asarray(voxels) > 0

    occ = downsample_occupancy(solid_vox.astype(np.uint8), target=int(skeleton_size))
    skel_path = index_dir / ("%s_skeleton.npz" % fid)
    feat_path = index_dir / ("%s.json" % fid)

    feature = {
        "id": fid,
        "source_path": str(path.relative_to(root)) if str(path).startswith(str(root)) else str(path),
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "overview": {
            "schematic_name": overview.get("schematic_name"),
            "size": overview.get("size"),
            "non_air": overview.get("non_air"),
            "density": overview.get("density"),
            "unique_block_types": overview.get("unique_block_types"),
        },
        "massing": {
            "hollow_score": hollow.get("hollow_score"),
            "interior_air_frac": hollow.get("interior_air_frac"),
            "exterior_solid_frac": hollow.get("exterior_solid_frac"),
            "floor_guess": floors.get("floor_guess"),
            "y_peaks": floors.get("y_peaks"),
            "families": structure.get("families"),
            "symmetry": structure.get("symmetry"),
            "solid_ratio": structure.get("solid_ratio"),
        },
        "materials": {
            "top_blocks": tops,
            "palette_buckets": style.get("palette_buckets"),
            "remap_targets": [b["name"] for b in tops if b.get("name")][:12],
        },
        "style": {
            **style_map,
            "raw_guesses": guesses_as_list(guesses=style.get("guesses")),
        },
        "redstone": {
            "total": redstone.get("total_redstone_blocks"),
            "pattern_ids": pattern_ids,
            "pattern_labels": pattern_labels,
            "inventory_nonzero": redstone.get("inventory_nonzero"),
            "summary": redstone.get("note"),
        },
        "skeleton": {
            "size": int(skeleton_size),
            "npz": str(skel_path.relative_to(root)),
            "occupancy_frac": float(occ.mean()),
            "occupied": int(occ.sum()),
        },
        "limits": [
            "特征来自 Phase1 启发式分析，非精确 BIM",
            "骨架为 %d³ 占位下采样，不是可编辑蓝图" % skeleton_size,
            "相似生成 = 条件VAE风格/地形 + 结构约束 + 可选骨架/材质启发，非复制粘贴",
        ],
    }

    if write:
        np.savez_compressed(skel_path, occupancy=occ.astype(np.uint8))
        # Block2Vec 144-d embedding (optional; soft-fail)
        if embed_block2vec:
            try:
                from src.app.block2vec_embed import attach_embedding_to_feature

                attach_embedding_to_feature(feature, path, index_dir=index_dir)
            except Exception as ex:
                feature["block2vec"] = {"ok": False, "error": str(ex)}
        feat_path.write_text(json.dumps(feature, ensure_ascii=False, indent=2), encoding="utf-8")
        _update_index_manifest(index_dir, feature)

    feature["_paths"] = {"feature_json": str(feat_path), "skeleton_npz": str(skel_path)}
    return feature


def guesses_as_list(guesses) -> list[Any]:
    if not guesses:
        return []
    out = []
    for g in guesses:
        if isinstance(g, dict):
            out.append(g)
        else:
            out.append({"name": str(g)})
    return out


def _update_index_manifest(index_dir: Path, feature: dict[str, Any]) -> None:
    man = index_dir / "index.json"
    items = []
    if man.exists():
        try:
            items = json.loads(man.read_text(encoding="utf-8")).get("items") or []
        except Exception:
            items = []
    items = [it for it in items if it.get("id") != feature["id"]]
    items.append(
        {
            "id": feature["id"],
            "feature_json": "%s.json" % feature["id"],
            "skeleton_npz": "%s_skeleton.npz" % feature["id"],
            "mapped_style": (feature.get("style") or {}).get("mapped_style"),
            "mapped_terrain": (feature.get("style") or {}).get("mapped_terrain"),
            "source_path": feature.get("source_path"),
            "created_at": feature.get("created_at"),
        }
    )
    man.write_text(
        json.dumps({"updated_at": feature.get("created_at"), "items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_feature(feature_id_or_json: str | Path, index_dir: str | Path | None = None) -> dict[str, Any]:
    root = project_root()
    index_dir = Path(index_dir) if index_dir else root / INDEX_DIR_DEFAULT
    if not index_dir.is_absolute():
        index_dir = root / index_dir
    p = Path(feature_id_or_json)
    if p.suffix == ".json" and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    cand = index_dir / ("%s.json" % feature_id_or_json)
    if cand.exists():
        return json.loads(cand.read_text(encoding="utf-8"))
    # try as path stem
    if p.exists() and p.suffix == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("feature not found: %s" % feature_id_or_json)


def load_skeleton(feature: dict[str, Any], index_dir: str | Path | None = None) -> np.ndarray:
    root = project_root()
    rel = (feature.get("skeleton") or {}).get("npz")
    if not rel:
        raise KeyError("no skeleton in feature")
    path = root / rel
    if not path.exists():
        index_dir = Path(index_dir) if index_dir else root / INDEX_DIR_DEFAULT
        path = (root / index_dir / ("%s_skeleton.npz" % feature["id"])) if not Path(index_dir).is_absolute() else Path(index_dir) / ("%s_skeleton.npz" % feature["id"])
    with np.load(path) as data:
        return np.asarray(data["occupancy"], dtype=np.uint8)


def apply_skeleton_guidance(
    voxels: np.ndarray,
    occupancy: np.ndarray,
    *,
    fill_id: int,
    strength: float = 0.5,
) -> tuple[np.ndarray, dict[str, int]]:
    """Soft guidance: fill some skeleton cells that are empty; lightly carve off-skeleton blobs.

    strength in [0,1]: fraction of candidate cells to touch (deterministic subsample).
    """
    out = np.asarray(voxels, dtype=np.int16).copy()
    occ = np.asarray(occupancy).astype(bool)
    if out.shape != occ.shape:
        # nearest resize occ to out
        occ = downsample_occupancy(occ.astype(np.uint8), target=out.shape[0])
        if occ.shape != out.shape:
            # only support cubic target matching first dim
            t = out.shape[0]
            occ = downsample_occupancy(np.asarray(occupancy).astype(np.uint8), target=t)

    stats = {"filled": 0, "carved": 0}
    strength = float(np.clip(strength, 0.0, 1.0))
    # fill: skeleton solid & sample air
    fill_candidates = np.argwhere(occ & (out == 0))
    if fill_candidates.size:
        n = int(len(fill_candidates) * strength)
        for idx, (x, y, z) in enumerate(fill_candidates):
            if idx >= n:
                break
            # only fill if neighborhood has some solid already (avoid floating shell alone)
            x0, x1 = max(0, x - 1), min(out.shape[0], x + 2)
            y0, y1 = max(0, y - 1), min(out.shape[1], y + 2)
            z0, z1 = max(0, z - 1), min(out.shape[2], z + 2)
            if int((out[x0:x1, y0:y1, z0:z1] > 0).sum()) >= 1 or strength >= 0.85:
                out[x, y, z] = fill_id
                stats["filled"] += 1

    # carve: sample solid deep where skeleton air and 26-neigh mostly solid (noise)
    carve_candidates = np.argwhere((~occ) & (out > 0))
    if carve_candidates.size and strength > 0:
        n = int(len(carve_candidates) * (0.35 * strength))
        carved = 0
        for x, y, z in carve_candidates:
            if carved >= n:
                break
            if not (1 <= x < out.shape[0] - 1 and 1 <= y < out.shape[1] - 1 and 1 <= z < out.shape[2] - 1):
                continue
            block = out[x - 1 : x + 2, y - 1 : y + 2, z - 1 : z + 2]
            if int((block > 0).sum()) >= 20:
                out[x, y, z] = 0
                carved += 1
        stats["carved"] = carved
    return out, stats


def material_remap_to_reference(
    voxels: np.ndarray,
    palette: dict[int, str],
    remap_targets: list[str],
) -> tuple[np.ndarray, dict[str, Any]]:
    """Remap most frequent solid ids in sample to reference top block names (by rank)."""
    out = np.asarray(voxels, dtype=np.int16).copy()
    if not remap_targets:
        return out, {"remapped": 0}

    # build name -> id for palette (reverse)
    name_to_id: dict[str, int] = {}
    for i, name in palette.items():
        name_to_id[_short(name)] = int(i)

    # resolve target ids (skip missing)
    target_ids: list[int] = []
    resolved = []
    for name in remap_targets:
        # try exact, then suffix match
        if name in name_to_id:
            target_ids.append(name_to_id[name])
            resolved.append(name)
            continue
        hit = None
        for pn, pid in name_to_id.items():
            if pn.endswith(name) or name.endswith(pn) or name.split("_")[-1] == pn.split("_")[-1]:
                hit = pid
                resolved.append(pn)
                break
        if hit is not None:
            target_ids.append(hit)

    if not target_ids:
        return out, {"remapped": 0, "note": "no remap targets in palette"}

    solid = out[out > 0]
    if solid.size == 0:
        return out, {"remapped": 0}
    ids, counts = np.unique(solid, return_counts=True)
    order = ids[np.argsort(-counts)]
    mapping = {}
    for i, sid in enumerate(order[: len(target_ids)]):
        mapping[int(sid)] = int(target_ids[i])

    remapped = 0
    for src, dst in mapping.items():
        if src == dst:
            continue
        mask = out == src
        n = int(mask.sum())
        out[mask] = dst
        remapped += n
    return out, {"remapped": remapped, "mapping": mapping, "resolved_targets": resolved}


def list_index(index_dir: str | Path | None = None) -> list[dict[str, Any]]:
    root = project_root()
    index_dir = Path(index_dir) if index_dir else root / INDEX_DIR_DEFAULT
    if not index_dir.is_absolute():
        index_dir = root / index_dir
    man = index_dir / "index.json"
    if not man.exists():
        return []
    return list(json.loads(man.read_text(encoding="utf-8")).get("items") or [])


def generate_similar_from_feature(
    feature: dict,
    *,
    num: int = 4,
    temperature: float = 1.0,
    checkpoint: str | Path | None = None,
    out_dir: str | Path | None = None,
    seed: int | None = None,
    structure_constrain: bool = True,
    structure_mode: str = "repair",
    use_skeleton: bool = True,
    skeleton_strength: float = 0.45,
    material_remap: bool = True,
) -> list[dict]:
    """Sample ConditionalVAE variants guided by reference feature index."""
    from src.app.sample_runner import generate_samples, project_root as _pr
    from src.utils import load_config, load_palette
    from src.app.structure_constraints import apply_structure_constraints, check_structure

    root = project_root()
    style = (feature.get("style") or {}).get("mapped_style") or "medieval"
    terrain = (feature.get("style") or {}).get("mapped_terrain") or "flat"
    fid = feature.get("id") or "ref"

    dest = Path(out_dir) if out_dir else root / "outputs" / "similar" / fid
    if not dest.is_absolute():
        dest = root / dest
    dest.mkdir(parents=True, exist_ok=True)

    # refresh Block2Vec neighbors if embedding on disk
    try:
        from src.app.block2vec_embed import load_embedding, search_index

        idx = root / "data" / "feature_index"
        vec = load_embedding(idx, fid)
        if vec is not None:
            neighbors = [n for n in search_index(vec, idx, top_k=6) if n["id"] != fid]
            feature.setdefault("block2vec", {})
            feature["block2vec"]["neighbors"] = neighbors[:5]
            feature["block2vec"]["ok"] = True
            feature["block2vec"]["dim"] = int(vec.size)
    except Exception:
        pass

    ckpt = checkpoint
    if ckpt is None:
        preferred = root / "checkpoints" / "cond_last.pt"
        ckpt = preferred if preferred.exists() else root / "checkpoints" / "last.pt"

    results = generate_samples(
        num=num,
        temperature=temperature,
        checkpoint=ckpt,
        out_dir=dest,
        seed=seed,
        style=style,
        terrain=terrain,
        structure_constrain=structure_constrain,
        structure_mode=structure_mode,
        structure_max_tries=8,
    )

    cfg = load_config(root / "configs/default.yaml")
    palette = load_palette(root / cfg["data"]["palette_path"])
    # palette is dict[int,str]
    remap_targets = (feature.get("materials") or {}).get("remap_targets") or []
    # prefer first non-air-ish solid-looking names
    fill_id = 1
    for name in remap_targets:
        for i, pn in palette.items():
            if _short(pn) == name and int(i) > 0:
                fill_id = int(i)
                break
        if fill_id > 1:
            break

    occ = None
    if use_skeleton:
        try:
            occ = load_skeleton(feature)
        except Exception as ex:
            occ = None
            sk_err = str(ex)
        else:
            sk_err = None
    else:
        sk_err = "disabled"

    from src.data.io_vox import save_npz_npz
    from src.data.export_mcfunction import export_mcfunction

    final = []
    for meta in results:
        vox = meta["voxels"]
        guide_stats = {}
        if occ is not None:
            vox, guide_stats = apply_skeleton_guidance(
                vox, occ, fill_id=fill_id, strength=float(skeleton_strength)
            )
            # light structure repair after guidance
            if structure_constrain:
                vox, rep = apply_structure_constraints(vox, mode="repair")
                guide_stats["post_structure_repairs"] = rep.repairs
                meta["structure"] = rep.to_dict()
        remap_stats = {}
        if material_remap and remap_targets:
            vox, remap_stats = material_remap_to_reference(vox, palette, remap_targets)

        # rewrite files
        npz_path = Path(meta["npz_path"])
        # rename to similar_ prefix
        new_path = npz_path.with_name(npz_path.name.replace("sample_", "similar_", 1))
        save_npz_npz(new_path, vox)
        mc_path = new_path.with_suffix(".mcfunction")
        commands = export_mcfunction(vox, palette, mc_path, origin=(0, 64, 0))
        # remove old sample files if different
        if new_path != npz_path and npz_path.exists():
            try:
                npz_path.unlink()
                old_mc = npz_path.with_suffix(".mcfunction")
                if old_mc.exists():
                    old_mc.unlink()
            except OSError:
                pass

        meta["voxels"] = vox
        meta["npz_path"] = new_path
        meta["mcfunction_path"] = mc_path
        meta["non_air"] = int((vox > 0).sum())
        meta["commands"] = commands
        meta["reference_id"] = fid
        meta["reference_style"] = style
        meta["reference_terrain"] = terrain
        meta["skeleton_guidance"] = guide_stats
        meta["skeleton_error"] = sk_err
        meta["material_remap"] = remap_stats
        meta["structure_final"] = check_structure(vox).to_dict()
        final.append(meta)

    # write run manifest
    b2v = feature.get("block2vec") or {}
    man = {
        "reference_id": fid,
        "style": style,
        "terrain": terrain,
        "num": len(final),
        "use_skeleton": use_skeleton,
        "skeleton_strength": skeleton_strength,
        "material_remap": material_remap,
        "structure_constrain": structure_constrain,
        "outputs": [str(m["npz_path"].name) for m in final],
        "block2vec": {
            "ok": b2v.get("ok"),
            "dim": b2v.get("dim"),
            "n_chunks": b2v.get("n_chunks"),
            "neighbors": b2v.get("neighbors") or [],
            "npy": b2v.get("npy"),
        },
    }
    (dest / "similar_run.json").write_text(
        __import__("json").dumps(man, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return final

