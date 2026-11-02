from pathlib import Path
p = Path("scripts/_run_rustic_pier12_smoke.py")
t = p.read_text(encoding="utf-8")
t = t.replace("rustic_pier_", "rustic_pier12_")
t = t.replace("# rustic_pier smoke", "# rustic_pier12 smoke")
t = t.replace('"""Smoke rustic wall pier spacing widen."""', '"""Smoke rustic wall_pier_spacing 10→12."""')
t = t.replace(
    'BEFORE_PIER = {"rustic": [322, 306], "european": 124, "modern": 0}',
    'BEFORE_PIER = {"rustic": [106, 81], "european": 124, "modern": 0}  # after sp=10 rustic_pier_20261019_191817',
)
t = t.replace('{"rustic.wall_pier_spacing": "4 -> 10"}', '{"rustic.wall_pier_spacing": "10 -> 12"}')
t = t.replace("before_ref\": \"full_style_review_20261019_190438 / door_wall_20261019_190033\"",
              "before_ref\": \"rustic_pier_20261019_191817 (sp=10 → pier 106/81)\"")
t = t.replace("pier before", "pier@sp10")
t = t.replace("- rustic `wall_pier_spacing` **4 → 10**", "- rustic `wall_pier_spacing` **10 → 12**")
t = t.replace("Only rustic pier spacing widened.", "Only rustic pier spacing 10→12.")
p.write_text(t, encoding="utf-8")
import ast
ast.parse(p.read_text(encoding="utf-8").lstrip("\ufeff"))
print("script ok")
