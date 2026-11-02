# Minecraft 知识库（Java 版）

面向 **mc-architecture-ai** 与 **mc-companion** 的实用笔记：版本变动、红石原理、刷怪/农场、**建筑方块族**。  
目标环境：companion `.env` 中 `MC_VERSION=26.3`（Java **26.3 / Wilderness Bound**）。

> 默认以 **Java Edition** 为准；Bedrock 仅在必要时对照命名。

机器可读索引：[INDEX.md](INDEX.md) · [index.json](index.json) · 来源：[SOURCES.md](SOURCES.md)  
刷新索引：`python scripts/kb_index.py`

## 目录树

| 目录 | 内容 | 对接建筑 AI / 导出 |
|------|------|---------------------|
| [versions/](versions/) | 版本时间线、新方块、降级调色板 | 方块 ID 是否可导出 |
| [blocks/](blocks/) | 楼梯台阶墙、木系、铜/凝灰岩、26.x 色块 | 调色与构件选择 |
| [builds/](builds/) | 形状语言、杨木主题、试炼语汇 | 生成约束与风格 |
| [redstone/](redstone/) | 信号、延迟、常用电路 | 机械装置接口 |
| [farms/](farms/) | 刷怪塔、交易/刷怪笼、农场 | 布局硬约束 |

## 已写文档

### 总览与版本
- [versions/overview.md](versions/overview.md) — 版本时间线速查（1.13 → 26.3）
- [versions/breaking-changes.md](versions/breaking-changes.md) — 破坏性变更与降级
- [versions/ai-safe-palette.md](versions/ai-safe-palette.md) — 导出/生成安全调色板
- [versions/flattening-1.13.md](versions/flattening-1.13.md) — Flattening 与建筑 ID
- [versions/1.14-1.15.md](versions/1.14-1.15.md) — 村庄与蜂巢
- [versions/1.16-nether.md](versions/1.16-nether.md) — 下界木与黑石
- [versions/1.17-1.18-caves.md](versions/1.17-1.18-caves.md) — 洞穴与世界高度
- [versions/1.19-1.20.md](versions/1.19-1.20.md) — 红树 / 樱花 / 竹
- [versions/1.21-26.x.md](versions/1.21-26.x.md) — 试炼铜凝灰岩、杨木、羊毛楼梯

### 方块族（本批新增）
- [blocks/stairs-slabs-walls.md](blocks/stairs-slabs-walls.md) — 楼梯/台阶/墙规则
- [blocks/wood-sets.md](blocks/wood-sets.md) — 木系全套前缀
- [blocks/copper-family.md](blocks/copper-family.md) — 铜系与涂蜡
- [blocks/tuff-family.md](blocks/tuff-family.md) — 凝灰岩系
- [blocks/sulfur-cinnabar-26.2.md](blocks/sulfur-cinnabar-26.2.md) — 硫黄/朱砂（26.2）
- [blocks/decorative-color-26.3.md](blocks/decorative-color-26.3.md) — 彩色楼梯与 26.3 装饰

### 建造笔记（本批新增）
- [builds/shape-language.md](builds/shape-language.md) — 体素形状语言
- [builds/poplar-dappled-26.3.md](builds/poplar-dappled-26.3.md) — 斑驳林/杨木主题
- [builds/trial-chambers-palette.md](builds/trial-chambers-palette.md) — 试炼密室调色
- [builds/structure-principles.md](builds/structure-principles.md) — 结构原则（接 look_harden）
- [builds/block-roles.md](builds/block-roles.md) — 方块角色（墙/楼/柱/屋顶）
- [builds/clean-materials.md](builds/clean-materials.md) — 净材 / despeckle / 角色 fallback
- [builds/window-opening-seal.md](builds/window-opening-seal.md) — 窗洞 vs 破洞密封（Phase F）
- [builds/partition-style-policy.md](builds/partition-style-policy.md) — 分间风格分层（Phase D）
- [builds/roof-guidelines.md](builds/roof-guidelines.md) — 屋顶准则摘要
- [builds/roof-types.md](builds/roof-types.md) — 屋顶类型速查

### 红石
- [redstone/basics.md](redstone/basics.md) — 充能、tick
- [redstone/components.md](redstone/components.md) — 器件
- [redstone/circuits-common.md](redstone/circuits-common.md) — 常用电路
- [redstone/qc-bud.md](redstone/qc-bud.md) — QC 与 BUD
- [redstone/version-diffs.md](redstone/version-diffs.md) — 版本差
- [redstone/ai-constraints.md](redstone/ai-constraints.md) — 生成 AI 约束
- [redstone/copper-bulb-builds.md](redstone/copper-bulb-builds.md) — 铜灯泡建筑照明

### 农场 / 刷怪
- [farms/mob-spawning-basics.md](farms/mob-spawning-basics.md)
- [farms/tower-types.md](farms/tower-types.md)
- [farms/crop-animal-farms.md](farms/crop-animal-farms.md)
- [farms/spawn-proofing.md](farms/spawn-proofing.md)
- [farms/version-pitfalls.md](farms/version-pitfalls.md)
- [farms/ai-layout-notes.md](farms/ai-layout-notes.md)
- [farms/trading-hall.md](farms/trading-hall.md)
- [farms/spawner-farms.md](farms/spawner-farms.md)

## 怎么打开库

1. 资源管理器打开：`E:\ai agent\mc-architecture-ai\docs\mc-knowledge\`
2. 或用 VS Code / Cursor 打开该文件夹，从本 `README.md` 跳转
3. 查标签/路径优先用 `INDEX.md` 或 `index.json`

## 写作约定

- 优先写 **namespaced ID**（如 `minecraft:oak_planks`）
- 版本写 Java 格式号；26.x 同时注明投名（如 Wilderness Bound）
- 引用 wiki 时链接 [minecraft.wiki](https://minecraft.wiki/) 或 [zh.minecraft.wiki](https://zh.minecraft.wiki/)
- **摘要改写，禁止大段原文粘贴**；见 [SOURCES.md](SOURCES.md)
