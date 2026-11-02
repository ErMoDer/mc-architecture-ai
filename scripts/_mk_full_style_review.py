from pathlib import Path
import re
p = Path("scripts/_run_full_style_review.py")
t = p.read_text(encoding="utf-8")
t = t.replace("door_wall_", "full_style_review_")
t = t.replace("# door_wall smoke", "# full_style_review batch")
t = t.replace(
    '"""Smoke door openings + wall pier rhythm on similar_scaffold."""',
    '"""Full multi-style similar_scaffold review batch (current polish, no new harden)."""',
)
styles = """STYLES = [
    (\"chinese\", \"flat\", 1, 101),
    (\"european\", \"flat\", 1, 102),
    (\"medieval\", \"flat\", 1, 103),
    (\"modern\", \"flat\", 1, 104),
    (\"rustic\", \"flat\", 2, 201),
    (\"fantasy\", \"flat\", 2, 301),
    (\"industrial\", \"flat\", 1, 401),
]"""
# use real quotes
styles = """STYLES = [
    ("chinese", "flat", 1, 101),
    ("european", "flat", 1, 102),
    ("medieval", "flat", 1, 103),
    ("modern", "flat", 1, 104),
    ("rustic", "flat", 2, 201),
    ("fantasy", "flat", 2, 301),
    ("industrial", "flat", 1, 401),
]"""
m = re.search(r"STYLES = \[.*?\]", t, re.S)
if not m:
    raise SystemExit("STYLES not found")
t = t[: m.start()] + styles + t[m.end() :]
t = t.replace(
    "- Added door frame+threshold; wall piers between window bays; modern stays opener (no piers/frame).",
    "- Review batch of current polish (look_polish + win_eave + door_wall). No new harden this run.",
)
t = t.replace(
    "- Code: `carve_front_door` (frame/threshold + facade faces), `place_wall_piers`, `_STYLE_FACADE` door/pier knobs.",
    "- Review only; polish code unchanged.\n- Metrics from existing look_harden actions (door/window/pier/eave).",
)
# report key
t = t.replace('"vs_win_eave"', '"vs_prior_polish"')
p.write_text(t, encoding="utf-8")
print("ok", "industrial" in t, t.count("full_style_review_"))
