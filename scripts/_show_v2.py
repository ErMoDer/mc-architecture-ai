from pathlib import Path
text = Path("scripts/_run_full_style_v2.py").read_text(encoding="utf-8")
print(text[:4000])
