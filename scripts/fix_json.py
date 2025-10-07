#!/usr/bin/env python3
"""Fix JSON formatting issues in French chunks"""
import json, re
from pathlib import Path

CHUNKS_DIR = Path("work/chunks")

for chunk_path in sorted(CHUNKS_DIR.glob("chunk_*.fr.json")):
    print(f"Fixing {chunk_path.name}...")

    # Read raw text
    text = chunk_path.read_text(encoding="utf-8")

    # Fix missing commas between objects in blocks array
    # Pattern: }\n    { (end of object, newline, start of object)
    # Should be: },\n    {
    text = re.sub(r'\}\n([ \t]+)\{', r'},\n\1{', text)

    # Try to parse
    try:
        data = json.loads(text)
        # Rewrite cleanly
        chunk_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"  ✓ Fixed and validated")
    except json.JSONDecodeError as e:
        print(f"  ✗ Still invalid: {e}")
        # Write the attempted fix anyway for manual review
        chunk_path.write_text(text, encoding="utf-8")

print("Done!")
