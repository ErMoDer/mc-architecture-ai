# 硫黄 / 朱砂建筑族（Java 26.2）

**用途**：硫黄洞穴主题；红黄对比装饰；目标版 ≥26.2 才可原样导出。

**来源**
- [Java版26.2](https://zh.minecraft.wiki/w/Java%E7%89%8826.2)
- [Stairs](https://minecraft.wiki/w/Stairs)（含 sulfur/cinnabar 变种列表）
- [Wall](https://minecraft.wiki/w/Wall)

---

## 结构（两族对称）

每族均有：原块、磨制、砖、雕纹；以及楼梯 / 台阶 / 墙。

| 族 | 前缀（示意） | 色感 |
|----|--------------|------|
| 硫黄 Sulfur | `sulfur_` / `polished_sulfur_` / `sulfur_brick_` | 黄 |
| 朱砂 Cinnabar | `cinnabar_` / `polished_cinnabar_` / `cinnabar_brick_` | 红 |

镐挖掘；自然生成于硫黄洞穴及相关结构。

---

## AI / 导出

- `target_version=26.3`：可保留。
- `≤1.21`：映射到 `sandstone`/`red_sandstone` 或染色陶瓦，避免未知方块。
- 不要与下界硫相关玩法方块混淆；这里是**建筑石材族**。

> 精确 namespaced ID 以 26.3 客户端 `/give` 或方块报告为准；写入 schematic 前做白名单校验。
