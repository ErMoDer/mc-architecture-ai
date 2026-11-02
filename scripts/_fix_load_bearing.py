# -*- coding: utf-8 -*-
from pathlib import Path

sm_path = Path("src/app/scaffold_materials.py")
sm = sm_path.read_text(encoding="utf-8")
old = (
    "def _score_role(short: str, role: str, style: str | None = None) -> float:\n"
    "    s = short.lower()\n"
    "    if _is_skip(s):\n"
    "        return -1.0\n"
    "    if _style_role_denied(s, role, style):\n"
    "        return -1.0\n"
)
new = (
    "def _score_role(short: str, role: str, style: str | None = None) -> float:\n"
    "    s = short.lower()\n"
    "    if _is_skip(s):\n"
    "        return -1.0\n"
    "    if _style_role_denied(s, role, style):\n"
    "        return -1.0\n"
    "    # Glass / panes never carry mass or load.\n"
    "    if role in (\"foundation\", \"wall\", \"roof\", \"floor\", \"accent\", \"load_bearing\"):\n"
    "        if \"glass\" in s or s.endswith(\"_pane\") or s in (\"iron_bars\", \"chain\", \"ladder\", \"scaffolding\"):\n"
    "            return -1.0\n"
    "    if role == \"window_frame\" and (\"glass\" in s or s.endswith(\"_pane\")):\n"
    "        return -1.0\n"
)
if old not in sm:
    raise SystemExit("score head missing")
sm = sm.replace(old, new, 1)

marker = 'info["load_bearing_id"] = int(roles["load_bearing"])'
if marker not in sm:
    raise SystemExit("marker missing")
inject = (
    "    # Harden load_bearing: full cube, never glass/stairs, prefer != wall.\n"
    "    lb = int(roles.get(\"load_bearing\") or 0)\n"
    "    lb_short = role_names.get(\"load_bearing\") or short_block_name(palette.get(lb, \"?\"))\n"
    "    if any(tok in lb_short for tok in (\"glass\", \"pane\", \"stair\", \"slab\", \"bar\", \"chain\")):\n"
    "        fb = list((fallbacks.get(\"load_bearing\") or ())) + list((fallbacks.get(\"accent\") or ())) + [\n"
    "            \"oak_log\", \"spruce_log\", \"stone_bricks\", \"iron_block\", \"cobblestone\",\n"
    "        ]\n"
    "        pid = _resolve_id(name_to_id, fb)\n"
    "        if pid:\n"
    "            roles[\"load_bearing\"] = int(pid)\n"
    "            role_names[\"load_bearing\"] = short_block_name(palette.get(int(pid), \"?\"))\n"
    "            info[\"load_bearing_remapped\"] = True\n"
    "    lb = int(roles[\"load_bearing\"])\n"
    "    lb = prefer_full_cube(name_to_id, role_names.get(\"load_bearing\", \"\"), palette, lb)\n"
    "    roles[\"load_bearing\"] = int(lb)\n"
    "    role_names[\"load_bearing\"] = short_block_name(palette.get(int(lb), \"?\"))\n"
    "    if roles[\"load_bearing\"] == roles[\"wall\"]:\n"
    "        for a in list((fallbacks.get(\"load_bearing\") or ())) + list((fallbacks.get(\"accent\") or ())) + [\n"
    "            \"oak_log\", \"spruce_log\", \"dark_oak_log\", \"iron_block\", \"stone_bricks\",\n"
    "        ]:\n"
    "            pid = _resolve_id(name_to_id, [a])\n"
    "            if pid and pid > 0 and pid != roles[\"wall\"]:\n"
    "                roles[\"load_bearing\"] = int(pid)\n"
    "                role_names[\"load_bearing\"] = short_block_name(palette.get(int(pid), \"?\"))\n"
    "                break\n"
    "\n"
)
sm = sm.replace(marker, inject + "    " + marker, 1)
sm_path.write_text(sm, encoding="utf-8")
print("scaffold_materials OK")

gs_path = Path("src/app/gen_strategy.py")
gs = gs_path.read_text(encoding="utf-8")
old2 = (
    "                # Corner posts use load_bearing when available (logs/stone), not trim clutter.\n"
    "                corner_id = int(mat_info.get(\"load_bearing_id\") or accent_id)\n"
)
new2 = (
    "                # Corner posts: load_bearing if distinct from wall, else accent (logs).\n"
    "                corner_id = int(mat_info.get(\"load_bearing_id\") or accent_id)\n"
    "                if corner_id == int(wall_id):\n"
    "                    corner_id = int(accent_id)\n"
    "\n"
)
if old2 not in gs:
    raise SystemExit("corner block missing")
gs_path.write_text(gs.replace(old2, new2, 1), encoding="utf-8")
print("gen_strategy OK")
