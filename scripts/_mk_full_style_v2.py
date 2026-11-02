from pathlib import Path
import re
p = Path("scripts/_run_full_style_v2.py")
t = p.read_text(encoding="utf-8")
t = t.replace("full_style_review_", "full_style_v2_")
t = t.replace("# full_style_review batch", "# full_style_v2 batch")
t = t.replace(
    '"""Full multi-style similar_scaffold review batch (current polish, no new harden)."""',
    '"""Full-style v2 review: style_refs pool + scaffold_struct + look polish (no code changes)."""',
)
# enrich NOTES / summary vs lines
t = t.replace(
    "- Review batch of current polish (look_polish + win_eave + door_wall). No new harden this run.",
    "- After style_refs_20261019_202242 (index~1052) + scaffold_struct_20261019_204603 + glass_dens/rustic pier=12. No new harden.",
)
t = t.replace(
    "- Review only; polish code unchanged.",
    "- Review only; no look_harden/gen_strategy edits.",
)
t = t.replace(
    "- Metrics from existing look_harden actions (door/window/pier/eave).",
    "- Metrics: structure/roof + door/window/pier; note retrieval reference_id when present.",
)
# ensure industrial in STYLES
if '("industrial"' not in t:
    raise SystemExit("industrial missing from STYLES")
p.write_text(t, encoding="utf-8")
# strip BOM if any
raw = p.read_bytes()
if raw.startswith(b"\xef\xbb\xbf"):
    p.write_bytes(raw[3:])
import ast
ast.parse(p.read_text(encoding="utf-8"))
print("script ok", "full_style_v2_" in p.read_text(encoding="utf-8"))
