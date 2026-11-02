"""可复用的采样与体素编辑逻辑，供桌面预览应用调用（不改 scripts/sample.py 行为）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import torch

from src.data.export_mcfunction import export_mcfunction
from src.data.io_vox import save_npz_npz
from src.models import ConditionalVoxelVAE, VoxelVAE
from src.data.labels import load_vocab, resolve_style_id, resolve_terrain_id
from src.utils import load_config, load_palette, resolve_device, set_seed
from src.app.structure_constraints import (
    apply_structure_constraints,
    check_structure,
    summarize_metrics_list,
)
from src.app.look_harden import look_harden


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_voxel_npz(path: Path | str) -> np.ndarray:
    path = Path(path)
    with np.load(path) as data:
        if "voxels" not in data:
            raise KeyError(f"{path} 中没有 voxels 数组")
        return np.asarray(data["voxels"], dtype=np.int16)


def list_sample_files(out_dir: Path | str | None = None) -> list[Path]:
    root = project_root()
    if out_dir is None:
        cfg = load_config(root / "configs/default.yaml")
        out_dir = root / cfg["sample"]["out_dir"]
    else:
        out_dir = Path(out_dir)
    if not out_dir.is_dir():
        return []
    files: list[Path] = []
    for p in sorted(out_dir.glob("sample_*.npz")):
        stem = p.stem  # sample_000 / sample_edit_001 / sample_smedieval_tflat_000
        if (
            re.fullmatch(r"sample_\d+", stem)
            or re.fullmatch(r"sample_edit_\d+", stem)
            or re.fullmatch(r"sample_s.+_t.+_\d+", stem)
        ):
            files.append(p)
    return files


def list_checkpoints(ckpt_dir: Path | str | None = None) -> list[Path]:
    root = project_root()
    d = Path(ckpt_dir) if ckpt_dir else root / "checkpoints"
    if not d.is_dir():
        return []
    pts = sorted(d.glob("*.pt"))
    pts.sort(key=lambda p: (0 if p.name == "last.pt" else 1, p.name))
    return pts


def short_block_name(full: str) -> str:
    if ":" in full:
        return full.split(":", 1)[1]
    return full


def count_blocks(
    voxels: np.ndarray, palette: dict[int, str]
) -> list[dict[str, Any]]:
    """统计非空气方块，按数量降序。"""
    flat = voxels.ravel()
    ids, counts = np.unique(flat[flat > 0], return_counts=True)
    rows: list[dict[str, Any]] = []
    for bid, cnt in zip(ids.tolist(), counts.tolist()):
        name = palette.get(int(bid), f"unknown:{bid}")
        rows.append(
            {
                "id": int(bid),
                "name": name,
                "short": short_block_name(name),
                "count": int(cnt),
            }
        )
    rows.sort(key=lambda r: (-r["count"], r["id"]))
    return rows


def replace_block_id(voxels: np.ndarray, source_id: int, target_id: int) -> tuple[np.ndarray, int]:
    """返回替换后的副本与替换数量。"""
    out = voxels.copy()
    mask = out == int(source_id)
    n = int(mask.sum())
    if n:
        out[mask] = int(target_id)
    return out, n


def next_edit_path(out_dir: Path) -> Path:
    """下一个 sample_edit_XXX.npz 路径。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = 0
    while True:
        p = out_dir / f"sample_edit_{idx:03d}.npz"
        if not p.exists():
            return p
        idx += 1


def save_voxels_pair(
    voxels: np.ndarray,
    palette: dict[int, str],
    npz_path: Path | str,
    *,
    origin: tuple[int, int, int] = (0, 64, 0),
) -> dict[str, Any]:
    """写出 .npz + .mcfunction。"""
    npz_path = Path(npz_path)
    mc_path = npz_path.with_suffix(".mcfunction")
    save_npz_npz(npz_path, voxels)
    commands = export_mcfunction(voxels, palette, mc_path, origin=origin)
    non_air = int((voxels > 0).sum())
    return {
        "npz_path": npz_path,
        "mcfunction_path": mc_path,
        "non_air": non_air,
        "commands": commands,
    }




