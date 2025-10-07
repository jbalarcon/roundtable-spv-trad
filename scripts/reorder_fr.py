#!/usr/bin/env python3
# Reorder sections and tables in out/fr/article.fr.md per plan step 7

import re
from pathlib import Path

FR_FILE = Path("out/fr/article.fr.md")


def split_table_row(row: str) -> list[str]:
    row = row.rstrip("\n")
    inner = row.strip().strip("|")
    # Keep empty cells by not filtering
    return [c.strip() for c in inner.split("|")]


def join_table_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def reorder_country_sections(txt: str) -> str:
    # Target region: H2 with legal-forms-for-spvs-by-country until next H2
    h2_pat = r"(?m)^##\s+.*\{#legal-forms-for-spvs-by-country\}\s*$"
    h2_match = re.search(h2_pat, txt)
    if not h2_match:
        return txt
    start = h2_match.start()
    next_h2 = re.search(r"(?m)^##\s+", txt[h2_match.end():])
    end = len(txt) if not next_h2 else h2_match.end() + next_h2.start()

    region = txt[start:end]

    # Find country subsections within region: headings with anchors {#spvs-in-...}
    h3_iter = list(re.finditer(r"(?m)^###\s+.*\{#spvs-in-[^}]+\}\s*$", region))
    if not h3_iter:
        return txt

    # Build blocks mapping from anchor suffix to block text
    blocks = []
    for i, m in enumerate(h3_iter):
        b_start = m.start()
        b_end = h3_iter[i+1].start() if i+1 < len(h3_iter) else len(region)
        block_text = region[b_start:b_end]
        anchor = re.search(r"\{#(spvs-in-[^}]+)\}", m.group(0)).group(1)
        blocks.append((anchor, block_text))

    # Determine new order
    order = [
        "spvs-in-france",
        "spvs-in-luxembourg",
        "spvs-in-germany",
        "spvs-in-spain",
        "spvs-in-the-united-kingdom",
        "spvs-in-the-united-states",
    ]
    # Preserve any unexpected blocks in original order after the known sequence
    known = {a for a, _ in blocks}
    unknown_blocks = [b for b in blocks if b[0] not in set(order)]
    ordered_blocks = [b for key in order for b in blocks if b[0] == key] + unknown_blocks

    # Reassemble region: keep everything before first country block and after last
    before = region[:h3_iter[0].start()]
    after = region[h3_iter[-1].end():]
    new_region = before + "".join(t for _, t in ordered_blocks) + after

    return txt[:start] + new_region + txt[end:]


def reorder_region_comparison_table(txt: str) -> str:
    # Locate the comparison table by heading anchor {#spv-structure-comparison-table-by-region}
    h3_pat = r"(?m)^###\s+.*\{#spv-structure-comparison-table-by-region\}\s*$"
    m = re.search(h3_pat, txt)
    if not m:
        return txt
    # From after heading, find consecutive table lines starting with '|'
    i = m.end()
    lines = txt.splitlines(True)  # keep newlines
    # Find line index for heading
    upto = 0
    for idx, l in enumerate(lines):
        upto += len(l)
        if upto >= m.end():
            hline_idx = idx
            break
    # Table starts at next non-empty line starting with '|'
    tstart = hline_idx + 1
    while tstart < len(lines) and not lines[tstart].lstrip().startswith("|"):
        tstart += 1
    if tstart >= len(lines) or not lines[tstart].lstrip().startswith("|"):
        return txt
    # Collect table block
    tend = tstart
    while tend < len(lines) and lines[tend].lstrip().startswith("|"):
        tend += 1
    table_block = lines[tstart:tend]
    if len(table_block) < 3:
        return txt

    header = split_table_row(table_block[0])
    align = split_table_row(table_block[1])
    rows = [split_table_row(r) for r in table_block[2:]]

    # Expected header names and desired order (excluding first descriptor column)
    name_to_idx = {name: i for i, name in enumerate(header)}
    # Ensure we have required names
    required = ["", "États‑Unis", "Royaume‑Uni", "France", "Allemagne", "Luxembourg", "Espagne"]
    if not all(n in name_to_idx for n in required if n != ""):
        # Try fallback with ASCII hyphen variants
        return txt

    desired = ["France", "Luxembourg", "Allemagne", "Royaume‑Uni", "Espagne", "États‑Unis"]

    # Build new header
    new_header = [header[0]] + [header[name_to_idx[n]] for n in desired]
    new_align = [align[0]] + [align[name_to_idx[n]] for n in desired]
    new_rows = []
    for r in rows:
        if len(r) < len(header):
            new_rows.append(r)
            continue
        first = r[0]
        new_r = [first] + [r[name_to_idx[n]] for n in desired]
        new_rows.append(new_r)

    # Write back table
    out_lines = [join_table_row(new_header) + "\n", join_table_row(new_align) + "\n"]
    out_lines += [join_table_row(r) + "\n" for r in new_rows]

    new_txt = "".join(lines[:tstart] + out_lines + lines[tend:])
    return new_txt


