# Clean materials (净材)

## Problem
Scaffold samples looked cluttered: rainbow mats from reference 	op_blocks
(green_concrete, tuff_bricks, acacia, bone_block), oak_log pier forests, speckles / floaters.

## Clutter sources found (eave_rooms batch)
- Industrial: tuff_bricks + bricks + spruce_planks + green_concrete (ref override)
- European: oak_log pier spam (~1100 cells)
- Western: acacia_planks / acacia_log
- Medieval: bone_block accent
- Modern: dark_oak_planks leak
- Mixed wall mats from reference copy + dense wall_piers

## Changes
- src/app/scaffold_materials.py: stronger per-style role deny; **all roles** use
  STYLE_ROLE_FALLBACKS (no ref rainbow for wall/roof/floor/foundation/accent/load).
- src/app/look_harden.py: drop hopper/dirt from style structural lists; bone/hopper junk;
  wall_pier_spacing widened to 8; unify_role_surfaces + despeckle_solids after geometry
  (one wall/roof/floor, cap accent, drop float CCs, despeckle); tighter palette when roles set.

## Keep
eave_rooms skin_gable, partitions, ring floors, corner posts, hollowness. No VAE / scrape.

## Smoke
scripts/_run_clean_mats.py -> outputs/design/clean_mats_<ts>/
Schematics: 净材_*_v26.3.litematic (PCL 26.3). early-tech untouched.

## Residual
Still multiple plank/stone roles by design (wall vs roof vs floor vs foundation).
Chinese / fantasy / medieval still denser shells; shape still boxy.
