from pathlib import Path

sec1 = """## Glass density (modern / industrial, 2026-10-19)

After `full_style_review_*` (modern glass~320, industrial~456):

- **modern**: `window_spacing=6`, `window_width_max=2`, `max_window_bands=2`, `window_from_corner=3` — still opener bay width than euro, breaks curtain walls.
- **industrial**: added to `_STYLE_FACADE` (was falling through to dense defaults); `spacing=4`, `width_max=1`, `max_window_bands=3`, solid panels via pier spacing.

Other styles unchanged. Smoke: `scripts/_run_glass_dens_smoke.py` -> `outputs/design/glass_dens_*`.
"""
sec2 = """## Glass density (modern / industrial, 2026-10-19)

`_STYLE_FACADE` only: modern/industrial window spacing & band caps. No change to euro/chinese/rustic flat-deck or door/pier rules for other styles.
Smoke: `scripts/_run_glass_dens_smoke.py`.
"""
for path, sec in [(Path("docs/look_harden.md"), sec1), (Path("docs/gen_strategy.md"), sec2)]:
    t = path.read_text(encoding="utf-8")
    start = t.find("## Glass density")
    head = t[:start] if start >= 0 else t.rstrip() + "\n\n"
    path.write_text(head.rstrip() + "\n\n" + sec, encoding="utf-8")
    print(path.name, "ok")
