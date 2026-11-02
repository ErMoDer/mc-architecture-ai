# Anti-box massing policy (night22)

**用途**： overnight Phase1–4 反方盒体量规则摘要；生成/脚手架改代码时先读本页，再动立面（见 [facade-rhythm.md](facade-rhythm.md)）。

**来源**：`src/app/gen_strategy.py` / `look_harden.py`；批次 `night22`→`night22d_20261022_005406`；游戏包 **夜齐_***。

---

## 硬规则

1. **禁止纯矩形满铺 footprint**（ pitched 住宅）：大 footprint 用 **L_wing** 或 **T_wing** 切一翼；中等可用 porch notch。
2. **工业 / 现代** 保持矩形 + 平顶（`skip_flat_style`），与 G 对照，勿硬套 L/T。
3. **上层退进** `_upper_setback_fp`：长边退 1–2 格；墙跟退进，**屋顶仍铺满 build_fp**（避免 P1 屋顶塌分）。
4. **门廊**：优先外向 cardinal 低体积；外沿无空时用 **inset**；中式 rng 跳过降至约 1/10；西部 T 翼用 **mild inset**（勿双切打穿屋顶）。
5. **坡顶**：`skin_gable` 升坡、控 plateau；中世/奇幻用较宽 plateau（≈0.70）对齐 G 的 roof_score；楼梯环加厚。

## 风格速查（night22d）

| style | anti | porch | 备注 |
|-------|------|------|------|
| industrial / modern | skip_flat | none | 与 G bit-match 对照 |
| european / rustic / chinese / western | T_wing | inset / entry / mild | 中式 porch 已开 |
| medieval / fantasy | L_wing | entry | roof≈G；勿再猛切 |

## 明确不做（本窗口）

- 交叉坡 / 四坡 hip（32³ + L/T 上易塌）
- 多栋院落 / U 型院子
- VAE / CUDA 续训

## 验收

- `structure_ok` 全风格；游戏导出优先 **夜齐_***，次选 **夜改3_***。
- 观感仍偏「单体 + 一翼」时：下一刀是 cross-gable/hip 或复合体量，**不是**加窗加柱遮方盒。

## night22e

- Cross-gable enabled for european/chinese/rustic; pack **夜坡_***. Hip/courtyard still residual.
