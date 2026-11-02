# -*- coding: utf-8 -*-
"""Phase A patch for scripts/viewer_app.py — undo stack, brush, clipboard."""
from __future__ import annotations

from pathlib import Path

APP = Path(r"E:\ai agent\mc-architecture-ai\scripts\viewer_app.py")
text = APP.read_text(encoding="utf-8")
orig = text

# --- 1) Expand imports ---
old_imp = '''from src.app.viewer_voxel_tools import (
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
)'''

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
)'''

if old_imp not in text:
    raise SystemExit("IMPORT BLOCK not found")
text = text.replace(old_imp, new_imp, 1)

# --- 2) State vars: undo stack + brush + clipboard + box corners ---
old_state = '''        self.current_voxels: np.ndarray | None = None
        self.current_path: Path | None = None
        self._undo_voxels: np.ndarray | None = None
        self._dirty = False
        self._generating = False
        self._source_id: int | None = None
        self._block_buttons: list = []
        self._last_render_info: dict = {}
        # style_perf_var set below (default True for orbit)
        # Y-slice: show only voxels with y <= value (32 = full for 32^3).
        self.y_slice_var = tk.IntVar(value=32)
        self._mode = MODE_BROWSE
        self._design_image_path: Path | None = None
        self._last_design_spec: DesignSpec | None = None
        self._scheme_slug: str | None = None
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
        self.style_perf_var = tk.BooleanVar(value=True)'''

new_state = '''        self.current_voxels: np.ndarray | None = None
        self.current_path: Path | None = None
        self._undo_stack = UndoStack(max_depth=32)
        self._dirty = False
        self._generating = False
        self._source_id: int | None = None
        self._block_buttons: list = []
        self._last_render_info: dict = {}
        # style_perf_var set below (default True for orbit)
        # Y-slice: show only voxels with y <= value (32 = full for 32^3).
        self.y_slice_var = tk.IntVar(value=32)
        self._mode = MODE_BROWSE
        self._design_image_path: Path | None = None
        self._last_design_spec: DesignSpec | None = None
        self._scheme_slug: str | None = None
        # MCBlock-like voxel tools + orbit LOD
        self._voxel_tool = TOOL_SELECT
        self._sel_pos: tuple[int, int, int] | None = None
        self._sel_corner_b: tuple[int, int, int] | None = None  # box second corner
        self._move_src: tuple[int, int, int] | None = None
        self._box_anchor: tuple[int, int, int] | None = None  # box-fill first click
        self._clipboard = VoxelClipboard()
        self._brush_radius = 0  # 0=1x1, 1=3x3x3, 2=5x5x5
        self._brush_shape = "cube"
        self._face_meta: list = []
        self._orbiting = False
        self._orbit_lod_active = False
        self._press_xy: tuple[float, float] | None = None
        self._did_drag = False
        self._draw_edges_var = tk.BooleanVar(value=False)
        # Default ON for snappier orbit on 3k-10k block houses (RTX 3050 laptop).
        self.style_perf_var = tk.BooleanVar(value=True)'''

if old_state not in text:
    raise SystemExit("STATE BLOCK not found")
text = text.replace(old_state, new_state, 1)

# --- 3) Edit panel UI: insert brush + clipboard after nudge hint (row 5), shift later rows ---
# We'll insert new UI between sel_pos_label block and bulk replace section.

old_ui_hint = '''        ctk.CTkLabel(
            right,
            text="放置/涂改用下方「目标」方块；旋转时自动降精度加速。",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=5, column=0, sticky="w", padx=14, pady=(0, 6))

        ctk.CTkLabel(right, text="方块批量替换", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=6, column=0, sticky="w", padx=14, pady=(6, 2)
        )'''

# The Chinese might be corrupted in our view - let's find by unique English-free markers
# Use a more robust approach: find by row markers around voxel tools

marker_after_nudge = 'nudge_row.grid(row=4, column=0, sticky="ew", padx=10, pady=2)'
if marker_after_nudge not in text:
    raise SystemExit("nudge_row marker not found")

# Find the bulk-replace label after nudge - search for unique pattern
idx_nudge = text.find(marker_after_nudge)
# Find next CTkLabel with row=5 after nudge
# We'll locate the section between row=5 hint and row=6 bulk header by line scanning

lines = text.splitlines(keepends=True)
# Find line index of nudge_row.grid
nudge_i = None
bulk_i = None
for i, ln in enumerate(lines):
    if 'nudge_row.grid(row=4' in ln:
        nudge_i = i
    if nudge_i is not None and bulk_i is None and 'row=6' in ln and 'weight="bold"' in ln:
        # the bulk replace label
        bulk_i = i
        break

if nudge_i is None or bulk_i is None:
    raise SystemExit(f"UI anchors not found nudge={nudge_i} bulk={bulk_i}")

# Find start of row=5 hint label (the CTkLabel before bulk)
hint_start = None
for i in range(bulk_i - 1, nudge_i, -1):
    if 'ctk.CTkLabel(' in lines[i]:
        hint_start = i
        break
if hint_start is None:
    raise SystemExit("hint label start not found")

# Replace from hint_start through the blank line before bulk with new UI block
# Keep bulk label but we'll renumber rows 6+ by +6 for the new widgets

new_ui_block = '''        ctk.CTkLabel(
            right,
            text="放置/涂改用下方「目标」；笔刷/盒填对破坏·放置·涂改生效。",
            wraplength=280,
            justify="left",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=11),
        ).grid(row=5, column=0, sticky="w", padx=14, pady=(0, 4))

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

        ctk.CTkLabel(right, text="方块批量替换", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=8, column=0, sticky="w", padx=14, pady=(6, 2)
        )
