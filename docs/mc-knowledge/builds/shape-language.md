# 建筑形状语言（给体素 AI）

**用途**：把「好看的 MC 建筑」拆成可执行的楼梯/台阶/墙规则，约束 32³ 生成。

**来源**（规则归纳自官方方块行为页，非照抄教程全文）
- [Stairs](https://minecraft.wiki/w/Stairs)
- [Wall](https://minecraft.wiki/w/Wall)
- [台阶](https://zh.minecraft.wiki/w/%E5%8F%B0%E9%98%B6)
- 项目内 [ai-safe-palette.md](../versions/ai-safe-palette.md)

---

## 立面层次（由外到内）

1. **轮廓**：完整方块墙身（木板/石砖/凝灰岩砖）。
2. **收边**：台阶做踢脚、窗台；楼梯做檐口/山墙斜面。
3. **洞口**：门高 2、窗 1×1 或 1×2；窗台用下台阶。
4. **顶饰**：倒放楼梯或墙垛；烟囱用墙或栅栏。

---

## 屋顶速查

| 屋顶 | 组成 | 注意 |
|------|------|------|
| 双坡 | 两侧朝向相对的楼梯 | 脊线可用台阶或满块 |
| 四坡 | 四向楼梯 + 角用自动内角 | 体素若无 shape，角会「硬」 |
| 平顶现代 | 混凝土 + 周边半砖女儿墙 | 26.3 可用混凝土楼梯收边 |
| 帐篷/营地 | 羊毛楼梯（26.3）+ 橡木栅栏 | 参考废弃营地语汇 |

---

## 禁止与降级

- 不要用墙 ID 当木栅栏；不要用坐垫当实心块。
- 红石构件默认不进住宅主体（见 `redstone/ai-constraints.md`）。
- solid_acc 低时：优先满块墙身，少用复杂楼梯角，导出后再手工修。

## Phase 2 采样约束

生成侧空心壳/楼层/屋顶启发式见项目根 [docs/structure_constraints.md](../../structure_constraints.md)。

## 相关

- [structure-principles.md](structure-principles.md) — 地基/层高/洞口顺序
- [roof-guidelines.md](roof-guidelines.md) / [roof-types.md](roof-types.md)
- [look_harden_rules.json](look_harden_rules.json) — 机读默认

## Phase B additive (2026-10-21)

- **Rooms**: Prefer T-split or cross partitions when the eroded interior is large; mid-only for industrial/modern lofts. Always leave a 2-high doorway so `room_air` stays connected.
- **Roof**: Residential pitched styles → hollow `skin_gable` + optional slope stairs; never solid attic fill. Industrial/modern → `flat_eave` lip only.
- **Piers**: Facade accents at wide spacing (≈8–12); load path = corners + wall piers, not random interior columns.
