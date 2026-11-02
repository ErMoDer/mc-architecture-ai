from pathlib import Path
import re

p = Path("src/app/look_harden.py")
t = p.read_text(encoding="utf-8")

# european: widen window spacing, fewer bands, more corner inset
t2, n1 = re.subn(
    r'("european": \{.*?"window_spacing": )\d+(.*? "max_window_bands": )\d+(.*? "wall_pier_spacing": )\d+',
    r"\g<1>5\g<2>2\g<3>3",
    t,
    count=1,
    flags=re.S,
)
if n1 != 1:
    raise SystemExit(f"european replace failed {n1}")

# also set window_from_corner on european if present in block - add after window_width_max line
if '"european":' in t2:
    # inject from_corner if missing in european block
    m = re.search(r'"european": \{.*?\}', t2, re.S)
    block = m.group(0) if m else ""
    if "window_from_corner" not in block:
        t2 = t2.replace(
            '"european": {\n        "window_spacing": 5,',
            '"european": {\n        "window_spacing": 5,\n        "window_from_corner": 3,',
            1,
        )

# fantasy: pier spacing 3 -> 12
t3, n2 = re.subn(
    r'("fantasy": \{.*?"wall_pier_spacing": )\d+',
    r"\g<1>12",
    t2,
    count=1,
    flags=re.S,
)
if n2 != 1:
    raise SystemExit(f"fantasy replace failed {n2}")

p.write_text(t3, encoding="utf-8")
from src.app.look_harden import style_facade_rules
import importlib
import src.app.look_harden as lh
importlib.reload(lh)
print("european", {k: lh.style_facade_rules("european").get(k) for k in ("window_spacing","max_window_bands","window_from_corner","wall_pier_spacing")})
print("fantasy", {k: lh.style_facade_rules("fantasy").get(k) for k in ("window_spacing","max_window_bands","wall_pier_spacing")})
print("modern unchanged", lh.style_facade_rules("modern").get("window_spacing"), lh.style_facade_rules("industrial").get("window_spacing"), lh.style_facade_rules("rustic").get("wall_pier_spacing"))
