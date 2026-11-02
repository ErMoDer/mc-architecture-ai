# -*- coding: utf-8 -*-
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
REPORT = ROOT / "outputs/design/long_fill2_20261020_135822"
INDEX = ROOT / "data/feature_index"
TZ = timezone(timedelta(hours=8))

def src(it):
    sp = (it.get("source_path") or it.get("id") or "").replace("\\", "/").lower()
    if "hack337" in sp or "h337" in sp:
        return "hack337"
    if "mcblock" in sp:
        return "mcblock"
    return "other"

def blob(it):
    return ((it.get("name") or "") + " " + (it.get("source_path") or "") + " " + (it.get("id") or "")).replace("%20", " ").lower()

FARM = ("farm", "xpfarm", "smelter", "spawner", "breeder", "iron_farm", "mob_farm", "kelp", "afk", "duper", "刷", "经验")

def counts():
    idx = json.loads((INDEX / "index.json").read_text(encoding="utf-8"))
    items = idx.get("items") or []
    out = {}
    for sty in ["industrial", "european", "modern", "rustic", "western", "chinese", "medieval", "fantasy", "unknown"]:
        mapped = [it for it in items if (it.get("mapped_style") or "unknown") == sty]
        mcb = [it for it in mapped if src(it) == "mcblock"]
        mcb_ok = []
        for it in mcb:
            b = blob(it)
            if it.get("exclude_from_residential"):
                continue
            if any(f in b for f in FARM) and "farmhouse" not in b and not any(
                h in b for h in ("house", "home", "loft", "cottage", "villa", "cabin")
            ):
                continue
            mcb_ok.append(it)
        h337 = [it for it in mapped if src(it) == "hack337"]
        out[sty] = {
            "mapped": len(mapped),
            "mcblock": len(mcb),
            "mcblock_resid_ok": len(mcb_ok),
            "hack337": len(h337),
        }
    out["_index_n"] = len(items)
    return out

before = json.loads((REPORT / "before_counts.json").read_text(encoding="utf-8"))
after = counts()
(REPORT / "after_counts.json").write_text(json.dumps(after, ensure_ascii=False, indent=2), encoding="utf-8")
retry = json.loads((REPORT / "mcblock_topup_retry.json").read_text(encoding="utf-8"))
retag = json.loads((REPORT / "hack337_retag.json").read_text(encoding="utf-8"))
cat = json.loads((ROOT / "data/redstone_templates/catalog.json").read_text(encoding="utf-8"))
cat_ids = [t["id"] for t in cat["templates"]]
new_rs = [
    "item_filter_stub",
    "torch_tower_elevator_frag",
    "hopper_clock_xor_alt",
    "lectern_book_signal",
    "target_block_signal",
    "brewing_stand_hopper_stub",
]
paste = {}
for tid in ("item_filter_stub", "lectern_book_signal"):
    d = REPORT / f"paste_{tid}"
    paste[tid] = {"ok": d.exists(), "dir": str(d)}

now = datetime.now(TZ).isoformat(timespec="seconds")
lines = []
lines.append("# Long fill2 COUNTS\n\n")
lines.append(f"Finished: {now} (Asia/Shanghai)\n\n")
lines.append("## Styles (before → after)\n\n")
lines.append("| style | before mapped | after mapped | before mcblock | after mcblock | before ok | after ok | before h337 | after h337 |\n")
lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
for s in ["industrial", "european", "modern", "rustic", "western", "chinese", "medieval", "fantasy", "unknown"]:
    b = before.get(s, {})
    a = after.get(s, {})
    lines.append(
        "| {} | {} | {} | {} | {} | {} | {} | {} | {} |\n".format(
            s,
            b.get("mapped"),
            a.get("mapped"),
            b.get("mcblock"),
            a.get("mcblock"),
            b.get("mcblock_resid_ok"),
            a.get("mcblock_resid_ok"),
            b.get("hack337"),
            a.get("hack337"),
        )
    )
lines.append("\n## Hack337 retag (already ingested, no re-download)\n")
lines.append(f"- retagged_n: **{retag['retagged_n']}**\n")
lines.append(f"- skipped: `{json.dumps(retag.get('skipped', {}), ensure_ascii=False)}`\n")
for r in retag.get("retagged") or []:
    lines.append(f"- `{r['id']}`: {r['from']} → {r['to']}\n")
lines.append("\n## MCBlock light topup (house-only, no industrial loft)\n")
lines.append("- First pass used styles+search_q=house → listed=0 (API AND too strict for CN titles). Then **retried without search_q**.\n")
for sty, res in retry.items():
    lines.append(
        f"- **{sty}** (retry): added={res.get('added_n')} listed={res.get('listed')} exhausted={res.get('exhausted')} "
        f"skipped=`{json.dumps(res.get('skipped', {}), ensure_ascii=False)}`\n"
    )
    for a in res.get("added") or []:
        lines.append(f"  - `{a.get('fid')}` {a.get('name')}\n")
lines.append(f"\n## Redstone\n- catalog **28 → {len(cat_ids)}**\n- new: {new_rs}\n")
lines.append("\n## Smoke\n")
for tid, info in paste.items():
    lines.append(f"- paste `{tid}`: ok={info.get('ok')} → `{info.get('dir')}`\n")
lines.append("\n## Residuals\n")
lines.append("- Industrial loft MCBlock not retried (exhausted prior session).\n")
lines.append("- Modern MCBlock house pool largely already ingested (63 already / 77 listed).\n")
lines.append("- Hack337 retag is keyword-based; villager/farm left as-is.\n")
lines.append("- No VAE train; early-tech companion Chinese names untouched.\n")
(REPORT / "COUNTS.md").write_text("".join(lines), encoding="utf-8")

summary = {
    "finished_at": now,
    "report_dir": str(REPORT),
    "before": before,
    "after": after,
    "hack337_retag": {"retagged_n": retag["retagged_n"], "ids": [r["id"] for r in retag.get("retagged") or []]},
    "mcblock_topup_retry": retry,
    "redstone": {"before": 28, "after": len(cat_ids), "new_ids": new_rs},
    "paste": paste,
    "residuals": [
        "Industrial loft not retried.",
        "Modern MCBlock near-exhausted for new residential.",
        "styles+search_q=house returns 0; use styles-only listing.",
        "No VAE train; early-tech names untouched.",
    ],
}
(REPORT / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

lh = ROOT / "docs/look_harden.md"
txt = lh.read_text(encoding="utf-8")
if "mcblock euro+3" not in txt and "MCBlock retry (no search_q)" not in txt:
    txt += (
        "\n\nMCBlock retry (no search_q): "
        f"european mcblock {before['european']['mcblock']}→{after['european']['mcblock']}, "
        f"rustic {before['rustic']['mcblock']}→{after['rustic']['mcblock']}, "
        f"modern unchanged ({after['modern']['mcblock']}).\n"
    )
    lh.write_text(txt, encoding="utf-8")

print("after", {k: after[k] for k in ["european", "modern", "rustic", "western", "industrial"]})
print("templates", len(cat_ids))
print("report", REPORT)
