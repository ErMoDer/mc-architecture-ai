from pathlib import Path

section = """## Window / eave polish (2026-10-19)

Scaffold look_harden facade polish (no VAE train):

1. **Window rhythm** — even story bands from `floor_spacing` (not every irregular floor peak); centered columns; optional **sill/header** with `window_frame` / accent; `max_window_bands` + style spacing (`_STYLE_FACADE`).
2. **Eaves** — `eave_overhang` (0–2) actually walks outward; never clears flat-deck cover on the footprint (euro/chinese/rustic preserve).
3. **Cornice ring** — peri trim at `roof_y-1` when style wants it; still works when the footprint fills the 32^3 box and overhang has no room.
4. Preserve existing window-like openings + glass; do not fill real windows when repairing floors/holes.

Smoke: `scripts/_run_win_eave_smoke.py` -> `outputs/design/win_eave_*`.
"""

section2 = """## Window / eave polish (2026-10-19)

similar_scaffold -> look_harden facade path:

- Regular window columns + sill/header; style spacing via `look_harden._STYLE_FACADE`.
- Eave overhang + cornice under deck; flat-deck styles keep roof cover from look_polish.
- Smoke: `scripts/_run_win_eave_smoke.py`.
"""

for path, sec in [
    (Path("docs/look_harden.md"), section),
    (Path("docs/gen_strategy.md"), section2),
]:
    t = path.read_text(encoding="utf-8")
    start = t.find("## Window / eave polish")
    head = t[:start] if start >= 0 else t.rstrip() + "\n\n"
    path.write_text(head.rstrip() + "\n\n" + sec, encoding="utf-8")
    print(path, "ok", "`floor_spacing`" in path.read_text(encoding="utf-8"))
