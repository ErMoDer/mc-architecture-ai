# -*- coding: utf-8 -*-
from pathlib import Path
import json

# docs
for path, section in [
    (
        Path("docs/look_harden.md"),
        """## Door / wall rhythm polish (2026-10-19)

After win_eave:

1. **Doors** — primary facade entrance via real outward faces; 1–2×2 opening; door block + **threshold** (floor) + optional **frame/lintel** (accent). Hole-fill will not reseal beside existing doors.
2. **Wall piers** — vertical accent columns between window bays (`wall_pier_spacing`); corner pillars kept. Modern stays opener (`place_wall_piers=False`).
3. Style knobs live in `look_harden._STYLE_FACADE`.

Smoke: `scripts/_run_door_wall_smoke.py` -> `outputs/design/door_wall_*`.
""",
    ),
    (
        Path("docs/gen_strategy.md"),
        """## Door / wall rhythm polish (2026-10-19)

similar_scaffold -> look_harden facade:

- Ground-floor door with threshold/frame; wall pier rhythm between windows.
- Does not undo window bands, eaves/cornice, or flat-deck roof preserve.
- Smoke: `scripts/_run_door_wall_smoke.py`.
""",
    ),
]:
    t = path.read_text(encoding="utf-8")
    start = t.find("## Door / wall rhythm polish")
    head = t[:start] if start >= 0 else t.rstrip() + "\n\n"
    path.write_text(head.rstrip() + "\n\n" + section, encoding="utf-8")
    print(path, "ok")

p = Path("docs/mc-knowledge/builds/look_harden_rules.json")
d = json.loads(p.read_text(encoding="utf-8"))
d["updated"] = "2026-10-19"
d["defaults"]["place_door_frame"] = True
d["defaults"]["place_wall_piers"] = True
d["defaults"]["wall_pier_spacing"] = 3
d["notes"]["place_door_frame"] = "Accent posts + lintel around front door; threshold uses floor role."
d["notes"]["place_wall_piers"] = "Vertical accent piers between window bays; modern may disable."
p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("rules ok")
