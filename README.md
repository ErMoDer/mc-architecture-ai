# MC Architecture AI（路线 A：体素生成）

输入：建筑体素数据 → 训练轻量 **3D VAE** → 采样出新建筑 → 导出 `.mcfunction`（后续可接 `.litematic` / `mc-companion`）。

## 环境

```powershell
cd "E:\ai agent\mc-architecture-ai"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

需要：Python 3.10+，建议 NVIDIA GPU（12GB+ 显存更舒服；CPU 也能跑通 demo）。

## 5 分钟跑通

```powershell
# 1) 合成 64 个小屋（验证链路，不是最终数据）
python scripts/make_demo_data.py --count 64 --size 32

# 2) 转成训练用体素
python scripts/prepare_data.py --size 32

# 3) 改 configs/default.yaml：data.size: 32，train.batch_size 可先 8
# 4) 训练（demo 可先 20 epoch）
python scripts/train.py --epochs 20 --batch-size 8

# 5) 采样
python scripts/sample.py --num 4
```

输出在 `outputs/samples/`：`.npz.npz` + `.mcfunction`。

## 用 MCBlock 真数据（推荐）

[MCBlock](https://mcblock.top/) 建筑库可导出 `.litematic`，本仓库已接公开 API：

```powershell
# 拉一批适合 64³ 的小建筑（请控制频率，仅供个人学习训练）
python scripts/fetch_mcblock.py --max-pages 2 --max-edge 64 --max-blocks 4000

# 转体素
python scripts/prepare_data.py --from-mcblock --size 32

# 训练
python scripts/train.py --epochs 30
```

清单写在 `data/raw/mcblock/manifest.json`（含风格/难度标签，后续可做条件生成）。

也可手动把 `.litematic` 丢进 `data/raw/` 再 `prepare_data.py`。

## 自己的数据（vox.json）

```json
{
  "size": 32,
  "blocks": [
    ["minecraft:oak_planks", 10, 0, 10],
    ["minecraft:glass", 12, 2, 10]
  ]
}
```

## 当前阶段 / 下一步

| 阶段 | 状态 |
|------|------|
| 无条件体素 VAE | ✅ MVP |
| 合成数据跑通训练 | ✅ |
| MCBlock 拉取 + `.litematic` 导入 | ✅ |
| 文本/标签条件生成 | 下一步 |
| 导出 `.litematic` + 对接 `mc-companion` | 下一步 |

## 配置

见 `configs/default.yaml`。先用 **size=32** 验证，再升 **64**。

## 采样 3D 预览（桌面应用）

`powershell
pip install -r requirements-app.txt
# 或双击 启动预览.bat
.\.venv\Scripts\python.exe scripts\viewer_app.py
`

详见 `docs/viewer.md`。

## Minecraft 知识库

Java 版特性 / 版本变动 / 红石 / 刷怪塔笔记（面向本项目与 companion **26.3**）：

- 入口：[docs/mc-knowledge/README.md](docs/mc-knowledge/README.md)
- 文档索引：[docs/README.md](docs/README.md)
