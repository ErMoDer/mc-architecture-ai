# -*- coding: utf-8 -*-
from pathlib import Path

util = Path("src/data/export_litematic_util.py")
text = util.read_text(encoding="utf-8")

old_resolve = '''def resolve_schematics_dir() -> Path:
    env = companion_env_path()
    if env is not None:
        try:
            for line in env.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("SCHEMATICS_DIR="):
                    raw = s.split("=", 1)[1].strip().strip('"').strip("'")
                    if raw:
                        return Path(raw)
        except OSError:
            pass
    return project_root() / "outputs" / "litematic"
'''

new_resolve = '''def resolve_schematics_dir(*, create: bool = True) -> Path:
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
'''

if old_resolve not in text:
    raise SystemExit("resolve block missing")
text = text.replace(old_resolve, new_resolve, 1)

# enrich export_voxels return with describe
old_ret = '''    info["schematics_dir"] = dest
    info["target_version"] = ver.id
'''
new_ret = '''    info["schematics_dir"] = str(dest)
    info["schematics_dir_source"] = getattr(resolve_schematics_dir, "last_source", None)
    info["target_version"] = ver.id
'''
if old_ret not in text:
    raise SystemExit("ret block missing")
text = text.replace(old_ret, new_ret, 1)

util.write_text(text, encoding="utf-8")
import ast
ast.parse(util.read_text(encoding="utf-8"))
print("util ok")
