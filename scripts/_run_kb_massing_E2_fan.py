# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.app.gen_strategy import generate_similar_scaffold, project_root
from src.app.look_harden import window_opening_count
from src.app.sample_runner import save_voxels_pair
from src.app.structure_constraints import (
    SCAFFOLD_THRESHOLDS,
    check_structure,
    compute_structure_metrics,
)
from src.data.export_litematic_util import export_voxels_to_companion
from src.utils import load_config, load_palette

ROOT = project_root()
OUT = ROOT / "outputs" / "design" / "kb_massing_E_20261021_004704"


def glass(vox) -> int:
    info = window_opening_count(vox)
    if isinstance(info, dict):
        for k, v in info.items():
            if "window" in str(k) and isinstance(v, (int, float, np.integer)):
                return int(v)
        return int(info.get("n") or info.get("count") or 0)
    return int(info)


def main() -> None:
    cfg = load_config(ROOT / "configs/default.yaml")
    palette = load_palette(ROOT / cfg["data"]["palette_path"])
    before = {"fantasy": 791, "european": 461}
    after: dict = {}
    for style, seed in [("european", 902), ("fantasy", 908)]:
        item = generate_similar_scaffold(
            style=style, terrain="flat", num=1, seed=seed, look_harden_enable=True
        )[0]
        vox = np.asarray(item["voxels"], dtype=np.int16)
        m = compute_structure_metrics(vox)
        g = glass(vox)
        after[style] = {
            "glass": g,
            "solids": int((vox > 0).sum()),
            "room_air": int(m.get("interior_room_air") or 0),
            "int_cover": float(m.get("floor_interior_cover") or 0),
            "roof": float(m.get("roof_score") or 0),
            "ok": bool(check_structure(vox, thresholds=dict(SCAFFOLD_THRESHOLDS)).ok),
            "part": (item.get("scaffold") or {}).get("partition_mode"),
        }
        print(
            style,
            "glass",
            before[style],
            "->",
            g,
            "solids",
            after[style]["solids"],
            "room",
            after[style]["room_air"],
            flush=True,
        )
        if style == "fantasy":
            save_voxels_pair(vox, palette, OUT / "npz" / "sample_sfantasy_tflat_000.npz")
            lit = export_voxels_to_companion(vox, palette, name="知新_幻想住宅_v26.3")
            after[style]["litematic"] = str(lit.get("path"))
            print("re-exported", lit.get("path"), flush=True)

    rows = json.loads((OUT / "rows.json").read_text(encoding="utf-8"))
    for r in rows:
        if r.get("style") == "fantasy":
            r["glass_before_E2"] = before["fantasy"]
            for k in ("glass", "solids", "room_air", "int_cover", "roof"):
                r[k] = after["fantasy"][k] if k != "int_cover" else round(after["fantasy"][k], 4)
            if "roof" in after["fantasy"]:
                r["roof"] = round(after["fantasy"]["roof"], 4)
            r["glass_E2"] = True
        if r.get("style") == "european":
            r["glass_control_E2"] = after["european"]["glass"]
    (OUT / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # Rebuild SUMMARY from rows
    ok_n = sum(1 for r in rows if r.get("ok"))
    lines = [
        "# Phase E — full 8-style (D partitions) + fantasy glass dens",
        "",
        f"- out: `{OUT.as_posix()}`",
        f"- structure_ok: **{ok_n}/8**",
        "- early-tech untouched",
        "",
        "| style | ok | solids | room_air | int_cover | roof | glass | part | policy | rooms | roof_mode | stairs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "| {style} | {ok} | {s} | {ra} | {ic} | {rf} | {g} | {p} | {pol} | {re} | {rm} | {st} |".format(
                style=r["style"],
                ok=r.get("ok"),
                s=r.get("solids"),
                ra=r.get("room_air"),
                ic=r.get("int_cover"),
                rf=r.get("roof"),
                g=r.get("glass"),
                p=r.get("part"),
                pol=r.get("policy"),
                re=r.get("rooms_est"),
                rm=r.get("roof_mode"),
                st=r.get("roof_stairs"),
            )
        )
    ratio_b = before["fantasy"] / before["european"]
    ratio_a = after["fantasy"]["glass"] / max(1, after["european"]["glass"])
    lines += [
        "",
        "## Schematics (知新_*)",
        "",
    ]
    for r in rows:
        if r.get("litematic") or r.get("cn"):
            lines.append(f"- `{r.get('cn')}`")
    lines += [
        "",
        "## E2 fantasy glass dens",
        "",
        f"| | european (control) | fantasy |",
        f"|--|--|--|",
        f"| glass before | {before['european']} | {before['fantasy']} |",
        f"| glass after | {after['european']['glass']} | **{after['fantasy']['glass']}** |",
        f"| ratio F/E | — | {ratio_b:.2f} → **{ratio_a:.2f}** |",
        "",
        "- Knobs: fantasy `window_spacing` 4→5, `window_from_corner` 2→3, `max_window_bands` 3→2.",
        "- Fantasy schematic re-exported; european control unchanged for export.",
        "",
    ]
    (OUT / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "e2_fan_glass.json").write_text(
        json.dumps({"before": before, "after": after}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("E2_DONE", after)


if __name__ == "__main__":
    main()