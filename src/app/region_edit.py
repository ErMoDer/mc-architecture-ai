"""对话式局部修改：把一句中文指令作用在选中的盒选区域上。

只改选区内的方块，不动其他部分；所有操作返回新数组，方便撤销。

    python -m src.app.region_edit <sample.npz> "换成玻璃窗"

支持的动作（按关键词自动识别）：
    替换材质 / 填满 / 清空 / 开窗 / 铺地板 / 封顶 / 加高一层 / 放火把
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np

# 材质关键词 → palette 名称片段（越具体的写在前面）
_MAT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("white_concrete", ("白混凝土", "白色混凝土", "white concrete")),
    ("light_gray_concrete", ("浅灰混凝土", "浅灰色混凝土")),
    ("gray_concrete", ("灰混凝土", "灰色混凝土", "水泥")),
    ("black_concrete", ("黑混凝土", "黑色混凝土")),
    ("stone_bricks", ("石砖", "石砖墙", "stone brick")),
    ("stone", ("石头", "石料")),
    ("mossy_cobblestone", ("苔石", "苔藓圆石")),
    ("cobblestone", ("圆石", "鹅卵石", "cobble")),
    ("smooth_stone", ("平滑石", "smooth stone")),
    ("deepslate_tiles", ("深板岩瓦", "深板岩砖")),
    ("deepslate", ("深板岩", "深板岩块", "deepslate")),
    ("polished_deepslate", ("磨制深板岩",)),
    ("dark_oak_planks", ("深色橡木", "黑橡木", "dark oak")),
    ("dark_oak_log", ("深色橡木原木", "黑橡木原木")),
    ("spruce_planks", ("云杉木板", "云杉木", "云杉")),
    ("spruce_log", ("云杉原木",)),
    ("birch_planks", ("白桦木板", "白桦木", "白桦")),
    ("jungle_planks", ("丛林木板", "丛林木")),
    ("cherry_planks", ("樱花木板", "樱花木", "樱花")),
    ("acacia_planks", ("金合欢",)),
    ("oak_planks", ("橡木板", "橡木木", "oak plank")),
    ("oak_log", ("橡木原木",)),
    ("planks", ("木板", "木材")),
    ("log", ("原木",)),
    ("glass_pane", ("玻璃板", "窗格")),
    ("glass", ("玻璃", "窗户", "窗", "glass")),
    ("terracotta", ("陶瓦", "陶土", "terracotta")),
    ("white_terracotta", ("白陶瓦", "白色陶瓦")),
    ("bricks", ("红砖", "砖块", "砖墙")),
    ("sandstone", ("砂岩",)),
    ("quartz", ("石英",)),
    ("prismarine", ("海晶",)),
    ("nether_brick", ("下界砖",)),
    ("white_wool", ("白羊毛",)),
    ("wool", ("羊毛",)),
    ("brown_carpet", ("棕色地毯",)),
    ("green_carpet", ("绿色地毯",)),
    ("carpet", ("地毯",)),
    ("glowstone", ("萤石",)),
    ("sea_lantern", ("海晶灯",)),
    ("lantern", ("提灯", "灯笼")),
    ("torch", ("火把",)),
    ("leaves", ("树叶", "叶子")),
    ("water", ("水",)),
    ("lava", ("岩浆",)),
)

# 动作关键词（顺序即优先级：先判专门动作，最后才当替换材质）
_CLEAR_KW = ("清空", "挖空", "清除", "拆除", "删掉", "删除", "去掉", "移除", "打掉")
_WINDOW_KW = ("开窗", "窗户", "玻璃窗", "掏窗", "开个窗", "加窗")
_LIGHT_KW = ("火把", "照明", "点亮", "提灯", "灯笼", "灯光")
_FLOOR_KW = ("地板", "铺地", "地面", "地砖")
_CEIL_KW = ("天花板", "屋顶", "封顶", "顶盖")
_RAISE_KW = ("加高", "增高", "加一层", "再高一层", "拔高")
_FILL_KW = ("填满", "填充", "填实", "实心", "灌满")
_REPLACE_KW = ("换成", "改成", "替换", "改为", "变成", "换为")


def _find_key(text: str, kws: Iterable[str]) -> str | None:
    low = text.lower()
    for kw in kws:
        if kw.lower() in low:
            return kw
    return None


def resolve_material(text: str, palette: dict[int, str]) -> tuple[int | None, str | None]:
    """从指令里找材质，返回 (调色板 id, 材质名)。"""
    low = text.lower()
    for fragment, kws in _MAT_KEYWORDS:
        hit = None
        for kw in kws:
            if kw.lower() in low:
                hit = kw
                break
        if hit is None:
            continue
        # 先找同名片块（stone → minecraft:stone），找不到再退回包含匹配
        names = {bid: name.split(":", 1)[-1] for bid, name in palette.items() if bid > 0}
        for bid, short in names.items():
            if short == fragment:
                return int(bid), str(palette[bid])
        for bid, short in names.items():
            if fragment in short:
                return int(bid), str(palette[bid])
    return None, None


def parse_instruction(
    text: str, palette: dict[int, str], *, fallback_material: int | None = None
) -> dict[str, Any]:
    """把中文指令解析成动作字典；无法识别时抛 ValueError。

    fallback_material：指令没写材质时的兜底（一般是建筑的主材质）。
    """
    cmd = (text or "").strip()
    if not cmd:
        raise ValueError("指令为空")

    mat_id, mat_name = resolve_material(cmd, palette)

    def _fallback() -> tuple[int | None, str | None]:
        if fallback_material and fallback_material in palette:
            return int(fallback_material), str(palette[fallback_material])
        bid, name = resolve_material("石砖", palette)
        if bid is None:
            bid, name = resolve_material("石头", palette)
        return bid, name

    if _find_key(cmd, _CLEAR_KW):
        return {"action": "clear", "material_id": 0, "material": None, "note": "清空选区"}
    if _find_key(cmd, _RAISE_KW):
        if mat_id is None:
            mat_id, mat_name = _fallback()
        if mat_id is None:
            raise ValueError("调色板里没有可用材质，无法加高")
        return {"action": "raise", "material_id": mat_id, "material": mat_name,
                "note": f"加高一层（{mat_name}）"}
    if _find_key(cmd, _WINDOW_KW):
        use_glass = mat_id
        if use_glass is None:
            gid, gname = resolve_material("玻璃", palette)
            use_glass, mat_name = gid, gname
        return {"action": "window", "material_id": use_glass or 0, "material": mat_name,
                "note": "开窗"}
    if _find_key(cmd, _LIGHT_KW):
        lid, lname = resolve_material("火把", palette)
        if mat_id is not None and mat_id != lid:
            lid, lname = mat_id, mat_name  # 用户指定了别的灯具
        if lid is None:
            raise ValueError("调色板里没有火把/灯具，无法放置光源")
        return {"action": "light", "material_id": int(lid), "material": lname,
                "note": f"放光源（{lname}）"}
    if _find_key(cmd, _FLOOR_KW):
        if mat_id is None:
            raise ValueError("铺地板需要指定材质，例如「铺石砖地板」")
        return {"action": "floor", "material_id": mat_id, "material": mat_name,
                "note": f"铺地板（{mat_name}）"}
    if _find_key(cmd, _CEIL_KW):
        if mat_id is None:
            raise ValueError("封顶需要指定材质，例如「用云杉封顶」")
        return {"action": "ceiling", "material_id": mat_id, "material": mat_name,
                "note": f"封顶（{mat_name}）"}
    if _find_key(cmd, _FILL_KW) or (_find_key(cmd, _REPLACE_KW) and mat_id is not None):
        if mat_id is None:
            raise ValueError("没识别出材质，试试「填满石头」")
        fill = bool(_find_key(cmd, _FILL_KW))
        return {"action": "fill" if fill else "replace", "material_id": mat_id,
                "material": mat_name,
                "note": (f"填满（{mat_name}）" if fill else f"替换为（{mat_name}）")}

    # 只给了材质名（如「石砖」）
    if mat_id is not None:
        return {"action": "replace", "material_id": mat_id, "material": mat_name,
                "note": f"替换为（{mat_name}）"}

    raise ValueError(
        "没听懂这条指令。可用说法：换成石砖 / 填满石头 / 清空 / 开窗 / "
        "铺石砖地板 / 用云杉封顶 / 加高一层 / 放火把"
    )


def normalize_box(
    a: tuple[int, int, int], b: tuple[int, int, int]
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    lo = tuple(min(int(a[i]), int(b[i])) for i in range(3))
    hi = tuple(max(int(a[i]), int(b[i])) for i in range(3))
    return lo, hi


def apply_region_op(
    voxels: np.ndarray,
    palette: dict[int, str],
    box: tuple[tuple[int, int, int], tuple[int, int, int]],
    op: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    """在 box（两个对角，含端点）内执行 op，返回 (新体素, 统计)。"""
    arr = np.asarray(voxels).copy()
    (x0, y0, z0), (x1, y1, z1) = normalize_box(box[0], box[1])
    x0, x1 = max(0, x0), min(arr.shape[0] - 1, x1)
    y0, y1 = max(0, y0), min(arr.shape[1] - 1, y1)
    z0, z1 = max(0, z0), min(arr.shape[2] - 1, z1)
    if x0 > x1 or y0 > y1 or z0 > z1:
        raise ValueError("选区为空或越界")

    sub = arr[x0:x1 + 1, y0:y1 + 1, z0:z1 + 1]
    mat = int(op.get("material_id") or 0)
    action = op["action"]

    if action == "clear":
        sub[:] = 0

    elif action == "fill":
        sub[:] = mat

    elif action == "replace":
        sub[sub > 0] = mat

    elif action == "floor":
        sub[:, 0, :] = mat

    elif action == "ceiling":
        sub[:, -1, :] = mat

    elif action == "raise":
        # 把选区顶面之上的一层补出来（选区外的一层）
        y = y1 + 1
        if y < arr.shape[1]:
            arr[x0:x1 + 1, y, z0:z1 + 1] = mat

    elif action == "light":
        sub[:] = _place_lights(sub, mat)

    elif action == "window":
        sub[:] = _carve_window(sub, mat)

    else:  # pragma: no cover - parse_instruction 已限制取值
        raise ValueError(f"未知动作：{action}")

    changed = int((arr != np.asarray(voxels)).sum())
    info = {
        "action": action,
        "material": op.get("material"),
        "note": op.get("note"),
        "changed": changed,
        "box": (x0, y0, z0, x1, y1, z1),
    }
    return arr, info


def _carve_window(sub: np.ndarray, glass_id: int) -> np.ndarray:
    """在选区最薄的方向上凿一个居中窗口，可选填玻璃。"""
    dx, dy, dz = sub.shape
    out = sub.copy()
    thin = int(np.argmin((dx, dy, dz)))

    # 两个长轴，取 20%~80% 范围作为窗口大小
    def span(n: int) -> tuple[int, int]:
        if n <= 3:
            return 0, n - 1
        lo = max(1, int(round(n * 0.25)))
        hi = min(n - 2, int(round(n * 0.75)))
        return (lo, hi) if lo <= hi else (n // 2, n // 2)

    a_lo, a_hi = span(dx)
    b_lo, b_hi = span(dz)
    h_lo, h_hi = span(dy)
    holes = np.zeros(out.shape, dtype=bool)
    if thin == 1:  # 最薄是竖直方向 → 水平板，开中央天窗
        holes[a_lo:a_hi + 1, :, b_lo:b_hi + 1] = True
    elif thin == 0:  # 薄在 x → 窗口覆盖 y(高) 与 z
        holes[:, h_lo:h_hi + 1, b_lo:b_hi + 1] = True
    else:  # 薄在 z → 窗口覆盖 x 与 y(高)
        holes[:, h_lo:h_hi + 1, a_lo:a_hi + 1] = True

    out[holes & (out > 0)] = glass_id if glass_id > 0 else 0
    return out


def _place_lights(sub: np.ndarray, light_id: int) -> np.ndarray:
    """在选区内挑空气格放光源：只放悬空且在实体上方的格。"""
    out = sub.copy()
    solid = out > 0
    air = out == 0
    below_solid = np.zeros_like(solid)
    below_solid[:, :-1, :] = solid[:, 1:, :]
    cand = air & below_solid
    if not cand.any():
        return out
    idx = np.argwhere(cand)
    # 均匀挑，避免糊成一片
    step = max(1, len(idx) // 8)
    for p in idx[::step][:8]:
        out[tuple(p)] = light_id
    return out


def _load_npz(path: str) -> np.ndarray:
    with np.load(path) as z:
        for key in ("voxels", "arr_0", "data"):
            if key in z:
                return z[key].astype(np.int16)
    raise KeyError(f"{path} 里没有 voxels 数据")


def _main(argv: list[str] | None = None) -> int:  # pragma: no cover - 手动调试
    import sys
    from pathlib import Path

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print("用法: python -m src.app.region_edit <sample.npz> \"指令\"")
        return 2
    from src.app.sample_runner import project_root
    from src.utils import load_palette

    root = project_root()
    palette = load_palette(root / "data" / "palette.json")
    vox = _load_npz(args[0])
    op = parse_instruction(args[1], palette)
    nz = np.argwhere(vox > 0)
    lo = tuple(int(v) for v in nz.min(axis=0))
    hi = tuple(int(v) for v in nz.max(axis=0))
    out, info = apply_region_op(vox, palette, (lo, hi), op)
    print(f"{op['action']} {op['material']} changed={info['changed']}")
    print(f"non_air {int((vox > 0).sum())} → {int((out > 0).sum())}  ({Path(args[0]).name})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
