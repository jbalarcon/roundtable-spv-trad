#!/usr/bin/env python3
"""Manually fix known JSON issues in French chunks"""
import re
from pathlib import Path

def smart_escape_quotes(value_str):
    """Escape quotes in a JSON string value, but preserve valid escapes"""
    result = []
    i = 0
    while i < len(value_str):
        if value_str[i] == '\\':
            # This is an escape sequence - keep it as-is
            if i + 1 < len(value_str):
                result.append(value_str[i:i+2])
                i += 2
            else:
                result.append(value_str[i])
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
    """Fix JSON file with unescaped quotes in string values"""
    lines = filepath.read_text(encoding="utf-8").split('\n')
    fixed_lines = []

    for line in lines:
        # Match lines with JSON string values: "key": "value",
        match = re.match(r'^(\s*"[^"]+"\s*:\s*)"(.*)"\s*([,}]?\s*)$', line)
        if match:
            prefix, value, suffix = match.groups()
            fixed_value = smart_escape_quotes(value)
            line = f'{prefix}"{fixed_value}"{suffix}'
        fixed_lines.append(line)

    return '\n'.join(fixed_lines)

# Process files
import json

for f in sorted(Path("work/chunks").glob("chunk_*.fr.json")):
    print(f"Processing {f.name}...")

    fixed_text = fix_json_file(f)

    try:
        data = json.loads(fixed_text)
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ Fixed and validated")
    except json.JSONDecodeError as e:
        print(f"  ✗ Error at line {e.lineno}: {e.msg}")
