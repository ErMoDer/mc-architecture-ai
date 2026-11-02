# 投影读懂报告（Phase 1）

对单个 `.litematic` 做**规则/图启发式**分析，输出中文 Markdown 报告（可选 JSON）。

## 做什么

- **概览 / 结构 / 美术**：体量、空心、楼层粗估、材质桶、风格猜测
- **红石（加深）**：
  - **D1 构成**：元件清单 + 角色桶
  - **D2 连通**：facing 感知邻接图 + 分量推断
  - **D3 信号强度**：粉尘按 **形状臂**（none/side/up）连通后 −1/格；实心强/弱充能；比较器 compare/subtract 真值（容器满度启发档）
  - **D4 时钟**：结构启发式时钟线索
  - **D5 QC/BUD**：Java 准连接 / BUD 嫌疑
  - **D6 原理**：知识库短摘录 + `redstone_principles_rules.json` 触发的规则 id（NC/PP、强弱充能、计划刻、瞬时线边界等）
  - **D7 简化 tick 仿真**：40–80 **rt**（1 rt=2 gt）；比较器 1 rt 延迟；强充穿实心粗模型；按钮脉冲；事件计数；关联 principle_rules（非原版对等、不推方块）
  - **D9 常用+少见电路模式**：门线/时钟/漏斗线/活塞门/QC/IO/锁存；Etho钟/投掷电梯/零刻BUD/脉冲/火把逻辑/瞬间线/幽匿/标靶/铜灯泡/音符盒/探测轨；多活塞推杆/飞船/传送门/烧炼酿造/水流滤器/潜影盒/日光钟/绊线/陷阱箱/讲台/雕纹书架/合成器等
  - **D8 局限**

分析使用完整区域；红石朝向依赖 `load_litematic_detailed`。

## 不做什么

- 不训练 / 不改 VAE / 不做 64³ / 不改 UI
- **简化 tick ≠ 原版引擎**；不保证电路在游戏内可运行
- 火把：1 tick 延迟；压在粉尘上不自熄；60 tick 内≥8 翻转先 soft-lock，再狂翻才烧毁
- QC：上方/上方邻格供电并稳定≥1 tick；仅 QC 无直供 → BUD 待机，邻接信号变化才伸出（仍不推动方块、无完整更新链）
- **不完整**建模：容器 NBT 真实满度、侧向非粉尘软充、实心块链条传强充、BUD 更新传播链
- Bedrock **无 QC**——QC 线索仅对 Java 有意义
- 粉尘 up 臂已接入连通图（如鸡舍 QC 线与上层粉尘）；**不推动方块**时换块器/QC 岛仍可能终态无电
- 常用/少见模式均为骨架线索；冰船等依赖实体的不识别
- 零刻/BUD 自走、XOR 等仅低置信结构启发，不做完整真值验证
- 不自动复刻电路

## 用法

```bat
.\.venv\Scripts\python.exe scripts\analyze_litematic.py data\raw\mcblock\某个.litematic --write-json
```

默认输出：`outputs/analyze/<stem>_report.md`（及可选 `.json`）。

## 模块

- `src/app/schematic_analyze.py` — 总报告
- `src/app/redstone_analyze.py` — 红石构成/图/Markdown
- `src/app/redstone_principles.py` — 原理规则表加载与报告挂载
- `docs/mc-knowledge/redstone/redstone_principles_rules.json` — 机读规则（非引擎）
- `src/app/redstone_physics.py` — QC·BUD / 时钟；强度委托 `redstone_strength.py`
- `src/app/redstone_strength.py` — 强弱充能 + 比较器真值
- `src/app/dust_connect.py` — 粉尘形状/臂连通
- `src/app/redstone_patterns.py` — 常用电路模式识别
- `src/app/redstone_tick_sim.py` — 简化离散 tick 仿真（rt/gt 标注、事件、原理规则挂载）
- `tests/test_redstone_tick_sim.py` — 粉尘/中继器/比较器/按钮粗测
- `src/data/litematic.py` — `load_litematic` / `load_litematic_detailed`

相关：Phase4 红石模板见 docs/redstone_templates.md

- D5 QC/observer: qc_groups, observer face/rear; BUD pattern-only. D7 may show observer_pulse / piston_bud_arm.
