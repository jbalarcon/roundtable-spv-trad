#!/usr/bin/env python3
"""
QA check for French translation chunks using Claude Sonnet 4.5
Validates: termbase compliance, DNT respect, French typography, structural integrity
"""
import json, sys
from pathlib import Path
from anthropic import Anthropic

CHUNKS_DIR = Path("work/chunks")
TERMBASE = Path("term/termbase.csv").read_text(encoding="utf-8")
DNT = Path("term/dnt.txt").read_text(encoding="utf-8")
REPORT = Path("work/qa_report_fr.json")

client = Anthropic()

QA_PROMPT = """You are a senior QA reviewer for legal-finance translations (EN→FR).

**Task**: Review this French translation chunk for:
1. **Termbase compliance** – verify key terms match the glossary
2. **DNT list respect** – ensure items in dnt.txt are NOT translated
3. **French typography** – check for U+202F before "; : ! ?", inside « … », space in "20 %", decimal comma
4. **Structural integrity** – all block IDs preserved, anchors intact, no dropped/added blocks
5. **Link preservation** – URLs and anchor IDs unchanged, only captions translated
6. **Table/list/code fence preservation** – structure maintained

**Reference files**:
<termbase>
{termbase}
</termbase>

<dnt>
{dnt}
</dnt>

<chunk>
{chunk}
</chunk>

**Output JSON schema**:
```json
{{
  "chunk_id": "string",
  "overall_status": "pass|warn|fail",
  "issues": [
    {{"type": "termbase|dnt|typography|structure|link|other", "severity": "error|warning", "detail": "string", "block_id": "string"}}
  ],
  "stats": {{"blocks_checked": 0, "errors": 0, "warnings": 0}},
  "notes": "optional summary"
}}
```

Return **only valid JSON**. No prose before or after.
"""

chunks_fr = sorted(CHUNKS_DIR.glob("chunk_*.fr.json"))
if not chunks_fr:
    print("No French chunks found", file=sys.stderr)
    sys.exit(1)

qa_results = []

for chunk_path in chunks_fr:
    chunk_data = json.loads(chunk_path.read_text(encoding="utf-8"))
    chunk_id = chunk_data.get("chunk_id", chunk_path.stem)

    print(f"QA checking {chunk_id}...", file=sys.stderr)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        temperature=0,
        messages=[{
            "role": "user",
            "content": QA_PROMPT.format(
                termbase=TERMBASE,
                dnt=DNT,
                chunk=json.dumps(chunk_data, ensure_ascii=False, indent=2)
            )
        }]
    )

    qa_text = response.content[0].text.strip()
    # Handle markdown code blocks if present
    if qa_text.startswith("```"):
        qa_text = "\n".join(qa_text.split("\n")[1:-1])

    qa_result = json.loads(qa_text)
    qa_results.append(qa_result)

    status = qa_result.get("overall_status", "unknown")
    errors = qa_result.get("stats", {}).get("errors", 0)
    warnings = qa_result.get("stats", {}).get("warnings", 0)

    print(f"  {chunk_id}: {status} ({errors} errors, {warnings} warnings)", file=sys.stderr)

REPORT.write_text(json.dumps({
    "qa_version": "v1",
    "model": "claude-sonnet-4-20250514",
    "chunks_reviewed": len(qa_results),
    "results": qa_results
}, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\nQA report written to {REPORT}", file=sys.stderr)

# Summary
total_errors = sum(r.get("stats", {}).get("errors", 0) for r in qa_results)
total_warnings = sum(r.get("stats", {}).get("warnings", 0) for r in qa_results)
print(f"Total: {total_errors} errors, {total_warnings} warnings", file=sys.stderr)

if total_errors > 0:
    sys.exit(1)