'''

# Drop old hint through bulk label (inclusive of bulk label line - we re-add it)
# Find end of bulk label statement (ends with ))
end_bulk = bulk_i
# the bulk label is multi-line: find closing )
while end_bulk < len(lines) and not (lines[end_bulk].rstrip().endswith(')') and 'grid(' in ''.join(lines[bulk_i:end_bulk+1])):
    end_bulk += 1
# Actually bulk label from earlier search IS the grid line of the label. Look backwards for CTkLabel start of bulk.
bulk_label_start = bulk_i
for i in range(bulk_i, hint_start, -1):
    if 'ctk.CTkLabel(' in lines[i] and i != hint_start:
        # might be the bulk one if it's right before row=6 grid
        pass
# Simpler: delete from hint_start to bulk_i's grid line inclusive, then insert new block
# Find the CTkLabel that contains row=6 - that's bulk header
# Going back from bulk_i to find its CTkLabel(
bs = bulk_i
while bs > hint_start and 'ctk.CTkLabel(' not in lines[bs]:
    bs -= 1

# Delete hint_start .. bulk_i (inclusive), insert new_ui_block
new_lines = lines[:hint_start] + [new_ui_block] + lines[bulk_i + 1:]
text = ''.join(new_lines)

# --- 4) Renumber subsequent grid rows in _build_right_edit that were 7..26 -> 9..28 ---
# After our insert, old rows 7+ need +2 (we added 2 row slots: brush=6, clip=7, bulk=8; old bulk was 6).
# Old: hint5, bulk6, list7, source8, tgt_lbl9, filter10, combo11, quick_lbl12, quick13, btn14, save15, ver_lbl16, ver17, note18, bom19, bom_note20, export21, scheme_lbl22, scheme_label23, srow124, srow225, srow326
# New: hint5, brush6, clip7, bulk8, list9, source10, ... so from old row>=7 add +2; old row 6 was replaced.
# Current text still has old row numbers for list onwards (7,8,...). Bump them.

def bump_rows_in_build_right(src: str) -> str:
    """Bump grid row=N for N>=7 inside _build_right_edit until _on_mode_change."""
    start = src.find("def _build_right_edit")
    end = src.find("def _on_mode_change")
    if start < 0 or end < 0:
        raise SystemExit("build_right / mode_change not found")
    head, mid, tail = src[:start], src[start:end], src[end:]
    # Only bump after our new clip_row (row=7) section — i.e. old widgets that still say row=7+
    # Careful not to bump brush_row row=6 or clip_row row=7 or new bulk row=8.
    # Strategy: bump row=26 down to row=7 in reverse order, but skip lines that are part of new block.
    # Mark new block lines by unique strings.
    protected = {
        'brush_row.grid(row=6',
        'clip_row.grid(row=7',
        'row=8, column=0, sticky="w", padx=14, pady=(6, 2)',  # new bulk header
        'row=5, column=0, sticky="w", padx=14, pady=(0, 4)',
    }
    out = []
    for ln in mid.splitlines(keepends=True):
        skip = any(p in ln for p in protected)
        if not skip:
            import re
            def repl(m):
                n = int(m.group(1))
                if n >= 7:
                    return f"row={n + 2}"
                return m.group(0)
            ln = re.sub(r"row=(\d+)", repl, ln)
        out.append(ln)
    return head + ''.join(out) + tail

text = bump_rows_in_build_right(text)

# --- 5) Undo/redo buttons ---
old_btns = '''        self.replace_btn = ctk.CTkButton(btn_row, text="一键替换", command=self.on_replace, width=100)
        self.replace_btn.pack(side="left", padx=2)
        self.undo_btn = ctk.CTkButton(btn_row, text="撤销", command=self.on_undo, width=70, state="disabled")
        self.undo_btn.pack(side="left", padx=2)'''

# Chinese may vary - find by attribute names
import re
m = re.search(
    r'self\.replace_btn = ctk\.CTkButton\(btn_row,.*?self\.undo_btn\.pack\(side="left", padx=2\)',
    text,
    re.S,
)
if not m:
    raise SystemExit("replace/undo buttons not found")
text = text[: m.start()] + '''self.replace_btn = ctk.CTkButton(btn_row, text="一键替换", command=self.on_replace, width=90)
        self.replace_btn.pack(side="left", padx=2)
        self.undo_btn = ctk.CTkButton(btn_row, text="撤销", command=self.on_undo, width=60, state="disabled")
        self.undo_btn.pack(side="left", padx=2)
        self.redo_btn = ctk.CTkButton(btn_row, text="重做", command=self.on_redo, width=60, state="disabled")
        self.redo_btn.pack(side="left", padx=2)''' + text[m.end() :]

# --- 6) Helper methods: inject before _on_voxel_tool_change ---
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
            extra = ""
            if self._sel_corner_b is not None:
                extra = f" → {self._sel_corner_b}"
            self.sel_pos_label.configure(text=f"选中：{self._sel_pos}{extra}")
        if self.current_voxels is not None:
            self.render_voxels(self.current_voxels)
        self._set_status(msg)

'''

