"""Core notmuch email functions for direct Python use.

Identical interface to MCP tools, usable without MCP server.
"""

from mcp_handley_lab.email.notmuch.tool import (
    Contact,
    EmailContent,
    MoveResult,
    SearchResult,
    TagResult,
    _find_contacts,
    _list_accounts,
    _list_folders,
    _list_tags,
    _move_emails,
    _resolve_id_in_query,
    _resolve_message_id,
    _search_emails,
    _show_email,
    _tag_email,
)


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

    # For headers/summary mode, use lightweight search
    if mode in ("headers", "summary"):
        results = _search_emails(query, limit, offset, include_excluded)
        if mode == "headers":
            return results
        # For summary, get truncated content
        return _show_email(
            query,
            mode="summary",
            limit=limit,
            include_excluded=include_excluded,
            save_to=save_attachments_to,
        )

    # Full content display
    return _show_email(
        query,
        mode=mode,
        limit=limit,
        include_excluded=include_excluded,
        save_to=save_attachments_to,
        segment_quotes=segment_quotes,
    )


def update(
    message_ids: list[str] | None = None,
    action: str = "",
    add_tags: list[str] | None = None,
    remove_tags: list[str] | None = None,
    destination_folder: str = "",
) -> TagResult | MoveResult:
    """Update email metadata - tag or move emails.

    Args:
        message_ids: A list of notmuch message IDs for the emails to update.
            Supports abbreviated IDs.
        action: Action: 'tag' (add/remove tags) or 'move' (relocate to folder).
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

    raise ValueError(f"Unknown action: {action}. Use 'tag' or 'move'.")
