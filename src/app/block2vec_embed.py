# -*- coding: utf-8 -*-
"""Embed Minecraft volumes with CraftGPT TransformerBlock2Vec (16x8x16 chunks → 144-d).

Vocab note: upstream shipped no block-id table. We map:
  - project palette.json ids if < 1096
  - else stable hash of block name -> 1..1095
  - air/cave_air/void_air -> 0; SEP=1096 PAD=1097 MASK=1098
Larger builds are tiled with stride; empty tiles skipped; mean-pooled.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from src.models.block2vec import (
    MAX_X,
    MAX_Y,
    MAX_Z,
    PAD_ID,
    TransformerBlock2Vec,
    load_block2vec,
)

_AIR = {"air", "cave_air", "void_air"}
_MODEL: TransformerBlock2Vec | None = None
_DEVICE: str | None = None


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _short(name: str) -> str:
    n = str(name).replace("minecraft:", "")
    if n.startswith("block.minecraft."):
        n = n[len("block.minecraft.") :]
    if "[" in n:
        n = n.split("[", 1)[0]
    return n


def _stable_token_id(name: str) -> int:
    s = _short(name)
    if s in _AIR or s.endswith("_air"):
        return 0
    h = hashlib.md5(s.encode("utf-8")).hexdigest()
    return 1 + (int(h[:8], 16) % 1095)


def build_name_to_token(palette: list[str] | dict[int, str] | None = None) -> dict[str, int]:
    """Map short block names -> token ids; prefer project palette indices when <1096."""
    root = project_root()
    mapping: dict[str, int] = {"air": 0, "cave_air": 0, "void_air": 0}
    pal_path = root / "data" / "palette.json"
    if pal_path.exists():
        raw = json.loads(pal_path.read_text(encoding="utf-8"))
        items = raw.items() if isinstance(raw, dict) else enumerate(raw)
        for k, name in items:
            tid = int(k) if not isinstance(k, int) else k
            short = _short(name)
            if tid < 1096:
                mapping[short] = tid
            else:
                mapping[short] = _stable_token_id(short)
    if palette is not None:
        if isinstance(palette, dict):
            seq = palette.items()
        else:
            seq = enumerate(palette)
        for i, name in seq:
            short = _short(name)
            if short in mapping:
                continue
            if int(i) < 1096:
                mapping[short] = int(i)
            else:
                mapping[short] = _stable_token_id(short)
    return mapping


def voxels_to_token_volume(
    voxels: np.ndarray,
    palette: list[str] | dict[int, str],
    name_to_token: dict[str, int] | None = None,
) -> np.ndarray:
    """Map schematic palette indices -> Block2Vec token ids; shape preserved."""
    name_to_token = name_to_token or build_name_to_token(palette)
    if isinstance(palette, dict):
        id_to_name = {int(k): _short(v) for k, v in palette.items()}
    else:
        id_to_name = {i: _short(n) for i, n in enumerate(palette)}
    v = np.asarray(voxels)
    out = np.zeros(v.shape, dtype=np.int32)
    for pid, short in id_to_name.items():
        tok = name_to_token.get(short)
        if tok is None:
            tok = _stable_token_id(short)
        out[v == pid] = tok
    return out


def iter_chunks(
    tokens: np.ndarray,
    *,
    chunk: tuple[int, int, int] = (MAX_X, MAX_Y, MAX_Z),
    stride: tuple[int, int, int] | None = None,
    min_non_air: int = 8,
) -> list[tuple[np.ndarray, tuple[int, int, int]]]:
    """Yield (tile, origin) for non-empty 16x8x16 tiles. Axis order (X,Y,Z)."""
    cx, cy, cz = chunk
    sx, sy, sz = (stride or (cx, cy, cz))
    vol = np.asarray(tokens)
    X, Y, Z = vol.shape
    pad_x = max(0, cx - X)
    pad_y = max(0, cy - Y)
    pad_z = max(0, cz - Z)
    if pad_x or pad_y or pad_z:
        vol = np.pad(vol, ((0, pad_x), (0, pad_y), (0, pad_z)), constant_values=0)
        X, Y, Z = vol.shape
    out: list[tuple[np.ndarray, tuple[int, int, int]]] = []
    xs = list(range(0, max(1, X - cx + 1), sx))
    ys = list(range(0, max(1, Y - cy + 1), sy))
    zs = list(range(0, max(1, Z - cz + 1), sz))
    if xs[-1] != max(0, X - cx):
        xs.append(max(0, X - cx))
    if ys[-1] != max(0, Y - cy):
        ys.append(max(0, Y - cy))
    if zs[-1] != max(0, Z - cz):
        zs.append(max(0, Z - cz))
    seen = set()
    for x0 in xs:
        for y0 in ys:
            for z0 in zs:
                key = (x0, y0, z0)
                if key in seen:
                    continue
                seen.add(key)
                tile = vol[x0 : x0 + cx, y0 : y0 + cy, z0 : z0 + cz]
                if tile.shape != (cx, cy, cz):
                    padded = np.zeros((cx, cy, cz), dtype=np.int32)
                    padded[: tile.shape[0], : tile.shape[1], : tile.shape[2]] = tile
                    tile = padded
                if int((tile > 0).sum()) < min_non_air:
                    continue
                out.append((tile, (x0, y0, z0)))
    if not out:
        out.append((np.zeros((cx, cy, cz), dtype=np.int32), (0, 0, 0)))
    return out


def _flatten_chunk(tile: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Flatten (X,Y,Z)=(16,8,16) -> tokens (T,), pos (T,3) order y,z,x."""
    cx, cy, cz = tile.shape
    assert (cx, cy, cz) == (MAX_X, MAX_Y, MAX_Z)
    tokens = []
    pos = []
    for y in range(cy):
        for z in range(cz):
            for x in range(cx):
                tokens.append(int(tile[x, y, z]))
                pos.append((x, y, z))
    return np.asarray(tokens, dtype=np.int64), np.asarray(pos, dtype=np.int64)


