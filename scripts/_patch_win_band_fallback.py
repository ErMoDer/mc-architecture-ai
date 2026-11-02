from pathlib import Path
PATH = Path("src/app/look_harden.py")
text = PATH.read_text(encoding="utf-8")
old = '''    if max_bands > 0 and len(bands) > int(max_bands):
        # keep lower bands (street-facing stories) first
        bands = bands[: int(max_bands)]
    info["bands"] = bands
    if not bands:
        return out, actions, info
'''
new = '''    if max_bands > 0 and len(bands) > int(max_bands):
        # keep lower bands (street-facing stories) first
        bands = bands[: int(max_bands)]
    # Fallback: one mid-wall band when schedule was too strict but wall is tall enough.
    if not bands and int(y1) - int(y0) >= ff + wh + 2:
        y_bot = int(y0) + max(ff, 2)
        y_top = min(y_bot + wh - 1, int(y1) - 2)
        if y_top >= y_bot:
            bands = [(y_bot, y_top)]
    info["bands"] = bands
    if not bands:
        return out, actions, info
'''
if old not in text:
    raise SystemExit('band fallback anchor missing')
PATH.write_text(text.replace(old, new, 1), encoding='utf-8')
print('fallback ok')
