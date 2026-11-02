# 采样 3D 预览应用

桌面小工具：调用已有 VoxelVAE checkpoint 生成建筑，并用 **MC 风格立方体** 预览 `outputs/samples`；支持方块选择与替换后另存。

## 安装依赖（一次）

```powershell
cd "E:\ai agent\mc-architecture-ai"
.\.venv\Scripts\Activate.ps1
pip install -r requirements-app.txt
```

## 启动

1. **双击** `启动预览.bat`（或 `start_viewer.bat`）
2. 或：

```powershell
cd "E:\ai agent\mc-architecture-ai"
.\.venv\Scripts\python.exe scripts\viewer_app.py
```

## 预览观感（MC 风格）

- 默认用**立方体外壳**（只画露在空气中的面），颜色按 `palette` 方块名近似原版（橡木棕、草方块绿、圆石灰、玻璃半透明等）
- 顶面亮、侧面略暗，浅蓝天空背景，略俯视机位
- 下方开关 **「性能模式（降采样）」**：大体素时可 2× 降采样加快；默认关闭以保持清晰
- **不**捆绑 Mojang 原版贴图；当前为纯色近似（若以后接本机 `.minecraft` 贴图会另说）

截图示例（自测）：`outputs/viewer_mc_style.png`、`outputs/viewer_mc_gui.png`

## 功能

### 采样与预览
- 生成建筑、3D 旋转缩放、浏览 `sample_XXX` / `sample_edit_XXX`
- 信息栏：非空气数、路径、是否未保存

### 编辑 / 建模（右侧，接近 MCBlock）
- **体素工具**：选择 / 破坏 / 放置 / 涂改 / 移动 — 在 3D 上点击外露面
- 放置/涂改使用下方「目标」方块；移动需点两次（抓取 → 目标面旁）
- 选中后可用 ±X/Y/Z 微调；方向键/PgUp/PgDn；Delete 删除
- **批量替换**：列表选源 → 目标 → 一键替换（仍可用）
- **撤销/重做**（深度 32，Ctrl+Z/Y）/ 另存 / 覆盖 / 导出 companion / 方案 照旧

### 流畅度
- 拖转时自动 **OrbitLOD**（降采样、无描边），松手恢复完整网格；机位不跳
- 默认勾选 **性能模式**；大体量建筑旋转更跟手
- 根因曾是 matplotlib 每帧重绘上万三角面；现改为拖转用轻量网格

## 模式说明（浏览 | 生成 | 设计 | 编辑 | 工具）

顶栏分段按钮切换左栏；中央始终是 3D 预览。

| 模式 | 用途 |
|------|------|
| 浏览 | 打开 outputs/samples 中的 npz |
| 生成 | 条件采样；可勾选 **结构约束**（Phase2：空心壳/楼板/屋顶修补，模式 repair / reject / reject_then_repair） |
| 设计 | 截图 + 文字 → 推断风格/地形再生成 |
| 编辑 | 点选建模（破坏/放置/涂改/移动）+ 批量替换与导出 |
| 工具 | Phase1–4 + 一键流水线（见下） |

### 「工具」面板（Phase1–4）

先 **浏览…** 选参考 .litematic，再点对应按钮（均后台跑现有 CLI，不重训、不改 32³）：

1. **分析 / 打开报告** — scripts/analyze_litematic.py → outputs/analyze/<stem>_report.md（可用系统默认程序打开）
2. **入库特征 / 生成相似** — learn_from_reference.py ingest|similar → 索引在 data/feature_index，相似输出 outputs/similar_gui
3. **红石模板复刻** — 
eplicate_redstone.py replicate → outputs/redstone_replicate_gui
4. **一键流水线** — pipeline_from_reference.py（可勾选「跳过红石复刻」）→ outputs/pipeline/<stem>__*/，含 pipeline_report.md

底部日志框显示命令与尾部输出；成功后若有 .npz 会尽量切到「浏览」预览。

相关文档：docs/schematic_analyze.md、structure_constraints.md、learn_from_reference.md、
edstone_templates.md、pipeline_from_reference.md。

### 红石嵌入当前建筑（P3）

对「浏览」里已打开的建筑 .npz，可用 CLI（或工具面板按钮「红石嵌入当前建筑」）：

scripts/paste_redstone_into_design.py --npz <当前.npz> --template auto:door

详见 docs/redstone_templates.md「嵌入建筑设计」。与「红石模板复刻」条带不同：本路径把模板嵌进外壳。



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



## 功能化 P0 · 工作台手感（2026-10-23）

在不动生成/VAE 的前提下，让预览更接近「能当工作台用」：

