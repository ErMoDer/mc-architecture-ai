"""截图 + 文字要求 → DesignSpec → 条件生成。

推理优先级：
1. 若存在 OPENAI_API_KEY（环境变量或项目根 .env），调用视觉聊天模型输出 JSON。
2. 否则：文字关键词映射 + 截图颜色/亮度启发式（不假装做过视觉理解）。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.data.labels import KNOWN_STYLES, TERRAIN_NAMES, load_vocab
from src.app.sample_runner import generate_samples, load_label_vocab, project_root


@dataclass
class DesignSpec:
    style: str = "medieval"
    terrain: str = "flat"
    materials: list[str] = field(default_factory=list)
    size_hint: str | None = None
    prompt_summary: str = ""
    confidence: float = 0.4
    source: str = "heuristic"  # openai | heuristic
    notes: str = ""
    screenshot_path: str | None = None
    text_brief: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# 风格关键词（中英），按优先级匹配
_STYLE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("chinese", ["中式", "中国", "古风", "江南", "飞檐", "chinese", "oriental pavilion"]),
    ("japanese", ["日式", "和风", "神社", "鸟居", "japanese", "torii", "zen"]),
    ("desert", ["沙漠风", "绿洲风", "adobe", "沙漠建筑"]),
    ("western", ["西部", "牛仔", "saloon", "western", "cowboy"]),
    ("industrial", ["工业", "工厂", "机械", "industrial", "factory", "steampunk"]),
    ("scifi", ["科幻", "未来", "太空", "scifi", "sci-fi", "futuristic", "cyber"]),
    ("european", ["欧式", "巴洛克", "哥特", "城堡风", "european", "gothic", "baroque", "victorian"]),
    ("rustic", ["乡村", "田园", "木屋风", "rustic", "cottage", "farmhouse"]),
    ("modern", ["现代", "当代", "极简", "混凝土", "modern", "contemporary", "minimal"]),
    ("fantasy", ["奇幻", "魔法", "精灵", "龙", "fantasy", "magic", "elven", "wizard"]),
    ("medieval", ["中世纪", "城堡", "要塞", "石墙", "medieval", "castle", "fortress", "keep"]),
]

_TERRAIN_KEYWORDS: list[tuple[str, list[str]]] = [
    ("nether", ["下界", "地狱", "nether", "hell"]),
    ("snow", ["雪山", "雪地", "冰原", "霜", "雪景", "snow", "ice", "frost", "寒带", "冬天", "雪"]),
    ("desert", ["沙漠", "沙丘", "绿洲", "desert", "dune", "oasis", "沙地"]),
    ("water", ["海边", "码头", "港口", "水上", "湖边", "桥", "灯塔", "water", "harbor", "dock", "pier", "海岸", "河边"]),
    ("mountain", ["悬崖", "峭壁", "山地", "mountain", "cliff", "slope", "山顶", "洞穴", "山"]),
    ("nature", ["自然", "森林", "树林", "花园", "nature", "forest", "garden", "丛林"]),
    ("flat", ["平地", "平原", "村庄", "flat", "plains", "village"]),
]


def _load_dotenv(path: Path) -> None:
    """轻量加载 .env（不覆盖已有环境变量）。不打印任何值。"""
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def api_key_available() -> bool:
    root = project_root()
    _load_dotenv(root / ".env")
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    return bool(key)


def _clamp_style(name: str, styles: list[str]) -> str:
    key = (name or "").strip().lower()
    if key in styles:
        return key
    if "medieval" in styles:
        return "medieval"
    return styles[0] if styles else "medieval"


def _clamp_terrain(name: str, terrains: list[str]) -> str:
    key = (name or "").strip().lower()
    if key in terrains:
        return key
    if "flat" in terrains:
        return "flat"
    return terrains[0] if terrains else "flat"


def _match_keyword_list(text: str, rules: list[tuple[str, list[str]]]) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    blob = text
    blob_l = text.lower()
    for label, kws in rules:
        for kw in kws:
            if kw.lower() in blob_l or kw in blob:
                return label, kw
    return None, None


def _heuristic_from_text(text: str) -> tuple[str | None, str | None, list[str], str | None, list[str]]:
    style, style_kw = _match_keyword_list(text, _STYLE_KEYWORDS)
    terrain, terr_kw = _match_keyword_list(text, _TERRAIN_KEYWORDS)
    materials: list[str] = []
    mat_map = [
        ("oak", ["橡木", "oak"]),
        ("spruce", ["云杉", "spruce"]),
        ("dark_oak", ["深色橡木", "黑橡木", "dark oak"]),
        ("stone", ["石头", "石砖", "stone", "cobble"]),
        ("brick", ["砖", "brick"]),
        ("glass", ["玻璃", "glass"]),
        ("quartz", ["石英", "quartz"]),
        ("deepslate", ["深板岩", "deepslate"]),
        ("sandstone", ["砂岩", "sandstone"]),
        ("prismarine", ["海晶", "prismarine"]),
        ("nether_brick", ["下界砖", "nether brick"]),
        ("white_concrete", ["白色混凝土", "白混凝土", "white concrete"]),
        ("concrete", ["混凝土", "concrete"]),
        ("terracotta", ["陶瓦", "terracotta"]),
        ("cherry", ["樱花", "cherry"]),
    ]
    low = text.lower()
    for mat, kws in mat_map:
        for kw in kws:
            if kw.lower() in low or kw in text:
                materials.append(mat)
                break
    size_hint = None
    for hint, kws in (
        ("small", ["小", "小屋", "tiny", "small"]),
        ("large", ["大", "巨型", "large", "huge", "grand", "塔楼", "高塔", "塔", "tower", "高楼", "宫殿", "大殿"]),
        ("medium", ["中等", "medium"]),
    ):
        for kw in kws:
            if kw.lower() in low or kw in text:
                size_hint = hint
                break
        if size_hint:
            break
    reasons = []
    if style_kw:
        reasons.append(f"style←「{style_kw}」")
    if terr_kw:
        reasons.append(f"terrain←「{terr_kw}」")
    return style, terrain, materials, size_hint, reasons


def _heuristic_from_image(image_path: Path) -> tuple[str | None, str | None, list[str], float]:
    """简单色调启发式。返回 (style_hint, terrain_hint, reasons, confidence_boost)。"""
    try:
        from PIL import Image
    except ImportError:
        return None, None, ["无 Pillow，跳过截图色调分析"], 0.0

    try:
        im = Image.open(image_path).convert("RGB")
    except OSError as exc:
        return None, None, [f"截图无法打开：{exc}"], 0.0

    # 缩略采样
    im = im.resize((64, 64))
    pixels = list(im.getdata())
    n = max(len(pixels), 1)
    r_avg = sum(p[0] for p in pixels) / n
    g_avg = sum(p[1] for p in pixels) / n
    b_avg = sum(p[2] for p in pixels) / n
    brightness = (r_avg + g_avg + b_avg) / 3.0

    # 粗略分类比例
    snowish = sum(1 for r, g, b in pixels if r > 180 and g > 180 and b > 180) / n
    sandy = sum(1 for r, g, b in pixels if r > 150 and g > 110 and b < 110 and r >= g) / n
    watery = sum(1 for r, g, b in pixels if b > r + 20 and b > g + 10 and b > 80) / n
    leafy = sum(1 for r, g, b in pixels if g > r + 15 and g > b + 15 and g > 70) / n
    nethery = sum(1 for r, g, b in pixels if r > 100 and g < 60 and b < 60 and r > g + 40) / n
    dark = sum(1 for r, g, b in pixels if (r + g + b) / 3 < 50) / n

    terrain = None
    style = None
    reasons: list[str] = []
    conf = 0.15

    if nethery > 0.12:
        terrain = "nether"
        reasons.append(f"截图偏暗红(nether≈{nethery:.0%})")
        conf = 0.35
    elif snowish > 0.28 and brightness > 160:
        terrain = "snow"
        reasons.append(f"截图偏白亮(snow≈{snowish:.0%})")
        conf = 0.35
    elif sandy > 0.22:
        terrain = "desert"
        reasons.append(f"截图偏沙黄(desert≈{sandy:.0%})")
        conf = 0.35
    elif watery > 0.18:
        terrain = "water"
        reasons.append(f"截图偏蓝(water≈{watery:.0%})")
        conf = 0.3
    elif leafy > 0.2:
        terrain = "nature"
        reasons.append(f"截图偏绿(nature≈{leafy:.0%})")
        conf = 0.3
    elif dark > 0.35:
        reasons.append(f"截图偏暗(dark≈{dark:.0%})，地形仍默认 flat")
        conf = 0.2
    else:
        reasons.append(
            f"截图色调中性(R{r_avg:.0f}G{g_avg:.0f}B{b_avg:.0f})，色调未强推地形"
        )

    return style, terrain, reasons, conf


def _openai_infer(image_path: Path | None, text: str, styles: list[str], terrains: list[str]) -> DesignSpec | None:
    _load_dotenv(project_root() / ".env")
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    base = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = (os.environ.get("OPENAI_VISION_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()

    schema_hint = {
        "style": f"one of {styles}",
        "terrain": f"one of {terrains}",
        "materials": ["oak", "stone", "..."],
        "size_hint": "small|medium|large|null",
        "prompt_summary": "one short Chinese sentence",
        "confidence": 0.0,
        "notes": "brief reason",
    }
    user_text = (
        "你是 Minecraft 建筑设计师助手。根据玩家截图（若有）和文字要求，"
        "推断条件生成所需的 style 与 terrain。只输出 JSON，不要 markdown。\n"
        f"允许 style：{styles}\n允许 terrain：{terrains}\n"
        f"JSON 字段示例：{json.dumps(schema_hint, ensure_ascii=False)}\n"
        f"玩家文字要求：{text or '（无）'}"
    )

    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    if image_path is not None and image_path.is_file():
        import base64

        suffix = image_path.suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
        b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
        )

    body = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Return only valid JSON matching the requested fields."},
            {"role": "user", "content": content},
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return DesignSpec(
            style=_clamp_style("medieval", styles),
            terrain=_clamp_terrain("flat", terrains),
            prompt_summary=(text or "")[:120],
            confidence=0.0,
            source="openai",
            notes=f"API 调用失败，请改用启发式或手改下拉：{exc}",
            screenshot_path=str(image_path) if image_path else None,
            text_brief=text or "",
        )

    try:
        raw = payload["choices"][0]["message"]["content"]
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        return DesignSpec(
            style=_clamp_style("medieval", styles),
            terrain=_clamp_terrain("flat", terrains),
            prompt_summary=(text or "")[:120],
            confidence=0.0,
            source="openai",
            notes=f"API 返回无法解析：{exc}",
            screenshot_path=str(image_path) if image_path else None,
            text_brief=text or "",
        )

    style = _clamp_style(str(data.get("style") or "medieval"), styles)
    terrain = _clamp_terrain(str(data.get("terrain") or "flat"), terrains)
    materials = data.get("materials") or []
    if not isinstance(materials, list):
        materials = []
    materials = [str(m) for m in materials][:12]
    size_hint = data.get("size_hint")
    if size_hint is not None:
        size_hint = str(size_hint)
    conf = data.get("confidence")
    try:
        conf_f = float(conf) if conf is not None else 0.7
    except (TypeError, ValueError):
        conf_f = 0.7
    conf_f = max(0.0, min(1.0, conf_f))
    summary = str(data.get("prompt_summary") or text or "")[:200]
    notes = str(data.get("notes") or "OpenAI 视觉推断")
    return DesignSpec(
        style=style,
        terrain=terrain,
        materials=materials,
        size_hint=size_hint,
        prompt_summary=summary,
        confidence=conf_f,
        source="openai",
        notes=notes,
        screenshot_path=str(image_path) if image_path else None,
        text_brief=text or "",
    )


def infer_design_spec(
    *,
    text_brief: str = "",
    image_path: str | Path | None = None,
    vocab_path: str | Path | None = None,
    prefer_api: bool = True,
) -> DesignSpec:
    """从截图路径 + 文字推断 DesignSpec。始终可手改 style/terrain。"""
    root = project_root()
    vocab = load_label_vocab(vocab_path)
    styles = list(vocab.get("styles") or KNOWN_STYLES)
    terrains = list(vocab.get("terrains") or TERRAIN_NAMES)

    img: Path | None = None
    if image_path:
        p = Path(image_path)
        if not p.is_absolute():
            p = root / p
        if p.is_file():
            img = p

    text = (text_brief or "").strip()

    if prefer_api and api_key_available():
        spec = _openai_infer(img, text, styles, terrains)
        if spec is not None and spec.confidence > 0:
            return spec
        # API 失败对象也直接返回（notes 已说明），但若 confidence==0 且 notes 含失败，继续启发式合并
        if spec is not None and "失败" not in (spec.notes or "") and "无法解析" not in (spec.notes or ""):
            return spec

    t_style, t_terrain, materials, size_hint, text_reasons = _heuristic_from_text(text)
    i_style, i_terrain, img_reasons, img_conf = (None, None, [], 0.0)
    if img is not None:
        i_style, i_terrain, img_reasons, img_conf = _heuristic_from_image(img)
    elif image_path:
        img_reasons = ["未提供有效截图文件，仅用文字"]

    # 文字优先于色调
    style = _clamp_style(t_style or i_style or "medieval", styles)
    terrain = _clamp_terrain(t_terrain or i_terrain or "flat", terrains)

    conf = 0.25
    if t_style:
        conf += 0.25
    if t_terrain:
        conf += 0.2
    conf += img_conf * 0.5
    if not text and img is None:
        conf = 0.15
    conf = max(0.1, min(0.85, conf))

    reasons = text_reasons + img_reasons
    if not t_style and not t_terrain:
        reasons.append("文字未命中明确风格/地形关键词，可用下拉手改")
    if not api_key_available():
        reasons.append("未检测到 OPENAI_API_KEY，使用启发式（非视觉大模型）")
    else:
        reasons.append("API 不可用或失败，已回退启发式")

    summary = text[:160] if text else (f"截图 {img.name}" if img else "（无输入）")
    return DesignSpec(
        style=style,
        terrain=terrain,
        materials=materials,
        size_hint=size_hint,
        prompt_summary=summary,
        confidence=round(conf, 2),
        source="heuristic",
        notes="；".join(reasons) if reasons else "启发式默认",
        screenshot_path=str(img) if img else (str(image_path) if image_path else None),
        text_brief=text,
    )


def generate_from_design(
    spec: DesignSpec,
    *,
    num: int = 1,
    temperature: float = 1.0,
    checkpoint: str | Path | None = None,
    out_dir: str | Path | None = None,
    seed: int | None = None,
    strategy: str = "similar_scaffold",
    vae_fill: bool = False,
) -> list[dict[str, Any]]:
    """Generate from DesignSpec. Default strategy=similar_scaffold (scaffold-first)."""
    from src.app.gen_strategy import generate_with_strategy

    root = project_root()
    ckpt = checkpoint
    if ckpt is None:
        preferred = root / "checkpoints" / "cond_last.pt"
        ckpt = preferred if preferred.exists() else root / "checkpoints" / "last.pt"
    results = generate_with_strategy(
        strategy or "similar_scaffold",
        style=spec.style,
        terrain=spec.terrain,
        num=num,
        temperature=temperature,
        checkpoint=ckpt,
        out_dir=out_dir,
        seed=seed,
        vae_fill=bool(vae_fill),
        look_harden_enable=True,
        structure_constrain=True,
        structure_mode="repair",
    )
    for r in results:
        r["design"] = spec.to_dict()
    return results

def format_spec_for_ui(spec: DesignSpec) -> str:
    mats = ", ".join(spec.materials) if spec.materials else "—"
    shot = Path(spec.screenshot_path).name if spec.screenshot_path else "—"
    return (
        f"来源：{spec.source}  置信度：{spec.confidence:.0%}\n"
        f"风格：{spec.style}    地形：{spec.terrain}\n"
        f"材料关键词：{mats}\n"
        f"体量：{spec.size_hint or '—'}\n"
        f"摘要：{spec.prompt_summary or '—'}\n"
        f"截图：{shot}\n"
        f"说明：{spec.notes}"
    )
