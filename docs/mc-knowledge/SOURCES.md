# 知识库来源与许可说明

本目录文档为 **mc-architecture-ai** 项目内部笔记：对公开 Wiki/指南做**改写摘要**与清单化，**不是**原文复制。

## 许可

- [minecraft.wiki](https://minecraft.wiki/) 与 [zh.minecraft.wiki](https://zh.minecraft.wiki/) 内容通常以 **CC BY-NC-SA** 等条款发布（以各站页脚为准）。
- 本仓库笔记：释义 + 结构化摘要 + 项目向检查清单；保留下方来源链接便于追溯。
- 请勿把本目录再当作「Wiki 原文镜像」二次发布。

## 本批抓取并摘要的 URL

| URL | 用于文档 |
|-----|----------|
| https://minecraft.wiki/w/Stairs | blocks/stairs-slabs-walls.md |
| https://zh.minecraft.wiki/w/%E5%8F%B0%E9%98%B6 | blocks/stairs-slabs-walls.md |
| https://minecraft.wiki/w/Wall | blocks/stairs-slabs-walls.md |
| https://zh.minecraft.wiki/w/%E6%9C%A8%E6%A5%BC%E6%A2%AF | blocks/stairs-slabs-walls.md, wood-sets.md |
| https://minecraft.wiki/w/Planks | blocks/wood-sets.md, decorative-color-26.3.md |
| https://minecraft.wiki/w/Crafting/Building_blocks | blocks/wood-sets.md |
| https://minecraft.wiki/w/Copper_Block | blocks/copper-family.md |
| https://zh.minecraft.wiki/w/%E9%93%9C | blocks/copper-family.md |
| https://minecraft.wiki/w/Tricky_Trials | copper-family, trial-chambers-palette, copper-bulb-builds |
| https://minecraft.wiki/w/Java_Edition_1.21 | copper-family.md |
| https://zh.minecraft.wiki/w/Java%E7%89%881.21 | tuff-family.md |
| https://minecraft.wiki/w/Tuff | blocks/tuff-family.md |
| https://zh.minecraft.wiki/w/%E5%87%9D%E7%81%B0%E5%B2%A9%E5%A2%99 | blocks/tuff-family.md |
| https://minecraft.wiki/w/Trial_Chambers | builds/trial-chambers-palette.md |
| https://zh.minecraft.wiki/w/Java%E7%89%8826.2 | blocks/sulfur-cinnabar-26.2.md |
| https://zh.minecraft.wiki/w/Java%E7%89%8826.3 | decorative-color, poplar-dappled, wood-sets |
| https://zh.minecraft.wiki/w/2026%E5%B9%B4%E7%AC%AC3%E6%AC%A1%E5%B0%8F%E6%9B%B4%E6%96%B0 | builds/poplar-dappled-26.3.md（展示期对照） |

## 未成功 / 跳过

- 未单独抓取基岩版长页作主来源（本库以 Java 为准；仅在楼梯历史等处对照命名）。
- 农场/交易大厅类：已有 `farms/` 多篇，本批未重复灌入长攻略。
- 部分方块精确 ID 字符串以客户端校验为准（笔记中已标明）。

## 抓取时间

约 2026-10-17（Asia/Shanghai）；Wiki 可能后续改版，以链接页为准。

## 建筑原则批（2026-10-18）

| URL | 用于文档 |
|-----|----------|
| https://www.minecraft.net/en-us/article/how-structure-your-build | builds/structure-principles.md |
| https://minecraft.wiki/w/Tutorial:Roof_construction_guidelines | builds/roof-guidelines.md, look_harden_rules.json |
| https://minecraft.wiki/w/Tutorial:Roof_types | builds/roof-types.md |

抓取时间：2026-10-18（Asia/Shanghai）；**仅改写摘要**，禁止整页粘贴。


## 外部数据集（2026-10-18）

| 来源 | 许可 | 本地路径 | 说明 |
|------|------|----------|------|
| https://huggingface.co/datasets/Hack337/Minecraft-Schematics | MIT（上游 README） | data/raw/hack337/ | 669 蓝图 + schematics；见 docs/hack337.md；LOCAL_ONLY 勿推送 |


## 红石原理片单摘要批（2026-10-19）

片单索引：[sources/mcje-principles-playlist.md](sources/mcje-principles-playlist.md)（视频/博客仅理解辅助；正文为 Wiki 向**改写摘要**）。

| URL | 用于文档 |
|-----|----------|
| https://zh.minecraft.wiki/w/%E6%96%B9%E5%9D%97%E6%9B%B4%E6%96%B0 | redstone/block-updates.md, tile-ticks.md |
| https://zh.minecraft.wiki/w/%E7%BA%A2%E7%9F%B3%E7%94%B5%E8%B7%AF/%E5%85%85%E8%83%BD%E4%B8%8E%E6%BF%80%E6%B4%BB | redstone/powering-charging.md |
| https://minecraft.wiki/w/Redstone_mechanics | powering-charging, block-updates, signals-timing |
| https://minecraft.wiki/w/Tick | redstone/tile-ticks.md |
| https://zh.minecraft.wiki/w/%E6%B4%BB%E5%A1%9E | redstone/signals-timing.md |
| https://minecraft.wiki/w/Redstone_circuits | signals-timing（交叉 circuits-common） |
| https://blog.fallenbreath.me/tags/%E6%B7%B1%E5%BA%A6%E5%89%96%E6%9E%90MC/ | 理解辅助（NC/PP、计划刻）；不入库原文 |
| https://www.youtube.com/playlist?list=PLcSOIxw2nIE2OpQxG1ckMLsQ22Mu4Aiuc | 片单 Dissecting Minecraft；不入库逐字稿 |

整理时间：2026-10-19（Asia/Shanghai）。禁止整页 Wiki / 视频字幕粘贴。
