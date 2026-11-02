# -*- coding: utf-8 -*-
"""UX P0 smoke: hotbar/crosshair code paths."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pathlib import Path as P
src = (ROOT / "scripts/viewer_app.py").read_text(encoding="utf-8")
for needle in ["HOTBAR_DEFAULTS", "_build_hotbar", "_select_hotbar", "_redraw_crosshair", "force_tool"]:
    assert needle in src, needle
import scripts.viewer_app as va
assert len(va.HOTBAR_DEFAULTS) == 9
app = va.ViewerApp(out_dir="outputs/design/night22e_full_20261022_071643/npz")
assert len(app._hotbar_buttons) == 9
app._select_hotbar(2)
assert app._hotbar_slot == 2 and app._parse_target_id() is not None
app._redraw_crosshair()
assert len(app._crosshair_artists) >= 2
try:
    app.destroy()
except Exception:
    pass
print("UX_P0_SMOKE_OK")
