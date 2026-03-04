"""Core notmuch email functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

import re
import subprocess

from mcp_handley_lab.email.common import _list_accounts
from mcp_handley_lab.email.notmuch.tool import (
    Contact,
    EmailContent,
    MoveResult,
    SearchResult,
    TagResult,
    _find_contacts,
    _list_folders,
    _list_tags,
    _move_emails,
    _resolve_id_in_query,
    _resolve_message_id,
    _search_emails,
    _show_email,
    _tag_email,
)


def _notmuch_count(query: str, include_excluded: bool = False) -> int:
    """Count emails matching query without fetching. Returns -1 on error."""
    cmd = ["notmuch", "count"]
    if include_excluded:
        cmd.append("--exclude=false")
    cmd.append(query)
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return -1


# -- Folder family detection and expansion --

_folder_families_cache: dict[str, list[str]] | None = None


def _build_folder_families(folders: list[str]) -> dict[str, list[str]]:
    """Group folders by year-suffix (.DDDD) into families.

    Only 4-digit year suffixes qualify (e.g. .2024). Topic suffixes like
    .PhD or .CATAM are organizational, not temporal, and are excluded.
    The base folder need not exist in the folder list.
    """
    year_suffix = re.compile(r"^(.+)\.(\d{4})$")
    families: dict[str, list[str]] = {}
    folder_set = set(folders)

    for folder in folders:
        m = year_suffix.match(folder)
        if m:
            base = m.group(1)
            families.setdefault(base, []).append(folder)

    # Include the base folder itself if it exists
    for base in list(families):
        if base in folder_set and base not in families[base]:
            families[base].insert(0, base)

    # Remove singletons — a family needs 2+ members
    return {
        base: sorted(members, key=lambda f: (f != base, f))
        for base, members in families.items()
        if len(members) >= 2
    }


def _get_folder_families() -> dict[str, list[str]]:
    """Cached folder family detection. Computed once per process."""
    global _folder_families_cache
    if _folder_families_cache is None:
        _folder_families_cache = _build_folder_families(_list_folders())
    return _folder_families_cache


# -- Query parsing state machine --


def _parse_query_tokens(query: str):
    """Yield (start, end, field, value, depth, negated) for field:value tokens.

    Tracks paren depth and quote state. Only yields tokens at depth 0.
    At depth > 0: skips quoted strings to avoid counting parens inside quotes.
    At depth 0: quotes are consumed only as part of field:value token parsing.
    """
    i = 0
    n = len(query)
    depth = 0
    field_pattern = re.compile(
        r"(folder|from|to|date|subject|tag|id|mid|cc|bcc):", re.IGNORECASE
    )

    def _skip_quote(pos: int) -> int:
        """Skip past a matched quoted string. Returns new position."""
        close = query.find('"', pos + 1)
        return (close + 1) if close != -1 else pos + 1

    while i < n:
        ch = query[i]

        # Track paren depth (quotes handled per-depth below)
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            i += 1
            continue

        if depth > 0:
            # Skip quoted strings to avoid counting parens inside quotes
            if ch == '"':
                i = _skip_quote(i)
            else:
                i += 1
            continue

        # At depth 0 — try to match field:value tokens first
        m = field_pattern.match(query, i)
        if not m:
            # Not a field token — skip quoted strings if present
            if ch == '"':
                i = _skip_quote(i)
            else:
                i += 1
            continue

        field = m.group(1).lower()
        val_start = m.end()

        # Check negation: preceding '-' or standalone NOT
        negated = False
        if i > 0 and query[i - 1] == "-":
            negated = True
        else:
            before = query[:i].rstrip()
            if len(before) >= 3:
                tokens = before.split()
                if tokens and tokens[-1].upper() == "NOT":
                    negated = True

        # Parse value (quoted or bare)
        if val_start < n and query[val_start] == '"':
            # Quoted value — find closing quote (same mechanism as above)
            close = query.find('"', val_start + 1)
            if close == -1:
                close = n
            else:
                close += 1  # include the closing quote
            value = query[val_start:close]
            end = close
        else:
            # Bare value — extends to next whitespace or ) at depth 0
            end = val_start
            while end < n and query[end] not in (" ", "\t", "\n", ")"):
                end += 1
            value = query[val_start:end]

        yield (i, end, field, value, depth, negated)
        i = end

    return


def _expand_folder_families(query: str, families: dict[str, list[str]]) -> str:
    """Expand folder:BASE to (folder:"BASE" OR folder:"BASE.2024" OR ...).

    Only expands top-level (depth 0), non-negated folder: tokens whose value
    matches a family base. Already-expanded tokens (inside parens) are skipped.
    """
    if not families:
        return query

    replacements = []  # (start, end, replacement_str)
    for start, end, field, value, _depth, negated in _parse_query_tokens(query):
        if field != "folder" or negated:
            continue
        # Unquote to get the raw folder name
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            raw = value[1:-1]
        else:
            raw = value
        if raw not in families:
            continue
        members = families[raw]
        parts = " OR ".join(f'folder:"{m}"' for m in members)
        replacements.append((start, end, f"({parts})"))

    if not replacements:
        return query

    # Apply replacements in reverse order to preserve positions
    result = query
    for s, e, repl in reversed(replacements):
        result = result[:s] + repl + result[e:]
    return result


def _extract_query_clauses(query: str) -> dict:
    """Extract top-level field:value clauses from a notmuch query.

    Returns {"folder": [...], "from": [...], "to": [...], "date": [...],
             "remainder": "..."} with all field values at depth 0.
    """
    clauses: dict[str, list[str]] = {
        "folder": [],
        "from": [],
        "to": [],
        "date": [],
    }
    spans_to_remove = []

    for start, end, field, value, _depth, negated in _parse_query_tokens(query):
        if field in clauses and not negated:
            clauses[field].append(value)
            spans_to_remove.append((start, end))

    # Build remainder by removing extracted spans
    remainder = query
    for s, e in sorted(spans_to_remove, reverse=True):
        remainder = remainder[:s] + remainder[e:]
    remainder = re.sub(r"\s+", " ", remainder).strip()
    # Clean up orphaned boolean operators
    remainder = re.sub(r"\b(and|or)\s*$", "", remainder, flags=re.IGNORECASE).strip()
    remainder = re.sub(r"^\s*(and|or)\b", "", remainder, flags=re.IGNORECASE).strip()

    return {**clauses, "remainder": remainder}


def _relax_query(query: str, clauses: dict, step: str) -> str:
    """Remove or rewrite a specific constraint type from the query.

    Uses span-based removal via _parse_query_tokens, not str.replace.
    The clauses parameter is only for eligibility checking.
    """
    spans_to_modify = []  # (start, end, replacement_or_None)

    for start, end, field, value, _depth, negated in _parse_query_tokens(query):
        if negated:
            continue  # only relax positive constraints
        if step in ("folder", "to", "date") and field == step:
            spans_to_modify.append((start, end, None))  # remove
        elif step == "from_domain" and field == "from":
            # Only apply to bare (unquoted) email addresses with single @
            if value.startswith('"'):
                continue
            if " " in value or value.count("@") != 1:
                continue
            _, domain = value.split("@", 1)
            spans_to_modify.append((start, end, f"from:{domain}"))

    if not spans_to_modify:
        return query

    result = query
    for s, e, repl in sorted(spans_to_modify, reverse=True):
        if repl is None:
            result = result[:s] + result[e:]
        else:
            result = result[:s] + repl + result[e:]

    # Clean whitespace and orphaned operators
    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"\b(and|or)\s*$", "", result, flags=re.IGNORECASE).strip()
    result = re.sub(r"^\s*(and|or)\b", "", result, flags=re.IGNORECASE).strip()
    return result


def _auto_relax(
    query: str,
    limit: int,
    offset: int,
    include_excluded: bool,
    mode: str,
    save_to: str = "",
    segment_quotes: bool = False,
) -> tuple[list, str | None]:
    """Try relaxing query constraints to find results. Returns (results, diagnostic)."""
    clauses = _extract_query_clauses(query)
    families = _get_folder_families()
    for step in ["folder", "to", "date", "from_domain"]:
        check_key = "from" if step == "from_domain" else step
        if not clauses.get(check_key):
            continue
        relaxed = _relax_query(query, clauses, step)
        if relaxed == query:
            continue  # transformation was a no-op
        # Apply folder expansion to relaxed query for consistency
        expanded = _expand_folder_families(relaxed, families)
        count = _notmuch_count(expanded, include_excluded)
        if count > 0:
            if mode == "headers":
                results = _search_emails(expanded, limit, offset, include_excluded)
            else:
                results = _show_email(
                    expanded,
                    mode=mode,
                    limit=limit,
                    include_excluded=include_excluded,
                    save_to=save_to,
                    segment_quotes=segment_quotes,
                )
            if not results:
                continue  # count/fetch mismatch
            label = (
                "Relaxed from: to domain"
                if step == "from_domain"
                else f"Removed {step} constraint"
            )
            diag = f"0 results for original query. {label} → {count} results."
            return results, diag
    return [], None


def _normalize_folder_query(query: str) -> str:
    """Normalize partially-quoted folder: terms in notmuch queries.

    Rewrites e.g. folder:Account/"Sent Items.2024" to folder:"Account/Sent Items.2024".
    Already fully-quoted values are left unchanged.
    """
    pattern = re.compile(
        r'folder:("(?:[^"\\]|\\.)*"|[^\s\)\]\}"]+(?:"(?:[^"\\]|\\.)*")?)'
    )

    def _rewrite(match: re.Match) -> str:
        value = match.group(1)
        if value.startswith('"') and value.endswith('"'):
            return match.group(0)
        clean = value.replace('"', "")
        return f'folder:"{clean}"'

    return pattern.sub(_rewrite, query)


def read(
    query: str = "",
    limit: int = 100,
    offset: int = 0,
    include_excluded: bool = False,
    mode: str = "headers",
    save_attachments_to: str = "",
    list_type: str = "",
    max_results: int = 10,
    segment_quotes: bool = False,
    _diagnostics: list[str] | None = None,
) -> list[SearchResult] | list[EmailContent] | list[str] | list[Contact]:
    """Search emails using notmuch query language.

    Args:
        query: A valid notmuch search query. Examples: 'from:boss', 'tag:inbox and date:2024-01-01..'.
            Supports abbreviated message IDs (e.g., 'id:CAHgsCeb' resolves to full ID if unique).
        limit: The maximum number of message IDs to return.
        offset: Number of results to skip for pagination.
        include_excluded: Include emails with excluded tags (spam, deleted) that are normally hidden.
        mode: Rendering mode: 'headers' (metadata only), 'summary' (first 2000 chars),
            or 'full' (complete optimized content).
        save_attachments_to: Directory to save email body and attachments to.
        list_type: For listing: 'tags', 'folders', or 'accounts'. When set, ignores query.
        max_results: For find_contacts: maximum results to return.
        segment_quotes: For full mode: include quote/signature segmentation in response.
        _diagnostics: If provided, diagnostic messages are appended (e.g. from auto-relaxation).

    Returns:
        List of SearchResult, EmailContent, strings, or Contact objects based on operation.
    """
    # Handle list operations
    if list_type:
        if list_type == "tags":
            return _list_tags()
        elif list_type == "folders":
            return _list_folders()
        elif list_type == "accounts":
            return _list_accounts()
        else:
            raise ValueError(
                f"Unknown list_type: {list_type}. Use 'tags', 'folders', or 'accounts'."
            )

    # Handle contact search
    if query.startswith("contact:"):
        contact_query = query[8:].strip()
        if not contact_query:
            raise ValueError("Contact query required after 'contact:'")
        return _find_contacts(contact_query, max_results)

    # Validate query for email operations
    if not query:
        raise ValueError(
            "Query required for email search/show. Use list_type for listing, or 'contact:name' for contacts."
        )

    # Resolve abbreviated message IDs in query (supports id: and mid: terms)
    if "id:" in query or "mid:" in query:
        query = _resolve_id_in_query(query)

    # Normalize folder: quoting BEFORE family expansion
    if "folder:" in query:
        query = _normalize_folder_query(query)

    # Expand year-partitioned folder families
    pre_expansion_query = query
    families = _get_folder_families()
    query = _expand_folder_families(query, families)

    # Execute search
    if mode == "headers":
        results = _search_emails(query, limit, offset, include_excluded)
    else:
        results = _show_email(
            query,
            mode=mode,
            limit=limit,
            include_excluded=include_excluded,
            save_to=save_attachments_to,
            segment_quotes=segment_quotes,
        )

    # Auto-relax on 0 results (only at offset==0 to avoid false trigger on pagination)
    # Gate uses expanded query (same families dict); relaxation uses pre-expansion
    # query (folder: at top level) then re-expands each relaxed variant
    if not results and pre_expansion_query and offset == 0:
        count = _notmuch_count(query, include_excluded)
        if count == 0:  # genuine 0 (not -1 = error)
            results, diag = _auto_relax(
                pre_expansion_query,
                limit,
                offset,
                include_excluded,
                mode,
                save_to=save_attachments_to,
                segment_quotes=segment_quotes,
            )
            if _diagnostics is not None and diag:
                _diagnostics.append(diag)

    return results


def update(
    message_ids: list[str] | None = None,
    action: str = "",
    add_tags: list[str] | None = None,
    remove_tags: list[str] | None = None,
    destination_folder: str = "",
) -> TagResult | MoveResult:
    """Update email metadata - tag, move, or archive emails.

    Args:
        message_ids: A list of notmuch message IDs for the emails to update.
            Supports abbreviated IDs.
        action: Action: 'tag' (add/remove tags), 'move' (relocate to folder),
            or 'archive' (move to Archive folder).
        add_tags: For action='tag': tags to add.
        remove_tags: For action='tag': tags to remove.
        destination_folder: For action='move': destination folder (e.g., 'Trash', 'Archive').

    Returns:
        TagResult or MoveResult based on action.
    """
    message_ids = message_ids or []
    add_tags = add_tags or []
    remove_tags = remove_tags or []

    # Resolve abbreviated message IDs
    message_ids = [_resolve_message_id(mid) for mid in message_ids]

    if action == "tag":
        if not message_ids:
            raise ValueError("At least one message_id required for tag action")
        if len(message_ids) == 1:
            return _tag_email(message_ids[0], add_tags, remove_tags)
        # Bulk tag operation
        for mid in message_ids:
            _tag_email(mid, add_tags, remove_tags)
        # Return summary result
        return TagResult(
            message_id=f"{len(message_ids)} messages",
            added_tags=add_tags,
            removed_tags=remove_tags,
        )

    if action == "move":
        if not message_ids:
            raise ValueError("At least one message_id required for move action")
        if not destination_folder:
            raise ValueError("destination_folder required for move action")
        return _move_emails(message_ids, destination_folder)

    if action == "archive":
        if not message_ids:
            raise ValueError("At least one message_id required for archive action")
        return _move_emails(message_ids, "archive")

    raise ValueError(f"Unknown action: {action}. Use 'tag', 'move', or 'archive'.")
