# 可保存设计方案（Schemes）

把一次设计（例如庄园）存成**命名方案**，之后可重新打开继续拓展、手改方块、或提交新的 .litematic 合并进同一方案。

## 目录结构

默认根目录：schemes/<slug>/

| 路径 | 说明 |
|------|------|
| scheme.json | 元数据：名称、创建/更新时间、style/terrain、备注、版本号、non_air |
| current.npz | 当前工作体素（32³） |
| current.mcfunction | 同步写出的指令文件 |
| history/ | 每次覆盖前的时间戳快照 |
| 
efs/ | 用户提交的原始 .litematic 副本 |
| ersions/ | 001.npz + 001.json 版本戳（导入/显式 bump） |

方案是**本地用户工程数据**，可随仓库忽略或自管；与 Hack337 训练数据的 LOCAL_ONLY 无关。

### slug 规则

- 显示名写在 scheme.json 的 
ame；文件夹名是 slug。
- 自动 slug：保留 ASCII 字母数字与中日韩统一表意文字（如 测试庄园、方案_观感冒烟），空白变 _，其它标点去掉；纯 ASCII 会小写。
- 也可用 --slug 指定稳定英文 id（冒烟用 schemes_e2e_smoke）。
- 若重名则自动加 _2、_3…

## CLI

在项目根：

`at
cd /d "E:\ai agent\mc-architecture-ai"

REM 列表
.venv\Scripts\python.exe scripts\scheme.py list

REM 从生成结果新建（庄园）
.venv\Scripts\python.exe scripts\scheme.py create "庄园" --from-npz outputs\samples\sample_000.npz --style medieval --terrain flat

REM 中文名 + 稳定 slug
.venv\Scripts\python.exe scripts\scheme.py create "方案_观感冒烟" --slug schemes_e2e_smoke --from-npz outputs\design\full_style_v4_20261020_112642\npz\sample_smedieval_tflat_000.npz --style medieval

REM 从 litematic 新建
.venv\Scripts\python.exe scripts\scheme.py create "庄园翼楼" --from-litematic path\to\ref.litematic

REM 加载（打印路径与 meta；可选拷贝）
.venv\Scripts\python.exe scripts\scheme.py load schemes_e2e_smoke --copy-to outputs\tmp_manor.npz

REM 手改后的 npz 写回方案（自动 history 快照）
.venv\Scripts\python.exe scripts\scheme.py save schemes_e2e_smoke --from-npz path\to\edited.npz --bump-version

REM 提交新投影（overlay=新非空覆盖；replace=整图替换；merge=仅填空+重叠更新）
.venv\Scripts\python.exe scripts\scheme.py import-litematic schemes_e2e_smoke path\to\new.litematic --mode overlay

REM 方块替换（palette id）
.venv\Scripts\python.exe scripts\scheme.py apply-edit schemes_e2e_smoke --replace 12 45

REM 导出 litematic（默认进 companion schematics；也可用 --out-dir / --name）
.venv\Scripts\python.exe scripts\scheme.py export schemes_e2e_smoke --litematic --name 方案_观感冒烟

REM 仅快照（加 --version 同时打 versions/vNNN）
.venv\Scripts\python.exe scripts\scheme.py snapshot schemes_e2e_smoke --version
`

导出目标：读 E:\ai agent\mc-companion\.env 的 SCHEMATICS_DIR（当前为 26.3 Fabric schematics）；若缺失则回落到 outputs/litematic/。

## 预览 GUI

1. 双击 start_viewer.bat 打开预览。
2. 顶栏切到 **编辑** 或 **设计**（两侧都有方案按钮；合并模式下拉在 **设计**）：
   - **存为方案**：把当前体素建成新命名方案并绑定。
   - **打开方案**：从 schemes/ 列表加载 current.npz。
   - **保存到方案**：把当前（可能已手改）体素写回已绑定方案，并留 history；可选 bump 版本。
   - **导入投影到方案**：选 .litematic，按 overlay/replace/merge 合并进当前方案。
   - **导出方案**：写出 .litematic 到 companion schematics。若 GUI 里有未保存修改，会**先自动写回方案再导出**，避免导出磁盘旧体素。
3. 编辑模式里照常「选源→替换→另存/覆盖」；对已绑定方案请用「保存到方案」写回。

## E2E 冒烟

`at
.venv\Scripts\python.exe scripts\schemes_e2e_smoke.py
`

- 脚本：scripts/schemes_e2e_smoke.py
- 最近一次通过：outputs/design/schemes_e2e_20261020_113217/SUMMARY.md
- 流程：create（full_style_v4 中世）→ load → apply-edit → save --bump → import-litematic overlay → export → snapshot
- 冒烟方案：schemes/schemes_e2e_smoke/（显示名「方案_观感冒烟」）
- 导出文件：方案_观感冒烟_v26.3.litematic（进 companion schematics）
- 若同名冒烟方案已存在，会先挪到 schemes_e2e_smoke_bak_<时间戳>/，不删用户其它方案。

## 模块

- src/app/schemes.py — 创建 / 保存 / 加载 / 导入合并 / 导出 / 版本
- scripts/scheme.py — 命令行入口
- scripts/schemes_e2e_smoke.py — CLI 端到端冒烟
- scripts/viewer_app.py — GUI「存为/打开/保存/导入/导出方案」

## 设计取舍

- **32³**：与现有 VAE / look_harden / 结构约束一致；过大 litematic 会居中裁切进立方体。
- **合并默认 overlay**：方便「在庄园上贴一块新翼楼」而不整图抹掉。
- **history + versions**：history 细粒度防手滑；versions 在导入/bump 时打戳，便于回滚对比。
- **导出前刷脏**：GUI「导出方案」在绑定且 dirty 时先 save_scheme，与所见一致。
- 不重训、不改 Hack337 管线；生成/设计仍走原有「生成 / 设计」模式，结果再「存为方案」。
