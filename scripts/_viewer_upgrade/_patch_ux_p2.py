# -*- coding: utf-8 -*-
"""Patch viewer_app.py for UX P2: schemes panel + one-click 进游戏."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
SRC = ROOT / "scripts" / "viewer_app.py"
text = SRC.read_text(encoding="utf-8")
orig = text

MARKER = "UX_P2_SCHEMES"
if MARKER in text:
    print("Already patched?")
    raise SystemExit(0)

# --- 1) Init: open-folder preference + scheme list widgets ---
old_init = """        self._toast_job = None
        self._press_button: int | None = None

        self._build_ui()"""
new_init = """        self._toast_job = None
        self._press_button: int | None = None
        # UX P2: schemes list + 进游戏
        self._scheme_list_rows: list = []
        self._open_folder_after_export = True  # default; mirrored by checkbox when built

        self._build_ui()"""
if old_init not in text:
    raise SystemExit("init anchor missing")
text = text.replace(old_init, new_init, 1)

# --- 2) Append schemes strip to browse panel (before _build_generate_panel) ---
old_browse_end = """        ctk.CTkLabel(
            parent,
            text="默认打开最新 design 批次，可上方目录切换",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=12),
        ).grid(row=9, column=0, sticky="w", padx=4, pady=(4, 8))

    def _build_generate_panel(self, parent: ctk.CTkFrame) -> None:"""

# Note: the garbled encoding in shell view might mean the file is UTF-8 Chinese.
# Search by unique English-ish parts instead.
needle_browse = 'def _build_generate_panel(self, parent: ctk.CTkFrame) -> None:'
idx = text.find(needle_browse)
if idx < 0:
    raise SystemExit("browse end / generate panel missing")

# Find the last grid before _build_generate_panel belonging to browse
# Insert schemes block just before _build_generate_panel
schemes_browse_block = '''
        # ---- UX P2: 方案列表（浏览侧项目感）----
        ctk.CTkLabel(parent, text="方案（项目）", font=ctk.CTkFont(weight="bold")).grid(
            row=11, column=0, sticky="w", padx=4, pady=(10, 2)
        )
        self.scheme_list_frame = ctk.CTkScrollableFrame(parent, height=120)
        self.scheme_list_frame.grid(row=12, column=0, sticky="nsew", padx=4, pady=2)
        parent.grid_rowconfigure(12, weight=1)

        sch_btns = ctk.CTkFrame(parent, fg_color="transparent")
        sch_btns.grid(row=13, column=0, sticky="ew", padx=4, pady=(4, 2))
        ctk.CTkButton(sch_btns, text="新建", width=60, height=28, command=self.on_scheme_new).pack(
            side="left", padx=1
        )
        ctk.CTkButton(sch_btns, text="打开", width=60, height=28, command=self.on_scheme_open).pack(
            side="left", padx=1
        )
        ctk.CTkButton(sch_btns, text="另存", width=60, height=28, command=self.on_scheme_save_as).pack(
            side="left", padx=1
        )
        ctk.CTkButton(sch_btns, text="保存", width=60, height=28, command=self.on_scheme_save).pack(
            side="left", padx=1
        )

        sch_btns2 = ctk.CTkFrame(parent, fg_color="transparent")
        sch_btns2.grid(row=14, column=0, sticky="ew", padx=4, pady=(2, 2))
        ctk.CTkButton(
            sch_btns2, text="导入投影", width=90, height=28, command=self.on_scheme_import_litematic
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            sch_btns2, text="导入npz", width=90, height=28, command=self.on_scheme_import_npz
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            sch_btns2, text="刷新", width=60, height=28, command=self._refresh_scheme_list
        ).pack(side="right", padx=1)

        self.open_folder_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            parent,
            text="导出后打开文件夹",
            variable=self.open_folder_var,
            width=180,
        ).grid(row=15, column=0, sticky="w", padx=4, pady=(4, 2))

        self.export_game_btn = ctk.CTkButton(
            parent,
            text="进游戏（导出 PCL）",
            command=self.on_export_to_game,
            height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#1b7f4a", "#1b7f4a"),
            hover_color=("#146038", "#146038"),
        )
        self.export_game_btn.grid(row=16, column=0, sticky="ew", padx=4, pady=(4, 10))
        # UX_P2_SCHEMES marker for smoke

    def _build_generate_panel(self, parent: ctk.CTkFrame) -> None:'''

text = text[:idx] + schemes_browse_block + text[idx + len(needle_browse):]
# Wait - that duplicates the def line incorrectly. Fix: replace including the def line.
text = SRC.read_text(encoding="utf-8")  # reset? No we already changed init.
# Re-read carefully - we already applied init. Reload from disk? Better rebuild from orig+init.

text = orig.replace(old_init, new_init, 1)
idx = text.find(needle_browse)
if idx < 0:
    raise SystemExit("generate panel still missing after init")
text = text[:idx] + schemes_browse_block + "\n" + text[idx:]

# --- 3) Edit-right: boost 进游戏 button + open-folder checkbox near export ---
# Replace export button text and add open folder + 进游戏 alias
old_export = '''        export_row = ctk.CTkFrame(right, fg_color="transparent")
        export_row.grid(row=23, column=0, sticky="ew", padx=10, pady=(8, 14))
        self.export_btn = ctk.CTkButton(
            export_row,
            text="导出到 companion",
            command=self.on_export_litematic,
            width=200,
            fg_color=("#2d6a4f", "#2d6a4f"),
        )
        self.export_btn.pack(side="left")'''

new_export = '''        if not hasattr(self, "open_folder_var"):
            self.open_folder_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            right,
            text="导出后打开文件夹",
            variable=self.open_folder_var,
            width=200,
        ).grid(row=23, column=0, sticky="w", padx=14, pady=(6, 0))

        export_row = ctk.CTkFrame(right, fg_color="transparent")
        export_row.grid(row=24, column=0, sticky="ew", padx=10, pady=(6, 6))
        self.export_btn = ctk.CTkButton(
            export_row,
            text="进游戏（导出 PCL）",
            command=self.on_export_to_game,
            width=200,
            height=34,
            font=ctk.CTkFont(weight="bold"),
            fg_color=("#1b7f4a", "#1b7f4a"),
            hover_color=("#146038", "#146038"),
        )
        self.export_btn.pack(side="left")
        # UX_P2_SCHEMES edit-panel'''

# Chinese text may already be in file - try both encodings / search flexibly
if old_export in text:
    text = text.replace(old_export, new_export, 1)
else:
    # Find by command=self.on_export_litematic in export_btn context
    key = "command=self.on_export_litematic,"
    kidx = text.find(key)
    if kidx < 0:
        raise SystemExit("export_btn anchor missing")
    # Find start of export_row = 
    start = text.rfind("export_row = ctk.CTkFrame", 0, kidx)
    end = text.find("self.export_btn.pack(side=\"left\")", kidx)
    if start < 0 or end < 0:
        raise SystemExit(f"export_row bounds missing {start} {end}")
    end = text.find("\n", end) + 1
    text = text[:start] + new_export + "\n" + text[end:]
    print("export block replaced via flexible match")

# Scheme section rows shifted because we inserted row 23 checkbox and moved export to 24
# Need to shift scheme label from 24->25 etc. Only if old numbers still present.
# After our replace, old scheme section still at 24+ which now conflicts.
# Fix: relocate scheme section row numbers 24..28 -> 25..29

repls = [
    ('ctk.CTkLabel(right, text="设计方案", font=ctk.CTkFont(weight="bold")).grid(\n            row=24,',
     'ctk.CTkLabel(right, text="设计方案", font=ctk.CTkFont(weight="bold")).grid(\n            row=25,'),
    ("self.scheme_label.grid(row=25,", "self.scheme_label.grid(row=26,"),
    ("scheme_row1.grid(row=26,", "scheme_row1.grid(row=27,"),
    ("scheme_row2.grid(row=27,", "scheme_row2.grid(row=28,"),
    ("scheme_row3.grid(row=28,", "scheme_row3.grid(row=29,"),
]
# The Chinese "设计方案" might not match if garbled in my search - use English-free anchors
for a, b in [
    ("self.scheme_label.grid(row=25,", "self.scheme_label.grid(row=26,"),
    ("scheme_row1.grid(row=26,", "scheme_row1.grid(row=27,"),
    ("scheme_row2.grid(row=27,", "scheme_row2.grid(row=28,"),
    ("scheme_row3.grid(row=28,", "scheme_row3.grid(row=29,"),
]:
    if a in text:
        text = text.replace(a, b, 1)
        print("shifted", a)
    else:
        print("WARN missing", a)

# Also shift the "设计方案" label row=24 - find near scheme_label
# Look for row=24 near scheme_label definition
sl = text.find("self.scheme_label = ctk.CTkLabel")
if sl > 0:
    # previous CTkLabel with row=24
    prev = text.rfind(".grid(", 0, sl)
    # search backwards for row=24 within 400 chars
    chunk_start = max(0, sl - 400)
    chunk = text[chunk_start:sl]
    if "row=24" in chunk and "row=25" not in chunk.split("scheme")[0][-80:]:
        # replace last row=24 before scheme_label
        last = chunk.rfind("row=24")
        if last >= 0:
            abs_i = chunk_start + last
            text = text[:abs_i] + "row=25" + text[abs_i + len("row=24"):]
            print("shifted scheme header to row=25")

# --- 4) After _build_ui / refresh, call _refresh_scheme_list ---
old_after_build = """        self._build_ui()
        self.refresh_lists()
        self._refresh_target_choices()"""
new_after_build = """        self._build_ui()
        self.refresh_lists()
        self._refresh_target_choices()
        try:
            self._refresh_scheme_list()
        except Exception:
            pass"""
if old_after_build not in text:
    raise SystemExit("after_build anchor missing")
text = text.replace(old_after_build, new_after_build, 1)

# --- 5) Inject new methods before _bind_canvas_interactions ---
methods = r'''
    def _refresh_scheme_list(self) -> None:
        """Populate browse-side scheme list (UX P2)."""
        frame = getattr(self, "scheme_list_frame", None)
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        self._scheme_list_rows = []
        try:
            rows = list_schemes()
        except Exception as exc:  # noqa: BLE001
            ctk.CTkLabel(frame, text=f"读取失败：{exc}", wraplength=250, anchor="w").pack(
                fill="x", padx=2, pady=2
            )
            return
        if not rows:
            ctk.CTkLabel(
                frame,
                text="暂无方案。点「新建」或「另存」创建。",
                wraplength=250,
                anchor="w",
                text_color=("gray40", "gray70"),
            ).pack(fill="x", padx=2, pady=4)
            return
        for r in rows:
            slug = str(r.get("slug") or "")
            name = str(r.get("name") or slug)
            non_air = r.get("non_air", "?")
            updated = str(r.get("updated") or "")[:16]
            label = f"{name}\n{slug} · 块{non_air} · {updated}"
            selected = slug == self._scheme_slug
            btn = ctk.CTkButton(
                frame,
                text=label,
                anchor="w",
                height=44,
                fg_color=("#1f538d", "#14375e") if selected else ("gray75", "gray30"),
                command=lambda s=slug: self._open_scheme_slug(s),
            )
            btn.pack(fill="x", padx=2, pady=2)
            self._scheme_list_rows.append((slug, btn))

    def _open_scheme_slug(self, slug: str) -> None:
        if self._dirty:
            if not messagebox.askyesno("未保存", "当前有未保存修改，打开方案会丢弃它们。继续？"):
                return
        try:
            data = load_scheme(slug)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("打开失败", str(exc))
            return
        self._bind_scheme(slug, data["voxels"], data["npz_path"], switch_edit=True)

    def on_scheme_new(self) -> None:
        """Create empty scheme or from current voxels."""
        name = simpledialog.askstring("新建方案", "方案名称（中文可）：", parent=self)
        if not name or not name.strip():
            return
        style = self.style_var.get() if hasattr(self, "style_var") else "medieval"
        terrain = self.terrain_var.get() if hasattr(self, "terrain_var") else "flat"
        use_current = False
        if self.current_voxels is not None:
            use_current = messagebox.askyesno(
                "新建方案",
                "是否把当前预览体素写入新方案？\n选「否」则创建空方案。",
            )
        try:
            result = create_scheme(
                name.strip(),
                voxels=self.current_voxels if use_current else None,
                style=style,
                terrain=terrain,
                notes="",
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("新建失败", str(exc))
            return
        data = load_scheme(result["slug"])
        self._bind_scheme(result["slug"], data["voxels"], data["npz_path"], switch_edit=True)
        self._refresh_scheme_list()
        self._flash_toast(f"已新建方案 {name.strip()}")

    def on_scheme_import_npz(self) -> None:
        """Import an npz into a new or current scheme."""
        path = filedialog.askopenfilename(
            title="选择要导入的 .npz",
            filetypes=[("NPZ", "*.npz"), ("全部", "*.*")],
            initialdir=str(self.out_dir),
        )
        if not path:
            return
        name = simpledialog.askstring(
            "导入为方案",
            "方案名称：",
            initialvalue=Path(path).stem,
            parent=self,
        )
        if not name or not name.strip():
            return
        style = self.style_var.get() if hasattr(self, "style_var") else "medieval"
        terrain = self.terrain_var.get() if hasattr(self, "terrain_var") else "flat"
        try:
            result = create_scheme(
                name.strip(),
                from_npz=path,
                style=style,
                terrain=terrain,
            )
            data = load_scheme(result["slug"])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导入失败", str(exc))
            return
        self._bind_scheme(result["slug"], data["voxels"], data["npz_path"], switch_edit=True)
        self._refresh_scheme_list()
        self._flash_toast(f"已导入 {name.strip()}")

    def on_export_to_game(self) -> None:
        """One-click: write .litematic to PCL schematics + BOM + toast. UX P2."""
        if self.current_voxels is None:
            self._set_status("没有可导出的体素，请先加载或生成建筑")
            messagebox.showwarning("进游戏", "请先加载样本 / 打开方案 / 生成建筑")
            return
        # Prefer bound scheme name; else sample stem
        base = "ai_preview"
        if self._scheme_slug:
            # flush dirty edits into scheme first
            if self._dirty:
                try:
                    saved = save_scheme(self._scheme_slug, self.current_voxels)
                    self.current_path = Path(saved["npz"])
                    self._dirty = False
                except Exception as exc:  # noqa: BLE001
                    messagebox.showerror("保存方案失败", str(exc))
                    return
            base = self._scheme_slug
        elif self.current_path is not None:
            stem = self.current_path.stem
            if stem.endswith(".npz"):
                stem = Path(stem).stem
            base = f"ai_{stem}"
        label = ""
        if hasattr(self, "export_version_var"):
            label = self.export_version_var.get()
        target = version_id_from_menu_label(label) if label else DEFAULT_VERSION_ID
        try:
            ver = get_version(target)
            info = export_voxels_to_companion(
                self.current_voxels,
                self.palette,
                name=base,
                target_version=target,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"进游戏导出失败：{exc}")
            messagebox.showerror("进游戏失败", str(exc))
            return
        path = Path(info["path"])
        schematics_dir = info.get("schematics_dir") or str(resolve_schematics_dir())
        bom_info = self._write_export_bom(
            self.current_voxels,
            path,
            source=f"scheme:{self._scheme_slug}" if self._scheme_slug else str(self.current_path or base),
            extra={
                "litematic": str(path),
                "target_version": info.get("target_version"),
                "slug": self._scheme_slug,
            },
        )
        bom_line = ""
        if bom_info.get("error"):
            bom_line = f"材料清单失败：{bom_info['error']}"
        elif not bom_info.get("skipped"):
            md = (bom_info.get("bom_paths") or {}).get("md", "")
            totals = bom_info.get("totals") or {}
            bom_line = (
                f"材料清单：{md}（种类 {totals.get('unique_blocks', '?')} / "
                f"合计 {totals.get('total_blocks', '?')}）"
            )
        tip = "游戏里 Andy：列出投影 → 建造"
        msg = (
            f"已进游戏目录\n{path}\n\n"
            f"目标版本：{info.get('target_display', ver.display_name)}\n"
            f"目录：{schematics_dir}\n"
            f"{bom_line}\n\n"
            f"提示：{tip}"
        )
        status = f"已导出 {path} · {tip}"
        if bom_line:
            status += f" · {bom_line[:80]}"
        self._set_status(status)
        self._flash_toast(f"已写入 PCL · {path.name}", ms=1600)
        messagebox.showinfo("进游戏成功", msg)
        open_folder = bool(getattr(self, "open_folder_var", None) and self.open_folder_var.get())
        if open_folder:
            try:
                folder = str(Path(schematics_dir))
                if sys.platform.startswith("win"):
                    os.startfile(folder)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen(["xdg-open", folder])
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"已导出，但打开文件夹失败：{exc}")

'''

anchor = "    def _bind_canvas_interactions(self) -> None:"
if anchor not in text:
    raise SystemExit("bind_canvas anchor missing")
# Avoid double-inject
if "def on_export_to_game" in text:
    print("methods already present?")
else:
    text = text.replace(anchor, methods + "\n" + anchor, 1)
    print("methods injected")

# --- 6) Update _bind_scheme to accept switch_edit and refresh list ---
old_bind = '''    def _bind_scheme(self, slug: str, voxels, npz_path: Path) -> None:
        self._scheme_slug = slug
        self.current_voxels = voxels
        self.current_path = Path(npz_path)
        self._undo_stack.clear()
        self._dirty = False
        if hasattr(self, "undo_btn"):
            self._refresh_undo_redo_buttons()
        self._refresh_scheme_label()
        self._update_info_panel()
        self._rebuild_block_list()
        self.render_voxels(voxels)
        non_air = int((voxels > 0).sum())
        self._set_status(f"已打开方案 {slug}，non_air={non_air}。")'''

# Flexible: find def _bind_scheme
bind_idx = text.find("    def _bind_scheme(self, slug: str, voxels, npz_path: Path)")
if bind_idx < 0:
    # try without type hints variance
    bind_idx = text.find("    def _bind_scheme(self, slug: str, voxels, npz_path:")
if bind_idx < 0:
    raise SystemExit("_bind_scheme missing")

# Replace function signature and add switch_edit + refresh at end
# Read until next def at same indent
next_def = text.find("\n    def ", bind_idx + 10)
old_fn = text[bind_idx:next_def]
new_fn = '''    def _bind_scheme(
        self, slug: str, voxels, npz_path: Path, *, switch_edit: bool = False
    ) -> None:
        self._scheme_slug = slug
        self.current_voxels = voxels
        self.current_path = Path(npz_path)
        self._undo_stack.clear()
        self._dirty = False
        if hasattr(self, "undo_btn"):
            self._refresh_undo_redo_buttons()
        self._refresh_scheme_label()
        self._update_info_panel()
        self._rebuild_block_list()
        self.render_voxels(voxels)
        non_air = int((voxels > 0).sum())
        self._set_status(f"已打开方案 {slug}，non_air={non_air}。")
        try:
            self._refresh_scheme_list()
        except Exception:
            pass
        if switch_edit:
            self._switch_mode(MODE_EDIT)
'''
text = text[:bind_idx] + new_fn + text[next_def:]
print("_bind_scheme updated")

# --- 7) Make on_scheme_open / save_as refresh list and switch edit ---
# After successful load in on_scheme_open, it calls _bind_scheme without switch_edit
text = text.replace(
    "self._bind_scheme(slug, data[\"voxels\"], data[\"npz_path\"])\n\n    def on_scheme_export",
    "self._bind_scheme(slug, data[\"voxels\"], data[\"npz_path\"], switch_edit=True)\n\n    def on_scheme_export",
    1,
)
# save_as bind
text = text.replace(
    "self._bind_scheme(slug, self.current_voxels, result[\"dir\"] / \"current.npz\")\n        messagebox.showinfo(\n            \"已保存方案\"",
    "self._bind_scheme(slug, self.current_voxels, result[\"dir\"] / \"current.npz\")\n        self._refresh_scheme_list()\n        messagebox.showinfo(\n            \"已保存方案\"",
    1,
)
# import litematic bind
text = text.replace(
    "self._bind_scheme(slug, data[\"voxels\"], data[\"npz_path\"])\n        messagebox.showinfo(\n            \"已导入投影\"",
    "self._bind_scheme(slug, data[\"voxels\"], data[\"npz_path\"], switch_edit=True)\n        self._refresh_scheme_list()\n        messagebox.showinfo(\n            \"已导入投影\"",
    1,
)

# Point old on_scheme_export toward game export when possible - leave as is but also refresh
# Point on_export_litematic callers: export_btn now uses on_export_to_game

if MARKER not in text:
    raise SystemExit("MARKER not in patched text")

SRC.write_text(text, encoding="utf-8")
print("WROTE", SRC)
print("len", len(text), "delta", len(text) - len(orig))
print("has on_export_to_game", "def on_export_to_game" in text)
print("has on_scheme_new", "def on_scheme_new" in text)
print("has scheme_list_frame", "scheme_list_frame" in text)
