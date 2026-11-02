# -*- coding: utf-8 -*-
"""Light in-game bridge helpers (UX P3) — no Fabric mod / no injection."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Prefixes we treat as "exported by this app" (highlight in list).
APP_OWNED_PREFIXES: tuple[str, ...] = (
    "夜齐_",
    "夜坡_",
    "夜改",
    "知齐_",
    "知抛_",
    "知全_",
    "知构_",
    "新池_",
    "ai_",
    "UXsmoke",
    "UX冒烟",
    "scheme_",
)

# Windows process-name heuristics (display only; never inject).
MC_PROCESS_HINTS: tuple[str, ...] = (
    "javaw",
    "java",
    "minecraft",
    "minecraftlauncher",
    "pcl",
    "plain craft launcher",
    "hmcl",
)


def materials_dir_for(schematics_dir: Path) -> Path:
    """materials/ under schematics (PCL layout used by this project)."""
    return Path(schematics_dir).resolve() / "materials"


def is_app_owned_name(name: str) -> bool:
    stem = Path(name).stem
    low = stem.lower()
    for p in APP_OWNED_PREFIXES:
        if stem.startswith(p) or low.startswith(p.lower()):
            return True
    # schemes slug often appears as-is before version tag
    if "_v" in stem and any(stem.startswith(x.rstrip("_")) for x in ("ai",)):
        return True
    return False


def list_schematics(schematics_dir: Path | None) -> list[dict[str, Any]]:
    """Return sorted .litematic entries; empty list if path missing."""
    if schematics_dir is None:
        return []
    d = Path(schematics_dir)
    if not d.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    try:
        files = list(d.glob("*.litematic"))
    except OSError:
        return []
    for p in files:
        try:
            st = p.stat()
            mtime = st.st_mtime
            size = st.st_size
        except OSError:
            mtime = 0.0
            size = 0
        rows.append(
            {
                "name": p.name,
                "stem": p.stem,
                "path": str(p.resolve()),
                "mtime": mtime,
                "size": size,
                "app_owned": is_app_owned_name(p.name),
            }
        )
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return rows


def write_last_export_sidecar(
    schematics_dir: Path,
    *,
    litematic_path: Path,
    slug: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Write LAST_EXPORT.txt + LAST_EXPORT.json into schematics (and mirror under materials/)."""
    schematics_dir = Path(schematics_dir)
    schematics_dir.mkdir(parents=True, exist_ok=True)
    lit = Path(litematic_path)
    now = datetime.now().astimezone()
    payload: dict[str, Any] = {
        "name": lit.name,
        "stem": lit.stem,
        "path": str(lit.resolve()) if lit.exists() else str(lit),
        "slug": slug,
        "exported_at": now.isoformat(timespec="seconds"),
        "exported_at_zone": str(now.tzinfo),
        "hint_zh": "游戏内 Andy：列出投影 → 建造 " + lit.stem,
    }
    if extra:
        # Drop non-JSON-serializable values (e.g. Path inside BOM dicts)
        safe = {}
        for k, v in extra.items():
            try:
                json.dumps(v, ensure_ascii=False)
                safe[k] = v
            except TypeError:
                safe[k] = str(v)
        payload.update(safe)

    txt_lines = [
        lit.name,
        lit.stem,
        payload["path"],
        payload["exported_at"],
        payload["hint_zh"],
        "",
    ]
    out: dict[str, str] = {}
    txt_path = schematics_dir / "LAST_EXPORT.txt"
    json_path = schematics_dir / "LAST_EXPORT.json"
    txt_path.write_text("\n".join(txt_lines), encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    out["txt"] = str(txt_path)
    out["json"] = str(json_path)

    mat = schematics_dir / "materials"
    try:
        mat.mkdir(parents=True, exist_ok=True)
        m_txt = mat / "LAST_EXPORT.txt"
        m_json = mat / "LAST_EXPORT.json"
        m_txt.write_text(txt_path.read_text(encoding="utf-8"), encoding="utf-8")
        m_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
        out["materials_txt"] = str(m_txt)
        out["materials_json"] = str(m_json)
    except OSError:
        pass
    return out


def build_step_card_text(*, filename: str, schematics_dir: str | Path) -> str:
    """Chinese step card after 「进游戏」 export."""
    stem = Path(filename).stem
    return (
        "建造步骤卡\n"
        "──────────\n"
        f"1) 切换到 Minecraft 26.3-Fabric（PCL）\n"
        f"2) Andy / Litematica：列出投影（schematics）\n"
        f"3) 选中文件：{filename}\n"
        f"   （短名：{stem}）\n"
        f"4) 执行「建造」\n"
        "──────────\n"
        f"目录：{schematics_dir}\n"
        "提示：可用「复制文件名」粘贴给 Andy。"
    )


def detect_minecraft_running() -> dict[str, Any]:
    """Heuristic process check. Never injects; display-only."""
    found: list[str] = []
    try:
        if sys.platform.startswith("win"):
            # tasklist is available on Windows; avoid PowerShell for speed/simplicity
            completed = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=8,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,  # pythonw 下防止弹出控制台
            )
            raw = completed.stdout or ""
            for line in raw.splitlines():
                low = line.lower()
                for hint in MC_PROCESS_HINTS:
                    if hint in low:
                        # CSV: "name","pid",...
                        name = line.split(",")[0].strip().strip('"') if line else hint
                        if name and name not in found:
                            found.append(name)
                        break
        else:
            completed = subprocess.run(
                ["ps", "-A", "-o", "comm="],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            for line in (completed.stdout or "").splitlines():
                low = line.strip().lower()
                for hint in MC_PROCESS_HINTS:
                    if hint in low:
                        if line.strip() and line.strip() not in found:
                            found.append(line.strip())
                        break
    except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
        return {
            "running": False,
            "label_zh": "检测失败（忽略即可）",
            "processes": [],
            "error": str(exc),
        }

    if found:
        # Prefer stronger signals
        strong = [p for p in found if "javaw" in p.lower() or "minecraft" in p.lower() or "pcl" in p.lower()]
        label = "游戏似乎在运行"
        if strong:
            label = f"游戏似乎在运行（{', '.join(strong[:3])}）"
        return {"running": True, "label_zh": label, "processes": found, "error": None}
    return {
        "running": False,
        "label_zh": "未检测到 Minecraft / PCL",
        "processes": [],
        "error": None,
    }


def open_in_explorer(path: Path | str, *, select_file: bool = False) -> None:
    """Open folder or reveal file in Explorer / xdg-open."""
    p = Path(path)
    if sys.platform.startswith("win"):
        if select_file and p.is_file():
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            target = str(p if p.is_dir() else p.parent)
            os.startfile(target)  # type: ignore[attr-defined]
    else:
        target = str(p if p.is_dir() else p.parent)
        subprocess.Popen(["xdg-open", target])


def copy_text_to_clipboard(text: str, *, root_widget=None) -> bool:
    """Copy via tkinter clipboard if widget given, else pyperclip/clip fallback."""
    if root_widget is not None:
        try:
            root_widget.clipboard_clear()
            root_widget.clipboard_append(text)
            root_widget.update_idletasks()
            return True
        except Exception:
            pass
    if sys.platform.startswith("win"):
        try:
            subprocess.run(
                ["clip"],
                input=text.encode("utf-16-le"),
                check=False,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return True
        except (OSError, subprocess.SubprocessError, TimeoutError):
            return False
    try:
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=False, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return False
