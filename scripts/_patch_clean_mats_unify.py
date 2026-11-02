from pathlib import Path
LH = Path("src/app/look_harden.py")
text = LH.read_text(encoding="utf-8")
# After resolving keep_special, if accent/load names look junk for style, treat as wall
# Simpler: in unify, after building keep_special, drop accent/load from keep if _is_junk or colored concrete noise
old = '''    keep_special = set(glass_ids) | door_ids | stair_ids
    keep_special |= {wall_id, floor_id, roof_id, foundation_id, accent_id, load_bearing_id}
    keep_special.discard(0)'''
new = '''    keep_special = set(glass_ids) | door_ids | stair_ids
    keep_special |= {wall_id, floor_id, roof_id, foundation_id}
    # Only keep accent/load_bearing if they look structural (not colored junk / bone / dirt)
    def _accent_ok(bid: int) -> bool:
        if bid <= 0 or bid == wall_id:
            return False
        sn = _short(palette.get(bid, "")).lower()
        if _is_junk(sn):
            return False
        bad = (
            "bone", "dirt", "moss", "hopper", "green_concrete", "lime_concrete",
            "yellow_concrete", "pink_concrete", "magenta_concrete", "purple_concrete",
            "blue_concrete", "cyan_concrete", "orange_concrete", "brown_concrete",
            "red_concrete", "acacia", "mangrove", "bamboo",
        )
        return not any(b in sn for b in bad)

    if _accent_ok(accent_id):
        keep_special.add(accent_id)
    if _accent_ok(load_bearing_id):
        keep_special.add(load_bearing_id)
    keep_special.discard(0)'''
assert old in text, "keep_special block missing"
text = text.replace(old, new, 1)
LH.write_text(text, encoding="utf-8")
print("unify accent_ok patched")
