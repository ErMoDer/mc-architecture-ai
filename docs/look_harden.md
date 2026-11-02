# Look Harden（观感后处理）

采样后、结构约束之后收紧壳/楼层/材质；**不重训、仍 32³**。

- 实现：`src/app/look_harden.py`
- 结构约束：`docs/structure_constraints.md`
- 材质 A/B：`outputs/design/look_harden_20261018_211701/LOOK_HARDEN.md`
- 壳+楼层加强 A/B：`outputs/design/look_harden_shell_floors_*/LOOK_HARDEN_SHELL_FLOORS.md`
- 保留窗洞 A/B：`outputs/design/look_harden_keep_windows_*/LOOK_HARDEN_KEEP_WINDOWS.md`
- **立面（门/屋顶/檐口/节奏）A/B**：最新一次 `outputs/design/look_harden_facade_*/LOOK_HARDEN_FACADE.md`
- CLI：`--structure-constrain` 默认开观感；`--no-look-harden` 可关
- 几何：默认 `geometry_mode="strong"`
- **窗洞**：默认 `preserve_windows=True`；全填墙：`preserve_windows=False`
- **立面**：默认 `facade_detail=True`（门洞、平顶/坡顶、檐口、束带、角柱）；关闭：`facade_detail=False`
- `sample_runner.generate_samples(..., preserve_windows=True, place_window_glass=True)`

## Scaffold deck preserve (2026-10-19)

`harden_roof_silhouette` forces flat/low deck (no pitched gable wipe) for **rustic / western / european / chinese** so similar_scaffold `low_pitch_deck` / filled euro decks keep `roof_score`.

## Window / eave polish (2026-10-19)

Scaffold look_harden facade polish (no VAE train):

1. **Window rhythm** — even story bands from `floor_spacing` (not every irregular floor peak); centered columns; optional **sill/header** with `window_frame` / accent; `max_window_bands` + style spacing (`_STYLE_FACADE`).
2. **Eaves** — `eave_overhang` (0–2) actually walks outward; never clears flat-deck cover on the footprint (euro/chinese/rustic preserve).
3. **Cornice ring** — peri trim at `roof_y-1` when style wants it; still works when the footprint fills the 32^3 box and overhang has no room.
4. Preserve existing window-like openings + glass; do not fill real windows when repairing floors/holes.

Smoke: `scripts/_run_win_eave_smoke.py` -> `outputs/design/win_eave_*`.

## Door / wall rhythm polish (2026-10-19)

After win_eave:

1. **Doors** — primary facade entrance via real outward faces; 1–2×2 opening; door block + **threshold** (floor) + optional **frame/lintel** (accent). Hole-fill will not reseal beside existing doors.
2. **Wall piers** — vertical accent columns between window bays (`wall_pier_spacing`); corner pillars kept. Modern stays opener (`place_wall_piers=False`).
3. Style knobs live in `look_harden._STYLE_FACADE`.

Smoke: `scripts/_run_door_wall_smoke.py` -> `outputs/design/door_wall_*`.

## Glass density (modern / industrial, 2026-10-19)

After `full_style_review_*` (modern glass~320, industrial~456):

- **modern**: `window_spacing=6`, `window_width_max=2`, `max_window_bands=2`, `window_from_corner=3` — still opener bay width than euro, breaks curtain walls.
- **industrial**: added to `_STYLE_FACADE` (was falling through to dense defaults); `spacing=4`, `width_max=1`, `max_window_bands=3`, solid panels via pier spacing.

Other styles unchanged. Smoke: `scripts/_run_glass_dens_smoke.py` -> `outputs/design/glass_dens_*`.

## Rustic pier spacing (2026-10-19)

After review batches showed rustic wall_piers ~300-322 cells (柱林):

- rustic `wall_pier_spacing` **4 → 10** only; piers kept, thinner vertical rhythm (~half columns).
- modern/industrial glass_dens knobs untouched.

Smoke: `scripts/_run_rustic_pier_smoke.py` -> `outputs/design/rustic_pier_*`.

## Rustic pier spacing 12 (2026-10-19)

Follow-up to rustic_pier (4→10): rustic `wall_pier_spacing` **10 → 12**. Other styles unchanged.
Smoke: `scripts/_run_rustic_pier12_smoke.py` -> `outputs/design/rustic_pier12_*`.

## euro_fan_dens (2026-10-19)

