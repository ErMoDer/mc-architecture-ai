# -*- coding: utf-8 -*-
"""Batch-embed missing Block2Vec vectors for feature_index (plan 3)."""
from __future__ import annotations

import argparse
import json
import time
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_HOUSE = (
    "house", "home", "cabin", "cottage", "manor", "villa", "tower", "hall", "shop",
    "residence", "住宅", "小屋", "民居", "别墅", "宅",
)
_BAD = (
    "challenge", "mcbuildchallenge", "farm", "pyramid", "breeder", "stash",
    "trading_hall", "spawner", "redstone", "afk", "xp_",
)


def _bucket(it: dict) -> str:
    path = (it.get("source_path") or "").replace("\\", "/").lower()
    blob = ((it.get("id") or "") + " " + path).lower()
    style = (it.get("mapped_style") or "").lower()
    is_mc = "mcblock" in path
    if is_mc and style in ("european", "medieval", "modern", "chinese"):
        return "mcblock_style4"
    if is_mc:
        return "mcblock_other"
    if style in ("european", "medieval", "modern"):
        return "eu_med_mod_other"
    if style == "chinese":
        if any(b in blob for b in _BAD):
            return "chinese_spam"
        if any(h in blob for h in _HOUSE) or "住宅" in (it.get("id") or ""):
            return "chinese_house"
        return "chinese_other"
    return "rest"


