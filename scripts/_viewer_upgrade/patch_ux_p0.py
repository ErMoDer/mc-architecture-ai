# -*- coding: utf-8 -*-
"""UX P0 patch: hotbar 1-9 + crosshair + game-like key/mouse hints."""
from __future__ import annotations

from pathlib import Path

APP = Path(r"E:\ai agent\mc-architecture-ai\scripts\viewer_app.py")
text = APP.read_text(encoding="utf-8")
orig = text

def must(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f"MISSING block for {label}:\n{old[:180]!r}")
    c = text.count(old)
    if c != 1:
        raise SystemExit(f"Expected 1 occurrence for {label}, got {c}")
    text = text.replace(old, new, 1)
    print("OK", label)

# ---- 1) imports: Line2D ----
must(
    "from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk\n",
    "from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk\n"
    "from matplotlib.lines import Line2D\n",
    "import Line2D",
)

# ---- 2) HOTBAR_DEFAULTS after QUICK_TARGETS ----
must(
    '''QUICK_TARGETS = [
    "minecraft:stone",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:oak_log",
    "minecraft:glass",
    "minecraft:bricks",
    "minecraft:dirt",
    "minecraft:grass_block",
    "minecraft:white_concrete",
    "minecraft:black_concrete",
    "minecraft:spruce_planks",
    "minecraft:dark_oak_planks",
]

MODE_BROWSE = "浏览"
''',
    '''QUICK_TARGETS = [
    "minecraft:stone",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:oak_log",
    "minecraft:glass",
    "minecraft:bricks",
    "minecraft:dirt",
    "minecraft:grass_block",
    "minecraft:white_concrete",
    "minecraft:black_concrete",
    "minecraft:spruce_planks",
    "minecraft:dark_oak_planks",
]

# UX P0: bottom hotbar defaults (slots 1-9) — place/paint target
HOTBAR_DEFAULTS = [
    "minecraft:stone",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:oak_log",
    "minecraft:glass",
    "minecraft:bricks",
    "minecraft:dirt",
    "minecraft:grass_block",
    "minecraft:white_concrete",
]

MODE_BROWSE = "浏览"
''',
    "HOTBAR_DEFAULTS",
)

# ---- 3) title + state ----
must(
    '        self.title("MC 建筑 AI · 采样 3D 预览")\n',
    '        self.title("MC 建筑 AI · 工作台预览")\n',
    "title",
)

must(
    "        self.style_perf_var = tk.BooleanVar(value=True)\n\n        self._build_ui()\n",
    "        self.style_perf_var = tk.BooleanVar(value=True)\n"
    "        # UX P0 workbench: hotbar + crosshair\n"
    "        self._hotbar_names: list[str] = list(HOTBAR_DEFAULTS)\n"
    "        self._hotbar_slot: int = 0  # 0..8\n"
    "        self._hotbar_buttons: list = []\n"
    "        self._crosshair_artists: list = []\n"
    "        self._press_button: int | None = None\n\n"
    "        self._build_ui()\n",
    "hotbar state",
)

# ---- 4) mid column: canvas host + hotbar + toolbar ----
must(
    '''        # —— 中栏：3D 始终可见 ——
        mid = ctk.CTkFrame(self)
        mid.grid(row=1, column=1, sticky="nsew", padx=4, pady=(4, 12))
        mid.grid_rowconfigure(0, weight=1)
        mid.grid_columnconfigure(0, weight=1)

        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.ax.set_title("3D 体素预览")
        self._draw_empty()

        self.canvas = FigureCanvasTkAgg(self.fig, master=mid)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))
        self._bind_canvas_interactions()

        toolbar_frame = tk.Frame(mid)
        toolbar_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
''',
    '''        # —— 中栏：3D + 准星 + 快捷栏（UX P0）——
        mid = ctk.CTkFrame(self)
        mid.grid(row=1, column=1, sticky="nsew", padx=4, pady=(4, 12))
        mid.grid_rowconfigure(0, weight=1)
        mid.grid_columnconfigure(0, weight=1)

        canvas_host = ctk.CTkFrame(mid, fg_color="transparent")
        canvas_host.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))
        canvas_host.grid_rowconfigure(0, weight=1)
        canvas_host.grid_columnconfigure(0, weight=1)

        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.ax.set_title("3D 体素预览")
        self._draw_empty()

        self.canvas = FigureCanvasTkAgg(self.fig, master=canvas_host)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._bind_canvas_interactions()
        self._redraw_crosshair()

        self._build_hotbar(mid)  # row 1

        toolbar_frame = tk.Frame(mid)
        toolbar_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
''',
    "mid layout hotbar",
)

