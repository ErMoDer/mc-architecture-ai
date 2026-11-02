from __future__ import annotations

from pathlib import Path
from time import time

import nbtlib
import numpy as np


def _bits_per_block(palette_len: int) -> int:
    return max(2, (palette_len - 1).bit_length())


def _as_u64(value: int) -> int:
    """Interpret a (possibly signed) Java long as unsigned 64-bit."""
    return int(value) & ((1 << 64) - 1)


def _unpack_block_states(longs: list[int] | np.ndarray, volume: int, bits: int) -> np.ndarray:
    """Litematica packed BlockStates -> flat palette indices."""
    mask = (1 << bits) - 1
    out = np.zeros(volume, dtype=np.int32)
    bit_index = 0
    for i in range(volume):
        start = bit_index
        start_long = start // 64
        start_offset = start % 64
        end_long = (start + bits - 1) // 64
        u0 = _as_u64(longs[start_long])
        if start_long == end_long:
            value = (u0 >> start_offset) & mask
        else:
            low = 64 - start_offset
            u1 = _as_u64(longs[end_long])
            v0 = u0 >> start_offset
            v1 = u1 & ((1 << (bits - low)) - 1)
            value = (v0 | (v1 << low)) & mask
        out[i] = value
        bit_index += bits
    return out


def _to_signed_long(value: int) -> int:
    """uint64 bit pattern -> Java/NBT signed long."""
    value &= (1 << 64) - 1
    if value >= (1 << 63):
        value -= 1 << 64
    return value


def _pack_block_states(indices: np.ndarray | list[int], bits: int) -> list[int]:
    """Flat palette indices -> Litematica packed BlockStates (signed longs)."""
    flat = np.asarray(indices, dtype=np.int64).ravel()
    volume = int(flat.size)
    if volume == 0:
        return []
    mask = (1 << bits) - 1
    n_longs = (volume * bits + 63) // 64
    longs = [0] * n_longs
    bit_index = 0
    for i in range(volume):
        value = int(flat[i]) & mask
        start = bit_index
        start_long = start // 64
        start_offset = start % 64
        end_long = (start + bits - 1) // 64
        if start_long == end_long:
            longs[start_long] |= value << start_offset
        else:
            low = 64 - start_offset
            longs[start_long] |= value << start_offset
            longs[end_long] |= value >> low
        bit_index += bits
    return [_to_signed_long(v) for v in longs]


def _palette_entry_name(entry) -> str:
    name = str(entry["Name"])
    props = entry.get("Properties")
    if not props:
        return name
    # Training: ignore block state, keep kind only
    return name


def _normalize_block_name(name: str) -> str:
    name = str(name).strip()
    if not name:
        return "minecraft:air"
    if name.startswith("minecraft:"):
        return name
    if ":" in name:
        return name
    return f"minecraft:{name}"


def _resolve_name_for_id(
    block_id: int,
    palette: dict[int, str] | list[str] | None,
) -> str:
    if palette is None:
        return "minecraft:air" if block_id == 0 else f"minecraft:unknown_{block_id}"
    if isinstance(palette, dict):
        return _normalize_block_name(
            palette.get(int(block_id), f"minecraft:unknown_{block_id}")
        )
    if 0 <= int(block_id) < len(palette):
        return _normalize_block_name(palette[int(block_id)])
    return f"minecraft:unknown_{block_id}"


def _is_air_name(name: str) -> bool:
    n = str(name).replace("minecraft:", "")
    return n in {"air", "cave_air", "void_air", "structure_void"}


