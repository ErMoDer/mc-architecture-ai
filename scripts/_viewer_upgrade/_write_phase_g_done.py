# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
G = "kb_massing_G_20261021_005529"
done = ROOT / "outputs" / "plans" / "plan_8h_20261021_DONE.md"

body = f"""# 8h 计划完成摘要 · 2026-10-21

时段约 00:30 起（Asia/Shanghai）。LOCAL_ONLY；无 VAE / 无大规模爬取。

---

## 怎么打开最新结果

1. 双击 `建筑预览.bat` / `start_viewer.bat`
2. **浏览**默认会选最新 `outputs/design/*/npz` → 当前为 **`outputs/design/{G}/npz`**
3. 或手动：浏览 → 选目录 → 上述路径
4. 游戏内 Litematica / Andy：加载 PCL schematics 里的 `知齐_*`（推荐最新全集）

---

## Viewer 新工具（Phase A）

| 能力 | 用法 |
|------|------|
| 撤销/重做 | 栈深 32；按钮或 Ctrl+Z / Ctrl+Y |
| 笔刷 | 小/中/大；破坏·放置·涂改 |
| 盒填 | 勾选后点两角 |
| 复制/剪切/粘贴 | 选择两角；Ctrl+C/X/V |
| 方案 + companion | 右侧另存/导出 .litematic |

---

## 投影文件前缀（PCL schematics）

| 前缀 | 含义 |
|------|------|
| `知增_` | Phase B 三风试跑（欧/工/田） |
| `知全_` | Phase C 全 8 风（隔墙偏猛，中式等 room_air 回退） |
| `知收_` | Phase D 收紧隔墙后的 5 风 |
| `知新_` | Phase E 全 8 + fantasy 玻璃旋钮 |
| `知洞_` | Phase F 开孔指标修复后的欧/西/幻 |
| **`知齐_`** | **Phase G 推荐全集（D 隔墙 + F 开孔检测）** |

早期科技投影（超级熔炉等）未改动。

---

## Phase 一览

- **A** 编辑器：撤销栈、笔刷、盒填、剪贴板
- **B** 隔墙 T/cross + 坡屋顶楼梯皮
- **C** 全 8 风；发现 cross 伤中式/中世纪/幻想 room_air
- **D** 风格化隔墙（上述三风 mid/短 L）；room_air 回收
- **E** 全 8 + fantasy dens；澄清 glass vs window_cells
- **F** 弱柱开孔不再算窗；fantasy window_cells 775→30
- **G** 规范包 `{G}` + `知齐_*`

---

## Phase G 指标（8/8 ok）

| style | part | solids | room_air | window_cells | glass_cells | roof_mode |
|-------|------|--------|----------|--------------|-------------|-----------|
| industrial | mid_x | 3407 | 19048 | 90 | 76 | flat_eave |
| european | cross | 4055 | 10949 | 262 | 113 | skin_gable |
| rustic | cross | 3485 | 15992 | 171 | 87 | skin_gable |
| chinese | L | 8333 | 20789 | 362 | 325 | skin_gable |
| modern | mid_z | 6340 | 19865 | 529 | 224 | flat_eave |
| western | cross | 4445 | 14624 | 335 | 298 | skin_gable |
| medieval | L | 6248 | 4530 | 60 | 53 | skin_gable |
| fantasy | L | 10880 | 8462 | 30 | 25 | skin_gable |

导出：`知齐_工业/欧式/田园/中式/现代/西部/中世纪/幻想住宅_v26.3.litematic`

---

## 残余限制

- 点选依赖外壳面投影；非 MagicaVoxel 雕刻
- modern `window_cells` 仍偏高（开敞立面）；可后续单独 dens
- `window_cells` ≠ 玻璃板：看 `glass_cells` 更准
- 未做全风格 GUI 手测编辑；`_smoke_phase_a.py` API 冒烟通过

**核心交付完成。建议游戏内优先加载 `知齐_*`。**
"""
done.write_text(body, encoding="utf-8")
print("wrote", done)

plan = ROOT / "outputs" / "plans" / "plan_8h_20261021.md"
pt = plan.read_text(encoding="utf-8")
sec = f"""
## Phase G — 规范全集 · **DONE**

- Batch: `outputs/design/{G}/` · structure_ok **8/8**
- 导出: `知齐_*住宅_v26.3.litematic`（推荐使用）
- Viewer 默认最新 design/*/npz 即本批；用户摘要见 `plan_8h_20261021_DONE.md`
- `_smoke_phase_a.py` SMOKE_OK
"""
if G not in pt:
    plan.write_text(pt.rstrip() + "\n" + sec + "\n", encoding="utf-8")
    print("plan appended")
else:
    print("plan already has G")
