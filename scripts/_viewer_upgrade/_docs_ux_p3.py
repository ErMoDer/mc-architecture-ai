# -*- coding: utf-8 -*-
"""Append P3 notes to plan / viewer.md / LAUNCH.md"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime

ROOT = Path(r"E:\ai agent\mc-architecture-ai")
now = datetime.now().strftime("%Y-%m-%d %H:%M") + " Asia/Shanghai"

plan = ROOT / "outputs/plans/plan_ux_functional_20261023.md"
pt2 = plan.read_text(encoding="utf-8")
for old, new in [
    ("**P0✓ P1✓ P2✓**", "**P0✓ P1✓ P2✓ P3✓**"),
    ("下一片 P3（接 MC 界面）", "P0–P3 已收口（P3=轻量桥接，非游戏内 HUD）"),
]:
    if old in pt2:
        pt2 = pt2.replace(old, new)

p3_block = f"""

## P3 完成（{now}）

轻量「游戏桥接」面板（**非** Fabric / 非游戏内 HUD）：

- 浏览侧 **游戏桥接（投影目录）**：列出 PCL schematics 下 .litematic（手动刷新 + 可选自动刷新 ~4s）
- 高亮本应用导出前缀（夜齐_/夜坡_/夜改/知*/ai_/…）；打开目录 / 定位文件 / 复制文件名 / 建造步骤卡
- 「进游戏」导出后：写 LAST_EXPORT.txt + LAST_EXPORT.json（schematics 与 materials/），剪贴板复制文件名，弹建造步骤卡（切 26.3-Fabric → Andy 列出投影 → 选文件 → 建造）
- 进程启发式：显示「游戏似乎在运行 / 未检测到」（tasklist，不注入）
- 模块：src/app/game_bridge.py；备份 *.bak_ux_p3_*；冒烟 scripts/_viewer_upgrade/_smoke_ux_p3.py → UX_P3_SMOKE_OK
- **残留**：仍无真正游戏内 HUD / Fabric 模组；需 Andy/Litematica 手工建造

| {now} | 用户「继续」；落地 P3 轻量桥接 |
| {now} | P3 收口 |

"""
if "## P3 完成" not in pt2:
    pt2 = pt2.rstrip() + p3_block
plan.write_text(pt2, encoding="utf-8")
print("plan updated")

viewer = ROOT / "docs/viewer.md"
vt = viewer.read_text(encoding="utf-8")
vblock = f"""

## 功能化 P3 — 游戏桥接（{now.split()[0]}）

浏览模式底部 **游戏桥接（投影目录）**：

1. 实时列出 companion / PCL schematics 内 .litematic（刷新 / 自动刷新）
2. 星标高亮本应用导出（夜齐_/夜坡_/ai_…）；打开目录、定位文件、复制文件名
3. 「进游戏」后弹出 **建造步骤卡**，并写 LAST_EXPORT.txt / LAST_EXPORT.json（materials/ 有镜像）
4. 状态行启发式显示 Minecraft/PCL 是否在跑（不注入、不改模组）

计划：outputs/plans/plan_ux_functional_20261023.md；冒烟：scripts/_viewer_upgrade/_smoke_ux_p3.py

**诚实残留**：仍不是游戏内 HUD；建造仍靠 Andy / Litematica。

"""
if "功能化 P3" not in vt:
    viewer.write_text(vt.rstrip() + vblock, encoding="utf-8")
    print("viewer.md updated")
else:
    print("viewer.md already has P3")

launch = ROOT / "LAUNCH.md"
lt = launch.read_text(encoding="utf-8")
lblock = f"""

## 功能化 P3（{now.split()[0]}）

轻量游戏桥接（投影列表 + 建造步骤卡 + LAST_EXPORT）。未训 VAE，未做 Fabric HUD。

- 计划：outputs/plans/plan_ux_functional_20261023.md（P0–P3 收口）
- 预览：
  ./.venv/Scripts/python.exe scripts/viewer_app.py --samples outputs/design/night22e_full_20261022_071643/npz
- 试法：浏览 → 底部「游戏桥接」看 PCL 投影列表 → 「进游戏」→ 看步骤卡 / 复制文件名 → 游戏内 Andy「列出投影 → 建造」

"""
if "功能化 P3" not in lt:
    launch.write_text(lt.rstrip() + lblock, encoding="utf-8")
    print("LAUNCH.md updated")
else:
    print("LAUNCH already has P3")