def reorder_common_legal_forms_table(txt: str) -> str:
    # Locate the common legal forms section table under {#common-legal-forms-of-spvs}
    h3_pat = r"(?m)^###\s+.*\{#common-legal-forms-of-spvs\}\s*$"
    m = re.search(h3_pat, txt)
    if not m:
        return txt
    # Find table lines following the heading (header + align + rows until a blank line or next heading)
    lines = txt.splitlines(True)
    upto = 0
    for idx, l in enumerate(lines):
        upto += len(l)
        if upto >= m.end():
            hline_idx = idx
            break
    # Table starts when we hit a line starting with '|'
    tstart = hline_idx + 1
    while tstart < len(lines) and not lines[tstart].lstrip().startswith("|"):
        tstart += 1
    if tstart >= len(lines) or not lines[tstart].lstrip().startswith("|"):
        return txt
    tend = tstart
    while tend < len(lines) and lines[tend].lstrip().startswith("|"):
        tend += 1
    table_block = lines[tstart:tend]
    if len(table_block) < 3:
        return txt

    header = table_block[0]
    align = table_block[1]
    body = table_block[2:]

    # Map first-cell labels to rows
    def first_cell(label_line: str) -> str:
        cells = split_table_row(label_line)
        return cells[0]

    rows_by_key = {first_cell(r): r for r in body}

    # Determine keys present (bold formatting preserved)
    # Keys we want in target order
    target_order = [
        "**Société Civile (SC)**",
        "**Structures de fonds**",
        "**Corporation / Limited Co.**",
        "**Limited Partnership (LP)**",
        "**Trusts**",
        "**Structures «\u202FSeries\u202F»/ségréguées**",
        "**Limited Liability Company (LLC)**",
    ]

    # Fallback for narrow spaces variants in the "Series" row
    series_keys = [k for k in rows_by_key.keys() if "Structures" in k and "Series" in k]
    if series_keys:
        # normalize target key to the exact present key
        target_order[5] = series_keys[0]

    new_body = []
    for key in target_order:
        if key in rows_by_key:
            new_body.append(rows_by_key[key])
    # Append any other rows that were not matched, in original order
    for k, r in rows_by_key.items():
        if r not in new_body:
            new_body.append(r)

    new_table = [header, align] + new_body
    new_txt = "".join(lines[:tstart] + new_table + lines[tend:])
    return new_txt


