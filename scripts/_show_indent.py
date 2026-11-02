from pathlib import Path
p = Path("scripts/_fetch_style_houses_curated.py")
lines = p.read_text(encoding="utf-8").splitlines(True)
for i in range(175, 200):
    print(f"{i+1}: {lines[i]!r}")
