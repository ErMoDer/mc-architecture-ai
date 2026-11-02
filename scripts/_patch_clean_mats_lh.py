# -*- coding: utf-8 -*-
from pathlib import Path

LH = Path("src/app/look_harden.py")
text = LH.read_text(encoding="utf-8")

CLEAN_FN = '''
def despeckle_solids(
    voxels: np.ndarray,
    *,
    min_neighbors: int = 2,
    protected_ids: set[int] | None = None,
) -> tuple[np.ndarray, int]:
    """Remove solid cells with fewer than min_neighbors solid 6-neighbors (speckles)."""
    out = np.asarray(voxels, dtype=np.int16).copy()
    prot = set(int(x) for x in (protected_ids or set()) if int(x) > 0)
    solid = out > 0
    if not solid.any():
        return out, 0
    nb = np.zeros(out.shape, dtype=np.int16)
    nb[1:, :, :] += solid[:-1, :, :]
    nb[:-1, :, :] += solid[1:, :, :]
    nb[:, 1:, :] += solid[:, :-1, :]
    nb[:, :-1, :] += solid[:, 1:, :]
    nb[:, :, 1:] += solid[:, :, :-1]
    nb[:, :, :-1] += solid[:, :, 1:]
    drop = solid & (nb < int(min_neighbors))
    if prot:
        for pid in prot:
            drop &= out != int(pid)
    if _PALETTE_REF is not None:
        for bid in np.unique(out[drop]):
            bid = int(bid)
            if bid <= 0:
                continue
            sn = _short(_PALETTE_REF.get(bid, ""))
            if sn.endswith("_door") or sn == "door" or "glass" in sn:
                drop &= out != bid
    n = int(drop.sum())
    if n:
        out[drop] = 0
    return out, n


def unify_role_surfaces(
    voxels: np.ndarray,
    palette: dict[int, str],
    *,
    wall_id: int,
    floor_id: int,
    roof_id: int,
    foundation_id: int,
    accent_id: int,
    load_bearing_id: int = 0,
    floor_ys: list[int] | None = None,
    max_accent_frac: float = 0.12,
) -> tuple[np.ndarray, list[str]]:
    """Force one wall / roof / floor mat; keep glass/door/stairs; cap accent spam."""
    out = np.asarray(voxels, dtype=np.int16).copy()
    actions: list[str] = []
    solid = out > 0
    if not solid.any():
        return out, ["unify_skip_empty"]

    sx, sy, sz = out.shape
    wall_id = int(wall_id)
    floor_id = int(floor_id) or wall_id
    roof_id = int(roof_id) or wall_id
    foundation_id = int(foundation_id) or wall_id
    accent_id = int(accent_id) or wall_id
    load_bearing_id = int(load_bearing_id) or accent_id

    glass_ids = _glass_ids_from_palette(palette)
    door_ids: set[int] = set()
    stair_ids: set[int] = set()
    for i, name in palette.items():
        sn = _short(name).lower()
        if int(i) <= 0:
            continue
        if sn.endswith("_door") or sn == "door":
            door_ids.add(int(i))
        if "stair" in sn:
            stair_ids.add(int(i))

    keep_special = set(glass_ids) | door_ids | stair_ids
    keep_special |= {wall_id, floor_id, roof_id, foundation_id, accent_id, load_bearing_id}
    keep_special.discard(0)

    fp, _ = _footprint(solid)
    peri = _perimeter_mask(fp)
    ys = np.where(solid.any(axis=(0, 2)))[0]
    y0, y1 = int(ys.min()), int(ys.max())

    xs_fp, zs_fp = np.where(fp)
    if xs_fp.size:
        minx, maxx = int(xs_fp.min()), int(xs_fp.max())
        minz, maxz = int(zs_fp.min()), int(zs_fp.max())
        corners = {(minx, minz), (minx, maxz), (maxx, minz), (maxx, maxz)}
    else:
        corners = set()

    remapped = 0
    accent_cleared = 0
    for bid in np.unique(out[out > 0]).tolist():
        bid = int(bid)
        if bid in keep_special:
            continue
        sn = _short(palette.get(bid, "")).lower()
        if sn.endswith("_door") or "glass" in sn or "stair" in sn:
            continue
        mask = out == bid
        n = int(mask.sum())
        if n:
            out[mask] = wall_id
            remapped += n
    if remapped:
        actions.append("unify_remap_to_wall:%d" % remapped)

    n_found = 0
    xs, zs = np.where(fp)
    for x, z in zip(xs.tolist(), zs.tolist()):
        cur = int(out[x, y0, z])
        if cur > 0 and cur not in glass_ids and cur not in door_ids:
            if cur != foundation_id:
                out[x, y0, z] = foundation_id
                n_found += 1
    if n_found:
        actions.append("unify_foundation:%d" % n_found)

    peaks = [int(y) for y in (floor_ys or []) if y0 < int(y) < y1]
    if not peaks:
        floors = _floor_metrics(out > 0)
        peaks = [int(y) for y in (floors.get("y_peaks") or []) if y0 < int(y) < y1]
    n_floor = 0
    for y in peaks:
        for x, z in zip(xs.tolist(), zs.tolist()):
            if not fp[x, z]:
                continue
            cur = int(out[x, y, z])
            if cur <= 0:
                continue
            if cur in glass_ids or cur in door_ids:
                continue
            if peri[x, z]:
                continue
            if cur != floor_id:
                out[x, y, z] = floor_id
                n_floor += 1
    if n_floor:
        actions.append("unify_floors:%d" % n_floor)

    n_roof = 0
    for x, z in zip(xs.tolist(), zs.tolist()):
        col = out[x, :, z]
        ys_col = np.where(col > 0)[0]
        if ys_col.size == 0:
            continue
        yt = int(ys_col.max())
        cur = int(out[x, yt, z])
        if cur in glass_ids or cur in door_ids or cur in stair_ids:
            continue
        if cur != roof_id:
            out[x, yt, z] = roof_id
            n_roof += 1
    if n_roof:
        actions.append("unify_roof:%d" % n_roof)

    n_wall = 0
    accent_ids = {accent_id, load_bearing_id}
    for x, z in zip(xs.tolist(), zs.tolist()):
        if not peri[x, z]:
            continue
        is_corner = (x, z) in corners
        for y in range(y0 + 1, y1):
            cur = int(out[x, y, z])
            if cur <= 0:
                continue
            if cur in glass_ids or cur in door_ids or cur in stair_ids:
                continue
            if is_corner and cur in accent_ids:
                continue
            if cur == wall_id:
                continue
            out[x, y, z] = wall_id
            n_wall += 1
            if cur in accent_ids:
                accent_cleared += 1
    if n_wall:
        actions.append("unify_peri_wall:%d" % n_wall)

    solids_n = int((out > 0).sum())
    if solids_n > 0 and accent_id > 0 and accent_id != wall_id:
        acc_n = int((out == accent_id).sum())
        if load_bearing_id and load_bearing_id != wall_id and load_bearing_id != accent_id:
            acc_n += int((out == load_bearing_id).sum())
        frac = acc_n / float(solids_n)
        if frac > float(max_accent_frac):
            budget = int(float(max_accent_frac) * solids_n)
            extra = acc_n - budget
            cleared = 0
            for x in range(sx):
                for z in range(sz):
                    if cleared >= extra:
                        break
                    if (x, z) in corners:
                        continue
                    for y in range(sy):
                        if cleared >= extra:
                            break
                        cur = int(out[x, y, z])
                        if cur in accent_ids and cur != wall_id:
                            out[x, y, z] = wall_id
                            cleared += 1
                            accent_cleared += 1
            if cleared:
                actions.append(
                    "accent_cap:%d (frac %.3f->target %.3f)"
                    % (cleared, frac, max_accent_frac)
                )

    if accent_cleared and not any(a.startswith("accent_cap") for a in actions):
        actions.append("accent_cleared_peri:%d" % accent_cleared)

    solid2 = out > 0
    n_cc, sizes, labels = _connected_components(solid2)
    if n_cc > 1 and sizes:
        best_label = 1
        best_count = 0
        for lab in range(1, n_cc + 1):
            c = int((labels == lab).sum())
            if c > best_count:
                best_count = c
                best_label = lab
        drop = (labels > 0) & (labels != best_label)
        n_drop = int(drop.sum())
        if n_drop:
            out[drop] = 0
            actions.append("unify_drop_float_cc:%d" % n_drop)

    prot = set(door_ids) | set(glass_ids)
    out, n_sp = despeckle_solids(out, min_neighbors=2, protected_ids=prot)
    if n_sp:
        actions.append("despeckle:%d" % n_sp)

    return out, actions


'''

