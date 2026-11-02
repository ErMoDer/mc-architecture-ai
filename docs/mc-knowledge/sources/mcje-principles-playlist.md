# MCJE 原理剖析 · 优质片单 / 书单（精选）

整理时间：2026-10-19（Asia/Shanghai）  
用途：给人看的入门→进阶路径；入库摘要时优先对照 Wiki，视频只作理解辅助（版权：摘要自写，不整段照搬）。

**版本注意**：下列主系列多为 **Java 1.13.x** 讲解。充能/更新大框架仍适用，但活塞、更新抑制、部分农场与 26.3 有差异——落地到本项目时对照 `redstone/version-diffs.md` 与 [方块更新 Wiki](https://zh.minecraft.wiki/w/%E6%96%B9%E5%9D%97%E6%9B%B4%E6%96%B0)。

---

## A. 入门视频：LogicalGeekBoy《剖析 MC》/ Dissecting Minecraft

与 SciCraft 的 Methodz 合作，面向「半科技」玩家拆原理。原版 YouTube 合集 16 集：

- [YouTube 合集 Dissecting Minecraft](https://www.youtube.com/playlist?list=PLcSOIxw2nIE2OpQxG1ckMLsQ22Mu4Aiuc)

B 站熟肉入口（搬运组常见标题「【熟肉】《剖析MC》」；完整集数在 **红石科技搬运组** 收藏夹里找连载）：

- [《剖析MC》#1 基础红石元件（B站）](https://www.bilibili.com/video/BV1o4411H7kE/)

建议观看顺序（对建筑设计 AI / 红石模板最有用的优先）：

| 优先级 | 集 | 主题 | 为何值得看 |
|--------|----|------|------------|
| P0 | #1–2 | 基础元件、强弱充能 | 和模板匹配、分析报告用语对齐 |
| P0 | #3–4 | 脉冲、时钟 | tick 级理解、简单循环 |
| P0 | #5–7 | 逻辑门、常用电路、比较器 | 门控/漏斗线/物品检测 |
| P1 | #8–9 | 活塞延伸、飞行器 | 活塞门/移动结构；模板勿乱发明 |
| P1 | #13 | Instant wire | 高速信号路径概念 |
| P1 | #14–15 | TNT、Tile ticks | 计划刻/延迟；对应分析里的 tick 简化 |
| P2 | #10–11 | 刷怪 | 农场布局知识，非建筑壳 |
| P2 | #12, #16 | 七段数码管、破基岩 | 趣味/高阶；AI 模板优先级低 |

---

## B. 中文深度图文：Fallen_Breath《深度剖析 Minecraft》

源码向，解释 NC/PP 更新、计划刻等「为什么这样动」。文集标签：

- [深度剖析MC 标签页](https://blog.fallenbreath.me/tags/%E6%B7%B1%E5%BA%A6%E5%89%96%E6%9E%90MC/)

必读顺序：

1. [#0 绪论](https://blog.fallenbreath.me/zh-CN/2019/deeply-dissecting-minecraft_0/)
2. [#1 游戏流程](https://blog.fallenbreath.me/zh-CN/2019/deeply-dissecting-minecraft_1/)（若链接随站改动，从标签页进）
3. [#2 方块更新](https://www.bilibili.com/read/cv4565671/)（B站专栏镜像；博客站亦有）
4. [#3 / #3.4 计划刻与计划刻元件](https://blog.fallenbreath.me/tags/%E6%B7%B1%E5%BA%A6%E5%89%96%E6%9E%90MC/)

---

## C. 权威对照（入库摘要首选源）

视频/博客理解完后，摘要请以 Wiki 为准：

- [红石电路（中文 Wiki）](https://zh.minecraft.wiki/w/%E7%BA%A2%E7%9F%B3%E7%94%B5%E8%B7%AF?variant=zh-cn)
- [红石电路/充能与激活](https://zh.minecraft.wiki/w/%E7%BA%A2%E7%9F%B3%E7%94%B5%E8%B7%AF/%E5%85%85%E8%83%BD%E4%B8%8E%E6%BF%80%E6%B4%BB)
- [方块更新](https://zh.minecraft.wiki/w/%E6%96%B9%E5%9D%97%E6%9B%B4%E6%96%B0)
- [Redstone mechanics（英文）](https://minecraft.wiki/w/Redstone_mechanics)

入门图文补充（非视频）：

- [Java 红石技术基础指南（B站图文）](https://www.bilibili.com/opus/982894804656455713)

---

## D. 不优先（先别当「原理课」）

- 纯农场合集、只给成品存档不讲因果的搬运
- 过旧 1.8 理论若未标注「1.13 后仍适用」需交叉验证（gp 延迟理论可作历史参考）
- 破版/复制/更新抑制黑科技：可了解，但本项目红石路径是**模板匹配**，不要求 VAE 发明电路

---

## E. 建议学习路径（约 1 周碎片时间）

1. 看《剖析MC》#1–7（或 YouTube 对应集）  
2. 读 Wiki「充能与激活」+「方块更新」摘要页  
3. 扫 Fallen_Breath #2（方块更新）巩固 NC/PP  
4. 回头对照本仓库 `docs/mc-knowledge/redstone/*`，缺的再摘要入库  

下一步可选：按本片单把缺口摘要进 `redstone/`（更新顺序、计划刻、强弱充能加深）。
