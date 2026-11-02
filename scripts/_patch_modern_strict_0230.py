from pathlib import Path
import re

p = Path("src/app/look_harden.py")
t = p.read_text(encoding="utf-8")
old = '''    "modern": {
        # Opener than euro (wider bays) but not curtain-wall: sp=5, ww=2, only 2 story bands.
        "window_spacing": 6,
        "window_width_max": 2,
        "window_height_max": 2,
        "window_from_corner": 3,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 2,
        "door_width": 2,
        "door_height": 2,
        "place_door_frame": False,
        "place_wall_piers": False,
        "corner_pillars": False,
    },'''
new = '''    "modern": {
        # Opener than euro (wider bays) but not curtain-wall: sp=6, ww=2, only 2 story bands.
        # 2:30 polish: strict openings (Phase F-style) — G modern window_cells 529 was mostly
        # weak-peri / near_rect holes; glass~224. Probe strict -> win~225.
        "window_spacing": 6,
        "window_width_max": 2,
        "window_height_max": 2,
        "window_from_corner": 3,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 2,
        "door_width": 2,
        "door_height": 2,
        "place_door_frame": False,
        "place_wall_piers": False,
        "corner_pillars": False,
        "strict_window_openings": True,
    },'''
if old not in t:
    raise SystemExit("modern block not found exactly")
t = t.replace(old, new, 1)
t, n = re.subn(
    r'style_l in \(\s*"fantasy",\s*"western",\s*\)',
    'style_l in (\n            "fantasy",\n            "western",\n            "modern",\n        )',
    t,
)
t, n2 = re.subn(
    r'\(str\(style or ""\)\.lower\(\) in \("fantasy", "western"\)\)',
    '(str(style or "").lower() in ("fantasy", "western", "modern"))',
    t,
)
p.write_text(t, encoding="utf-8")
print("ok", "tuple", n, "hole", n2)
from src.app.look_harden import style_facade_rules
r = style_facade_rules("modern")
print("modern strict", r.get("strict_window_openings"), "sp", r.get("window_spacing"))
