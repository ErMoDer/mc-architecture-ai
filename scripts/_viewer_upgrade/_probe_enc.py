from pathlib import Path
p = Path(r"E:\ai agent\mc-architecture-ai\scripts\viewer_app.py")
lines = p.read_text(encoding="utf-8").splitlines()
for i, ln in enumerate(lines):
    if "nudge_row.grid" in ln:
        print("nudge", i+1)
    if "block_list = ctk" in ln:
        print("block_list", i+1)
    if "def on_undo" in ln:
        print("on_undo", i+1)
    if "_undo_voxels" in ln:
        print("undo_ref", i+1, ln.strip()[:70])
    if "def _handle_voxel_click" in ln:
        print("handle_click", i+1)
print("total", len(lines))
# show codepoints around line 688
s = lines[687]
print("line688:", s)
print("codepoints:", [hex(ord(c)) for c in s if ord(c)>127][:20])