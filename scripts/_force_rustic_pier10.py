from pathlib import Path
from src.app.look_harden import style_facade_rules
import importlib
import src.app.look_harden as lh
p = Path("src/app/look_harden.py")
t = p.read_text(encoding="utf-8")
i = t.find('"rustic":')
print(repr(t[i:i+550]))
print("rule", style_facade_rules("rustic").get("wall_pier_spacing"))
# force replace any rustic wall_pier_spacing
import re
t2, n = re.subn(
    r'("rustic": \{.*?"wall_pier_spacing": )\d+',
    r"\g<1>10",
    t,
    count=1,
    flags=re.S,
)
print("subs", n)
p.write_text(t2, encoding="utf-8")
importlib.reload(lh)
print("after", lh.style_facade_rules("rustic").get("wall_pier_spacing"))
