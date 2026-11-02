# 方块角色（给 similar_scaffold / look_harden）

**用途**：把「这是墙还是屋顶」收成机读角色，避免多数票把实心壳涂成同色糊。

**接到代码**：src/app/scaffold_materials.py → 
esolve_role_materials()；生成侧 gen_strategy 传入 
ole_materials；观感侧 look_harden.pick_fill_ids。

---

## 角色表

| 角色 | 语义 | 典型方块 |
|------|------|----------|
| oundation | 地基条带 / 首层脚线 | 圆石、石砖、深板岩、混凝土 |
| wall | 外墙 1 格厚主体 | 砖、石砖、木板、混凝土 |
| loor | 楼板环（非满铺） | 木板、平滑石 |
| 
oof | 屋盖 / 坡顶体量 | 深色木板、深板岩、黑混凝土 |
| ccent / load_bearing | 角柱承重与立面竖向节奏 | 原木、铁块、石柱感满块 |
| window_frame | 窗楣窗台框 | 原木 / 铁 / 石 |
| glass / door | look_harden 单独解析 | 玻璃、门 |

**填充 vs 承重**：墙/楼板/屋顶是面层；角柱与墙墩（wall piers）才是竖向荷载路径。禁止用漏斗、锁链、红石当住宅质量角色。

## 风格调色直觉

| 风格 | 墙 | 顶 | 承重 |
|------|----|----|------|
| european | 砖 / 石砖 | 深色木板 | 橡木原木 |
| rustic | 橡木板 | 云杉板 | 橡木原木 |
| industrial | 灰混凝土 / 石砖 | 黑混凝土 | 铁块 / 抛光深板岩 |
| modern | 白混凝土 | 灰混凝土 | 铁 / 石英 |
| medieval | 石砖 | 深色木板 | 原木 |

## 结构硬规则（与 look_harden_rules.json 对齐）

1. 墙厚默认 **1**（32³）
2. 层间净空 **≥3**（loor_spacing 通常 5–6）
3. 楼板用 **环带**，默认 **不要十字走廊**（会像脚手架）
4. 承重：外轮廓 **四角柱** + 立面墙墩；室内不要随机竖柱
5. 屋顶：坡顶有檐；平顶（工业/现代）可无檐，但勿做实心箱盖

## 相关

- [structure-principles.md](structure-principles.md)
- [look_harden_rules.json](look_harden_rules.json)
- [wood-sets.md](../blocks/wood-sets.md)
