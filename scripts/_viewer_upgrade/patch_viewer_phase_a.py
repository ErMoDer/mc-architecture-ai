# -*- coding: utf-8 -*-
"""Phase A full patch for viewer_app.py (line-based surgery)."""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(r"E:\ai agent\mc-architecture-ai\scripts\viewer_app.py")
text = APP.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)

def find_line(substr: str, start: int = 0) -> int:
    for i in range(start, len(lines)):
        if substr in lines[i]:
            return i
    raise SystemExit(f"not found: {substr!r}")

# ========== 1) imports ==========
i0 = find_line("from src.app.viewer_voxel_tools import (")
i1 = find_line(")", i0)
new_imp = '''from src.app.viewer_voxel_tools import (
    BRUSH_PRESETS,
    TOOL_BREAK,
    TOOL_MOVE,
    TOOL_PAINT,
    TOOL_PLACE,
    TOOL_SELECT,
    UndoStack,
    VoxelClipboard,
    apply_box_fill,
    apply_break,
    apply_break_brush,
    apply_move,
    apply_paint,
    apply_paint_brush,
    apply_place,
    apply_place_brush,
    copy_region,
    cut_region,
    nudge,
    paste_region,
    pick_nearest_face,
    place_pos_from_face,
)
'''
lines[i0 : i1 + 1] = [new_imp]

# ========== 2) state ==========
# re-find after mutation
text = "".join(lines)
lines = text.splitlines(keepends=True)
i = find_line("self._undo_voxels: np.ndarray | None = None")
lines[i] = "        self._undo_stack = UndoStack(max_depth=32)\n"
# insert extra state after _sel_pos / _move_src
i_sel = find_line("self._sel_pos: tuple[int, int, int] | None = None")
lines.insert(i_sel + 1, "        self._sel_corner_b: tuple[int, int, int] | None = None  # box second corner\n")
i_move = find_line("self._move_src: tuple[int, int, int] | None = None")
extra = (
    "        self._box_anchor: tuple[int, int, int] | None = None  # box-fill first click\n"
    "        self._clipboard = VoxelClipboard()\n"
    "        self._brush_radius = 0  # 0=1x1, 1=3x3x3, 2=5x5x5\n"
    "        self._brush_shape = \"cube\"\n"
)
lines.insert(i_move + 1, extra)

# ========== 3) UI: insert brush/clipboard after row=5 hint ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
# Find ).grid(row=5 ... pady=(0, 6)) in _build_right_edit
hint_grid = None
for i, ln in enumerate(lines):
    if 'row=5, column=0, sticky="w", padx=14, pady=(0, 6)' in ln:
        hint_grid = i
        break
if hint_grid is None:
    raise SystemExit("hint grid row=5 not found")
# Update hint text line (a few lines above)
for j in range(hint_grid, hint_grid - 10, -1):
    if 'text="' in lines[j] and "wraplength" not in lines[j]:
        lines[j] = (
            '            text="放置/涂改用下方「目标」；笔刷/盒填对破坏·放置·涂改生效。",\n'
        )
        break
lines[hint_grid] = lines[hint_grid].replace("pady=(0, 6)", "pady=(0, 4)")

# Find bulk header row=6 and bump all rows from block_list onward
bulk = None
for i, ln in enumerate(lines):
    if 'CTkLabel(right' in ln and 'weight="bold"' in ln and i > hint_grid and i < hint_grid + 20:
        bulk = i
        break
if bulk is None:
    raise SystemExit("bulk label not found")
# bulk is two lines: CTkLabel... and row=6...
# Insert brush+clip BEFORE bulk, then change bulk to row=8 and bump later rows in function