def reset_model(device: str | None = None) -> TransformerBlock2Vec:
    """Drop cached weights (e.g. after CUDA illegal access) and reload."""
    global _MODEL, _DEVICE
    _MODEL = None
    _DEVICE = None
    if device and device.startswith("cuda"):
        try:
            import torch

            torch.cuda.empty_cache()
            torch.cuda.synchronize()
        except Exception:
            pass
    return get_model(device=device)


def get_model(device: str | None = None) -> TransformerBlock2Vec:
    global _MODEL, _DEVICE
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if _MODEL is None or _DEVICE != device:
        _MODEL = load_block2vec(device=device)
        _DEVICE = device
    return _MODEL


def embed_token_volume(
    tokens: np.ndarray,
    *,
    device: str | None = None,
    max_chunks: int = 64,
) -> dict[str, Any]:
    """Embed full token volume via chunking; returns vector + meta."""
    model = get_model(device=device)
    dev = next(model.parameters()).device
    chunks = iter_chunks(tokens)
    if len(chunks) > max_chunks:
        chunks = sorted(chunks, key=lambda t: int((t[0] > 0).sum()), reverse=True)[:max_chunks]
    vecs = []
    origins = []
    with torch.no_grad():
        for tile, origin in chunks:
            tok, pos = _flatten_chunk(tile)
            # Clamp to vocab: illegal CUDA indexing if id >= VOCAB_SIZE
            tok = tok.clip(0, 1098)
            tt = torch.as_tensor(tok, device=dev).unsqueeze(0)
            pp = torch.as_tensor(pos, device=dev).unsqueeze(0)
            pad_mask = tt == PAD_ID
            emb = model.embed_pooled(tt, pp, key_padding_mask=pad_mask)
            vecs.append(emb.squeeze(0).float().cpu().numpy())
            origins.append(list(origin))
    stacked = np.stack(vecs, axis=0)
    weights = np.array([max(1, int((c[0] > 0).sum())) for c in chunks], dtype=np.float64)
    weights = weights / weights.sum()
    mean = (stacked * weights[:, None]).sum(axis=0)
    mean = mean / (np.linalg.norm(mean) + 1e-8)
    return {
        "dim": int(mean.shape[0]),
        "vector": mean.astype(np.float32),
        "n_chunks": len(chunks),
        "chunk_origins": origins,
        "backend": "transformer_block2vec",
        "chunk_size": [MAX_X, MAX_Y, MAX_Z],
        "token_map": "palette_then_md5_hash",
    }


