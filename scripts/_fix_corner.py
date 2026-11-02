from pathlib import Path
p=Path('src/app/gen_strategy.py')
t=p.read_text(encoding='utf-8')
old="                # Corner posts use load_bearing when available (logs/stone), not trim clutter.
                corner_id = int(mat_info.get('load_bearing_id') or accent_id)
"
new="                # Corner posts: load_bearing if distinct from wall, else accent (logs).
                corner_id = int(mat_info.get('load_bearing_id') or accent_id)
                if corner_id == int(wall_id):
                    corner_id = int(accent_id)
"
if old not in t:
    raise SystemExit('missing')
p.write_text(t.replace(old,new,1),encoding='utf-8')
print('ok')