ui_insert = '''
        brush_row = ctk.CTkFrame(right, fg_color="transparent")
        brush_row.grid(row=6, column=0, sticky="ew", padx=10, pady=2)
        ctk.CTkLabel(brush_row, text="笔刷").pack(side="left", padx=(4, 6))
        self.brush_var = ctk.StringVar(value="小")
        self.brush_seg = ctk.CTkSegmentedButton(
            brush_row,
            values=["小", "中", "大"],
            variable=self.brush_var,
            command=self._on_brush_change,
            width=150,
            height=26,
            font=ctk.CTkFont(size=12),
        )
        self.brush_seg.pack(side="left", padx=2)
        self.box_fill_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            brush_row,
            text="盒填",
            variable=self.box_fill_var,
            command=self._on_box_fill_toggle,
            width=60,
        ).pack(side="left", padx=(8, 2))

        clip_row = ctk.CTkFrame(right, fg_color="transparent")
        clip_row.grid(row=7, column=0, sticky="ew", padx=10, pady=2)
        ctk.CTkButton(clip_row, text="复制", width=60, height=26, command=self.on_copy_selection).pack(
            side="left", padx=2
        )
        ctk.CTkButton(clip_row, text="剪切", width=60, height=26, command=self.on_cut_selection).pack(
            side="left", padx=2
        )
        ctk.CTkButton(clip_row, text="粘贴", width=60, height=26, command=self.on_paste_at_selection).pack(
            side="left", padx=2
        )
        self.clip_label = ctk.CTkLabel(clip_row, text="剪贴板：空", anchor="w")
        self.clip_label.pack(side="left", padx=6)

'''
# Insert before bulk label line
lines.insert(bulk, ui_insert)

# Now bump row numbers in _build_right_edit for old widgets that were >=6
# Find function bounds again
text = "".join(lines)
lines = text.splitlines(keepends=True)
fn_start = find_line("def _build_right_edit")
fn_end = find_line("def _on_mode_change")
# Bulk header should become row=8; everything that was row>=6 (except our new 5,6,7) needs +2
# After insert, old row=6 bulk still says row=6 — change it and bump 7+
protected_substrings = (
    "brush_row.grid(row=6",
    "clip_row.grid(row=7",
    'pady=(0, 4)',  # hint row=5
)
for i in range(fn_start, fn_end):
    ln = lines[i]
    if any(p in ln for p in protected_substrings):
        continue
    # also protect the new hint row=5
    if "row=5," in ln and "pady=(0, 4)" in ln:
        continue
    m = re.search(r"row=(\d+)", ln)
    if not m:
        continue
    n = int(m.group(1))
    # Only bump rows that belong to the old layout (>=6)
    if n >= 6:
        lines[i] = re.sub(r"row=\d+", f"row={n + 2}", ln, count=1)

# ========== 4) undo/redo buttons ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
iu = find_line("self.undo_btn = ctk.CTkButton")
# find undo pack line
ip = find_line('self.undo_btn.pack', iu)
# maybe shrink widths on previous lines — optional
redo_lines = (
    '        self.redo_btn = ctk.CTkButton(btn_row, text="重做", command=self.on_redo, width=60, state="disabled")\n'
    '        self.redo_btn.pack(side="left", padx=2)\n'
)
lines.insert(ip + 1, redo_lines)
# shrink undo width if present
if "width=70" in lines[iu]:
    lines[iu] = lines[iu].replace("width=70", "width=60")

# ========== 5) load_and_show reset ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
i = find_line("self._undo_voxels = None")
# first occurrence in load_and_show
# replace block
block_old_start = i
# Expect nearby lines
assert "_undo_voxels" in lines[i]
lines[i] = "        self._undo_stack.clear()\n"
# insert clears for new state after _sel_pos = None
i_sel = find_line("self._sel_pos = None", i)
lines.insert(i_sel + 1, "        self._sel_corner_b = None\n        self._box_anchor = None\n")
# undo_btn.configure disabled -> refresh
i_btn = find_line("self.undo_btn.configure(state=\"disabled\")", i)
lines[i_btn] = "        self._refresh_undo_redo_buttons()\n"

# ========== 6) on_replace ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
i = find_line("self._undo_voxels = self.current_voxels.copy()")
# This should be on_replace (first remaining after load)
lines[i] = "        self._push_undo()\n"
# find undo clear on n==0
i2 = find_line("self._undo_voxels = None", i)
lines[i2] = "            self._undo_stack._undo.pop()  # discard empty push\n"
i3 = find_line('self.undo_btn.configure(state="normal")', i)
lines[i3] = "        self._refresh_undo_redo_buttons()\n"

