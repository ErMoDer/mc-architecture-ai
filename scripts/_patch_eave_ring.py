# -*- coding: utf-8 -*-
from pathlib import Path
import ast

p = Path("src/app/gen_strategy.py")
t = p.read_text(encoding="utf-8")
old = """    # 1) eave deck
    for x, z in zip(xs.tolist(), zs.tolist()):
        out[x, eave_y, z] = int(roof_id)
        roof_count += 1
    # 2) clear old mass above eave on footprint, then place skin
"""
new = """    # 1) eave ring (not full attic slab — full deck inflated interior_cover)
    eave_ring = _dilate_mask(peri & roof_fp if peri.shape == roof_fp.shape else peri, 1) & roof_fp
    if int(eave_ring.sum()) < max(8, int(0.12 * int(roof_fp.sum()))):
        eave_ring = _dilate_mask(peri, 2) & roof_fp
    for x, z in zip(*np.where(eave_ring)):
        out[x, eave_y, z] = int(roof_id)
        roof_count += 1
    # 2) clear old mass above eave on footprint, then place skin
"""
if old not in t:
    raise SystemExit("eave deck block missing")
t = t.replace(old, new, 1)

# Also skip interior eave deck paint in look_harden skin path for non-peri
# Soften: in look_harden, only place eave_y roof on peri (not full active)
p2 = Path("src/app/look_harden.py")
t2 = p2.read_text(encoding="utf-8")
old2 = """        # Skin-only: eave deck + surface at h (+ underlay). No solid attic fill.
        if win_mask is not None and win_mask[x, eave_y, z]:
            pass
        elif not _cell_is_glass(int(out[x, eave_y, z])):
            out[x, eave_y, z] = int(roof_block)
            placed += 1
"""
new2 = """        # Skin-only: peri eave ring + surface at h (+ underlay). No solid attic fill/deck.
        if peri[x, z]:
            if win_mask is not None and win_mask[x, eave_y, z]:
                pass
            elif not _cell_is_glass(int(out[x, eave_y, z])):
                out[x, eave_y, z] = int(roof_block)
                placed += 1
"""
if old2 not in t2:
    raise SystemExit("look_harden eave skin missing")
t2 = t2.replace(old2, new2, 1)

# For medieval/fantasy: skip partitions if footprint already dense (avoid extra mass); actually partitions don't affect floor cover. Instead after floors force more open for med/fan.
old3 = """            if style_l in (\"medieval\", \"fantasy\"):
                depth = 1
            else:
                depth = 2 if y == y_foundation else 1
            use_fp = _ring_floor_mask(use_fp, depth=depth, keep_cross=False)
            out[:, y, :][use_fp] = int(floor_id)
            out[:, y, :][peri] = peri_block
            stats[\"floors\"] += int(use_fp.sum())
            stats[\"floor_mode\"] = \"ring\"
"""
new3 = """            if style_l in (\"medieval\", \"fantasy\"):
                depth = 1
            else:
                depth = 2 if y == y_foundation else 1
            use_fp = _ring_floor_mask(use_fp, depth=depth, keep_cross=False)
            # Extra carve for dense refs: keep only peri-adjacent walk band
            if style_l in (\"medieval\", \"fantasy\") and use_fp.any():
                keep = _dilate_mask(peri, 1) & use_fp
                if int(keep.sum()) >= max(12, int(0.15 * int(build_fp.sum()))):
                    use_fp = keep
            out[:, y, :][use_fp] = int(floor_id)
            out[:, y, :][peri] = peri_block
            stats[\"floors\"] += int(use_fp.sum())
            stats[\"floor_mode\"] = \"ring\"
"""
if old3 not in t:
    raise SystemExit("floor paint block missing")
t = t.replace(old3, new3, 1)

p.write_text(t, encoding="utf-8")
p2.write_text(t2, encoding="utf-8")
ast.parse(t)
ast.parse(t2)
print("patched eave ring + med floors")
