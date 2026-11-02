# 导出 .litematic 给 mc-companion

把 `outputs/samples` 里的采样体素写成 Litematica 投影，放到 companion 的 `SCHEMATICS_DIR`，进游戏后对 Andy 说话即可建造。

## 一键导出

双击项目根目录 `export_litematic.bat`，或：

```powershell
cd "E:\ai agent\mc-architecture-ai"
.\.venv\Scripts\python.exe scripts\export_litematic.py
```

默认行为：

- 输入：`outputs/samples` 里**最新 4 个** `sample_*.npz` / `sample_edit_*.npz`
- 输出目录：读取 `E:\ai agent\mc-companion\.env` 的 `SCHEMATICS_DIR`；读不到则写到 `outputs/litematic`
- 文件名：`ai_sample_000.litematic` 这类（可用 `--name` 改前缀）

## 常用参数

```powershell
# 指定单个样本
.\.venv\Scripts\python.exe scripts\export_litematic.py --input "outputs\samples\sample_000.npz"

# 导出目录内全部，并指定输出目录
.\.venv\Scripts\python.exe scripts\export_litematic.py --latest 0 --out-dir "C:\path\to\schematics"

# 改文件名前缀
.\.venv\Scripts\python.exe scripts\export_litematic.py --name mybuild --latest 2
```

## 进游戏用法

1. 确认 companion（Andy）已连上世界，且 `SCHEMATICS_DIR` 指向当前版本的 `schematics` 文件夹
2. 聊天对 Andy 说：**列出投影**
3. 再说：**建造 ai_sample_000**（名字与文件名去掉 `.litematic` 一致）

## 预览应用

预览窗口右侧有 **「导出到 companion」** 按钮：把当前显示的体素写出到 `SCHEMATICS_DIR`，状态栏会显示完整路径。

## 说明

- 写出格式与仓库 `load_litematic` / companion `loadLitematic` 一致（YZX 打包）
- 每个文件会做 Python 往返校验（尺寸 + 非空气数）
- 楼梯等方块暂不写 Properties，companion 仍可摆，朝向可能是默认值

## 材料清单与分层（Nova 借鉴）

导出后可加 --materials（以及 --layers）写出本仓库轻量 BOM / Y 切片，无需进游戏：

`powershell
.\venv\Scripts\python.exe scripts\export_litematic.py --input "outputs\samples\sample_000.npz" --materials --layers
`

或独立：scripts\materials_bom.py --input <npz|litematic> --layers。说明见 [nova-borrow.md](nova-borrow.md)。完整图标材料表仍推荐用 [Litematica-Nova](https://github.com/LitematicaViewer/Litematica-Nova) 打开 .litematic。


## 预览 GUI

编辑模式右侧勾选 **附带材料清单** / **附带分层预览**，再点 **导出到 companion**，与 CLI `--materials` / `--layers` 写到同一套 `materials/<stem>/` 布局。详见 [nova-borrow.md](nova-borrow.md)。

## 对接 mc-companion

完整游戏内步骤见 **[companion_export.md](companion_export.md)**。CLI 可先 `--print-dir` 确认目标文件夹。
