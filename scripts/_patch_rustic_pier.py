from pathlib import Path
p = Path("src/app/look_harden.py")
t = p.read_text(encoding="utf-8")
old = '''    "rustic": {
        "window_spacing": 4,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        "wall_pier_spacing": 4,
    },
'''
new = '''    "rustic": {
        "window_spacing": 4,
        "window_width_max": 1,
        "eave_overhang": 1,
        "place_cornice": True,
        "place_sill_header": True,
        "max_window_bands": 3,
        "door_width": 1,
        "door_height": 2,
        "place_door_frame": True,
        "place_wall_piers": True,
        # Was sp=4 (~300 pier cells / 柱林); widen so vertical accent stays but thinner rhythm.
        "wall_pier_spacing": 8,
    },
'''
if old not in t:
    raise SystemExit("rustic block missing")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
from src.app.look_harden import style_facade_rules
print("rustic pier sp", style_facade_rules("rustic").get("wall_pier_spacing"))