# ---- 5) mode hints emphasize Browse/Edit/Generate ----
must(
    '            self.mode_hint.configure(text="当前：浏览 · 拖转自动降面减卡；编辑模式可点方块")\n',
    '            self.mode_hint.configure(text="主路径·浏览：看样本 / 拖转降面；要改方块切「编辑」")\n',
    "hint browse",
)
must(
    '            self.mode_hint.configure(text="当前：手动选风格/地形生成 · 可开结构约束")\n',
    '            self.mode_hint.configure(text="主路径·生成：选风格/地形后生成；可开结构约束")\n',
    "hint generate",
)
must(
    '            self.mode_hint.configure(text="当前：截图+文字设计 · 可先理解再手改，再生成")\n',
    '            self.mode_hint.configure(text="次要·设计：截图+文字（主路径仍是浏览/编辑/生成）")\n',
    "hint design",
)
must(
    '            self.mode_hint.configure(text="当前：分析 / 相似 / 红石模板 / 一键流水线")\n',
    '            self.mode_hint.configure(text="次要·工具：分析/相似/红石/流水线（主路径仍是浏览/编辑/生成）")\n',
    "hint tools",
)
must(
    '            self.mode_hint.configure(text="当前：编辑 · 点选/破坏/放置/涂改/移动（接近 MCBlock）")\n',
    '            self.mode_hint.configure(\n'
    '                text="主路径·编辑：左键=工具 · 右键=快捷栏放置 · 1-9切栏 · 准星对准外壳面"\n'
    '            )\n',
    "hint edit",
)
must(
    '            self._set_status("选工具后在 3D 点击；或列表批量替换")\n',
    '            self._set_status("编辑：左键工具 / 右键放置 / 1-9 快捷栏")\n'
    '            self._select_hotbar(self._hotbar_slot)\n'
    '            self._update_workbench_hint()\n',
    "edit status+hotbar sync",
)

