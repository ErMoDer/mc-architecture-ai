# -*- coding: utf-8 -*-
import sys
from pathlib import Path
ROOT = Path(r"E:\ai agent\mc-architecture-ai")
sys.path.insert(0, str(ROOT))
import numpy as np
from src.app.viewer_voxel_tools import (
    UndoStack, VoxelClipboard, apply_break_brush, apply_place_brush,
    apply_paint_brush, apply_box_fill, copy_region, cut_region, paste_region,
    BRUSH_PRESETS,
)

v = np.zeros((32, 32, 32), dtype=np.int32)
v[10:15, 10:12, 10:15] = 3
stack = UndoStack(20)
stack.push(v)
n = apply_break_brush(v, (12, 10, 12), radius=1)
assert n > 0
restored = stack.undo(v)
assert restored is not None
v[:] = restored
assert int((v > 0).sum()) == 5 * 2 * 5
stack.push(v)
n2 = apply_place_brush(v, (20, 20, 20), 7, radius=0)
assert n2 == 1
redone = stack.redo(v)  # should be None? we pushed after undo so redo cleared
# after undo, redo had the broken state; then we overwrote v and pushed again clearing redo
assert not stack.can_redo()

# brush presets
assert BRUSH_PRESETS["小"] == 0 and BRUSH_PRESETS["中"] == 1 and BRUSH_PRESETS["大"] == 2

# box fill
stack.push(v)
n3 = apply_box_fill(v, (1, 1, 1), (3, 2, 4), 9, mode="place")
assert n3 == 3 * 2 * 4

# clipboard
clip = copy_region(v, (1, 1, 1), (3, 2, 4))
assert clip.non_air == n3
stack.push(v)
cut_region(v, (1, 1, 1), (3, 2, 4))
assert int(v[1:4, 1:3, 1:5].sum()) == 0
n4 = paste_region(v, clip, (5, 5, 5), mode="overlay")
assert n4 == n3
print("SMOKE_OK", "non_air", int((v > 0).sum()), "undo_len", stack.undo_len)