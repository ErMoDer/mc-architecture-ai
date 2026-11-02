#!/usr/bin/env python3
"""E2E smoke for saved design schemes (CLI path).

Exercises: create → load → apply-edit/save → import-litematic → export → snapshot.
Writes SUMMARY.md under outputs/design/schemes_e2e_YYYYMMDD_HHMMSS/.

LOCAL_ONLY. Does not retrain or touch look_harden / early-tech packs.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app.sample_runner import load_voxel_npz
from src.app.schemes import (
    apply_block_replace,
    create_scheme,
    export_scheme_litematic,
    import_litematic,
    list_schemes,
    load_scheme,
    save_scheme,
    scheme_dir,
    snapshot_current,
    stamp_version,
)
from src.data.export_litematic_util import describe_schematics_target


SMOKE_SLUG = "schemes_e2e_smoke"
SMOKE_NAME = "方案_观感冒烟"
EXPORT_NAME = "方案_观感冒烟"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _pick_source_npz() -> Path:
    v4 = ROOT / "outputs" / "design" / "full_style_v4_20261020_112642" / "npz"
    preferred = [
        v4 / "sample_smedieval_tflat_000.npz",
        v4 / "sample_seuropean_tflat_000.npz",
    ]
    for p in preferred:
        if p.is_file():
            return p
    # fallback: any v4 npz
    if v4.is_dir():
        hits = sorted(v4.glob("sample_*.npz"))
        if hits:
            return hits[0]
    raise FileNotFoundError("no full_style_v4 sample npz found")


def _pick_import_litematic() -> Path:
    """Prefer a small probe/sample litematic, not early-tech packs."""
    cands = [
        ROOT / "outputs" / "tmp_scheme_probe" / "方案_smoke_probe_v26.3.litematic",
        ROOT / "outputs" / "litematic" / "scheme_smoke_manor_v26.3.litematic",
    ]
    for p in cands:
        if p.is_file() and p.stat().st_size > 0:
            return p
    # use an existing scheme export if any ai_sample in companion
    from src.data.export_litematic_util import resolve_schematics_dir

    sch = resolve_schematics_dir(create=False)
    for pat in ("中世纪_*.litematic", "欧式_*.litematic", "ai_sample_*.litematic"):
        hits = sorted(sch.glob(pat))
        if hits:
            return hits[0]
    raise FileNotFoundError("no litematic available for import overlay smoke")


def _backup_existing_smoke() -> Path | None:
    d = scheme_dir(SMOKE_SLUG)
    if not d.exists():
        return None
    bak = d.parent / f"{SMOKE_SLUG}_bak_{_stamp()}"
    shutil.move(str(d), str(bak))
    return bak


def main() -> int:
    out_dir = ROOT / "outputs" / "design" / f"schemes_e2e_{_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    steps: list[dict] = []

    def note(msg: str) -> None:
        print(msg)
        log.append(msg)

    note(f"# schemes E2E smoke — {datetime.now().astimezone().isoformat(timespec='seconds')}")
    note(f"out_dir: {out_dir}")

    bak = _backup_existing_smoke()
    if bak:
        note(f"backed up prior smoke scheme → {bak.name}")

    src_npz = _pick_source_npz()
    note(f"source npz: {src_npz}")
    vox0 = load_voxel_npz(src_npz)
    non0 = int((vox0 > 0).sum())

    # 1) create
    created = create_scheme(
        SMOKE_NAME,
        from_npz=src_npz,
        style="medieval",
        terrain="flat",
        notes="E2E smoke from full_style_v4; LOCAL_ONLY",
        slug=SMOKE_SLUG,
    )
    steps.append({"step": "create", "ok": True, "slug": created["slug"], "non_air": created["non_air"]})
    note(f"[create] slug={created['slug']} non_air={created['non_air']} (src={non0})")
    assert created["slug"] == SMOKE_SLUG
    assert created["non_air"] == non0 and non0 > 0

    # 2) load
    loaded = load_scheme(SMOKE_SLUG)
    steps.append(
        {
            "step": "load",
            "ok": True,
            "shape": list(loaded["voxels"].shape),
            "non_air": int((loaded["voxels"] > 0).sum()),
            "meta_name": loaded["meta"].get("name"),
        }
    )
    note(f"[load] name={loaded['meta'].get('name')} shape={loaded['voxels'].shape}")

    # 3) apply-edit: replace a frequent non-air id with another (or self-noop-safe pick)
    vox = loaded["voxels"]
    ids, counts = __import__("numpy").unique(vox[vox > 0], return_counts=True)
    src_id = int(ids[int(counts.argmax())])
    # pick a different existing id if possible, else use stone-ish 1 if present else src
    alt = [int(i) for i in ids if int(i) != src_id]
    tgt_id = alt[0] if alt else (1 if src_id != 1 else 2)
    edited = apply_block_replace(SMOKE_SLUG, src_id, tgt_id)
    steps.append(
        {
            "step": "apply_edit",
            "ok": True,
            "src": src_id,
            "tgt": tgt_id,
            "replaced": edited["replaced"],
            "non_air": edited["non_air"],
        }
    )
    note(f"[apply-edit] {src_id}->{tgt_id} replaced={edited['replaced']}")

    # 4) save with bump (re-load after edit already wrote; save again with notes)
    after_edit = load_scheme(SMOKE_SLUG)
    saved = save_scheme(
        SMOKE_SLUG,
        after_edit["voxels"],
        notes="after apply-edit + save bump",
        bump_version=True,
    )
    steps.append(
        {
            "step": "save_bump",
            "ok": True,
            "non_air": saved["non_air"],
            "version": saved["meta"].get("version"),
            "history_count": saved["meta"].get("history_count"),
        }
    )
    note(
        f"[save] non_air={saved['non_air']} ver={saved['meta'].get('version')} "
        f"history={saved['meta'].get('history_count')}"
    )

    # 5) import-litematic overlay
    lit_in = _pick_import_litematic()
    note(f"import litematic: {lit_in} ({lit_in.stat().st_size} bytes)")
    imported = import_litematic(SMOKE_SLUG, lit_in, mode="overlay")
    steps.append(
        {
            "step": "import_overlay",
            "ok": True,
            "non_air": imported["non_air"],
            "ref": Path(imported["ref"]).name,
            "version": imported["meta"].get("version"),
        }
    )
    note(
        f"[import] mode=overlay non_air={imported['non_air']} "
        f"ref={Path(imported['ref']).name} ver={imported['meta'].get('version')}"
    )

    # 6) export to companion schematics (default out_dir)
    target = describe_schematics_target()
    note(f"schematics target: {target.get('schematics_dir')} exists={target.get('exists')}")
    exported = export_scheme_litematic(SMOKE_SLUG, name=EXPORT_NAME)
    lit_path = Path(exported.get("path") or exported.get("out_path") or "")
    lit_size = lit_path.stat().st_size if lit_path.is_file() else 0
    steps.append(
        {
            "step": "export",
            "ok": lit_path.is_file() and lit_size > 0,
            "path": str(lit_path),
            "size": lit_size,
            "non_air": exported.get("non_air"),
            "target_version": exported.get("target_version"),
        }
    )
    note(f"[export] {lit_path} size={lit_size} non_air={exported.get('non_air')}")
    assert lit_path.is_file() and lit_size > 0, "export litematic missing or empty"

    # also copy export into smoke out_dir for the report bundle
    bundle_lit = out_dir / lit_path.name
    shutil.copy2(lit_path, bundle_lit)

    # 7) snapshot + version stamp
    hist = snapshot_current(SMOKE_SLUG, reason="e2e_smoke")
    ver_path = stamp_version(SMOKE_SLUG, label="e2e_smoke")
    meta_final = load_scheme(SMOKE_SLUG)["meta"]
    steps.append(
        {
            "step": "snapshot",
            "ok": hist is not None and ver_path.is_file(),
            "history": str(hist) if hist else None,
            "version_file": str(ver_path),
            "meta_version": meta_final.get("version"),
            "history_count": meta_final.get("history_count"),
        }
    )
    note(f"[snapshot] history={hist} version={ver_path} meta.ver={meta_final.get('version')}")

    # list schemes (smoke must appear)
    rows = list_schemes()
    smoke_row = next((r for r in rows if r.get("slug") == SMOKE_SLUG), None)
    steps.append({"step": "list", "ok": smoke_row is not None, "n_schemes": len(rows)})

    summary = {
        "ok": all(s.get("ok") for s in steps),
        "slug": SMOKE_SLUG,
        "name": SMOKE_NAME,
        "export_path": str(lit_path),
        "export_size": lit_size,
        "schematics_dir": target.get("schematics_dir"),
        "scheme_dir": str(scheme_dir(SMOKE_SLUG)),
        "steps": steps,
        "final_meta": meta_final,
        "backed_up": str(bak) if bak else None,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    md_lines = [
        "# Schemes E2E smoke",
        "",
        f"- **ok**: `{summary['ok']}`",
        f"- **slug**: `{SMOKE_SLUG}`",
        f"- **name**: {SMOKE_NAME}",
        f"- **scheme dir**: `{scheme_dir(SMOKE_SLUG)}`",
        f"- **export**: `{lit_path}` ({lit_size} bytes)",
        f"- **schematics_dir**: `{target.get('schematics_dir')}`",
        f"- **final version counter**: {meta_final.get('version')}",
        f"- **history_count**: {meta_final.get('history_count')}",
        "",
        "## Steps",
        "",
    ]
    for s in steps:
        md_lines.append(f"- `{s['step']}`: ok={s.get('ok')} — `{json.dumps(s, ensure_ascii=False, default=str)}`")
    md_lines += [
        "",
        "## How to continue this manor",
        "",
        "GUI：双击 `start_viewer.bat` → **编辑** 或 **设计** → **打开方案** → 选 "
        f"`{SMOKE_SLUG}` / {SMOKE_NAME} → 改完点 **保存到方案** → **导出方案** 进 companion schematics。",
        "",
        "CLI：",
        "```bat",
        f'.venv\\Scripts\\python.exe scripts\\scheme.py load {SMOKE_SLUG}',
        f'.venv\\Scripts\\python.exe scripts\\scheme.py export {SMOKE_SLUG} --litematic --name {EXPORT_NAME}',
        "```",
        "",
        "## Log",
        "",
        "```",
        *log,
        "```",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(md_lines), encoding="utf-8")
    note(f"SUMMARY → {out_dir / 'SUMMARY.md'}")
    print(json.dumps({"ok": summary["ok"], "out_dir": str(out_dir), "export": str(lit_path)}, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
