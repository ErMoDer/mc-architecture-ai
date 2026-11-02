# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"E:\ai agent\mc-architecture-ai\scripts\viewer_app.py")
t = p.read_text(encoding="utf-8")
assert "_undo_voxels" not in t, "still has _undo_voxels"
assert "UndoStack" in t
assert "on_redo" in t
assert "on_copy_selection" in t
assert "apply_place_brush" in t
assert "盒填" in t
assert "笔刷" in t
# count defs
for name in ["_push_undo","on_undo","on_redo","on_copy_selection","on_cut_selection","on_paste_at_selection","_handle_voxel_click","_on_brush_change"]:
    c = t.count(f"def {name}")
    print(f"def {name}: {c}")
print("lines", len(t.splitlines()))
ast.parse(t)
print("OK")