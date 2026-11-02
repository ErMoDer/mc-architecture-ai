# Generation strategies

Default **structure source** is no longer raw ConditionalVAE sampling.

| Strategy | Flag | What it does |
|---|---|---|
| **similar_scaffold** (primary) | --strategy similar_scaffold | Retrieve 1-3 refs from data/feature_index, build shell+floors from 32^3 skeleton, paint materials, look_harden. Falls back to 
ule_scaffold if no refs. |
| **rule_scaffold** | --strategy rule_scaffold | Procedural box shell + floors + pitched roof, then look_harden. |
| **vae_look** (legacy) | --strategy vae_look | Old path: ConditionalVAE -> structure repair -> look_harden. |

## CLI

`at
cd /d "E:\ai agent\mc-architecture-ai"
.venv\Scripts\python.exe scripts\design_from_brief.py --text "medieval stone house" --strategy similar_scaffold --num 2
.venv\Scripts\python.exe scripts\sample.py --conditional --style medieval --terrain flat --strategy similar_scaffold --num 4 --out-dir outputs/samples_scaffold
.venv\Scripts\python.exe scripts\ab_gen_strategy.py
`

Optional: --vae-fill on similar_scaffold for sparse VAE materials inside the scaffold.

## Code

- src/app/gen_strategy.py — retrieve, scaffold builders, generate_with_strategy
- Wires: scripts/design_from_brief.py, scripts/sample.py, src/app/design_brief.generate_from_design
- Related: docs/learn_from_reference.md, docs/look_harden.md, docs/structure_constraints.md


## Retrieval ranking (similar_scaffold)

`retrieve_style_refs` scores `data/feature_index` entries via `_score_ref` then hollow/size bonus:

| Signal | Effect |
|---|---|
| `mapped_style` == query | **+4.0** |
| wrong `mapped_style` (esp. chinese dump on non-chinese query) | **-0.5 / -1.0** |
| English/CJK path style keywords | **+2.0** (kept weaker than label+source) |
| residential tokens (`house`, `住宅`, ...) | **+1.5** |
| challenge / farm / pyramid / breeder / drop / stash / trading_hall | **-4.0** |
| path under `raw/mcblock` | **+4.0**, plus **+1.5** if style also matches |
| path under `hack337` | **-1.5**, extra **-2.0** if chinese-mislabeled for other styles |
| matching `mapped_terrain` | **+0.5** |
| hollow_score >= 0.45 / mid non_air band | **+1.0 / +0.5** after load |

Goal: style-correct MCBlock houses outrank Hack337 `MCBuildChallenge` / English keyword spam.

## Rustic / irregular roof scaffold (2026-10-19)

similar_scaffold roof path for lakeside/low-pitch refs:

1. **Building footprint** (_building_footprint_from_occ) skips full-box ground-fill slabs in 32^3 skeletons.
2. **low_pitch_deck** roof over that footprint (style-aware rise 2-3) instead of painting only the sparse top occupancy slice.
3. **Full peri walls every Y** up to the deck so tapered rings stay one CC (avoids drop_float_cc chopping the roof).
4. **Roof cover metric** uses _elevated_footprint (columns above the ground band). SCAFFOLD_THRESHOLDS.min_roof_score stays **0.18** — not loosened further.
5. **look_harden**: rustic/western facade silhouette keeps **flat** deck (scaffold already low-pitch); aggressive gable clear was wiping lakeside decks.

Smoke: outputs/design/rustic_roof_fix_* (rustic lakeside 3/3 ok; fantasy regression 2/2 ok).

## Structure checker (scaffold path)

VAE samples use `DEFAULT_THRESHOLDS`. Scaffold generators pass `SCAFFOLD_THRESHOLDS`:

- `min_exterior_solid_frac`: 0.06 → **0.0** (volume-box faces; centered scaffolds often ~0)
- `min_roof_score`: 0.30 → **0.18** (sparse flat roofs)
- `min_hollow_score`: 0.32 → **0.28**
- `min_largest_cc_frac`: 0.40 → **0.35**
- `min_non_air`: 120 → **80**

Do not treat `structure_ok` alone as look quality; still inspect PNG previews.

## Why

Continue-train from ~ep900 collapses; VAE+look_harden still looks like painted mush. Scaffold-first uses real schematic occupancy for shell/floors before polish.

## Block2Vec blend (plan 3)

After plan-2 heuristic ranking, `retrieve_style_refs` optionally adds a light embedding term:

1. Prototype = mean L2 vector of same-style **mcblock** embeddings in `data/feature_index/*_block2vec.npy` (fallback: any same-style).
2. Candidate pool = top `top_k*5` with heuristic base >= 0.5.
3. `score = base + 0.85 * cosine(prototype, candidate)` when the candidate has an embedding.
4. Toggle: `use_block2vec=False` or `b2v_weight=0` disables the blend.

Heuristic source/style boosts still dominate; Block2Vec only reorders within the curated pool. Batch embed: `scripts/batch_embed_block2vec.py`. Smoke: `scripts/smoke_b2v_retrieval.py`.

## Style aliases (specialty pools)

| Canonical | Aliases / path keywords (non-exhaustive) |
|---|---|
| **rustic** | cabin, barn, farmhouse, log cabin; CJK: 田园, 农舍, 木屋, 乡村 |
| **fantasy** | elf, wizard, mage, fairy, mushroom; CJK: 奇幻, 精灵, 魔法 |

similar_scaffold ranks by mapped_style + mcblock source first. When the rustic/fantasy **mcblock house** pool is thin, tops can still drift toward european/medieval cottages via shared tokens (armhouse, cottage). Prefer curated specialty houses in data/feature_index (see outputs/design/rustic_fantasy_pool_*).

