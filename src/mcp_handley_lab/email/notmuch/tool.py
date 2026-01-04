"""Notmuch email search and indexing provider."""

import json
import os
import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parseaddr
from pathlib import Path

from pydantic import BaseModel, Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp
from mcp_handley_lab.email.extraction import (
    EmailBodySegment,
    EmailPartInfo,
    extract_email_content,
)

MAILDIR_LEAFS = {"cur", "new", "tmp"}


def _new() -> str:
    """Index newly received emails into notmuch database (internal helper)."""
    stdout, _ = run_command(["notmuch", "new"], timeout=60)
    return stdout.decode().strip()


def _get_account_folders(maildir_root: Path, account_name: str) -> dict[str, Path]:
    """Get folders for a specific account using shallow directory scan (fast; skips cur/new/tmp)."""
    account_path = maildir_root / account_name
    folders: dict[str, Path] = {}

    try:
        children = list(account_path.iterdir())
    except (FileNotFoundError, NotADirectoryError):
        return folders

    for child in children:
        if child.is_dir() and child.name not in MAILDIR_LEAFS:
            folders[child.name] = child

    return folders


def _find_smart_destination(
    source_files: list[str], maildir_root: Path, destination_folder: str
) -> Path:
    """Find existing destination folder based on source email locations. Never creates new folders."""
    if not source_files:
        raise ValueError("No source files provided to determine destination.")

    folder_map = {
        "archive": ["archive"],
        "trash": ["bin", "trash", "deleted"],
        "sent": ["sent"],
        "drafts": ["drafts", "draft"],
        "spam": ["spam", "junk"],
    }

    first_source = Path(source_files[0])
    rel_path = first_source.relative_to(maildir_root)

    # Determine account path - handles both root and account-specific folders
    if len(rel_path.parts) > 2:  # Account/folder/cur/file.eml
        account_name = rel_path.parts[0]
        account_path = maildir_root / account_name
    else:  # cur/file.eml or new/file.eml (root level)
        account_path = maildir_root
        account_name = account_path.name

    # Try exact match first
    exact_match = account_path / destination_folder
    if exact_match.is_dir():
        return exact_match

    # Get folders from notmuch index (fast, no filesystem scan)
    account_folders = _get_account_folders(maildir_root, account_name)

    # Try common name variations (case-insensitive)
    destination_lower = destination_folder.lower()
    if potential_names := folder_map.get(destination_lower):
        for folder_name, folder_path in account_folders.items():
            if any(name in folder_name.lower() for name in potential_names):
                return folder_path

    # No match found - fail with helpful error
    raise FileNotFoundError(
        f"No existing folder matching '{destination_folder}' found in account '{account_name}'. "
        f"Available folders: {list(account_folders.keys())}"
    )


class EmailContent(BaseModel):
    """Structured representation of a single email's content."""

    id: str = Field(
        ...,
        description="Complete message ID (use ENTIRE string including @domain for id: queries).",
    )
    subject: str = Field(..., description="The subject line of the email.")
    from_address: str = Field(..., description="The sender's email address and name.")
    to_address: str = Field(
        ..., description="The primary recipient's email address and name."
    )
    date: str = Field(
        ..., description="The date the email was sent, in a human-readable format."
    )
    tags: list[str] = Field(
        ..., description="A list of notmuch tags associated with the email."
    )
    body_markdown: str = Field(
        ...,
        description="The body of the email, converted to Markdown for best LLM comprehension. Preserves lists, tables, links, and formatting.",
    )
    body_format: str = Field(
        ...,
        description="The original format of the body ('html', 'text', or 'empty').",
    )
    attachments: list[str] = Field(
        default_factory=list,
        description="A list of filenames for any attachments in the email.",
    )
    saved_files: list[str] = Field(
        default_factory=list,
        description="Paths to saved files when save_attachments_to is used (body + attachments).",
    )

    # Selected part info (summary + full modes)
    selected_part: EmailPartInfo | None = Field(
        default=None, description="Which MIME part was chosen as body."
    )

    # Truncation metadata (summary mode only)
    is_truncated: bool | None = Field(
        default=None, description="True if body was truncated in summary mode."
    )
    original_length: int | None = Field(
        default=None, description="Char count of body_markdown before truncation."
    )

    # Warnings (summary + full modes)
    extraction_warnings: list[str] | None = Field(
        default=None, description="Non-fatal issues during extraction."
    )

    # Preservation fields (full mode only - use None for omission from serialization)
    body_raw: str | None = Field(
        default=None, description="Decoded text before processing (full mode only)."
    )
    body_html_raw: str | None = Field(
        default=None, description="Original HTML if source was HTML (full mode only)."
    )
    segments: list[EmailBodySegment] | None = Field(
        default=None, description="Quote detection results (full mode only)."
    )
    parts_manifest: list[EmailPartInfo] | None = Field(
        default=None, description="All MIME parts in the message (full mode only)."
    )


