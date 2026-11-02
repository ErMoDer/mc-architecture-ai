# -*- coding: utf-8 -*-
from pathlib import Path
p = Path("scripts/_long_fill2_session.py")
text = p.read_text(encoding="utf-8")
start = text.find("            try:\n                path = download_projection(bid,")
if start < 0:
    raise SystemExit("start not found")
end = text.find("            except Exception as e:\n                failed.append({\"id\": bid, \"error\": f\"index:{e}\"})", start)
if end < 0:
    raise SystemExit("end not found")
end = text.find("\n", end + 1)
# include full except block lines
end = text.find("\n", text.find("index:{e}", start)) 
# find end of that except block (next line after failed.append index)
marker = 'failed.append({"id": bid, "error": f"index:{e}"})'
end = text.find(marker, start)
if end < 0:
    raise SystemExit("marker not found")
end = text.find("\n", end) + 1
new = '''            row = {**it, **{k: detail.get(k) for k in ("primaryType", "styles", "tags", "name", "description", "projectionFileUrl", "downloadUrl", "width", "height", "depth", "blockCount") if detail.get(k) is not None}}
            try:
                dest = download_projection(row, ROOT / "data" / "raw" / "mcblock")
            except Exception as e:
                failed.append({"id": bid, "error": f"dl:{e}"})
                continue
            if not dest or not Path(dest).exists():
                failed.append({"id": bid, "error": "no_file"})
                continue
            try:
                feat = extract_reference_features(dest, skeleton_size=32, index_dir=index_dir, write=True, embed_block2vec=False)
                fid = feat.get("id")
                target = style if style != "western" else "western"
                override_style(fid, target, index_dir, "long_fill2 mcblock topup")
                feat_path = index_dir / f"{fid}.json"
                if feat_path.exists():
                    data = json.loads(feat_path.read_text(encoding="utf-8"))
                    data["mapped_terrain"] = data.get("mapped_terrain") or "flat"
                    feat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                man.append({"id": bid, "name": row.get("name"), "styles": row.get("styles") or [style], "file": str(Path(dest).relative_to(ROOT)), "_topup": "long_fill2"})
                man_path.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
                added.append({"id": bid, "fid": fid, "name": row.get("name")})
                known.add(bid)
                existing.add(fid)
            except Exception as e:
                failed.append({"id": bid, "error": f"ingest:{e}"})
'''
text = text[:start] + new + text[end:]
# remove bogus save_manifest noop
text = text.replace(
    '''        # persist manifest touch
        try:
            if man_path.exists():
                man = json.loads(man_path.read_text(encoding="utf-8"))
            save_manifest(man_path, man) if False else None
        except Exception:
            pass
''',
    "",
)
p.write_text(text, encoding="utf-8")
print("ok", start, end)
