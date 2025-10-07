#!/usr/bin/env python3
import re, sys, hashlib, json, unicodedata
from pathlib import Path

SRC = Path("src/article.en.md")
PREP = Path("work/article.prepped.en.md")
MAP  = Path("work/anchors_map.json")

md = SRC.read_text(encoding="utf-8")

def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\- ]+", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"\s+", "-", text)
    return text

lines = md.splitlines()
out = []
anchors = {}
i = 0
in_code = False

for ln in lines:
    if ln.strip().startswith("```"):
        in_code = not in_code
        out.append(ln)
        continue
    if in_code:
        out.append(ln)
        continue
    m = re.match(r"^(#{1,6})\s+(.+?)(\s*\{#([A-Za-z0-9\-\_]+)\}\s*)?$", ln)
    if m:
        level, title, _, existing = m.groups()
        anchor = existing or slugify(title)
        anchors[title] = anchor
        out.append(f"{level} {title} {{#{anchor}}}")
    else:
        out.append(ln)

# Stable block IDs per logical block separated by blank lines or headings/code fences
text = "\n".join(out)
blocks = []
buf = []
in_code = False
for ln in text.splitlines():
    if ln.strip().startswith("```"):
        if buf: blocks.append("\n".join(buf)); buf=[]
        in_code = not in_code
        blocks.append(ln)  # fence line as its own block
        continue
    if in_code:
        blocks.append(ln)
        continue
    if re.match(r"^#{1,6}\s", ln) or ln.strip()=="":
        if buf:
            blocks.append("\n".join(buf)); buf=[]
        blocks.append(ln)
    else:
        buf.append(ln)
if buf: blocks.append("\n".join(buf))

# assign IDs as SHA1(prefix) of trimmed content
final = []
for b in blocks:
    content = b.strip("\n")
    if not content:
        final.append(b); continue
    if content.startswith("```") or re.match(r"^#{1,6}\s", content):
        # no ID comment for the fence line itself or headings (heading already has anchor)
        final.append(b)
        continue
    h = hashlib.sha1(content.encode("utf-8")).hexdigest()[:10]
    final.append(f"<!-- id:{h} -->\n{b}")

PREP.parent.mkdir(parents=True, exist_ok=True)
PREP.write_text("\n".join(final), encoding="utf-8")
MAP.write_text(json.dumps({"anchors":anchors}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Prepared -> {PREP}")