class TagResult(BaseModel):
    """Result of tag operation."""

    message_id: str = Field(..., description="The notmuch message ID that was tagged.")
    added_tags: list[str] = Field(
        ..., description="A list of tags that were added to the message."
    )
    removed_tags: list[str] = Field(
        ..., description="A list of tags that were removed from the message."
    )


class MoveResult(BaseModel):
    """Result of a successful email move operation."""

    message_ids: list[str] = Field(
        ..., description="The list of message IDs that were targeted for moving."
    )
    destination_folder: str = Field(
        ..., description="The maildir folder the emails were moved to."
    )
    moved_files_count: int = Field(
        ..., description="The number of email files successfully moved."
    )
    status: str = Field(..., description="A summary of the move operation.")


class SearchResult(BaseModel):
    """Structured search result for a single email."""

    id: str = Field(
        ...,
        description="Complete message ID (use ENTIRE string including @domain for id: queries).",
    )
    subject: str = Field(..., description="The subject line of the email.")
    from_address: str = Field(..., description="The sender's email address and name.")
    to_address: str = Field(
        default="",
        description="The primary recipient's email address (empty if not available).",
    )
    date: str = Field(
        default="", description="The date the email was sent (empty if not available)."
    )
    tags: list[str] = Field(
        default_factory=list, description="Tags associated with this email."
    )


def _search_emails(
    query: str,
    limit: int = 100,
    offset: int = 0,
    include_excluded: bool = False,
) -> list[SearchResult]:
    """Internal search implementation using notmuch show --body=false for efficiency."""
    cmd = ["notmuch", "show", "--format=json", "--body=false"]
    if include_excluded:
        cmd.append("--exclude=false")
    cmd.extend(["--limit", str(limit), "--offset", str(offset)])
    cmd.append(query)
    stdout, _ = run_command(cmd)

    # notmuch show returns nested structure: [[thread1], [thread2], ...]
    # Each thread contains messages: [msg1, [replies...], msg2, ...]
    threads = json.loads(stdout.decode().strip())

    results = []
    for thread in threads:
        for item in thread:
            # item is either a message dict or a list of replies
            _collect_messages_from_thread(item, results)

    return results


def _collect_messages_from_thread(item, results: list[SearchResult]) -> None:
    """Recursively collect messages from notmuch thread structure."""
    if isinstance(item, dict):
        # This is a message
        headers = item.get("headers", {})
        results.append(
            SearchResult(
                id=item.get("id", ""),
                subject=headers.get("Subject", "") or "[No Subject]",
                from_address=headers.get("From", "") or "[Unknown Sender]",
                to_address=headers.get("To", ""),
                date=headers.get("Date", ""),
                tags=item.get("tags", []),
            )
        )
    elif isinstance(item, list):
        # This is a list of replies or nested messages
        for sub_item in item:
            _collect_messages_from_thread(sub_item, results)


