# -*- coding: utf-8 -*-
"""Copy early-tech (and chicken-coop ref) litematics into SCHEMATICS_DIR with Chinese names.

Idempotent: overwrites only the mapped destination stems; never deletes other schematics.
Usage (from repo root):
  .venv\\Scripts\\python.exe scripts\\sync_early_tech_to_companion.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.export_litematic_util import resolve_schematics_dir  # noqa: E402

# source relative to ROOT -> destination stem (no .litematic)
COPY_MAP: list[tuple[str, str]] = [
    (
        "schematics/early_tech_26.3/Super_Smelter_V1_15furnace.litematic",
        "超级熔炉_15炉_V1_v26.3",
    ),
    (
        "schematics/early_tech_26.3/Simple_Super_Smelter_Mysticat.litematic",
        "超级熔炉_简易可扩展_v26.3",
    ),
    (
        "schematics/early_tech_26.3/Super_Smelter_Oregano_20k.litematic",
        "超级熔炉_Oregano_20k_v26.3",
    ),
    (
        "schematics/early_tech_26.3/Compact_Early_Iron_Farm_Zinko.litematic",
        "小型铁矿_Zinko_v26.3",
    ),
    (
        "schematics/early_tech_26.3/Easy_Iron_Farm.litematic",
        "简易铁矿_大型_v26.3",
    ),
    (
        "schematics/early_tech_26.3/Mega_Mob_XP_Farm_1.21.litematic",
        "大型刷怪经验塔_v26.3",
    ),
    (
        "data/raw/mcblock/鸡舍_二__6b7d9b9d.litematic",
        "鸡舍_二_红石参考_v26.3",
    ),
]


def main() -> int:
    out_dir = resolve_schematics_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    missing = 0
    for rel, stem in COPY_MAP:
        src = ROOT / rel
        dst = out_dir / f"{stem}.litematic"
        if not src.is_file():
            print(f"MISSING_SRC {src}")
            missing += 1
            continue
        shutil.copy2(src, dst)
        print(f"OK {stem}.litematic  ({src.stat().st_size} -> {dst.stat().st_size} bytes)")
        ok += 1
    print(f"Done: {ok} copied, {missing} missing -> {out_dir}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