# ========== 7) Replace on_undo entirely + insert on_redo ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
i_undo = find_line("def on_undo(self)")
i_next = find_line("def on_save_as", i_undo)
new_undo = '''    def on_undo(self) -> None:
        if self.current_voxels is None or not self._undo_stack.can_undo():
            self._set_status("没有可撤销的操作")
            return
        restored = self._undo_stack.undo(self.current_voxels)
        if restored is None:
            self._set_status("没有可撤销的操作")
            return
        self.current_voxels = restored
        self._dirty = True
        self._source_id = None
        self.source_label.configure(text="源方块：未选择")
        self.source_label_left.configure(text="源方块：未选择")
        self._refresh_undo_redo_buttons()
        self._rebuild_block_list()
        self._update_info_panel()
        self.render_voxels(self.current_voxels)
        self._set_status(
            f"已撤销（还可撤 {self._undo_stack.undo_len}，重做 {self._undo_stack.redo_len}）"
        )

    def on_redo(self) -> None:
        if self.current_voxels is None or not self._undo_stack.can_redo():
            self._set_status("没有可重做的操作")
            return
        restored = self._undo_stack.redo(self.current_voxels)
        if restored is None:
            self._set_status("没有可重做的操作")
            return
        self.current_voxels = restored
        self._dirty = True
        self._refresh_undo_redo_buttons()
        self._rebuild_block_list()
        self._update_info_panel()
        self.render_voxels(self.current_voxels)
        self._set_status(
            f"已重做（还可撤 {self._undo_stack.undo_len}，重做 {self._undo_stack.redo_len}）"
        )

'''
lines[i_undo:i_next] = [new_undo]

# ========== 8) save_as / overwrite clear ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
# replace remaining _undo_voxels = None + undo_btn disabled pairs
i = 0
while True:
    try:
        i = find_line("self._undo_voxels = None", i)
    except SystemExit:
        break
    lines[i] = "        self._undo_stack.clear()\n"
    # if next few lines have undo_btn disabled, replace
    for k in range(i, min(i + 3, len(lines))):
        if 'self.undo_btn.configure(state="disabled")' in lines[k]:
            lines[k] = "        self._refresh_undo_redo_buttons()\n"
    i += 1

# ========== 9) Helpers + rewrite _handle_voxel_click + copy/cut/paste + keys ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
i_tool = find_line("def _on_voxel_tool_change")
helpers = '''
    def _push_undo(self) -> None:
        """Snapshot current voxels before a mutating edit."""
        if self.current_voxels is None:
            return
        self._undo_stack.push(self.current_voxels)

    def _refresh_undo_redo_buttons(self) -> None:
        if hasattr(self, "undo_btn"):
            self.undo_btn.configure(
                state=("normal" if self._undo_stack.can_undo() else "disabled")
            )
        if hasattr(self, "redo_btn"):
            self.redo_btn.configure(
                state=("normal" if self._undo_stack.can_redo() else "disabled")
            )

    def _refresh_clip_label(self) -> None:
        if not hasattr(self, "clip_label"):
            return
        if self._clipboard.empty():
            self.clip_label.configure(text="剪贴板：空")
        else:
            sx, sy, sz = self._clipboard.size or (0, 0, 0)
            self.clip_label.configure(
                text=f"剪贴板：{sx}×{sy}×{sz} ({self._clipboard.non_air})"
            )

    def _on_brush_change(self, value: str) -> None:
        self._brush_radius = int(BRUSH_PRESETS.get(value, 0))
        self._set_status(f"笔刷：{value}（半径 {self._brush_radius}）")

    def _on_box_fill_toggle(self) -> None:
        self._box_anchor = None
        on = bool(self.box_fill_var.get()) if hasattr(self, "box_fill_var") else False
        self._set_status("盒填：开 — 点两次对角" if on else "盒填：关 — 用笔刷半径")

    def _after_voxel_edit(self, msg: str) -> None:
        self._dirty = True
        self._refresh_undo_redo_buttons()
        self._rebuild_block_list()
        self._update_info_panel()
        if hasattr(self, "sel_pos_label") and self._sel_pos is not None:
            extra = f" → {self._sel_corner_b}" if self._sel_corner_b is not None else ""
            self.sel_pos_label.configure(text=f"选中：{self._sel_pos}{extra}")
        if self.current_voxels is not None:
            self.render_voxels(self.current_voxels)
        self._set_status(msg)

    def on_copy_selection(self) -> None:
        if self.current_voxels is None or self._sel_pos is None:
            self._set_status("请先用「选择」点选（或选两角）")
            return
        self._clipboard = copy_region(self.current_voxels, self._sel_pos, self._sel_corner_b)
        self._refresh_clip_label()
        if self._clipboard.empty():
            self._set_status("复制失败：区域为空")
            return
        self._set_status(
            f"已复制 {self._clipboard.size}，non_air={self._clipboard.non_air}"
        )

    def on_cut_selection(self) -> None:
        if self.current_voxels is None or self._sel_pos is None:
            self._set_status("请先用「选择」点选（或选两角）")
            return
        self._push_undo()
        self._clipboard = cut_region(self.current_voxels, self._sel_pos, self._sel_corner_b)
        if self._clipboard.empty():
            self._undo_stack._undo.pop()
            self._set_status("剪切失败：区域为空")
            return
        self._sel_pos = None
        self._sel_corner_b = None
        self._refresh_clip_label()
        self._after_voxel_edit(
            f"已剪切 {self._clipboard.size}，non_air={self._clipboard.non_air}"
        )

    def on_paste_at_selection(self) -> None:
        if self.current_voxels is None:
            self._set_status("请先加载建筑")
            return
        if self._clipboard.empty():
            self._set_status("剪贴板为空，请先复制/剪切")
            return
        dest = self._sel_pos
        if dest is None:
            self._set_status("请先选择粘贴角点（选择工具点一下）")
            return
        self._push_undo()
        n = paste_region(self.current_voxels, self._clipboard, dest, mode="overlay")
        if n == 0:
            self._undo_stack._undo.pop()
            self._set_status("粘贴无变化（越界或全空）")
            return
        self._after_voxel_edit(f"已粘贴 {n} 格到 {dest}")

'''
lines.insert(i_tool, helpers)