def _get_message_from_raw_source(message_id: str) -> EmailMessage:
    """Fetches the raw source of an email from notmuch and parses it into an EmailMessage object."""
    raw_email_bytes, _ = run_command(
        ["notmuch", "show", "--format=raw", f"id:{message_id}"]
    )
    parser = BytesParser(policy=policy.default)
    return parser.parsebytes(raw_email_bytes)


def _save_email_files(
    msg, message_id: str, body_content: str, body_format: str, save_path: Path
) -> list[str]:
    """Save email body and attachments to files."""
    saved_files = []
    save_path.mkdir(parents=True, exist_ok=True)

    # Create safe base filename from message_id
    safe_id = re.sub(r'[\\/*?:"<>|@]', "_", message_id)[:50]

    # Save body as txt or html (explicit encoding for robustness)
    body_ext = ".html" if body_format == "html" else ".txt"
    body_file = save_path / f"{safe_id}_body{body_ext}"
    body_file.write_text(body_content, encoding="utf-8", errors="replace")
    saved_files.append(str(body_file))

    # Save attachments
    for part in msg.walk():
        if part_filename := part.get_filename():
            clean_filename = re.sub(r'[\\/*?:"<>|]', "_", Path(part_filename).name)
            file_path = save_path / clean_filename

            # Handle filename collisions
            counter = 1
            stem, suffix = file_path.stem, file_path.suffix
            while file_path.exists():
                file_path = save_path / f"{stem}_{counter}{suffix}"
                counter += 1

            if payload := part.get_payload(decode=True):
                file_path.write_bytes(payload)
                saved_files.append(str(file_path))

    return saved_files


def _show_email(
    query: str,
    mode: str = "full",
    limit: int | None = None,
    include_excluded: bool = False,
    save_to: str = "",
    segment_quotes: bool = False,
) -> list[EmailContent]:
    """Internal implementation of email display.

    Uses new extraction pipeline that never silently loses content.
    Mode controls response projection (what fields are returned), not extraction.

    Args:
        query: notmuch query string
        mode: 'headers' (metadata only), 'summary' (truncated body), 'full' (complete)
        limit: max messages to return
        include_excluded: include spam/deleted
        save_to: directory to save attachments
        segment_quotes: if True, include quote detection segments (full mode only)
    """
    cmd = ["notmuch", "search", "--format=json", "--output=messages"]
    if include_excluded:
        cmd.append("--exclude=false")
    cmd.append(query)
    stdout, _ = run_command(cmd)
    message_ids = json.loads(stdout.decode().strip())

    # Apply limit to prevent token overflow if specified
    if limit is not None and len(message_ids) > limit:
        message_ids = message_ids[:limit]

    save_path = Path(save_to).expanduser() if save_to else None

    results = []
    for message_id in message_ids:
        msg = _get_message_from_raw_source(message_id)

        # Extract headers
        subject = msg.get("Subject", "") or "[No Subject]"
        from_address = msg.get("From", "") or "[Unknown Sender]"
        to_address = msg.get("To", "") or "[Unknown Recipient]"
        date = msg.get("Date", "") or "[Unknown Date]"

        # Get tags
        tag_cmd = ["notmuch", "search", "--output=tags", f"id:{message_id}"]
        tag_stdout, _ = run_command(tag_cmd)
        tags = [
            tag.strip()
            for tag in tag_stdout.decode().strip().split("\n")
            if tag.strip()
        ]

        # Extract email content (summary and full modes)
        # Note: headers mode is handled by read() calling _search_emails() directly
        # Parse email address from From header for talon signature detection
        _, sender_email = parseaddr(from_address)
        extraction = extract_email_content(
            msg,
            segment_quotes=segment_quotes and mode == "full",
            sender_email=sender_email,
        )

        # Prepare body content
        full_body_content = extraction.body_markdown
        body_format = extraction.body_format

        # Save files if requested - always save FULL content, never truncated
        saved_files = []
        if save_path:
            saved_files = _save_email_files(
                msg, message_id, full_body_content, body_format, save_path
            )

        # Summary mode: truncate for response (after saving full)
        body_content = full_body_content
        is_truncated = None
        original_length = None
        if mode == "summary" and len(full_body_content) > 2000:
            original_length = len(full_body_content)
            body_content = full_body_content[:2000]
            is_truncated = True

        # Build result with progressive disclosure
        email_content = EmailContent(
            id=message_id,
            subject=subject,
            from_address=from_address,
            to_address=to_address,
            date=date,
            tags=tags,
            body_markdown=body_content,
            body_format=body_format,
            attachments=extraction.attachments,
            saved_files=saved_files,
            # Summary + full modes
            selected_part=extraction.selected_part,
            extraction_warnings=extraction.extraction_warnings or None,
            # Summary mode only
            is_truncated=is_truncated,
            original_length=original_length,
        )

        # Full mode: add preservation fields
        if mode == "full":
            email_content.body_raw = extraction.body_raw or None
            email_content.body_html_raw = extraction.body_html_raw or None
            email_content.parts_manifest = extraction.parts_manifest or None
            if segment_quotes and extraction.segments:
                email_content.segments = extraction.segments

        results.append(email_content)

    return results


