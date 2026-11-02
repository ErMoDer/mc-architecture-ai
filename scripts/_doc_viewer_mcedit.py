# -*- coding: utf-8 -*-
from pathlib import Path

# LAUNCH.md append
launch = Path("LAUNCH.md")
t = launch.read_text(encoding="utf-8")
marker = "## Viewer edit / performance (MCBlock-like)"
if marker not in t:
    t = t.rstrip() + """

## Viewer edit / performance (MCBlock-like)

Bar we mirrored from MCBlock preview/editor UX (not a clone):

1. **Snappy orbit** — while dragging the 3D view, mesh switches to OrbitLOD (downsample + no edges); full mesh restores on release. Camera elev/azim is preserved across rebuilds. Default **性能模式** is ON.
2. **Click modeling** (Edit mode) — tools: 选择 / 破坏 / 放置 / 涂改 / 移动. Click an exposed face in the 3D view. Place/Paint use the palette target below. Move: click grab, click again to set destination. Nudge with ±X/Y/Z buttons or arrow keys (PageUp/Down = ±Y). Delete/Backspace breaks selection.
3. Bulk replace / save / export companion / schemes unchanged.

Docs: `docs/viewer.md`.
"""
    launch.write_text(t, encoding="utf-8")
    print("LAUNCH updated")
else:
    print("LAUNCH already has section")

# docs/viewer.md
doc = Path("docs/viewer.md")
d = doc.read_text(encoding="utf-8")
if "体素工具" not in d:
    # update 方块替换 section and 已知限制
    d = d.replace(
        "### 方块替换（右侧）\n1. 列表显示当前方块名 + 数量 → 点击选源（3D 高亮）\n2. 下拉/搜索或快捷选目标 → **一键替换**\n3. **撤销**一步 / **另存为** `sample_edit_XXX` / **覆盖保存**（需确认）\n4. 替换后颜色跟新方块名走\n",
        "### 编辑 / 建模（右侧，接近 MCBlock）\n"
        "- **体素工具**：选择 / 破坏 / 放置 / 涂改 / 移动 — 在 3D 上点击外露面\n"
        "- 放置/涂改使用下方「目标」方块；移动需点两次（抓取 → 目标面旁）\n"
        "- 选中后可用 ±X/Y/Z 微调；方向键/PgUp/PgDn；Delete 删除\n"
        "- **批量替换**：列表选源 → 目标 → 一键替换（仍可用）\n"
        "- **撤销**一步 / 另存 / 覆盖 / 导出 companion / 方案 照旧\n\n"
        "### 流畅度\n"
        "- 拖转时自动 **OrbitLOD**（降采样、无描边），松手恢复完整网格；机位不跳\n"
        "- 默认勾选 **性能模式**；大体量建筑旋转更跟手\n"
        "- 根因曾是 matplotlib 每帧重绘上万三角面；现改为拖转用轻量网格\n",
    )
    d = d.replace(
        "| 编辑 | 方块替换与导出 |\n",
        "| 编辑 | 点选建模（破坏/放置/涂改/移动）+ 批量替换与导出 |\n",
    )
    d = d.replace(
        "- non_air 极大时 MC 模式仍可能较慢，可开性能模式\n",
        "- non_air 极大时仍可能较慢；拖转已用 LOD，静止精细预览仍受 matplotlib 限制（不是游戏引擎）\n"
        "- 点击拾取依赖外壳面投影，极端透视下可能点偏，换个角度即可\n",
    )
    doc.write_text(d, encoding="utf-8")
    print("viewer.md updated")
else:
    print("viewer.md already")
