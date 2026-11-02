# 红石原理（Java）

信号怎么传、延迟怎么算、常用电路怎么搭。建筑 AI 若要生成「能动的门/隐藏楼梯/简易自动化」，先读 basics，再读充能/更新与组件；涉及齐平门再读 QC。

目标环境：companion **MC_VERSION=26.3**。

片单入口（理解辅助，入库以 Wiki 摘要为准）：[sources/mcje-principles-playlist.md](../sources/mcje-principles-playlist.md)。

## 已写

| 文档 | 说明 |
|------|------|
| [basics.md](basics.md) | 信号强度、gt/rt、粉尘/中继器/比较器/观察者入门 |
| [powering-charging.md](powering-charging.md) | 强弱充能、供电 vs 激活（加深） |
| [block-updates.md](block-updates.md) | NC/PP 直觉、更新顺序、与 BUD 关系 |
| [tile-ticks.md](tile-ticks.md) | 计划刻 vs 红石 tick |
| [signals-timing.md](signals-timing.md) | 瞬时线/活塞延伸概念与模板约束 |
| [components.md](components.md) | 组件细表（含目标块、幽匿、铜灯泡、合成器） |
| [circuits-common.md](circuits-common.md) | 时钟、脉冲、RS/T、单向、物品运输红石 |
| [qc-bud.md](qc-bud.md) | 准连接 QC 与 BUD |
| [version-diffs.md](version-diffs.md) | 建筑/电路向版本差摘要 |
| [ai-constraints.md](ai-constraints.md) | 生成建筑时的红石约束 |
| [copper-bulb-builds.md](copper-bulb-builds.md) | 铜灯泡建筑向短注 |
| [redstone_principles_rules.json](redstone_principles_rules.json) | 机读规则：分析 D6 / 模板匹配注释 |

## 建议阅读顺序

1. `basics` → `powering-charging` → `components`  
2. `block-updates` → `tile-ticks`（要读懂 QC/农场时序时）  
3. `circuits-common` → `signals-timing`（要做装置 / 懂高级概念边界时）  
4. `qc-bud`（Java 隐藏门 / 怪活塞）  
5. `version-diffs`（换版或标 min_version）  
6. `ai-constraints`（接建筑 AI / 导出）

## 待写

- [ ] `circuits-doors.md` — 常见活塞门尺寸图（含非 QC 方案）  
- [ ] `circuits-item-filters.md` — 漏斗过滤与多物品分流详解  
- [ ] `sculk-redstone.md` — 振动频率表与消音施工  
- [ ] `crafter-factories.md` — 合成器产线实例  
- [ ] 对照 Bedrock 的「同功能不同接法」短表

## 和建筑 AI 的关系

当前体素模型**几乎不理解红石时序**。短期：机械用手搭或模板拼接；中期：外壳与电路分两层投影。默认遵守 `ai-constraints.md`。原理课缺口由本目录摘要补齐，**不**要求模型发明电路。

## 与分析器 tick 仿真

Phase-1 `redstone_tick_sim`：**1 sim tick = 1 rt = 2 gt**。读 [tile-ticks.md](tile-ticks.md) / [powering-charging.md](powering-charging.md)；机读规则见 [redstone_principles_rules.json](redstone_principles_rules.json)。仿真明确 **不是** 原版引擎。

- Analyze D5: qc_groups + observer face/rear; tick events observer_pulse / piston_bud_arm (coarse).
