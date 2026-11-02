"""训练体素 VAE（路线 A MVP），支持 --conditional 条件风格/地形。"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import VoxelBuildDataset
from src.data.labels import load_vocab
from src.models import ConditionalVoxelVAE, VoxelVAE
from src.utils import load_config, load_palette, resolve_device, set_seed


def _expand_class_tensors(state: dict, old_n: int, new_n: int) -> dict:
    """Grow embedding / final conv class dims when palette expands; keep old rows."""
    if old_n == new_n:
        return state
    if new_n < old_n:
        raise SystemExit(f"cannot shrink classes {old_n} -> {new_n}")
    out = dict(state)
    for key, tensor in state.items():
        if not hasattr(tensor, "shape"):
            continue
        # embed.weight: [C, D]
        if key.endswith("embed.weight") and tensor.ndim == 2 and tensor.shape[0] == old_n:
            import torch
            expanded = tensor.new_zeros((new_n, tensor.shape[1]))
            expanded[:old_n] = tensor
            if new_n > old_n:
                expanded[old_n:] = tensor.mean(dim=0, keepdim=True)
            out[key] = expanded
            print(f"expand {key} {tuple(tensor.shape)} -> {tuple(expanded.shape)}")
        # final 1x1x1 conv: weight [C, in, 1,1,1], bias [C]
        elif key.endswith("dec.8.weight") and tensor.ndim == 5 and tensor.shape[0] == old_n:
            import torch
            expanded = tensor.new_zeros((new_n, *tensor.shape[1:]))
            expanded[:old_n] = tensor
            if new_n > old_n:
                expanded[old_n:] = tensor.mean(dim=0, keepdim=True)
            out[key] = expanded
            print(f"expand {key} {tuple(tensor.shape)} -> {tuple(expanded.shape)}")
        elif key.endswith("dec.8.bias") and tensor.ndim == 1 and tensor.shape[0] == old_n:
            import torch
            expanded = tensor.new_zeros((new_n,))
            expanded[:old_n] = tensor
            if new_n > old_n:
                expanded[old_n:] = tensor.mean()
            out[key] = expanded
            print(f"expand {key} {tuple(tensor.shape)} -> {tuple(expanded.shape)}")
    return out



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument(
        "--conditional",
        action="store_true",
        help="按 style/terrain 条件训练，写出 checkpoints/cond_last.pt",
    )
    parser.add_argument("--vocab", default="data/label_vocab.json")
    parser.add_argument("--labels", default="data/processed/labels.json")
    parser.add_argument(
        "--resume",
        default=None,
        help="checkpoint path to load weights from (e.g. checkpoints/cond_last.pt)",
    )
    parser.add_argument(
        "--start-epoch",
        type=int,
        default=0,
        help="offset so logged epoch = start_epoch + loop; use with --resume",
    )
    parser.add_argument(
        "--processed-dir",
        default=None,
        help="override data.processed_dir (e.g. data/processed/hack337); does not rewrite yaml",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=None,
        help="override train.lr (useful for short fine-tunes)",
    )
    parser.add_argument(
        "--ckpt-dir",
        default=None,
        help="override checkpoint output dir (default checkpoints/); useful when the project dir is not writable",
    )
    parser.add_argument(
        "--freeze-palette",
        action="store_true",
        help="Keep checkpoint num_classes; do not expand class heads. Remap OOV block ids (>= num_classes) to air (0).",
    )
    parser.add_argument(
        "--binary",
        action="store_true",
        help="两阶段-形状：输入输出二值化（air=0/实心=1），num_classes=2，从头训练",
    )
    parser.add_argument(
        "--solid-only",
        action="store_true",
        help="两阶段-材质：交叉熵只在实心体素上计算（air 忽略，不参与竞争）",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="checkpoint 文件名前缀（如 occ/mat），默认沿用 cond/空",
    )
    args = parser.parse_args()

    cfg = load_config(ROOT / args.config)
    conditional = bool(args.conditional or cfg.get("model", {}).get("conditional", False))
    set_seed(int(cfg["seed"]))
    device = resolve_device(cfg["device"])

    size = int(cfg["data"]["size"])
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    data_num_classes = max(palette) + 1
    num_classes = 2 if args.binary else data_num_classes
    freeze_palette = bool(args.freeze_palette)
    resume_ckpt = None
    if args.resume:
        resume_path_early = ROOT / args.resume
        if not resume_path_early.exists():
            raise SystemExit(f"resume checkpoint missing: {resume_path_early}")
        resume_ckpt = torch.load(resume_path_early, map_location="cpu", weights_only=False)
        ckpt_classes = int(resume_ckpt.get("num_classes") or 0)
        if freeze_palette:
            if not ckpt_classes:
                raise SystemExit("--freeze-palette requires checkpoint num_classes")
            num_classes = ckpt_classes
            print(
                f"freeze-palette: ckpt_classes={ckpt_classes} data_palette_classes={data_num_classes}; "
                f"OOV ids >= {num_classes} -> air(0); no class-head expand"
            )
        elif ckpt_classes and ckpt_classes != data_num_classes:
            print(f"palette size ckpt={ckpt_classes} data={data_num_classes} (will expand on load if larger)")

    processed_dir = Path(args.processed_dir) if args.processed_dir else Path(cfg["data"]["processed_dir"])
    if not processed_dir.is_absolute():
        processed_dir = ROOT / processed_dir
    print(f"processed_dir={processed_dir}")

    ds = VoxelBuildDataset(
        processed_dir,
        size=size,
        conditional=conditional,
        labels_path=ROOT / args.labels if conditional else None,
    )
    batch_size = args.batch_size or int(cfg["train"]["batch_size"])
    loader = DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=int(cfg["train"]["num_workers"]),
        drop_last=len(ds) >= batch_size,
    )

    def _remap_oov(voxels: torch.Tensor) -> torch.Tensor:
        if not freeze_palette:
            return voxels
        out = voxels.clone()
        out[out >= num_classes] = 0
        return out

    # 按体素频率估权重
    counts = torch.zeros(num_classes, dtype=torch.float64)
    oov_vox = 0
    for i in range(len(ds)):
        item = ds[i]
        v = (item[0] if conditional else item).reshape(-1)
        if args.binary:
            v = (v > 0).long()
        v_min, v_max = int(v.min()), int(v.max())
        if v_min < 0 or v_max >= num_classes:
            if not freeze_palette:
                raise SystemExit(
                    f"数据越界：{ds.files[i].name} 的方块 ID 范围 [{v_min}, {v_max}]，"
                    f"超出 palette 范围 [0, {num_classes - 1}]。\n"
                    "GPU 上训练会以 CUDA illegal memory access 崩溃。请重新生成 palette，"
                    "或加 --freeze-palette 将越界 ID 重映射为 air(0)。"
                )
            oov_vox += int((v >= num_classes).sum().item())
            v = v.clone()
            v[v >= num_classes] = 0
        counts += torch.bincount(v, minlength=num_classes).to(torch.float64)
    if freeze_palette:
        print(f"freeze-palette OOV voxels remapped to air: {oov_vox}")
    freq = counts / counts.sum().clamp_min(1)
    # 两级平衡权重（极端类别不平衡的标准做法）：
    # 1) 空气 vs 实心 先平衡：空气占 94.8%，若不平权，逐体素决策永远是空气赢
    #    （损失里每体素按 w[c] 加权，argmax 看 w*p，空气 0.948*w_air 会压过实心）
    #    实心类整体乘 freq_air/freq_solid_total ≈ 18，使两侧总损失质量各占一半
    # 2) 实心类内部按稀有度温和上调（开方 + 限幅），防止常见材质淹没稀有材质
    air_w = 1.0
    solid_freq = freq[1:]
    solid_total = solid_freq.sum().clamp_min(1e-12)
    med = solid_freq[solid_freq > 0].median().clamp_min(1e-12)
    balance = (med / solid_freq.clamp_min(1e-12)).clamp(1.0, 10.0).sqrt()
    solid_w = (float(freq[0]) / float(solid_total)) * balance
    weights = torch.cat([torch.tensor([air_w], dtype=torch.float64), solid_w])
    if args.solid_only:
        # 材质阶段空气不参与损失，权重无意义，显式置 0
        weights[0] = 0.0
    # 归一化到“平均体素权重=1”，便于和旧 loss 量级对照
    weights = weights / (weights * freq).sum().clamp_min(1e-12)
    print(f"class_weights: air={float(weights[0]):.4f} "
          f"solid_min={float(weights[1:].min()):.3f} solid_med={float(weights[1:].median()):.3f} "
          f"solid_max={float(weights[1:].max()):.3f}")
    class_weights = weights.to(dtype=torch.float32, device=device)

    vocab = None
    num_styles = num_terrains = 0
    if conditional:
        vocab = load_vocab(ROOT / args.vocab)
        num_styles = int(vocab.get("num_styles") or len(vocab["styles"]))
        num_terrains = int(vocab.get("num_terrains") or len(vocab["terrains"]))
        model = ConditionalVoxelVAE(
            num_classes=num_classes,
            num_styles=num_styles,
            num_terrains=num_terrains,
            latent_dim=int(cfg["model"]["latent_dim"]),
            base_channels=int(cfg["model"]["base_channels"]),
            size=size,
            cond_emb_dim=int(cfg["model"].get("cond_emb_dim", 32)),
        ).to(device)
    else:
        model = VoxelVAE(
            num_classes=num_classes,
            latent_dim=int(cfg["model"]["latent_dim"]),
            base_channels=int(cfg["model"]["base_channels"]),
            size=size,
        ).to(device)

    lr = float(args.lr) if args.lr is not None else float(cfg["train"]["lr"])
    print(f"lr={lr}")
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=float(cfg["train"]["weight_decay"]),
    )

    start_epoch = int(args.start_epoch or 0)
    if args.resume:
        resume_path = ROOT / args.resume
        ckpt = resume_ckpt if resume_ckpt is not None else torch.load(resume_path, map_location=device, weights_only=False)
        # move tensors to device via load_state_dict; keep ckpt on CPU is fine
        state = ckpt["model"]
        old_classes = int(ckpt.get("num_classes") or 0)
        if old_classes and old_classes != num_classes:
            if freeze_palette:
                raise SystemExit(
                    f"freeze-palette mismatch: ckpt={old_classes} model={num_classes}"
                )
            print(f"palette grew {old_classes} -> {num_classes}; expanding class heads")
            state = _expand_class_tensors(state, old_classes, num_classes)
        elif freeze_palette:
            print(f"freeze-palette: skipping expand (classes={num_classes})")
        missing, unexpected = model.load_state_dict(state, strict=False)
        if missing or unexpected:
            print(f"load_state_dict missing={list(missing)[:8]} unexpected={list(unexpected)[:8]}")
        if start_epoch <= 0:
            start_epoch = int(ckpt.get("epoch") or 0)
        print(f"resumed weights from {resume_path} (ckpt_epoch={ckpt.get('epoch')} start_epoch={start_epoch})")

    ckpt_dir = Path(args.ckpt_dir) if args.ckpt_dir else ROOT / "checkpoints"
    if not ckpt_dir.is_absolute():
        ckpt_dir = ROOT / ckpt_dir
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    # 条件训练不覆盖无条件 last.pt；若存在则备份一份
    if args.name:
        tag = args.name
        last_name = f"{tag}_last.pt"
    elif conditional:
        tag = "cond"
        last = ckpt_dir / "last.pt"
        if last.exists():
            bak = ckpt_dir / f"last_uncond_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
            if not any(ckpt_dir.glob("last_uncond_backup_*.pt")):
                shutil.copy2(last, bak)
                print(f"backup uncond last.pt -> {bak.name}")
        last_name = "cond_last.pt"
    else:
        tag = ""
        last_name = "last.pt"

    epochs = args.epochs or int(cfg["train"]["epochs"])
    beta = float(cfg["train"]["beta"])

    print(
        f"device={device}  samples={len(ds)}  size={size}  classes={num_classes}  "
        f"conditional={conditional}  freeze_palette={freeze_palette}  data_classes={data_num_classes}"
    )
    if conditional:
        print(f"num_styles={num_styles} num_terrains={num_terrains}")
        print(f"styles={vocab['styles']}")
        print(f"terrains={vocab['terrains']}")
    print(f"class_weights[0:5]={class_weights[:5].tolist()}")

    global_step = 0
    total_target = start_epoch + epochs
    for epoch in range(start_epoch + 1, total_target + 1):
        model.train()
        pbar = tqdm(loader, desc=f"epoch {epoch}/{total_target}")
        running = {"loss": 0.0, "recon": 0.0, "kl": 0.0, "acc": 0.0, "solid_acc": 0.0, "pred_solid": 0.0}
        n = 0
        for batch in pbar:
            opt.zero_grad(set_to_none=True)
            if conditional:
                voxels, style_id, terrain_id = batch
                voxels = _remap_oov(voxels.to(device))
                if args.binary:
                    voxels = (voxels > 0).long()
                style_id = style_id.to(device)
                terrain_id = terrain_id.to(device)
                loss, stats = model.loss(
                    voxels, style_id, terrain_id, beta=beta,
                    class_weights=class_weights, ignore_air=bool(args.solid_only),
                )
            else:
                voxels = _remap_oov(batch.to(device))
                if args.binary:
                    voxels = (voxels > 0).long()
                loss, stats = model.loss(voxels, beta=beta, class_weights=class_weights)
            loss.backward()
            opt.step()
            n += 1
            for k in running:
                running[k] += stats.get(k, 0.0)
            global_step += 1
            if global_step % int(cfg["train"]["log_every"]) == 0:
                pbar.set_postfix({k: f"{running[k]/n:.4f}" for k in ("loss", "recon", "solid_acc")})

        avg = {k: running[k] / max(n, 1) for k in running}
        print(
            f"epoch {epoch}: loss={avg['loss']:.4f} recon={avg['recon']:.4f} "
            f"kl={avg['kl']:.4f} acc={avg['acc']:.4f} solid_acc={avg['solid_acc']:.4f} "
            f"pred_solid={avg['pred_solid']:.4f}"
        )
        # 塌陷保护：预测实心比例应接近数据的 ~5%；跑偏成“全实心/全空气”立刻停，别白烧算力
        # 前 2 轮是从旧权重过渡的预热期，实心比例天然偏高，不参与判定
        # 材质阶段（--solid-only）空气无监督，pred_solid 无意义，跳过
        if conditional and not args.solid_only and epoch >= start_epoch + 3:
            ps = avg["pred_solid"]
            if ps > 0.60:
                raise SystemExit(f"检测到实心塌陷 pred_solid={ps:.3f} > 0.60，已停止训练")
            if ps < 0.012:
                raise SystemExit(f"检测到空气塌陷 pred_solid={ps:.4f} < 0.012，已停止训练")

        payload = {
            "model": model.state_dict(),
            "config": cfg,
            "num_classes": num_classes,
            "epoch": epoch,
            "conditional": conditional,
            "binary": bool(args.binary),
            "solid_only": bool(args.solid_only),
            "num_styles": num_styles if conditional else None,
            "num_terrains": num_terrains if conditional else None,
            "vocab": {
                "styles": vocab["styles"],
                "terrains": vocab["terrains"],
                "style_to_id": vocab["style_to_id"],
                "terrain_to_id": vocab["terrain_to_id"],
            }
            if conditional
            else None,
        }
        torch.save(payload, ckpt_dir / last_name)
        if epoch % int(cfg["train"]["save_every"]) == 0:
            prefix = f"{tag}_" if tag else ""
            torch.save(payload, ckpt_dir / f"{prefix}epoch_{epoch:03d}.pt")

    if conditional:
        print(f"条件训练结束。采样：python scripts/sample.py --conditional --style medieval --terrain flat")
        print(f"checkpoint: checkpoints/{last_name}")
    else:
        print("训练结束。采样：python scripts/sample.py")


if __name__ == "__main__":
    main()
