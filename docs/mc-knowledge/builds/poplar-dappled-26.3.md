# 斑驳森林 / 杨木主题建造笔记（26.3）

**用途**：companion 目标版 **Java 26.3** 下「秋色林中小屋/营地」的调色与结构提示。

**来源**
- [Java版26.3](https://zh.minecraft.wiki/w/Java%E7%89%8826.3)
- [2026年第3次小更新](https://zh.minecraft.wiki/w/2026%E5%B9%B4%E7%AC%AC3%E6%AC%A1%E5%B0%8F%E6%9B%B4%E6%96%B0)（展示期摘要，正式内容以 26.3 条目为准）

---

## 生物群系与结构

- **斑驳森林（Dappled Forest）**：偏冷群系附近；地表砂土；杨树（红/橙/黄叶）+ 少量云杉；红灌木、棕色蘑菇、枯叶堆。
- **废弃营地（Abandoned Camp）**：多主世界森林类群系变种；羊毛楼梯、橡木栅栏、蛛网等；箱/铜箱/桶战利品。

---

## 推荐调色板（建筑 AI）

```
主材: poplar_planks, poplar_log, stripped_poplar_log
屋顶: poplar_stairs 或 橙/红 wool_stairs（营地风）
点缀: red_shrub（地毯层近似）, spruce_log 梁
地面: coarse_dirt / podzol / spruce_planks
灯光: lantern；避免过多火把破坏秋色氛围
```

叶子三色仅作环境，不建议大量实心叶墙（易糊、旧版无对应）。

---

## 与导出版本

| 目标 | 处理 |
|------|------|
| 26.3 | 原样 |
| 1.21 | poplar→birch；羊毛楼梯→羊毛；去掉坐垫实体 |
| 1.16 | 再去掉苍白橡木等，落回 oak/spruce |

详见 `versions/ai-safe-palette.md` G 组与降级表。