After `full_style_v2_20261019_211250` user picked **压欧式玻璃 / 奇幻壁柱**:

| style | knob | before (v2) | after | aim |
|---|---|---|---|---|
| european | `window_spacing` 3→**4**, `max_window_bands` 4→**3**, `window_from_corner` 2→**3** | glass **448** | ~**256** (smoke) | 200–280 |
| fantasy | `wall_pier_spacing` 3→**5** | piers **221** (000) / 115 (001) | ~**81** / ~**56** | ~60–120 / rustic~90 |

First mid-patch overshot (eu sp5/bands2 → glass~130; fantasy pier12 → ~33); settled on values above.

**Untouched:** modern `window_spacing=6`, industrial `=4`, rustic `wall_pier_spacing=12`, scaffold_struct, flat-deck preserve, doors/windows/eaves generally.

Smoke: `outputs/design/euro_fan_dens_<timestamp>/`.

## full_style_v3 (2026-10-20)

Full-style similar_scaffold smoke after `euro_fan_dens_20261019_212806` knobs (no code change this run).

- out: `outputs/design/full_style_v3_20261020_085033/`
- structure_ok: **9/9**
- euro/chinese/rustic roof~1: **True**
- vs: `full_style_v2_20261019_211250` (pre dens) + `euro_fan_dens_20261019_212806`

| style | ok | roof | glass v2 -> v3 | piers v2 -> v3 | note |
|---|---|---|---|---|---|
| chinese | True | 1.000 | 242 -> 242 | 25 -> 25 | stable |
| european | True | 1.000 | **448 -> 256** | 60 -> 109 | matches euro_fan_dens; aim 200-280 |
| medieval | True | 0.750 | 348 -> 348 | 174 -> 174 | pitched+gable residual |
| modern | True | 1.000 | 208 -> 208 | 0 -> 0 | glass_dens held |
| rustic | True | 1.000 | 168 -> 168 | 88 -> 88 | pier=12 held |
| rustic | True | 1.000 | 346 -> 346 | 90 -> 90 | second sample |
| fantasy | True | 0.770 | 374 -> 374 | **221 -> 81** | matches euro_fan_dens |
| fantasy | True | 0.718 | 238 -> 238 | **115 -> 56** | matches euro_fan_dens |
| industrial | True | 1.000 | 186 -> 186 | 35 -> 35 | glass_dens held |

**No regression:** eu glass not back near 448; fantasy piers not back near 200+; roofs unchanged vs v2. Previews under that run dir `previews/`.

## fantasy_glass_dens (2026-10-20)

After `full_style_v3_20261020_085033` user asked to **补足短板** (fantasy glass still high; roof left for follow-up):

| style | knob | before (v3) | after | aim |
|---|---|---|---|---|
| fantasy | `window_spacing` 3→**4**, `max_window_bands` 4→**3**, `window_from_corner` (default2) kept **2** | glass **374** / 238 | ~**230** / ~**144** | denser 200–280; stay a bit glazier than euro |
| fantasy | `wall_pier_spacing` **5** kept | piers **81** / 56 | **81** / **56** | hold euro_fan_dens pier mid |

First mid-patch used euro settle recipe c3 → denser glass~212 (ok) but sparse~126 and piers 81→133 (more solid wall for pier fill). Softened to **from_corner=2**; piers snapped back, denser glass~230.

**Untouched:** european 4/3/c3, modern sp=6, industrial sp=4, rustic pier=12, scaffold_struct / pitched roof scaffold.

Smoke: `outputs/design/fantasy_glass_dens_20261020_090033/` (prior probe `..._090008` was c3). Scripts: `scripts/_patch_fantasy_glass_dens.py`, `_patch_fantasy_glass_dens2.py`, `_run_fantasy_glass_dens.py`.

**Residual (closed by pitch_roof):** medieval/fantasy pitched roof_score ~0.72–0.77 → see § pitch_roof (plateau 0.72 / rise cap 3).

## pitch_roof (medieval / fantasy, 2026-10-20)

After `fantasy_glass_dens_20261020_090033`, remaining shortfall was **pitched roof_score ~0.72–0.77** (medieval/fantasy). Metric uses `top_footprint_cover` at absolute `y_max`; look_harden's pitched gable used plateau **0.32×half** + rise≈half (cap 5), so only a thin ridge hit `y_max` (cover ~0.37–0.49) while wiping scaffold `low_pitch_deck+gable`.

