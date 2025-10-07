#!/usr/bin/env python3
"""Final quality gates for French translation"""
import re, sys
from pathlib import Path

NBSP = "\u00A0"
NNBSP = "\u202F"

def check_file(filepath):
    """Run quality checks on a file"""
    text = filepath.read_text(encoding="utf-8")
    issues = []

    # Check 1: French punctuation should have U+202F
    bad_punct = re.findall(r'[^\u202F]([;:!?])', text)
    if bad_punct:
        issues.append(f"Found {len(bad_punct)} punctuation marks without U+202F")

    # Check 2: Guillemets should have U+202F
    bad_guillemets = re.findall(r'«[^\u202F]|[^\u202F]»', text)
    if bad_guillemets:
        issues.append(f"Found {len(bad_guillemets)} guillemets without U+202F")

    # Check 3: Percentages should have U+202F (but not in URLs)
    # Only check percentages that are standalone (word boundary after %)
    bad_percent = re.findall(r'\d+[^\u202F]%(?=\s|$|[,\.;])', text)
    if bad_percent:
        issues.append(f"Found {len(bad_percent)} percentages without U+202F")

    # Check 4: No SVP typos (should be SPV)
    svp_typos = re.findall(r'\bSVP\b', text)
    if svp_typos:
        issues.append(f"CRITICAL: Found {len(svp_typos)} 'SVP' typos (should be 'SPV')")

    # Check 5: Anchors are preserved
    anchors = re.findall(r'\{#[a-z0-9\-]+\}', text)
    if len(anchors) < 10:
        issues.append(f"WARNING: Only {len(anchors)} anchors found (expected many more)")

    # Check 6: Links are present
    links = re.findall(r'\[.+?\]\(.+?\)', text)
    if len(links) < 20:
        issues.append(f"WARNING: Only {len(links)} links found (expected many more)")

    return issues

# Run checks
print("=== FINAL QA CHECKS ===\n")

checks = [
    ("French markdown", Path("out/fr/article.fr.md")),
]

all_pass = True
for name, filepath in checks:
    if not filepath.exists():
        print(f"✗ {name}: FILE NOT FOUND")
        all_pass = False
        continue

    issues = check_file(filepath)
    if issues:
        print(f"✗ {name}:")
        for issue in issues:
            print(f"  - {issue}")
        all_pass = False
    else:
        print(f"✓ {name}: PASS")

print("\n" + "="*50)
if all_pass:
    print("✓ ALL CHECKS PASSED")
    sys.exit(0)
else:
    print("✗ SOME CHECKS FAILED - review issues above")
    sys.exit(1)
