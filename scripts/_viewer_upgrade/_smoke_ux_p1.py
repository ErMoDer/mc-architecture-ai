# -*- coding: utf-8 -*-
"""UX P1 smoke: textures + hotbar icons + zh feedback."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.app.mc_textures import ensure_textures, average_rgba, load_pil_icon, texture_status_line
from src.app.mc_colors import rgba_for_name
from src.app.block_zh_cn import zh_name
info = ensure_textures()
print("TEXTURE_INFO", info.get("ok"), info.get("note"), "cache=", info.get("cached_count"))
assert "note" in info
avg = average_rgba("minecraft:oak_planks")
rgba = rgba_for_name("minecraft:oak_planks")
assert rgba is not None and len(rgba) == 4
print("oak_planks", tuple(round(x, 3) for x in rgba), "tex_avg", avg is not None)
icon = load_pil_icon("minecraft:stone", size=16)
print("stone_icon", icon is not None)
print("zh", zh_name("minecraft:stone"))
src = (ROOT / "scripts/viewer_app.py").read_text(encoding="utf-8")
for needle in ["UX_P1_TEXTURES", "load_pil_icon", "_flash_toast", "block_zh_name", "ensure_textures"]:
    assert needle in src, needle
import scripts.viewer_app as va
app = va.ViewerApp(out_dir="outputs/design/night22e_full_20261022_071643/npz")
assert len(app._hotbar_buttons) == 9
app._select_hotbar(0)
app._refresh_hotbar_ui()
app._redraw_crosshair()
assert len(app._crosshair_artists) >= 2
app._flash_toast("smoke")
try:
    app.destroy()
except Exception:
    pass
print("UX_P1_SMOKE_OK", texture_status_line())
