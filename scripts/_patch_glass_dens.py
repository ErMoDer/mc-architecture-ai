from pathlib import Path

PATH = Path("src/app/look_harden.py")
text = PATH.read_text(encoding="utf-8")

OLD_MOD = '''    "modern": {
        "window_spacing": 4,
        "window_width_max": 2,
        "window_height_max": 2,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 2,
        "door_width": 2,
        "door_height": 2,
        "place_door_frame": False,
        "place_wall_piers": False,
        "corner_pillars": False,
    },
'''

NEW_MOD = '''    "modern": {
        # Keep opener than euro/chinese, but break curtain walls: wider gaps, 1-cell bays, 2 bands.
        "window_spacing": 6,
        "window_width_max": 1,
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
    },
'''

# Insert industrial after modern block (before fantasy)
OLD_FAN = '''    "fantasy": {
'''

NEW_IND_AND_FAN = '''    "industrial": {
        # Was falling through to defaults (sp=3, bands=4, ww=2) -> ~450 glass; use strip windows + solid panels.
        "window_spacing": 5,
        "window_width_max": 1,
        "window_height_max": 2,
        "window_from_corner": 2,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 2,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 5,
        "corner_pillars": True,
    },
    "fantasy": {
'''

if OLD_MOD not in text:
    raise SystemExit("modern block missing")
if OLD_FAN not in text:
    raise SystemExit("fantasy anchor missing")
if '"industrial": {' in text.split("_STYLE_FACADE")[1].split("def style_facade")[0]:
    raise SystemExit("industrial already in _STYLE_FACADE")

text = text.replace(OLD_MOD, NEW_MOD, 1)
text = text.replace(OLD_FAN, NEW_IND_AND_FAN, 1)
PATH.write_text(text, encoding="utf-8")

from src.app.look_harden import style_facade_rules
for s in ("modern", "industrial"):
    r = style_facade_rules(s)
    print(s, r.get("window_spacing"), r.get("window_width_max"), r.get("max_window_bands"), r.get("window_from_corner"))
print("ok")
