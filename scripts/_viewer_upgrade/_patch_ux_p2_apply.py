from pathlib import Path
ROOT = Path(r"E:\ai agent\mc-architecture-ai")
SRC = ROOT / "scripts" / "viewer_app.py"
text = SRC.read_text(encoding="utf-8")
orig = text
MARKER = "UX_P2_SCHEMES"
assert MARKER not in text

old = """        self._toast_job = None
        self._press_button: int | None = None

        self._build_ui()
        self.refresh_lists()
        self._refresh_target_choices()"""
new = """        self._toast_job = None
        self._press_button: int | None = None
        # UX P2: schemes list + export-to-game
        self._scheme_list_rows: list = []

        self._build_ui()
        self.refresh_lists()
        self._refresh_target_choices()
        try:
            self._refresh_scheme_list()
        except Exception:
            pass"""
assert old in text, "init block missing"
text = text.replace(old, new, 1)

needle = "    def _build_generate_panel(self, parent: ctk.CTkFrame) -> None:"
idx = text.find(needle)
assert idx > 0
block = """
        # ---- UX P2: schemes project list (browse) ----
        ctk.CTkLabel(parent, text=\"方案（项目）\", font=ctk.CTkFont(weight=\"bold\")).grid(
            row=11, column=0, sticky=\"w\", padx=4, pady=(10, 2)
        )
        self.scheme_list_frame = ctk.CTkScrollableFrame(parent, height=120)
        self.scheme_list_frame.grid(row=12, column=0, sticky=\"nsew\", padx=4, pady=2)
        parent.grid_rowconfigure(12, weight=1)

        sch_btns = ctk.CTkFrame(parent, fg_color=\"transparent\")
        sch_btns.grid(row=13, column=0, sticky=\"ew\", padx=4, pady=(4, 2))
        ctk.CTkButton(sch_btns, text=\"新建\", width=60, height=28, command=self.on_scheme_new).pack(
            side=\"left\", padx=1
        )
        ctk.CTkButton(sch_btns, text=\"打开\", width=60, height=28, command=self.on_scheme_open).pack(
            side=\"left\", padx=1
        )
        ctk.CTkButton(sch_btns, text=\"另存\", width=60, height=28, command=self.on_scheme_save_as).pack(
            side=\"left\", padx=1
        )
        ctk.CTkButton(sch_btns, text=\"保存\", width=60, height=28, command=self.on_scheme_save).pack(
            side=\"left\", padx=1
        )

        sch_btns2 = ctk.CTkFrame(parent, fg_color=\"transparent\")
        sch_btns2.grid(row=14, column=0, sticky=\"ew\", padx=4, pady=(2, 2))
        ctk.CTkButton(
            sch_btns2, text=\"导入投影\", width=90, height=28, command=self.on_scheme_import_litematic
        ).pack(side=\"left\", padx=1)
        ctk.CTkButton(
            sch_btns2, text=\"导入npz\", width=90, height=28, command=self.on_scheme_import_npz
        ).pack(side=\"left\", padx=1)
        ctk.CTkButton(
            sch_btns2, text=\"刷新\", width=60, height=28, command=self._refresh_scheme_list
        ).pack(side=\"right\", padx=1)

        self.open_folder_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            parent,
            text=\"导出后打开文件夹\",
            variable=self.open_folder_var,
            width=180,
        ).grid(row=15, column=0, sticky=\"w\", padx=4, pady=(4, 2))

        self.export_game_btn = ctk.CTkButton(
            parent,
            text=\"进游戏（导出 PCL）\",
            command=self.on_export_to_game,
            height=36,
            font=ctk.CTkFont(size=14, weight=\"bold\"),
            fg_color=(\"#1b7f4a\", \"#1b7f4a\"),
            hover_color=(\"#146038\", \"#146038\"),
        )
        self.export_game_btn.grid(row=16, column=0, sticky=\"ew\", padx=4, pady=(4, 10))
        # UX_P2_SCHEMES

"""
text = text[:idx] + block + text[idx:]

