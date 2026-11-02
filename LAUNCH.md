# 一键启动 / 应用说明

本仓库本地训练、预览与导出脚本。请勿依赖绝对盘符路径。

## 预览 GUI
1. 双击 `启动预览.bat` 或 `start_viewer.bat`
2. 脚本会 `cd` 到 bat 所在目录，检测 `.venv`；缺 `customtkinter`/`matplotlib` 时自动 `pip install -r requirements-app.txt`
3. 启动 `scripts/viewer_app.py`

## 导出 .litematic
- `export_litematic.bat`（参数透传给 `scripts/export_litematic.py`）

## 依赖
- 训练/采样：`requirements.txt`
- 桌面预览：`requirements-app.txt`（matplotlib、customtkinter）

## 注意
- 训练编排已在跑时，请勿再开第二个 `scripts/train.py`
- Hack337 / mixed 数据 LOCAL_ONLY，不要 git push
- GPU 训练时预览可开，但可能挤占显存导致第二进程 OOM

更新于 2026-10-22（LAUNCH note：night22c 预览）

## 浏览样本目录（design 批次）

双击 `启动预览.bat` / `start_viewer.bat` 时，浏览模式默认打开**最新**的 `outputs/design/*/npz`，不必再敲 `--samples`。左侧「样本目录」可切换到默认 `outputs/samples` 或其它 design 批次，也可用「选目录…」。CLI `--samples` / `--out-dir` 仍可用。

## 今晚推荐预览（2026-10-22 反方盒）

- **预览对比（night22e 交叉坡）**：`outputs/design/night22e_full_20261022_071643/npz` — L/T 翼 + 退进/门廊 inset；中世/奇幻 roof≈G。在浏览模式「样本目录」里选该文件夹，或：
  `.\.venv\Scripts\python.exe scripts\viewer_app.py --samples outputs/design/night22e_full_20261022_071643/npz`
- **游戏投影（规范包）**：PCL schematics 优先 **夜坡_*（交叉坡）/ 夜齐_***（来自 night22d）；次选 **夜改3_***（与 night22c 同阶段快照）。
- 无 VAE / 不重跑生成。交叉坡/歇山仍未做。

## Design schemes
- docs/schemes.md
- CLI: .venv\Scripts\python.exe scripts\scheme.py list|create|save|load|import-litematic|export
- GUI: Edit/Tools -> save/open/import/export scheme
- Dir: schemes/<slug>/

## Viewer edit / performance (MCBlock-like)

Bar we mirrored from MCBlock preview/editor UX (not a clone):

1. **Snappy orbit** — while dragging the 3D view, mesh switches to OrbitLOD (downsample + no edges); full mesh restores on release. Camera elev/azim is preserved across rebuilds. Default **性能模式** is ON.
2. **Click modeling** (Edit mode) — tools: 选择 / 破坏 / 放置 / 涂改 / 移动. Click an exposed face in the 3D view. Place/Paint use the palette target below. Move: click grab, click again to set destination. Nudge with ±X/Y/Z buttons or arrow keys (PageUp/Down = ±Y). Delete/Backspace breaks selection.
3. Bulk replace / save / export companion / schemes unchanged.

Docs: `docs/viewer.md`.


## Viewer edit (Phase A · 2026-10-21)

Edit mode now has:

1. Undo/redo stack (depth 32) — buttons + Ctrl+Z / Ctrl+Y
2. Brush sizes 小/中/大 + optional 盒填 (two-click AABB) for break/place/paint
3. Copy / cut / paste region (select two corners, then paste at click) — Ctrl+C/X/V
4. Scheme save/export + 导出到 companion (.litematic) unchanged on the right panel

Docs: `docs/viewer.md`. 8h plan: `outputs/plans/plan_8h_20261021.md`.

## 功能化 P0（2026-10-23）

工作台骨架（快捷栏 + 准星 + 键位），**未**训 VAE、未重生成风格包。

- 计划：outputs/plans/plan_ux_functional_20261023.md（P0 进行中 → 完成后改 DONE）
- 启动仍用 启动预览.bat / start_viewer.bat，或：
  ./.venv/Scripts/python.exe scripts/viewer_app.py --samples outputs/design/night22e_full_20261022_071643/npz
- **试法**：切「编辑」→ 看 3D 下快捷栏与准星 → 按 1–9 切目标 → 左键用当前工具、**右键放置**
- 游戏投影优先仍用 **夜齐_*** / **夜坡_***；本切片只改预览壳



## 功能化 P1（2026-10-23）

材质+反馈：快捷栏贴图、平均色、高亮、中文名/toast。**未**训 VAE。

- 计划：outputs/plans/plan_ux_functional_20261023.md
- 缓存：outputs/cache/block_textures/
- 预览：./.venv/Scripts/python.exe scripts/viewer_app.py --samples outputs/design/night22e_full_20261022_071643/npz

## 功能化 P2（2026-10-23）

方案列表 + 一键进 PCL。**未**训 VAE。

- 计划：outputs/plans/plan_ux_functional_20261023.md（P0–P2 完成 → 下一步 P3）
- 启动：
  ./.venv/Scripts/python.exe scripts/viewer_app.py --samples outputs/design/night22e_full_20261022_071643/npz
- **试法**：浏览 → 底部「方案」新建/打开 → 点绿色「进游戏（导出 PCL）」→ PCL schematics 出现 .litematic + materials/ → 游戏内 Andy「列出投影 → 建造」
- 游戏投影：继续可用 **夜齐_*** / **夜坡_***；本片只做工作台闭环

## 功能化 P3（2026-10-23）

轻量游戏桥接（投影列表 + 建造步骤卡 + LAST_EXPORT）。未训 VAE，未做 Fabric HUD。

- 计划：outputs/plans/plan_ux_functional_20261023.md（P0–P3 收口）
- 预览：
  ./.venv/Scripts/python.exe scripts/viewer_app.py --samples outputs/design/night22e_full_20261022_071643/npz
- 试法：浏览 → 底部「游戏桥接」看 PCL 投影列表 → 「进游戏」→ 看步骤卡 / 复制文件名 → 游戏内 Andy「列出投影 → 建造」

