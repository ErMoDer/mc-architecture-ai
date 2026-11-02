import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(".")
outdir = Path(open("_style_refs_outdir.txt", encoding="utf-8").read().strip())
tz = timezone(timedelta(hours=8))
items = json.loads((ROOT / "data/feature_index/index.json").read_text(encoding="utf-8")).get("items") or []

def is_mcblock(it):
    sp = str(it.get("source_path") or it.get("source") or "").replace("\\", "/").lower()
    return "mcblock" in sp

c = Counter(it.get("mapped_style") or "unknown" for it in items)
mc = Counter(it.get("mapped_style") or "unknown" for it in items if is_mcblock(it))
before = json.loads((outdir / "STYLE_COUNTS_BEFORE.json").read_text(encoding="utf-8"))
after = {
    "at": datetime.now(tz).isoformat(timespec="seconds"),
    "feature_index_n": len(items),
    "mapped_style": dict(c.most_common()),
    "mcblock_mapped_style": dict(mc.most_common()),
    "block2vec_npy_n": len(list((ROOT / "data/feature_index").glob("*_block2vec.npy"))),
}
(outdir / "STYLE_COUNTS_AFTER.json").write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")

fetch = json.loads((outdir / "report.json").read_text(encoding="utf-8")) if (outdir / "report.json").exists() else {}
reing = json.loads((outdir / "reingest/report.json").read_text(encoding="utf-8")) if (outdir / "reingest/report.json").exists() else {}
supp = json.loads((outdir / "supplement_weak.json").read_text(encoding="utf-8")) if (outdir / "supplement_weak.json").exists() else {}
smoke = json.loads((outdir / "smoke/smoke_retrieval.json").read_text(encoding="utf-8"))

styles = ["european", "chinese", "medieval", "modern", "industrial", "rustic", "fantasy"]
mb = before.get("mapped_style") or {}
ma = after["mapped_style"]
mcb = before.get("mcblock_mapped_style") or {}
mca = after["mcblock_mapped_style"]

lines = [
    "# style_refs report",
    "",
    f"- out: `{outdir.as_posix()}`",
    "- no VAE train",
    "",
    "## Counts before → after",
    "",
    "| style | mapped before | mapped after | mcblock before | mcblock after | Δ mcblock |",
    "|---|---|---|---|---|---|",
]
for s in styles:
    lines.append(
        "| %s | %s | %s | %s | %s | %+d |"
        % (s, mb.get(s, 0), ma.get(s, 0), mcb.get(s, 0), mca.get(s, 0), int(mca.get(s, 0)) - int(mcb.get(s, 0)))
    )
lines += [
    "",
    f"- feature_index_n: **{before.get('feature_index_n')} → {after['feature_index_n']}** (+{after['feature_index_n']-int(before.get('feature_index_n') or 0)})",
    f"- block2vec npy files: {after['block2vec_npy_n']}",
    "",
    "## Added this run",
    f"- fetch_new (API curated): {fetch.get('fetch_new_rows')} → {fetch.get('fetch_added_by_style')}",
    f"- reingest existing houses: {len(reing.get('index_ingested') or [])} → {reing.get('index_ingested_by_style')}",
    f"- supplement weak (styles-only, no difficulty): {supp.get('added_by_style')}",
    "",
    "## Saturation / residuals",
    "- **chinese / industrial / rustic / modern**: MCBlock API largely **saturated** for *new* strong residential hits (query + styles-only + no-diff mostly already in manifest). mcblock counts for these barely moved.",
    "- **european**: +1 new via supplement; pool still smaller than medieval/fantasy.",
    "- **medieval / fantasy**: main gains (new API downloads + reingest of existing litematics into feature_index + block2vec).",
    "- Index still chinese-heavy overall from non-mcblock mass; retrieval scoring keeps **mcblock on top** for all target styles.",
    "",
    "## Retrieval smoke (top-3 with Block2Vec)",
    "",
]
style_ok = 0
style_tot = 0
for st, block in (smoke.get("styles") or {}).items():
    tops = block.get("with_b2v") or []
    lines.append(f"### {st}")
    lines.append(
        f"- mcblock_all_top={block.get('mcblock_all_top')} hack337_in_top={block.get('hack337_in_top')}"
    )
    for t in tops:
        ms = t.get("mapped_style")
        style_tot += 1
        if ms == st:
            style_ok += 1
        lines.append(
            f"  - `{t.get('id')}` mapped_style={ms} score={t.get('score')} mc={t.get('is_mcblock')} hack={t.get('is_hack337')}"
        )
    lines.append("")
lines.append(f"**mcblock_wins_all_styles:** {smoke.get('mcblock_wins_all_styles')}")
lines.append(f"**mapped_style match in top-3:** {style_ok}/{style_tot}")
lines.append("")
(outdir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
(outdir / "NOTES.md").write_text(
    "# NOTES\n\n- LOCAL_ONLY; no VAE train; no PR.\n"
    "- Used `_fetch_style_houses_curated.py`, reingest, `_supplement_weak_style_houses.py`.\n"
    "- Strong house evidence only; Hack337 challenge spam rejected.\n",
    encoding="utf-8",
)
print("index", before.get("feature_index_n"), "->", after["feature_index_n"])
print("mcblock after", {k: mca.get(k) for k in styles})
print("delta mcblock", {k: int(mca.get(k, 0)) - int(mcb.get(k, 0)) for k in styles})
print("style match", style_ok, "/", style_tot)
print("wrote", outdir / "SUMMARY.md")
