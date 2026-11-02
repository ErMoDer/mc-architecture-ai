from pathlib import Path
PATH = Path("src/app/look_harden.py")
text = PATH.read_text(encoding="utf-8")

# 1) Add _facade_face_cells after _bbox_faces
old_bb = '''def _bbox_faces(peri: np.ndarray) -> dict[str, list[tuple[int, int]]]:
'''
# find full function to insert after — read it
start = text.find("def _bbox_faces(peri: np.ndarray)")
if start < 0:
    raise SystemExit("bbox missing")
# find next def after bbox
next_def = text.find("\ndef ", start + 1)
bb = text[start:next_def]
print("bbox len", len(bb), "head", bb[:120].replace("\n"," "))

helper = '''
def _facade_face_cells(
    peri: np.ndarray,
    fp: np.ndarray | None = None,
) -> dict[str, list[tuple[int, int]]]:
    """Perimeter cells that face open air (real facade), not only bbox extremes.

    Organic / fantasy footprints often have almost no peri on the AABB faces;
    this keeps window rhythm working on irregular outlines.
    """
    if fp is None:
        return _bbox_faces(peri)
    faces: dict[str, list[tuple[int, int]]] = {"x0": [], "x1": [], "z0": [], "z1": []}
    sx, sz = peri.shape
    px, pz = np.where(peri)
    for x, z in zip(px.tolist(), pz.tolist()):
        if x <= 0 or not fp[x - 1, z]:
            faces["x0"].append((x, z))
        if x >= sx - 1 or not fp[x + 1, z]:
            faces["x1"].append((x, z))
        if z <= 0 or not fp[x, z - 1]:
            faces["z0"].append((x, z))
        if z >= sz - 1 or not fp[x, z + 1]:
            faces["z1"].append((x, z))
    # If a face is still tiny, fall back to bbox for that face only.
    bb = _bbox_faces(peri)
    for k, cells in list(faces.items()):
        if len(cells) < 3 and bb.get(k):
            faces[k] = bb[k]
    return faces

'''

if "_facade_face_cells" not in text:
    text = text[:next_def] + "\n" + helper + text[next_def:]
    print("inserted helper")
else:
    print("helper exists")

# 2) Update place_window_rhythm signature + faces source + action if sill
old_sig = '''def place_window_rhythm(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    y0: int,
    y1: int,
    floor_ys: list[int],
    glass_id: int,
    wall_id: int,
    spacing: int = 3,
    from_corner: int = 2,
    from_floor: int = 1,
    win_h: int = 2,
    win_w: int = 1,
    frame_id: int = 0,
    place_sill_header: bool = True,
    floor_spacing: int = 5,
    max_bands: int = 4,
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
'''
new_sig = '''def place_window_rhythm(
    voxels: np.ndarray,
    *,
    peri: np.ndarray,
    y0: int,
    y1: int,
    floor_ys: list[int],
    glass_id: int,
    wall_id: int,
    spacing: int = 3,
    from_corner: int = 2,
    from_floor: int = 1,
    win_h: int = 2,
    win_w: int = 1,
    frame_id: int = 0,
    place_sill_header: bool = True,
    floor_spacing: int = 5,
    max_bands: int = 4,
    fp: np.ndarray | None = None,
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
'''
if old_sig not in text:
    raise SystemExit("sig missing")
text = text.replace(old_sig, new_sig, 1)

text = text.replace(
    "    faces = _bbox_faces(peri)\n",
    "    faces = _facade_face_cells(peri, fp=fp)\n",
    1,
)

# relax min face length: fc*2+ww -> max(ww+2, fc+ww)
text = text.replace(
    "        if len(cells) < fc * 2 + ww:\n            continue\n",
    "        if len(cells) < max(ww + 2, fc + ww):\n            continue\n",
    1,
)

# also use smaller from_corner when face is short
# insert after usable = ...
old_use = '''        usable = cells_s[fc : max(fc, len(cells_s) - fc)]
        if not usable:
            continue
'''
new_use = '''        face_fc = fc if len(cells_s) >= fc * 2 + ww + 1 else max(1, min(fc, 1))
        usable = cells_s[face_fc : max(face_fc, len(cells_s) - face_fc)]
        if not usable:
            continue
'''
if old_use not in text:
    raise SystemExit("usable block missing")
text = text.replace(old_use, new_use, 1)

text = text.replace(
    "    if placed:\n        actions.append(\n            \"window_rhythm:cells=%d cols=%d sp=%d bands=%d sill=%d\"\n            % (placed, cols, sp, len(bands), sill_n)\n        )\n",
    "    if placed or sill_n:\n        actions.append(\n            \"window_rhythm:cells=%d cols=%d sp=%d bands=%d sill=%d\"\n            % (placed, cols, sp, len(bands), sill_n)\n        )\n",
    1,
)

# 3) pass fp= from harden_facade call
old_call = '''        out, act, wr = place_window_rhythm(
            out,
            peri=peri,
            y0=y0,
            y1=y1,
            floor_ys=peaks,
            glass_id=int(gid),
            wall_id=int(wall_id),
            spacing=int(rules.get("window_spacing", 3)),
            from_corner=int(rules.get("window_from_corner", 2)),
            from_floor=int(rules.get("window_from_floor", 1)),
            win_h=wh,
            win_w=ww,
            frame_id=int(frame_for_win),
            place_sill_header=bool(rules.get("place_sill_header", True)),
            floor_spacing=int(rules.get("floor_spacing", 5)),
            max_bands=int(rules.get("max_window_bands", 4)),
        )
'''
new_call = '''        out, act, wr = place_window_rhythm(
            out,
            peri=peri,
            y0=y0,
            y1=y1,
            floor_ys=peaks,
            glass_id=int(gid),
            wall_id=int(wall_id),
            spacing=int(rules.get("window_spacing", 3)),
            from_corner=int(rules.get("window_from_corner", 2)),
            from_floor=int(rules.get("window_from_floor", 1)),
            win_h=wh,
            win_w=ww,
            frame_id=int(frame_for_win),
            place_sill_header=bool(rules.get("place_sill_header", True)),
            floor_spacing=int(rules.get("floor_spacing", 5)),
            max_bands=int(rules.get("max_window_bands", 4)),
            fp=fp,
        )
'''
if old_call not in text:
    raise SystemExit("harden call missing")
text = text.replace(old_call, new_call, 1)

PATH.write_text(text, encoding="utf-8")
import ast
ast.parse(text)
print("patched facade faces ok")
