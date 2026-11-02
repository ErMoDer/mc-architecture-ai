import json
from pathlib import Path
from src.app.gen_strategy import retrieve_style_refs

outdir = Path(open("_style_refs_outdir.txt", encoding="utf-8").read().strip())
styles = ["european", "chinese", "medieval", "modern", "industrial", "rustic", "fantasy"]
rows = []
ok = tot = 0
for st in styles:
    refs = retrieve_style_refs(st, "flat", top_k=3, use_block2vec=True)
    tops = []
    for f in refs:
        ms = (f.get("style") or {}).get("mapped_style") or f.get("mapped_style")
        src = (f.get("source_path") or "").replace("\\", "/")
        tot += 1
        if ms == st:
            ok += 1
        tops.append({
            "id": f.get("id"),
            "mapped_style": ms,
            "score": round(float(f.get("_retrieve_score") or 0), 4),
            "is_mcblock": "mcblock" in src.lower(),
            "is_hack337": "hack337" in src.lower(),
        })
    rows.append({"style": st, "tops": tops, "mcblock_all": all(t["is_mcblock"] for t in tops), "style_hits": sum(1 for t in tops if t["mapped_style"]==st)})
    print(st, "hits", rows[-1]["style_hits"], "/3", [t["mapped_style"] for t in tops])

rep = {"mapped_style_match": f"{ok}/{tot}", "per_style": rows}
(outdir / "smoke" / "smoke_style_match.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

# append correction to SUMMARY
sum_path = outdir / "SUMMARY.md"
t = sum_path.read_text(encoding="utf-8")
extra = [
    "",
    "## Style match (corrected: `style.mapped_style`)",
    f"- **{ok}/{tot}** top-3 hits have mapped_style == query style",
    "- Note: smoke_b2v_retrieval `_brief` reads top-level `mapped_style` (often null); nested `style.mapped_style` is authoritative.",
    "",
]
for r in rows:
    extra.append(f"- **{r['style']}**: {r['style_hits']}/3 correct; mcblock_all={r['mcblock_all']}; styles={[t['mapped_style'] for t in r['tops']]}")
extra.append("")
if "## Style match (corrected" not in t:
    sum_path.write_text(t.rstrip() + "\n" + "\n".join(extra), encoding="utf-8")
print("match", ok, tot)