def _tag_email(
    message_id: str,
    add_tags: list[str] | None = None,
    remove_tags: list[str] | None = None,
) -> TagResult:
    """Internal tag implementation."""
    add_tags = add_tags or []
    remove_tags = remove_tags or []
    cmd = (
        ["notmuch", "tag"]
        + [f"+{tag}" for tag in add_tags]
        + [f"-{tag}" for tag in remove_tags]
        + [f"id:{message_id}"]
    )

    run_command(cmd)

    return TagResult(
        message_id=message_id, added_tags=add_tags, removed_tags=remove_tags
    )


def _move_emails(
    message_ids: list[str],
    destination_folder: str,
) -> MoveResult:
    """
    Moves emails to a specified maildir folder.

    This function performs three main steps:
    1. Finds the filesystem paths of the emails using their message IDs.
    2. Moves the email files to the destination maildir folder (into its 'new' subdirectory).
    3. Updates the notmuch database to reflect the changes.
    """
    if not message_ids:
        raise ValueError("At least one message_id must be provided.")

    query = " or ".join([f"id:{mid}" for mid in message_ids])
    search_cmd = ["notmuch", "search", "--output=files", query]
    stdout, _ = run_command(search_cmd)

    source_files = [
        line.strip() for line in stdout.decode().strip().split("\n") if line.strip()
    ]

    if not source_files:
        raise FileNotFoundError(
            f"No email files found for the given message IDs: {message_ids}"
        )

    # Get maildir root and determine smart destination folder
    db_path_str, _ = run_command(["notmuch", "config", "get", "database.path"])
    maildir_root = Path(db_path_str.decode().strip())

    # Find the appropriate destination based on source email locations
    smart_destination = _find_smart_destination(
        source_files, maildir_root, destination_folder
    )
    destination_dir = smart_destination / "new"

    # Create the destination 'new' directory if needed (this is safe)
    destination_dir.mkdir(parents=True, exist_ok=True)

    moved_count = 0
    for file_path in source_files:
        source_path = Path(file_path)
        destination_path = destination_dir / source_path.name

        # Handle filename collisions (similar to extract_attachments)
        counter = 1
        stem, suffix = destination_path.stem, destination_path.suffix
        while destination_path.exists():
            destination_path = destination_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        try:
            os.rename(source_path, destination_path)
            moved_count += 1
        except OSError as e:
            raise OSError(
                f"Failed to move {source_path} to {destination_path}: {e}"
            ) from e

    # Update the notmuch index to discover the moved files
    _new()

    # Apply destination-based tag policies using resolved folder name
    tag_policies = {
        "archive": {"add": [], "remove": ["inbox"]},  # Keep unread status
        "trash": {"add": ["deleted"], "remove": ["inbox", "unread"]},
        "bin": {"add": ["deleted"], "remove": ["inbox", "unread"]},
        "deleted": {"add": ["deleted"], "remove": ["inbox", "unread"]},
        "spam": {"add": ["spam"], "remove": ["inbox", "unread"]},
        "junk": {"add": ["spam"], "remove": ["inbox", "unread"]},
        "junk email": {"add": ["spam"], "remove": ["inbox", "unread"]},
        "sent": {"add": [], "remove": ["inbox"]},
        "drafts": {"add": ["draft"], "remove": ["inbox"]},
    }

    # Use resolved folder name for policy matching (handles Hermes/Archive -> archive)
    dest_key = smart_destination.name.lower()
    if policy := tag_policies.get(dest_key):
        for mid in message_ids:
            tag_changes = [f"+{t}" for t in policy["add"]] + [
                f"-{t}" for t in policy["remove"]
            ]
            if tag_changes:
                run_command(["notmuch", "tag"] + tag_changes + [f"id:{mid}"])

    # Construct and return a structured result
    moved_count = len(source_files)
    status_message = f"Successfully moved {moved_count} email(s) to '{destination_folder}' and updated the index."
    if moved_count < len(message_ids):
        status_message += f" Note: {len(message_ids) - moved_count} of the requested message IDs could not be found."

    return MoveResult(
        message_ids=message_ids,
        destination_folder=destination_folder,
        moved_files_count=moved_count,
        status=status_message,
    )


