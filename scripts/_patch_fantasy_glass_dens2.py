"""Soft-retune fantasy glass: sp=4 bands=3 from_corner=2 (keep pier=5)."""
from pathlib import Path

p = Path("src/app/look_harden.py")
text = p.read_text(encoding="utf-8")

old_fan = '''    "fantasy": {
        # full_style_v2/v3 seed301 glass~374 / seed+1 ~238 (curtain-y).
        # Mid dens (same recipe as euro settle): sp=4 bands=3 from_corner=3.
        # Aim denser sample ~200-280; keep wall_pier_spacing=5 (~81/56).
        "window_spacing": 4,
        "window_from_corner": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 5,
    },'''

new_fan = '''    "fantasy": {
        # full_style_v2/v3 seed301 glass~374 / seed+1 ~238 (curtain-y).
        # First mid (sp4/bands3/c3) -> denser~212 (ok) but sparse~126 + piers 81->133.
        # Soft: same sp/bands, from_corner=2 (keep a bit glazier than euro c3).
        "window_spacing": 4,
        "window_from_corner": 2,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 5,
    },'''

if old_fan not in text:
    raise SystemExit("fantasy block not found")
bak = p.with_suffix(".py.bak_fantasy_glass_dens2")
if not bak.exists():
    bak.write_text(text, encoding="utf-8")
    print("bak", bak)
p.write_text(text.replace(old_fan, new_fan, 1), encoding="utf-8")
print("patched fantasy: sp=4 bands=3 from_corner=2 pier_sp=5")
