#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Walk docs/mc-knowledge/**/*.md and regenerate INDEX.md + index.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "mc-knowledge"
SKIP_NAMES = {"README.md", "INDEX.md", "SOURCES.md", "index.json"}

TAG_HINTS = {
    "versions": ["version"],
    "redstone": ["redstone"],
    "farms": ["farm"],
    "blocks": ["block"],
    "builds": ["build"],
}


def title_and_summary(text: str) -> tuple[str, str]:
    title = ""
    purpose = ""
    for line in text.splitlines():
        s = line.strip()
        if not title and s.startswith("# "):
            title = s[2:].strip()
            continue
        if s.startswith("**用途**") or s.startswith("**目的**"):
            purpose = re.sub(r"^\*\*用[途的]\*\*[：:]\s*", "", s)
            purpose = purpose.replace("**用途**：", "").replace("**用途**:", "")
            if purpose.startswith("**"):
                purpose = re.sub(r"^\*\*[^*]+\*\*[：:]\s*", "", s)
            break
        if not purpose and s and not s.startswith("#") and not s.startswith(">") and not s.startswith("|"):
            if s.startswith("**") and "用途" in s:
                purpose = re.sub(r"^\*\*[^*]+\*\*[：:]\s*", "", s)
                break
    if not purpose:
        for line in text.splitlines():
            s = line.strip()
            if s and not s.startswith("#") and not s.startswith(">") and not s.startswith("|") and not s.startswith("**来源"):
                if s.startswith("面向") or s.startswith("companion") or "笔记" in s or "速查" in s:
                    purpose = s[:120]
                    break
    return title or "untitled", (purpose or title)[:160]


def tags_for(rel: Path) -> list[str]:
    parts = rel.parts
    tags: list[str] = []
    if parts:
        tags.extend(TAG_HINTS.get(parts[0], [parts[0]]))
    name = rel.stem.lower()
    for key in ("version", "redstone", "farm", "block", "build", "copper", "tuff", "wood", "26.3", "1.21"):
        if key.replace(".", "") in name.replace(".", "") or key in name:
            if key not in tags:
                tags.append(key)
    # normalize
    out: list[str] = []
    for t in tags:
        if t not in out:
            out.append(t)
    return out


def main() -> None:
    entries = []
    for path in sorted(ROOT.rglob("*.md")):
        if path.name in SKIP_NAMES:
            continue
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        title, summary = title_and_summary(text)
        eid = str(rel).replace("\\", "/").removesuffix(".md").replace("/", "-")
        entries.append(
            {
                "id": eid,
                "title": title,
                "path": str(rel).replace("\\", "/"),
                "tags": tags_for(rel),
                "summary": summary,
            }
        )

    index_json = ROOT / "index.json"
    index_json.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 知识库索引",
        "",
        "由 `scripts/kb_index.py` 自动生成。勿手改；改文档后重新运行脚本。",
        "",
        f"共 **{len(entries)}** 篇。",
        "",
        "| id | title | path | tags | summary |",
        "|----|-------|------|------|---------|",
    ]
    for e in entries:
        tags = ", ".join(e["tags"])
        summary = e["summary"].replace("|", "\\|")
        title = e["title"].replace("|", "\\|")
        lines.append(f"| `{e['id']}` | {title} | [{e['path']}]({e['path']}) | {tags} | {summary} |")
    lines.append("")
    (ROOT / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {index_json} and INDEX.md ({len(entries)} entries)")


if __name__ == "__main__":
    main()