def reorder_provider_sections_and_table(txt: str) -> str:
    # Locate provider section by H2 heading '## Quelle est la meilleure plateforme SPV'
    h2_pat = r"(?m)^##\s+.*\{#whats-the-best-spv-platform\}\s*$"
    m = re.search(h2_pat, txt)
    if not m:
        return txt
    start = m.start()
    next_h2 = re.search(r"(?m)^##\s+", txt[m.end():])
    end = len(txt) if not next_h2 else m.end() + next_h2.start()
    region = txt[start:end]

    # Identify provider subsections (### <name> {#anchor}) until the comparison table heading
    prov_iter = list(re.finditer(r"(?m)^###\s+.*\{#(angellist|carta|roundtable|bunch|allocations|sydecar|flow-apex|odin|securitize)\}\s*$", region))
    if prov_iter:
        # Capture intro part before first provider, and everything after last provider remains
        before = region[:prov_iter[0].start()]
        after_from = prov_iter[-1].end()
        # The last provider's content goes until next H3 (comparison table) or end of region
        next_h3 = re.search(r"(?m)^###\s+.*\{#spv-provider-comparison-table\}\s*$", region[after_from:])
        # If we didn't find comparison heading by anchor, fallback to heading text
        if not next_h3:
            next_h3 = re.search(r"(?m)^###\s+Tableau comparatif des prestataires SPV\s*\{#spv-provider-comparison-table\}\s*$", region[after_from:])
        # Or generic heading start
        next_h3_generic = re.search(r"(?m)^###\s+", region[after_from:])
        last_block_end = after_from + (next_h3.start() if next_h3 else (next_h3_generic.start() if next_h3_generic else len(region[after_from:])))

        # Build blocks for each provider
        blocks = []
        for i, pm in enumerate(prov_iter):
            b_start = pm.start()
            b_end = prov_iter[i+1].start() if i+1 < len(prov_iter) else last_block_end
            block_text = region[b_start:b_end]
            anchor = re.search(r"\{#([a-z\-]+)\}", pm.group(0)).group(1)
            blocks.append((anchor, block_text))

        # Desired order: Roundtable, bunch, Odin, then US/others
        desired = ["roundtable", "bunch", "odin", "angellist", "carta", "flow-apex", "allocations", "sydecar", "securitize"]
        ordered_blocks = [b for key in desired for b in blocks if b[0] == key] + [b for b in blocks if b[0] not in set(desired)]

        # Everything after providers (comparison heading + table + rest)
        tail = region[last_block_end:]
        region = before + "".join(t for _, t in ordered_blocks) + tail

    # Reorder provider comparison table rows under heading {#spv-provider-comparison-table}
    h3_cmp = re.search(r"(?m)^###\s+.*\{#spv-provider-comparison-table\}\s*$", region)
    if not h3_cmp:
        # fallback on text without explicit anchor line (use the text shown in article)
        h3_cmp = re.search(r"(?m)^###\s+Tableau comparatif des prestataires SPV\s*\{#spv-provider-comparison-table\}\s*$", region)
    if h3_cmp:
        lines = region.splitlines(True)
        # index of the heading line
        upto = 0
        for idx, l in enumerate(lines):
            upto += len(l)
            if upto >= h3_cmp.end():
                hline_idx = idx
                break
        # Find table start
        tstart = hline_idx + 1
        while tstart < len(lines) and not lines[tstart].lstrip().startswith("|"):
            tstart += 1
        if tstart < len(lines) and lines[tstart].lstrip().startswith("|"):
            tend = tstart
            while tend < len(lines) and lines[tend].lstrip().startswith("|"):
                tend += 1
            table_block = lines[tstart:tend]
            if len(table_block) >= 3:
                header = table_block[0]
                align = table_block[1]
                body = table_block[2:]

                # Map provider name to complete row text for reordering
                def extract_name(row_line: str) -> str:
                    cells = split_table_row(row_line)
                    # First cell contains **[Name](link)**; strip markdown to get Name
                    first = cells[0]
                    m = re.search(r"\*\*\[([^\]]+)\]", first)
                    return m.group(1) if m else first

                by_name = {extract_name(r): r for r in body}
                order_names = [
                    "Roundtable",
                    "bunch",
                    "Odin",
                    "AngelList",
                    "Carta",
                    "Flow (Apex)",
                    "Allocations",
                    "Sydecar",
                    "Securitize",
                ]
                new_body = []
                for nm in order_names:
                    if nm in by_name:
                        new_body.append(by_name[nm])
                for nm, row in by_name.items():
                    if row not in new_body:
                        new_body.append(row)

                table_out = [header, align] + new_body
                region = "".join(lines[:tstart] + table_out + lines[tend:])

    return txt[:start] + region + txt[end:]


def main():
    txt = FR_FILE.read_text(encoding="utf-8")
    orig = txt
    txt = reorder_common_legal_forms_table(txt)
    txt = reorder_country_sections(txt)
    txt = reorder_region_comparison_table(txt)
    txt = reorder_provider_sections_and_table(txt)

    if txt != orig:
        FR_FILE.write_text(txt, encoding="utf-8")
        print("Reordered FR article per step 7.")
    else:
        print("No changes applied.")


if __name__ == "__main__":
    main()