**Fix (pitched styles only — medieval/fantasy):**

| path | knob | before | after |
|---|---|---|---|
| `look_harden.harden_roof_silhouette` | ridge plateau | 0.32×half | **0.72×half** |
| same | rise | min(5, half) | **cap 3** (still ≥2) |
| `gen_strategy` scaffold gable + `rule_scaffold_voxels` | plateau / rise | 0.35×half / ≤4 | **0.72×half / ≤3** |

Flat-deck preserve for rustic/western/european/chinese **unchanged** (want_pitch forced off). Facade dens knobs **unchanged** (fantasy sp4/bands3/c2 pier5; euro 4/3/c3; rustic pier12).

Smoke: `outputs/design/pitch_roof_20261020_090715/` — **5/5** structure_ok.

| style | roof before→after | cover before→after | glass | piers | note |
|---|---|---|---|---|---|
| medieval | 0.750→**0.937** | 0.445→0.860 | 348→344 | 174→183 | pitched kept |
| fantasy | 0.770→**0.967** | 0.490→0.926 | 230→228 | 81→88 | dens held |
| fantasy | 0.718→**0.935** | 0.374→0.855 | 144→138 | 56→33 | glass dens; pier thinner on sparse sample |
| european | 1.000→1.000 | 1.0 | 256 | 109 | flat control |
| rustic | 1.000→1.000 | 1.0 | 168 | 88 | flat control |

**Residual:** scores ~0.93–0.97, not flat 1.0 (outer ~28% still slopes — honest). Sparse fantasy pier cells can dip when eave/peak shift pier column height; spacing knob untouched. Further →1.0 would need near-flat plateau or a top-band cover metric change.

Scripts: `scripts/_patch_pitch_roof.py`, `_run_pitch_roof_smoke.py`.

## full_style_v4 (2026-10-20)

Full-style similar_scaffold smoke after antasy_glass_dens_20261020_090033 + pitch_roof_20261020_090715 (no code change this run; facade+roof knobs held).

- out: outputs/design/full_style_v4_20261020_112642/
- structure_ok: **9/9**
- euro/chinese/rustic roof~1: **True**
- vs: ull_style_v3_20261020_085033 (pre glass dens + pre pitch_roof) + dens/pitch smokes

| style | ok | roof v3 -> v4 | glass v3 -> v4 | piers v3 -> v4 | note |
|---|---|---|---|---|---|
| chinese | True | 1.000 -> 1.000 | 242 -> 242 | 25 -> 25 | stable |
| european | True | 1.000 -> 1.000 | **256 -> 256** | 109 -> 109 | euro dens held |
| medieval | True | 0.750 -> **0.937** | 348 -> 344 | 174 -> 183 | pitch_roof held |
| modern | True | 1.000 -> 1.000 | 208 -> 208 | 0 -> 0 | glass_dens held |
| rustic | True | 1.000 -> 1.000 | 168 -> 168 | 88 -> 88 | pier=12 held |
| rustic | True | 1.000 -> 1.000 | 346 -> 346 | 90 -> 90 | second sample |
| fantasy | True | 0.770 -> **0.967** | 374 -> **228** | 81 -> 88 | glass dens + pitch held |
| fantasy | True | 0.718 -> **0.935** | 238 -> **138** | 56 -> 33 | glass dens; sparse pier thinner (spacing knob untouched) |
| industrial | True | 1.000 -> 1.000 | 186 -> 186 | 35 -> 35 | glass_dens held |

**Knobs still present:** european window_spacing=4 / max_window_bands=3 / window_from_corner=3; fantasy wall_pier_spacing=5 / window_spacing=4 / max_window_bands=3 / window_from_corner=2; modern sp=6; industrial sp=4; rustic pier=12; pitch_roof plateau 0.72 + rise cap 3 (harden + scaffold sync).

**Export:** 9 architecture litematics into companion SCHEMATICS_DIR as Chinese stems 中式/欧式/中世纪/现代/工业/田园_000|_001/奇幻_000|_001_v26.3.litematic (overwrite prior architecture demos). Early-tech Chinese names (超级熔炉_*, 小型铁矿_*, 简易铁矿_*, 大型刷怪经验塔_*, 鸡舍_二_红石参考_*) left untouched.

Scripts: scripts/_run_full_style_v4.py, scripts/_export_full_style_v4_cn.py.

## Style refs top-up (2026-10-20)

