from pathlib import Path
PATH = Path("src/app/look_harden.py")
text = PATH.read_text(encoding="utf-8")
old_m = '''    "modern": {
        # Keep opener than euro/chinese, but break curtain walls: wider gaps, 1-cell bays, 2 bands.
        "window_spacing": 6,
        "window_width_max": 1,
        "window_height_max": 2,
        "window_from_corner": 3,
'''
new_m = '''    "modern": {
        # Opener than euro (wider bays) but not curtain-wall: sp=5, ww=2, only 2 story bands.
        "window_spacing": 5,
        "window_width_max": 2,
        "window_height_max": 2,
        "window_from_corner": 3,
'''
old_i = '''    "industrial": {
        # Was falling through to defaults (sp=3, bands=4, ww=2) -> ~450 glass; use strip windows + solid panels.
        "window_spacing": 5,
        "window_width_max": 1,
        "window_height_max": 2,
        "window_from_corner": 2,
'''
new_i = '''    "industrial": {
        # Was defaults (sp=3, bands=4, ww=2) -> ~450 glass; strip windows + solid panels between.
        "window_spacing": 4,
        "window_width_max": 1,
        "window_height_max": 2,
        "window_from_corner": 2,
'''
if old_m not in text or old_i not in text:
    raise SystemExit("anchors missing")
PATH.write_text(text.replace(old_m, new_m, 1).replace(old_i, new_i, 1), encoding="utf-8")
print("tuned")
