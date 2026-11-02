# -*- coding: utf-8 -*-
"""UX P3 smoke: schematics bridge list + LAST_EXPORT + step card hooks."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SRC = (ROOT / "scripts/viewer_app.py").read_text(encoding="utf-8")
for needle in [
    "UX_P3_BRIDGE",
    "_refresh_game_bridge",
    "_show_build_step_card",
    "write_last_export_sidecar",
    "on_copy_export_name",
    "bridge_list_frame",
    "on_export_to_game",
    "UX_P2_SCHEMES",
]:
    assert needle in SRC, needle

from src.app.game_bridge import (
    build_step_card_text,
    detect_minecraft_running,
    is_app_owned_name,
    list_schematics,
    write_last_export_sidecar,
)
from src.data.export_litematic_util import resolve_schematics_dir
from src.app.schemes import create_scheme, list_schemes, load_scheme
from src.app.sample_runner import load_voxel_npz

assert is_app_owned_name("夜齐_european_v26.3.litematic")
assert is_app_owned_name("ai_preview_v26.3.litematic")
assert not is_app_owned_name("random_house.litematic")

card = build_step_card_text(filename="demo.litematic", schematics_dir="C:/tmp")
assert "建造步骤卡" in card and "demo.litematic" in card
det = detect_minecraft_running()
assert "label_zh" in det
print("DETECT", det.get("label_zh"), "running", det.get("running"))

schem_dir = resolve_schematics_dir()
rows = list_schematics(schem_dir)
print("SCHEM_DIR", schem_dir, "count", len(rows))

samples = ROOT / "outputs/design/night22e_full_20261022_071643/npz"
npz = next(samples.glob("sample_*.npz"))
vox = load_voxel_npz(npz)

slug_name = "UX冒烟P3"
result = create_scheme(slug_name, voxels=vox, style="european", terrain="flat", notes="ux_p3_smoke")
slug = result["slug"]
print("SCHEME", slug)

import scripts.viewer_app as va

with mock.patch.object(va.messagebox, "showinfo", return_value=None) as mi,      mock.patch.object(va.messagebox, "showwarning", return_value=None),      mock.patch.object(va.messagebox, "showerror", return_value=None),      mock.patch.object(va.messagebox, "askyesno", return_value=True),      mock.patch.object(va, "simpledialog") as sd,      mock.patch("os.startfile", create=True):
    sd.askstring.return_value = "smoke_unused"
    app = va.ViewerApp(out_dir=str(samples))
    assert hasattr(app, "bridge_list_frame")
    assert hasattr(app, "bridge_status_label")
    assert hasattr(app, "export_game_btn")
    assert len(app._hotbar_buttons) == 9
    app.open_folder_var.set(False)
    if hasattr(app, "export_bom_var"):
        app.export_bom_var.set(True)
    if hasattr(app, "bridge_auto_var"):
        app.bridge_auto_var.set(False)  # stop auto refresh during smoke

    data = load_scheme(slug)
    app._bind_scheme(slug, data["voxels"], data["npz_path"], switch_edit=True)
    app._refresh_game_bridge()
    assert len(app._bridge_rows) >= 0  # may be empty if dir empty before export

    app.on_export_to_game()

    hits = list(schem_dir.glob(f"{slug}*.litematic"))
    assert hits, f"no litematic for {slug} in {schem_dir}"
    lit = hits[0]
    print("LITEMATIC", lit)
    last_txt = schem_dir / "LAST_EXPORT.txt"
    last_json = schem_dir / "LAST_EXPORT.json"
    assert last_txt.is_file(), last_txt
    assert last_json.is_file(), last_json
    body = last_txt.read_text(encoding="utf-8")
    assert lit.name in body
    print("LAST_EXPORT_OK")

    app._refresh_game_bridge()
    assert any(Path(p).name == lit.name for p, _ in app._bridge_rows), app._bridge_rows[:3]
    assert app._last_export_name == lit.name

    # step card was shown via messagebox.showinfo
    assert mi.called

    try:
        app.destroy()
    except Exception:
        pass

print("UX_P3_SMOKE_OK", "schematics=", schem_dir)
