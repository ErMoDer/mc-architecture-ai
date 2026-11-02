from pathlib import Path
src = Path("scripts/_run_full_style_v2.py").read_text(encoding="utf-8")
dst = src.replace("full_style_v2_", "full_style_v3_")
dst = dst.replace("# full_style_v2 batch", "# full_style_v3 batch")
dst = dst.replace(
    '"""Full-style v2 review: style_refs pool + scaffold_struct + look polish (no code changes)."""',
    '"""Full-style v3 smoke: after euro_fan_dens facade knobs; similar_scaffold only; no retrain."""',
)
dst = dst.replace(
    "- After style_refs_20261019_202242 (index~1052) + scaffold_struct_20261019_204603 + glass_dens/rustic pier=12. No new harden.",
    "- After euro_fan_dens_20261019_212806 (eu glass dens + fantasy pier=5) on top of style_refs~1052 + scaffold_struct. No new harden this run.",
)
dst = dst.replace("## vs win_eave", "## vs full_style_v2 / euro_fan_dens")
dst = dst.replace(
    "- Kept window rhythm / sill / eaves / cornice / flat decks.",
    "- Expect eu glass ~256 (was v2 448); fantasy piers ~81/56 (was 221/115); modern/industrial/rustic stable; roofs hold.",
)
dst = dst.replace(
    "- Review only; no look_harden/gen_strategy edits.",
    "- Review only after euro_fan_dens; no look_harden/gen_strategy edits this run.",
)
Path("scripts/_run_full_style_v3.py").write_text(dst, encoding="utf-8")
import ast
ast.parse(dst)
print("wrote", "full_style_v3_" in dst, len(dst))
