# Window openings vs shell defects (Phase F)

## Problem

Tall / irregular refs (fantasy, western) leave many air cells on **weak perimeter
columns** (column mass 0–2: eaves tips, jagged footprint). detect_window_mask
treated those as windows → window_cells ~700+ while true glass_cells ~30.

## Policy

1. Only scan **wall-strength peri** columns (mass >= 3 when strict, else >= 2).
2. Strict styles (fantasy, western): keep rectangular mid ≤2×2 or repeating rect bands; seal 
ear_rect_mid.
3. Always report **window_cells** (kept openings on wall peri) and **glass_cells** (panes) separately.

## Wired

- look_harden.detect_window_mask(..., style=) + min_col_mass / wall_peri
- _STYLE_FACADE["fantasy"|"western"]["strict_window_openings"]=true
- look_harden_rules.json v5 notes
