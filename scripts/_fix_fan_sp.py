from pathlib import Path
p = Path("src/app/look_harden.py")
text = p.read_text(encoding="utf-8")
old = '''        # full_style_v2 seed301 piers~221 cols dense at sp=3; sp=12 over-thinned to ~33.
        # Mid dens: wall_pier_spacing=7 -> probe ~108 (aim rustic~90 / euro~60-120).'''
new = '''        # full_style_v2 seed301 piers~221 at sp=3; sp=12 over-thinned to ~33.
        # Mid dens: wall_pier_spacing=5 -> probe ~81 (aim rustic~90 / euro~60-120).'''
if old not in text:
    raise SystemExit("comment missing")
text = text.replace(old, new, 1).replace('"wall_pier_spacing": 7,\n    },\n    "western"', '"wall_pier_spacing": 5,\n    },\n    "western"', 1)
p.write_text(text, encoding="utf-8")
print("fantasy pier spacing now 5")
