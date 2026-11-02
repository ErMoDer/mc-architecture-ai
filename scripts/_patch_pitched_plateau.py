from pathlib import Path
p = Path("src/app/look_harden.py")
t = p.read_text(encoding="utf-8")
old = '''    placed = 0
    stair_n = 0
    ridge_z = (minz + maxz) / 2.0
    ridge_x = (minx + maxx) / 2.0
    for x, z in zip(ax.tolist(), az.tolist()):
        if ridge_along_x:
            dist = abs(float(z) - ridge_z)
        else:
            dist = abs(float(x) - ridge_x)
        # height: peak at ridge, down 1 per step
        h = int(round(peak_y - dist))
        h = max(eave_y, min(peak_y, h))
        # solid fill from eave_y to h
        for y in range(eave_y, h + 1):
'''
new = '''    placed = 0
    stair_n = 0
    ridge_z = (minz + maxz) / 2.0
    ridge_x = (minx + maxx) / 2.0
    # Broad ridge plateau so top_footprint_cover / roof_score are not needle-thin
    plateau = max(1, int(0.32 * max(1, half)))
    for x, z in zip(ax.tolist(), az.tolist()):
        if ridge_along_x:
            dist = abs(float(z) - ridge_z)
        else:
            dist = abs(float(x) - ridge_x)
        if dist <= plateau:
            h = int(peak_y)
        else:
            # height falls from plateau edge to eave
            span = max(1e-6, float(half - plateau))
            tnorm = min(1.0, (dist - plateau) / span)
            h = int(round(peak_y - tnorm * (peak_y - eave_y)))
        h = max(eave_y, min(peak_y, h))
        # solid fill from eave_y to h
        for y in range(eave_y, h + 1):
'''
if old not in t:
    raise SystemExit("pitched loop missing")
t = t.replace(old, new, 1)
# Also ensure eave-level lid on all active columns (attic floor) for continuity — already filled by range from eave_y
p.write_text(t, encoding="utf-8")
import ast
ast.parse(p.read_text(encoding="utf-8"))
print("look_harden pitched plateau ok")
