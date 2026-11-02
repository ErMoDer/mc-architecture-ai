"""两阶段采样：occupancy 模型生成形状，material 模型在形状内填材质。"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.labels import resolve_style_id, resolve_terrain_id  # noqa: E402
from src.models import ConditionalVoxelVAE, ShapeMaterialVAE  # noqa: E402
from src.utils import resolve_device  # noqa: E402


def load_model(path: str, device: torch.device) -> tuple[torch.nn.Module, dict]:
    ck = torch.load(path, map_location=device, weights_only=False)
    mcfg = (ck.get("config") or {}).get("model", {})
    kwargs = dict(
        num_classes=int(ck["num_classes"]),
        num_styles=int(ck["num_styles"]),
        num_terrains=int(ck["num_terrains"]),
        latent_dim=int(mcfg.get("latent_dim", 128)),
        base_channels=int(mcfg.get("base_channels", 32)),
        size=int(mcfg.get("size", 32) or 32),
        cond_emb_dim=int(mcfg.get("cond_emb_dim", 32)),
    )
    cls = ShapeMaterialVAE if ck.get("shape_cond") else ConditionalVoxelVAE
    model = cls(**kwargs).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    return model, ck


@torch.no_grad()
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--occ", required=True, help="occupancy checkpoint")
    ap.add_argument("--mat", required=True, help="material checkpoint")
    ap.add_argument("--style", default="medieval")
    ap.add_argument("--terrain", default="flat")
    ap.add_argument("--num", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument(
        "--solid-frac",
        type=float,
        default=None,
        help="按分位数定阈值，使预测实心比例约等于该值（如 0.05 对齐训练数据）。不填则用概率随机采样",
    )
    ap.add_argument("--out-dir", required=True)
    ap.add_argument(
        "--snap-ground",
        action="store_true",
        default=True,
        help="输出前把最低实心层滚到 y=0（默认开启）",
    )
    ap.add_argument("--no-snap-ground", dest="snap_ground", action="store_false")
    ap.add_argument("--cfg", default="configs/default.yaml")
    args = ap.parse_args()

    device = resolve_device("auto")
    occ, ck_occ = load_model(args.occ, device)
    mat, ck_mat = load_model(args.mat, device)
    size = occ.size

    vocab = ck_occ.get("vocab") or json.load(open(ROOT / "data/label_vocab.json", encoding="utf-8"))
    sid = resolve_style_id(vocab, args.style)
    tid = resolve_terrain_id(vocab, args.terrain)

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    g = torch.Generator(device=device).manual_seed(args.seed)
    rows = []
    for i in range(args.num):
        z = torch.randn(1, occ.latent_dim, device=device, generator=g) * args.temperature
        s = torch.full((1,), sid, device=device, dtype=torch.long)
        t = torch.full((1,), tid, device=device, dtype=torch.long)
        occ_logits = occ.decode(occ.fuse_condition(z, s, t))
        p_solid = torch.softmax(occ_logits, dim=1)[0, 1]
        if args.solid_frac is not None:
            # 分位数校准：取概率最高的前 solid_frac 比例为实心
            k = max(1, int(p_solid.numel() * args.solid_frac))
            flat = p_solid.flatten()
            thr = torch.topk(flat, k).values[-1]
            solid = p_solid >= thr
        else:
            solid = torch.rand_like(p_solid) < p_solid

        if isinstance(mat, ShapeMaterialVAE):
            vox = mat.sample(solid.float().unsqueeze(0), s, t, temperature=args.temperature)
        else:
            mz = torch.randn(1, mat.latent_dim, device=device, generator=g) * args.temperature
            mat_logits = mat.decode(mat.fuse_condition(mz, s, t))[0]
            mat_logits[0] = -1e9  # 材质模型不产出空气；空气由 occupancy 决定
            vox = mat_logits.argmax(dim=0)
        vox = torch.where(solid, vox, torch.zeros_like(vox))

        arr = vox.cpu().numpy().astype(np.int16)
        y_off = 0
        if args.snap_ground and (arr > 0).any():
            ys = np.where((arr > 0).any(axis=(0, 2)))[0]
            y_off = int(ys[0])
            if y_off:
                arr = np.roll(arr, -y_off, axis=1)
        n = int((arr > 0).sum())
        idx = np.where((arr > 0).any(axis=(1, 2)))[0]
        bbox = None
        if n:
            ys = np.where((arr > 0).any(axis=(0, 2)))[0]
            zs = np.where((arr > 0).any(axis=(0, 1)))[0]
            bbox = (int(idx[-1] - idx[0] + 1), int(ys[-1] - ys[0] + 1), int(zs[-1] - zs[0] + 1))
        mats = int(len(np.unique(arr[arr > 0])))
        rows.append(
            {
                "i": i,
                "non_air": n,
                "bbox": bbox,
                "materials": mats,
                "y_offset": y_off,
                "p_solid_mean": round(float(p_solid.mean()), 4),
            }
        )
        np.savez_compressed(out_dir / f"two_stage_{args.style}_{args.terrain}_{i:03d}.npz", voxels=arr)
    print(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
