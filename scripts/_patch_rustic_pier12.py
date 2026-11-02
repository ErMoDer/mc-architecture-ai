from pathlib import Path
import re

p = Path("src/app/look_harden.py")
t = p.read_text(encoding="utf-8")
t2, n = re.subn(
    r'("rustic": \{.*?"wall_pier_spacing": )\d+',
    r"\g<1>12",
    t,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("rustic pier replace failed: %s" % n)
# update comment if present
t2 = t2.replace("Was sp=4 (~300 pier cells", "Was sp=4 then 10 (~300 then ~100 pier cells")
p.write_text(t2, encoding="utf-8")

from src.app.look_harden import style_facade_rules
assert style_facade_rules("rustic").get("wall_pier_spacing") == 12
print("rustic pier sp", style_facade_rules("rustic").get("wall_pier_spacing"))

sec = """## Rustic pier spacing 12 (2026-10-19)

Follow-up to rustic_pier (4→10): rustic `wall_pier_spacing` **10 → 12**. Other styles unchanged.
Smoke: `scripts/_run_rustic_pier12_smoke.py` -> `outputs/design/rustic_pier12_*`.
"""
for path in [Path("docs/look_harden.md"), Path("docs/gen_strategy.md")]:
    t = path.read_text(encoding="utf-8")
    start = t.find("## Rustic pier spacing 12")
    head = t[:start] if start >= 0 else t.rstrip() + "\n\n"
    path.write_text(head.rstrip() + "\n\n" + sec, encoding="utf-8")
    print(path.name, "doc ok")
