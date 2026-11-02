# 借鉴 Litematica-Nova（不引入其二进制）

参考：[Litematica-Nova](https://github.com/LitematicaViewer/Litematica-Nova) Beta 0.2.1（MPL-2.0，Rust 桌面端）。

## 许可

- Nova 为 **MPL-2.0**：可阅读其思路与公开 README，**不要复制其源码或 vendoring 安装包进本仓库**。
- 本仓库只做**轻量自研**助手（材料 BOM、Y 分层预览），与现有 `export_litematic` / `viewer_app` / `mcfunction` 互补。
- 完整投影库、三维渲染、方块替换预览、主题 UI 等仍推荐用 Nova 打开导出的 `.litematic`。

## 借鉴什么

| 想法 | 本仓库落地 | 留给 Nova 桌面端 |
|------|------------|------------------|
| 材料清单（中文名 + 数量） | `scripts/materials_bom.py` + `src/app/materials_bom.py` | 图标、按区域统计、容器内物品 |
| 「箱-盒-组-个」拆分 | 同左（64 / 1728 / 46656） | 切换显示模式的 GUI |
| 导出 CSV / TXT | `--csv` / 默认写 BOM 文件 | SVG / 网页导出 |
| 按层（Y）施工视图 | `src/app/layer_preview.py` → PNG + 简易 HTML 网格 | 拖动缩放、半透明下层、测量工具 |
| 生成 → 投影 → 看料看层 | 导出后 `--materials` / 独立 CLI；文档推荐 Nova | 进游戏前一站式 dig |
| 原版 **26.3** 物品映射 | 本项目导出默认 `target_version=26.3`（见 `src/data/mc_versions.py`） | Nova 材料映射以 26.3 为准；复杂模组方块以 Nova 为准 |

## 不借鉴 / 不做

- 不把 Nova Setup.exe / AppImage 放进仓库当硬依赖。
- 不复制其 UI、图标资源、渲染管线。
- 不做投影库分类树、在线资源、方块替换另存为（用 Nova）。
- 不做 VAE 续训；本功能只读已有 `.npz` / `.litematic`。

## 预览 GUI 一键导出（推荐）

1. 双击 `启动预览.bat` / `start_viewer.bat`，或运行 `scripts/viewer_app.py`
2. 切到 **编辑** 模式（右侧有导出区）
3. 勾选 **附带材料清单**（默认开）、可选 **附带分层预览**（默认关，会多写 PNG）
4. 点绿色 **导出到 companion**（或作品方案里的 **导出方案**）

导出后会在 `.litematic` 同目录写入：

```
<SCHEMATICS_DIR>/
  ai_xxx.litematic
  materials/
    ai_xxx/
      ai_xxx_BOM.md
      ai_xxx_BOM.txt
      ai_xxx_BOM.csv
      ai_xxx_BOM.json
      layers/          # 仅勾选「附带分层预览」时
```

实现：`src/app/materials_bom.py` → `write_export_sidecars()`，GUI / CLI 共用。

## 怎么用（本仓库）

```powershell
cd "E:\ai agent\mc-architecture-ai"

# 对单个样本出材料清单 + 分层预览
.\.venv\Scripts\python.exe scripts\materials_bom.py `
  --input "outputs\design\scaffold_materials_20261019_165804\npz\sample_seuropean_tflat_000.npz" `
  --layers --csv

# 导出 litematic 时顺带出 BOM（写到同目录 materials/）
.\.venv\Scripts\python.exe scripts\export_litematic.py `
  --input "outputs\design\scaffold_materials_20261019_165804\npz\sample_seuropean_tflat_000.npz" `
  --latest 0 --out-dir "outputs\litematic_tmp" --materials --layers
```

导出的 `.litematic` 仍可用 **Litematica-Nova** 打开做正式施工预览（推荐）。

## 计数约定（箱盒组个）

与常见中文投影材料习惯一致（嵌套）：

- **个** = 1
- **组** = 64（一组 / 一组堆叠）
- **盒** = 27 组 = 1728（满潜影盒）
- **箱** = 27 盒 = 46656（满箱潜影盒）

不可堆叠或特殊堆叠上限的方块，BOM 里仍按 64 拆分并注明 `stack_size`；精确生存配方成本以游戏 / Nova 为准。

## 与现有管线关系

```
similar_scaffold / sample → .npz (+ .mcfunction)
        ↓
export_litematic.py → .litematic（Java 26.3 remap）
        ↓
materials_bom / --materials → BOM.md + BOM.csv + layers/
        ↓（可选）
Litematica-Nova 打开 .litematic → 图标材料表 / 分层施工 GUI
```
