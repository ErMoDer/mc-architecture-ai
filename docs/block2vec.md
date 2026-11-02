# TransformerBlock2Vec 接入说明

来源：[CraftGPT/TransformerBlock2Vec](https://huggingface.co/CraftGPT/TransformerBlock2Vec)（MIT，约 30MB DeepSpeed 权重）

官方 GitHub **没有**推理代码；本仓库根据 `mp_rank_00_model_states.pt` 与模型卡 **反推** 了 6 层 / 8 头 / 144 维 / SwiGLU / 3D RoPE 结构，仅做 **推理**，不重训。

## 本地路径

```
checkpoints/transformer_block2vec/
  mp_rank_00_model_states.pt   # 模型权重（已下载）
  README.md

src/models/block2vec.py        # 结构 + load_block2vec
src/app/block2vec_embed.py     # 分块嵌入 / 检索 / 入库
```

## 限制与回退

| 项 | 说明 |
|----|------|
| 分块 | 单块最大 **16x8x16**；更大投影按该尺寸切块后加权均值 |
| 词表 | 上游未公布 block id 表；优先用本项目 `data/palette.json`（id<1096），其余方块名 **MD5 稳定哈希** 到 1..1095 |
| 特殊 token | SEP=1096 PAD=1097 MASK=1098（与模型卡一致） |
| 硬件 | RTX 3050 4GB 上 fp16 推理即可 |
| 失败 | `extract_reference_features` 里嵌入失败会写 `block2vec.ok=false`，不阻断骨架入库 |

## 接入点

1. **`extract_reference_features(..., embed_block2vec=True)`**（默认开）  
   写入 `data/feature_index/<id>_block2vec.npy` + JSON 字段 `block2vec`
2. **`generate_similar_from_feature`**  
   `similar_run.json` 带上 `block2vec.neighbors`（余弦近邻，供参考，不替代 VAE 采样）
3. CLI：`learn_from_reference.py embed|search`

## 命令

```bat
cd /d "E:\ai agent\mc-architecture-ai"

REM 冒烟（嵌入 + 入库 + 可选 similar）
.\.venv\Scripts\python.exe scripts\smoke_block2vec.py --similar --num 1 --seed 7

REM 只算嵌入 / 检索
.\.venv\Scripts\python.exe scripts\learn_from_reference.py embed --litematic "data\user_try\樱花别墅投影.litematic"
.\.venv\Scripts\python.exe scripts\learn_from_reference.py search --litematic "data\user_try\樱花别墅投影.litematic" --top-k 8

REM 原有 similar（现在会带 neighbors）
.\.venv\Scripts\python.exe scripts\learn_from_reference.py similar --litematic "data\user_try\樱花别墅投影.litematic" --num 2 --seed 7
```

## 诚实边界

- 近邻检索质量依赖词表对齐；与 CraftGPT 原训练 id **不一定**逐块一致，同库内相对相似仍可用
- **不会**让 VAE 突然变聪明；similar 仍是条件 VAE + 骨架/材质启发
- RoPE 轴向与 token 展平顺序为工程约定（Y→Z→X）；若上游日后公开代码，可再对齐

下载权重：

```bat
.\.venv\Scripts\python.exe -c "from huggingface_hub import hf_hub_download; hf_hub_download('CraftGPT/TransformerBlock2Vec','mp_rank_00_model_states.pt',local_dir=r'checkpoints/transformer_block2vec')"
```

## 批量入库

ingest-batch 默认**不算** Block2Vec（避免上百个投影太慢）。需要时加：

```bat
.\.venv\Scripts\python.exe scripts\learn_from_reference.py ingest-batch data\raw\hack337\schematics --max-edge 64 --embed-block2vec
```

单条 ingest 默认会算嵌入；可加 --no-block2vec 跳过。

## Batch embed for feature_index (plan 3)

```bat
cd /d "E:\ai agent\mc-architecture-ai"
.venv\Scripts\python.exe scripts\batch_embed_block2vec.py --priority mcblock_style4,mcblock_other,eu_med_mod_other,chinese_house --out-dir outputs\design\block2vec_index_run
.venv\Scripts\python.exe scripts\smoke_b2v_retrieval.py --out-dir outputs\design\block2vec_index_run
```

Priority buckets cover style houses used by `similar_scaffold`. Model reloads every ~20 embeds to avoid CUDA illegal-access on long 4GB runs. Token ids are clamped to 0..1098 before Embedding lookup.

`similar_scaffold` retrieval uses Block2Vec as a **light within-style** score on top of plan-2 heuristics (see `docs/gen_strategy.md`).
