# -*- coding: utf-8 -*-
"""Lightweight zh-CN display names for architecture BOM (not Mojang assets).

Heuristics + curated overrides. Unknown ids fall back to short English id.
Do not copy Litematica-Nova code; names are approximate for builder UX.
"""
from __future__ import annotations

_PREFIX: dict[str, str] = {
    "oak": "橡木",
    "spruce": "云杉木",
    "birch": "白桦木",
    "jungle": "丛林",
    "acacia": "金合欢",
    "dark_oak": "深色橡木",
    "mangrove": "红树",
    "cherry": "樱花",
    "bamboo": "竹",
    "crimson": "绯红",
    "warped": "诡异",
    "pale_oak": "苍白橡木",
    "poplar": "白杨",
    "white": "白色",
    "orange": "橙色",
    "magenta": "品红色",
    "light_blue": "淡蓝色",
    "yellow": "黄色",
    "lime": "黄绿色",
    "pink": "粉红色",
    "gray": "灰色",
    "light_gray": "淡灰色",
    "cyan": "青色",
    "purple": "紫色",
    "blue": "蓝色",
    "brown": "棕色",
    "green": "绿色",
    "red": "红色",
    "black": "黑色",
}

_SUFFIX: dict[str, str] = {
    "planks": "木板",
    "log": "原木",
    "wood": "木头",
    "stem": "菌柄",
    "hyphae": "菌核",
    "stairs": "楼梯",
    "slab": "台阶",
    "fence": "栅栏",
    "fence_gate": "栅栏门",
    "door": "门",
    "trapdoor": "活板门",
    "button": "按钮",
    "pressure_plate": "压力板",
    "sign": "告示牌",
    "hanging_sign": "悬挂式告示牌",
    "wall_sign": "墙上的告示牌",
    "leaves": "树叶",
    "sapling": "树苗",
    "wall": "墙",
    "pane": "板",
    "carpet": "地毯",
    "wool": "羊毛",
    "concrete": "混凝土",
    "concrete_powder": "混凝土粉末",
    "terracotta": "陶瓦",
    "glazed_terracotta": "带釉陶瓦",
    "stained_glass": "染色玻璃",
    "stained_glass_pane": "染色玻璃板",
    "bed": "床",
    "candle": "蜡烛",
    "banner": "旗帜",
    "shulker_box": "潜影盒",
}

