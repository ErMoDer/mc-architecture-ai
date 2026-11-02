# -*- coding: utf-8 -*-
"""Patch viewer_app.py for MCBlock-like orbit LOD + voxel edit tools."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "viewer_app.py"
text = PATH.read_text(encoding="utf-8")
orig = text

# --- 1) imports ---
old_imp = "from src.app.mc_render import render_mc_voxels"
new_imp = """from src.app.mc_render import render_mc_voxels
from src.app.viewer_voxel_tools import (
    TOOL_BREAK,
    TOOL_MOVE,
    TOOL_PAINT,
    TOOL_PLACE,
    TOOL_SELECT,
    apply_break,
    apply_move,
    apply_paint,
    apply_place,
    nudge,
    pick_nearest_face,
    place_pos_from_face,
)"""
if "viewer_voxel_tools" not in text:
    if old_imp not in text:
        raise SystemExit("missing mc_render import")
    text = text.replace(old_imp, new_imp, 1)

# --- 2) __init__ state ---
needle = "        self._scheme_slug: str | None = None\n\n        self._build_ui()"
insert = """        self._scheme_slug: str | None = None
        # MCBlock-like voxel tools + orbit LOD
        self._voxel_tool = TOOL_SELECT
        self._sel_pos: tuple[int, int, int] | None = None
        self._move_src: tuple[int, int, int] | None = None
        self._face_meta: list = []
        self._orbiting = False
        self._orbit_lod_active = False
        self._press_xy: tuple[float, float] | None = None
        self._did_drag = False
        self._draw_edges_var = tk.BooleanVar(value=False)
        # Default ON for snappier orbit on 3k-10k block houses (RTX 3050 laptop).
        self.style_perf_var = tk.BooleanVar(value=True)

        self._build_ui()"""
# Avoid double-setting style_perf_var — remove previous assignment if we re-add
if "self._voxel_tool" not in text:
    if needle not in text:
        raise SystemExit("missing scheme_slug needle")
    text = text.replace(needle, insert, 1)
    # remove the earlier style_perf_var = False line (keep one True via insert)
    text = text.replace(
        "        self.style_perf_var = tk.BooleanVar(value=False)\n",
        "        # style_perf_var set below (default True for orbit)\n",
        1,
    )

# --- 3) After canvas created, bind events ---
canvas_needle = """        self.canvas = FigureCanvasTkAgg(self.fig, master=mid)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))
"""
canvas_repl = """        self.canvas = FigureCanvasTkAgg(self.fig, master=mid)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))
        self._bind_canvas_interactions()
