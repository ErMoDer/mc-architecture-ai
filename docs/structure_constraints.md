# Phase 2：结构约束采样（32³）

在 **不重训、不升 64³** 的前提下，于 ConditionalVoxelVAE / VoxelVAE 采样后施加启发式结构约束，减轻「实心乱填」。

相关形状语汇见 [`mc-knowledge/builds/shape-language.md`](mc-knowledge/builds/shape-language.md)。

## 做什么

1. **检查**（`check_structure`）
   - 空心度 `hollow_score`（壳内空气占比）
   - 外壳实心比例、主体连通分量占比
   - 楼层峰值 `floor_guess`、屋顶线索 `roof_score`
   - 非空气数量 / 占地 footprint 上下限
2. **修复**（`repair_structure`，保守）
   - 丢弃非最大连通分量（浮空碎块）
   - 掏空过实内部（邻域极实心的体素→空气）
   - 在楼层 Y 峰（或每约 5 层）铺地板
   - 屋顶顶盖 + 外轮廓竖向补墙
3. **拒绝重采**（`reject` / `reject_then_repair`）
   - 不合格则再次 `model.sample`，受 `--structure-max-tries` 限制

## 怎么用

```bat
cd /d "E:\ai agent\mc-architecture-ai"

REM 条件采样 + 修复约束
.venv\Scripts\python.exe scripts\sample.py --conditional --style medieval --terrain flat --num 4 --structure-constrain --structure-mode repair --out-dir outputs/samples_struct

REM 不合格则重采（必要时再修）
.venv\Scripts\python.exe scripts\sample.py --conditional --style chinese --terrain flat --num 4 --structure-constrain --structure-mode reject_then_repair --structure-max-tries 10 --out-dir outputs/samples_struct_rej

REM 与无约束对比指标
.venv\Scripts\python.exe scripts\sample.py --conditional --style medieval --terrain flat --num 4 --structure-constrain --structure-mode repair --structure-compare --out-dir outputs/samples_struct_cmp --seed 42
```

预览应用可调用 `src.app.sample_runner.generate_samples(..., structure_constrain=True)`（本阶段不改 UI）。

## 模块

| 文件 | 作用 |
|------|------|
| `src/app/structure_constraints.py` | 指标 / 检查 / 修复 / 汇总 |
| `src/app/sample_runner.py` | `generate_samples` 接入约束 |
| `scripts/sample.py` | CLI：`--structure-constrain` 等 |

## 演示对比（medieval / flat，seed=42，n=4，repair）

| | 无约束 | 约束后 |
|--|--------|--------|
| 结构通过率 | 0% | **75%** |
| 均 hollow | ~0.31 | **~0.52** |
| 均 roof | ~0.49 | **~1.0** |
| 均 non_air | ~19900 | **~15600** |

输出目录示例：outputs/samples_struct_cmp/。

## 局限（Gaps）

- **不是**可微结构损失，也不改 VAE 权重；复杂坡屋顶/山墙仍靠模型
- 修复用众数方块铺地板/屋顶，材质可能单调
- `reject` 在阈值样本上可能耗尽 tries 而数量不足
- 阈值对「好看」只是代理；solid_acc / 风格对齐需另看
- 仍保持 32³；无 Apex / 无训练循环改动

Phase 3 参考学习：[learn_from_reference.md](learn_from_reference.md)。

## Look harden（观感硬化，后处理）

在结构约束之后默认启用（可用 `--no-look-harden` 关闭）：

1. **材质 top-K**：丢弃花/告示牌/地毯等 junk，映射到风格白名单结构块（默认每样本 ≤6 种 + 少量 trim）
2. **平整楼板**：在楼层峰 Y 铺满 footprint 地板
3. **外轮廓墙**：footprint 周缘竖向补墙 + 顶盖

模块：`src/app/look_harden.py`；采样参数：`look_harden_enable` / `look_harden_top_k`。



壳/楼层加强（2026-10-18）：默认 geometry_mode=strong（周界补洞、规则楼板、屋顶修补）；详见 docs/look_harden.md 与 outputs/design/look_harden_shell_floors_20261018_212712/.

## 知识原则（look_harden）

层高/墙厚/窗距/门/檐/顶等观感参数见 [`mc-knowledge/builds/look_harden_rules.json`](mc-knowledge/builds/look_harden_rules.json) 与 [`look_harden.md`](look_harden.md)。结构约束仍负责空心与连通；原则摘要不重训。

## Scaffold structure harden (2026-10-19)

See `docs/gen_strategy.md`. Scaffold path still uses `SCAFFOLD_THRESHOLDS` (min_roof 0.18). Floor/shell/roof builders live in `gen_strategy.scaffold_from_occupancy`; pitched cover plateau in `look_harden.harden_roof_silhouette` (non flat-deck styles only).

## Hollow / room metrics (2026-10-20)

- max_enclosed_air_cc: air CCs not reachable from volume border (misleading when doors are open air).
- interior_room_air: air over footprint interior (fp minus peri), door-tolerant house signal.
- loor_interior_cover: solids / interior at floor peaks (excludes roof deck Y). Full slabs ~0.95+; ring floors ~0.1–0.4.

Scaffold thresholds prefer max_floor_interior_cover + min_interior_room_air over enclosed-CC.