Quality path = **more correct residential refs + templates**, not VAE resume.

- Report: outputs/design/style_refs_topup_20261020_120308/TOPUP_REPORT.md
- **rustic** mcblock residential: **3 → 32** (retag cabin/cottage/farmhouse/木屋/农舍 with strong house evidence; API rustic pool saturated ~16)
- feature_index: 1052 → 1054 (+2 reingest modern/western residential)
- european/modern: API already largely in manifest; small net change from rustic retags
- Retrieval smoke (smoke/smoke_retrieval.json): mcblock tops for rustic/european/modern
- Scaffold smoke: outputs/design/scaffold_rustic_topup_20261020_121627/
- Script: scripts/_topup_style_refs_residential.py (style-only discovery; avoids difficulty+q 400s)

## Industrial loft top-up (2026-10-20)

Goal: thin mcblock industrial **residential** loft pool + farm pollution in industrial mapped.

- Demoted **46** farm/smelter/kelp/XP-ish Hack337 dumps: mapped_style industrial → unknown, exclude_from_residential=true, exclude_reason=public_production.
- Expanded _BUILDING_PENALTY (kelp/smelter/bonemeal/…) and hard -50 score when exclude_from_residential.
- MCBlock new residential ingest (detail URL required): industrial **mapped 137→99** (46 demoted), **mcblock 7→15** (+8 residential loft/house).
- Retrieval smoke: industrial top-5 all **mcblock** houses (no farm tops).
- Report: outputs/design/industrial_rs_topup_20261020_131918/.
- **No VAE train.** Queries for loft/warehouse often return 0; API list is mostly public_production — best-effort residential-only.



## Long fill residential refs (long_fill_20261020_134027)

No facade knob changes. Industrial mcblock 15→16; european 31→37; modern 35→38; chinese mapped 572→456 (farmish demoted). See `outputs/design/long_fill_20261020_134027/COUNTS.md`.


## Long fill2 (long_fill2_20261020_135822)

No facade knob / VAE changes. Hack337 house retag n=16 + MCBlock house topup; european mapped 40→44 (mcblock 37→40); modern 42→46 (mcblock 38); rustic 36→48 (mcblock 32→35); western 13→15. RS catalog 28→34. See `outputs/design/long_fill2_20261020_135822/COUNTS.md`.


MCBlock retry (no search_q): european mcblock 37→40, rustic 32→35, modern unchanged (38).

Final snapshot: european mapped 44 / mcblock 40; modern 46 / 38; rustic 48 / 35; western 15; RS 34.

## Hollow shell floors (2026-10-20)

similar_scaffold looked like solid crates: full-footprint floor slabs every ~5 Y + sparse euro interior posts under filled decks.

Changes (no VAE train):

1. **look_harden** hollow_floors=True (default on strong path): paint **ring** floors (depth 1) and carve center floor fill; wider floor spacing (>=6). Prefer openings over denser mass.
2. Metrics: loor_interior_cover, interior_room_air (door-tolerant). Scaffold gates use these instead of flood-fill enclosed-CC (doors connect rooms to outside).
3. Smoke: scripts/_run_shell_hollow.py -> outputs/design/shell_hollow_*; game names 壳改_<风格>住宅_v26.3.

See also docs/gen_strategy.md hollow shell section.

## eave_rooms (2026-10-20)

True eaves / pitched **skin** silhouette + simple interior partitions (no VAE).

- **Scaffold** (`gen_strategy`): `skin_gable` for european/rustic/western/chinese/medieval/fantasy — eave **ring** (not full attic slab) + roof surface only + overhang 1–2; industrial/modern keep `flat_eave_deck` + eave lip. Interior mid/L partition (1-thick, doorway). Ring floors + corner load posts kept.
- **look_harden**: stop force-flat on euro/rustic/western/chinese; pitched path is **skin-only** (no solid attic fill). european/rustic `eave_overhang=2`; industrial overhang=1 + cornice.
- Smoke: `scripts/_run_eave_rooms.py` → `outputs/design/eave_rooms_*`; schematics `檐分_*_v26.3`.
- vs `block_struct_20261020_200345`: euro/industrial/rustic room_air up / int_cover down; pitched roof_score ~0.74–0.85 (silhouette tradeoff vs flat 1.0). structure_ok 8/8.

**Residual:** boxy massing; partitions are crude L/mid only; chinese solids still high; roof_score heuristic underrates skin gables.
