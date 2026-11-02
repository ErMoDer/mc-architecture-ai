from pathlib import Path
for path, sec in [
    (Path("docs/look_harden.md"), """## Rustic pier spacing (2026-10-19)

After review batches showed rustic `wall_piers` ~300–322 cells (柱林):

- rustic `wall_pier_spacing` **4 → 8** only; piers kept, thinner vertical rhythm (~half columns).
- modern/industrial glass_dens knobs untouched.

Smoke: `scripts/_run_rustic_pier_smoke.py` -> `outputs/design/rustic_pier_*`.
"""),
    (Path("docs/gen_strategy.md"), """## Rustic pier spacing (2026-10-19)

`_STYLE_FACADE[\"rustic\"].wall_pier_spacing` 4→8. Other styles unchanged.
Smoke: `scripts/_run_rustic_pier_smoke.py`.
"""),
]:
    # fix gen_strategy without escaped quotes in content
    pass

sec1 = """## Rustic pier spacing (2026-10-19)

After review batches showed rustic wall_piers ~300-322 cells (柱林):

- rustic `wall_pier_spacing` **4 → 8** only; piers kept, thinner vertical rhythm (~half columns).
- modern/industrial glass_dens knobs untouched.

Smoke: `scripts/_run_rustic_pier_smoke.py` -> `outputs/design/rustic_pier_*`.
"""
sec2 = """## Rustic pier spacing (2026-10-19)

`_STYLE_FACADE` rustic `wall_pier_spacing` 4→8. Other styles unchanged.
Smoke: `scripts/_run_rustic_pier_smoke.py`.
"""
for path, sec in [(Path("docs/look_harden.md"), sec1), (Path("docs/gen_strategy.md"), sec2)]:
    t = path.read_text(encoding="utf-8")
    start = t.find("## Rustic pier spacing")
    head = t[:start] if start >= 0 else t.rstrip() + "\n\n"
    path.write_text(head.rstrip() + "\n\n" + sec, encoding="utf-8")
    print(path.name, "ok")
