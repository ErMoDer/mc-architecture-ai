# Hack337 Minecraft-Schematics 接入

来源：[Hack337/Minecraft-Schematics](https://huggingface.co/datasets/Hack337/Minecraft-Schematics)

## 许可与本地约定

- **License**：上游 README `license: mit`（MIT）
- **LOCAL_ONLY**：`data/raw/hack337/`、`data/processed/hack337/` 仅本机，不要 git commit/push 大数据
- 对话微调文件 `dataset_openai.jsonl` 不进 ConditionalVAE

## 目录

```
data/raw/hack337/
  blueprints/              # 669 JSON 网格（VAE 主路径）
  schematics/              # ~844 .litematic + ~29 .schem
  schematics_mapping.json
  blueprints_mapping.jsonl
  dataset_openai.jsonl
  INGEST_STATUS.json

data/processed/hack337/
  h337_*.npz              # 32^3 crop/pad
  meta.json / tags.json / SOURCE.json / INGEST_REPORT.json
  labels.json                # build_labels 后
```

## 下载

```bat
.\.venv\Scripts\pip.exe install huggingface_hub
.\.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('Hack337/Minecraft-Schematics', repo_type='dataset', local_dir=r'data/raw/hack337')"
```

## 接入

```bat
.\.venv\Scripts\python.exe scripts\ingest_hack337.py --feature-ingest --feature-max-edge 64
```

| 参数 | 含义 |
|------|------|
| `--max-edge-skip 96` | 任一边过大则跳过 blueprint |
| `--feature-ingest` | 写入 `data/feature_index`（similar） |
| `--feature-max-edge 64` | feature 入库尺寸上限 |
| `--feature-max N` | 限制入库条数 |

`.schem` 暂不解析（有对应 blueprint/litematic）。

批量入库 CLI：

```bat
.\.venv\Scripts\python.exe scripts\learn_from_reference.py ingest-batch data\raw\hack337\schematics --max-edge 64
```

## 标签 / 训练（不自动开长训）

```bat
.\.venv\Scripts\python.exe scripts\build_labels.py --processed data/processed/hack337 --labels-out data/processed/hack337/labels.json
```

把 `configs/default.yaml` 的 `data.processed_dir` 指到 `data/processed/hack337`，或合并 npz。RTX 3050 4GB 保持 `size: 32`。

## 统计

见 `data/processed/hack337/INGEST_REPORT.json`。
