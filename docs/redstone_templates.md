# Phase 4：红石原理级复刻（模板库）

**不是**用 VAE 发明电路，也**不是**原版 tick 引擎。

做法：Phase1 分析得到的 D9 模式 id → 在 `data/redstone_templates/` 中匹配**手写最小骨架** → 并排粘贴为 `.litematic` + 中文报告。

## 模板目录

`data/redstone_templates/`

| 内容 | 说明 |
|------|------|
| `catalog.json` | 清单 |
| `<id>/meta.json` | matches / 中文名 / 尺寸 / 说明 |
| `<id>/blocks.json` | 相对坐标 + 方块名 + Properties（朝向等） |

内置示例：漏斗钟、杠杆灯 IO、RS 锁存示意、双活塞门、粘活塞换块、QC 活塞排、火把钟、日光钟、观察者边沿、中继器链、投掷电梯、绊线等。

## 命令

```bat
cd /d "E:\ai agent\mc-architecture-ai"

.venv\Scripts\python.exe scripts\replicate_redstone.py bootstrap
.venv\Scripts\python.exe scripts\replicate_redstone.py list
.venv\Scripts\python.exe scripts\replicate_redstone.py match "data\raw\mcblock\鸡舍_二__6b7d9b9d.litematic"
.venv\Scripts\python.exe scripts\replicate_redstone.py replicate "data\raw\mcblock\鸡舍_二__6b7d9b9d.litematic" --out-dir outputs/redstone_replicate/鸡舍_二
```

## 模块

- `src/app/redstone_templates.py` — 模板定义、匹配、画布粘贴、带 Properties 的 litematic 写出
- `scripts/replicate_redstone.py（条带复刻）、scripts/paste_redstone_into_design.py（嵌入建筑）` — CLI

## 局限（务必读）

- 模板是**教学向原理骨架**，不是把参考建筑里的红石原样搬进变体
- 不含漏斗物品 NBT、完整 BUD/零刻时序、装修与精确坐标对齐
- 匹配依赖 D9/时钟启发式；未覆盖的模式不会出现
- 粘贴结果需在游戏内接电源、放物品、微调朝向后才可用
- 与 Phase3「相似外壳」分开：本阶段只产出红石模板条带，不自动嵌入 VAE 体素

一键流水线：[pipeline_from_reference.md](pipeline_from_reference.md)

## 嵌入建筑设计（P3，2026-10-20）

把**手写模板**粘进已有 32³ 建筑体素（不是并排条带，也不是 VAE 造电路）。

### 一键命令

`at
cd /d "E:\ai agent\mc-architecture-ai"

.venv\Scripts\python.exe scripts\paste_redstone_into_design.py --list

.venv\Scripts\python.exe scripts\paste_redstone_into_design.py ^
  --npz outputs\design\full_style_v4_20261020_112642\npz\sample_seuropean_tflat_000.npz ^
  --template auto:door ^
  --companion --companion-name 欧式_红石门控
`

| 参数 | 含义 |
|------|------|
| --npz | 建筑 sample_*.npz |
| --template | 模板 id，或 uto（杠杆灯）/ uto:door（双活塞门）/ uto:clock（漏斗钟） |
| --collision | ir_only（默认，不凿墙）或 overwrite |
| --origin x,y,z | 手动原点；省略则室内楼板+靠墙（门控会靠门）启发式 |
| --companion | 额外写入 companion schematics（不删其它投影） |
| --out-dir | 默认 outputs/design/rs_paste_<时间戳>/ |

### 产出

- *_before.npz / *_after.npz + previews/*_before.png / *_after.png
- 合并 .litematic（states 路径，**保留模板朝向 Properties**）
- paste_report.md / paste_summary.json
- 可选 companion：如 欧式_红石门控_v26.3.litematic

### 模块 API

- ind_paste_origin / paste_template_into_voxels / paste_redstone_into_design
- GUI「工具」：**红石嵌入当前建筑**（对浏览中已打开的 .npz 跑同一 CLI）

### 与「复刻条带」的区别

| | 
eplicate_redstone.py | paste_redstone_into_design.py |
|--|--|--|
| 输入 | 参考 .litematic（含红石） | 建筑 .npz |
| 输出 | 模板**并排条带** | 模板**嵌进外壳** |
| 用途 | 原理对照 / 报告 | 可造的「房子+小红石」 |

### 额外局限（嵌入）

- 只贴教学骨架；不会自动造完整熔炉/刷怪塔（那些用 early_tech 整包）
- ir_only 可能跳过与墙重叠的格；跳太多时用 --collision overwrite 或 --origin
- companion 调色板导出会丢部分朝向；冒烟目录里的 states litematic 更保真

## 原理规则挂载（2026-10-19）

匹配结果会附带 `principle_rule_ids` 与规则表注释（来自 `docs/mc-knowledge/redstone/redstone_principles_rules.json`）：

- 强弱充能 / 供电vs激活
- 方块更新 NC/PP（BUD 前提）
- 计划刻 vs 红石 tick
- 瞬时线 / 活塞延伸 **仅模板**
- AI：模板匹配，非引擎

这些注释帮助选模板与写报告，**不会**提高「原版可运行」保证。详见 `docs/mc-knowledge/redstone/signals-timing.md` 与 `ai-constraints.md`。

## Everyday house stubs (2026-10-20)

Added **6** teaching skeletons (12 → **18**). Still template paste only — not learned circuits.

| id | purpose |
|----|---------|
| urnace_input_hopper_stub | chest → hopper → furnace feed |
| urnace_output_hopper_stub | furnace → hopper → chest drain |
| piston_door_1wide_2high | narrow sticky door teaching |
| or_gate_torch | dual-lever OR → lamp |
| nd_gate_torch | dual-input AND sketch |
| utton_iron_door | stone button + iron door pulse |

Bootstrap: python scripts/replicate_redstone.py bootstrap (force rewrite from canonical_templates).
Smoke paste: outputs/design/rs_paste_furnace_stub_20261020_121546/ (urnace_input_hopper_stub into rustic sample).

## Teaching stubs top-up (2026-10-20)

Added to canonical_templates() / data/redstone_templates/ (catalog **18 → 22**):

| id | purpose |
|----|---------|
| hopper_line_transfer | chest→hopper→hopper→chest horizontal pipe |
| observer_clock_loop | dual-observer fast clock (≠ observer_edge) |
| urnace_fuel_side_hopper | side fuel feed (pairs with input/output stubs) |
| comparator_chest_read | comparator reads chest fullness → lamp |

Still teaching stubs only — not full iron farms / mega smelters. Paste smoke: urnace_fuel_side_hopper into industrial sample → companion 工业_燃料漏斗桩_v26.3.



## Long fill stubs (2026-10-20)

Catalog **22 → 28**. New house-usable teaching stubs: `note_block_alert`, `dropper_dispenser_pulse`, `water_stream_item_tiny`, `trapped_chest_signal`, `daylight_sensor_lamp_stub`, `pressure_plate_iron_door`. Report: `outputs/design/long_fill_20261020_134027/`.


## Long fill2 stubs (2026-10-20)

Catalog **28 → 34**. New indoor teaching stubs: `item_filter_stub`, `torch_tower_elevator_frag`, `hopper_clock_xor_alt`, `lectern_book_signal`, `target_block_signal`, `brewing_stand_hopper_stub`. Report: `outputs/design/long_fill2_20261020_135822/`.
