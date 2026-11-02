from pathlib import Path
p = Path("scripts/_run_win_eave_smoke.py")
t = p.read_text(encoding="utf-8")
old = '''from src.app.look_harden import window_opening_count
'''
new = '''from src.app.look_harden import window_opening_count
import src.app.look_harden as _lh
'''
if "import src.app.look_harden as _lh" not in t:
    t = t.replace(old, new, 1)

old2 = '''            win = window_opening_count(vox)
'''
new2 = '''            # Ensure glass heuristics see palette (window_opening_count uses module palette ref).
            _lh._PALETTE_REF = palette
            win = window_opening_count(vox)
            # also count glass by palette name (robust)
            glass_by_name = 0
            for bid in np.unique(vox[vox > 0]):
                name = str(palette.get(int(bid), ""))
                if "glass" in name.lower() or name.endswith("_pane"):
                    glass_by_name += int((vox == bid).sum())
            win["glass_cells"] = max(int(win.get("glass_cells", 0)), glass_by_name)
'''
if old2 not in t:
    raise SystemExit('win count anchor missing')
t = t.replace(old2, new2, 1)
p.write_text(t, encoding="utf-8")
print("smoke metric fix ok")