# ---- 6) after _set_status, insert helpers before _draw_empty ----
must(
    '''    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _draw_empty(self) -> None:
''',
    '''    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _build_hotbar(self, parent: ctk.CTkFrame) -> None:
        """Bottom hotbar slots 1-9 + workbench hint (UX P0)."""
        wrap = ctk.CTkFrame(parent, fg_color=("#252525", "#252525"))
        wrap.grid(row=1, column=0, sticky="ew", padx=8, pady=(6, 2))
        wrap.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(wrap, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        self._hotbar_buttons = []
        for i in range(9):
            slot = ctk.CTkFrame(
                bar,
                width=58,
                height=54,
                fg_color=("#3a3a3a", "#3a3a3a"),
                border_width=2,
                border_color=("#666666", "#666666"),
                corner_radius=6,
            )
            slot.pack(side="left", padx=3)
            slot.pack_propagate(False)
            num = ctk.CTkLabel(
                slot, text=str(i + 1), font=ctk.CTkFont(size=10), text_color=("gray60", "gray70")
            )
            num.place(x=4, y=1)
            swatch = ctk.CTkLabel(slot, text="", width=30, height=16, corner_radius=3)
            swatch.place(relx=0.5, rely=0.38, anchor="center")
            namel = ctk.CTkLabel(slot, text="", font=ctk.CTkFont(size=9), wraplength=54)
            namel.place(relx=0.5, rely=0.78, anchor="center")
            for w in (slot, num, swatch, namel):
                w.bind("<Button-1>", lambda _e, idx=i: self._select_hotbar(idx))
            self._hotbar_buttons.append((slot, swatch, namel))

        self.workbench_hint = ctk.CTkLabel(
            wrap,
            text="",
            anchor="w",
            justify="left",
            wraplength=640,
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray75"),
        )
        self.workbench_hint.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 6))
        self._refresh_hotbar_ui()
        self._update_workbench_hint()

    def _rgb_to_hex(self, rgba: tuple[float, float, float, float]) -> str:
        r, g, b = rgba[0], rgba[1], rgba[2]
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    def _select_hotbar(self, idx: int) -> None:
        self._hotbar_slot = max(0, min(8, int(idx)))
        name = self._hotbar_names[self._hotbar_slot]
        if hasattr(self, "target_var"):
            self._set_target(name)
        self._refresh_hotbar_ui()
        self._update_workbench_hint()

    def _refresh_hotbar_ui(self) -> None:
        if not getattr(self, "_hotbar_buttons", None):
            return
        for i, (slot, swatch, namel) in enumerate(self._hotbar_buttons):
            name = self._hotbar_names[i] if i < len(self._hotbar_names) else "minecraft:stone"
            bid = int(self.name_to_id.get(name, 0) or 0)
            hexc = self._rgb_to_hex(_block_color(bid if bid > 0 else (i + 1)))
            try:
                swatch.configure(fg_color=hexc, text="")
            except Exception:
                swatch.configure(text="■", text_color=hexc)
            short = short_block_name(name)
            namel.configure(text=short[:9])
            selected = i == self._hotbar_slot
            slot.configure(
                border_color=("#f1c40f", "#f1c40f") if selected else ("#666666", "#666666"),
                border_width=3 if selected else 2,
                fg_color=("#4a3f10", "#4a3f10") if selected else ("#3a3a3a", "#3a3a3a"),
            )

    def _update_workbench_hint(self) -> None:
        if not hasattr(self, "workbench_hint"):
            return
        tool = "?"
        if hasattr(self, "voxel_tool_var"):
            try:
                tool = self.voxel_tool_var.get() or "?"
            except Exception:
                tool = str(getattr(self, "_voxel_tool", "?"))
        tid = None
        tname = "?"
        if hasattr(self, "target_var"):
            tid = self._parse_target_id()
            if tid is not None:
                tname = short_block_name(self.palette.get(tid, str(tid)))
            else:
                tname = short_block_name(self._hotbar_names[self._hotbar_slot])
        else:
            tname = short_block_name(self._hotbar_names[self._hotbar_slot])
            tid = self.name_to_id.get(self._hotbar_names[self._hotbar_slot])
        id_part = f"id={tid}" if tid is not None else "id=?"
        self.workbench_hint.configure(
            text=(
                f"工具：{tool}  ·  快捷栏 [{self._hotbar_slot + 1}] {tname} ({id_part})  ·  "
                f"左键=当前工具 / 右键=放置 / 1-9 切栏"
            )
        )

    def _clear_crosshair(self) -> None:
        for art in getattr(self, "_crosshair_artists", []) or []:
            try:
                art.remove()
            except Exception:
                pass
        self._crosshair_artists = []

    def _redraw_crosshair(self) -> None:
        """Center crosshair in figure coords (MC-like +)."""
        self._clear_crosshair()
        if not hasattr(self, "fig"):
            return
        cx, cy, arm = 0.50, 0.50, 0.022
        style = dict(
            transform=self.fig.transFigure,
            color="#f2f2f2",
            linewidth=1.35,
            solid_capstyle="butt",
            zorder=10_000,
            clip_on=False,
        )
        for xs, ys in (([cx - arm, cx + arm], [cy, cy]), ([cx, cx], [cy - arm, cy + arm])):
            ln = Line2D(xs, ys, **style)
            self.fig.add_artist(ln)
            self._crosshair_artists.append(ln)
        # slight gap at center (MC style) via dark overlay stubs
        gap = 0.006
        gap_style = dict(
            transform=self.fig.transFigure,
            color="#1a1a1a",
            linewidth=2.2,
            solid_capstyle="butt",
            zorder=10_001,
            clip_on=False,
        )
        for xs, ys in (([cx - gap, cx + gap], [cy, cy]), ([cx, cx], [cy - gap, cy + gap])):
            ln = Line2D(xs, ys, **gap_style)
            self.fig.add_artist(ln)
            self._crosshair_artists.append(ln)

    def _draw_empty(self) -> None:
''',
    "hotbar+crosshair methods",
)

