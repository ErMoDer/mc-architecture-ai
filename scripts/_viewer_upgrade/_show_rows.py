# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"E:\ai agent\mc-architecture-ai\scripts\viewer_app.py")
lines = p.read_text(encoding="utf-8").splitlines()
start = next(i for i,l in enumerate(lines) if "def _build_right_edit" in l)
end = next(i for i,l in enumerate(lines) if "def _on_mode_change" in l)
for i in range(start, end):
    if "row=" in lines[i] or "brush_row" in lines[i] or "clip_row" in lines[i] or "block_list" in lines[i] or "weight=\"bold\"" in lines[i] or "undo_btn" in lines[i] or "redo_btn" in lines[i] or "scheme_row" in lines[i] or "export_btn" in lines[i]:
        print(f"{i+1}|{lines[i]}")