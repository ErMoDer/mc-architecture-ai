# 知识库索引

由 `scripts/kb_index.py` 自动生成。勿手改；改文档后重新运行脚本。

共 **47** 篇。

| id | title | path | tags | summary |
|----|-------|------|------|---------|
| `blocks-copper-family` | 铜系建筑方块（含 1.21 扩展） | [blocks/copper-family.md](blocks/copper-family.md) | block, copper | 试炼风/工业/青锈装饰；导出时优先涂蜡 ID，避免世界内继续氧化。 |
| `blocks-decorative-color-26.3` | 彩色结构件与 26.3 装饰 | [blocks/decorative-color-26.3.md](blocks/decorative-color-26.3.md) | block, 26.3 | 现代/营地/节日建筑的色带、屋顶与软装；区分「方块」与「实体」。 |
| `blocks-stairs-slabs-walls` | 楼梯 / 台阶 / 墙：形状族速查 | [blocks/stairs-slabs-walls.md](blocks/stairs-slabs-walls.md) | block | 建筑 AI 用「半砖/斜面/围墙」拼屋顶、檐口、女儿墙与围栏时的统一约定。 |
| `blocks-sulfur-cinnabar-26.2` | 硫黄 / 朱砂建筑族（Java 26.2） | [blocks/sulfur-cinnabar-26.2.md](blocks/sulfur-cinnabar-26.2.md) | block | 硫黄洞穴主题；红黄对比装饰；目标版 ≥26.2 才可原样导出。 |
| `blocks-tuff-family` | 凝灰岩系（Tuff）建筑族 | [blocks/tuff-family.md](blocks/tuff-family.md) | block, tuff | 1.21 试炼密室灰调石材；洞穴/地下建筑中性基底。 |
| `blocks-wood-sets` | 木系套装：原木 → 全套构件 | [blocks/wood-sets.md](blocks/wood-sets.md) | block, wood | 按「一套木头」生成住宅/谷仓时选对 ID 前缀，避免混搭无对应门窗。 |
| `builds-anti-box-policy` | Anti-box massing policy (night22) | [builds/anti-box-policy.md](builds/anti-box-policy.md) | build | overnight Phase1–4 反方盒体量规则摘要；生成/脚手架改代码时先读本页，再动立面（见 [facade-rhythm.md](facade-rhythm.md)）。 |
| `builds-block-roles` | 方块角色（给 similar_scaffold / look_harden） | [builds/block-roles.md](builds/block-roles.md) | build, block | 把「这是墙还是屋顶」收成机读角色，避免多数票把实心壳涂成同色糊。 |
| `builds-clean-materials` | Clean materials (净材) | [builds/clean-materials.md](builds/clean-materials.md) | build | Clean materials (净材) |
| `builds-facade-rhythm` | Facade rhythm after anti-box massing | [builds/facade-rhythm.md](builds/facade-rhythm.md) | build | 立面节奏（窗距 / 壁柱 / 门带）在 night22 L/T 体量之后如何取值；给 look_harden _STYLE_FACADE 与后续微调用。 |
| `builds-partition-style-policy` | Interior partition style policy (Phase D) | [builds/partition-style-policy.md](builds/partition-style-policy.md) | build | Interior partition style policy (Phase D) |
| `builds-poplar-dappled-26.3` | 斑驳森林 / 杨木主题建造笔记（26.3） | [builds/poplar-dappled-26.3.md](builds/poplar-dappled-26.3.md) | build, 26.3 | companion 目标版 **Java 26.3** 下「秋色林中小屋/营地」的调色与结构提示。 |
| `builds-roof-guidelines` | 屋顶建造准则摘要（改写） | [builds/roof-guidelines.md](builds/roof-guidelines.md) | build | 屋顶比例、坡度、大体量拆分与接缝的**项目向摘要**，供 look_harden 坡顶/平顶启发式使用。 |
| `builds-roof-types` | 屋顶类型速查摘要（改写） | [builds/roof-types.md](builds/roof-types.md) | build | 常见屋顶类型的**短定义 + 生成侧选用表**。不复制 Wiki 图文教程。 |
| `builds-shape-language` | 建筑形状语言（给体素 AI） | [builds/shape-language.md](builds/shape-language.md) | build | 把「好看的 MC 建筑」拆成可执行的楼梯/台阶/墙规则，约束 32³ 生成。 |
| `builds-structure-principles` | 建筑结构原则摘要（给 look_harden） | [builds/structure-principles.md](builds/structure-principles.md) | build | 把「地基 → 墙厚 → 层高 → 屋顶体量」收成可执行参数，喂给 `look_harden` / 结构约束。**原文改写摘要**，非 Wiki/官网全文照搬。 |
| `builds-trial-chambers-palette` | 试炼密室建筑语汇（调色，非攻略） | [builds/trial-chambers-palette.md](builds/trial-chambers-palette.md) | build | 生成「试炼风」室内/地牢走廊时的方块组合；不包含刷怪笼机制详解。 |
| `builds-window-opening-seal` | Window openings vs shell defects (Phase F) | [builds/window-opening-seal.md](builds/window-opening-seal.md) | build | Window openings vs shell defects (Phase F) |
| `farms-ai-layout-notes` | 建筑 AI：农场 / 刷怪布局注意事项 | [farms/ai-layout-notes.md](farms/ai-layout-notes.md) | farm | 建筑 AI：农场 / 刷怪布局注意事项 |
| `farms-crop-animal-farms` | 作物、甘蔗/竹子与动物农场（原理要点） | [farms/crop-animal-farms.md](farms/crop-animal-farms.md) | farm | 作物、甘蔗/竹子与动物农场（原理要点） |
| `farms-mob-spawning-basics` | 敌对刷怪规则入门（Java） | [farms/mob-spawning-basics.md](farms/mob-spawning-basics.md) | farm | 敌对刷怪规则入门（Java） |
| `farms-spawn-proofing` | 防刷与建筑共存（照明、半砖、地毯、城市规划） | [farms/spawn-proofing.md](farms/spawn-proofing.md) | farm | 防刷与建筑共存（照明、半砖、地毯、城市规划） |
| `farms-spawner-farms` | 刷怪笼农场与相关摘要（传送门 / 猪人） | [farms/spawner-farms.md](farms/spawner-farms.md) | farm | 刷怪笼农场与相关摘要（传送门 / 猪人） |
| `farms-tower-types` | 常见敌对刷怪塔类型（原理与布局约束） | [farms/tower-types.md](farms/tower-types.md) | farm | 常见敌对刷怪塔类型（原理与布局约束） |
| `farms-trading-hall` | 村民交易厅（原理与布局量级） | [farms/trading-hall.md](farms/trading-hall.md) | farm | 村民交易厅（原理与布局量级） |
| `farms-version-pitfalls` | 农场 / 刷怪版本坑（Java → 26.3） | [farms/version-pitfalls.md](farms/version-pitfalls.md) | farm, version | 农场 / 刷怪版本坑（Java → 26.3） |
| `redstone-ai-constraints` | 建筑 AI 的红石约束（别瞎放） | [redstone/ai-constraints.md](redstone/ai-constraints.md) | redstone | 建筑 AI 的红石约束（别瞎放） |
| `redstone-basics` | 红石入门：信号、时间与基本组件（Java） | [redstone/basics.md](redstone/basics.md) | redstone | 红石入门：信号、时间与基本组件（Java） |
| `redstone-block-updates` | 方块更新：NC / PP 与更新顺序（Java） | [redstone/block-updates.md](redstone/block-updates.md) | redstone, block | 讲清「谁通知谁变了」——理解 QC/BUD、观察者、计划刻的前置概念。给模板匹配与简化 tick 仿真用语对齐，**不是**完整原版引擎说明。 |
| `redstone-circuits-common` | 常用红石电路（Java / 26.3） | [redstone/circuits-common.md](redstone/circuits-common.md) | redstone | 周期性开关，驱动农场、灯、发射器。 |
| `redstone-components` | 红石组件细表（Java / 26.3） | [redstone/components.md](redstone/components.md) | redstone | 红石组件细表（Java / 26.3） |
| `redstone-copper-bulb-builds` | 铜灯泡用于建筑照明（短记） | [redstone/copper-bulb-builds.md](redstone/copper-bulb-builds.md) | redstone, build, copper | 补全「装饰照明」与红石开关灯；非工厂教程。 |
| `redstone-powering-charging` | 充能与激活：强弱电、供电 vs 激活（Java） | [redstone/powering-charging.md](redstone/powering-charging.md) | redstone | 把玩家理论里的「强/弱充能」「给方块供电 vs 激活组件」收成建筑 AI / 模板匹配能用的规则。加深 [basics.md](basics.md) §3，避免只背口诀。 |
| `redstone-qc-bud` | 准连接（QC）与 BUD（Java） | [redstone/qc-bud.md](redstone/qc-bud.md) | redstone | 把「附近方块发生了某种变化」变成红石脉冲/电平，而不是接一根显式输入线。 |
| `redstone-signals-timing` | 信号时序概念：瞬时线、活塞延伸与模板约束（Java） | [redstone/signals-timing.md](redstone/signals-timing.md) | redstone | 把《剖析 MC》里「瞬时导线 / 活塞延伸」收成**高阶概念 + 模板约束**，供匹配与预留空间——**不教 AI 发明**这类电路。 |
| `redstone-tile-ticks` | 计划刻 / Tile ticks（Java，中级） | [redstone/tile-ticks.md](redstone/tile-ticks.md) | redstone | 区分「红石 tick」与「方块计划刻」，方便分析报告与简化仿真对齐。不实现原版计划刻队列。 |
| `redstone-version-diffs` | 红石版本差异摘要（建筑 / 电路向） | [redstone/version-diffs.md](redstone/version-diffs.md) | redstone, version | 面向「换版本后电路坏了」和「生成装置该标最低版本」。 |
| `sources-mcje-principles-playlist` | untitled | [sources/mcje-principles-playlist.md](sources/mcje-principles-playlist.md) | sources |  |
| `versions-1.14-1.15` | 1.14–1.15：村庄与蜂巢（建筑向） | [versions/1.14-1.15.md](versions/1.14-1.15.md) | version | 1.14–1.15：村庄与蜂巢（建筑向） |
| `versions-1.16-nether` | 1.16 下界更新（建筑向） | [versions/1.16-nether.md](versions/1.16-nether.md) | version | 1.16 下界更新（建筑向） |
| `versions-1.17-1.18-caves` | 1.17–1.18：洞穴与悬崖（高度 / 新方块） | [versions/1.17-1.18-caves.md](versions/1.17-1.18-caves.md) | version | 1.17–1.18：洞穴与悬崖（高度 / 新方块） |
| `versions-1.19-1.20` | 1.19–1.20：荒野与旅途传说（建筑向） | [versions/1.19-1.20.md](versions/1.19-1.20.md) | version | 1.19–1.20：荒野与旅途传说（建筑向） |
| `versions-1.21-26.x` | 1.21–26.x：试炼、铜扩族与年号制（至 26.3） | [versions/1.21-26.x.md](versions/1.21-26.x.md) | version, 1.21 | 1.21–26.x：试炼、铜扩族与年号制（至 26.3） |
| `versions-ai-safe-palette` | AI 安全调色板：按版本生成 / 导出注意 | [versions/ai-safe-palette.md](versions/ai-safe-palette.md) | version | AI 安全调色板：按版本生成 / 导出注意 |
| `versions-breaking-changes` | 建筑相关：破坏性变更与失效项 | [versions/breaking-changes.md](versions/breaking-changes.md) | version | 建筑相关：破坏性变更与失效项 |
| `versions-flattening-1.13` | 1.13 Flattening 与建筑相关 ID | [versions/flattening-1.13.md](versions/flattening-1.13.md) | version | 1.13 Flattening 与建筑相关 ID |
| `versions-overview` | 版本时间线速查（Java Edition） | [versions/overview.md](versions/overview.md) | version | 朋友语气速查：每个节点「加了什么」「搞坏了什么」「对建筑 AI 意味着啥」。 |
