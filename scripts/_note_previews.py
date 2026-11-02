from pathlib import Path
p = Path("outputs/design/win_eave_20261019_185103/SUMMARY.md")
t = p.read_text(encoding="utf-8")
if "attach_previews" not in t:
    t = t.rstrip() + "\n\nPreviews: `previews/<stem>.png` and `attach_previews/` (8 isometric).\n"
    p.write_text(t, encoding="utf-8")
print("summary updated")
