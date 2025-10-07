#!/usr/bin/env python3
"""Fix unescaped quotes in JSON string values"""
import json, re
from pathlib import Path

def fix_unescaped_quotes(text):
    """Escape quotes within JSON string values"""

    # Strategy: Find all string values and escape internal quotes
    # Match pattern: "key": "value with possible "quotes" inside"

    def escape_internal_quotes(match):
        key = match.group(1)
        value = match.group(2)
        # Escape quotes that are not already escaped
        fixed_value = re.sub(r'(?<!\\)"', r'\"', value)
        return f'"{key}": "{fixed_value}"'

    # Match JSON string key-value pairs
    # This regex finds: "key": "value..." where value may contain unescaped quotes
    pattern = r'"([^"]+)":\s*"((?:[^"\\]|\\.)*)(?<!\\)"'

    # Need a more robust approach - use line-by-line
    lines = text.split('\n')
    fixed_lines = []

    for line in lines:
        # Check if this is a JSON string value line
        if '": "' in line:
            # Find the value part
            match = re.match(r'(\s*"[^"]+"\s*:\s*)"(.*)"\s*([,}]?\s*)$', line)
            if match:
                prefix = match.group(1)
                value = match.group(2)
                suffix = match.group(3)

                # Escape unescaped quotes in value
                # Already escaped quotes will have a backslash before them
                fixed_value = re.sub(r'(?<!\\)"', r'\"', value)

                line = f'{prefix}"{fixed_value}"{suffix}'

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)

# Process all French chunks
for f in sorted(Path("work/chunks").glob("chunk_*.fr.json")):
    print(f"Fixing {f.name}...")
    text = f.read_text(encoding="utf-8")

    try:
        json.loads(text)
        print(f"  ✓ Already valid")
        continue
    except json.JSONDecodeError as e:
        print(f"  Fixing line {e.lineno}...")

    fixed = fix_unescaped_quotes(text)

    try:
        data = json.loads(fixed)
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ Fixed and saved")
    except json.JSONDecodeError as e:
        print(f"  ✗ Still invalid at line {e.lineno}: {e.msg}")
        # Save anyway for inspection
        Path(f.parent / f"{f.stem}.fixed.json").write_text(fixed, encoding="utf-8")
