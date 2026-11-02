# Facade rhythm after anti-box massing

**用途**：立面节奏（窗距 / 壁柱 / 门带）在 night22 L/T 体量之后如何取值；给 look_harden _STYLE_FACADE 与后续微调用。

**来源**：项目 src/app/look_harden.py _STYLE_FACADE；批次 
ight22d_20261022_005406；游戏包 夜齐_*。

---

## 原则

1. **先体量、后立面**：anti-box（L/T 翼、退进、门廊/inset、陡坡顶）先定 footprint；再跑 facade rhythm。不要用加窗/加柱去遮方盒。
2. **壁柱是强调不是承重林**：wall_pier_spacing 宜宽（约 8–12）；角柱保留；禁止室内乱柱。
3. **窗洞与碎洞分开**：像窗的开口保留（有玻璃更好）；小碎洞才封。见 [window-opening-seal.md](window-opening-seal.md)。

## 当前 knobs（2026-10-22）

| style | window_spacing | wall_pier_spacing | notes |
|-------|----------------|-------------------|-------|
| european | 4 | 8 | max bands 3；夜齐 roof≈0.75 |
| chinese | 3 | 8 | 门廊 inset 已开 |
| rustic | 4 | **12** | 曾过密，保持宽距 |
| western | 3 | 8 | mild inset + T |
| medieval | 3 | 8 | L_wing；roof≈0.94 |
| fantasy | 4 | **5** | euro_fan_dens 后中档 |
| modern | 6 | off | flat；严格开洞 |
| industrial | 4 | 8 | flat_eave；与 G 对照 |

## night22 之后立面仍弱的点

- 交叉坡 / 四坡未做 → 立面再密窗也仍像单一体量。
- 欧式 inset 门廊有了，但立面分带仍偏匀。
- 下一刀优先：**交叉坡/hip** 或 **欧式窗带非匀间距**；不要再广扫 pier。

## 游戏 / 预览

- 投影优先：夜齐_*_v26.3.litematic（PCL 26.3-Fabric schematics）
- 预览批次：outputs/design/night22d_20261022_005406/npz

## 相关

- [shape-language.md](shape-language.md) · [structure-principles.md](structure-principles.md)
- [roof-guidelines.md](roof-guidelines.md) · docs/look_harden.md