# ---- 7) hook crosshair into render_voxels ----
must(
    '''        self._face_meta = list(info.get("face_meta") or [])
        self.canvas.draw_idle()
        self._last_render_info = info
''',
    '''        self._face_meta = list(info.get("face_meta") or [])
        self._redraw_crosshair()
        self.canvas.draw_idle()
        self._last_render_info = info
''',
    "render crosshair",
)

# Also hook _draw_empty body — find canvas.draw after empty
# Read what _draw_empty looks like
idx = text.find("    def _draw_empty(self) -> None:")
# after our insert there may be two? no we replaced the def header only once with methods+_draw_empty
print("draw_empty at", idx)

# ---- 8) _set_target also refresh hint ----
must(
    '''        self.target_var.set(label)
        self._set_status(f"目标设为 {label}")
''',
    '''        self.target_var.set(label)
        # keep hotbar highlight in sync when target matches a slot
        for i, n in enumerate(self._hotbar_names):
            bid = self.name_to_id.get(n)
            if bid is not None and f"[{bid}]" in label:
                self._hotbar_slot = i
                break
        self._refresh_hotbar_ui()
        self._update_workbench_hint()
        self._set_status(f"目标设为 {label}")
''',
    "set_target sync hotbar",
)

# ---- 9) voxel tool change updates hint ----
must(
    '''        self._voxel_tool = mapping.get(value, TOOL_SELECT)
        self._move_src = None
        self._set_status(f"工具：{value}（在 3D 上点击）")
''',
    '''        self._voxel_tool = mapping.get(value, TOOL_SELECT)
        self._move_src = None
        self._update_workbench_hint()
        self._set_status(f"工具：{value}（左键）· 右键放置 · 栏{self._hotbar_slot + 1}")
''',
    "tool change hint",
)

# ---- 10) mouse: track button; right-click place ----
must(
    '''    def _on_canvas_press(self, event) -> None:
        if event.inaxes != self.ax:
            return
        if event.button != 1:
            return
        self._press_xy = (float(event.x), float(event.y))
        self._did_drag = False

    def _on_canvas_motion(self, event) -> None:
        if self._press_xy is None or event.button != 1:
            return
''',
    '''    def _on_canvas_press(self, event) -> None:
        if event.inaxes != self.ax:
            return
        if event.button not in (1, 3):
            return
        self._press_button = int(event.button)
        self._press_xy = (float(event.x), float(event.y))
        self._did_drag = False

    def _on_canvas_motion(self, event) -> None:
        if self._press_xy is None:
            return
        # orbit LOD only for left-drag
        if event.button not in (1, None) and self._press_button != 1:
            # still track drag distance for right-click cancel
            pass
        if self._press_button == 1 and event.button not in (1, None):
            return
        if self._press_button != 1:
            dx = float(event.x) - self._press_xy[0]
            dy = float(event.y) - self._press_xy[1]
            if (dx * dx + dy * dy) >= 36:
                self._did_drag = True
            return
''',
    "press/motion buttons",
)

must(
    '''    def _on_canvas_release(self, event) -> None:
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
''',
    '''    def _on_canvas_release(self, event) -> None:
        btn = int(getattr(event, "button", 0) or 0)
        press_btn = self._press_button
        self._press_button = None
        press = self._press_xy
        self._press_xy = None

        # Right-click: place from hotbar (Edit, no drag)
        if btn == 3 or press_btn == 3:
            dragged = self._did_drag
            self._did_drag = False
            if self._mode != MODE_EDIT or dragged:
                return
            if event.inaxes != self.ax or press is None:
                return
            # ensure hotbar target is active
            if hasattr(self, "_hotbar_names"):
                self._set_target(self._hotbar_names[self._hotbar_slot])
            self._handle_voxel_click(event, force_tool=TOOL_PLACE)
            return

        if btn != 1:
            return
        was_orbit = self._orbiting
        self._orbiting = False
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
''',
    "release right-place",
)

