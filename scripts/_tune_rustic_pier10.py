from pathlib import Path
from src.app.gen_strategy import generate_similar_scaffold, project_root

p = Path("src/app/look_harden.py")
t = p.read_text(encoding="utf-8")
# Only replace inside rustic: the comment+8 line we added
needle = """        # Was sp=4 (~300 pier cells / 柱林); widen so vertical accent stays but thinner rhythm.
        \"wall_pier_spacing\": 8,"""
# file has normal quotes
needle = """        # Was sp=4 (~300 pier cells / 柱林); widen so vertical accent stays but thinner rhythm.
        "wall_pier_spacing": 8,"""
repl = """        # Was sp=4 (~300 pier cells / 柱林); widen so vertical accent stays but thinner rhythm.
        "wall_pier_spacing": 10,"""
if needle not in t:
    raise SystemExit("needle missing")
p.write_text(t.replace(needle, repl, 1), encoding="utf-8")

root = project_root()
for seed in (201, 202):
    m = generate_similar_scaffold(
        style="rustic", terrain="flat", num=1,
        out_dir=root / "outputs" / "_tmp_rp10" / str(seed),
        seed=seed, top_k_refs=3, vae_fill=False, look_harden_enable=True,
    )[0]
    pier = next((a for a in (m.get("look_harden") or {}).get("actions") or [] if str(a).startswith("wall_piers:")), None)
    print(seed, pier, "roof", (m.get("structure") or {}).get("metrics", {}).get("roof_score"))
