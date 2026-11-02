# -*- coding: utf-8 -*-
from pathlib import Path
p = Path("scripts/viewer_app.py")
t = p.read_text(encoding="utf-8")
needle = '            self.mode_hint.configure(text="当前：编辑 · 点选/破坏/放置/涂改/移动（接近 MCBlock）")\n            self.edit_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))\n            self.right.grid(row=1, column=2, sticky="nsew", padx=(4, 12), pady=(4, 12))\n            self.grid_columnconfigure(2, weight=0)'
repl = needle + """
            if self.current_voxels is not None:
                self.after(50, lambda: self.render_voxels(self.current_voxels, orbit_lod=False))"""
if "接近 MCBlock" in t and "after(50, lambda: self.render_voxels" not in t:
    if needle not in t:
        raise SystemExit("needle missing for edit switch")
    t = t.replace(needle, repl, 1)
    p.write_text(t, encoding="utf-8")
    print("switch-mode re-render added")
else:
    print("skip or already")
