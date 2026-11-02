from pathlib import Path
p = Path("scripts/_run_full_style_v2.py")
t = p.read_text(encoding="utf-8")
# add scaffold fields to row dict if missing
if '"scaffold_roof_mode"' not in t:
    t = t.replace(
        '"reference_id": meta.get("reference_id"),\n            }',
        '"reference_id": meta.get("reference_id"),\n'
        '                "scaffold_floor_ys": (meta.get("scaffold") or {}).get("floor_ys"),\n'
        '                "scaffold_roof_mode": (meta.get("scaffold") or {}).get("roof_mode"),\n'
        '            }',
    )
# extend SUMMARY table
if "scaffold_roof" not in t:
    t = t.replace(
        "| style | ok | roof | door | w | frame | thr | piers | glass |",
        "| style | ok | roof | door | w | frame | thr | piers | glass | scaffold_roof | ref |",
    )
    t = t.replace(
        "|---|---|---|---|---|---|---|---|---|",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    )
    old = '''            "| %s | %s | %.3f | %s | %d | %d | %d | %d | %d |"
            % (
                r["style"],
                r["structure_ok"],
                r["roof_score"],
                r["door_block"],
                r["door_width"],
                r["door_frame"],
                r["door_threshold"],
                r["wall_pier_cells"],
                r["glass_cells"],
            )
'''
    new = '''            "| %s | %s | %.3f | %s | %d | %d | %d | %d | %d | %s | %s |"
            % (
                r["style"],
                r["structure_ok"],
                r["roof_score"],
                r["door_block"],
                r["door_width"],
                r["door_frame"],
                r["door_threshold"],
                r["wall_pier_cells"],
                r["glass_cells"],
                r.get("scaffold_roof_mode") or "",
                (str(r.get("reference_id") or "")[:24]),
            )
'''
    if old not in t:
        raise SystemExit("summary row format missing")
    t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
import ast
ast.parse(p.read_text(encoding="utf-8"))
print("enriched ok")