# ========== 10) Rewrite _handle_voxel_click ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
i_h = find_line("def _handle_voxel_click")
i_nudge = find_line("def on_nudge_selection", i_h)
new_handle = '''    def _handle_voxel_click(self, event) -> None:
        if self.current_voxels is None:
            return
        if not self._face_meta:
            self.render_voxels(self.current_voxels, orbit_lod=False)
        meta = pick_nearest_face(self.ax, (float(event.x), float(event.y)), self._face_meta)
        if meta is None:
            self._set_status("未点到外壳面，换个角度再点")
            return
        tool = self._voxel_tool
        pos = meta["voxel"]
        box_on = bool(self.box_fill_var.get()) if hasattr(self, "box_fill_var") else False

        if tool == TOOL_SELECT:
            # First click = corner A; Shift/second click = corner B for copy region
            if self._sel_pos is not None and self._sel_corner_b is None and pos != self._sel_pos:
                self._sel_corner_b = pos
            else:
                self._sel_pos = pos
                self._sel_corner_b = None
            bid = int(meta["bid"])
            name = short_block_name(self.palette.get(bid, str(bid)))
            extra = f" → {self._sel_corner_b}" if self._sel_corner_b else ""
            self.sel_pos_label.configure(text=f"选中：{self._sel_pos}{extra} · {name}")
            self._select_source(bid, self.palette.get(bid, str(bid)))
            self.render_voxels(self.current_voxels)
            self._set_status(f"选中 {self._sel_pos}{extra} ({name})")
            return

        # Box fill: two clicks for break/place/paint
        if box_on and tool in (TOOL_BREAK, TOOL_PLACE, TOOL_PAINT):
            if self._box_anchor is None:
                if tool in (TOOL_PLACE, TOOL_PAINT):
                    tid = self._parse_target_id()
                    if tid is None:
                        self._set_status("盒填前请先选目标方块")
                        return
                    anchor = place_pos_from_face(meta) if tool == TOOL_PLACE else pos
                else:
                    anchor = pos
                self._box_anchor = anchor
                self._sel_pos = anchor
                self.sel_pos_label.configure(text=f"盒填角点 A：{anchor}，再点对角")
                self._set_status(f"盒填：已设角点 {anchor}，再点另一个角")
                return
            corner_a = self._box_anchor
            self._box_anchor = None
            if tool == TOOL_PLACE:
                corner_b = place_pos_from_face(meta)
                tid = self._parse_target_id()
                if tid is None:
                    self._set_status("请先选目标方块")
                    return
                self._push_undo()
                n = apply_box_fill(self.current_voxels, corner_a, corner_b, tid, mode="place")
                msg = f"盒填放置 {n} 格 {corner_a}→{corner_b}"
            elif tool == TOOL_PAINT:
                corner_b = pos
                tid = self._parse_target_id()
                if tid is None:
                    self._set_status("请先选目标方块")
                    return
                self._push_undo()
                n = apply_box_fill(self.current_voxels, corner_a, corner_b, tid, mode="paint")
                msg = f"盒填涂改 {n} 格 {corner_a}→{corner_b}"
            else:
                corner_b = pos
                self._push_undo()
                n = apply_box_fill(self.current_voxels, corner_a, corner_b, 0, mode="break")
                msg = f"盒填破坏 {n} 格 {corner_a}→{corner_b}"
            if n == 0:
                self._undo_stack._undo.pop()
                self._set_status(msg + "（无变化）")
                return
            self._sel_pos = corner_a
            self._sel_corner_b = corner_b
            self._after_voxel_edit(msg)
            return

        # Brush / single for break/place/paint; move unchanged
        self._push_undo()
        changed_n = 0
        msg = ""
        r = int(getattr(self, "_brush_radius", 0) or 0)
        shape = getattr(self, "_brush_shape", "cube")

        if tool == TOOL_BREAK:
            changed_n = apply_break_brush(self.current_voxels, pos, r, shape=shape)
            msg = f"破坏 {pos} ×{changed_n}" if changed_n else "此处无可破坏"
            if changed_n:
                self._sel_pos = None
        elif tool == TOOL_PLACE:
            tid = self._parse_target_id()
            if tid is None:
                self._undo_stack._undo.pop()
                self._set_status("放置前请先选目标方块")
                return
            dst = place_pos_from_face(meta)
            changed_n = apply_place_brush(self.current_voxels, dst, tid, r, shape=shape)
            msg = f"放置 {dst} ×{changed_n}" if changed_n else f"无法放置到 {dst}（越界或已被占）"
            if changed_n:
                self._sel_pos = dst
        elif tool == TOOL_PAINT:
            tid = self._parse_target_id()
            if tid is None:
                self._undo_stack._undo.pop()
                self._set_status("涂改前请先选目标方块")
                return
            changed_n = apply_paint_brush(self.current_voxels, pos, tid, r, shape=shape)
            msg = f"涂改 {pos} ×{changed_n}" if changed_n else "涂改无变化"
            if changed_n:
                self._sel_pos = pos
        elif tool == TOOL_MOVE:
            self._undo_stack._undo.pop()  # move uses its own push timing
            if self._move_src is None:
                self._move_src = pos
                self._sel_pos = pos
                self.sel_pos_label.configure(text=f"移动：已抓取 {pos}，再点目标外壳面")
                self.render_voxels(self.current_voxels)
                self._set_status(f"已抓取 {pos}，再点目标位置")
                return
            dst = place_pos_from_face(meta)
            self._push_undo()
            ok = apply_move(self.current_voxels, self._move_src, dst)
            msg = f"移动 {self._move_src} → {dst}" if ok else "移动失败（目标被占或越界）"
            if ok:
                self._sel_pos = dst
                changed_n = 1
            self._move_src = None
            if not ok:
                self._undo_stack._undo.pop()
                self._set_status(msg)
                return
            self._after_voxel_edit(msg)
            return
        else:
            self._undo_stack._undo.pop()
            return

        if not changed_n:
            self._undo_stack._undo.pop()
            self._set_status(msg)
            return
        self._after_voxel_edit(msg)

'''
lines[i_h:i_nudge] = [new_handle]

