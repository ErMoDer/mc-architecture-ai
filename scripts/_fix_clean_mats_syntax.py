from pathlib import Path
p = Path("scripts/_run_clean_mats.py")
lines = p.read_text(encoding="utf-8").splitlines()
out = []
i = 0
while i < len(lines):
    line = lines[i]
    if "_latest_clean_mats.txt" in line and "SUMMARY.md" in line:
        out.append('    (root / "outputs" / "design" / "_latest_clean_mats.txt").write_text(out.name, encoding="utf-8")')
        out.append('    (out / "SUMMARY.md").write_text("\\n".join(lines), encoding="utf-8")')
        i += 1
        continue
    if "_latest_eave_rooms.txt" in line:
        # do not overwrite eave pointer from clean_mats run
        i += 1
        continue
    out.append(line)
    i += 1
p.write_text("\n".join(out) + "\n", encoding="utf-8")
# verify compile
compile(p.read_text(encoding="utf-8"), str(p), "exec")
print("fixed ok")
