"""Evidence alignment: tier claim support and map it against goals.

Reads an evidence_ledger.md (the standardised CLM scheme) and classifies each
claim as strong / partial / weak. With --goals, reports per-goal coverage and the
gaps to close, including goals with no matching claim (prompts for research).
"""

import argparse
import os
import re

FIELDS = ["Claim", "Derivation", "Literature", "Numerical", "Status"]
PLACEHOLDER = re.compile(r"\b(tbd|todo|none|n/?a|pending|\?\?\?)\b", re.IGNORECASE)
AFFIRMATIVE = re.compile(
    r"prov(ed|en)|supported|established|holds|correct|confirmed", re.IGNORECASE
)
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
    records = []
    chunks = re.split(r"^##\s+(\S+):\s*(.*)$", text, flags=re.MULTILINE)
    for i in range(1, len(chunks), 3):
        cid, title, body = chunks[i].strip(), chunks[i + 1].strip(), chunks[i + 2]
        fields = {}
        for fld in FIELDS:
            m = re.search(rf"\*\*{fld}:\*\*\s*(.+)", body)
            if m:
                fields[fld] = m.group(1).strip()
        records.append({"id": cid, "title": title, "fields": fields})
    return records


def _has(fields, key):
    v = fields.get(key, "")
    return bool(v) and not PLACEHOLDER.search(v)


def tier(rec):
    f = rec["fields"]
    status = f.get("Status", "")
    affirmative = bool(AFFIRMATIVE.search(status)) and not WEAK_STATUS.search(status)
    lit, num = _has(f, "Literature"), _has(f, "Numerical")
    if affirmative and lit and num:
        return "strong"
    if not affirmative and not (lit or num):
        return "weak"
    return "partial"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger")
    ap.add_argument("--goals", default="", help="Comma-separated goal keywords/phrases.")
    args = ap.parse_args()

    if not os.path.exists(args.ledger):
        print(f"Error: {args.ledger} not found.")
        return 2
    records = parse_records(read_safe(args.ledger))
    for r in records:
        r["tier"] = tier(r)

    goals = [g.strip() for g in args.goals.split(",") if g.strip()]
    lines = [f"# Evidence Support Map: {os.path.basename(args.ledger)}", ""]
    counts = {t: sum(1 for r in records if r["tier"] == t) for t in ("strong", "partial", "weak")}
    lines.append(f"**Ledger:** {len(records)} claims - "
                 f"{counts['strong']} strong, {counts['partial']} partial, {counts['weak']} weak.")
    lines.append("")

    if goals:
        lines.append("## Coverage by goal")
        for g in goals:
            gl = g.lower()
            matched = [r for r in records
                       if gl in r["title"].lower() or gl in r["fields"].get("Claim", "").lower()]
            if not matched:
                lines.append(f"- **{g}**: NO matching claim - uncovered. Scout literature or derive.")
                continue
            strong = [r for r in matched if r["tier"] == "strong"]
            gaps = [r for r in matched if r["tier"] != "strong"]
            cov = f"{len(strong)}/{len(matched)} strong"
            lines.append(f"- **{g}**: {cov}.")
            for r in gaps:
                lines.append(f"    - gap [{r['tier']}] `{r['id']}` {r['title']}")
        lines.append("")

    lines.append("## All claims by tier")
    for t in ("weak", "partial", "strong"):
        tier_recs = [r for r in records if r["tier"] == t]
        if tier_recs:
            lines.append(f"### {t} ({len(tier_recs)})")
            for r in tier_recs:
                lines.append(f"- `{r['id']}` {r['title']}")
            lines.append("")

    report = "\n".join(lines)
    print(report)
    out = os.path.join(os.path.dirname(os.path.abspath(args.ledger)), "support_map.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\nSupport map written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
