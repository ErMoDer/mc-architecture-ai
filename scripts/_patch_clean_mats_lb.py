from pathlib import Path

SM = Path("src/app/scaffold_materials.py")
text = SM.read_text(encoding="utf-8")

# Force style fallback for accent / window_frame / load_bearing too (clean-house)
old = '''        # Clean-house: mass roles (wall/roof/floor/foundation) always use style
        # fallbacks so ref rainbow / junk (green_concrete, bone, acacia, tuff) cannot
        # paint the shell. Accent / frame / load_bearing may still take a clean ref.
        mass = role in ("wall", "roof", "foundation", "floor")
        if mass:
            info["source"] = "style_fallback_clean"
            if denied:
                info.setdefault("style_denied_refs", {})[role] = int(denied)
            pid = _resolve_id(name_to_id, list(fallbacks.get(role, ())))
            if pid is None:
                pid = _resolve_id(
                    name_to_id,
                    ["stone_bricks", "cobblestone", "oak_planks", "stone", "spruce_planks"],
                )
            return int(pid or 1)
        # Non-mass: allow clean ref if it scored well
        if best_id is not None and best_score >= 1.5:
            info["source"] = "reference+style"
            return int(best_id)
        if denied:
            info["source"] = "style_fallback_denied_ref"
        pid = _resolve_id(name_to_id, list(fallbacks.get(role, ())))
        if pid is None:
            pid = _resolve_id(
                name_to_id,
                ["stone_bricks", "cobblestone", "oak_planks", "stone", "spruce_planks"],
            )
        return int(pid or 1)'''

new = '''        # Clean-house: ALL roles use style fallbacks so ref rainbow / junk
        # (green_concrete, bone, acacia, tuff, odd load_bearing) cannot paint the build.
        info["source"] = "style_fallback_clean"
        if denied:
            info.setdefault("style_denied_refs", {})[role] = int(denied)
        pid = _resolve_id(name_to_id, list(fallbacks.get(role, ())))
        if pid is None:
            pid = _resolve_id(
                name_to_id,
                ["stone_bricks", "cobblestone", "oak_planks", "stone", "spruce_planks", "oak_log", "iron_block"],
            )
        return int(pid or 1)'''

assert old in text, "pick block missing"
text = text.replace(old, new, 1)

# Strengthen industrial accent deny for spruce plank-ish / green
old_ind_acc = '''        "accent": ("plank", "wool", "hay", "mud", "bone", "dirt", "moss", "green_concrete"),
        "window_frame": ("plank", "wool", "hay", "mud", "bone", "dirt"),
        "load_bearing": ("plank", "wool", "hay", "mud", "bone", "dirt", "moss"),
    },'''
# already have industrial block - expand load_bearing further
if '"load_bearing": ("plank", "wool", "hay", "mud", "bone", "dirt", "moss"),' in text:
    text = text.replace(
        '"load_bearing": ("plank", "wool", "hay", "mud", "bone", "dirt", "moss"),',
        '"load_bearing": ('
        '"plank", "wool", "hay", "mud", "bone", "dirt", "moss", "log",'
        '"green_concrete", "lime_concrete", "yellow_concrete", "orange_concrete",'
        '"red_concrete", "blue_concrete", "cyan_concrete", "purple_concrete",'
        '"magenta_concrete", "pink_concrete", "brown_concrete", "terracotta", "brick",'
        '),',
        1,
    )
    print("expanded load_bearing deny")

SM.write_text(text, encoding="utf-8")
print("scaffold_materials updated")
