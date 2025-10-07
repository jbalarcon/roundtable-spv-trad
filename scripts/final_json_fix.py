#!/usr/bin/env python3
"""Final comprehensive JSON fix for French chunks"""
import json, re
from pathlib import Path

def fix_json_string_value(value_str):
    """
    Fix a JSON string value by:
    1. Escaping unescaped quotes
    2. Removing invalid escapes like \. \$ \% etc.
    """
    result = []
    i = 0
    while i < len(value_str):
        if value_str[i] == '\\':
            # Check what follows the backslash
            if i + 1 < len(value_str):
                next_char = value_str[i+1]
                # Valid JSON escapes: " \ / b f n r t u
                if next_char in '"\\/ bfnrtu':
                    # Keep valid escape
                    result.append(value_str[i:i+2])
                    i += 2
                else:
                    # Invalid escape like \. or \% - remove the backslash
                    result.append(next_char)
                    i += 2
            else:
                # Trailing backslash - remove it
                i += 1
        elif value_str[i] == '"':
            # Unescaped quote - escape it
            result.append('\\"')
            i += 1
        else:
            result.append(value_str[i])
            i += 1
    return ''.join(result)

def fix_json_file(filepath):
    """Fix JSON file"""
    lines = filepath.read_text(encoding="utf-8").split('\n')
    fixed_lines = []

    for line in lines:
        # Match lines with JSON string values
        match = re.match(r'^(\s*"[^"]+"\s*:\s*)"(.*)"\s*([,}]?\s*)$', line)
        if match:
            prefix, value, suffix = match.groups()
            fixed_value = fix_json_string_value(value)
            line = f'{prefix}"{fixed_value}"{suffix}'
        fixed_lines.append(line)

    return '\n'.join(fixed_lines)

# Process all French chunks
for f in sorted(Path("work/chunks").glob("chunk_*.fr.json")):
    print(f"Processing {f.name}...")

    original = f.read_text(encoding="utf-8")

    # Try to parse original first
    try:
        data = json.loads(original)
        print(f"  ✓ Already valid")
        # Reformat for consistency
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        continue
    except json.JSONDecodeError as e:
        print(f"  Fixing error at line {e.lineno}: {e.msg}")

    # Apply fixes
    fixed_text = fix_json_file(f)

    # Try to parse fixed version
    try:
        data = json.loads(fixed_text)
        # Save with proper formatting
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ Successfully fixed and saved")
    except json.JSONDecodeError as e:
        print(f"  ✗ Still invalid at line {e.lineno}: {e.msg}")
        # Save for inspection
        debug_file = f.parent / f"{f.stem}.debug.json"
        debug_file.write_text(fixed_text, encoding="utf-8")
        print(f"    Saved debug version to {debug_file.name}")