| 能力 | 说明 |
|------|------|
| **快捷栏 1–9** | 3D 下方格子；色块+短名；点击或数字键切换；选中栏同步为放置/涂改「目标」 |
| **准星** | 3D 画布中心十字（figure 坐标叠加），对准外壳面再点 |
| **键鼠** | **左键**=当前体素工具（选择/破坏/放置/涂改/移动）；**右键**=用快捷栏放置；**1–9** 切栏 |
| **提示行** | 快捷栏下方：当前工具 + 栏位方块名/id |
| **主路径文案** | 顶栏仍五段；提示突出浏览/编辑/生成，设计/工具标为次要 |

计划：outputs/plans/plan_ux_functional_20261023.md。P1 才会接 .minecraft 贴图 atlas。



## 功能化 P1 · 材质与反馈（2026-10-23）

| 能力 | 说明 |
|------|------|
| **原版贴图平均色** | 运行时从本机 client jar 提取 block PNG 到 outputs/cache/block_textures/（不进 git）；mc_colors 优先贴图采样 |
| **快捷栏图标** | CTkImage 像素图标；缺失则色块 + FALLBACK |
| **选中高亮** | 选中体素黄白抬升 |
| **中文名反馈** | 准星下 / 选中行 / 快捷栏用 lock_zh_cn；放置破坏状态短闪 |
| **路径探测** | MC_ASSETS_JAR / MC_TEXTURES_DIR；默认扫 Desktop/PCL* 与 AppData\.minecraft |

计划：outputs/plans/plan_ux_functional_20261023.md。

## 已知限制

- 体素面仍是 matplotlib 纯色四边形（贴图平均色），**不是**游戏内 UV；快捷栏可显示像素图标
- non_air 极大时仍可能较慢；拖转已用 LOD，静止精细预览仍受 matplotlib 限制（不是游戏引擎）
- 点击拾取依赖外壳面投影，极端透视下可能点偏，换个角度即可
- 未保存切换会提示（撤销/重做见上方 Phase A 表，深度 32）
- 不含训练 / 风格调色板一键换搭

### 导出 .litematic（companion）+ 材料清单

- 右侧 **导出到 companion**：把当前建筑写成 `.litematic`（默认目录见 mc-companion `.env` 的 `SCHEMATICS_DIR`）
- 勾选 **附带材料清单**（默认开）：同目录 `materials/<name>/` 写出 BOM（中文名 + 箱/盒/组/个，md/txt/csv/json）
- 勾选 **附带分层预览**（默认关）：额外写 Y 切片 PNG + HTML（略慢）
- 也可双击项目根目录 `export_litematic.bat`；详见 docs/export_litematic.md、docs/nova-borrow.md
- 在游戏里对 Andy 说**列出投影** / **加载 ai_sample_000**

## 功能化 P2 — 方案列表 + 进游戏（2026-10-23）

浏览模式左侧底部新增 **方案（项目）** 条：

1. 列表显示 schemes/ 下已存方案（中文名 + slug + 非空块数）
2. **新建 / 打开 / 另存 / 保存 / 导入投影 / 导入npz / 刷新**
3. 打开方案会载入 current.npz 并切到 **编辑**
4. 绿色 **进游戏（导出 PCL）**：写入 companion SCHEMATICS_DIR（默认 PCL 26.3-Fabric schematics），并默认写 materials/<stem>/ BOM；状态栏/弹窗提示完整路径与「游戏里 Andy：列出投影 → 建造」；勾选「导出后打开文件夹」可打开资源管理器

编辑右侧原「导出到 companion」已换成同一 **进游戏** 按钮。快捷栏/准星/贴图（P0/P1）不变。

计划：outputs/plans/plan_ux_functional_20261023.md。冒烟：scripts/_viewer_upgrade/_smoke_ux_p2.py。

**P3 残留**：应用内仍无游戏内 HUD；进游戏仍靠导出投影 + Andy/Litematica，不做 Fabric 模组。

## 功能化 P3 — 游戏桥接（2026-10-23）

浏览模式底部 **游戏桥接（投影目录）**：

1. 实时列出 companion / PCL schematics 内 .litematic（刷新 / 自动刷新）
2. 星标高亮本应用导出（夜齐_/夜坡_/ai_…）；打开目录、定位文件、复制文件名
3. 「进游戏」后弹出 **建造步骤卡**，并写 LAST_EXPORT.txt / LAST_EXPORT.json（materials/ 有镜像）
4. 状态行启发式显示 Minecraft/PCL 是否在跑（不注入、不改模组）

计划：outputs/plans/plan_ux_functional_20261023.md；冒烟：scripts/_viewer_upgrade/_smoke_ux_p3.py

**诚实残留**：仍不是游戏内 HUD；建造仍靠 Andy / Litematica。

