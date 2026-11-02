# -*- coding: utf-8 -*-
from pathlib import Path

doc = '''# 对接 mc-companion / 游戏内投影

把建筑 AI 的 `.litematic` 写到 **mc-companion** 读取的 `SCHEMATICS_DIR`，进游戏后让 Andy 加载建造。  
**不需要**把 Litematica/Nova 源码拷进本仓库；游戏里仍需已装好能配合 companion 的投影/建造流程（Andy 读 litematic 落块）。

## 路径怎么定

1. 读 `E:\\ai agent\\mc-companion\\.env` 里的 `SCHEMATICS_DIR`
2. 若缺失，退回本仓库 `outputs/litematic`

查看当前目标：

```bat
cd /d "E:\\ai agent\\mc-architecture-ai"
.venv\\Scripts\\python.exe scripts\\export_litematic.py --print-dir
```

默认应指向 PCL 26.3 的 `...\\versions\\26.3-Fabric 0.19.5\\schematics`（与 companion `.env` / `config.js` 一致）。

## 推荐流程（生成 → 导出 → 进游戏）

1. **生成建筑**（预览 GUI 或 similar_scaffold 冒烟输出的 `.npz`）
2. **导出到 companion 目录**
   - GUI：预览器右侧点 **导出到 companion**（可选材料清单 / 分层）
   - 或 CLI：
     ```bat
     .venv\\Scripts\\python.exe scripts\\export_litematic.py --input "outputs\\design\\scaffold_struct_20261019_204603\\npz\\sample_seuropean_tflat_000.npz" --name ai_euro_review --latest 1
     ```
   - 或双击 `export_litematic.bat`（默认导出 `outputs/samples` 里最新若干份）
3. **开游戏 26.3**，确认 companion（Andy）已连上、且你有权限（如 `/op Andy`）
4. 聊天：
   - `Andy 列出投影`
   - `Andy 建造 <文件名不含.litematic>`（例如 `Andy 建造 ai_euro_review_v26.3`）
   - 可选：`Andy 建造 xxx 旋转90` / `Andy 停建`

详细指令见 `E:\\ai agent\\mc-companion\\README.md` / `使用说明.txt`。

## 版本

导出默认按 **Java 26.3** 做方块 ID remap（与你当前客户端一致）。GUI 可改目标版本；文件名常带 `_v26.3` 后缀。

## 可选侧车

`--materials` / `--layers`（或 GUI 勾选）在 schematics 旁写 `materials/<stem>/` BOM 与分层预览，**不影响** `.litematic` 本体加载。

## 故障排查

| 现象 | 处理 |
|---|---|
| `--print-dir` 指到 `outputs/litematic` | 检查 companion `.env` 是否有 `SCHEMATICS_DIR=` |
| Andy 说找不到投影 | 确认文件已在 `SCHEMATICS_DIR`；名字与指令一致（可先 `列出投影`） |
| 导出成功但游戏里没有 | 是否开错版本目录；PCL 多版本时 `SCHEMATICS_DIR` 必须对应当前 26.3 |
| 方块怪异 | 确认导出目标版本是 26.3；看 remap 日志 |

相关：`docs/export_litematic.md`、`src/data/export_litematic_util.py`。
'''
Path("docs/companion_export.md").write_text(doc, encoding="utf-8")

# pointer in export_litematic.md
p = Path("docs/export_litematic.md")
t = p.read_text(encoding="utf-8")
ptr = "\n\n## 对接 mc-companion\n\n完整游戏内步骤见 **[companion_export.md](companion_export.md)**。CLI 可先 `--print-dir` 确认目标文件夹。\n"
if "companion_export.md" not in t:
    p.write_text(t.rstrip() + ptr, encoding="utf-8")
print("docs ok")
