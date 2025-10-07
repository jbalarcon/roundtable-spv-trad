#!/usr/bin/env python3
"""Assemble French markdown from translated chunks"""
import json
from pathlib import Path

CHUNKS_DIR = Path("work/chunks")
OUTPUT = Path("out/fr/article.fr.md")

# Load all French chunks in order
chunks = []
for chunk_file in sorted(CHUNKS_DIR.glob("chunk_*.fr.json")):
    data = json.loads(chunk_file.read_text(encoding="utf-8"))
    chunks.append(data)

# Assemble markdown from blocks
lines = []
for chunk in chunks:
    for block in chunk.get("blocks", []):
        translation = block.get("translation_md", "")
        if translation:
            lines.append(translation)

# Join with proper spacing
markdown = "\n".join(lines)

# Write output
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(markdown, encoding="utf-8")

print(f"Assembled {len(chunks)} chunks -> {OUTPUT}")
print(f"Total lines: {len(lines)}")
