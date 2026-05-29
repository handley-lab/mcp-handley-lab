"""Evidence ledger completeness check.

Parses an evidence_ledger.md in the standardised CLM scheme and flags records that
are not yet earned: a missing field, a placeholder, or a non-affirmative status.
Mirrors the structured-ledger style of the other mccaul-protocol scripts.
"""

import os
import re
import sys

FIELDS = ["Claim", "Derivation", "Literature", "Numerical", "Status"]
PLACEHOLDER = re.compile(r"\b(tbd|todo|none|n/?a|pending|\?\?\?)\b", re.IGNORECASE)
AFFIRMATIVE = re.compile(
    r"prov(ed|en)|supported|established|holds|correct|confirmed", re.IGNORECASE
)
# A weak status asserts a gap. Guard against 'no gap' / 'without gap'.
WEAK_STATUS = re.compile(
    r"(?<!no )(?<!without )\b(gap|unproved|conjectur\w*|assumed|assumption|heuristic|incomplete)\b",
    re.IGNORECASE,
)


def read_safe(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, encoding="utf-16") as f:
            return f.read()


def parse_records(text):
    """Return list of (id, title, {field: value})."""
    records = []
    # Split on '## <ID>: <title>' headers.
    chunks = re.split(r"^##\s+(\S+):\s*(.*)$", text, flags=re.MULTILINE)
    # chunks: [pre, id1, title1, body1, id2, title2, body2, ...]
    for i in range(1, len(chunks), 3):
        cid = chunks[i].strip()
        title = chunks[i + 1].strip()
        body = chunks[i + 2]
        fields = {}
        for fld in FIELDS:
            m = re.search(rf"\*\*{fld}:\*\*\s*(.+)", body)
            if m:
                fields[fld] = m.group(1).strip()
        records.append((cid, title, fields))
    return records


def check(path):
    if not os.path.exists(path):
        print(f"Error: {path} not found.")
        return 2
    records = parse_records(read_safe(path))
    if not records:
        print("No CLM records found. Expected '## <ID>: <title>' headers.")
        return 2

    incomplete, weak = [], []
    for cid, title, fields in records:
        missing = [f for f in FIELDS if f not in fields or not fields[f]]
        thin = [
            f
            for f in ("Literature", "Numerical")
            if f in fields and PLACEHOLDER.search(fields[f])
        ]
        status = fields.get("Status", "")
        status_weak = bool(WEAK_STATUS.search(status)) or not AFFIRMATIVE.search(status)
        if missing or thin:
            incomplete.append((cid, title, missing, thin))
        if status_weak:
            weak.append((cid, title, status))

    print(f"# Evidence Ledger Check: {os.path.basename(path)}")
    print(f"Records: {len(records)} | incomplete: {len(incomplete)} | weak-status: {len(weak)}")
    print()
    if incomplete:
        print("## Incomplete records (not yet earned)")
        for cid, title, missing, thin in incomplete:
            bits = []
            if missing:
                bits.append("missing " + ", ".join(missing))
            if thin:
                bits.append("placeholder in " + ", ".join(thin))
            print(f"- `{cid}` {title}: {'; '.join(bits)}")
        print()
    if weak:
        print("## Non-affirmative status (gap / conjecture / assumption)")
        for cid, title, status in weak:
            print(f"- `{cid}` {title}: {status}")
        print()
    if not incomplete and not weak:
        print("All claims are structurally complete and affirmatively supported.")
    return 0 if not incomplete else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_ledger.py <path_to_evidence_ledger.md>")
        sys.exit(2)
    sys.exit(check(sys.argv[1]))
