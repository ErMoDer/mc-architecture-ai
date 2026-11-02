# -*- coding: utf-8 -*-
"""Fix SUMMARY/REPORT params to from_corner=2; append docs/look_harden.md."""
from pathlib import Path
import json

out = Path("outputs/design/fantasy_glass_dens_20261020_090033")
rep = json.loads((out / "REPORT.json").read_text(encoding="utf-8"))
rep["params"]["fantasy"] = (
    "window_spacing=4 max_window_bands=3 window_from_corner=2; "
    "wall_pier_spacing=5 kept (first mid c3: denser~212 sparse~126 piers81->133; soft c2 settled)"
)
rep["settle"] = {
    "first_mid": "sp4/bands3/c3 -> glass 212/126 piers 133/55",
    "settled": "sp4/bands3/c2 -> glass 230/144 piers 81/56",
}
(out / "REPORT.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

lines = [
    "# fantasy_glass_dens batch",
    "",
    "- out: `%s`" % out.as_posix(),
    "- vs: `full_style_v3_20261020_085033`",
    "- structure_ok: **4/4**",
    "",
    "## Params",
    "- fantasy: `window_spacing=4`, `max_window_bands=3`, `window_from_corner=2`",
    "- fantasy piers: `wall_pier_spacing=5` (unchanged)",
    "- controls unchanged: european 4/3/3, rustic pier=12",
    "- settle: first mid c3 -> glass 212/126 + piers 133/55; soft **c2** -> 230/144 + 81/56",
    "",
    "| style | ok | roof | glass before->after | piers before->after |",
    "|---|---|---|---|---|",
]
for r in rep["rows"]:
    lines.append(
        "| %s | %s | %.3f | %s -> %d | %s -> %d |"
        % (
            r["style"],
            r["structure_ok"],
            r["roof_score"],
            r.get("glass_before_v3") if r.get("glass_before_v3") is not None else "?",
            r["glass_cells"],
            r.get("piers_before_v3") if r.get("piers_before_v3") is not None else "?",
            r["wall_pier_cells"],
        )
    )
lines += [
    "",
    "## Aim / residuals",
    "- fantasy denser glass **230** in aim 200-280 (was 374); sparse **144** (was 238).",
    "- fantasy piers **81/56** held at spacing=5.",
    "- european glass **256**, rustic pier **88** unchanged.",
    "- pitched roof residual (~0.72-0.77) left for follow-up; not this pass.",
    "",
    "Previews: `previews/` and `attach_previews/`.",
    "",
]
(out / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
print("fixed SUMMARY/REPORT")

doc = Path("docs/look_harden.md")
text = doc.read_text(encoding="utf-8")
marker = "## fantasy_glass_dens (2026-10-20)"
if marker in text:
    print("doc section already present; skip append")
else:
    section = """
## fantasy_glass_dens (2026-10-20)

After `full_style_v3_20261020_085033` user asked to **补足短板** (fantasy glass still high; roof left for follow-up):

| style | knob | before (v3) | after | aim |
|---|---|---|---|---|
| fantasy | `window_spacing` 3→**4**, `max_window_bands` 4→**3**, `window_from_corner` (default2) kept **2** | glass **374** / 238 | ~**230** / ~**144** | denser 200–280; stay a bit glazier than euro |
| fantasy | `wall_pier_spacing` **5** kept | piers **81** / 56 | **81** / **56** | hold euro_fan_dens pier mid |

First mid-patch used euro settle recipe c3 → denser glass~212 (ok) but sparse~126 and piers 81→133 (more solid wall for pier fill). Softened to **from_corner=2**; piers snapped back, denser glass~230.

**Untouched:** european 4/3/c3, modern sp=6, industrial sp=4, rustic pier=12, scaffold_struct / pitched roof scaffold.

Smoke: `outputs/design/fantasy_glass_dens_20261020_090033/` (prior probe `..._090008` was c3). Scripts: `scripts/_patch_fantasy_glass_dens.py`, `_patch_fantasy_glass_dens2.py`, `_run_fantasy_glass_dens.py`.

**Residual:** medieval/fantasy pitched roof_score ~0.72–0.77 still needs a later scaffold pass (not this dens).
"""
    doc.write_text(text.rstrip() + "\n" + section, encoding="utf-8")
    print("appended fantasy_glass_dens to docs/look_harden.md")

# Also fix hardcoded params in run script for future re-runs
run = Path("scripts/_run_fantasy_glass_dens.py")
rt = run.read_text(encoding="utf-8")
rt2 = rt.replace(
    '"fantasy": "window_spacing=4 max_window_bands=3 window_from_corner=3; wall_pier_spacing=5 kept"',
    '"fantasy": "window_spacing=4 max_window_bands=3 window_from_corner=2; wall_pier_spacing=5 kept"',
).replace(
    "- fantasy: `window_spacing=4`, `max_window_bands=3`, `window_from_corner=3`",
    "- fantasy: `window_spacing=4`, `max_window_bands=3`, `window_from_corner=2`",
)
if rt2 != rt:
    run.write_text(rt2, encoding="utf-8")
    print("updated run script params strings")
else:
    print("run script params already ok or pattern miss")