def _is_sent_message(message_id: str) -> bool:
    """Check if message is from Sent folder. Uses tags first, path fallback."""
    # Check for 'sent' tag (most reliable)
    stdout, _ = run_command(["notmuch", "search", "--output=tags", f"id:{message_id}"])
    tags = stdout.decode().strip().lower().split("\n")
    if "sent" in tags:
        return True

    # Fallback: check file paths (handles multiple files)
    stdout, _ = run_command(["notmuch", "search", "--output=files", f"id:{message_id}"])
    file_paths = stdout.decode().strip().lower().split("\n")
    sent_patterns = ["/sent/", "/sent items/", "/outbox/", "/.sent/", "/sent messages/"]
    return any(
        any(pattern in path for pattern in sent_patterns) for path in file_paths if path
    )


def _get_thread_message_ids(message_id: str) -> list[str]:
    """Get all message IDs in the same thread, oldest first."""
    # Get thread ID for this message
    stdout, _ = run_command(
        ["notmuch", "search", "--output=threads", f"id:{message_id}"]
    )
    thread_id = stdout.decode().strip()

    if not thread_id:
        return []

    # Normalize thread ID format (ensure it starts with "thread:")
    if not thread_id.startswith("thread:"):
        thread_id = f"thread:{thread_id}"

    # Get all message IDs in thread, oldest first
    stdout, _ = run_command(
        ["notmuch", "search", "--output=messages", "--sort=oldest-first", thread_id]
    )
    return [m.strip() for m in stdout.decode().strip().split("\n") if m.strip()]


