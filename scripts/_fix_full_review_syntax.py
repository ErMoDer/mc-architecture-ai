from pathlib import Path
p = Path("scripts/_run_full_style_review.py")
t = p.read_text(encoding="utf-8")
bad = '''                "- Review only; polish code unchanged.
- Metrics from existing look_harden actions (door/window/pier/eave).",
'''
good = '''                "- Review only; polish code unchanged.",
                "- Metrics from existing look_harden actions (door/window/pier/eave).",
'''
if bad not in t:
    raise SystemExit("bad block not found")
p.write_text(t.replace(bad, good, 1), encoding="utf-8")
import ast
ast.parse(p.read_text(encoding="utf-8"))
print("fixed")