def generate_samples(
    *,
    num: int = 1,
    temperature: float = 1.0,
    checkpoint: str | Path | None = None,
    config_path: str | Path | None = None,
    out_dir: str | Path | None = None,
    seed: int | None = None,
    style: str | int | None = None,
    terrain: str | int | None = None,
    vocab_path: str | Path | None = None,
    structure_constrain: bool = False,
    structure_mode: str = "repair",
    structure_max_tries: int = 8,
    look_harden_enable: bool | None = None,
    look_harden_top_k: int = 6,
    preserve_windows: bool = True,
    place_window_glass: bool = True,
) -> list[dict[str, Any]]:
    """采样并写出 .npz + .mcfunction。可选结构约束（空心/楼层/屋顶）。"""
    root = project_root()
    cfg = load_config(root / (config_path or "configs/default.yaml"))
    if seed is not None:
        set_seed(int(seed))
    else:
        set_seed(int(cfg["seed"]))

    device = resolve_device(cfg["device"])
    size = int(cfg["data"]["size"])
    palette = load_palette(root / cfg["data"]["palette_path"])
    num_classes = max(palette) + 1

    ckpt_path = Path(checkpoint) if checkpoint else root / cfg["sample"]["checkpoint"]
    if not ckpt_path.is_absolute():
        ckpt_path = root / ckpt_path
    if not ckpt_path.exists():
        raise FileNotFoundError("找不到权重：%s" % ckpt_path)

    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    conditional = bool(ckpt.get("conditional"))
    n = max(1, min(int(num), 8))
    temp = float(temperature)

    style_id = 0
    terrain_id = 0
    style_key = "medieval"
    terrain_key = "flat"

    if conditional:
        vpath = root / (vocab_path or "data/label_vocab.json")
        vocab = ckpt.get("vocab") or load_vocab(vpath)
        if "style_to_id" not in vocab:
            vocab = load_vocab(vpath)
        num_styles = int(ckpt.get("num_styles") or len(vocab["styles"]))
        num_terrains = int(ckpt.get("num_terrains") or len(vocab["terrains"]))
        style_key = style if style is not None else "medieval"
        terrain_key = terrain if terrain is not None else "flat"
        style_id = resolve_style_id(vocab, style_key)
        terrain_id = resolve_terrain_id(vocab, terrain_key)
        model = ConditionalVoxelVAE(
            num_classes=ckpt.get("num_classes", num_classes),
            num_styles=num_styles,
            num_terrains=num_terrains,
            latent_dim=int(cfg["model"]["latent_dim"]),
            base_channels=int(cfg["model"]["base_channels"]),
            size=size,
            cond_emb_dim=int(cfg["model"].get("cond_emb_dim", 32)),
        ).to(device)
        model.load_state_dict(ckpt["model"])
        model.eval()
        samples = (
            model.sample(
                n,
                device=device,
                temperature=temp,
                style_id=style_id,
                terrain_id=terrain_id,
            )
            .cpu()
            .numpy()
            .astype(np.int16)
        )
        name_prefix = "sample_s%s_t%s_" % (style_key, terrain_key)
    else:
        model = VoxelVAE(
            num_classes=ckpt.get("num_classes", num_classes),
            latent_dim=int(cfg["model"]["latent_dim"]),
            base_channels=int(cfg["model"]["base_channels"]),
            size=size,
        ).to(device)
        model.load_state_dict(ckpt["model"])
        model.eval()
        samples = model.sample(n, device=device, temperature=temp).cpu().numpy().astype(np.int16)
        name_prefix = "sample_"

    dest = Path(out_dir) if out_dir else root / cfg["sample"]["out_dir"]
    if not dest.is_absolute():
        dest = root / dest
    dest.mkdir(parents=True, exist_ok=True)

    structure_mode_l = (structure_mode or "repair").lower()

    def _sample_batch(k: int) -> np.ndarray:
        if conditional:
            return (
                model.sample(
                    k,
                    device=device,
                    temperature=temp,
                    style_id=style_id,
                    terrain_id=terrain_id,
                )
                .cpu()
                .numpy()
                .astype(np.int16)
            )
        return model.sample(k, device=device, temperature=temp).cpu().numpy().astype(np.int16)

    results: list[dict[str, Any]] = []
    need = n
    produced = 0
    attempt = 0
    max_attempts = need
    if structure_constrain:
        max_attempts = max(need, need * max(1, int(structure_max_tries)))
    raw_pool = samples
    pool_idx = 0

    while produced < need and attempt < max_attempts:
        attempt += 1
        if pool_idx < len(raw_pool):
            vox = raw_pool[pool_idx]
            pool_idx += 1
        else:
            vox = _sample_batch(1)[0]

        pre = check_structure(vox)
        if structure_constrain and structure_mode_l == "reject":
            if not pre.ok:
                continue
            out_vox = vox
            rep = pre
        elif structure_constrain:
            if structure_mode_l == "reject_then_repair" and pre.ok:
                out_vox, rep = vox, pre
            else:
                out_vox, rep = apply_structure_constraints(vox, mode="repair")
                if structure_mode_l == "reject_then_repair" and not rep.ok:
                    continue
        else:
            out_vox, rep = vox, pre

        # Look harden: palette top-K + shell/floors (default ON with structure)
        do_look = look_harden_enable
        if do_look is None:
            do_look = bool(structure_constrain)
        look_rep = None
        if do_look:
            style_for_look = str(style_key) if conditional else None
            out_vox, look_rep = look_harden(
                out_vox,
                palette,
                style=style_for_look,
                top_k=int(look_harden_top_k),
                preserve_windows=bool(preserve_windows),
                place_window_glass=bool(place_window_glass),
            )
            rep = check_structure(out_vox)
            if look_rep.actions and getattr(rep, "repairs", None) is not None:
                rep.repairs = list(getattr(rep, "repairs", []) or []) + [
                    "look_harden"
                ]

        if conditional:
            npz_path = dest / ("%s%03d.npz" % (name_prefix, produced))
        else:
            npz_path = dest / ("sample_%03d.npz" % produced)
        meta = save_voxels_pair(out_vox, palette, npz_path)
        meta["index"] = produced
        meta["voxels"] = out_vox
        meta["structure"] = rep.to_dict()
        meta["structure_pre"] = pre.to_dict()
        if conditional:
            meta["style"] = str(style_key)
            meta["terrain"] = str(terrain_key)
        if structure_constrain:
            meta["structure_constrain"] = True
            meta["structure_mode"] = structure_mode_l
        if look_rep is not None:
            meta["look_harden"] = look_rep.to_dict()
        results.append(meta)
        produced += 1

    return results

def load_label_vocab(vocab_path: str | Path | None = None) -> dict[str, Any]:
    root = project_root()
    p = Path(vocab_path) if vocab_path else root / "data/label_vocab.json"
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        return {"styles": ["unknown"], "terrains": ["flat"]}
    return load_vocab(p)

