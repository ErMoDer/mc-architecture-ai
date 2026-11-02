from pathlib import Path

# --- CLI ---
cli = Path("scripts/export_litematic.py")
t = cli.read_text(encoding="utf-8")
if "describe_schematics_target" not in t:
    t = t.replace(
        "from src.data.export_litematic_util import export_voxels_to_companion, resolve_schematics_dir",
        "from src.data.export_litematic_util import (\n"
        "    describe_schematics_target,\n"
        "    export_voxels_to_companion,\n"
        "    resolve_schematics_dir,\n"
        ")",
    )
# add --print-dir flag after --out-dir
if "--print-dir" not in t:
    t = t.replace(
        'parser.add_argument("--latest", type=int, default=4, help="when input is a dir, export N newest (0=all)")',
        'parser.add_argument("--latest", type=int, default=4, help="when input is a dir, export N newest (0=all)")\n'
        '    parser.add_argument(\n'
        '        "--print-dir",\n'
        '        action="store_true",\n'
        '        help="print resolved companion schematics dir and exit",\n'
        '    )',
    )
# after parse_args, handle print-dir and always print target
needle = "    args = parser.parse_args()\n"
if "print_dir" not in t:
    insert = '''    args = parser.parse_args()
    if getattr(args, "print_dir", False):
        info = describe_schematics_target()
        print("schematics_dir=", info["schematics_dir"])
        print("exists=", info["exists"])
        print("companion_env=", info["companion_env"])
        print("source=", info["source"])
        return

'''
    if needle not in t:
        raise SystemExit("parse_args needle missing")
    t = t.replace(needle, insert, 1)

# print target before export loop
if "Export target:" not in t and "schematics_dir=" not in t.split("exporting")[0]:
    t = t.replace(
        '    print(f"exporting {len(inputs)} file(s)")',
        '    target = Path(args.out_dir) if args.out_dir else resolve_schematics_dir()\n'
        '    print(f"export target: {target}")\n'
        '    print(f"exporting {len(inputs)} file(s)")',
    )
cli.write_text(t, encoding="utf-8")
print("cli ok")

# --- viewer status: include schematics_dir explicitly ---
viewer = Path("scripts/viewer_app.py")
vt = viewer.read_text(encoding="utf-8")
old = '''        path = info["path"]
        remap_n = info.get("remap_changed_pairs", 0)
'''
# find status set - make sure schematics_dir is in message
if 'info.get("schematics_dir"' not in vt:
    # replace a short status pattern
    import re
    # After successful export, status already mentions path; prepend schematics_dir line
    m = re.search(r'self\._set_status\(\s*f"已导', vt)
    if not m:
        # try ascii garb
        for frag in ['已导出', '已导', 'Exported']:
            if frag in vt:
                print("found frag", frag)
                break
    # Simpler: after path = info["path"], add dest note into bom_note area
    if 'path = info["path"]' in vt and "schematics_dir_note" not in vt:
        vt = vt.replace(
            'path = info["path"]\n        remap_n = info.get("remap_changed_pairs", 0)',
            'path = info["path"]\n'
            '        schematics_dir_note = info.get("schematics_dir") or resolve_schematics_dir()\n'
            '        remap_n = info.get("remap_changed_pairs", 0)',
            1,
        )
        # inject into status f-string - find _set_status after export
        # append to bom_note instead (safer)
        vt = vt.replace(
            'bom_note = ""\n        if bom_info.get("error"):',
            'bom_note = f"\\n目标目录：{schematics_dir_note}"\n        if bom_info.get("error"):',
            1,
        )
        print("viewer patched")
    else:
        print("viewer skip", "schematics_dir_note" in vt)
else:
    print("viewer already has schematics_dir")
viewer.write_text(vt, encoding="utf-8")
