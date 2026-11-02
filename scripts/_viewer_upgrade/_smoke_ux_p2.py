# -*- coding: utf-8 -*-
"""UX P2 smoke: schemes panel + one-click export to PCL schematics."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SRC = (ROOT / "scripts/viewer_app.py").read_text(encoding="utf-8")
for needle in [
    "UX_P2_SCHEMES",
    "on_export_to_game",
    "on_scheme_new",
    "on_scheme_import_npz",
    "_refresh_scheme_list",
    "scheme_list_frame",
    "进游戏（导出 PCL）",
]:
    assert needle in SRC, needle

from src.app.schemes import create_scheme, list_schemes, load_scheme, schemes_root
from src.app.sample_runner import load_voxel_npz
from src.data.export_litematic_util import resolve_schematics_dir
from src.app.materials_bom import write_export_sidecars

samples = ROOT / "outputs/design/night22e_full_20261022_071643/npz"
npz = next(samples.glob("sample_*.npz"))
vox = load_voxel_npz(npz)

slug_name = "UX冒烟P2"
# clean prior smoke scheme if any
existing = [r for r in list_schemes() if r.get("name") == slug_name or "ux冒烟p2" in str(r.get("slug", "")).lower()]
# create fresh
result = create_scheme(slug_name, voxels=vox, style="european", terrain="flat", notes="ux_p2_smoke")
slug = result["slug"]
print("SCHEME_CREATED", slug, "non_air", result["non_air"])

import scripts.viewer_app as va

# Avoid blocking dialogs / opening explorer during smoke
with mock.patch.object(va.messagebox, "showinfo", return_value=None), \
     mock.patch.object(va.messagebox, "showwarning", return_value=None), \
     mock.patch.object(va.messagebox, "showerror", return_value=None), \
     mock.patch.object(va.messagebox, "askyesno", return_value=True), \
     mock.patch.object(va, "simpledialog") as sd, \
     mock.patch("os.startfile", create=True):
    sd.askstring.return_value = "smoke_unused"
    app = va.ViewerApp(out_dir=str(samples))
    assert hasattr(app, "scheme_list_frame")
    assert hasattr(app, "export_game_btn")
    assert hasattr(app, "open_folder_var")
    assert len(app._hotbar_buttons) == 9  # P0/P1 intact
    app.open_folder_var.set(False)  # don't open explorer
    # ensure BOM on
    if hasattr(app, "export_bom_var"):
        app.export_bom_var.set(True)

    data = load_scheme(slug)
    app._bind_scheme(slug, data["voxels"], data["npz_path"], switch_edit=True)
    assert app._scheme_slug == slug
    assert app._mode == va.MODE_EDIT
    app._refresh_scheme_list()
    assert len(app._scheme_list_rows) >= 1

    app.on_export_to_game()

    schem_dir = resolve_schematics_dir()
    # exported name uses slug + version tag
    hits = list(schem_dir.glob(f"{slug}*.litematic"))
    assert hits, f"no litematic for {slug} in {schem_dir}"
    lit = hits[0]
    print("LITEMATIC", lit)
    mat_dir = schem_dir / "materials" / lit.stem
    bom_md = mat_dir / f"{lit.stem}_BOM.md"
    assert mat_dir.is_dir(), mat_dir
    assert bom_md.is_file() or any(mat_dir.glob("*BOM*")), list(mat_dir.iterdir())
    print("BOM_DIR", mat_dir)

    try:
        app.destroy()
    except Exception:
        pass

print("UX_P2_SMOKE_OK", "schematics=", schem_dir)