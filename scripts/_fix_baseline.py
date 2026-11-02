from pathlib import Path
p = Path("scripts/_run_clean_mats.py")
t = p.read_text(encoding="utf-8")
old = '''def _baseline_eave(root: Path) -> Path | None:
    design = root / "outputs" / "design"
    if rid.is_file():'''
new = '''def _baseline_eave(root: Path) -> Path | None:
    design = root / "outputs" / "design"
    rid = design / "_latest_eave_rooms.txt"
    if rid.is_file():'''
assert old in t
p.write_text(t.replace(old, new, 1), encoding="utf-8")
compile(p.read_text(encoding="utf-8"), str(p), "exec")
print("baseline fixed")
