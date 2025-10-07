#!/usr/bin/env python3
"""Repair malformed JSON from ChatGPT translation output"""
import json, re
from pathlib import Path

def repair_json_string(text):
    """Fix common JSON issues from ChatGPT output"""

    # Fix escaped backslash followed by escaped quote: \\" -> \"
    text = text.replace(r'\\\"', r'\"')

    # Fix unescaped quotes in values (but not at string boundaries)
    # This is tricky - we need to escape quotes within string values

    # Try to parse and return if successful
    try:
        return json.loads(text)
    except:
        pass

    # Alternative: use ast.literal_eval-style repair
    # Fix trailing backslash before quotes in string values
    text = re.sub(r'\\"\s*,', r'",', text)

    try:
        return json.loads(text)
    except Exception as e:
        print(f"Still can't parse: {e}")
        return None

# Process all French chunks
for chunk_file in sorted(Path("work/chunks").glob("chunk_*.fr.json")):
    print(f"Repairing {chunk_file.name}...")

    raw = chunk_file.read_text(encoding="utf-8")

    # Try direct parse first
    try:
        data = json.loads(raw)
        print(f"  ✓ Already valid")
        continue
    except json.JSONDecodeError as e:
        print(f"  ✗ Invalid: {e}")

    # Try repair
    repaired = repair_json_string(raw)
    if repaired:
        chunk_file.write_text(
            json.dumps(repaired, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"  ✓ Repaired and saved")
    else:
        print(f"  ✗ Could not repair - manual fix needed")
        # Show problematic line
        lines = raw.split('\n')
        try:
            json.loads(raw)
        except json.JSONDecodeError as e:
            if e.lineno and e.lineno <= len(lines):
                print(f"    Line {e.lineno}: {lines[e.lineno-1][:100]}")