# ========== 11) on_nudge_selection ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
i_n = find_line("def on_nudge_selection")
i_k = find_line("def _on_canvas_key", i_n)
new_nudge = '''    def on_nudge_selection(self, delta: tuple[int, int, int]) -> None:
        if self.current_voxels is None or self._sel_pos is None:
            self._set_status("先用「选择」点选一个方块")
            return
        self._push_undo()
        new_pos = nudge(self.current_voxels, self._sel_pos, delta)
        if new_pos is None:
            self._undo_stack._undo.pop()
            self._set_status("微调失败（越界或目标被占）")
            return
        self._sel_pos = new_pos
        self._after_voxel_edit(f"已微调到 {new_pos}")

'''
lines[i_n:i_k] = [new_nudge]

# ========== 12) key handler with Ctrl+Z/Y/C/X/V ==========
text = "".join(lines)
lines = text.splitlines(keepends=True)
i_k = find_line("def _on_canvas_key")
i_main = find_line("def main()", i_k)
new_key = '''    def _on_canvas_key(self, event) -> None:
        key = getattr(event, "keysym", "") or ""
        state = int(getattr(event, "state", 0) or 0)
        ctrl = bool(state & 0x4)  # Control on Windows Tk

        if ctrl and key.lower() == "z":
            self.on_undo()
            return
        if ctrl and key.lower() in ("y", "Z"):  # Ctrl+Y redo; some layouts use Shift
            self.on_redo()
            return
        if ctrl and key.lower() == "y":
            self.on_redo()
            return
        if ctrl and key.lower() == "c":
            self.on_copy_selection()
            return
        if ctrl and key.lower() == "x":
            self.on_cut_selection()
            return
        if ctrl and key.lower() == "v":
            self.on_paste_at_selection()
            return

        if self._mode != MODE_EDIT or self._sel_pos is None:
            return
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
            self._push_undo()
            if apply_break(self.current_voxels, self._sel_pos):
                self._sel_pos = None
                if hasattr(self, "sel_pos_label"):
                    self.sel_pos_label.configure(text="选中：无")
                self._after_voxel_edit("已删除选中方块")
            else:
                self._undo_stack._undo.pop()
            return
        delta = mapping.get(key)
        if delta is not None:
            self.on_nudge_selection(delta)

'''
lines[i_k:i_main] = [new_key]

