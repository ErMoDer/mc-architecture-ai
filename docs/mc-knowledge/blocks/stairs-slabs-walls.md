# 楼梯 / 台阶 / 墙：形状族速查

**用途**：建筑 AI 用「半砖/斜面/围墙」拼屋顶、檐口、女儿墙与围栏时的统一约定。

**来源**
- [Stairs](https://minecraft.wiki/w/Stairs)
- [台阶](https://zh.minecraft.wiki/w/%E5%8F%B0%E9%98%B6)
- [Wall](https://minecraft.wiki/w/Wall)
- [木楼梯](https://zh.minecraft.wiki/w/%E6%9C%A8%E6%A5%BC%E6%A2%AF)

---

## 共同规则（Java）

| 类型 | 合成效率 | 切石机 | 关键方块状态 |
|------|----------|--------|--------------|
| 楼梯 | 6 块 → 4 楼梯 | 石质/砖/铜/混凝土等可切（木/羊毛不可） | `facing` `half` `shape` `waterlogged` |
| 台阶 | 3 块 → 6 台阶（常见） | 同上 | `type`=`bottom/top/double` `waterlogged` |
| 墙 | 6 块 → 6 墙 | 可切 | `north/east/south/west`=`none/low/tall` `up` `waterlogged` |

- 楼梯会与相邻楼梯自动拼内角/外角（`inner_*` / `outer_*`）；正放与倒放互不拼接。
- 走上楼梯比跳跃不耗饥饿；完整面挡光，缺口透光。
- 墙对生物碰撞高约 1.5 格（类似栅栏），省材料围栏；蜘蛛/骆驼等仍可能越过。
- 墙与栅栏一般不相连，但可连栅栏门；可含水。

---

## 楼梯材料族（建筑相关摘录）

**木质**：oak / spruce / birch / jungle / acacia / dark_oak / mangrove / cherry / pale_oak / **poplar（26.3）** / bamboo / bamboo_mosaic / crimson / warped  

**石与砖**：stone、cobblestone、stone_bricks、深板岩系、**tuff / polished_tuff / tuff_bricks（1.21）**、brick、mud_brick、resin_brick、砂岩系、海晶石系、下界砖/黑石系、末地石砖、紫珀、石英  

**铜**：cut_copper 楼梯（四氧化阶段 × 涂蜡）  

**26.2**：sulfur / polished_sulfur / sulfur_brick；cinnabar / polished_cinnabar / cinnabar_brick  

**26.3**：16 色 `*_wool_stairs`；16 色 `*_concrete_stairs`

---

## 墙材料族（摘录）

圆石/石砖/花岗岩/闪长岩/安山岩、深板岩系、凝灰岩系、砖/泥砖/树脂砖、砂岩、海晶/下界/黑石/末地石砖；**26.2 硫黄与朱砂系墙**。无木墙。

---

## 给建筑 AI 的检查清单

1. 屋顶优先：同材质 `*_stairs` + `*_slab`，檐口用倒放楼梯（`half=top`）。
2. 围栏：石质用 `*_wall`；木质用 `*_fence`（不要误用墙 ID）。
3. 导出旧版时：羊毛/混凝土楼梯 → 同色全块或台阶；杨木 → birch/oak；硫黄/朱砂 → 相近石砖。
4. 体素模型若无楼梯状态，预览可近似为台阶；进游戏再靠 Litematica 细调。
