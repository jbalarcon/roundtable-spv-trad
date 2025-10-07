#!/usr/bin/env python3
import re, json
from pathlib import Path

PREP = Path("work/article.prepped.en.md")
OUTDIR = Path("work/chunks")
OUTDIR.mkdir(parents=True, exist_ok=True)

text = PREP.read_text(encoding="utf-8")
parts = re.split(r"(?m)^##\s", text)
head = parts[0]
sections = parts[1:]

chunks = []
cur, cur_tokens = [], 0

def est_tokens(s):  # simple heuristic ~4 chars per token
    return max(1, int(len(s)/4))

for sec in sections:
    sec_md = "## " + sec
    t = est_tokens(sec_md)
    if cur_tokens + t > 7000 and cur:
        chunks.append("\n".join(cur))
        # add overlap: last ~1200 chars
        overlap = cur[-1][-1200:] if cur else ""
        cur = [overlap, sec_md]
        cur_tokens = est_tokens(overlap) + t
    else:
        cur.append(sec_md)
        cur_tokens += t

if cur:
    chunks.append("\n".join(cur))

for idx, ch in enumerate(chunks, start=1):
    meta = {
        "chunk_id": f"{idx:03d}",
        "source": "work/article.prepped.en.md",
        "approx_tokens": est_tokens(ch),
        "schema": "v1"
    }
    # convert to block array split by our <!-- id:... -->
    blocks=[]
    for raw in ch.split("\n"):
        blocks.append(raw)
    # merge lines into blocks delimited by <!-- id:... -->, headings, blank, code fences
    out=[]
    buf=[]
    in_code=False
    for ln in ch.splitlines():
        if ln.strip().startswith("```"):
            if buf: out.append("\n".join(buf)); buf=[]
            in_code = not in_code
            out.append(ln)
            continue
        if in_code:
            out.append(ln); continue
        if ln.startswith("<!-- id:") or re.match(r"^#{1,6}\s", ln) or ln.strip()=="":
            if buf: out.append("\n".join(buf)); buf=[]
            out.append(ln)
        else:
            buf.append(ln)
    if buf: out.append("\n".join(buf))

    # package as items with ids where present
    items=[]
    cur_id=None
    for el in out:
        m = re.match(r"^<!-- id:([0-9a-f]{10}) -->$", el.strip())
        if m:
            cur_id=m.group(1)
            continue
        md_type = "unknown"
        if re.match(r"^#{1,6}\s", el): md_type="heading"
        elif el.strip().startswith("```"): md_type="code_or_fence"
        elif "|" in el and "---" in el: md_type="table_candidate"
        elif el.strip().startswith(">"): md_type="blockquote"
        elif el.strip().startswith(("-", "*")) or re.match(r"^\d+\.\s", el.strip()): md_type="list_candidate"
        elif el.strip()=="":
            continue
        else:
            md_type="paragraph_or_misc"
        items.append({"id": cur_id or "", "md_type": md_type, "source_md": el})
        cur_id=None

    Path(OUTDIR/f"chunk_{idx:03d}.en.json").write_text(
        json.dumps({"meta":meta, "blocks":items}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

print(f"Wrote {len(chunks)} chunks to {OUTDIR}")
