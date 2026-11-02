# -*- coding: utf-8 -*-
from pathlib import Path
t = Path(r"E:\ai agent\mc-architecture-ai\scripts\viewer_app.py").read_text(encoding="utf-8")
checks = ["笔刷", "小", "中", "大", "盒填", "复制", "剪切", "粘贴", "剪贴板：空", "撤销", "重做", "一键替换"]
for c in checks:
    print(f"{c!r}: {c in t}")
# list bak files
import glob
baks = glob.glob(r"E:\ai agent\mc-architecture-ai\**\*bak_phase_a*", recursive=True)
print("backups:", len(baks))
for b in baks:
    print(" ", b)