def _is_cuda_err(ex: BaseException) -> bool:
    s = str(ex).lower()
    return "cuda" in s or "illegal memory" in s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-dir", default="data/feature_index")
    ap.add_argument(
        "--priority",
        default="mcblock_style4,mcblock_other,eu_med_mod_other,chinese_house",
    )
    ap.add_argument("--max-items", type=int, default=0)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--reset-every", type=int, default=25, help="reload model every N ok embeds")
    args = ap.parse_args()

    import sys

    sys.path.insert(0, str(ROOT))
    import torch
    from src.app import block2vec_embed as b2v_mod
    from src.app.block2vec_embed import attach_embedding_to_feature, get_model, reset_model
    from src.app.reference_features import load_feature

    index_dir = Path(args.index_dir)
    if not index_dir.is_absolute():
        index_dir = ROOT / index_dir
    man = json.loads((index_dir / "index.json").read_text(encoding="utf-8"))
    items = man.get("items") or []

    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "outputs" / "design" / ("block2vec_index_%s" % stamp)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    want = {b.strip() for b in args.priority.split(",") if b.strip()}
    do_all = "all" in want or args.priority.strip().lower() == "all"

    missing = []
    have = 0
    counts = Counter()
    for it in items:
        fid = it.get("id") or ""
        npy = index_dir / ("%s_block2vec.npy" % fid)
        b = _bucket(it)
        counts[b] += 1
        if npy.exists() and not args.force:
            have += 1
            continue
        if do_all or b in want:
            missing.append(it)

    order = [
        "mcblock_style4",
        "mcblock_other",
        "eu_med_mod_other",
        "chinese_house",
        "chinese_other",
        "chinese_spam",
        "rest",
    ]
    missing.sort(key=lambda it: order.index(_bucket(it)) if _bucket(it) in order else 99)
    if args.max_items and args.max_items > 0:
        missing = missing[: int(args.max_items)]

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    get_model(device=device)

    report = {
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "index_dir": str(index_dir.relative_to(ROOT)),
        "device": device,
        "index_total": len(items),
        "already_have_npy": have,
        "bucket_counts_all": dict(counts),
        "to_embed": len(missing),
        "priority": args.priority,
        "ok": 0,
        "fail": 0,
        "cpu_fallback": 0,
        "resets": 0,
        "failures": [],
        "by_bucket_ok": Counter(),
        "by_style_ok": Counter(),
    }

    t0 = time.time()
    ok_since_reset = 0

    def _try_embed(feat, src, dev):
        attach_embedding_to_feature(
            feat, src, index_dir=index_dir, device=dev, skip_neighbors=True
        )
        b2v = feat.get("block2vec") or {}
        if not b2v.get("ok"):
            raise RuntimeError(b2v.get("error") or "block2vec not ok")
        if dev.startswith("cuda"):
            torch.cuda.synchronize()
        return b2v

    for i, it in enumerate(missing, 1):
        fid = it["id"]
        b = _bucket(it)
        try:
            feat = load_feature(fid, index_dir=index_dir)
            src = feat.get("source_path") or it.get("source_path")
            if not src:
                raise RuntimeError("no source_path")

            used = device
            try:
                _try_embed(feat, src, device)
            except Exception as ex1:
                if device.startswith("cuda") and _is_cuda_err(ex1):
                    report["resets"] += 1
                    print("CUDA glitch on %s; reset+retry" % fid[:40], flush=True)
                    reset_model(device=device)
                    try:
                        _try_embed(feat, src, device)
                    except Exception as ex2:
                        print("CUDA retry fail; CPU fallback %s" % fid[:40], flush=True)
                        reset_model(device="cpu")
                        _try_embed(feat, src, "cpu")
                        used = "cpu"
                        report["cpu_fallback"] += 1
                        # restore cuda model for next items
                        reset_model(device=device)
                else:
                    raise

            (index_dir / ("%s.json" % fid)).write_text(
                json.dumps(feat, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            report["ok"] += 1
            report["by_bucket_ok"][b] += 1
            report["by_style_ok"][str(it.get("mapped_style") or "?")] += 1
            ok_since_reset += 1
            if args.reset_every > 0 and ok_since_reset >= args.reset_every and device.startswith("cuda"):
                reset_model(device=device)
                report["resets"] += 1
                ok_since_reset = 0
        except Exception as ex:
            report["fail"] += 1
            report["failures"].append({"id": fid, "bucket": b, "error": str(ex)[:300]})
            if _is_cuda_err(ex) and device.startswith("cuda"):
                try:
                    reset_model(device=device)
                    report["resets"] += 1
                except Exception:
                    pass
            if len(report["failures"]) <= 5:
                traceback.print_exc()
        if i % 10 == 0 or i == len(missing):
            elapsed = time.time() - t0
            rate = i / max(elapsed, 1e-6)
            eta = (len(missing) - i) / max(rate, 1e-6)
            print(
                "[%d/%d] ok=%d fail=%d cpu_fb=%d resets=%d rate=%.2f/s eta=%.0fs"
                % (
                    i,
                    len(missing),
                    report["ok"],
                    report["fail"],
                    report["cpu_fallback"],
                    report["resets"],
                    rate,
                    eta,
                ),
                flush=True,
            )

    have_after = sum(1 for it in items if (index_dir / ("%s_block2vec.npy" % it["id"])).exists())
    style_cov = Counter()
    style_tot = Counter()
    mc_have = mc_tot = 0
    for it in items:
        path = (it.get("source_path") or "").replace("\\", "/").lower()
        style = (it.get("mapped_style") or "").lower() or "?"
        npy = index_dir / ("%s_block2vec.npy" % it["id"])
        style_tot[style] += 1
        if npy.exists():
            style_cov[style] += 1
        if "mcblock" in path:
            mc_tot += 1
            if npy.exists():
                mc_have += 1

    report["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    report["elapsed_sec"] = round(time.time() - t0, 1)
    report["have_npy_after"] = have_after
    report["mcblock_coverage"] = "%d/%d" % (mc_have, mc_tot)
    report["style_coverage"] = {k: "%d/%d" % (style_cov[k], style_tot[k]) for k in sorted(style_tot)}
    report["by_bucket_ok"] = dict(report["by_bucket_ok"])
    report["by_style_ok"] = dict(report["by_style_ok"])

    (out_dir / "embed_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("OUT", out_dir)
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "fail": report["fail"],
                "cpu_fallback": report["cpu_fallback"],
                "resets": report["resets"],
                "have_npy_after": have_after,
                "mcblock_coverage": report["mcblock_coverage"],
                "elapsed_sec": report["elapsed_sec"],
                "style_coverage_focus": {
                    k: report["style_coverage"].get(k)
                    for k in ("european", "medieval", "modern", "chinese")
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()