"""
if "_bind_canvas_interactions" not in text:
    if canvas_needle not in text:
        raise SystemExit("missing canvas needle")
    text = text.replace(canvas_needle, canvas_repl, 1)

# --- 4) Replace render_voxels ---
old_rv_start = "    def render_voxels(self, voxels: np.ndarray) -> None:"
old_rv_end = "    def _rebuild_block_list(self) -> None:"
i0 = text.find(old_rv_start)
i1 = text.find(old_rv_end)
if i0 < 0 or i1 < 0:
    raise SystemExit("render_voxels block not found")
new_rv = '''    def render_voxels(self, voxels: np.ndarray, *, orbit_lod: bool | None = None) -> None:
        perf = bool(self.style_perf_var.get()) if hasattr(self, "style_perf_var") else False
        use_orbit = bool(orbit_lod) if orbit_lod is not None else bool(getattr(self, "_orbit_lod_active", False))
        work = np.asarray(voxels, dtype=np.int16)
        y_cut = int(self.y_slice_var.get()) if hasattr(self, "y_slice_var") else 99
        if work.ndim == 3 and y_cut < work.shape[1] - 1:
            work = work.copy()
            work[:, y_cut + 1 :, :] = 0
        # Collect face meta only when editing (pick) and not in orbit LOD.
        collect = (self._mode == MODE_EDIT) and (not use_orbit)
        draw_edges = bool(getattr(self, "_draw_edges_var", tk.BooleanVar(value=False)).get())
        info = render_mc_voxels(
            self.ax,
            self.fig,
            work,
            self.palette,
            highlight_id=self._source_id,
            highlight_pos=getattr(self, "_sel_pos", None),
            performance=perf,
            orbit_lod=use_orbit,
            preserve_view=True,
            draw_edges=draw_edges,
            collect_meta=collect,
        )
        info = dict(info)
        info["y_slice"] = y_cut
        self._face_meta = list(info.get("face_meta") or [])
        self.canvas.draw_idle()
        self._last_render_info = info

'''
text = text[:i0] + new_rv + text[i1:]

# --- 5) Expand edit panel left hint ---
old_steps = '''        steps = (
            "1. 在方块列表点选「源」\\n"
            "2. 搜索或点快捷选「目标」\\n"
            "3. 点「一键替换」\\n"
            "4. 另存 / 覆盖 / 导出"
        )'''
new_steps = '''        steps = (
            "建模（接近 MCBlock）：\\n"
            "· 选工具后在 3D 上点击\\n"
            "· 破坏 / 放置 / 涂改 / 移动\\n"
            "· 选中后可用微调按钮\\n"
            "——\\n"
            "批量：列表选源 → 目标 → 替换\\n"
            "最后另存 / 导出 companion"
        )'''
if old_steps in text:
    text = text.replace(old_steps, new_steps, 1)

# --- 6) Insert voxel tool UI into right edit panel after title ---
# After "方块替换" header block, insert builder tools section before block_list
marker = '''        self.block_list = ctk.CTkScrollableFrame(right, height=240)
        self.block_list.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
'''
tool_ui = '''        # —— MCBlock-like voxel tools ——
        ctk.CTkLabel(right, text="体素工具（点 3D）", font=ctk.CTkFont(weight="bold")).grid(
            row=1, column=0, sticky="w", padx=14, pady=(8, 2)
        )
        self.voxel_tool_var = ctk.StringVar(value="选择")
        self.voxel_tool_seg = ctk.CTkSegmentedButton(
            right,
            values=["选择", "破坏", "放置", "涂改", "移动"],
            variable=self.voxel_tool_var,
            command=self._on_voxel_tool_change,
            width=280,
            height=28,
            font=ctk.CTkFont(size=12),
        )
        self.voxel_tool_seg.grid(row=2, column=0, sticky="ew", padx=10, pady=2)
        self.sel_pos_label = ctk.CTkLabel(
            right, text="选中：无", anchor="w", wraplength=280, justify="left"
        )
        self.sel_pos_label.grid(row=3, column=0, sticky="ew", padx=14, pady=(2, 2))
        nudge_row = ctk.CTkFrame(right, fg_color="transparent")
        nudge_row.grid(row=4, column=0, sticky="ew", padx=10, pady=2)
        for i, (lab, dx, dy, dz) in enumerate(
            [("-X", -1, 0, 0), ("+X", 1, 0, 0), ("-Y", 0, -1, 0), ("+Y", 0, 1, 0), ("-Z", 0, 0, -1), ("+Z", 0, 0, 1)]
        ):
            ctk.CTkButton(
                nudge_row,
                text=lab,
                width=42,
                height=24,
                command=lambda a=dx, b=dy, c=dz: self.on_nudge_selection((a, b, c)),
            ).grid(row=0, column=i, padx=1, pady=1)
        ctk.CTkLabel(
            right,
            text="放置/涂改用下方「目标」；拖转时自动降面数减卡顿",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=5, column=0, sticky="w", padx=14, pady=(0, 6))

        ctk.CTkLabel(right, text="批量方块替换", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=6, column=0, sticky="w", padx=14, pady=(6, 2)
        )

        self.block_list = ctk.CTkScrollableFrame(right, height=160)
        self.block_list.grid(row=7, column=0, sticky="nsew", padx=10, pady=4)
'''
if "voxel_tool_var" not in text:
    if marker not in text:
        raise SystemExit("block_list marker missing")
    text = text.replace(marker, tool_ui, 1)
    # Fix subsequent row numbers in _build_right_edit — they used fixed rows 3..21.
    # Remap: source_label was 3 -> 8, target filter 4->9, ... export etc.
    # Safer: rewrite the remaining grid rows after block_list with a regex pass.
    remaps = [
        ("self.source_label = ctk.CTkLabel(right, text=\"源方块：未选择\", wraplength=280, justify=\"left\")\n        self.source_label.grid(row=3,",
         "self.source_label = ctk.CTkLabel(right, text=\"源方块：未选择\", wraplength=280, justify=\"left\")\n        self.source_label.grid(row=8,"),
        ("ctk.CTkLabel(right, text=\"替换目标（可搜索）\").grid(\n            row=4,",
         "ctk.CTkLabel(right, text=\"替换目标（可搜索）\").grid(\n            row=9,"),
        ("self.target_filter.grid(row=5,", "self.target_filter.grid(row=10,"),
        ("self.target_combo.grid(row=6,", "self.target_combo.grid(row=11,"),
        ("ctk.CTkLabel(right, text=\"常用目标\").grid(row=7,", "ctk.CTkLabel(right, text=\"常用目标\").grid(row=12,"),
        ("quick.grid(row=8,", "quick.grid(row=13,"),
        ("btn_row.grid(row=9,", "btn_row.grid(row=14,"),
        ("save_row.grid(row=10,", "save_row.grid(row=15,"),
        ("ctk.CTkLabel(right, text=\"目标版本（Java）\").grid(\n            row=11,",
         "ctk.CTkLabel(right, text=\"目标版本（Java）\").grid(\n            row=16,"),
        ("self.export_version_menu.grid(row=12,", "self.export_version_menu.grid(row=17,"),
        (").grid(row=13, column=0, sticky=\"w\", padx=14, pady=(2, 4))",
         ").grid(row=18, column=0, sticky=\"w\", padx=14, pady=(2, 4))"),
        ("bom_opts.grid(row=14,", "bom_opts.grid(row=19,"),
        (").grid(row=15, column=0, sticky=\"w\", padx=14, pady=(2, 0))",
         ").grid(row=20, column=0, sticky=\"w\", padx=14, pady=(2, 0))"),
        ("export_row.grid(row=16,", "export_row.grid(row=21,"),
        ("ctk.CTkLabel(right, text=\"设计方案\", font=ctk.CTkFont(weight=\"bold\")).grid(\n            row=17,",
         "ctk.CTkLabel(right, text=\"设计方案\", font=ctk.CTkFont(weight=\"bold\")).grid(\n            row=22,"),
        ("self.scheme_label.grid(row=18,", "self.scheme_label.grid(row=23,"),
        ("scheme_row1.grid(row=19,", "scheme_row1.grid(row=24,"),
        ("scheme_row2.grid(row=20,", "scheme_row2.grid(row=25,"),
        ("scheme_row3.grid(row=21,", "scheme_row3.grid(row=26,"),
    ]
    for a, b in remaps:
        if a not in text:
            print("WARN missing remap:", a[:60])
        else:
            text = text.replace(a, b, 1)

# Also bump right.grid_rowconfigure weight row if needed
text = text.replace(
    "        self.right.grid_rowconfigure(2, weight=1)",
    "        self.right.grid_rowconfigure(7, weight=1)",
    1,
)

# --- 7) Browse panel: edges checkbox near perf ---
# Find style_perf checkbox area and add edges + help note
# Skip if already present

# --- 8) Append new methods before main() ---
METHODS = r'''
    def _bind_canvas_interactions(self) -> None:
        """Orbit LOD on drag; click-to-edit when not dragging (MCBlock-like)."""
        self.canvas.mpl_connect("button_press_event", self._on_canvas_press)
        self.canvas.mpl_connect("button_release_event", self._on_canvas_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_canvas_motion)
        widget = self.canvas.get_tk_widget()
        widget.bind("<Key>", self._on_canvas_key)
        try:
            widget.focus_set()
        except Exception:
            pass

    def _on_voxel_tool_change(self, value: str) -> None:
        mapping = {
            "选择": TOOL_SELECT,
            "破坏": TOOL_BREAK,
            "放置": TOOL_PLACE,
            "涂改": TOOL_PAINT,
            "移动": TOOL_MOVE,
        }
        self._voxel_tool = mapping.get(value, TOOL_SELECT)
        self._move_src = None
        self._set_status(f"工具：{value}（在 3D 上点击）")

    def _on_canvas_press(self, event) -> None:
        if event.inaxes != self.ax:
            return
        if event.button != 1:
            return
        self._press_xy = (float(event.x), float(event.y))
        self._did_drag = False

    def _on_canvas_motion(self, event) -> None:
        if self._press_xy is None or event.button != 1:
            return
        dx = float(event.x) - self._press_xy[0]
        dy = float(event.y) - self._press_xy[1]
        if (dx * dx + dy * dy) < 36:
            return
        self._did_drag = True
        if not self._orbiting:
            self._orbiting = True
            self._orbit_lod_active = True
            if self.current_voxels is not None:
                # One LOD rebuild, then matplotlib orbit redraws the light mesh.
                self.render_voxels(self.current_voxels, orbit_lod=True)

    def _on_canvas_release(self, event) -> None:
        if event.button != 1:
            return
        was_orbit = self._orbiting
        self._orbiting = False
        press = self._press_xy
        self._press_xy = None
        if was_orbit or self._did_drag:
            self._orbit_lod_active = False
            if self.current_voxels is not None:
                self.render_voxels(self.current_voxels, orbit_lod=False)
            self._did_drag = False
            return
        self._did_drag = False
        # Click (no drag): voxel tool in EDIT mode
        if self._mode != MODE_EDIT:
            return
        if event.inaxes != self.ax or press is None:
            return
        self._handle_voxel_click(event)

    def _handle_voxel_click(self, event) -> None:
        if self.current_voxels is None:
            return
        if not self._face_meta:
            # rebuild with meta
            self.render_voxels(self.current_voxels, orbit_lod=False)
        meta = pick_nearest_face(self.ax, (float(event.x), float(event.y)), self._face_meta)
        if meta is None:
            self._set_status("未点到方块面，换个角度再点")
            return
        tool = self._voxel_tool
        pos = meta["voxel"]
        if tool == TOOL_SELECT:
            self._sel_pos = pos
            bid = int(meta["bid"])
            name = short_block_name(self.palette.get(bid, str(bid)))
            self.sel_pos_label.configure(text=f"选中：{pos} · {name}")
            self._select_source(bid, self.palette.get(bid, str(bid)))
            self.render_voxels(self.current_voxels)
            self._set_status(f"选中 {pos} ({name})")
            return

        self._undo_voxels = self.current_voxels.copy()
        changed = False
        if tool == TOOL_BREAK:
            changed = apply_break(self.current_voxels, pos)
            msg = f"破坏 {pos}" if changed else "此处无可破坏"
            if changed:
                self._sel_pos = None
        elif tool == TOOL_PLACE:
            tid = self._parse_target_id()
            if tid is None:
                self._undo_voxels = None
                self._set_status("放置前请先选目标方块")
                return
            dst = place_pos_from_face(meta)
            changed = apply_place(self.current_voxels, dst, tid)
            msg = f"放置 {dst}" if changed else f"无法放置到 {dst}（越界或已被占）"
            if changed:
                self._sel_pos = dst
        elif tool == TOOL_PAINT:
            tid = self._parse_target_id()
            if tid is None:
                self._undo_voxels = None
                self._set_status("涂改前请先选目标方块")
                return
            changed = apply_paint(self.current_voxels, pos, tid)
            msg = f"涂改 {pos}" if changed else "涂改未变化"
            if changed:
                self._sel_pos = pos
        elif tool == TOOL_MOVE:
            if self._move_src is None:
                self._undo_voxels = None
                self._move_src = pos
                self._sel_pos = pos
                self.sel_pos_label.configure(text=f"移动：已抓取 {pos}，再点目标面旁放置")
                self.render_voxels(self.current_voxels)
                self._set_status(f"已抓取 {pos}，再点目标位置")
                return
            dst = place_pos_from_face(meta)
            # allow clicking same solid to swap onto adjacent
            changed = apply_move(self.current_voxels, self._move_src, dst)
            msg = f"移动 {self._move_src} → {dst}" if changed else "移动失败（目标被占或越界）"
            if changed:
                self._sel_pos = dst
            self._move_src = None
        else:
            self._undo_voxels = None
            return

        if not changed:
            self._undo_voxels = None
            self._set_status(msg)
            return
        self._dirty = True
        self.undo_btn.configure(state="normal")
        self._rebuild_block_list()
        self._update_info_panel()
        if hasattr(self, "sel_pos_label") and self._sel_pos is not None:
            self.sel_pos_label.configure(text=f"选中：{self._sel_pos}")
        self.render_voxels(self.current_voxels)
        self._set_status(msg + "（可撤销）")

    def on_nudge_selection(self, delta: tuple[int, int, int]) -> None:
        if self.current_voxels is None or self._sel_pos is None:
            self._set_status("先用「选择」点选一个方块")
            return
        self._undo_voxels = self.current_voxels.copy()
        new_pos = nudge(self.current_voxels, self._sel_pos, delta)
        if new_pos is None:
            self._undo_voxels = None
            self._set_status("微调失败（越界或目标被占）")
            return
        self._sel_pos = new_pos
        self._dirty = True
        self.undo_btn.configure(state="normal")
        self.sel_pos_label.configure(text=f"选中：{new_pos}")
        self._rebuild_block_list()
        self._update_info_panel()
        self.render_voxels(self.current_voxels)
        self._set_status(f"已微调到 {new_pos}")

    def _on_canvas_key(self, event) -> None:
        if self._mode != MODE_EDIT or self._sel_pos is None:
            return
        key = getattr(event, "keysym", "") or ""
        mapping = {
            "Left": (-1, 0, 0),
            "Right": (1, 0, 0),
            "Up": (0, 0, -1),
            "Down": (0, 0, 1),
            "Prior": (0, 1, 0),  # PageUp
            "Next": (0, -1, 0),  # PageDown
            "Delete": None,
            "BackSpace": None,
        }
        if key in ("Delete", "BackSpace"):
            self._undo_voxels = self.current_voxels.copy()
            if apply_break(self.current_voxels, self._sel_pos):
                self._dirty = True
                self.undo_btn.configure(state="normal")
                self._sel_pos = None
                self.sel_pos_label.configure(text="选中：无")
                self._rebuild_block_list()
                self._update_info_panel()
                self.render_voxels(self.current_voxels)
                self._set_status("已删除选中方块")
            else:
                self._undo_voxels = None
            return
        delta = mapping.get(key)
        if delta is not None:
            self.on_nudge_selection(delta)

'''

if "def _bind_canvas_interactions" not in text:
    anchor = "\ndef main() -> None:"
    if anchor not in text:
        raise SystemExit("main() not found")
    text = text.replace(anchor, "\n" + METHODS + "\ndef main() -> None:", 1)

# --- 9) Update edit mode hints ---
text = text.replace(
    'self.mode_hint.configure(text="当前：编辑方块 · 先选源再选目标")',
    'self.mode_hint.configure(text="当前：编辑 · 点选/破坏/放置/涂改/移动（接近 MCBlock）")',
    1,
)
text = text.replace(
    'self._set_status("先选源方块，再选目标后替换")',
    'self._set_status("选工具后在 3D 点击；或列表批量替换")',
    1,
)
text = text.replace(
    'self.mode_hint.configure(text="当前：查看已有样本 · 中间拖动旋转，滚轮缩放")',
    'self.mode_hint.configure(text="当前：浏览 · 拖转自动降面减卡；编辑模式可点方块")',
    1,
)

# --- 10) Reset selection on load ---
old_load = """        self._source_id = None
        self.undo_btn.configure(state="disabled")
        self.source_label.configure(text="源方块：未选择")
        self.source_label_left.configure(text="源方块：未选择")
"""
new_load = """        self._source_id = None
        self._sel_pos = None
        self._move_src = None
        self._orbit_lod_active = False
        self.undo_btn.configure(state="disabled")
        self.source_label.configure(text="源方块：未选择")
        self.source_label_left.configure(text="源方块：未选择")
        if hasattr(self, "sel_pos_label"):
            self.sel_pos_label.configure(text="选中：无")
"""
if old_load in text:
    text = text.replace(old_load, new_load, 1)

# --- 11) Add edges checkbox near perf if present ---
perf_chk = 'variable=self.style_perf_var,'
# leave as-is; optional edges via drawn flag already wired in render

if text == orig:
    raise SystemExit("no changes made")
backup = PATH.with_suffix(".py.bak_mcedit")
if not backup.exists():
    backup.write_text(orig, encoding="utf-8")
PATH.write_text(text, encoding="utf-8")
print("patched", PATH)
print("backup", backup)
print("delta chars", len(text) - len(orig))
