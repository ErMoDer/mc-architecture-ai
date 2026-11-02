# -*- coding: utf-8 -*-
"""Smoke window rhythm + eaves/cornice polish on similar_scaffold."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.look_harden import window_opening_count
import src.app.look_harden as _lh
from src.app.structure_constraints import (
    SCAFFOLD_THRESHOLDS,
    check_structure,
    compute_structure_metrics,
)
from src.app.sample_runner import save_voxels_pair
from src.utils import load_config, load_palette


STYLES = [
    ("chinese", "flat", 1, 101),
    ("european", "flat", 1, 102),
    ("medieval", "flat", 1, 103),
    ("modern", "flat", 1, 104),
    ("rustic", "flat", 2, 201),
    ("fantasy", "flat", 2, 301),
]


def _acts_of_interest(actions: list) -> list[str]:
    keys = (
        "window_rhythm",
        "eave_strip",
        "cornice",
        "facade_stats",
        "windows:",
        "window_glass",
        "preserve_windows",
        "roof_pitched",
        "roof_flat",
        "knowledge:",
    )
    out = []
    for a in actions or []:
        s = str(a)
        if any(k in s for k in keys):
            out.append(s)
    return out


def main() -> None:
    root = project_root()
    cfg = load_config(root / "configs/default.yaml")
    palette = load_palette(root / cfg["data"]["palette_path"])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = root / "outputs" / "design" / ("win_eave_" + stamp)
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
            # Ensure glass heuristics see palette (window_opening_count uses module palette ref).
            _lh._PALETTE_REF = palette
            win = window_opening_count(vox)
            # also count glass by palette name (robust)
            glass_by_name = 0
            for bid in np.unique(vox[vox > 0]):
                name = str(palette.get(int(bid), ""))
                if "glass" in name.lower() or name.endswith("_pane"):
                    glass_by_name += int((vox == bid).sum())
            win["glass_cells"] = max(int(win.get("glass_cells", 0)), glass_by_name)
            lh = meta.get("look_harden") or {}
            acts = lh.get("actions") or []
            interesting = _acts_of_interest(acts)
            # parse facade_stats / rhythm tokens
            rhythm_cells = sill = eave_n = cornice_n = 0
            for a in acts:
                if a.startswith("window_rhythm:"):
                    # cells=%d cols=%d sp=%d bands=%d sill=%d
                    parts = {}
                    for tok in a.split(":", 1)[-1].replace("~", "").split():
                        if "=" in tok:
                            k, v = tok.split("=", 1)
                            try:
                                parts[k] = int(v)
                            except ValueError:
                                parts[k] = v
                    rhythm_cells = int(parts.get("cells", 0))
                    sill = int(parts.get("sill", 0))
                if a.startswith("eave_strip:"):
                    try:
                        eave_n = int(a.split(":", 1)[1].split("@", 1)[0])
                    except Exception:
                        pass
                if a.startswith("cornice_ring:"):
                    try:
                        cornice_n = int(a.split(":", 1)[1].split("@", 1)[0])
                    except Exception:
                        pass
                if a.startswith("facade_stats:") and "cornice=" in a:
                    try:
                        cornice_n = int(a.split("cornice=")[1].split()[0].split("roof")[0])
                    except Exception:
                        pass

            stem = "sample_s%s_t%s_%03d" % (style, terrain, i)
            saved = save_voxels_pair(vox, palette, out / "npz" / (stem + ".npz"))
            role_names = (meta.get("materials") or {}).get("role_names") or {}
            row = {
                "stem": stem,
                "style": style,
                "structure_ok": ok,
                "roof_score": float(m.get("roof_score") or 0),
                "top_footprint_cover": float(m.get("top_footprint_cover") or 0),
                "non_air": int(m.get("non_air") or 0),
                "glass_cells": int(win.get("glass_cells", 0)),
                "window_cells": int(win.get("window_cells", 0)),
                "window_components": int(win.get("window_components", 0)),
                "rhythm_cells": rhythm_cells,
                "sill_header": sill,
                "eave_cells": eave_n,
                "cornice_cells": cornice_n,
                "role_names": role_names,
                "roof_ne_wall": role_names.get("wall") != role_names.get("roof"),
                "look_actions": interesting,
                "reasons": st.get("reasons") if isinstance(st, dict) else [],
                "reference_id": meta.get("reference_id"),
            }
            for cand in (saved.get("preview_path"), meta.get("preview_path")):
                if cand and Path(cand).is_file():
                    dest = out / "previews" / (stem + ".png")
                    shutil.copy2(cand, dest)
                    row["preview"] = str(dest.relative_to(out)).replace("\\", "/")
                    shutil.copy2(cand, out / "attach_previews" / (stem + ".png"))
                    break
            mcf = meta.get("mcfunction_path") or meta.get("mcfunction")
            if mcf and Path(mcf).is_file():
                shutil.copy2(mcf, out / "mcfunction" / Path(mcf).name)
            rows.append(row)
            print(
                stem,
                "ok",
                ok,
                "roof",
                round(row["roof_score"], 3),
                "glass",
                row["glass_cells"],
                "rhythm",
                rhythm_cells,
                "sill",
                sill,
                "eave",
                eave_n,
                "cornice",
                cornice_n,
            )

    ok_n = sum(1 for r in rows if r["structure_ok"])
    report = {
        "out_dir": str(out),
        "n": len(rows),
        "structure_ok": "%d/%d" % (ok_n, len(rows)),
        "vs_look_polish": {
            "note": "look_polish residuals: irregular/over-glass walls, eave_overhang unused, no sill/header/cornice",
            "this_run": "regular bands+sill/header; eave overhang; cornice under deck; flat-deck cover kept",
        },
        "rows": rows,
    }
    (out / "REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# win_eave smoke",
        "",
        "- out: `%s`" % out.as_posix(),
        "- structure_ok: **%d/%d**" % (ok_n, len(rows)),
        "",
        "| style | ok | roof | glass | rhythm | sill | eave | cornice |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| %s | %s | %.3f | %d | %d | %d | %d | %d |"
            % (
                r["style"],
                r["structure_ok"],
                r["roof_score"],
                r["glass_cells"],
                r["rhythm_cells"],
                r["sill_header"],
                r["eave_cells"],
                r["cornice_cells"],
            )
        )
    lines += [
        "",
        "## vs look_polish",
        "- Before: window_rhythm could glass entire walls (600–800+ cells); `eave_overhang` logged but unused; no sill/header/cornice.",
        "- After: capped story bands + centered columns + sill/header; real overhang; cornice ring under deck (helps full-box rustic).",
        "- Flat euro/chinese/rustic decks: roof_score stay high (no gable wipe).",
        "",
    ]
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    notes = [
        "# NOTES",
        "",
        "- Code: `src/app/look_harden.py` (`place_window_rhythm`, `place_eave_strip`, `place_cornice_ring`, `_STYLE_FACADE`).",
        "- Docs: `docs/look_harden.md`, `docs/gen_strategy.md`, `docs/mc-knowledge/builds/look_harden_rules.json`.",
        "- No VAE training.",
        "",
    ]
    (out / "NOTES.md").write_text("\n".join(notes), encoding="utf-8")
    print("DONE", out, "ok", ok_n, "/", len(rows))


if __name__ == "__main__":
    main()
