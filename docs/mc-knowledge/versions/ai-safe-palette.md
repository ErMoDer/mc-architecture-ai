# AI 安全调色板：按版本生成 / 导出注意

给 **mc-architecture-ai** 采样、方块替换、`.litematic` → companion（**26.3**）用的实用清单。  
原则：**宁可用旧而稳的 ID，也不要输出目标版不存在的方块。**

---

## 1. 总规则

1. 只输出 `minecraft:` namespaced ID（见 [flattening-1.13.md](flattening-1.13.md)）。  
2. 导出前指定 `target_version`（当前默认 **26.3**）。  
3. 未知 ID → 查下表「降级替换」，禁止原样写入。  
4. 会氧化的铜 → 优先 `waxed_*`。  
5. 门 / 楼梯 / 台阶 / 原木 / 活塞尽量带 state；不能带则少生成这类块。  
6. **实体不是方块**：画框、盔甲架、坐垫 cushion、物品展示框等不要当 setblock。  

---

## 2. 按目标版：可用「风格包」

### A. 万能保守包（≤1.13 语义，实际 ID 已是现代名）

适合：旧数据、最大兼容、不确定时兜底。

```
oak_planks, spruce_planks, birch_planks, dark_oak_planks,
oak_log, oak_stairs, oak_slab, oak_fence, glass, glass_pane,
cobblestone, stone_bricks, mossy_stone_bricks, bricks,
sandstone, smooth_stone, white_wool, red_wool, torch
```

### B. 村庄 / 中世纪+（≥1.14）

在 A 基础上加：

```
campfire, barrel, lantern, blast_furnace, smoker, stonecutter,
smithing_table, lectern, scaffolding(慎用), bell
```

### C. 下界风（≥1.16）

```
crimson_planks, warped_planks, crimson_stem, warped_stem,
blackstone, polished_blackstone_bricks, basalt, polished_basalt,
shroomlight, soul_lantern, nether_bricks, chaining→chain
```

### D. 洞穴 / 地下（≥1.17，高度叙事 ≥1.18）

```
cobbled_deepslate, polished_deepslate, deepslate_bricks, deepslate_tiles,
moss_block, moss_carpet, dripstone_block, amethyst_block, calcite,
waxed_copper_block, waxed_cut_copper, tinted_glass
```

### E. 沼泽 / 樱花 / 竹（≥1.19 / 1.20）

```
# ≥1.19
mangrove_planks, mangrove_log, mud_bricks, packed_mud
# ≥1.20
cherry_planks, cherry_log, bamboo_planks, bamboo_mosaic,
cherry_leaves, pink_petals
```

### F. 试炼铜厅（≥1.21）

```
waxed_copper_block, waxed_cut_copper, waxed_chiseled_copper,
waxed_copper_grate, waxed_copper_bulb, waxed_copper_door,
tuff_bricks, polished_tuff, chiseled_tuff_bricks
```

### G. 26.3 限定（companion 当前）

```
poplar_planks, poplar_log, poplar_stairs, poplar_slab, poplar_fence,
# 树叶颜色 ID 导出前在游戏内确认
red_shrub,
white_wool_stairs, orange_wool_stairs, red_wool_slab,
white_concrete_stairs, gray_concrete_stairs, orange_concrete_slab
# straw_bed 可用；cushion 不要当方块
```

---

## 3. 常见降级替换表（目标版缺 ID 时）

| 源（新） | 可降级为 | 备注 |
|----------|----------|------|
| `poplar_*` | `birch_*` 或 `oak_*` | 秋林风次选白桦 |
| `pale_oak_*` | `light_gray` 木 / `stripped_oak_*` | 苍白感近似 |
| `*_wool_stairs` | 同色 `*_wool` 或同色混凝土台阶（若有） | 26.3 才有羊毛楼梯 |
| `*_concrete_stairs` | 同色 `*_concrete` | |
| `waxed_copper_grate` | `waxed_cut_copper` | 1.21 前 |
| `tuff_bricks` | `deepslate_bricks` 或 `stone_bricks` | |
| `mangrove_*` | `dark_oak_*` | 深色木近似 |
| `cherry_*` | `birch_*` + 粉羊毛点缀 | |
| `bamboo_planks` | `jungle_planks` | |
| `sculk` | `deepslate` / `blackstone` | 避免误放传感器 |
| `crafter` | `crafting_table` | 仅外形兜底 |
| `decorated_pot` | `terracotta` 或带釉陶瓦 | |
| `candle` | `torch` / `lantern` | 无层数状态时 |

---

## 4. 导出到 companion 的检查清单

- [ ] 所有 ID 能在 26.3 创造搜索到  
- [ ] 无数字 ID、无 `planks`/`wool` 总类名  
- [ ] 铜已 waxed（若需要定妆）  
- [ ] 无 cushion / 画框等实体当方块  
- [ ] 门与楼梯朝向可接受，或已换成无朝向块  
- [ ] 文件已进 schematics，游戏内「列出投影」能看见  

---

## 5. 和训练标签的对应（建议）

| 条件标签 | 优先风格包 |
|----------|------------|
| `style=medieval` | A+B |
| `style=nether` / `fantasy` 暗色 | C |
| `terrain=cave` | D |
| `terrain=water` / swamp | E 红树 |
| `style=sakura` | E 樱花 |
| `style=trial` / copper | F |
| `style=autumn` / dappled | G 杨木 |

标签稀有时：先用 A 生成结构，再 **替换表** 上色，比硬训空标签稳。

---

## 6. 待核实

- 26.3 杨树叶精确 ID 字符串（红/橙/黄前缀写法）以你客户端为准。  
- Copper Age（1.21.10 一系）新增铜傀儡等相关块是否全部进 26.3 玩法包。  
- 模组（Fabric）是否额外改名或禁用原版块——以运行中的 26.3-Fabric 为准。
