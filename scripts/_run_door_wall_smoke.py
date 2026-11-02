# -*- coding: utf-8 -*-
"""Smoke door openings + wall pier rhythm on similar_scaffold."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

import src.app.look_harden as _lh
from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.look_harden import window_opening_count
from src.app.sample_runner import save_voxels_pair
from src.app.structure_constraints import (
    SCAFFOLD_THRESHOLDS,
    check_structure,
    compute_structure_metrics,
)
from src.utils import load_config, load_palette


STYLES = [
    ("chinese", "flat", 1, 101),
    ("european", "flat", 1, 102),
    ("medieval", "flat", 1, 103),
    ("modern", "flat", 1, 104),
    ("rustic", "flat", 2, 201),
    ("fantasy", "flat", 2, 301),
]


def _interesting(actions: list) -> list[str]:
    keys = (
        "front_door",
        "wall_piers",
        "corner_pillars",
        "facade_band",
        "facade_stats",
        "window_rhythm",
        "eave_strip",
        "cornice",
        "preserve_windows",
    )
    return [str(a) for a in (actions or []) if any(k in str(a) for k in keys)]


def _parse_token(a: str, key: str) -> int:
    if key + "=" not in a:
        return 0
    try:
        return int(a.split(key + "=")[1].split()[0].split("door")[0].rstrip(","))
    except Exception:
        return 0


def _render_iso(vox, palette, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from src.app.mc_render import render_mc_voxels

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="3d")
    render_mc_voxels(ax, fig, vox, palette, performance=True)
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    root = project_root()
    cfg = load_config(root / "configs/default.yaml")
    palette = load_palette(root / cfg["data"]["palette_path"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = root / "outputs" / "design" / ("door_wall_" + stamp)
    for sub in ("previews", "attach_previews", "npz", "mcfunction", "raw_by_case"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    rows = []
    for style, terrain, num, seed0 in STYLES:
        metas = generate_similar_scaffold(
            style=style,
            terrain=terrain,
            num=num,
            out_dir=out / "raw_by_case" / style,
            seed=seed0,
            top_k_refs=3,
            vae_fill=False,
            look_harden_enable=True,
        )
        for i, meta in enumerate(metas):
            vox = meta["voxels"]
            st = meta.get("structure") or {}
            m = (st.get("metrics") if isinstance(st, dict) else None) or compute_structure_metrics(
                vox
            )
            ok = (
                bool(st.get("ok"))
                if isinstance(st, dict)
                else check_structure(vox, SCAFFOLD_THRESHOLDS).ok
            )
            _lh._PALETTE_REF = palette
            win = window_opening_count(vox)
            glass_by_name = 0
            for bid in np.unique(vox[vox > 0]):
                name = str(palette.get(int(bid), ""))
                if "glass" in name.lower() or name.endswith("_pane"):
                    glass_by_name += int((vox == bid).sum())
            win["glass_cells"] = max(int(win.get("glass_cells", 0)), glass_by_name)

            lh = meta.get("look_harden") or {}
            acts = lh.get("actions") or []
            door_frame = door_thr = pier_n = door_w = 0
            door_yes = False
            for a in acts:
                s = str(a)
                if s.startswith("front_door:"):
                    door_frame = _parse_token(s, "frame")
                    door_thr = _parse_token(s, "thr")
                    door_yes = "door=yes" in s
                    if "w=" in s:
                        try:
                            door_w = int(s.split("w=")[1].split()[0])
                        except Exception:
                            pass
                if s.startswith("wall_piers:"):
                    try:
                        pier_n = int(s.split(":")[1].split()[0])
                    except Exception:
                        pass

            role_names = (meta.get("materials") or {}).get("role_names") or {}
            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            saved = save_voxels_pair(vox, palette, out / "npz" / (stem + ".npz"))
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "roof_score": float(m.get("roof_score") or 0),
                "top_footprint_cover": float(m.get("top_footprint_cover") or 0),
                "non_air": int(m.get("non_air") or 0),
                "glass_cells": int(win.get("glass_cells", 0)),
                "door_block": door_yes,
                "door_width": door_w,
                "door_frame": door_frame,
                "door_threshold": door_thr,
                "wall_pier_cells": pier_n,
                "role_names": role_names,
                "roof_ne_wall": role_names.get("wall") != role_names.get("roof"),
                "look_actions": _interesting(acts),
                "reasons": st.get("reasons") if isinstance(st, dict) else [],
                "reference_id": meta.get("reference_id"),
            }
            png = out / "previews" / (stem + ".png")
            try:
                _render_iso(vox, palette, png)
                shutil.copy2(png, out / "attach_previews" / (stem + ".png"))
                row["preview"] = "previews/" + stem + ".png"
            except Exception as e:
                row["preview_error"] = str(e)
            mcf = meta.get("mcfunction_path") or meta.get("mcfunction")
            if mcf and Path(mcf).is_file():
                shutil.copy2(mcf, out / "mcfunction" / Path(mcf).name)
            # also copy save_voxels mcfunction if present
            mcf2 = saved.get("mcfunction_path")
            if mcf2 and Path(mcf2).is_file():
                dest = out / "mcfunction" / Path(mcf2).name
                if not dest.exists():
                    shutil.copy2(mcf2, dest)
            rows.append(row)
            print(
                stem,
                "ok",
                ok,
                "roof",
                round(row["roof_score"], 3),
                "door",
                door_yes,
                "w",
                door_w,
                "frame",
                door_frame,
                "thr",
                door_thr,
                "piers",
                pier_n,
            )

    ok_n = sum(1 for r in rows if r["structure_ok"])
    euro_cn_ru = [r for r in rows if r["style"] in ("european", "chinese", "rustic")]
    flat_ok = all(r["roof_score"] >= 0.95 for r in euro_cn_ru)
    report = {
        "out_dir": str(out),
        "n": len(rows),
        "structure_ok": "%d/%d" % (ok_n, len(rows)),
        "euro_chinese_rustic_roof_near_1": flat_ok,
        "vs_win_eave": {
            "kept": "window bands, sill/header, eave_overhang, cornice, flat-deck, roof!=wall, role materials",
            "added": "door frame/threshold; wall pier rhythm; hole-fill skips door neighbors",
        },
        "rows": rows,
    }
    (out / "REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# door_wall smoke",
        "",
        "- out: `%s`" % out.as_posix(),
        "- structure_ok: **%d/%d**" % (ok_n, len(rows)),
        "- euro/chinese/rustic roof~1: **%s**" % flat_ok,
        "",
        "| style | ok | roof | door | w | frame | thr | piers | glass |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| %s | %s | %.3f | %s | %d | %d | %d | %d | %d |"
            % (
                r["style"],
                r["structure_ok"],
                r["roof_score"],
                r["door_block"],
                r["door_width"],
                r["door_frame"],
                r["door_threshold"],
                r["wall_pier_cells"],
                r["glass_cells"],
            )
        )
    lines += [
        "",
        "## vs win_eave",
        "- Kept window rhythm / sill / eaves / cornice / flat decks.",
        "- Added door frame+threshold; wall piers between window bays; modern stays opener (no piers/frame).",
        "",
        "Previews: `previews/<stem>.png` and `attach_previews/`.",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "NOTES.md").write_text(
        "\n".join(
            [
                "# NOTES",
                "",
                "- Code: `carve_front_door` (frame/threshold + facade faces), `place_wall_piers`, `_STYLE_FACADE` door/pier knobs.",
                "- Docs: `docs/look_harden.md`, `docs/gen_strategy.md`.",
                "- No VAE training.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("DONE", out, "ok", ok_n, "/", len(rows), "flat_roof", flat_ok)


if __name__ == "__main__":
    main()
