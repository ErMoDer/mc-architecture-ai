# 铜系建筑方块（含 1.21 扩展）

**用途**：试炼风/工业/青锈装饰；导出时优先涂蜡 ID，避免世界内继续氧化。

**来源**
- [Block of Copper](https://minecraft.wiki/w/Copper_Block)
- [Tricky Trials](https://minecraft.wiki/w/Tricky_Trials)
- [Java Edition 1.21](https://minecraft.wiki/w/Java_Edition_1.21)
- [铜](https://zh.minecraft.wiki/w/%E9%93%9C)

---

## 氧化四阶段 × 涂蜡

未涂蜡会随时间变色：`copper_block` → `exposed_copper` → `weathered_copper` → `oxidized_copper`。  
蜂巢涂蜡 → 对应 `waxed_*`；斧可刮蜡/降一级氧化；雷击可去锈。

**建筑 AI 默认一律输出 `waxed_` 前缀**，颜色稳定。

---

## 构件清单（每阶段都有 waxed）

| 构件 | 典型 ID 例 | 备注 |
|------|------------|------|
| 铜块 | `waxed_copper_block` | 存储/实心墙 |
| 切制铜 | `waxed_cut_copper` | 细纹理墙 |
| 切制楼梯/台阶 | `waxed_cut_copper_stairs` / `_slab` | 屋顶与收边 |
| 雕纹铜 | `waxed_chiseled_copper` | 1.21 装饰 |
| 铜格栅 | `waxed_copper_grate` | 透光/透水（以客户端为准） |
| 铜灯泡 | `waxed_copper_bulb` | 红石切换灯光；氧化越深越暗 |
| 铜门/活板门 | `waxed_copper_door` / `_trapdoor` | 1.21 |

切石机从铜块切切制系效率高于工作台。

---

## 与凝灰岩搭配

试炼密室语汇：**凝灰岩砖 + 涂蜡切制铜**。  
AI 标签 `style=trial` / `copper` → 见 [tuff-family.md](tuff-family.md) 与 `versions/ai-safe-palette.md` 的 F 组。

---

## 降级映射（目标版 < 1.21）

| 源 | 建议 |
|----|------|
| grate / bulb / chiseled_copper | `waxed_cut_copper` 或 `waxed_copper_block` |
| copper_door | `iron_door` 或木门 |
| 未涂蜡铜 | 强制改 waxed，再按版本裁剪 |
