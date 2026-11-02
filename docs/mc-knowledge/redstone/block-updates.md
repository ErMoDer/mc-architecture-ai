# 方块更新：NC / PP 与更新顺序（Java）

**用途**：讲清「谁通知谁变了」——理解 QC/BUD、观察者、计划刻的前置概念。给模板匹配与简化 tick 仿真用语对齐，**不是**完整原版引擎说明。

**版本**：主系列讲解多基于 ~1.13；**NC/PP 大框架在 26.3 仍成立**。活塞链、更新抑制、实验性粉尘规则见 [version-diffs.md](version-diffs.md)。细节以 Wiki 为准。

**来源（改写摘要，非原文）**
- [方块更新（中文 Wiki）](https://zh.minecraft.wiki/w/%E6%96%B9%E5%9D%97%E6%9B%B4%E6%96%B0)
- [Redstone mechanics](https://minecraft.wiki/w/Redstone_mechanics)
- 理解辅助：Fallen_Breath《深度剖析》#2 方块更新；片单见 [sources/mcje-principles-playlist.md](../sources/mcje-principles-playlist.md)

---

## 1. 一句话

方块状态一变，引擎会按规则**通知邻居**（或更远的格子）去重新检查自己该不该动——这就是**方块更新**。红石「突然醒了 / 突然卡了」往往卡在：**充能条件已满足，但更新还没送到执行器**。

---

## 2. NC 与 PP（社区常用称呼）

社区与剖析文常把更新粗分成两类（名称随作者略有出入，含义如下）：

| 称呼 | 直觉 | 典型触发 |
|------|------|----------|
| **NC（Neighbor Changed）** | 「邻居告诉你：我变了」 | 邻格放置/破坏/状态变；多数组件被邻接粉尘点亮后的检查 |
| **PP（形如 Comparator/计划刻相关的二次通知，社区或称 shape / comparator update 等）** | 「形状/比较器链/更远依赖也要再算一遍」 | 比较器读容器、部分状态变化沿链条传播；与「只看六面邻居」不完全同一套 |

入库记法（够用）：

1. **先有状态变化，才有更新**——没有更新，活塞可能「QC 该动却不动」（见 [qc-bud.md](qc-bud.md)）。  
2. **观察者**专门「看见」正面的方块更新并吐脉冲——用观察者比手搓 BUD 更可预期。  
3. 本项目**不实现**完整 NC/PP 调度器；分析报告里最多写「依赖方块更新 / 可能 BUD」。

> 术语「PP」在不同文章里不完全等同。若与某源码分析文冲突，以 **Wiki「方块更新」** 与实测为准，并把差异标 **待核实**。

---

## 3. 更新顺序（直觉级）

同一 game tick 内，引擎会处理一串待办。对建筑/红石模板有用的直觉：

1. **粉尘网络**往往在同 tick 内快速传开（0 红石延迟的「线」），但**中继器/比较器/活塞**有自己的延迟档。  
2. **多个活塞同 tick 被激活**时，伸出顺序与位置有关——齐平门模板必须按已验证布局粘贴，不能旋转后指望行为不变。  
3. **计划刻（tile tick）** 是另一条队列（水流、农作物、部分延迟行为），见 [tile-ticks.md](tile-ticks.md)；不要和「红石 tick」混为一谈。

---

## 4. 和 QC / BUD 的关系

| 现象 | 更新视角 |
|------|----------|
| QC 活塞头上有电却不动 | 激活条件已满足，**缺一次传到本体的更新** |
| 邻块一变活塞突然伸出 | 更新到了 → BUD 行为 |
| 观察者替代旧 BUD | 把「更新」显式变成脉冲，少玄学 |

详见 [qc-bud.md](qc-bud.md)。

---

## 5. 对建筑 AI 的约束

**可用**

- 在报告/注释里写：`needs_block_update`、`may_bud`、`prefer_observer_over_bud`。  
- 模板元数据：`update_sensitive=true`（不可随意镜像/旋转）。  
- 预留机房时避开「头顶误铺电源」除非模板明确需要 QC。

**不可用 / 不可宣称**

- 不可声称 VAE/体素模型「会算完整 NC/PP 顺序」。  
- 不可自动发明 BUD/更新抑制电路；齐平门只用人工 Java 模板。  
- 不可把 1.13 教程的更新抑制黑科技默认搬到 26.3。

---

## 参考

- Wiki：[方块更新](https://zh.minecraft.wiki/w/%E6%96%B9%E5%9D%97%E6%9B%B4%E6%96%B0)、[Redstone mechanics](https://minecraft.wiki/w/Redstone_mechanics)
- 片单：[mcje-principles-playlist.md](../sources/mcje-principles-playlist.md)
- 续读：[powering-charging.md](powering-charging.md)、[tile-ticks.md](tile-ticks.md)、[qc-bud.md](qc-bud.md)