if "def unify_role_surfaces(" not in text:
    marker = "\ndef look_harden(\n"
    assert marker in text, "look_harden marker"
    text = text.replace(marker, "\n" + CLEAN_FN + marker, 1)
    print("inserted helpers")
else:
    print("helpers already present")

old_lim = """    out, pal_stats = limit_palette(
        vox0,
        palette,
        style=style,
        top_k=max(int(top_k), 6 if force_keep else int(top_k)),
        keep_trim_top=keep_trim_top,
        force_keep=force_keep,
    )"""
new_lim = """    # With role materials, keep palette tight (wall/roof/floor/accent + glass/door).
    _tk = 4 if force_keep else int(top_k)
    _kt = 1 if force_keep else int(keep_trim_top)
    out, pal_stats = limit_palette(
        vox0,
        palette,
        style=style,
        top_k=max(_tk, len(force_keep or [])),
        keep_trim_top=_kt,
        force_keep=force_keep,
    )"""
assert old_lim in text, "limit_palette miss"
text = text.replace(old_lim, new_lim, 1)
print("limit_palette ok")

anchor = """        pal_stats[\"shell_floors\"] = geo_extra

    after = check_structure(out)"""
insert = """        pal_stats[\"shell_floors\"] = geo_extra

    # --- clean material noise (one wall/roof/floor; despeckle; cap accent) ---
    if role_materials:
        fl_ys = []
        for a in actions:
            if \"flat_floors\" in a and \"@y=\" in a:
                try:
                    raw = a.split(\"@y=\", 1)[1].strip()
                    fl_ys = [int(x) for x in raw.strip(\"[]\").replace(\" \", \"\").split(\",\") if x]
                except Exception:
                    fl_ys = []
        out, clean_acts = unify_role_surfaces(
            out,
            palette,
            wall_id=int(wall_id),
            floor_id=int(floor_id),
            roof_id=int(roof_id),
            foundation_id=int(foundation_id),
            accent_id=int(load_bearing_id if load_bearing_id else accent_id),
            load_bearing_id=int(load_bearing_id),
            floor_ys=fl_ys or None,
            max_accent_frac=0.10,
        )
        actions.extend(clean_acts)
        if clean_acts:
            actions.append(\"clean_mats:on\")

    after = check_structure(out)"""
assert anchor in text, "wire anchor miss"
text = text.replace(anchor, insert, 1)
print("wire ok")

LH.write_text(text, encoding="utf-8")
print("look_harden done", LH.stat().st_size)