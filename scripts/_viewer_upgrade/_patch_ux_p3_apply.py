# -*- coding: utf-8 -*-
"""Apply UX P3 bridge into viewer_app.py (run on LOCAL laptop)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
SRC = ROOT / "scripts" / "viewer_app.py"
FRAG_DIR = Path(__file__).resolve().parent
BRIDGE_DST = ROOT / "src" / "app" / "game_bridge.py"

src_bridge = FRAG_DIR / "game_bridge.py"
if src_bridge.is_file():
    BRIDGE_DST.write_text(src_bridge.read_text(encoding="utf-8"), encoding="utf-8")
    print("copied game_bridge.py ->", BRIDGE_DST)
assert BRIDGE_DST.is_file(), BRIDGE_DST

text = SRC.read_text(encoding="utf-8")
assert "UX_P3_BRIDGE" not in text, "P3 already applied"

old_imp = "from src.data.export_litematic_util import export_voxels_to_companion, resolve_schematics_dir"
new_imp = old_imp + """
from src.app.game_bridge import (
    build_step_card_text,
    copy_text_to_clipboard,
    detect_minecraft_running,
    list_schematics,
    open_in_explorer,
    write_last_export_sidecar,
)"""
assert old_imp in text, "import missing"
text = text.replace(old_imp, new_imp, 1)

old_init = """        # UX P2: schemes list + export-to-game
        self._scheme_list_rows: list = []

        self._build_ui()
        self.refresh_lists()
        self._refresh_target_choices()
        try:
            self._refresh_scheme_list()
        except Exception:
            pass"""
new_init = """        # UX P2: schemes list + export-to-game
        self._scheme_list_rows: list = []
        # UX P3: game bridge (schematics list / step card / MC detect)
        self._bridge_rows: list = []
        self._bridge_selected: str | None = None  # full path
        self._last_export_name: str | None = None
        self._bridge_auto_job = None
        self._bridge_auto_ms = 4000

        self._build_ui()
        self.refresh_lists()
        self._refresh_target_choices()
        try:
            self._refresh_scheme_list()
        except Exception:
            pass
        try:
            self._refresh_game_bridge()
            self._schedule_bridge_auto()
        except Exception:
            pass"""
assert old_init in text, "init block missing"
text = text.replace(old_init, new_init, 1)

marker = "        # UX_P2_SCHEMES" + chr(10)
assert marker in text, "UX_P2_SCHEMES marker missing"
bridge_ui = (FRAG_DIR / "bridge_ui.frag").read_text(encoding="utf-8")
text = text.replace(marker, bridge_ui, 1)

idx = text.find("def on_export_to_game(self) -> None:")
assert idx > 0
idx2 = text.find("def _bind_canvas_interactions(self) -> None:", idx)
assert idx2 > 0
block = text[idx:idx2]
needle = 'open_folder = bool(getattr(self, "open_folder_var", None) and self.open_folder_var.get())'
npos = block.rfind(needle)
assert npos > 0, "open_folder not found"
inject = """        # UX P3: sidecar + step card + clipboard + refresh list
        self._last_export_name = path.name
        self._bridge_selected = str(path)
        try:
            write_last_export_sidecar(
                Path(schematics_dir),
                litematic_path=path,
                slug=self._scheme_slug,
                extra={
                    "target_version": info.get("target_version"),
                    "bom": bom_info if isinstance(bom_info, dict) else {},
                },
            )
        except Exception as _sc_exc:  # noqa: BLE001
            self._set_status(f"已导出；LAST_EXPORT 写入失败：{_sc_exc}")
        try:
            copy_text_to_clipboard(path.name, root_widget=self)
        except Exception:
            pass
        try:
            self._refresh_game_bridge()
        except Exception:
            pass
        self._show_build_step_card(path.name, schematics_dir)

"""
new_block = block[:npos] + inject + block[npos:]
text = text[:idx] + new_block + text[idx2:]

methods = (FRAG_DIR / "bridge_methods.frag").read_text(encoding="utf-8")
if not methods.endswith(chr(10)):
    methods += chr(10)
anchor = "    def _bind_canvas_interactions(self) -> None:"
assert text.count(anchor) == 1
assert "def _refresh_game_bridge" not in text
text = text.replace(anchor, methods + chr(10) + anchor, 1)

SRC.write_text(text, encoding="utf-8")
print("PATCHED", SRC)
print("markers", "UX_P3_BRIDGE" in text, "write_last_export_sidecar" in text)
print("methods", "def _refresh_game_bridge" in text, "def _show_build_step_card" in text)
