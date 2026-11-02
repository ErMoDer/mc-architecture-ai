# 版本时间线速查（Java Edition）

朋友语气速查：每个节点「加了什么」「搞坏了什么」「对建筑 AI 意味着啥」。  
目标版：**26.3（Wilderness Bound）**。事实以 [minecraft.wiki](https://minecraft.wiki/) 为准；拿不准标「待核实」。

---

## 版本号怎么读（2026 起）

| 阶段 | 例子 | 说明 |
|------|------|------|
| 传统 1.x | `1.21`、`1.21.4` | 大版本 + 小更 |
| 年号制（2026+） | `26.1`、`26.2`、`26.3` | **年份.当年第几次正式投放** |
| companion | `MC_VERSION=26.3` | 与本机 PCL `26.3-Fabric` 对齐 |

`26.x` **不是**「1.26」的简写。内容上接在 1.21.x 系列之后；方块仍是 `minecraft:...` namespaced ID。

---

## 速查表（建筑 / 导出相关）

| 版本 | 常见称呼 | 大致年份 | 新内容（建筑向摘要） | 破坏性 / 失效注意 | 对建筑 AI |
|------|----------|----------|----------------------|-------------------|-----------|
| **1.13** | Update Aquatic / Flattening | 2018 | 海洋、珊瑚、剥皮原木；**方块 ID Flattening**；含水 `waterlogged` | 数字 ID / 元数据作废；`planks` 拆成 `oak_planks` 等 | **所有导出必须用 namespaced ID** |
| **1.14** | Village & Pillage | 2019 | 新村庄建筑、脚手架、鼓风机/烟熏炉、营火、石匠系石材用法变多 | 旧村庄结构大改；交易大改 | 中世纪村庄风素材更丰富 |
| **1.15** | Buzzy Bees | 2019 | 蜂箱、蜜脾块、蜂蜜块 | 较少破坏建筑 ID | 装饰块：蜜脾/蜂箱 |
| **1.16** | Nether Update | 2020 | 绯红/诡异木全套、黑石、玄武岩、下界合金、目标方块 | 下界地形/生物群系重做；部分旧下界导航失效 | **下界风格调色板**可用 |
| **1.17** | Caves & Cliffs Pt.I | 2021 | 铜、紫晶、滴水石、深板岩、凝灰岩、苔藓、缠根泥土 | 部分方块继续拆分（炼药锅等） | 洞穴装饰、铜氧化系列 |
| **1.18** | Caves & Cliffs Pt.II | 2021 | 世界高度扩到 **-64～319**；山地/洞穴生成大改 | 旧超平坦/自定义世界要迁移；**敌对刷怪要求方块光 0** | 山地/洞穴地形标签更重要；照明逻辑变了 |
| **1.19** | The Wild Update | 2022 | 红树全套、泥巴、幽匿系、深暗之域、悦灵 | 幽匿传感器会侦测振动（红石/农场相关） | 沼泽/深暗风格；注意振动与羊毛消音 |
| **1.20** | Trails & Tales | 2023 | **樱花/竹木**全套、吊牌、雕纹书架、饰纹陶罐、锻造模板 | 锻造「钻石→下界合金」改模板制 | 东亚/自然风调色板；展示用书架 |
| **1.20.5+** | （组件制铺垫） | 2024 | 物品组件（data components）推进 | 命令/数据包旧写法陆续失效 | 对体素导出影响小；对物品 NBT 大 |
| **1.21** | Tricky Trials | 2024-06 | 试炼密室、**合成器 crafter**、铜格栅/灯泡/门等、凝灰岩砖系、重锤、微风 | 不祥之兆等事件改动；活塞音效等小改 | 铜装饰大增；机械可用合成器 |
| **1.21.2–1.21.4** | Bundles / Garden Awakens 等 | 2024 | 收纳袋稳定化；**苍白橡木 Pale Oak**、树脂、嘎枝等（1.21.4） | 小更叠加方块 | 苍白花园风调色板 |
| **1.21.5–1.21.11** | Spring to Life / Chase the Skies / Copper Age / Mounts… | 2025 | 动物变种、幸福恶魂等；铜相关后续投放（细节以 wiki 为准） | 生态内容多，建筑块以官宣为准 | 生成前查目标版是否已有该 ID |
| **26.1** | Tiny Takeover | 2026-03 | 年号制首个投放 | 模组/插件生态可能滞后 | 确认 Fabric/Litematica 支持 |
| **26.2** | Chaos Cubed | 2026-06 | 内容见 wiki；建筑向摘要待补全篇 | 同上 | 同上 |
| **26.3** | Wilderness Bound | 2026-09-15 | **斑驳森林**、**杨树 poplar 全套**、架生蘑菇、红灌木、废弃营地；**羊毛/混凝土楼梯与台阶**；草垫床、坐垫 | 资源包/数据包格式升高；部分地图/结构相关改动 | **可生成新木种与彩色楼梯台阶**；旧投影缺 ID 时需替换 |

---

## 26.3 建筑向方块（companion 当前版）

导出进 26.3 世界时，下列系列可用（节选，完整表见 wiki「Java Edition 26.3」）：

| 系列 | 示例 / 说明 |
|------|-------------|
| 杨木套装 | `minecraft:poplar_log`、`poplar_planks`、`poplar_stairs`、`poplar_slab`、`poplar_door`、`poplar_fence`、`poplar_fence_gate`、`poplar_trapdoor`、`poplar_sign`、`poplar_hanging_sign`、`poplar_button`、`poplar_pressure_plate`、`poplar_shelf`、`poplar_sapling` 等 |
| 杨树叶 | 红/橙/黄三色杨树叶（wiki：red / orange / yellow poplar leaves）。写入导出前用游戏或 `/setblock` 核对确切 ID |
| 装饰植物 | `minecraft:red_shrub`；架生蘑菇（shelf mushroom，有大小变体） |
| 彩色结构块 | 16 色羊毛楼梯/台阶、16 色混凝土楼梯/台阶（可用切石机） |
| 营地相关 | `minecraft:straw_bed`（草垫床，一次性、不重置出生点）；**坐垫 cushion 是实体**，不是普通方块 |

> **对建筑 AI**：训练数据若来自旧版 MCBlock，可能没有杨木/羊毛楼梯。条件生成「autumn / dappled」风格时，可在后处理把橡木系映射到杨木系，或等数据扩充后再训。

---

## 和本项目的对应关系

| 项目环节 | 建议 |
|----------|------|
| `.litematic` / companion 建造 | 方块 ID ⊆ 目标版注册表；未知 ID 先替换成同色近亲 |
| 条件标签 `style` / `terrain` | 下界风 → 1.16+；樱花 → 1.20+；苍白 → 1.21.4+；斑驳秋林 → 26.3 |
| 预览调色板 | 可按版本分档（「1.16 下界」「1.20 樱花」「26.3 杨木」） |

---

## 参考

- [Java Edition version history](https://minecraft.wiki/w/Java_Edition_version_history)
- [Java Edition 1.21](https://minecraft.wiki/w/Java_Edition_1.21)
- [Java Edition 26.3](https://minecraft.wiki/w/Java_Edition_26.3)
- [The Flattening](https://minecraft.wiki/w/The_Flattening_(Java_Edition))
