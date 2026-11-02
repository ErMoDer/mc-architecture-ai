from pathlib import Path
import ast
p = Path("src/app/gen_strategy.py")
t = p.read_text(encoding="utf-8")
old = "    stats[\"roof_deck_y\"] = int(roof_deck_y)\n\n        # Story slabs: regularize ref peaks (avoid floor every 3 cells) and never paint roof as floor\n    _max_stories = 3 if style_l in (\"medieval\", \"fantasy\") else 4\n"
new = "    stats[\"roof_deck_y\"] = int(roof_deck_y)\n\n    style_l = (style or \"\").strip().lower()\n    # Story slabs: regularize ref peaks (avoid floor every 3 cells) and never paint roof as floor\n    _max_stories = 3 if style_l in (\"medieval\", \"fantasy\") else 4\n"
if old not in t:
    raise SystemExit("missing")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
ast.parse(p.read_text(encoding="utf-8"))
print("fixed")
