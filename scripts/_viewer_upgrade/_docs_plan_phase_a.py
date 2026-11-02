# -*- coding: utf-8 -*-
from pathlib import Path
import re

root = Path(r"E:\ai agent\mc-architecture-ai")

# --- docs/viewer.md: append Phase A section (read, update key bullets) ---
viewer = (root / "docs" / "viewer.md").read_text(encoding="utf-8")
marker = "### 编辑 / 建模（右侧，接近 MCBlock）"
# Find edit section and enhance, or append Phase A notes at end before 已知限制
phase_a_note = """

## 编辑增强（Phase A · 2026-10-21）

在 matplotlib/tk 预览里对齐 MCBlock 的高价值子集（非完整体素编辑器）：

| 能力 | 用法 |
|------|------|
| **撤销/重做栈** | 深度 32；每次方块改动入栈。按钮「撤销」「重做」，或 **Ctrl+Z / Ctrl+Y** |
| **笔刷** | 小=1×1×1 / 中=3×3×3 / 大=5×5×5；对 **破坏 / 放置 / 涂改** 生效 |
| **盒填** | 勾选「盒填」后，同一工具下点两次对角，填充轴对齐盒子 |
| **复制/剪切/粘贴** | 「选择」点第一角，再点第二角定区域；复制/剪切；选粘贴角点后粘贴。快捷键 **Ctrl+C / X / V** |
| **方案 + companion** | 右侧已有：另存为方案 / 保存到方案 / 导出方案 / 导出到 companion（.litematic） |

仍保留：外壳面点选、移动（抓取→目标面）、±XYZ 微调、批量替换、OrbitLOD。

"""

if "Phase A · 2026-10-21" not in viewer:
    # insert before ## 已知限制 if present
    if "## 已知限制" in viewer:
        viewer = viewer.replace("## 已知限制", phase_a_note + "## 已知限制", 1)
    else:
        viewer += phase_a_note
    # update known limits about single undo
    viewer = viewer.replace(
        "- 撤销仅一层，未做多级撤销/重做",
        "- （已升级）撤销/重做栈深度 32；仍无体积笔刷雕刻/多层历史时间线",
    )
    if "撤销仅一层" in viewer:
        viewer = re.sub(r"- 撤销仅一层[^\n]*\n", "- 撤销/重做栈深度 32（Phase A）；无 MagicaVoxel 级雕刻\n", viewer)
    (root / "docs" / "viewer.md").write_text(viewer, encoding="utf-8")
    print("viewer.md updated")
else:
    print("viewer.md already has Phase A")

# --- LAUNCH.md ---
launch = (root / "LAUNCH.md").read_text(encoding="utf-8")
launch_add = """

## Viewer edit (Phase A · 2026-10-21)

Edit mode now has:

1. Undo/redo stack (depth 32) — buttons + Ctrl+Z / Ctrl+Y
2. Brush sizes 小/中/大 + optional 盒填 (two-click AABB) for break/place/paint
3. Copy / cut / paste region (select two corners, then paste at click) — Ctrl+C/X/V
4. Scheme save/export + 导出到 companion (.litematic) unchanged on the right panel

Docs: `docs/viewer.md`. 8h plan: `outputs/plans/plan_8h_20261021.md`.
"""
if "Phase A · 2026-10-21" not in launch:
    launch += launch_add
    (root / "LAUNCH.md").write_text(launch, encoding="utf-8")
    print("LAUNCH.md updated")
else:
    print("LAUNCH.md already has Phase A")

# --- plan file ---
plan = root / "outputs" / "plans" / "plan_8h_20261021.md"
plan.parent.mkdir(parents=True, exist_ok=True)
plan.write_text("""# 8h 自主计划 · 2026-10-21（Asia/Shanghai ~00:30–08:30）

窗口：约 8 小时。约束：LOCAL_ONLY、不训 VAE、红石仅模板、控 Grok Bot 周用量。

## Phase A — 应用完整度（MCBlock 向）· **DONE**

目标：在现有 matplotlib/tk viewer 上补齐高价值编辑能力。

已交付：

1. **Undo/redo 栈**（深度 32）— `UndoStack` in `src/app/viewer_voxel_tools.py`；编辑面板按钮 + Ctrl+Z/Y
2. **笔刷 / 盒填** — 小/中/大半径；「盒填」两角 AABB；破坏/放置/涂改
3. **复制 / 剪切 / 粘贴** — 选择两角定区；剪贴板缓冲；Ctrl+C/X/V
4. **方案 + .litematic** — 编辑侧已有「另存为方案 / 保存 / 导出方案 / 导出到 companion」（本阶段确认接线，未重写导出内核）
5. 文档：`docs/viewer.md`、`LAUNCH.md`；本计划文件

备份：`*.bak_phase_a_20261021_*`

冒烟：`scripts/_viewer_upgrade/_smoke_phase_a.py`（无 GUI）

已知限制：非 MagicaVoxel；笔刷为立方邻域非雕刻笔触；点选仍依赖外壳面投影。

## Phase B — 知识库充实（无 VAE）· **NEXT**

建议顺序（父代理续跑）：

1. 盘点 `docs/mc-knowledge/`、`data/feature_index`、现有 `kb_index.py` / principles 产出
2. 轻量：从已有 analyze / similar / redstone_templates 汇总可检索条目（不爬巨站）
3. 可选：补少量 curated 参考标签或 BOM/结构约束说明写入 knowledge
4. 不做：CUDA 长训、VAE ep900、大规模 web crawl

## Phase C — 回归 / 导出冒烟

1. 有显示器时开 `start_viewer.bat` 手测笔刷/撤销/粘贴
2. `export_litematic` / companion 路径冒烟（已有 bat）
3. 记录 blockers 到本计划末尾

## 用量注意

- 单线程聚焦；避免并行开多个重 agent
- 优先本机脚本与已有数据，少搜网页
""", encoding="utf-8")
print("plan written", plan)