# 信号时序概念：瞬时线、活塞延伸与模板约束（Java）

**用途**：把《剖析 MC》里「瞬时导线 / 活塞延伸」收成**高阶概念 + 模板约束**，供匹配与预留空间——**不教 AI 发明**这类电路。

**版本**：1.13 时代讲解的现象在 26.3 **大多仍可遇见**（活塞 12 格、短脉冲粘性特性等），但具体 compact 设计随版本有更替（观察者、铜灯泡常能替换老方案）。对照 [version-diffs.md](version-diffs.md)。

**来源（改写摘要）**
- [Redstone mechanics](https://minecraft.wiki/w/Redstone_mechanics)、[活塞](https://zh.minecraft.wiki/w/%E6%B4%BB%E5%A1%9E)
- 电路骨架见已有 [circuits-common.md](circuits-common.md)（时钟/脉冲/逻辑选型）
- 理解辅助：《剖析 MC》#8–9、#13；[sources/mcje-principles-playlist.md](../sources/mcje-principles-playlist.md)

---

## 1. 已经覆盖的（勿重复造轮子）

下列在 [circuits-common.md](circuits-common.md) / [basics.md](basics.md) 已写清，本篇只交叉引用：

- 时钟、脉冲延长/缩短、RS/T、单向、漏斗钟  
- 中继器 1–4 rt、比较器 1 rt、观察者短脉冲  

本篇补：**瞬时线概念**、**活塞延伸链约束**、**和更新/计划刻的边界**。

---

## 2. Instant wire（瞬时导线）——概念级

**玩家说法**：希望信号在「几乎同一红石 tick」内传过很长距离，而不是每 15 格一个中继器那样「加满再走」。

**现实**：

- 原版粉尘同 tick 传播，但**强度仍每格 -1**，满电只有 15 格。  
- 「瞬时线」通常指：**利用活塞/黏液块/特殊更新顺序**把「方块是否存在 / 是否导电」在同 tick 内改掉，从而让远处几乎同时看到变化——属于**高阶模板**，不是粉尘升级版。  
- 本项目：**禁止生成**；若方案需要，只能粘贴标注 `template:instant_wire_*` 且 `min_version` 明确的人工投影。

**AI 报告可用词**：`signal_path=dust_15` | `signal_path=repeater_chain` | `signal_path=template_instant`（仅当模板存在）。

---

## 3. 活塞延伸（Piston extender）——概念级

**玩家说法**：活塞推动另一活塞或黏液块，把结构推出超过单活塞行程。

**硬约束（模板匹配）**：

| 规则 | 说明 |
|------|------|
| 推限 | 单次推动链条有方块数上限（长期为 **12**；粘液/蜂蜜团另算） |
| 短脉冲粘性 | 过短脉冲可能「推了不拉」——可做 T 触发，也可导致门卡住 |
| 更新顺序 | 多活塞同 tick 伸出顺序敏感；**镜像/旋转模板必须重测** |
| 机腔 | 延伸门/床需预留深度；见 [ai-constraints.md](ai-constraints.md) 空间表 |

**建筑 AI**：只预留空洞 + 粘贴 `template:piston_door_*` / `template:extender_*`；禁止体素随机堆活塞。

---

## 4. 比较器与逻辑（补强一句）

逻辑门（与/或/非）本质是火把/中继器/比较器组合；选型表已在 circuits-common。  
比较器模式提醒：

- **比较**：后侧 ≥ 侧边 → 输出后侧强度。  
- **减法**：后侧 − 侧边。  
- **读容器**：满度 0～15——物品过滤、隐门密码常用。

不要用比较器「续航加满到 15」（那是中继器的工作）。

---

## 5. 时序对齐检查清单（模板粘贴后）

1. 电源是脉冲还是电平？执行器要哪一种？  
2. 延迟单位是 rt 还是计划刻？  
3. 是否依赖 QC / 同 tick 多活塞顺序？  
4. 粉尘是否超过 15 格未中继？  
5. `min_version` 是否 ≤ companion 26.3？

---

## 6. 对建筑 AI 的约束

**可用**

- 概念标签与空间预留；匹配已知模板 ID。  
- 在 SUMMARY/分析里写「建议改用铜灯泡 T 触发，避免短脉冲粘性门」。  

**不可用 / 不可宣称**

- 不可生成 instant wire / 飞行器 / 更新抑制桥。  
- 不可声称简化 tick 仿真覆盖瞬时线竞态。  
- 不可从视频教程坐标照抄到训练体素当「学到的红石」。

---

## 参考

- [circuits-common.md](circuits-common.md)、[qc-bud.md](qc-bud.md)、[block-updates.md](block-updates.md)、[tile-ticks.md](tile-ticks.md)
- Wiki：[活塞](https://zh.minecraft.wiki/w/%E6%B4%BB%E5%A1%9E)、[Redstone circuits](https://minecraft.wiki/w/Redstone_circuits)
