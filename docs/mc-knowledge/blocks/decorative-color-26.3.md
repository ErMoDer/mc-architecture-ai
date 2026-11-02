# 彩色结构件与 26.3 装饰

**用途**：现代/营地/节日建筑的色带、屋顶与软装；区分「方块」与「实体」。

**来源**
- [Java版26.3](https://zh.minecraft.wiki/w/Java%E7%89%8826.3)
- [Stairs](https://minecraft.wiki/w/Stairs)（羊毛/混凝土楼梯）
- [Planks](https://minecraft.wiki/w/Planks) / [Crafting/Building blocks](https://minecraft.wiki/w/Crafting/Building_blocks)

---

## 26.3 新增结构色块

| 类型 | 数量 | 合成提示 | AI 注意 |
|------|------|----------|---------|
| 羊毛楼梯 / 台阶 | 16 色 | 工作台用羊毛 | 易燃；旧版 → 同色羊毛全块 |
| 混凝土楼梯 / 台阶 | 16 色 | 工作台或切石机 | 硬装首选；旧版 → 同色混凝土 |
| 标签 | `#concrete_stairs` `#concrete_slabs` 等 | — | 数据包/命令可用 |

颜色名与羊毛一致：`white_` … `black_` 前缀 + `wool_stairs` / `concrete_slab` 等。

---

## 杨木相关自然装饰

- 杨树叶：红 / 橙 / 黄三色树冠（斑驳森林）。
- `red_shrub`：地表红灌木斑块。
- 层孔菇（shelf mushroom）：树干装饰；有弹性，**不是**普通墙砖。
- 麦秆床 `straw_bed`：可睡过夜但**不设重生点**，一次性；下界/末地尝试会毁。

---

## 坐垫（实体，不是方块）

- 16 色坐垫：由 3 个同色羊毛台阶合成；放置后可坐。
- **禁止**当 `setblock` 实心方块写入体素/示意图核心；导出时忽略或改为地毯/台阶近似。

---

## 经典装饰（各版通用，建筑常用）

`lantern` / `soul_lantern`、`campfire`、`flower_pot`、染色玻璃/玻璃板、陶瓦与带釉陶瓦、蜡烛（需状态）、铁栏杆、锁链。

现代风：混凝土色带 + 铜灯；中世纪：灯笼 + 原木梁 + 楼梯檐。