key = "command=self.on_export_litematic,"
kidx = text.find(key)
assert kidx > 0, "export cmd missing"
start = text.rfind("export_row = ctk.CTkFrame", 0, kidx)
end = text.find('self.export_btn.pack(side="left")', kidx)
assert start > 0 and end > 0
end = text.find("\n", end) + 1
new_export = """        if not hasattr(self, \"open_folder_var\"):
            self.open_folder_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            right,
            text=\"导出后打开文件夹\",
            variable=self.open_folder_var,
            width=200,
        ).grid(row=23, column=0, sticky=\"w\", padx=14, pady=(6, 0))

        export_row = ctk.CTkFrame(right, fg_color=\"transparent\")
        export_row.grid(row=24, column=0, sticky=\"ew\", padx=10, pady=(6, 6))
        self.export_btn = ctk.CTkButton(
            export_row,
            text=\"进游戏（导出 PCL）\",
            command=self.on_export_to_game,
            width=200,
            height=34,
            font=ctk.CTkFont(weight=\"bold\"),
            fg_color=(\"#1b7f4a\", \"#1b7f4a\"),
            hover_color=(\"#146038\", \"#146038\"),
        )
        self.export_btn.pack(side=\"left\")
        # UX_P2_SCHEMES edit-panel
"""
text = text[:start] + new_export + text[end:]

for a, b in [
    ("self.scheme_label.grid(row=25,", "self.scheme_label.grid(row=26,"),
    ("scheme_row1.grid(row=26,", "scheme_row1.grid(row=27,"),
    ("scheme_row2.grid(row=27,", "scheme_row2.grid(row=28,"),
    ("scheme_row3.grid(row=28,", "scheme_row3.grid(row=29,"),
]:
    assert a in text, a
    text = text.replace(a, b, 1)

sl = text.find("self.scheme_label = ctk.CTkLabel")
chunk_start = max(0, sl - 350)
chunk = text[chunk_start:sl]
last = chunk.rfind("row=24")
assert last >= 0, "scheme header row=24 missing"
abs_i = chunk_start + last
text = text[:abs_i] + "row=25" + text[abs_i + len("row=24") :]

methods_path = ROOT / "scripts" / "_viewer_upgrade" / "_ux_p2_methods.pyfrag"
methods = methods_path.read_text(encoding="utf-8")
anchor = "    def _bind_canvas_interactions(self) -> None:"
assert anchor in text
assert "def on_export_to_game" not in text
text = text.replace(anchor, methods + "\n" + anchor, 1)

bind_idx = text.find("    def _bind_scheme(self, slug: str, voxels, npz_path: Path) -> None:")
assert bind_idx > 0
next_def = text.find("\n    def ", bind_idx + 10)
new_fn = """    def _bind_scheme(
        self, slug: str, voxels, npz_path: Path, *, switch_edit: bool = False
    ) -> None:
        self._scheme_slug = slug
        self.current_voxels = voxels
        self.current_path = Path(npz_path)
        self._undo_stack.clear()
        self._dirty = False
        if hasattr(self, \"undo_btn\"):
            self._refresh_undo_redo_buttons()
        self._refresh_scheme_label()
        self._update_info_panel()
        self._rebuild_block_list()
        self.render_voxels(voxels)
        non_air = int((voxels > 0).sum())
        self._set_status(f\"已打开方案 {slug}，non_air={non_air}。\")
        try:
            self._refresh_scheme_list()
        except Exception:
            pass
        if switch_edit:
            self._switch_mode(MODE_EDIT)
"""
text = text[:bind_idx] + new_fn + text[next_def:]

pat = 'self._bind_scheme(slug, data["voxels"], data["npz_path"])'
print("bind_scheme(slug,data) count", text.count(pat))
text = text.replace(
    pat,
    'self._bind_scheme(slug, data["voxels"], data["npz_path"], switch_edit=True)',
)

pat2 = 'self._bind_scheme(slug, self.current_voxels, result["dir"] / "current.npz")'
assert pat2 in text
text = text.replace(pat2, pat2 + "\n        self._refresh_scheme_list()", 1)

assert MARKER in text
assert "def on_export_to_game" in text
assert "def on_scheme_new" in text
assert "scheme_list_frame" in text
assert "command=self.on_export_litematic," not in text
assert "def on_export_litematic" in text

SRC.write_text(text, encoding="utf-8")
print("WROTE", SRC, "delta", len(text) - len(orig))