def load_litematic(path: str | Path) -> tuple[np.ndarray, list[str], dict]:
    """
    Read .litematic, return:
    - voxels: int32 [X,Y,Z] palette indices
    - palette: block name list
    - meta: name/size/...
    """
    path = Path(path)
    nbt = nbtlib.load(path)
    meta_tag = nbt.get("Metadata", {})
    regions = nbt["Regions"]
    if not regions:
        raise ValueError(f"{path.name}: no Regions")

    best_name = None
    best_region = None
    best_vol = -1
    for name, region in regions.items():
        size = region["Size"]
        sx, sy, sz = abs(int(size["x"])), abs(int(size["y"])), abs(int(size["z"]))
        vol = sx * sy * sz
        if vol > best_vol:
            best_vol = vol
            best_name = str(name)
            best_region = region

    assert best_region is not None
    size = best_region["Size"]
    sx, sy, sz = abs(int(size["x"])), abs(int(size["y"])), abs(int(size["z"]))
    palette_tag = best_region["BlockStatePalette"]
    palette = [_palette_entry_name(e) for e in palette_tag]
    bits = _bits_per_block(len(palette))
    longs = list(best_region["BlockStates"])
    flat = _unpack_block_states(longs, sx * sy * sz, bits)

    # Litematica order: YZX -> [X,Y,Z]
    voxels = flat.reshape((sy, sz, sx)).transpose(2, 0, 1)

    meta = {
        "name": str(meta_tag.get("Name", path.stem)),
        "author": str(meta_tag.get("Author", "")),
        "region": best_name,
        "size": (sx, sy, sz),
        "total_blocks": int(meta_tag.get("TotalBlocks", 0)),
        "source": str(path),
    }
    return voxels.astype(np.int32), palette, meta



def _palette_entry_props(entry) -> dict[str, str]:
    props = entry.get("Properties")
    if not props:
        return {}
    out: dict[str, str] = {}
    for k, v in props.items():
        out[str(k)] = str(v)
    return out


def load_litematic_detailed(
    path: str | Path,
) -> tuple[np.ndarray, list[str], list[dict[str, str]], dict]:
    """Like load_litematic, but also returns per-palette-index blockstate properties.

    Used by schematic analysis for facing-aware redstone heuristics.
    Training path should keep using load_litematic (names only).
    """
    path = Path(path)
    nbt = nbtlib.load(path)
    meta_tag = nbt.get("Metadata", {})
    regions = nbt["Regions"]
    if not regions:
        raise ValueError(f"{path.name}: no Regions")

    best_name = None
    best_region = None
    best_vol = -1
    for name, region in regions.items():
        size = region["Size"]
        sx, sy, sz = abs(int(size["x"])), abs(int(size["y"])), abs(int(size["z"]))
        vol = sx * sy * sz
        if vol > best_vol:
            best_vol = vol
            best_name = str(name)
            best_region = region

    assert best_region is not None
    size = best_region["Size"]
    sx, sy, sz = abs(int(size["x"])), abs(int(size["y"])), abs(int(size["z"]))
    palette_tag = best_region["BlockStatePalette"]
    palette = [_palette_entry_name(e) for e in palette_tag]
    props_list = [_palette_entry_props(e) for e in palette_tag]
    bits = _bits_per_block(len(palette))
    longs = list(best_region["BlockStates"])
    flat = _unpack_block_states(longs, sx * sy * sz, bits)
    voxels = flat.reshape((sy, sz, sx)).transpose(2, 0, 1)

    meta = {
        "name": str(meta_tag.get("Name", path.stem)),
        "author": str(meta_tag.get("Author", "")),
        "region": best_name,
        "size": (sx, sy, sz),
        "total_blocks": int(meta_tag.get("TotalBlocks", 0)),
        "source": str(path),
    }
    return voxels.astype(np.int32), palette, props_list, meta


