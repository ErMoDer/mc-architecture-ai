# 木系套装：原木 → 全套构件

**用途**：按「一套木头」生成住宅/谷仓时选对 ID 前缀，避免混搭无对应门窗。

**来源**
- [Planks](https://minecraft.wiki/w/Planks)
- [Crafting/Building blocks](https://minecraft.wiki/w/Crafting/Building_blocks)
- [木楼梯](https://zh.minecraft.wiki/w/%E6%9C%A8%E6%A5%BC%E6%A2%AF)
- [Java版26.3](https://zh.minecraft.wiki/w/Java%E7%89%8826.3)

---

## 主世界木系（前缀）

| 前缀 | 风格直觉 | 最低 Java 大致版本 |
|------|----------|-------------------|
| `oak_` | 默认中世纪/村庄 | 早期 |
| `spruce_` | 冷色针叶、北欧 | 早期 |
| `birch_` | 浅色、现代/森林 | 早期 |
| `jungle_` | 热带 | 早期 |
| `acacia_` | 稀树草原橙木 | 1.7+ |
| `dark_oak_` | 厚重深色 | 1.7+ |
| `mangrove_` | 沼泽红褐 | 1.19 |
| `cherry_` | 樱粉、东亚风 | 1.20 |
| `bamboo_` / `bamboo_mosaic_` | 东方/轻盈 | 1.20 |
| `pale_oak_` | 苍白花园 | ~1.21.2+ |
| `poplar_` | 秋色斑驳林（26.3） | **26.3** |

下界：`crimson_` / `warped_`（不燃，无船）。

---

## 一套木头通常包含

```
{prefix}log / stripped_{prefix}log / {prefix}wood / stripped_{prefix}wood
{prefix}planks
{prefix}stairs / {prefix}slab / {prefix}fence / {prefix}fence_gate
{prefix}door / {prefix}trapdoor
{prefix}button / {prefix}pressure_plate
{prefix}sign / {prefix}hanging_sign
{prefix}boat 或 raft（竹） / chest boat
```

竹：原木位用 `bamboo_block` / `stripped_bamboo_block`，木板由竹块合成（效率与普通原木不同）。

---

## AI 选套规则

| 风格标签 | 推荐前缀 |
|----------|----------|
| medieval | oak + spruce 屋顶 |
| modern | birch / pale_oak + 混凝土 |
| sakura | cherry + 粉羊毛 |
| swamp | mangrove + mud_bricks |
| autumn / dappled | **poplar**（仅 26.3）否则 birch |
| nether / fantasy 暗 | crimson / warped + blackstone |
| asia_light | bamboo + bamboo_mosaic |

**约束**：同一立面主木材不超过 2 个前缀；门窗楼梯与墙板同前缀。
