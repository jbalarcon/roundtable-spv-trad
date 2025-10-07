Here is the end‑to‑end, cost‑aware workflow. Follow the steps in order.

---

## 0) Repository scaffold (one‑time)

1. **Clone and branch**

```bash
git clone https://github.com/jbalarcon/roundtable-spv-trad.git
cd roundtable-spv-trad
git checkout -b prep/normalization
```

2. **Folders and project files**

```bash
mkdir -p src term work/chunks out/fr out/de scripts
printf "# Roundtable SPV translation\n" > README.md
printf "root = true\n[*]\nend_of_line = lf\ninsert_final_newline = true\ncharset = utf-8\nindent_style = space\nindent_size = 2\n" > .editorconfig
```

3. **Place your files**

* Put the English article here: `src/article.en.md`
* Put your **termbase** here: `term/termbase.csv` with columns:

  * `source,en; target,fr; target,de; type(=preferred|forbid|dnt); note`
* Put your **do‑not‑translate list** here: `term/dnt.txt` (one term per line).

---

## 1) Prepare the markdown (normalize, anchor IDs, stable block IDs)

You will run three local scripts from Cursor’s terminal. Copy each file exactly, save, then run.

**`scripts/prepare_md.py`**

````python
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
````

Run:

```bash
python3 scripts/prepare_md.py
git add work/article.prepped.en.md work/anchors_map.json
git commit -m "prep: normalize headings and add stable block IDs"
```

---

## 2) Chunking for translation

**Rule**: split on `##` (H2). Target ≤ 6–8k tokens per chunk. Include 200–400 tokens of **overlap** containing definitions/examples.

**`scripts/chunk_md.py`**

````python
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
````

Run:

```bash
python3 scripts/chunk_md.py
git add work/chunks/*.en.json
git commit -m "chore: chunked source"
```

---

## 3) Translation pass in ChatGPT (GPT‑5 Pro) — **French first**

You will work **chunk by chunk**. For each `chunk_XXX.en.json`:

1. Open a new Chat in ChatGPT with **GPT‑5 Pro**.
2. Upload `term/termbase.csv`, `term/dnt.txt`, and the current `work/chunks/chunk_XXX.en.json`.
3. Paste the **FR translator prompt** below and send. Save the JSON reply as `work/chunks/chunk_XXX.fr.json`.

**FR translator prompt (paste exactly)**

> **System**
> You are a senior legal‑finance translator (EN→FR). Output must be **valid JSON** per the schema. Preserve Markdown structure and anchors. Keep “SPV” as primary term for French investors; mention “véhicule ad hoc” or “entité ad hoc” in the definition and 2–3 other strategic mentions. Respect the **do‑not‑translate** list. Apply French typography: non‑breaking thin space (U+202F) before `; : ! ?` and inside « … », number formatting with non‑breaking spaces for thousands and a **decimal comma**, and `20 %` with a non‑breaking space.
>
> **User**
> Translate EN→FR with these rules:
>
> * Keep all original link URLs and anchor IDs `{#...}`. Translate link captions only.
> * Preserve tables, code fences, lists, callouts, footnotes. Do not convert tables to text.
> * Keep block `id` values identical. Do not invent or drop blocks.
> * If a source block is a heading with an anchor, keep the anchor untouched.
> * Do not change order or content beyond translation. Statistics remain as in EN for now.
> * For **SPV vs SPAC**, keep the section but make it a short sidebar that clarifies differences for a French investor. No US‑only jargon without one‑line gloss.
> * Use the termbase and DNT: exact match priority > case‑insensitive > substring. Never translate items marked `dnt` or `forbid`.
>
> **JSON schema**
>
> ```json
> {
>   "chunk_id": "string",
>   "lang_target": "fr",
>   "blocks": [
>     {
>       "id": "string or empty",
>       "md_type": "heading|paragraph_or_misc|list_candidate|table_candidate|blockquote|code_or_fence|unknown",
>       "source_md": "string",
>       "translation_md": "string"
>     }
>   ],
>   "glossary_applied": ["array of term hits"],
>   "notes": "optional"
> }
> ```
>
> **Files provided**
>
> * `termbase.csv`
> * `dnt.txt`
> * `chunk_XXX.en.json`
>
> **Task**
> Return only the JSON. No prose.

Repeat for all chunks.

---

## 4) Cross‑check in Claude Code (Sonnet 4.5)
Note for Claude Code: Maybe we should use sub-agents here to manage context better?

For each pair `chunk_XXX.en.json` + `chunk_XXX.fr.json`:

1. Open Claude Code.
2. Upload both files plus `termbase.csv` and `dnt.txt`.
3. Paste the **QA prompt**. Save output as `work/chunks/chunk_XXX.fr.qa.json`.

**QA prompt (Claude Sonnet 4.5)**

> Audit the FR translation JSON for **terminology, DNT, numeric drift, anchor/format parity, table integrity, and legal clarity**. Return JSON only:
>
> ```json
> {
>   "chunk_id": "XXX",
>   "summary": {"severity":"ok|minor|major","counts":{"issues":0}},
>   "issues": [
>     {
>       "block_id":"id or ''",
>       "type":"terminology|dnt|number|anchor|format|table|register",
>       "severity":"minor|major",
>       "evidence":{"source_excerpt":"...", "target_excerpt":"..."},
>       "suggested_fix":"exact FR replacement or instruction"
>     }
>   ]
> }
> ```
>
> Rules:
>
> * **SPV** remains “SPV” in FR; mention “véhicule ad hoc” as defined, not as replacement.
> * Keep anchors `{#...}` identical. Keep all URLs untouched.
> * Numbers and `%` follow FR typography (decimal comma, `20 %`).
> * Tables must retain column/row counts and alignment pipes.
>   Return JSON only.

4. **Fix pass** in ChatGPT GPT‑5 Pro: upload the FR translation JSON and the QA JSON, then paste:

**FR fix‑apply prompt (GPT‑5 Pro)**

> Apply the provided QA `issues` to the translation JSON **minimally**. Preserve schema, anchors, block ids, and formatting. Return the **corrected translation JSON** only.

Save as `chunk_XXX.fr.fixed.json`. If no issues, copy the original.

---

## 5) Assemble FR markdown

**`scripts/assemble_md.py`**

```python
#!/usr/bin/env python3
import json, re
from pathlib import Path
IN = Path("work/chunks")
OUT = Path("out/fr/article.fr.md")
files = sorted(IN.glob("chunk_*.fr.fixed.json")) or sorted(IN.glob("chunk_*.fr.json"))

# de-duplicate by block id; keep first occurrence
seen=set()
md=[]
for f in files:
    data=json.loads(f.read_text(encoding="utf-8"))
    for b in data["blocks"]:
        tid=b.get("translation_md","").rstrip("\n")
        sid=b.get("source_md","")
        bid=b.get("id","")
        # Pass through headings and code fences as they come
        if bid and bid in seen: 
            continue
        if bid: seen.add(bid)
        md.append(tid if tid else sid)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(md)+"\n", encoding="utf-8")
print(f"Wrote {OUT}")
```

Run:

```bash
python3 scripts/assemble_md.py
```

---

## 6) French typography fixer

**`scripts/fix_typo_fr.py`**

````python
#!/usr/bin/env python3
import re
from pathlib import Path

IN = Path("out/fr/article.fr.md")
txt = IN.read_text(encoding="utf-8")

NBTHIN = "\u202F"
NBSP = "\u00A0"

# thin NBSP before ; : ! ?
txt = re.sub(r"\s*([;:!?])", NBTHIN + r"\1", txt)
# French « » with thin spaces inside
txt = re.sub(r'«\s*', '«'+NBTHIN, txt)
txt = re.sub(r'\s*»', NBTHIN+'»', txt)
# Percent spacing: 20 % -> 20 %
txt = re.sub(r'(\d)\s*%', r'\1'+NBTHIN+'%', txt)
# Decimal comma: 1.23 -> 1,23 (avoid URLs, code fences by skipping lines with http or ``` )
fixed=[]
in_code=False
for ln in txt.splitlines():
    if ln.strip().startswith("```"): in_code = not in_code; fixed.append(ln); continue
    if in_code or "http" in ln or "|" in ln: 
        fixed.append(ln); continue
    ln = re.sub(r'(\d)\.(\d)', r'\1,\2', ln)
    fixed.append(ln)

IN.write_text("\n".join(fixed)+"\n", encoding="utf-8")
print("FR typography fixed.")
````

Run:

```bash
python3 scripts/fix_typo_fr.py
git checkout -b fr/translation
git add out/fr/article.fr.md
git commit -m "feat(fr): initial FR translation with typography"
```

---

## 7) Structural reorder pass for FR (as requested)

Goal: France first, then Europe, then US for:

* **Common legal forms** section and its table.
* **Legal forms by country** section and the “comparison by region” table.
* **Best SPV platforms**: FR companies first, then EU, then others.
* Keep anchors. Keep SPV vs SPAC as a concise sidebar.

In ChatGPT GPT‑5 Pro:

