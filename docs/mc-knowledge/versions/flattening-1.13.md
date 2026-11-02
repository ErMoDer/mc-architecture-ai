# 1.13 Flattening 与建筑相关 ID

**版本**：Java 1.13（Update Aquatic，2018）  
**为何单独成篇**：这是现代 Java 方块命名的分水岭。本项目、Litematica、companion（26.3）全部建立在 Flattening 之后的 **namespaced ID** 上。

事实参考：[The Flattening](https://minecraft.wiki/w/The_Flattening_(Java_Edition))、[Java Edition 1.13](https://minecraft.wiki/w/Java_Edition_1.13)。

---

## 发生了什么

1. **取消数字方块 ID / 物品 damage（元数据）**  
   旧式 `5`、`5:1`、`wool:14` 等在 Java 正式玩法中作废。
2. **一个「种类 + 变体」拆成多个方块**  
   每种木板、每种颜色羊毛、每种台阶等都有独立资源位置。
3. **引入 / 强化方块状态（block states）**  
   朝向、对半、含水等用 `facing=`、`type=`、`waterlogged=` 表达，而不是塞进 ID。
4. **流体合并**  
   `flowing_water` 等旧概念失效；水用统一水方块 + 等级/含水状态。
5. **大量生物群系字符串重命名**  
   如 `hell` → `nether`（对建筑体素影响小，对数据包/定位大）。

---

## 建筑向：常用 ID 对照（节选）

> 下表「旧」指 1.12.2 及更早常见写法；「新」为 1.13+ 仍沿用至 26.3 的写法。完整表极长，只列生成/投影最常踩坑的。

### 木板与原木

| 旧（概念） | 新 ID |
|------------|-------|
| 橡木木板 | `minecraft:oak_planks` |
| 云杉木板 | `minecraft:spruce_planks` |
| 白桦木板 | `minecraft:birch_planks` |
| 丛林木板 | `minecraft:jungle_planks` |
| 金合欢木板 | `minecraft:acacia_planks` |
| 深色橡木木板 | `minecraft:dark_oak_planks` |
| 橡木原木 | `minecraft:oak_log`（轴用 `axis=`） |
| 木头（六面树皮） | `minecraft:oak_wood` 等 |

另有 **剥皮原木**（1.13）：`stripped_oak_log` 等——建筑装饰常用。

### 石材与砖

| 概念 | 新 ID 示例 |
|------|------------|
| 圆石 | `cobblestone` |
| 石砖 | `stone_bricks` |
| 苔石砖 | `mossy_stone_bricks` |
| 裂石砖 | `cracked_stone_bricks` |
| 雕纹石砖 | `chiseled_stone_bricks` |
| 平滑石头 | `smooth_stone`（后续版本配方稳定后常用） |

### 羊毛与染色

每种颜色独立，例如：

- `white_wool`、`orange_wool`、`magenta_wool`、…、`black_wool`  
- **不要**写 `wool` 或 `wool:14`。

混凝土、陶瓦、染色玻璃同理（`orange_concrete`、`blue_terracotta`、`cyan_stained_glass`…）。

### 台阶 / 楼梯 / 栅栏

旧「双石台阶 + 元数据」→ 各自独立，例如：

- `oak_slab`、`oak_stairs`、`oak_fence`、`oak_fence_gate`  
- `stone_brick_slab`、`stone_brick_stairs`、`cobblestone_wall`  

台阶状态常见：`type=bottom|top|double`（以目标版为准）。

### 门 / 活板门 / 按钮

- `oak_door`、`iron_door`、`oak_trapdoor`、`oak_button`…  
- 门有 `facing`、`half`、`hinge`、`open`、`powered` 等状态——**只存方块种类不存状态时，导出容易「门朝反/半扇错」**。

---

## 含水（waterlogged）——码头与半砖建筑

1.13 起，许多非实心方块可含水，例如楼梯、台阶、栅栏、铁栏杆、玻璃板、活板门、梯子、箱子、告示牌等。

| 要点 | 说明 |
|------|------|
| 状态 | `waterlogged=true/false` |
| 导出 | 若 Litematica/体素丢了 state，码头会「看起来有楼梯但没有水」 |
| AI | 当前 VAE 多半只学 **方块种类**；水域建筑建议后处理灌水或单独存 state |

---

## 失效 / 变更（建筑相关）

1. 任何依赖数字 ID 的旧 schematic 转换器必须跑一遍。  
2. 命令方块 / 函数里的 `setblock 5` 全部失效。  
3. 材质包路径与模型大量改名（对导出建筑本身影响小）。  
4. 碰撞箱与部分方块底部纹理修正——极老红石/门机制可能差一丝，但日常盖房可忽略。

---

## 对 AI 生成与 `.litematic` 的注意点

| 规则 | 做法 |
|------|------|
| 词表 | 只用 `minecraft:*` 现代 ID；拒绝数字 ID |
| 未知 ID | 导出前映射到同色近亲（见 [ai-safe-palette.md](ai-safe-palette.md)） |
| 状态 | 门、楼梯、台阶、原木轴、活塞朝向尽量保留；做不到就生成「无朝向敏感」的块为主 |
| 训练数据 | MCBlock / 旧图若含史前 ID，`prepare_data` 阶段必须规范化 |
| companion 26.3 | 完全是 Flattening 之后体系；再叠杨木等新 ID，见 [1.21-26.x.md](1.21-26.x.md) |

---

## 自查

- [ ] 投影里还有 `planks`、`wool`、`stone_slab` 这种「总类」吗？  
- [ ] `setblock` / `.mcfunction` 是否全是 namespaced？  
- [ ] 含水建筑是否打算后处理？  

下一篇可配合 [breaking-changes.md](breaking-changes.md) 与 [overview.md](overview.md) 一起读。
