# -*- coding: utf-8 -*-
"""Load MCJE redstone principle rules JSON and attach to analyze / template match.

Not a vanilla engine. Rules are for report vocabulary + template notes only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_RULES_REL = Path("docs/mc-knowledge/redstone/redstone_principles_rules.json")
_cached: dict[str, Any] | None = None


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def rules_path(root: Path | None = None) -> Path:
    return (root or project_root()) / _RULES_REL


def load_principle_rules(root: Path | None = None, *, force: bool = False) -> dict[str, Any]:
    global _cached
    if _cached is not None and not force:
        return _cached
    path = rules_path(root)
    if not path.is_file():
        _cached = {
            "schema_version": 0,
            "disclaimer": "rules JSON missing",
            "rules": [],
            "pattern_cite_extras": {},
            "kb_docs": [],
            "_path": str(path),
            "_loaded": False,
        }
        return _cached
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        data["_path"] = str(path.relative_to(root or project_root())).replace("\\", "/")
    except ValueError:
        data["_path"] = str(path).replace("\\", "/")
    data["_loaded"] = True
    _cached = data
    return data


def _snippet(path: Path, max_chars: int = 140, prefer_keywords: list[str] | None = None) -> str:
    """Short paragraph from a KB md (same spirit as analyze._load_cite_snippet)."""
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    paras: list[str] = []
    buf: list[str] = []
    link_re = re.compile(r"\[([^\]]+)\]\([^)]+\)")
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            if buf:
                paras.append(" ".join(buf))
                buf = []
            h = s.lstrip("#").strip()
            if h:
                paras.append(h)
            continue
        if not s or s.startswith("|") or s.startswith("---") or s.startswith(">"):
            if buf:
                paras.append(" ".join(buf))
                buf = []
            continue
        s = link_re.sub(r"\1", s).replace("**", "")
        buf.append(s)
    if buf:
        paras.append(" ".join(buf))
    prefer = [k.lower() for k in (prefer_keywords or []) if k]
    ranked: list[tuple[int, str]] = []
    for para in paras:
        if len(para) < 16:
            continue
        score = sum(1 for k in prefer if k in para.lower()) if prefer else 0
        ranked.append((score, para))
    if not ranked:
        return ""
    ranked.sort(key=lambda x: (-x[0], -len(x[1])))
    if prefer and ranked[0][0] > 0:
        para = ranked[0][1]
    else:
        para = next((p for _s, p in ranked if len(p) >= 40), ranked[0][1])
    return para[:max_chars].rstrip() + ("…" if len(para) > max_chars else "")


def extra_cites_for_pattern(pattern_id: str, root: Path | None = None) -> list[str]:
    data = load_principle_rules(root)
    return list((data.get("pattern_cite_extras") or {}).get(pattern_id) or [])


def rules_for_pattern(pattern_id: str, root: Path | None = None) -> list[dict[str, Any]]:
    data = load_principle_rules(root)
    out = []
    for rule in data.get("rules") or []:
        pids = rule.get("pattern_ids") or []
        if pattern_id in pids:
            out.append(rule)
    return out


def rules_for_template_match(match_id: str, root: Path | None = None) -> list[dict[str, Any]]:
    data = load_principle_rules(root)
    out = []
    for rule in data.get("rules") or []:
        mids = rule.get("template_matches") or []
        if "*" in mids or match_id in mids:
            out.append(rule)
    return out


def apply_principle_rules_to_analyze(
    analyze_rs: dict[str, Any],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Return principle_rules block to merge into redstone analyze dict."""
    root = root or project_root()
    data = load_principle_rules(root)
    pattern_ids: set[str] = set()
    for inf in analyze_rs.get("global_inferences") or []:
        if inf.get("id"):
            pattern_ids.add(str(inf["id"]))
    for pat in (analyze_rs.get("common_patterns") or {}).get("patterns") or []:
        if pat.get("id"):
            pattern_ids.add(str(pat["id"]))
    for clk in (analyze_rs.get("clocks") or {}).get("clocks") or []:
        if clk.get("id"):
            pattern_ids.add(str(clk["id"]))
    qc = analyze_rs.get("qc_bud") or {}
    if qc.get("qc_candidate_count") or qc.get("bud_standby_suspect_count"):
        pattern_ids.add("qc_bud")

    applied: list[dict[str, Any]] = []
    seen_rule: set[str] = set()
    for pid in sorted(pattern_ids):
        for rule in rules_for_pattern(pid, root):
            rid = rule["id"]
            if rid in seen_rule:
                for a in applied:
                    if a["id"] == rid and pid not in a["triggered_by"]:
                        a["triggered_by"].append(pid)
                continue
            seen_rule.add(rid)
            applied.append(
                {
                    "id": rid,
                    "title": rule.get("title"),
                    "note_zh": rule.get("note_zh"),
                    "tags": list(rule.get("tags") or []),
                    "vocabulary": list(rule.get("vocabulary") or []),
                    "cites": list(rule.get("cites") or []),
                    "ai_may": list(rule.get("ai_may") or []),
                    "ai_must_not": list(rule.get("ai_must_not") or []),
                    "triggered_by": [pid],
                }
            )

    if analyze_rs.get("total_redstone_blocks") and "ai_template_only" not in seen_rule:
        for rule in data.get("rules") or []:
            if rule.get("id") == "ai_template_only":
                applied.append(
                    {
                        "id": rule["id"],
                        "title": rule.get("title"),
                        "note_zh": rule.get("note_zh"),
                        "tags": list(rule.get("tags") or []),
                        "vocabulary": list(rule.get("vocabulary") or []),
                        "cites": list(rule.get("cites") or []),
                        "ai_may": list(rule.get("ai_may") or []),
                        "ai_must_not": list(rule.get("ai_must_not") or []),
                        "triggered_by": ["*"],
                    }
                )
                break

    principles = analyze_rs.get("principles") or []
    extras_map = data.get("pattern_cite_extras") or {}
    for pitem in principles:
        pid = pitem.get("id")
        extra_paths = list(extras_map.get(pid) or [])
        existing = {c.get("path") for c in (pitem.get("cites") or [])}
        cites = list(pitem.get("cites") or [])
        for rel in extra_paths:
            if rel in existing:
                continue
            snippet = _snippet(root / rel, prefer_keywords=list(str(pitem.get("title") or "").split()))
            cites.append({"path": rel, "snippet": snippet, "via": "principle_rules"})
        pitem["cites"] = cites
        pitem["principle_rule_ids"] = [r["id"] for r in rules_for_pattern(str(pid), root)]

    return {
        "schema_version": data.get("schema_version"),
        "rules_path": data.get("_path"),
        "loaded": bool(data.get("_loaded")),
        "disclaimer": data.get("disclaimer"),
        "kb_docs": list(data.get("kb_docs") or []),
        "applied": applied,
        "pattern_ids_considered": sorted(pattern_ids),
    }


def principle_notes_for_template(
    pattern_id: str,
    template_id: str,
    *,
    root: Path | None = None,
) -> tuple[list[str], str]:
    """Return (rule_ids, notes_zh) for a template match row."""
    root = root or project_root()
    seen: dict[str, dict[str, Any]] = {}
    for r in rules_for_pattern(pattern_id, root):
        seen[r["id"]] = r
    for r in rules_for_template_match(pattern_id, root):
        seen[r["id"]] = r
    for r in rules_for_template_match(template_id, root):
        seen[r["id"]] = r
    ids = list(seen.keys())
    notes = " | ".join(
        f"[{r['id']}] {r.get('note_zh')}" for r in seen.values() if r.get("note_zh")
    )
    return ids, notes
