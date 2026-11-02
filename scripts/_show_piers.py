from pathlib import Path
text = Path("src/app/look_harden.py").read_text(encoding="utf-8")
i = text.find("def place_wall_piers")
print(text[i:i+1800])
