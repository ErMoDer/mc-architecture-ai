# Interior partition style policy (Phase D)

Actionable knobs for `gen_strategy._place_interior_partitions` / `look_harden_rules.json` `partition_modes`.

## Why

Full-height `cross_split` on dense / tall styles (chinese, medieval, fantasy) added hundreds of solids and cut `interior_room_air` almost 1:1 (Phase C regression). European/rustic still benefit from stronger splits.

## Policy

| Tier | Styles | Max mode | Height |
|------|--------|----------|--------|
| open | industrial, modern | mid wall + door | full to eave-1 |
| mild | chinese, medieval, fantasy, japanese | mid or **short L** (stub ≤4) | **~1 story** (y_lo..y_lo+4) |
| strong | european, rustic, western | T or cross when cavity large | full to eave-1 |

## Requirements

- Always punch a 2-high doorway on the primary wall.
- Never fuse partitions into the outer shell (erode interior before placing).
- Prefer raising `room_air` over maximizing room count on mild tier.

## Wired

- Code: `src/app/gen_strategy.py` → `_place_interior_partitions`
- JSON: `look_harden_rules.json` v4 `partition_modes` + notes.partition_policy