def _get_thread_messages(
    message_id: str,
    max_messages: int = 5,
) -> list[tuple[str, str, str, str]]:
    """Get messages in thread for reply context.

    Args:
        message_id: The message being replied to (will be excluded)
        max_messages: Max previous messages to include (0=none, -1=all, default 5)

    Returns: List of (date, from_address, subject, body) tuples, oldest first
    """
    thread_message_ids = _get_thread_message_ids(message_id)

    # Exclude the message being replied to
    thread_message_ids = [m for m in thread_message_ids if m != message_id]

    if not thread_message_ids:
        return []

    # Limit to most recent N messages (take from end since sorted oldest-first)
    if max_messages == 0:
        return []
    if max_messages > 0 and len(thread_message_ids) > max_messages:
        thread_message_ids = thread_message_ids[-max_messages:]

    # Fetch each message using new extraction pipeline
    messages = []
    for mid in thread_message_ids:
        try:
            msg = _get_message_from_raw_source(mid)
            # Use extraction module for full content (no quote stripping for thread context)
            extraction = extract_email_content(msg, segment_quotes=False)

            messages.append(
                (
                    msg.get("Date", "[Unknown Date]"),
                    msg.get("From", "[Unknown Sender]"),
                    msg.get("Subject", "[No Subject]"),
                    extraction.body_markdown,
                )
            )
        except Exception:
            continue  # Skip messages that fail to parse

    return messages


# Contact finding helpers (moved from mutt_aliases for read tool)
class Contact(BaseModel):
    """Contact information."""

    alias: str
    email: str
    name: str = ""


def _parse_alias_line(line: str) -> Contact:
    """Parse a mutt alias line into a Contact object."""
    line = line.strip()
    if not line.startswith("alias "):
        raise ValueError(f"Invalid alias line: {line}")

    match = re.match(r'alias\s+(\S+)\s+"([^"]+)"\s*<([^>]+)>', line)
    if match:
        alias, name, email = match.groups()
        return Contact(alias=alias, email=email, name=name)

    match = re.match(r"alias\s+(\S+)\s+(\S+)", line)
    if match:
        alias, email = match.groups()
        name = line.split("#", 1)[1].strip() if "#" in line else ""
        return Contact(alias=alias, email=email, name=name)

    raise ValueError(f"Could not parse alias line: {line}")


def _get_alias_file(config_file: str = "") -> Path:
    """Get mutt alias file path from mutt configuration."""
    cmd = ["mutt", "-Q", "alias_file"]
    if config_file:
        cmd.extend(["-F", config_file])

    stdout, _ = run_command(cmd)
    result = stdout.decode().strip()
    path = result.split("=")[1].strip("\"'")
    if path.startswith("~"):
        path = str(Path.home()) + path[1:]
    return Path(path)


def _find_contacts(query: str, max_results: int = 10) -> list[Contact]:
    """Find contacts using simple fuzzy matching."""
    alias_file = _get_alias_file()

    try:
        content = alias_file.read_text()
    except FileNotFoundError:
        return []

    contacts = []
    for line in content.splitlines():
        if line.strip().startswith("alias "):
            try:
                contacts.append(_parse_alias_line(line))
            except ValueError:
                continue

    query_lower = query.lower()
    matches = [
        c
        for c in contacts
        if query_lower in c.alias.lower()
        or query_lower in c.email.lower()
        or query_lower in c.name.lower()
    ]
    return matches[:max_results]


# List helpers (moved from main tool.py)
def _list_tags() -> list[str]:
    """List all tags in the notmuch database."""
    stdout, _ = run_command(["notmuch", "search", "--output=tags", "*"])
    output = stdout.decode().strip()
    return sorted([tag.strip() for tag in output.split("\n") if tag.strip()])


def _list_folders() -> list[str]:
    """List maildir folders using shallow directory scan."""
    db_path_stdout, _ = run_command(["notmuch", "config", "get", "database.path"])
    maildir_root = Path(db_path_stdout.decode().strip())

    folders: set[str] = set()
    for account in maildir_root.iterdir():
        try:
            children = list(account.iterdir())
        except NotADirectoryError:
            continue
        for child in children:
            if child.name in MAILDIR_LEAFS:
                continue
            try:
                list((child / "cur").iterdir())
                folders.add(f"{account.name}/{child.name}")
            except (NotADirectoryError, FileNotFoundError):
                continue
    return sorted(folders)