# ---- 11) _handle_voxel_click accepts force_tool ----
must(
    '''    def _handle_voxel_click(self, event) -> None:
        if self.current_voxels is None:
            return
        if not self._face_meta:
            self.render_voxels(self.current_voxels, orbit_lod=False)
        meta = pick_nearest_face(self.ax, (float(event.x), float(event.y)), self._face_meta)
        if meta is None:
            self._set_status("未点到外壳面，换个角度再点")
            return
        tool = self._voxel_tool
''',
    '''    def _handle_voxel_click(self, event, *, force_tool: str | None = None) -> None:
        if self.current_voxels is None:
            return
        if not self._face_meta:
            self.render_voxels(self.current_voxels, orbit_lod=False)
        meta = pick_nearest_face(self.ax, (float(event.x), float(event.y)), self._face_meta)
        if meta is None:
            self._set_status("未点到外壳面，换个角度再点")
            return
        tool = force_tool or self._voxel_tool
''',
    "force_tool param",
)

# ---- 12) keys 1-9 + bind on root ----
must(
    '''        widget.bind("<Control-v>", lambda e: (self.on_paste_at_selection(), "break")[1])
        self.bind("<Control-z>", lambda e: self.on_undo())
        self.bind("<Control-y>", lambda e: self.on_redo())
        try:
            widget.focus_set()
        except Exception:
            pass
''',
    '''        widget.bind("<Control-v>", lambda e: (self.on_paste_at_selection(), "break")[1])
        self.bind("<Control-z>", lambda e: self.on_undo())
        self.bind("<Control-y>", lambda e: self.on_redo())
        for d in range(1, 10):
            self.bind(str(d), lambda e, n=d: self._select_hotbar(n - 1))
            widget.bind(str(d), lambda e, n=d: self._select_hotbar(n - 1))
        try:
            widget.focus_set()
        except Exception:
            pass
''',
    "bind digits",
)

must(
    '''        if ctrl and key.lower() == "v":
            self.on_paste_at_selection()
            return

        if self._mode != MODE_EDIT or self._sel_pos is None:
            return
''',
    '''        if ctrl and key.lower() == "v":
            self.on_paste_at_selection()
            return

        if (not ctrl) and key in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
            self._select_hotbar(int(key) - 1)
            return

        if self._mode != MODE_EDIT or self._sel_pos is None:
            return
''',
    "key digits handler",
)

# ---- 13) after successful place/break, update hint ----
# light touch: _after_voxel_edit — find it
if "def _after_voxel_edit" in text:
    must(
        "    def _after_voxel_edit(self, msg: str) -> None:\n",
        "    def _after_voxel_edit(self, msg: str) -> None:\n"
        "        self._update_workbench_hint()\n",
        "after_voxel_edit hint",
    )
else:
    print("WARN no _after_voxel_edit")

# ---- ensure _draw_empty also redraws crosshair ----
# Find body of _draw_empty
import re
m = re.search(r"def _draw_empty\(self\) -> None:\n(?:.*\n)*?        self\.canvas\.draw\(\)\n", text)
if not m:
    # try draw_idle
    m = re.search(r"def _draw_empty\(self\) -> None:\n(?:.*\n){1,40}", text)
    print("draw_empty snippet:\n", m.group(0)[:500] if m else "NONE")
else:
    old = m.group(0)
    if "_redraw_crosshair" not in old:
        new = old.replace("        self.canvas.draw()\n", "        self._redraw_crosshair()\n        self.canvas.draw()\n")
        text = text.replace(old, new, 1)
        print("OK draw_empty crosshair")

if text == orig:
    raise SystemExit("No changes applied")
APP.write_text(text, encoding="utf-8")
print("WROTE", APP, "delta chars", len(text) - len(orig))
# syntax check
compile(text, str(APP), "exec")
print("SYNTAX_OK")
