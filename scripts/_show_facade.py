from pathlib import Path
text = Path("src/app/look_harden.py").read_text(encoding="utf-8")
i = text.find('"european"')
print(text[i-80:i+1100])
print("-----FANTASY-----")
j = text.find('"fantasy"')
print(text[j-40:j+900])
