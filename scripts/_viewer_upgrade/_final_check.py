# -*- coding: utf-8 -*-
from pathlib import Path
import py_compile

root = Path(r"E:\ai agent\mc-architecture-ai")
py_compile.compile(str(root / "scripts" / "viewer_app.py"), doraise=True)
py_compile.compile(str(root / "src" / "app" / "viewer_voxel_tools.py"), doraise=True)
print("py_compile OK")

# _bind_scheme undo refs
t = (root / "scripts" / "viewer_app.py").read_text(encoding="utf-8")
for i, ln in enumerate(t.splitlines()):
    if "_bind_scheme" in ln or ("undo" in ln.lower() and "stack" in ln.lower()) or "_undo" in ln:
        if "def " in ln or "_undo" in ln or "Undo" in ln:
            if i < 2500:
                pass
# show _bind_scheme body
idx = t.find("def _bind_scheme")
print(t[idx:idx+700])

# viewer.md snippet check
v = (root / "docs" / "viewer.md").read_text(encoding="utf-8")
print("Phase A in viewer.md:", "Phase A" in v)
print("plan exists:", (root / "outputs" / "plans" / "plan_8h_20261021.md").is_file())