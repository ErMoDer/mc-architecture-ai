from pathlib import Path
p = Path("src/app/look_harden.py")
t = p.read_text(encoding="utf-8")
old = """    \"modern\": {
        \"window_spacing\": 3,
        \"window_width_max\": 2,
        \"window_height_max\": 2,
        \"eave_overhang\": 0,
        \"place_cornice\": False,
        \"place_sill_header\": False,
        \"max_window_bands\": 3,
    },"""
# file uses normal quotes
old = '''    "modern": {
        "window_spacing": 3,
        "window_width_max": 2,
        "window_height_max": 2,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 3,
    },'''
new = '''    "modern": {
        "window_spacing": 4,
        "window_width_max": 2,
        "window_height_max": 2,
        "eave_overhang": 0,
        "place_cornice": False,
        "place_sill_header": False,
        "max_window_bands": 2,
    },'''
if old not in t:
    raise SystemExit("modern block missing")
t = t.replace(old, new, 1)
old_doc = "- facade rhythm: front door, pitched/flat roof, eave strip, banding, corner pillars"
new_doc = "- facade rhythm: front door, pitched/flat roof, eave overhang, cornice, window sill/header, banding, corner pillars"
t = t.replace(old_doc, new_doc, 1)
p.write_text(t, encoding="utf-8")
print("ok")
