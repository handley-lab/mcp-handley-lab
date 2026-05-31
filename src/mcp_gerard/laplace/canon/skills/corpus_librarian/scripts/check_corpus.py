"""Global literature corpus completeness and consistency check.

Parses a corpus.bib in the corpus_librarian scheme and flags records that are not
yet well-formed: a missing required field, a status outside the allowed vocabulary,
a citekey off the deterministic pattern, or a duplicate key.

Stdlib-only, regex-based, in the structured-ledger style of the other laplace scripts.
The point is a gate that never blocks ingestion but never lets a malformed record pass
silently - degrade loudly, never guess.
"""

import os
import re
import sys

REQUIRED = ["title", "author", "year", "tldr", "claim", "status", "added", "scout"]
STATUS_VOCAB = {
    "unverified", "provisional", "borrowed", "contested", "established", "open-gap",
}
# partial:<restriction> is also allowed - matched separately.
PARTIAL = re.compile(r"^partial:\S+$", re.IGNORECASE)
PLACEHOLDER = re.compile(r"^\s*(tbd|todo|none|n/?a|pending|\?\?\?|)\s*$", re.IGNORECASE)
# Deterministic citekey: lowercase firstauthor + 4-digit year + title word.
CITEKEY = re.compile(r"^[a-z][a-z0-9]*\d{4}[a-z0-9]+$")


def read_safe(path):
    for enc in ("utf-8", "utf-16"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_records(text):
    """Return list of (citekey, {field: value}). Tolerant brace/quote field parse."""
    records = []
    # Each record starts at @type{key,
    for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", text):
        key = m.group(1).strip()
        start = m.end()
        # Body runs to the matching close brace of the entry (balanced scan).
        depth = 1
        i = m.start() + text[m.start():].index("{") + 1
        j = i
        while j < len(text) and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[start:j - 1]
        fields = {}
        # field = {value}  or  field = "value"  or  field = value,
        for fm in re.finditer(
            r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|[^,\n]+)", body
        ):
            name = fm.group(1).strip().lower()
            val = fm.group(2).strip().strip("{}").strip('"').strip()
            fields[name] = val
        records.append((key, fields))
    return records


def check(path):
    if not os.path.exists(path):
        print(f"Error: {path} not found.")
        return 2
    records = parse_records(read_safe(path))
    if not records:
        print("No bib records found. Expected '@type{key, ...}' entries.")
        return 2

    incomplete, bad_status, bad_key, dupes = [], [], [], []
    seen = {}
    for key, fields in records:
        seen[key] = seen.get(key, 0) + 1
        missing = [f for f in REQUIRED if f not in fields or PLACEHOLDER.match(fields.get(f, ""))]
        if missing:
            incomplete.append((key, missing))
        status = fields.get("status", "").strip().lower()
        if status and status not in STATUS_VOCAB and not PARTIAL.match(status):
            bad_status.append((key, status))
        if not CITEKEY.match(key):
            bad_key.append(key)
    dupes = [k for k, n in seen.items() if n > 1]

    n = len(records)
    print(f"# Corpus Check: {os.path.basename(path)}")
    print(
        f"Records: {n} | incomplete: {len(incomplete)} | "
        f"bad-status: {len(bad_status)} | off-pattern keys: {len(bad_key)} | "
        f"duplicate keys: {len(dupes)}"
    )
    print()
    if incomplete:
        print("## Incomplete records (missing required field)")
        for key, missing in incomplete:
            print(f"- `{key}`: missing {', '.join(missing)}")
        print()
    if bad_status:
        print("## Status outside the allowed vocabulary")
        for key, status in bad_status:
            print(f"- `{key}`: '{status}' (allowed: {', '.join(sorted(STATUS_VOCAB))}, partial:<r>)")
        print()
    if bad_key:
        print("## Citekeys off the deterministic pattern (firstauthor+year+word)")
        for key in bad_key:
            print(f"- `{key}`")
        print()
    if dupes:
        print("## Duplicate citekeys")
        for key in dupes:
            print(f"- `{key}` x{seen[key]}")
        print()
    clean = not (incomplete or bad_status or bad_key or dupes)
    if clean:
        print("Corpus is well-formed: all records complete, statuses valid, keys unique and on-pattern.")
    return 0 if clean else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_corpus.py <path_to_corpus.bib>")
        sys.exit(2)
    sys.exit(check(sys.argv[1]))
