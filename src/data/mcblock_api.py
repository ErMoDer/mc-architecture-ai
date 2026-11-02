from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


BASE = "https://mcblock.top"
CDN_UA = "mc-architecture-ai/0.1 (personal training; +local)"


def _get_json(url: str, timeout: float = 30.0, retries: int = 3) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": CDN_UA, "Accept": "application/json"})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # SSL/限流/瞬时断连
            last_err = e
            if attempt + 1 >= retries:
                break
            time.sleep(1.0 + attempt)
    assert last_err is not None
    raise last_err


def _download(url: str, dest: Path, timeout: float = 60.0) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": CDN_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def list_buildings(
    *,
    limit: int = 40,
    max_pages: int = 5,
    sort: str = "recommended",
    styles: list[str] | None = None,
    difficulties: list[str] | None = None,
    max_blocks: int | None = None,
    max_width: int | None = None,
    max_depth: int | None = None,
    search_q: str | None = None,
    sleep_s: float = 0.35,
) -> list[dict[str, Any]]:
    """分页拉取建筑库 discovery 列表。

    注意：站点接口用单数 query（difficulty / styles），多值时分次请求再合并。
    """
    # 多难度/多风格：分别请求后按 id 去重（比猜数组语法更稳）
    style_list = styles or [None]
    diff_list = difficulties or [None]
    seen: set[str] = set()
    items: list[dict[str, Any]] = []

    for style in style_list:
        for diff in diff_list:
            cursor = 0
            snapshot = None
            for _ in range(max_pages):
                q: list[tuple[str, str]] = [
                    ("limit", str(limit)),
                    ("sort", sort),
                ]
                if search_q:
                    q.append(("q", search_q))
                if cursor:
                    q.append(("cursor", str(cursor)))
                    if snapshot:
                        q.append(("snapshot", snapshot))
                if style:
                    q.append(("styles", style))
                if diff:
                    q.append(("difficulty", diff))
                if max_blocks is not None:
                    q.append(("maxBlocks", str(max_blocks)))
                if max_width is not None:
                    q.append(("maxWidth", str(max_width)))
                if max_depth is not None:
                    q.append(("maxDepth", str(max_depth)))
                url = f"{BASE}/api/buildings/discovery?{urllib.parse.urlencode(q)}"
                payload = _get_json(url)
                if not payload.get("success"):
                    raise RuntimeError(f"discovery 失败: {payload}")
                data = payload["data"]
                # API 分页需携带 snapshot.id，否则 cursor 会 400
                snap = data.get("snapshot") or {}
                if isinstance(snap, dict) and snap.get("id"):
                    snapshot = snap["id"]
                batch = data.get("items") or []
                for it in batch:
                    bid = it.get("id")
                    if bid and bid not in seen:
                        seen.add(bid)
                        items.append(it)
                nxt = data.get("nextCursor")
                if nxt is None or not batch:
                    break
                cursor = nxt
                time.sleep(sleep_s)
    return items


def get_building(building_id: str) -> dict[str, Any]:
    payload = _get_json(f"{BASE}/api/buildings/{building_id}")
    if not payload.get("success"):
        raise RuntimeError(f"building {building_id} 失败: {payload}")
    return payload["data"]


def download_projection(building: dict[str, Any], out_dir: Path) -> Path | None:
    """下载 .litematic/.schem；返回本地路径。"""
    url = building.get("projectionFileUrl") or building.get("downloadUrl")
    if not url:
        return None
    if isinstance(url, str) and url.startswith("/"):
        url = BASE + url
    suffix = Path(urllib.parse.urlparse(url).path).suffix or ".litematic"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in building.get("name", building["id"]))[:80]
    dest = out_dir / f"{safe}__{building['id'][:8]}{suffix}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    _download(url, dest)
    return dest


def save_manifest(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
