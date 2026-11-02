# 准连接（QC）与 BUD（Java）

**QC = Quasi-Connectivity（准连接）**  
**BUD = Block Update Detector（方块更新检测）**

这两样是 Java 红石「省空间活塞门」的灵魂，也是「为什么我没接线活塞自己动了」的元凶。  
**Bedrock 没有 QC**——跨版建筑电路不要共用同一张图。

参考：[Tutorial:Quasi-connectivity](https://minecraft.wiki/w/Tutorial:Quasi-connectivity)、[Tutorial:Block update detector](https://minecraft.wiki/w/Tutorial:Block_update_detector)、[Redstone mechanics](https://minecraft.wiki/w/Redstone_mechanics)。

---

## 1. QC 一句话

对 **活塞、粘性活塞、发射器、投掷器** 这几类：

> 除了给「自己」供电外，若 **正上方那一格**（即使是空气）处于被充能状态，也算它们被激活。

检查激活时，相当于多看了一个「头上」的充能位置。

动力铁轨等曾经受影响的组件，现代版本行为以 wiki 为准（多数已不像活塞这样 QC）。

---

## 2. 为什么会「BUD 住」

QC 的麻烦在于：**头上有电** 和 **本体收到方块更新** 不是一回事。

1. 你先给活塞**上方**供电（粉尘点亮上方实心块、红石块在上方侧面等）；  
2. 活塞「按理该动」但可能**先不动**——因为更新没传到本体；  
3. 附近任何方块更新（放块、拆块、邻居状态变）→ 活塞突然「醒过来」伸出。

这种「该动却等更新才动」的状态，常被叫做 **BUD-powered / budded piston**。  
注意：社区有时把 QC 和 BUD 混称，但 wiki 强调——**QC ≠ BUD**，只是很多 BUD 利用了 QC 的更新延迟。

---

## 3. 谁吃 QC？

| 组件 | QC？ |
|------|------|
| 活塞 / 粘性活塞 | 是 |
| 发射器 / 投掷器 | 是 |
| 普通门、灯、音符盒等 | 否（要直接供电逻辑） |
| 观察者 | 否（看的是正面更新） |

---

## 4. BUD 在干什么

**目的**：把「附近方块发生了某种变化」变成红石脉冲/电平，而不是接一根显式输入线。

经典结构直觉（活塞 BUD）：

1. 让粘性活塞处于「靠 QC 应该伸、但还没更新」的待机；  
2. 邻块一更新 → 伸出；  
3. 伸出后破坏自己的 QC 供电条件 → 缩回（自复位），打出一次脉冲。

现代很多场景可用 **观察者** 正面代替旧活塞 BUD，更直观、更少玄学——但紧凑齐平门仍大量用 QC。

---

## 5. 实战：想用 QC 时

| 用法 | 说明 |
|------|------|
| 省空间给活塞供电 | 线铺在活塞上前方块顶面，本体可不挨粉尘 |
| 齐平隐藏门 | 大量 Java 门图依赖 QC 与更新顺序 |
| 有意 BUD | 先 QC 供电，再在需要的时机打更新 |

调试技巧：怀疑 QC 时，看活塞**头顶一格**是否被粉尘/中继器/红石块间接点亮。

---

## 6. 实战：不想用 QC 时

1. 活塞正上方不要留「被充能的实心块 / 可被粉尘点亮的块」。  
2. 头顶不要走裸露粉尘（粉尘会弱充下方块，进而 QC）。  
3. 用中继器直接顶活塞侧面/背面，供电路径清晰。  
4. 发射器仓库：上方不要随手塞红石灯座。  

建筑生成时：机房层高至少留清「活塞顶上一格」，避免装饰地板误充能。

---

## 7. 版本注意

| 点 | 说明 |
|----|------|
| QC 是长期 Java 特性 | 官方已当特性维护，不是「随手修掉的纯 bug」 |
| 观察者（1.11+） | 新装置优先观察者检测更新 |
| 实验性红石改动（快照曾出现） | 曾尝试收紧粉尘更新范围，**会打碎大量 QC 设计**；是否进你玩的 26.3 正式规则以客户端为准——**待核实**若启用实验数据包 |
| 26.3 | 默认仍按经典 Java QC 理解；模组可能改红石 |

---

## 8. 和建筑 AI 的关系

- 体素网络**学不会**可靠 QC 时序。  
- 隐藏活塞门：用人工模板，不要让 AI「随机插活塞+粉尘」。  
- 约束见 [ai-constraints.md](ai-constraints.md)：住宅风默认 **禁止 QC 依赖**；仅 `redstone_expert_template` 才粘贴 QC 门。

---

## 9. 自查

- [ ] 这张图要给 Bedrock 用吗？有 QC 就废。  
- [ ] 活塞头顶一格什么状态？  
- [ ] 是「忘了接线却自己动」还是「故意 BUD」？  
- [ ] 能否改成观察者方案降低维护成本？

---

## 10. Coarse tick / analyze model (NOT vanilla)

| Item | Coarse behavior |
|------|-----------------|
| QC | Cell above piston + horizontal neighbors (dust/rs-block/repeater into that cell) |
| BUD | QC without body power -> arm; neighbor change or observer 1rt pulse -> extend flag (no push) |
| Observer | facing=watched; opposite=rear 15 for 1 rt; event observer_pulse |
| Report | D5 qc_groups + observer face/rear; D7 related events |

See principle rules nc_pp_block_update / observer_face_pulse.

