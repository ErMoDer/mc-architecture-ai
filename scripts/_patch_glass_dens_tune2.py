from pathlib import Path
p=Path("src/app/look_harden.py")
t=p.read_text(encoding="utf-8")
t=t.replace('"window_spacing": 5,\n        "window_width_max": 2,\n        "window_height_max": 2,\n        "window_from_corner": 3,\n        "eave_overhang": 0,\n        "place_cornice": False,\n        "place_sill_header": False,\n        "max_window_bands": 2,\n        "door_width": 2,',
            '"window_spacing": 6,\n        "window_width_max": 2,\n        "window_height_max": 2,\n        "window_from_corner": 3,\n        "eave_overhang": 0,\n        "place_cornice": False,\n        "place_sill_header": False,\n        "max_window_bands": 2,\n        "door_width": 2,', 1)
# industrial bump slightly toward 180-280: ww=1 sp=4 bands=2 gave 124; try bands=3 or ww=1 sp=4 max_bands=3
t=t.replace('"window_spacing": 4,\n        "window_width_max": 1,\n        "window_height_max": 2,\n        "window_from_corner": 2,\n        "eave_overhang": 0,\n        "place_cornice": False,\n        "place_sill_header": False,\n        "max_window_bands": 2,\n        "door_width": 1,',
            '"window_spacing": 4,\n        "window_width_max": 1,\n        "window_height_max": 2,\n        "window_from_corner": 2,\n        "eave_overhang": 0,\n        "place_cornice": False,\n        "place_sill_header": False,\n        "max_window_bands": 3,\n        "door_width": 1,', 1)
p.write_text(t, encoding="utf-8")
print("ok")