def _list_accounts(config_file: str = "") -> list[str]:
    """List available msmtp accounts by parsing msmtp config."""
    msmtprc_path = Path(config_file) if config_file else Path.home() / ".msmtprc"

    accounts = []
    with open(msmtprc_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("account ") and not line.startswith("account default"):
                account_name = line.split()[1]
                accounts.append(account_name)
    return accounts


# ============================================================================
# Unified Tools
# ============================================================================


@mcp.tool(
    description="""Search emails using notmuch query language. Supports sender, subject, date ranges, tags, attachments, and body content filtering with boolean operators."""
)
def read(
    query: str = Field(
        default="",
        description="A valid notmuch search query. Examples: 'from:boss', 'tag:inbox and date:2024-01-01..', 'subject:\"Project X\"'. For ID queries, use the COMPLETE id field from search results including the @domain part (e.g., 'id:ABC123@example.com', NOT 'id:ABC123').",
    ),
    limit: int = Field(
        default=100,
        description="The maximum number of message IDs to return.",
        gt=0,
    ),
    offset: int = Field(
        default=0,
        description="Number of results to skip for pagination.",
        ge=0,
    ),
    include_excluded: bool = Field(
        default=False,
        description="Include emails with excluded tags (spam, deleted) that are normally hidden.",
    ),
    mode: str = Field(
        default="headers",
        description="Rendering mode: 'headers' (metadata only), 'summary' (first 2000 chars), or 'full' (complete optimized content)",
    ),
    save_attachments_to: str = Field(
        default="",
        description="Directory to save email body and attachments to. Body saved as .txt/.html, attachments saved with original filenames. Paths returned in saved_files field.",
    ),
    list_type: str = Field(
        default="",
        description="For listing: 'tags', 'folders', or 'accounts'. When set, ignores query and returns list.",
    ),
    max_results: int = Field(
        default=10,
        description="For find_contacts: maximum results to return.",
        gt=0,
    ),
    segment_quotes: bool = Field(
        default=False,
        description="For full mode: include quote/signature segmentation in response (requires talon).",
    ),
) -> list[SearchResult] | list[EmailContent] | list[str] | list[Contact]:
    """Unified read tool for emails.

    Operations based on parameters:
    - list_type set: Returns list of tags/folders/accounts
    - query starts with "contact:": Searches contacts (e.g., "contact:alice")
    - query + mode="headers"/"summary": Search with lightweight results
    - query + mode="full": Full email content display

    Returns different types based on operation.
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

    # For headers/summary mode, use lightweight search
    if mode in ("headers", "summary"):
        # Get search results first
        results = _search_emails(query, limit, offset, include_excluded)
        if mode == "headers":
            return results
        # For summary, get truncated content (save_to supported in all modes)
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


@mcp.tool(
    description="""Update email metadata. Actions: 'tag' (add/remove tags), 'move' (relocate to folder)."""
)
def update(
    message_ids: list[str] = Field(
        default_factory=list,
        description="A list of notmuch message IDs for the emails to update.",
    ),
    action: str = Field(
        ...,
        description="Action: 'tag' (add/remove tags) or 'move' (relocate to folder).",
    ),
    add_tags: list[str] = Field(
        default_factory=list,
        description="For action='tag': tags to add.",
    ),
    remove_tags: list[str] = Field(
        default_factory=list,
        description="For action='tag': tags to remove.",
    ),
    destination_folder: str = Field(
        default="",
        description="For action='move': destination folder (e.g., 'Trash', 'Archive').",
    ),
) -> TagResult | MoveResult:
    """Unified update tool for email metadata.

    Actions:
    - tag: Add/remove tags from emails
    - move: Move emails to a maildir folder
    """
    if action == "tag":
        if not message_ids:
            raise ValueError("At least one message_id required for tag action")
        if len(message_ids) == 1:
            return _tag_email(message_ids[0], add_tags, remove_tags)
        # Bulk tag operation
        results = []
        for mid in message_ids:
            results.append(_tag_email(mid, add_tags, remove_tags))
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