1. Upload `out/fr/article.fr.md`.
2. Paste this **reorder prompt**:

> Reorder sections and specific tables per rules:
>
> * Move sections to the order: France → Europe → États‑Unis.
> * In affected tables, reorder **rows** and **columns** to the same France → Europe → États‑Unis order. Do not alter cell text except header labels.
> * Keep all anchors `{#...}` and existing link URLs unchanged.
> * Keep “SPV vs SPAC” as a short callout sidebar, not a main section.
>   Return full Markdown only.

Replace `out/fr/article.fr.md` with the returned file. Commit.

---

## 8) German pass (repeat quickly)
Note for Claude Code: I've added dnt-de.txt and termbase-de.csv in the term folder.

* Use **exactly the same pipeline**, but with the DE translator prompt.

**DE translator prompt (GPT‑5 Pro)**

> **System**
> You are a senior legal‑finance translator (EN→DE for Germany). Output must be **valid JSON** per schema. Keep “SPV” as primary term; mention “Zweckgesellschaft” in the definition and 2–3 strategic mentions. Respect DNT. Typography: German quotes „…“ (leave inside quotes unchanged if the English content uses legal names or code), decimal comma, dot for thousands, non‑breaking space before `%` as `20 %`. Avoid Switzerland/AT variants unless the text specifies those jurisdictions.
>
> **User**
> Same schema and rules as FR prompt above, with DE as `lang_target`. Keep anchors and URLs. Keep tables. Statistics unchanged. Return JSON only.

* Run the same **Claude QA** with German‑specific checks:

  * SPV kept as “SPV”. “Zweckgesellschaft” only as explanatory mention.
  * Decimal comma and `20 %`.
* Assemble to `out/de/article.de.md`.
* Optional reorder pass for DE identical to FR.

**German typography fixer** (optional; mirror FR script, but no « » rules; keep `20 %` and decimal comma conversion outside code/URLs).

---

## 9) Quality gates before publishing

Run a simple structural QA.

**`scripts/qa_check.py`**

````python
#!/usr/bin/env python3
import re, sys
from pathlib import Path

def check(path):
    txt = Path(path).read_text(encoding="utf-8")
    # anchors
    anchors = re.findall(r"\{#([A-Za-z0-9\-_]+)\}", txt)
    dup = [a for a in set(anchors) if anchors.count(a)>1]
    # code fence parity
    fences = txt.count("```")
    # footnotes pairing
    refs = set(re.findall(r"\[\^([^\]]+)\]", txt))
    defs = set(re.findall(r"(?m)^\[\^([^\]]+)\]:", txt))
    missing_defs = sorted(list(refs - defs))
    missing_refs = sorted(list(defs - refs))
    return {
        "file": path,
        "anchors_total": len(anchors),
        "anchor_duplicates": dup,
        "code_fences_mod2": fences % 2,
        "footnote_refs_wo_defs": missing_defs,
        "footnote_defs_wo_refs": missing_refs
    }

for f in ["out/fr/article.fr.md","out/de/article.de.md"]:
    if Path(f).exists():
        print(check(f))
````

Run:

```bash
python3 scripts/qa_check.py
```

If `code_fences_mod2` is `1`, fix the unmatched code fence in that file.

---

## 10) Publish

```bash
git add out/fr/article.fr.md out/de/article.de.md
git commit -m "feat: FR and DE translations (SPV primary term), reordered sections and tables"
git push origin fr/translation
git checkout -b de/translation
git push origin de/translation
# Open PRs in GitHub, request legal review from France-qualified counsel
```

---

## 11) Cost control tactics (no API keys, no coding skills assumed)

* **Chunk size**: keep chunks ≤ 7k tokens to avoid retries and reduce hallucinations.
* **Minimize rework**: run the termbase and DNT from the start. That eliminates back‑and‑forth.
* **Two‑model split**: GPT‑5 Pro for translation only. Claude Sonnet for QA only. No second full translation pass.
* **Calibrate on one chunk first**: run Chunk 001 through the full pipeline. Inspect time and visible token usage in ChatGPT/Claude. Adjust chunk size if needed.
* **Avoid schema drift**: always paste the schema verbatim so responses are one‑shot usable.

---

## 14) German specifics quick reference

* Primary term: **SPV**. Explanatory mentions: **Zweckgesellschaft**.
* Typography: „…“ quotes common in DE; decimal comma; `20 %`; ranges use en dash `–` with spaces: `10–20 %`.
* Localized legal references: keep as in EN first pass. Add DE/EU equivalents later if you decide.
