from pathlib import Path
p = Path("scripts/_fetch_style_houses_curated.py")
lines = p.read_text(encoding="utf-8").splitlines(True)
# find the bad block around query_list
for i, line in enumerate(lines):
    if "query_list" in line or 'style in ("rustic"' in line or "MCBlock: styles=" in line:
        print(f"{i+1}: {line!r}")
