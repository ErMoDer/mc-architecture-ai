# -*- coding: utf-8 -*-
from pathlib import Path
import re
p = Path(r"E:\ai agent\mc-architecture-ai\scripts\viewer_app.py")
t = p.read_text(encoding="utf-8")
# Fix messy Ctrl+Y branch in _on_canvas_key
old = '''        if ctrl and key.lower() in ("y", "Z"):  # Ctrl+Y redo; some layouts use Shift
            self.on_redo()
            return
        if ctrl and key.lower() == "y":
            self.on_redo()
            return'''
new = '''        if ctrl and key.lower() == "y":
            self.on_redo()
            return'''
if old in t:
    t = t.replace(old, new, 1)
    print("fixed ctrl-y")
else:
    print("ctrl-y block not exact; dumping nearby")
    i = t.find('key.lower() == "z"')
    print(repr(t[i:i+350]))

# Show grid rows in _build_right_edit
start = t.find("def _build_right_edit")
end = t.find("def _on_mode_change")
mid = t[start:end]
rows = re.findall(r"\.grid\(row=(\d+)", mid)
print("grid rows in edit panel:", rows)

p.write_text(t, encoding="utf-8")
import ast
ast.parse(t)
print("AST still OK")