# Also bind Control keys on the root / canvas widget
text = "".join(lines)
lines = text.splitlines(keepends=True)
i_bind = find_line("def _bind_canvas_interactions")
# find widget.bind Key line and add more binds after
i_keybind = find_line('widget.bind("<Key>"', i_bind)
extra_binds = '''        widget.bind("<Control-z>", lambda e: (self.on_undo(), "break")[1])
        widget.bind("<Control-y>", lambda e: (self.on_redo(), "break")[1])
        widget.bind("<Control-Z>", lambda e: (self.on_undo(), "break")[1])
        widget.bind("<Control-c>", lambda e: (self.on_copy_selection(), "break")[1])
        widget.bind("<Control-x>", lambda e: (self.on_cut_selection(), "break")[1])
        widget.bind("<Control-v>", lambda e: (self.on_paste_at_selection(), "break")[1])
        self.bind("<Control-z>", lambda e: self.on_undo())
        self.bind("<Control-y>", lambda e: self.on_redo())
'''
lines.insert(i_keybind + 1, extra_binds)

# ========== 13) Fix any leftover _undo_voxels ==========
text = "".join(lines)
left = []
for i, ln in enumerate(text.splitlines()):
    if "_undo_voxels" in ln:
        left.append((i + 1, ln.strip()))
if left:
    print("WARNING leftover _undo_voxels:")
    for item in left:
        print(" ", item)

# Fix _bind_scheme or other clears that still mention undo_voxels
# Manual fix remaining
new_lines = []
for ln in text.splitlines(keepends=True):
    if "self._undo_voxels = None" in ln:
        ln = ln.replace("self._undo_voxels = None", "self._undo_stack.clear()")
    if 'self.undo_btn.configure(state="disabled")' in ln and "_refresh_undo_redo" not in ln:
        ln = ln.replace(
            'self.undo_btn.configure(state="disabled")',
            "self._refresh_undo_redo_buttons()",
        )
    if 'self.undo_btn.configure(state="normal")' in ln and "_refresh_undo_redo" not in ln:
        ln = ln.replace(
            'self.undo_btn.configure(state="normal")',
            "self._refresh_undo_redo_buttons()",
        )
    new_lines.append(ln)

APP.write_text("".join(new_lines), encoding="utf-8")
print("wrote", APP, "lines", len(new_lines))

# syntax check
import ast
ast.parse(APP.read_text(encoding="utf-8"))
print("AST OK")