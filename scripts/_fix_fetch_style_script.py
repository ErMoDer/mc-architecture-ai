from pathlib import Path

p = Path("scripts/_fetch_style_houses_curated.py")
t = p.read_text(encoding="utf-8")

bad = '''        queries = list(STYLE_QUERIES.get(style, [style + " house"]))
            # MCBlock: styles=[rustic|fantasy] works; combining English search_q often returns empty.
            if style in ("rustic", "fantasy"):
                query_list = [None] + queries
            else:
                query_list = queries + [None]
        for query in query_list:
'''
good = '''        queries = list(STYLE_QUERIES.get(style, [style + " house"]))
        # MCBlock: styles=[rustic|fantasy] works; combining English search_q often returns empty.
        if style in ("rustic", "fantasy"):
            query_list = [None] + queries
        else:
            query_list = queries + [None]
        for query in query_list:
'''
if bad not in t:
    raise SystemExit("indent block not found")
t = t.replace(bad, good, 1)

# Expand queries + bump caps for this refill (keep strong residential evidence filters)
old_q = '''STYLE_QUERIES = {
    "european": ["european house", "victorian house", "townhouse", "european villa"],
    "medieval": ["medieval house", "medieval cottage", "stone house", "farmhouse"],
    "modern": ["modern house", "modern villa", "apartment", "concrete house"],
    "chinese": ["chinese house", "siheyuan", "��ʽ����", "��ʽС��", "�ĺ�Ժ"],
    "japanese": ["japanese house", "minka"],
    "industrial": ["industrial house", "warehouse loft", "brick factory house"],
'''
# Use unicode escapes for CJK to avoid encoding issues in this patcher
old_caps = '''CAPS = {
    "european": 15, "medieval": 15, "modern": 15,
    "chinese": 15, "japanese": 12, "industrial": 10,
    "rustic": 20, "fantasy": 20,
}
'''
new_caps = '''CAPS = {
    "european": 18, "medieval": 18, "modern": 18,
    "chinese": 20, "japanese": 12, "industrial": 18,
    "rustic": 18, "fantasy": 15,
}
'''
if old_caps not in t:
    raise SystemExit("CAPS missing")
t = t.replace(old_caps, new_caps, 1)

# Strengthen STYLE_QUERIES with alternate English (CJK already in file)
# Replace european/medieval/modern/industrial/chinese query lists carefully
import re

def set_queries(text, style, queries):
    # replace the list after "style": 
    pat = rf'("{style}": )\[(.*?)\]'
    repl = rf'\1{json_dumps}'
    return text

import json as _json
replacements = {
    "european": ["european house", "victorian house", "townhouse", "european villa", "georgian house", "row house", "french house", "german house"],
    "medieval": ["medieval house", "medieval cottage", "stone house", "timber house", "half timbered house", "castle house", "nordic house"],
    "modern": ["modern house", "modern villa", "apartment", "concrete house", "minimalist house", "contemporary house", "glass house"],
    "chinese": [
        "chinese house", "siheyuan", "chinese villa", "chinese courtyard", "chinese pavilion house",
        "\u4e2d\u5f0f\u5efa\u7b51", "\u4e2d\u5f0f\u5c0f\u5c4b", "\u56db\u5408\u9662", "\u4e2d\u5f0f\u522b\u5885",
    ],
    "industrial": ["industrial house", "warehouse loft", "brick factory house", "loft house", "industrial loft", "brick warehouse home"],
    "rustic": [
        "rustic house", "cabin", "log cabin", "farmhouse", "cottage", "chalet", "barn house", "mountain cabin",
        "\u7530\u56ed", "\u519c\u820d", "\u6728\u5c4b", "\u4e61\u6751\u5c0f\u5c4b",
    ],
    "fantasy": [
        "fantasy house", "elf house", "wizard tower house", "fairy cottage", "mushroom house", "mage house",
        "\u5947\u5e7b", "\u7cbe\u7075\u5c0f\u5c4b", "\u9b54\u6cd5\u5c0f\u5c4b",
    ],
}
for style, qs in replacements.items():
    pat = re.compile(rf'("{style}": )\[.*?\]', re.S)
    m = pat.search(t)
    if not m:
        print("warn no match", style)
        continue
    # only replace within STYLE_QUERIES section (first occurrence after STYLE_QUERIES)
    t = pat.sub(rf'\1{_json.dumps(qs, ensure_ascii=False)}', t, count=1)
    print("queries", style, len(qs))

p.write_text(t, encoding="utf-8")
import ast
ast.parse(p.read_text(encoding="utf-8"))
print("syntax ok")
