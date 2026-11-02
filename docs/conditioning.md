# 风格 / 地形条件生成

## 标签体系

### style（风格）

优先使用 MCBlock `labels.styles`；多风格时按优先级取一个主风格：

`chinese > japanese > desert > western > industrial > scifi > european > rustic > modern > medieval > fantasy`

无标签 / demo 小屋 → `unknown`。

词表见 `data/label_vocab.json` 的 `styles` / `style_to_id`。

### terrain（地形）

数据没有显式地形字段，由 `scripts/build_labels.py` **推断**（规则可解释，不瞎标）。
扫描顺序：文件名 stem → MCBlock 显示名 → tags → style/primaryType。

| terrain | 触发条件（按优先级） |
|---------|----------------------|
| `nether` | 下界 / 地狱 / nether |
| `snow` | 雪景 / 雪人 / 雪屋 / 冰原 / 冰雪 / snow 等 |
| `desert` | 沙漠 / desert / 绿洲，或 style 含 desert |
| `water` | 码头 / 水上 / 湖畔 / 泳池 / 船 / 桥 / 喷泉 / dock / boat 等 |
| `mountain` | 吊脚 / 悬崖 / 山顶 / 山庄 / 山寨 / mountain / cliff 等 |
| `nature` | `primaryType` 为 landscape_component / plant_nature / sculpture_figure，或 tags 含 自然 / 植物（且未被上面更强规则命中） |
| `other` | 载具等无法归类（如 vehicle_transport 且非船名） |
| `flat` | **默认**：普通平地建筑 |

稀有类样本少时条件会弱；可用 `scripts/fetch_rare_terrain.py` 按名称关键词扩水/雪/山等。

产出：

- `data/label_vocab.json`：style_id / terrain_id 映射与计数
- `data/processed/labels.json`：每样本 `style` / `terrain` / id / `reason`

## 模型

`ConditionalVoxelVAE`：编码器同无条件 VAE；解码前把 `style` / `terrain` embedding 拼到 latent `z` 再过一层 MLP。

无条件路径 `VoxelVAE` 仍保留；条件 checkpoint 默认 `checkpoints/cond_last.pt`，不覆盖 `last.pt`。

## 怎么训

```bat
cd /d "E:\ai agent\mc-architecture-ai"
.venv\Scripts\python.exe scripts\build_labels.py
.venv\Scripts\python.exe scripts\train.py --conditional --batch-size 2 --epochs 40
```

扩稀有地形后再训：

```bat
.venv\Scripts\python.exe scripts\fetch_rare_terrain.py --max-pages 20 --sleep 0.55
.venv\Scripts\python.exe scripts\prepare_data.py --size 32 --raw data/raw
.venv\Scripts\python.exe scripts\build_labels.py
.venv\Scripts\python.exe scripts\train.py --conditional --batch-size 2 --epochs 40
```

## 怎么采

```bat
.venv\Scripts\python.exe scripts\sample.py --conditional --style medieval --terrain flat --num 4
.venv\Scripts\python.exe scripts\sample.py --conditional --style medieval --terrain water --num 2
.venv\Scripts\python.exe scripts\sample.py --conditional --style chinese --terrain nature --num 2
```

也可在预览应用里选风格/地形后点「生成建筑」（需加载 `cond_last.pt`）。

导出 litematic：预览里「导出到 companion」，或 `export_litematic.bat`。

采样时可加结构约束（空心/楼层/屋顶）见 [structure_constraints.md](structure_constraints.md)。

参考 Litematic 相似变体见 [learn_from_reference.md](learn_from_reference.md)。

## 已知限制

- 地形靠启发式，船/桥以外的「临水小屋」若名称无关键词可能仍标 `flat`
- 稀有风格（scifi/western）与稀有地形样本仍偏少时，条件几乎学不到
- 类数多（800+）、4GB 显存，条件生成仍偏糊；需更多数据与标签质量

一键流水线：[pipeline_from_reference.md](pipeline_from_reference.md)