def embed_litematic(path: str | Path, *, device: str | None = None) -> dict[str, Any]:
    from src.data.litematic import load_litematic

    root = project_root()
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    loaded = load_litematic(path)
    voxels, palette = loaded[0], loaded[1]
    meta = loaded[2] if len(loaded) > 2 else {"size": list(voxels.shape)}
    tokens = voxels_to_token_volume(voxels, palette)
    result = embed_token_volume(tokens, device=device)
    result["source"] = str(path)
    result["size"] = list(meta.get("size") or voxels.shape)
    return result


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8))


def save_embedding(index_dir: Path, feature_id: str, vector: np.ndarray, meta: dict[str, Any]) -> Path:
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    npy = index_dir / ("%s_block2vec.npy" % feature_id)
    np.save(npy, np.asarray(vector, dtype=np.float32))
    side = {
        "id": feature_id,
        "dim": int(np.asarray(vector).size),
        "n_chunks": meta.get("n_chunks"),
        "chunk_size": meta.get("chunk_size"),
        "backend": meta.get("backend"),
        "token_map": meta.get("token_map"),
        "npy": npy.name,
    }
    (index_dir / ("%s_block2vec.json" % feature_id)).write_text(
        json.dumps(side, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return npy


def load_embedding(index_dir: Path, feature_id: str) -> np.ndarray | None:
    npy = Path(index_dir) / ("%s_block2vec.npy" % feature_id)
    if not npy.exists():
        return None
    return np.load(npy)


def search_index(
    query: np.ndarray,
    index_dir: str | Path | None = None,
    *,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """Nearest neighbors in feature_index by Block2Vec cosine."""
    root = project_root()
    index_dir = Path(index_dir) if index_dir else root / "data" / "feature_index"
    if not index_dir.is_absolute():
        index_dir = root / index_dir
    man = index_dir / "index.json"
    items = []
    if man.exists():
        items = json.loads(man.read_text(encoding="utf-8")).get("items") or []
    scored: list[dict[str, Any]] = []
    q = np.asarray(query, dtype=np.float32)
    for it in items:
        fid = it.get("id")
        if not fid:
            continue
        vec = load_embedding(index_dir, fid)
        if vec is None:
            continue
        scored.append(
            {
                "id": fid,
                "score": cosine(q, vec),
                "mapped_style": it.get("mapped_style"),
                "mapped_terrain": it.get("mapped_terrain"),
                "source_path": it.get("source_path"),
            }
        )
    scored.sort(key=lambda d: -d["score"])
    return scored[: int(top_k)]


def attach_embedding_to_feature(
    feature: dict[str, Any],
    path: str | Path,
    *,
    index_dir: str | Path | None = None,
    device: str | None = None,
    skip_neighbors: bool = False,
) -> dict[str, Any]:
    """Compute Block2Vec, save beside feature, mutate feature['block2vec']."""
    root = project_root()
    index_dir = Path(index_dir) if index_dir else root / "data" / "feature_index"
    if not index_dir.is_absolute():
        index_dir = root / index_dir
    try:
        emb = embed_litematic(path, device=device)
        npy = save_embedding(index_dir, feature["id"], emb["vector"], emb)
        feature["block2vec"] = {
            "dim": emb["dim"],
            "n_chunks": emb["n_chunks"],
            "backend": emb["backend"],
            "chunk_size": emb["chunk_size"],
            "token_map": emb["token_map"],
            "npy": str(npy.relative_to(root)) if str(npy).startswith(str(root)) else str(npy),
            "vector_preview": [round(float(x), 5) for x in emb["vector"][:8]],
            "ok": True,
        }
        if not skip_neighbors:
            neighbors = [
                n for n in search_index(emb["vector"], index_dir, top_k=6) if n["id"] != feature["id"]
            ]
            feature["block2vec"]["neighbors"] = neighbors[:5]
    except Exception as ex:
        feature["block2vec"] = {"ok": False, "error": str(ex)}
    return feature
