# 一键流水线：参考 Litematic → 分析 / 相似 / 红石模板

也可在预览 GUI 顶栏「工具」里一键运行（见 docs/viewer.md）。

把已有能力串成**一条命令**：

1. **Phase 1** 分析报告（结构 / 风格 / 红石 D9）
2. **Phase 3** 特征入库 + ConditionalVAE 相似变体（结构约束 / 可选骨架与材质映射）
3. **Phase 4** 按 D9 匹配手写红石模板并粘贴为 `.litematic`

不重训、不升 64³、不改 Apex/UI。

## 命令

```bat
cd /d "E:\ai agent\mc-architecture-ai"

.venv\Scripts\python.exe scripts\pipeline_from_reference.py "data\raw\mcblock\鸡舍_二__6b7d9b9d.litematic" --num 3 --seed 7
```

常用参数：

| 参数 | 含义 |
|------|------|
| `--out-dir` | 输出根目录（默认 `outputs/pipeline/<stem>`） |
| `--num` | 相似变体个数（默认 3） |
| `--seed` / `--temperature` | 采样种子与温度 |
| `--skip-similar` | 只做分析 + 红石模板 |
| `--skip-redstone` | 跳过 Phase4 |
| `--skip-analyze` | 跳过写分析报告（仍会为 Phase3 抽特征） |
| `--no-skeleton` / `--no-material-remap` | 关闭相似阶段引导 |
| `--structure-mode` | `repair` / `reject` / `reject_then_repair` |
| `--max-templates` | 红石模板条带最多条数 |
| `--checkpoint` | 条件 VAE 权重 |

## 输出布局

```
outputs/pipeline/<stem>/
  pipeline_report.md          # 中文总览
  pipeline_manifest.json      # 机器可读步骤
  01_analyze/
    <stem>_report.md
    <stem>_report.json
  02_features/
    <id>.json
    <id>_skeleton.npz
    index.json
  03_similar/
    similar_*.npz / .mcfunction
    similar_run.json
  04_redstone_templates/
    *_templates.litematic
    *_replicate_report.md
    *_replicate.json
```

同时会尝试写入全局 `data/feature_index/`，便于单独再跑 `learn_from_reference.py similar`。

## 相关文档

- Phase1：`docs/schematic_analyze.md`
- Phase3：`docs/learn_from_reference.md`
- Phase4：`docs/redstone_templates.md`
- Phase2 结构约束：`docs/structure_constraints.md`

## 局限

- 流水线成功 ≠ 游戏内可直接使用的成品建筑
- 相似变体不会复刻门窗细节；红石是原理骨架条带，需手动接线/放物品
- Phase3 依赖 `checkpoints/cond_last.pt`；缺权重时相似步骤会失败
- 任一步失败时总 `ok=false`，已完成步骤的产物仍保留在对应子目录
