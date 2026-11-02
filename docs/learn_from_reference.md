# Phase 3：从参考 Litematic 学特征 → 生成相似变体

**诚实边界**：这不是「复制粘贴原理图」，也不是重训 VAE。流程是：

1. 用 Phase 1 `analyze` 抽 **体量/材质/风格猜测/红石模式摘要**
2. 下采样 **32³ 占位骨架**（空心轮廓启发）
3. 映射到 ConditionalVAE 的 `style` / `terrain`
4. 采样 + **Phase 2 结构约束** + 可选骨架引导 / 材质重映射

仍为 **32³**；不重训、不升 64³、不改 Apex UI。

## 特征索引

默认目录：`data/feature_index/`

| 文件 | 内容 |
|------|------|
| `<id>.json` | massing / materials / style 映射 / redstone 模式摘要 |
| `<id>_skeleton.npz` | `occupancy` bool/uint8 32³ |
| `index.json` | 清单 |

## 命令

```bat
cd /d "E:\ai agent\mc-architecture-ai"

REM 入库（分析 + 骨架）
.venv\Scripts\python.exe scripts\learn_from_reference.py ingest "data\raw\mcblock\温馨木屋__449de557.litematic"

REM 列表
.venv\Scripts\python.exe scripts\learn_from_reference.py list

REM 生成相似变体（可直接 --litematic 自动 ingest）
.venv\Scripts\python.exe scripts\learn_from_reference.py similar --feature 温馨木屋__449de557 --num 3 --seed 7 --out-dir outputs/similar/温馨木屋__449de557
```

常用开关：

- `--no-skeleton` / `--skeleton-strength 0.45`：骨架引导强度
- `--no-material-remap`：不做参考顶部材质重映射
- `--no-structure`：关闭 Phase 2 结构约束
- `--structure-mode repair|reject|reject_then_repair`

## 模块

- `src/app/reference_features.py` — 提取 / 索引 / 相似生成
- `scripts/learn_from_reference.py` — CLI
- 依赖：`schematic_analyze`、`sample_runner`、`structure_constraints`、`cond_last.pt`

## 局限（Gaps）

- 风格/地形靠启发式映射，稀有风格可能落到 `medieval`/`flat`
- 骨架只是占位下采样，**不会**复现原版门窗楼梯细节
- 材质重映射按频次对齐参考 top blocks，可能错家族（石↔木）
- 红石模式仅写入特征摘要，**不会**在变体里复刻红石电路
- 输出仍受 32³ VAE 糊度限制；像「同一栋的换皮改版」多于「同作者新作」

相关：Phase4 红石模板见 docs/redstone_templates.md

一键流水线：[pipeline_from_reference.md](pipeline_from_reference.md)


## Block2Vec（TransformerBlock2Vec）

入库时默认写入 144 维嵌入（`*_block2vec.npy`）。详见 [block2vec.md](block2vec.md)。

```bat
.\.venv\Scripts\python.exe scripts\learn_from_reference.py embed --litematic path\to\ref.litematic
.\.venv\Scripts\python.exe scripts\learn_from_reference.py search --litematic path\to\ref.litematic --top-k 8
```
