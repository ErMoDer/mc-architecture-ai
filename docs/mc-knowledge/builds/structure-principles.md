# 建筑结构原则摘要（给 look_harden）

**用途**：把「地基 → 墙厚 → 层高 → 屋顶体量」收成可执行参数，喂给 `look_harden` / 结构约束。**原文改写摘要**，非 Wiki/官网全文照搬。

**来源（请引用链接，勿当原文镜像）**
- [How to Structure your Build](https://www.minecraft.net/en-us/article/how-structure-your-build)（Minecraft.net / Guide to Creative 节选）
- 项目机读规则：[look_harden_rules.json](look_harden_rules.json)
- 屋顶细则：[roof-guidelines.md](roof-guidelines.md)、[roof-types.md](roof-types.md)

---

## 建造顺序（推荐）

1. **定形**：先选简单轮廓（矩形最稳；圆/球仅作点缀）。
2. **地基**：先落完整 footprint 底板，再起墙；避免「空中飘墙」。
3. **墙身**：外墙连续；小体量墙厚 1，大体量可 2（32³ 默认仍 1）。
4. **层高**：人可站立净空 **≥ 3**；常用墙高约 **4–5**（含楼板时 `floor_spacing≈5`）。
5. **洞口**：门居中、窗有节奏；再收檐口与屋顶。

## 形状语汇（官网节选意译）

| 形 | 用途 | AI 注意 |
|----|------|---------|
| 四边形 | 房间、平墙基底 | 默认 footprint |
| 三角 | 屋顶剖面、斜墙 | 内部难装修 |
| 圆/球 | 点缀或挑战体 | 32³ 代价高，后处理不硬造球 |
| 棱锥 / 三角棱柱 | 帐篷、阁楼感 | 用坡顶近似 |

## 机读默认（与 JSON 对齐）

| 规则 | 参数 | 默认 |
|------|------|------|
| 地基条带 | `foundation_height` | 1 |
| 墙厚 | `shell_thickness` | 1 |
| 最小净空 | `min_story_clear` | 3 |
| 楼板间距 | `floor_spacing` | 5 |
| 窗洞高×宽 | `window_height_*` / `window_width_*` | 1–2 × 1–2 |
| 窗列间距 | `window_spacing` | 3 |
| 门 | `door_width`×`door_height`，居中 | 1×2 |
| 檐口挑出 | `eave_overhang` | 1 |
| 坡顶升起上限 | `roof_rise_max` | 5 |

## 接到代码

- `src/app/look_harden.py` → `load_knowledge_rules()` / `knowledge_defaults()`
- 结构约束仍管空心/连通；观感后处理管壳、层、窗、门、檐、顶

## 承重与楼板（2026-10-20）

- **不要**在室内画十字楼板梁（X scaffolds）；楼板用沿墙环带。
- **承重路径**：外轮廓四角柱 + 立面墙墩；见 lock-roles.md 的 load_bearing。
- 空腔观感门槛：min_interior_room_air、max_floor_interior_cover（scaffold thresholds）。