def fit_to_cube(
    voxels: np.ndarray,
    size: int,
    air_id: int = 0,
) -> np.ndarray:
    """Crop/center into size^3 cube; oversized crops centered."""
    out = np.full((size, size, size), air_id, dtype=np.int32)
    sx, sy, sz = voxels.shape
    solid = voxels != air_id
    if not solid.any():
        return out
    xs = np.where(solid.any(axis=(1, 2)))[0]
    ys = np.where(solid.any(axis=(0, 2)))[0]
    zs = np.where(solid.any(axis=(0, 1)))[0]
    crop = voxels[xs[0] : xs[-1] + 1, ys[0] : ys[-1] + 1, zs[0] : zs[-1] + 1]
    cx, cy, cz = crop.shape

    if cx > size or cy > size or cz > size:
        x0 = max(0, (cx - size) // 2)
        y0 = max(0, (cy - size) // 2)
        z0 = max(0, (cz - size) // 2)
        crop = crop[x0 : x0 + size, y0 : y0 + size, z0 : z0 + size]
        cx, cy, cz = crop.shape

    ox = (size - cx) // 2
    oy = (size - cy) // 2
    oz = (size - cz) // 2
    out[ox : ox + cx, oy : oy + cy, oz : oz + cz] = crop
    return out


def save_litematic(
    voxels: np.ndarray,
    palette: dict[int, str] | list[str] | None,
    out_path: str | Path,
    *,
    name: str | None = None,
    author: str = "mc-architecture-ai",
    region_name: str | None = None,
    minecraft_data_version: int = 3953,
    version: int = 7,
    sub_version: int = 1,
    description: str = "Exported from mc-architecture-ai",
    verify: bool = True,
) -> dict:
    """
    Write [X,Y,Z] voxels as a valid .litematic (gzip NBT).

    palette: global id->name (training palette), or name list aligned with voxels.
    Region palette is compacted to used blocks only, with air at index 0.
    Returns a summary dict; when verify=True, round-trips via load_litematic.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    vox = np.asarray(voxels)
    if vox.ndim != 3:
        raise ValueError(f"voxels must be 3D [X,Y,Z], got shape={vox.shape}")
    sx, sy, sz = (int(vox.shape[0]), int(vox.shape[1]), int(vox.shape[2]))
    volume = sx * sy * sz

    used_ids = sorted({int(i) for i in np.unique(vox)})
    air_name = "minecraft:air"
    for cand in used_ids:
        n = _resolve_name_for_id(cand, palette)
        if _is_air_name(n):
            air_name = _normalize_block_name(n if n not in {"air", "cave_air", "void_air"} else "minecraft:air")
            if air_name == "minecraft:air" or _is_air_name(air_name):
                air_name = "minecraft:air"
            break

    region_palette: list[str] = [air_name]
    id_to_region: dict[int, int] = {}
    for bid in used_ids:
        bname = _resolve_name_for_id(bid, palette)
        if _is_air_name(bname):
            id_to_region[bid] = 0
            continue
        if bname not in region_palette:
            region_palette.append(bname)
        id_to_region[bid] = region_palette.index(bname)

    # Vectorized remap: [X,Y,Z] -> YZX flat (x + z*SizeX + y*SizeX*SizeZ)
    remap_lut = np.zeros(max(used_ids) + 1 if used_ids else 1, dtype=np.int32)
    for bid, rid in id_to_region.items():
        if bid < remap_lut.size:
            remap_lut[bid] = rid
        else:
            # grow if needed (shouldn't happen often)
            new_lut = np.zeros(bid + 1, dtype=np.int32)
            new_lut[: remap_lut.size] = remap_lut
            new_lut[bid] = rid
            remap_lut = new_lut
    remapped_xyz = remap_lut[vox.astype(np.int32)]
    # transpose [X,Y,Z] -> [Y,Z,X] then ravel C-order = y major, then z, then x
    # Want flat index i = x + z*sx + y*sx*sz
    # Equivalent: reshape of array ordered (y, z, x)
    remapped = np.transpose(remapped_xyz, (1, 2, 0))  # [Y,Z,X]
    flat = remapped.reshape(-1)

    bits = _bits_per_block(len(region_palette))
    packed = _pack_block_states(flat, bits)
    non_air = int((flat != 0).sum())

    schematic_name = name or out_path.stem
    rname = region_name or schematic_name
    now_ms = int(time() * 1000)

    palette_tag = nbtlib.List[nbtlib.Compound](
        [nbtlib.Compound({"Name": nbtlib.String(n)}) for n in region_palette]
    )
    block_states = nbtlib.LongArray([nbtlib.Long(v) for v in packed])
    empty_compound_list = nbtlib.List[nbtlib.Compound]([])
    empty_list = nbtlib.List([])

    region = nbtlib.Compound(
        {
            "Size": nbtlib.Compound(
                {"x": nbtlib.Int(sx), "y": nbtlib.Int(sy), "z": nbtlib.Int(sz)}
            ),
            "Position": nbtlib.Compound(
                {"x": nbtlib.Int(0), "y": nbtlib.Int(0), "z": nbtlib.Int(0)}
            ),
            "BlockStatePalette": palette_tag,
            "BlockStates": block_states,
            "TileEntities": empty_compound_list,
            "Entities": empty_compound_list,
            "PendingBlockTicks": empty_list,
            "PendingFluidTicks": empty_list,
        }
    )

    metadata = nbtlib.Compound(
        {
            "Name": nbtlib.String(schematic_name),
            "Author": nbtlib.String(author),
            "Description": nbtlib.String(description),
            "RegionCount": nbtlib.Int(1),
            "TotalVolume": nbtlib.Int(volume),
            "TotalBlocks": nbtlib.Int(non_air),
            "TimeCreated": nbtlib.Long(now_ms),
            "TimeModified": nbtlib.Long(now_ms),
            "EnclosingSize": nbtlib.Compound(
                {"x": nbtlib.Int(sx), "y": nbtlib.Int(sy), "z": nbtlib.Int(sz)}
            ),
        }
    )

    root = nbtlib.File(
        {
            "Version": nbtlib.Int(version),
            "SubVersion": nbtlib.Int(sub_version),
            "MinecraftDataVersion": nbtlib.Int(minecraft_data_version),
            "Metadata": metadata,
            "Regions": nbtlib.Compound({rname: region}),
        },
        gzipped=True,
        byteorder="big",
    )
    root.save(out_path)

    loaded_non_air = non_air
    if verify:
        loaded, loaded_pal, _loaded_meta = load_litematic(out_path)
        if tuple(int(x) for x in loaded.shape) != (sx, sy, sz):
            raise RuntimeError(
                f"roundtrip size mismatch: wrote {(sx, sy, sz)} got {loaded.shape}"
            )
        loaded_non_air = 0
        for idx in np.unique(loaded):
            nm = loaded_pal[int(idx)] if 0 <= int(idx) < len(loaded_pal) else "air"
            if not _is_air_name(nm):
                loaded_non_air += int((loaded == idx).sum())
        if abs(loaded_non_air - non_air) > max(1, non_air // 1000):
            raise RuntimeError(
                f"roundtrip non_air mismatch: wrote {non_air} got {loaded_non_air}"
            )
        # Spot-check: compare normalized names on a flat sample of cells
        flat_src = vox.reshape(-1)
        flat_dst = loaded.reshape(-1)
        step = max(1, flat_src.size // 4096)
        for i in range(0, flat_src.size, step):
            src = _resolve_name_for_id(int(flat_src[i]), palette)
            dst = loaded_pal[int(flat_dst[i])] if 0 <= int(flat_dst[i]) < len(loaded_pal) else "air"
            if _is_air_name(src) and _is_air_name(dst):
                continue
            if _normalize_block_name(src) != _normalize_block_name(dst):
                raise RuntimeError(
                    f"roundtrip block mismatch at flat[{i}]: {src} vs {dst}"
                )

    return {
        "path": out_path,
        "name": schematic_name,
        "size": (sx, sy, sz),
        "non_air": non_air,
        "palette_len": len(region_palette),
        "bits": bits,
        "loaded_non_air": loaded_non_air,
        "ok": True,
    }
