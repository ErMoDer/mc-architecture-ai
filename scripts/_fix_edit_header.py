# -*- coding: utf-8 -*-
from pathlib import Path
p = Path("scripts/viewer_app.py")
t = p.read_text(encoding="utf-8")
start = t.find('        ctk.CTkLabel(right, text="方块替换"')
if start < 0:
    raise SystemExit("start not found")
mid = t.find("        # —— MCBlock-like voxel tools ——", start)
if mid < 0:
    raise SystemExit("mid not found")
# keep from mid; replace header before mid
header = '''        ctk.CTkLabel(right, text="编辑 / 建模", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=14, pady=(14, 2)
        )

'''
# find end of old subtitle grid (before mid)
t = t[:start] + header + t[mid:]
p.write_text(t, encoding="utf-8")
print("ok")
