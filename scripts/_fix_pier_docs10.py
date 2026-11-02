from pathlib import Path
for path in [Path("docs/look_harden.md"), Path("docs/gen_strategy.md")]:
    t = path.read_text(encoding="utf-8")
    t = t.replace("4 → 8", "4 → 10").replace("4->8", "4→10").replace("4→8", "4→10")
    path.write_text(t, encoding="utf-8")
print("docs")