anchor = "    def _on_voxel_tool_change(self, value: str) -> None:"
if anchor not in text:
    raise SystemExit("_on_voxel_tool_change not found")
text = text.replace(anchor, helpers + anchor, 1)

# --- 7) Replace on_undo / add on_redo ---
old_undo = '''    def on_undo(self) -> None:
        if self._undo_voxels is None:
            self._set_status("没有可撤销的操作")
            return
        self.current_voxels = self._undo_voxels
        self._undo_voxels = None
        self._dirty = True
        self.undo_btn.configure(state="disabled")
        self._source_id = None
        self.source_label.configure(text="源方块：未选择")
        self.source_label_left.configure(text="源方块：未选择")
        self._rebuild_block_list()
        self._update_info_panel()
        if self.current_voxels is not None:
            self.render_voxels(self.current_voxels)
        self._set_status("已撤销上一次替换")'''

# Match flexibly
m = re.search(r"    def on_undo\(self\) -> None:.*?(?=\n    def on_)", text, re.S)
if not m:
    raise SystemExit("on_undo not found")
text = text[: m.start()] + '''    def on_undo(self) -> None:
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
        self._set_status(f"已撤销（还可撤 {self._undo_stack.undo_len}，重做 {self._undo_stack.redo_len}）")

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
        self._set_status(f"已重做（还可撤 {self._undo_stack.undo_len}，重做 {self._undo_stack.redo_len}）")

''' + text[m.end() :]

# --- 8) Replace all _undo_voxels usages ---
# load_and_show clear
text = text.replace(
    '''        self._undo_voxels = None
        self._dirty = False
        self._source_id = None
        self._sel_pos = None
        self._move_src = None
        self._orbit_lod_active = False
        self.undo_btn.configure(state="disabled")''',
    '''        self._undo_stack.clear()
        self._dirty = False
        self._source_id = None
        self._sel_pos = None
        self._sel_corner_b = None
        self._box_anchor = None
        self._move_src = None
        self._orbit_lod_active = False
        self._refresh_undo_redo_buttons()''',
)

# on_replace
text = text.replace(
    '''        self._undo_voxels = self.current_voxels.copy()
        new_vox, n = replace_block_id(self.current_voxels, self._source_id, target_id)
        if n == 0:
            self._set_status("没有可替换的方块")
            self._undo_voxels = None
            return
        self.current_voxels = new_vox
        self._dirty = True
        self.undo_btn.configure(state="normal")''',
    '''        self._push_undo()
        new_vox, n = replace_block_id(self.current_voxels, self._source_id, target_id)
        if n == 0:
            self._undo_stack._undo.pop()  # discard empty push
            self._set_status("没有可替换的方块")
            return
        self.current_voxels = new_vox
        self._dirty = True
        self._refresh_undo_redo_buttons()''',
)

# save_as / overwrite clear undo
text = text.replace(
    '''        self._dirty = False
        self._undo_voxels = None
        self.undo_btn.configure(state="disabled")
        self.refresh_lists()''',
    '''        self._dirty = False
        self._undo_stack.clear()
        self._refresh_undo_redo_buttons()
        self.refresh_lists()''',
)
text = text.replace(
    '''        self._dirty = False
        self._undo_voxels = None
        self.undo_btn.configure(state="disabled")
        self._update_info_panel()
        self._set_status(f"已覆盖保存 {self.current_path.name}，non_air={meta['non_air']}）")''',
    '''        self._dirty = False
        self._undo_stack.clear()
        self._refresh_undo_redo_buttons()
        self._update_info_panel()
        self._set_status(f"已覆盖保存 {self.current_path.name}，non_air={meta['non_air']}）")''',
)

# Remaining _undo_voxels references — report them
left = [i + 1 for i, ln in enumerate(text.splitlines()) if "_undo_voxels" in ln]
print("remaining _undo_voxels lines:", left)

APP.write_text(text, encoding="utf-8")
print("partial patch written, bytes", APP.stat().st_size)
print("changed", text != orig)