_EXACT: dict[str, str] = {
    "air": "空气",
    "stone": "石头",
    "cobblestone": "圆石",
    "mossy_cobblestone": "苔石",
    "stone_bricks": "石砖",
    "mossy_stone_bricks": "苔石砖",
    "cracked_stone_bricks": "裂纹石砖",
    "chiseled_stone_bricks": "錾制石砖",
    "smooth_stone": "平滑石头",
    "granite": "花岗岩",
    "polished_granite": "磨制花岗岩",
    "diorite": "闪长岩",
    "polished_diorite": "磨制闪长岩",
    "andesite": "安山岩",
    "polished_andesite": "磨制安山岩",
    "deepslate": "深板岩",
    "cobbled_deepslate": "深板岩圆石",
    "polished_deepslate": "磨制深板岩",
    "deepslate_bricks": "深板岩砖",
    "deepslate_tiles": "深板岩瓦",
    "tuff": "凝灰岩",
    "bricks": "砖块",
    "mud_bricks": "泥砖",
    "packed_mud": "泥坯",
    "dirt": "泥土",
    "grass_block": "草方块",
    "dirt_path": "土径",
    "coarse_dirt": "粗泥",
    "podzol": "灰化土",
    "mycelium": "菌丝",
    "sand": "沙子",
    "red_sand": "红沙",
    "gravel": "沙砾",
    "sandstone": "砂岩",
    "cut_sandstone": "切制砂岩",
    "chiseled_sandstone": "錾制砂岩",
    "smooth_sandstone": "平滑砂岩",
    "red_sandstone": "红砂岩",
    "smooth_red_sandstone": "平滑红砂岩",
    "glass": "玻璃",
    "glass_pane": "玻璃板",
    "iron_bars": "铁栏杆",
    "iron_door": "铁门",
    "iron_trapdoor": "铁活板门",
    "ladder": "梯子",
    "torch": "火把",
    "wall_torch": "墙上的火把",
    "lantern": "灯笼",
    "soul_lantern": "灵魂灯笼",
    "glowstone": "荧石",
    "sea_lantern": "海晶灯",
    "shroomlight": "菌光体",
    "bookshelf": "书架",
    "chiseled_bookshelf": "雕纹书架",
    "crafting_table": "工作台",
    "furnace": "熔炉",
    "blast_furnace": "高炉",
    "smoker": "烟熏炉",
    "chest": "箱子",
    "trapped_chest": "陷阱箱",
    "barrel": "木桶",
    "hopper": "漏斗",
    "dropper": "投掷器",
    "dispenser": "发射器",
    "observer": "侦测器",
    "piston": "活塞",
    "sticky_piston": "粘性活塞",
    "redstone_wire": "红石线",
    "redstone_block": "红石块",
    "redstone_torch": "红石火把",
    "redstone_lamp": "红石灯",
    "lever": "拉杆",
    "stone_button": "石头按钮",
    "oak_button": "橡木按钮",
    "note_block": "音符盒",
    "jukebox": "唱片机",
    "enchanting_table": "附魔台",
    "anvil": "铁砧",
    "hay_block": "干草块",
    "netherrack": "下界岩",
    "nether_bricks": "下界砖块",
    "red_nether_bricks": "红色下界砖块",
    "basalt": "玄武岩",
    "smooth_basalt": "平滑玄武岩",
    "polished_basalt": "磨制玄武岩",
    "blackstone": "黑石",
    "polished_blackstone": "磨制黑石",
    "polished_blackstone_bricks": "磨制黑石砖",
    "obsidian": "黑曜石",
    "crying_obsidian": "哭泣的黑曜石",
    "amethyst_block": "紫水晶块",
    "quartz_block": "石英块",
    "smooth_quartz": "平滑石英",
    "chiseled_quartz_block": "錾制石英块",
    "quartz_pillar": "石英柱",
    "quartz_bricks": "石英砖",
    "prismarine": "海晶石",
    "prismarine_bricks": "海晶石砖",
    "dark_prismarine": "暗海晶石",
    "purpur_block": "紫珀块",
    "purpur_pillar": "紫珀柱",
    "end_stone": "末地石",
    "end_stone_bricks": "末地石砖",
    "terracotta": "陶瓦",
    "clay": "黏土块",
    "ice": "冰",
    "packed_ice": "浮冰",
    "blue_ice": "蓝冰",
    "snow_block": "雪块",
    "calcite": "方解石",
    "dripstone_block": "滴水石块",
    "moss_block": "苔藓块",
    "moss_carpet": "苔藓地毯",
    "scaffolding": "脚手架",
    "chain": "锁链",
    "lightning_rod": "避雷针",
    "copper_block": "铜块",
    "cut_copper": "切制铜块",
    "tuff_bricks": "凝灰岩砖",
    "resin_block": "树脂块",
    "resin_bricks": "树脂砖",
    "short_grass": "矮草",
    "campfire": "营火",
    "soul_campfire": "灵魂营火",
    "water": "水",
    "lava": "熔岩",
}


def short_name(full: str) -> str:
    if ":" in full:
        return full.split(":", 1)[1]
    return full


def zh_name(full_or_short: str) -> str:
    """Return a Chinese display name; fall back to short id."""
    raw = full_or_short.strip()
    name = short_name(raw).lower()
    if not name:
        return "未知"
    if name in _EXACT:
        return _EXACT[name]

    stripped = False
    if name.startswith("stripped_"):
        stripped = True
        name = name[len("stripped_") :]

    prefix_zh = ""
    rest = name
    for pref in sorted(_PREFIX.keys(), key=len, reverse=True):
        if name == pref:
            return ("去皮" if stripped else "") + _PREFIX[pref]
        if name.startswith(pref + "_"):
            prefix_zh = _PREFIX[pref]
            rest = name[len(pref) + 1 :]
            break

    if rest in _SUFFIX:
        return ("去皮" if stripped else "") + prefix_zh + _SUFFIX[rest]

    for suf, suf_zh in sorted(_SUFFIX.items(), key=lambda x: -len(x[0])):
        if name == suf:
            return suf_zh
        if name.endswith("_" + suf):
            base = name[: -(len(suf) + 1)]
            base_zh = _EXACT.get(base, "")
            if not base_zh:
                for pref in sorted(_PREFIX.keys(), key=len, reverse=True):
                    if base == pref or base.startswith(pref + "_") or base.startswith(pref):
                        base_zh = _PREFIX[pref]
                        break
            if not base_zh:
                base_zh = prefix_zh or base.replace("_", "")
            return ("去皮" if stripped else "") + base_zh + suf_zh

    if prefix_zh:
        return ("去皮" if stripped else "") + prefix_zh + rest.replace("_", "")

    if ":" in raw:
        ns, short = raw.split(":", 1)
        if ns != "minecraft":
            return f"{short}（{ns}）"
    return short_name(raw)