## Role materials (scaffold path, 2026-10-19)

similar_scaffold / rule_scaffold paint **role-based** blocks (not one wall_id mush):

| Role | Typical |
|---|---|
| foundation | cobble / stone_bricks / gray_concrete |
| wall | style primary (planks, bricks, concrete, quartz…) |
| roof | darker / contrast full cube (from stair hint when present) |
| floor | planks / smooth_stone / concrete |
| accent | logs / pillars / amethyst (corners + banding) |
| window_frame | log / stone / iron (glass still separate) |

Code: src/app/scaffold_materials.py → 
esolve_role_materials; wired in gen_strategy + look_harden(role_materials=…).
Smoke: scripts/_run_scaffold_materials.py → outputs/design/scaffold_materials_*.

## Look polish (2026-10-19)

Scaffold path visual polish (no VAE continue-train):

1. **Sparse / European roof deck** — `_fill_footprint_holes` closes outline rings; solid deck over filled footprint; european/sparse `max_rise<=1` + broad plateau so `roof_score` is not killed by needle tips.
2. **Junk / odd role materials** — expanded skip list + `_STYLE_ROLE_DENY` (e.g. acacia Victorian walls, chinese `mud_bricks` house walls) fall back to style wood/stone/plaster.
3. **Roof != wall after cube remap** — re-diversify after `prefer_full_cube`; hard-force style roof if still equal.

Smoke: `scripts/_run_look_polish_smoke.py` -> `outputs/design/look_polish_*`.

## Window / eave polish (2026-10-19)

similar_scaffold -> look_harden facade path:

- Regular window columns + sill/header; style spacing via `look_harden._STYLE_FACADE`.
- Eave overhang + cornice under deck; flat-deck styles keep roof cover from look_polish.
- Smoke: `scripts/_run_win_eave_smoke.py`.

## Door / wall rhythm polish (2026-10-19)

similar_scaffold -> look_harden facade:

- Ground-floor door with threshold/frame; wall pier rhythm between windows.
- Does not undo window bands, eaves/cornice, or flat-deck roof preserve.
- Smoke: `scripts/_run_door_wall_smoke.py`.

## Glass density (modern / industrial, 2026-10-19)

`_STYLE_FACADE` only: modern/industrial window spacing & band caps. No change to euro/chinese/rustic flat-deck or door/pier rules for other styles.
Smoke: `scripts/_run_glass_dens_smoke.py`.

## Rustic pier spacing (2026-10-19)

`_STYLE_FACADE` rustic `wall_pier_spacing` 4→10. Other styles unchanged.
Smoke: `scripts/_run_rustic_pier_smoke.py`.

## Rustic pier spacing 12 (2026-10-19)

Follow-up to rustic_pier (4→10): rustic `wall_pier_spacing` **10 → 12**. Other styles unchanged.
Smoke: `scripts/_run_rustic_pier12_smoke.py` -> `outputs/design/rustic_pier12_*`.

## Scaffold structure harden (2026-10-19)

similar_scaffold / rule_scaffold skeleton polish (no VAE train; facade look_harden unchanged):

1. **Floors** — `_normalize_story_floors`: spacing≈5, min_gap=3, max 5 stories; ref `y_peaks` are hints only (stops industrial floor-every-3). Roof deck Y is not a floor slab. Sparse interiors fill only on the **ground** story.
2. **Shell** — `_seal_shell_columns` closes perimeter air gaps under the deck.
3. **Roof** — flat-deck styles keep filled low deck (euro/chinese/rustic roof≈1). Medieval/fantasy add broad **deck+gable** on scaffold; look_harden pitched uses a **ridge plateau** so cover is not needle-thin.

Smoke: `scripts/_run_scaffold_struct_smoke.py` -> `outputs/design/scaffold_struct_*`.

## 红石嵌入建筑

观感样例导出后，可用 scripts/paste_redstone_into_design.py 把原理模板嵌进外壳（见 docs/redstone_templates.md）。不经 VAE，不改 look_harden 旋钮。

## Hollow shell (2026-10-20)

Root cause of "solid blob" houses: full footprint floors + sparse euro low_pitch_deck_filled interior posts.

scaffold_from_occupancy / 
ule_scaffold_voxels:

1. **Ring floors** via _ring_floor_mask (distance-from-perimeter band; upper stories depth 1).
2. Story schedule spacing 6 / min_gap 4 / max 4 stories.
3. Sparse roof: perimeter seal only — **no** (x+z)%3 interior posts; mode low_pitch_deck_shell.
4. _force_open_room after scaffold and again after look_harden (flat styles clear core; pitched styles loors_only).

Gates in SCAFFOLD_THRESHOLDS: max_floor_interior_cover, min_interior_room_air.

Smoke: scripts/_run_shell_hollow.py. Euro/industrial/rustic solids roughly halved vs pool_scaffold; interior_cover ~0.97→~0.2.

## eave_rooms roof + partitions (2026-10-20)

`scaffold_from_occupancy` roof modes:

| style family | roof_mode | notes |
|---|---|---|
| european / rustic / western / chinese / medieval / fantasy | `skin_gable` | hollow attic; eave ring + overhang; gable-end peri walls under slope |
| industrial / modern | `flat_eave_deck` | flat cover + 1-cell eave lip |

Also: `_place_interior_partitions` (mid wall or L-split, doorway). Medieval/fantasy use thinner ring floors so `interior_cover` stays under scaffold gate.

Helpers: `_gable_rise_map`, `_place_skin_gable_roof`, `_place_interior_partitions`.
Smoke: `scripts/_run_eave_rooms.py`.
