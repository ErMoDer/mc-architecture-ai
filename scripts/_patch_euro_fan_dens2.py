"""Retune european glass dens + fantasy pier dens only (LOCAL)."""
from pathlib import Path

p = Path("src/app/look_harden.py")
text = p.read_text(encoding="utf-8")

old_eu = '''    "european": {
        "window_spacing": 5,
        "window_from_corner": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 2,
        "door_width": 2,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 3,
    },'''

new_eu = '''    "european": {
        # full_style_v2 seed102 glass~448 (curtain-wall relapse vs older ~224).
        # Mid dens: sp=4 bands=3 from_corner=3 -> probe ~256 (aim 200-280).
        "window_spacing": 4,
        "window_from_corner": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 2,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 3,
    },'''

old_fan = '''    "fantasy": {
        "window_spacing": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 4,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 12,
    },'''

new_fan = '''    "fantasy": {
        # full_style_v2 seed301 piers~221 cols dense at sp=3; sp=12 over-thinned to ~33.
        # Mid dens: wall_pier_spacing=7 -> probe ~108 (aim rustic~90 / euro~60-120).
        "window_spacing": 3,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 4,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 7,
    },'''

if old_eu not in text:
    raise SystemExit("european block not found")
if old_fan not in text:
    raise SystemExit("fantasy block not found")
bak = p.with_suffix(".py.bak_euro_fan_dens2")
if not bak.exists():
    bak.write_text(text, encoding="utf-8")
    print("bak", bak)
text2 = text.replace(old_eu, new_eu, 1).replace(old_fan, new_fan, 1)
p.write_text(text2, encoding="utf-8")
print("patched eu sp4/bands3/c3; fantasy pier_sp=7")
