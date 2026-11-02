from pathlib import Path
sec1 = """## Scaffold structure harden (2026-10-19)

similar_scaffold / rule_scaffold skeleton polish (no VAE train; facade look_harden unchanged):

1. **Floors** — `_normalize_story_floors`: spacing≈5, min_gap=3, max 5 stories; ref `y_peaks` are hints only (stops industrial floor-every-3). Roof deck Y is not a floor slab. Sparse interiors fill only on the **ground** story.
2. **Shell** — `_seal_shell_columns` closes perimeter air gaps under the deck.
3. **Roof** — flat-deck styles keep filled low deck (euro/chinese/rustic roof≈1). Medieval/fantasy add broad **deck+gable** on scaffold; look_harden pitched uses a **ridge plateau** so cover is not needle-thin.

Smoke: `scripts/_run_scaffold_struct_smoke.py` -> `outputs/design/scaffold_struct_*`.
"""
sec2 = """## Scaffold structure harden (2026-10-19)

See `docs/gen_strategy.md`. Scaffold path still uses `SCAFFOLD_THRESHOLDS` (min_roof 0.18). Floor/shell/roof builders live in `gen_strategy.scaffold_from_occupancy`; pitched cover plateau in `look_harden.harden_roof_silhouette` (non flat-deck styles only).
"""
for path, sec in [(Path("docs/gen_strategy.md"), sec1), (Path("docs/structure_constraints.md"), sec2)]:
    t = path.read_text(encoding="utf-8")
    start = t.find("## Scaffold structure harden")
    head = t[:start] if start >= 0 else t.rstrip() + "\n\n"
    path.write_text(head.rstrip() + "\n\n" + sec, encoding="utf-8")
    print(path.name, "ok")
