"""Helpers for exporting litematic to companion schematics dir."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.data.litematic import save_litematic
from src.data.mc_versions import (
    DEFAULT_VERSION_ID,
    filename_version_tag,
    get_version,
    remap_palette,
    remap_summary,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def companion_env_path() -> Path | None:
    candidates = [
        project_root().parent / "mc-companion" / ".env",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def resolve_schematics_dir(*, create: bool = True) -> Path:
    """Companion SCHEMATICS_DIR from mc-companion/.env, else outputs/litematic.

    Always returns an absolute Path. Optionally creates the directory so export
    does not fail when PCL schematics folder was deleted.
    """
    env = companion_env_path()
    dest: Path | None = None
    source = "fallback:outputs/litematic"
    if env is not None:
        try:
            for line in env.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("SCHEMATICS_DIR="):
                    raw = s.split("=", 1)[1].strip().strip('"').strip("'")
                    if raw:
                        dest = Path(raw).expanduser()
                        source = f"mc-companion/.env:{env}"
                        break
        except OSError:
            pass
    if dest is None:
        dest = project_root() / "outputs" / "litematic"
    dest = dest.resolve() if dest.is_absolute() else (project_root() / dest).resolve()
    if create:
        dest.mkdir(parents=True, exist_ok=True)
    # stash for callers / CLI messaging
    resolve_schematics_dir.last_source = source  # type: ignore[attr-defined]
    return dest


def describe_schematics_target() -> dict:
    """Human-readable export target (for CLI / GUI status)."""
    env = companion_env_path()
    path = resolve_schematics_dir(create=False)
    return {
        "schematics_dir": str(path),
        "exists": path.is_dir(),
        "companion_env": str(env) if env else None,
        "source": getattr(resolve_schematics_dir, "last_source", None),
    }


def export_voxels_to_companion(
    voxels,
    palette: dict[int, str],
    *,
    name: str,
    author: str = "mc-architecture-ai",
    out_dir: Path | None = None,
    verify: bool = True,
    target_version: str | None = None,
    version_in_filename: bool = True,
) -> dict:
    """Export voxels as .litematic, remapping block IDs for a Java target version.

    Default target_version is Java 26.3 (Wilderness Bound). Generation palette
    is unchanged; only the written schematic names are remapped/downgraded.
    """
    ver = get_version(target_version)
    dest = Path(out_dir) if out_dir else resolve_schematics_dir()
    dest.mkdir(parents=True, exist_ok=True)

    tag = filename_version_tag(ver.id)
    out_name = name
    if version_in_filename:
        # avoid double suffix if caller already included _v26.3
        if f"_{tag}" not in name and not name.endswith(tag):
            out_name = f"{name}_{tag}"

    out_path = dest / f"{out_name}.litematic"

    vox = np.asarray(voxels)
    used_ids = sorted({int(i) for i in np.unique(vox)})
    summary = remap_summary(palette, ver.id, used_ids)
    remapped = remap_palette(palette, ver.id)

    description = (
        f"Exported from mc-architecture-ai; target Java {ver.id} "
        f"({ver.display_name}); remapped_pairs={summary['changed_pairs']}"
    )
    info = save_litematic(
        voxels,
        remapped,
        out_path,
        name=out_name,
        author=author,
        description=description,
        verify=verify,
    )
    info["schematics_dir"] = str(dest)
    info["schematics_dir_source"] = getattr(resolve_schematics_dir, "last_source", None)
    info["target_version"] = ver.id
    info["target_display"] = ver.display_name
    info["remap_changed_pairs"] = summary["changed_pairs"]
    info["remap_examples"] = summary["examples"]
    info["default_version"] = DEFAULT_VERSION_ID
    return info
