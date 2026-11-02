from pathlib import Path
from src.app.look_harden import style_facade_rules
r = style_facade_rules("fantasy")
for k in ("window_spacing","max_window_bands","window_from_corner","wall_pier_spacing"):
    print(k, r.get(k))
print("--- SUMMARY ---")
print(Path("outputs/design/fantasy_glass_dens_20261020_090033/SUMMARY.md").read_text(encoding="utf-8"))
print("--- REPORT knobs ---")
import json
rep=json.loads(Path("outputs/design/fantasy_glass_dens_20261020_090033/REPORT.json").read_text(encoding="utf-8"))
print(json.dumps(rep["knobs"], indent=2))
print(json.dumps(rep["params"], indent=2))
