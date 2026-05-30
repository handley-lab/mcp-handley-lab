"""Identity drift check.

Reads a per-project identity manifest (the ID-NNN scheme) and a draft, and reports
which load-bearing identity elements - coined terms, framings, motifs, thesis - the
draft has kept or dropped. A draft missing a load-bearing element has drifted from
the paper's identity.
"""

import argparse
import os
import re

FIELDS = ["Kind", "Forms", "Role", "Status"]


def read_safe(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, encoding="utf-16") as f:
            return f.read()


def parse_manifest(text):
    records = []
    chunks = re.split(r"^##\s+(\S+):\s*(.*)$", text, flags=re.MULTILINE)
    for i in range(1, len(chunks), 3):
        cid, title, body = chunks[i].strip(), chunks[i + 1].strip(), chunks[i + 2]
        fields = {}
        for fld in FIELDS:
            m = re.search(rf"\*\*{fld}:\*\*\s*(.+)", body)
            if m:
                fields[fld] = m.group(1).strip()
        forms = [f.strip() for f in fields.get("Forms", title).split(",") if f.strip()]
        records.append(
            {
                "id": cid,
                "title": title,
                "kind": fields.get("Kind", ""),
                "forms": forms or [title],
                "role": fields.get("Role", ""),
                "load_bearing": "load-bearing" in fields.get("Status", "").lower(),
            }
        )
    return records


def _present(form, draft_lower):
    """Whitespace-flexible, case-insensitive whole-token-ish match."""
    pat = r"\b" + r"\s+".join(re.escape(w) for w in form.split()) + r"\b"
    return re.search(pat, draft_lower, re.IGNORECASE) is not None


def check(draft_path, manifest_path):
    for p in (draft_path, manifest_path):
        if not os.path.exists(p):
            print(f"Error: {p} not found.")
            return 2
    draft = read_safe(draft_path)
    records = parse_manifest(read_safe(manifest_path))
    if not records:
        print("No ID records found in manifest. Expected '## ID-NNN: title' headers.")
        return 2

    present, missing_lb, missing_opt = [], [], []
    for r in records:
        hit = any(_present(f, draft) for f in r["forms"])
        if hit:
            present.append(r)
        elif r["load_bearing"]:
            missing_lb.append(r)
        else:
            missing_opt.append(r)

    print(f"# Identity Check: {os.path.basename(draft_path)}")
    print(f"Elements: {len(records)} | present: {len(present)} | "
          f"missing load-bearing: {len(missing_lb)} | missing optional: {len(missing_opt)}")
    print()
    if missing_lb:
        print("## DRIFT - load-bearing identity dropped")
        for r in missing_lb:
            print(f"- `{r['id']}` {r['title']} [{r['kind']}]: {r['role']}")
        print()
    if missing_opt:
        print("## Missing (optional)")
        for r in missing_opt:
            print(f"- `{r['id']}` {r['title']}")
        print()
    if present:
        print("## Preserved")
        for r in present:
            print(f"- `{r['id']}` {r['title']}")
    if not missing_lb:
        print("\nNo identity drift: every load-bearing element is present.")
    return 1 if missing_lb else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()
    raise SystemExit(check(args.draft, args.manifest))
