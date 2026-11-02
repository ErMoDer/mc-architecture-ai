# 前期科技投影包（Early Tech Pack）

面向 **Minecraft Java 26.3（Wilderness Bound）** 生存开局：超级熔炉、铁矿、刷怪/经验塔，以及一份鸡舍红石参考。  
投影本体已拷进 companion 读取的 SCHEMATICS_DIR（PCL 26.3 的 schematics），进游戏后对 **Andy** 列出 / 建造即可。

本页讲「怎么用、先造谁」；文件来源与外站链接见仓库内  
schematics/early_tech_26.3/README.md。

## 游戏内中文名对照

| 游戏内文件名（不含 .litematic） | 用途 | 源文件（仓库） |
|---|---|---|
| 超级熔炉_15炉_V1_v26.3 | 紧凑 15 炉自动熔炉，开局优先 | schematics/early_tech_26.3/Super_Smelter_V1_15furnace.litematic |
| 超级熔炉_简易可扩展_v26.3 | Mysticat 简易可加长熔炉 | .../Simple_Super_Smelter_Mysticat.litematic |
| 超级熔炉_Oregano_20k_v26.3 | 大炉（约 20k/h、材料重），料多再造 | .../Super_Smelter_Oregano_20k.litematic |
| 小型铁矿_Zinko_v26.3 | 26.3 紧凑早期铁矿（首选） | .../Compact_Early_Iron_Farm_Zinko.litematic |
| 简易铁矿_大型_v26.3 | 占地更大的简易铁矿 | .../Easy_Iron_Farm.litematic |
| 大型刷怪经验塔_v26.3 | 通用刷怪/经验塔（非沼泽专精） | .../Mega_Mob_XP_Farm_1.21.litematic |
| 鸡舍_二_红石参考_v26.3 | 此前分析用的鸡舍红石参考（非 early_tech 外站包） | data/raw/mcblock/鸡舍_二__6b7d9b9d.litematic |

目标目录（与 mc-companion 的 SCHEMATICS_DIR 一致）：

C:\Users\16119\Desktop\PCL 下载\.minecraft\versions\26.3-Fabric 0.19.5\schematics

## 建议建造顺序

1. **超级熔炉_15炉_V1_v26.3**（或先用 超级熔炉_简易可扩展_v26.3）
2. **小型铁矿_Zinko_v26.3**
3. **大型刷怪经验塔_v26.3**（有沼泽后再换沼泽塔）
4. 铁/漏斗够了再上 **超级熔炉_Oregano_20k_v26.3** 或 **简易铁矿_大型_v26.3**
5. **鸡舍_二_红石参考_v26.3** 按需参考，不当作开局硬依赖

一句话：**熔炉 V1 → Zinko 铁矿 → 经验塔 → 大炉/大矿。**

## 进游戏怎么列 / 建（Andy）

前提：开 **26.3**、companion 已连上、需要时 /op Andy；站在打算落投影的位置附近。

聊天示例：

`	ext
Andy 列出投影
Andy 建造 超级熔炉_15炉_V1_v26.3
Andy 建造 小型铁矿_Zinko_v26.3
Andy 建造 大型刷怪经验塔_v26.3 旋转90
Andy 停建
`

更多指令见 E:\ai agent\mc-companion\README.md / 使用说明.txt，以及本仓库 [companion_export.md](companion_export.md)。

## 源目录与缺口

- **本包源目录：** E:\ai agent\mc-architecture-ai\schematics\early_tech_26.3\（含英文原名 .litematic 与 README.md）
- **同步到游戏目录：** 可跑 scripts/sync_early_tech_to_companion.py（幂等拷贝 + 中文名；不删其它投影）
- **仍缺、需浏览器手下一份：** 沼泽豪华刷怪塔  
  帖子：https://www.mcimg.com/forum-post/10306.html  
  （站点是 JS SPA，curl 下不到附件；下好后把 .litematic 放进 early_tech_26.3，再跑同步脚本即可。）

## 注意

- 外站投影多为 1.21+/26.x；漏斗/熔炉/铁傀儡等机制大体可用，**粘贴前请备份存档**。
- Oregano 大炉材料很重；作者提示大炉漏斗填料可按「每漏斗约 2 组」估算规模。
- 不要用建筑样例导出脚本去清 schematics；前期科技中文名文件应保留。
