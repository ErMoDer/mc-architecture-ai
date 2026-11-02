"""Saved design schemes: named projects with voxels, history, and litematic refs.

Layout under schemes/<slug>/:
  scheme.json   meta (name, times, style/terrain, notes, version)
  current.npz   working voxels (size^3)
  current.mcfunction
  history/      timestamped snapshots before overwrite
  refs/         submitted .litematic originals
  versions/     stamped vNNN.npz + sidecar meta
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np

from src.app.sample_runner import load_voxel_npz, project_root, save_voxels_pair
from src.data.io_vox import save_npz_npz
from src.data.litematic import fit_to_cube, load_litematic
from src.data.export_litematic_util import export_voxels_to_companion
from src.utils import load_config, load_palette

MergeMode = Literal["replace", "overlay", "merge"]


def schemes_root(root: Path | None = None) -> Path:
    r = Path(root) if root else project_root()
    d = r / "schemes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def slugify(name: str) -> str:
    """Readable folder slug: ASCII + CJK kept; punctuation stripped. Display name stays in scheme.json.

    Pure-ASCII names are lowercased. Chinese-only names (e.g. 测试庄园) keep the
    characters so the folder matches the label — matching the existing schemes store.
    If nothing usable remains, fall back to scheme_<timestamp>.
    """
    s = str(name).strip()
    s = re.sub(r"\s+", "_", s)
    kept = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "", s).strip("_-")
    if len(kept) >= 1:
        # lower() is a no-op on CJK; keeps ASCII paths stable
        return kept.lower()[:80]
    return f"scheme_{_stamp()}"


def unique_slug(name: str, root: Path | None = None) -> str:
    base = slugify(name)
    root = schemes_root(root)
    if not (root / base).exists():
        return base
    i = 2
    while (root / f"{base}_{i}").exists():
        i += 1
    return f"{base}_{i}"


def scheme_dir(slug: str, root: Path | None = None) -> Path:
    return schemes_root(root) / slug


def meta_path(slug: str, root: Path | None = None) -> Path:
    return scheme_dir(slug, root) / "scheme.json"


def current_npz_path(slug: str, root: Path | None = None) -> Path:
    return scheme_dir(slug, root) / "current.npz"


def read_meta(slug: str, root: Path | None = None) -> dict[str, Any]:
    p = meta_path(slug, root)
    if not p.is_file():
        raise FileNotFoundError(f"scheme not found: {slug}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def write_meta(slug: str, meta: dict[str, Any], root: Path | None = None) -> Path:
    p = meta_path(slug, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return p


def list_schemes(root: Path | None = None) -> list[dict[str, Any]]:
    root = schemes_root(root)
    rows: list[dict[str, Any]] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        mp = d / "scheme.json"
        if not mp.is_file():
            continue
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        m = dict(m)
        m["slug"] = d.name
        m["path"] = str(d)
        cur = d / "current.npz"
        m["has_current"] = cur.is_file()
        rows.append(m)
    rows.sort(key=lambda r: r.get("updated") or r.get("created") or "", reverse=True)
    return rows


def _default_size(root: Path | None = None) -> int:
    r = Path(root) if root else project_root()
    try:
        cfg = load_config(r / "configs/default.yaml")
        return int(cfg["data"]["size"])
    except Exception:
        return 32


def _palette(root: Path | None = None) -> dict[int, str]:
    r = Path(root) if root else project_root()
    cfg = load_config(r / "configs/default.yaml")
    return load_palette(r / cfg["data"]["palette_path"])


def _name_to_id(palette: dict[int, str]) -> dict[str, int]:
    return {v: k for k, v in palette.items()}


def _empty_voxels(size: int) -> np.ndarray:
    return np.zeros((size, size, size), dtype=np.int16)


def _map_litematic_to_palette(
    voxels: np.ndarray, names: list[str], palette: dict[int, str]
) -> np.ndarray:
    """Map raw litematic palette indices to project palette ids."""
    n2i = _name_to_id(palette)
    air = n2i.get("minecraft:air", 0)
    lut = np.full(max(len(names), 1), air, dtype=np.int16)
    for i, name in enumerate(names):
        name = str(name)
        if name in n2i:
            lut[i] = n2i[name]
        elif name.endswith(":air"):
            lut[i] = air
        else:
            lut[i] = n2i.get("minecraft:stone", air)
    flat = np.asarray(voxels, dtype=np.int32).ravel()
    flat = np.clip(flat, 0, len(lut) - 1)
    mapped = lut[flat].reshape(voxels.shape)
    return mapped.astype(np.int16)


def load_litematic_as_voxels(
    path: Path | str,
    *,
    size: int | None = None,
    root: Path | None = None,
) -> np.ndarray:
    path = Path(path)
    size = int(size or _default_size(root))
    palette = _palette(root)
    raw, names, _meta = load_litematic(path)
    mapped = _map_litematic_to_palette(raw, names, palette)
    fitted = fit_to_cube(mapped, size=size, air_id=0)
    return fitted.astype(np.int16)


def merge_voxels(
    base: np.ndarray,
    incoming: np.ndarray,
    mode: MergeMode = "overlay",
) -> np.ndarray:
    a = np.asarray(base, dtype=np.int16)
    b = np.asarray(incoming, dtype=np.int16)
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch: {a.shape} vs {b.shape}")
    if mode == "replace":
        return b.copy()
    if mode == "overlay":
        out = a.copy()
        mask = b > 0
        out[mask] = b[mask]
        return out
    if mode == "merge":
        out = a.copy()
        only_b = (b > 0) & (a == 0)
        both = (b > 0) & (a > 0)
        out[only_b] = b[only_b]
        out[both] = b[both]
        return out
    raise ValueError(f"unknown merge mode: {mode}")


def snapshot_current(
    slug: str, root: Path | None = None, *, reason: str = "manual"
) -> Path | None:
    d = scheme_dir(slug, root)
    cur = d / "current.npz"
    if not cur.is_file():
        return None
    hist = d / "history"
    hist.mkdir(parents=True, exist_ok=True)
    dest = hist / f"{_stamp()}_{reason}.npz"
    shutil.copy2(cur, dest)
    meta = read_meta(slug, root)
    meta["history_count"] = int(meta.get("history_count") or 0) + 1
    meta["updated"] = _now_iso()
    write_meta(slug, meta, root)
    return dest


def _write_current(
    slug: str,
    voxels: np.ndarray,
    root: Path | None = None,
    *,
    snapshot: bool = True,
    reason: str = "save",
) -> dict[str, Any]:
    d = scheme_dir(slug, root)
    d.mkdir(parents=True, exist_ok=True)
    (d / "history").mkdir(exist_ok=True)
    (d / "refs").mkdir(exist_ok=True)
    (d / "versions").mkdir(exist_ok=True)
    if snapshot and (d / "current.npz").is_file():
        snapshot_current(slug, root, reason=reason)
    palette = _palette(root)
    meta_files = save_voxels_pair(voxels, palette, d / "current.npz")
    m = read_meta(slug, root)
    m["updated"] = _now_iso()
    m["non_air"] = int((np.asarray(voxels) > 0).sum())
    m["size"] = int(voxels.shape[0])
    write_meta(slug, m, root)
    return {
        "slug": slug,
        "dir": d,
        "npz": meta_files["npz_path"],
        "mcfunction": meta_files["mcfunction_path"],
        "non_air": meta_files["non_air"],
        "meta": m,
    }


def create_scheme(
    name: str,
    *,
    voxels: np.ndarray | None = None,
    from_npz: Path | str | None = None,
    from_litematic: Path | str | None = None,
    style: str = "medieval",
    terrain: str = "flat",
    notes: str = "",
    slug: str | None = None,
    root: Path | None = None,
    size: int | None = None,
) -> dict[str, Any]:
    root_p = Path(root) if root else project_root()
    size = int(size or _default_size(root_p))
    slug = slug or unique_slug(name, root_p)
    d = scheme_dir(slug, root_p)
    if d.exists() and (d / "scheme.json").is_file():
        raise FileExistsError(f"scheme already exists: {slug}")
    d.mkdir(parents=True, exist_ok=True)
    (d / "history").mkdir(exist_ok=True)
    (d / "refs").mkdir(exist_ok=True)
    (d / "versions").mkdir(exist_ok=True)

    if voxels is not None:
        vox = np.asarray(voxels, dtype=np.int16)
    elif from_npz is not None:
        vox = load_voxel_npz(from_npz)
    elif from_litematic is not None:
        src = Path(from_litematic)
        ref_dest = d / "refs" / src.name
        shutil.copy2(src, ref_dest)
        vox = load_litematic_as_voxels(src, size=size, root=root_p)
    else:
        vox = _empty_voxels(size)

    if vox.shape != (size, size, size):
        vox = fit_to_cube(vox, size=size, air_id=0).astype(np.int16)

    now = _now_iso()
    meta = {
        "name": name,
        "slug": slug,
        "created": now,
        "updated": now,
        "style": style,
        "terrain": terrain,
        "notes": notes,
        "size": size,
        "version": 1,
        "history_count": 0,
        "non_air": int((vox > 0).sum()),
        "refs": [],
    }
    if from_litematic is not None:
        meta["refs"] = [Path(from_litematic).name]
    write_meta(slug, meta, root_p)
    palette = _palette(root_p)
    save_voxels_pair(vox, palette, d / "current.npz")
    return {"slug": slug, "dir": d, "meta": meta, "non_air": meta["non_air"]}


def save_scheme(
    slug: str,
    voxels: np.ndarray,
    *,
    notes: str | None = None,
    style: str | None = None,
    terrain: str | None = None,
    bump_version: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    meta = read_meta(slug, root)
    if notes is not None:
        meta["notes"] = notes
    if style is not None:
        meta["style"] = style
    if terrain is not None:
        meta["terrain"] = terrain
    write_meta(slug, meta, root)
    result = _write_current(slug, voxels, root, snapshot=True, reason="save")
    if bump_version:
        stamp_version(slug, root=root, label="save")
        result["meta"] = read_meta(slug, root)
    return result


def load_scheme(slug: str, root: Path | None = None) -> dict[str, Any]:
    meta = read_meta(slug, root)
    npz = current_npz_path(slug, root)
    if not npz.is_file():
        raise FileNotFoundError(f"missing current.npz for scheme {slug}")
    voxels = load_voxel_npz(npz)
    return {
        "slug": slug,
        "meta": meta,
        "voxels": voxels,
        "npz_path": npz,
        "dir": scheme_dir(slug, root),
    }


def stamp_version(slug: str, root: Path | None = None, *, label: str = "") -> Path:
    d = scheme_dir(slug, root)
    ver_dir = d / "versions"
    ver_dir.mkdir(exist_ok=True)
    meta = read_meta(slug, root)
    ver = int(meta.get("version") or 1)
    dest = ver_dir / f"v{ver:03d}.npz"
    shutil.copy2(d / "current.npz", dest)
    side = {
        "version": ver,
        "label": label,
        "stamped": _now_iso(),
        "non_air": meta.get("non_air"),
        "notes": meta.get("notes", ""),
    }
    (ver_dir / f"v{ver:03d}.json").write_text(
        json.dumps(side, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    meta["version"] = ver + 1
    meta["updated"] = _now_iso()
    write_meta(slug, meta, root)
    return dest


def import_litematic(
    slug: str,
    litematic_path: Path | str,
    *,
    mode: MergeMode = "overlay",
    root: Path | None = None,
) -> dict[str, Any]:
    meta = read_meta(slug, root)
    size = int(meta.get("size") or _default_size(root))
    src = Path(litematic_path)
    if not src.is_file():
        raise FileNotFoundError(src)
    d = scheme_dir(slug, root)
    refs = d / "refs"
    refs.mkdir(exist_ok=True)
    dest_ref = refs / f"{_stamp()}_{src.name}"
    shutil.copy2(src, dest_ref)
    incoming = load_litematic_as_voxels(src, size=size, root=root)
    cur_path = current_npz_path(slug, root)
    if cur_path.is_file() and mode != "replace":
        base = load_voxel_npz(cur_path)
        merged = merge_voxels(base, incoming, mode=mode)
    else:
        merged = incoming
    refs_list = list(meta.get("refs") or [])
    refs_list.append(dest_ref.name)
    meta["refs"] = refs_list
    meta["updated"] = _now_iso()
    meta["last_import"] = {
        "file": dest_ref.name,
        "mode": mode,
        "at": _now_iso(),
    }
    write_meta(slug, meta, root)
    result = _write_current(slug, merged, root, snapshot=True, reason=f"import_{mode}")
    stamp_version(slug, root=root, label=f"import-{mode}")
    result["ref"] = dest_ref
    result["mode"] = mode
    result["meta"] = read_meta(slug, root)
    return result


def apply_block_replace(
    slug: str,
    source_id: int,
    target_id: int,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    data = load_scheme(slug, root)
    vox = data["voxels"].copy()
    mask = vox == int(source_id)
    n = int(mask.sum())
    vox[mask] = int(target_id)
    result = _write_current(slug, vox, root, snapshot=True, reason="edit_replace")
    result["replaced"] = n
    return result


def export_scheme_litematic(
    slug: str,
    *,
    out_dir: Path | str | None = None,
    name: str | None = None,
    target_version: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    data = load_scheme(slug, root)
    palette = _palette(root)
    export_name = name or slug
    return export_voxels_to_companion(
        data["voxels"],
        palette,
        name=export_name,
        out_dir=Path(out_dir) if out_dir else None,
        target_version=target_version,
    )


def export_scheme_npz(slug: str, dest: Path | str, root: Path | None = None) -> Path:
    data = load_scheme(slug, root)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    save_npz_npz(dest, data["voxels"])
    return dest
