#!/usr/bin/env python3
"""Fix French typography in the assembled markdown and chunks"""
import re, json
from pathlib import Path

NBSP = "\u00A0"  # U+00A0 non-breaking space
NNBSP = "\u202F"  # U+202F narrow non-breaking space

def fix_french_typography(text):
    """Apply French typography rules"""

    # Process line by line to avoid breaking URLs
    lines = text.split('\n')
    fixed_lines = []

    for line in lines:
        # Skip if line contains URL encoding (%)
        if '%20' in line or '%2' in line or '%3' in line:
            fixed_lines.append(line)
            continue

        # 1. Fix punctuation with U+202F before : ; ! ?
        # Replace any space (or no space) before these punctuation marks with U+202F
        line = re.sub(r'\s*([;:!?])', f'{NNBSP}\\1', line)

        # 2. Fix guillemets: « text » should have U+202F inside
        line = re.sub(r'«\s*', f'«{NNBSP}', line)
        line = re.sub(r'\s*»', f'{NNBSP}»', line)

        # 3. Fix percentage: should be number + U+202F + %
        line = re.sub(r'(\d+(?:,\d+)?)\s*%', f'\\1{NNBSP}%', line)

        # 4. Fix currency: number + U+202F + currency symbol
        line = re.sub(r'(\d+(?:[,.]\d+)?)\s*([€$£])', f'\\1{NNBSP}\\2', line)

        # 5. Fix large numbers: use U+202F for thousands separator (if spaces are used)
        line = re.sub(r'(\d{1,3})\s(\d{3})\b', f'\\1{NNBSP}\\2', line)

        # 6. Fix the SVP typo identified in QA
        line = re.sub(r'\bSVP\b', 'SPV', line)

        fixed_lines.append(line)

    return '\n'.join(fixed_lines)

# Fix the assembled markdown
print("Fixing French typography in assembled markdown...")
md_file = Path("out/fr/article.fr.md")
if md_file.exists():
    content = md_file.read_text(encoding="utf-8")
    fixed = fix_french_typography(content)
    md_file.write_text(fixed, encoding="utf-8")
    print(f"  ✓ Fixed {md_file}")

# Also fix the chunks so they're correct for future use
print("\nFixing French typography in chunks...")
for chunk_file in sorted(Path("work/chunks").glob("chunk_*.fr.json")):
    data = json.loads(chunk_file.read_text(encoding="utf-8"))

    for block in data.get("blocks", []):
        if "translation_md" in block:
            block["translation_md"] = fix_french_typography(block["translation_md"])

    chunk_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ Fixed {chunk_file.name}")

print("\nDone! French typography rules applied.")
