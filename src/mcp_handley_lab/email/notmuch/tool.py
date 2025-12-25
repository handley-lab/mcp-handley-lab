"""Notmuch email search and indexing provider."""

import json
import os
import re
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

import ftfy
from email_reply_parser import EmailReplyParser
from inscriptis import get_text
from pydantic import BaseModel, Field
from selectolax.parser import HTMLParser

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp

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

    id: str = Field(..., description="The unique message ID of the email.")
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
        description="The original format of the body ('html' or 'text'). Indicates if the markdown was converted or is original plain text.",
    )
    attachments: list[str] = Field(
        default_factory=list,
        description="A list of filenames for any attachments in the email.",
    )
    saved_files: list[str] = Field(
        default_factory=list,
        description="Paths to saved files when save_attachments_to is used (body + attachments).",
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

    id: str = Field(..., description="The unique message ID of the email.")
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


@mcp.tool(
    description="""Search emails using notmuch query language. Supports sender, subject, date ranges, tags, attachments, and body content filtering with boolean operators."""
)
def search(
    query: str = Field(
        ...,
        description="A valid notmuch search query. Examples: 'from:boss', 'tag:inbox and date:2024-01-01..', 'subject:\"Project X\"'.",
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
) -> list[SearchResult]:
    """Search emails using notmuch query syntax.

    Returns structured search results with id, subject, from, date, and tags.
    Use show() for full email content including body.
    """
    cmd = [
        "notmuch",
        "search",
        "--format=json",
        "--output=messages",
        "--limit",
        str(limit),
        "--offset",
        str(offset),
    ]
    if include_excluded:
        cmd.append("--exclude=false")
    cmd.append(query)
    stdout, _ = run_command(cmd)
    message_ids = json.loads(stdout.decode().strip())

    results = []
    for message_id in message_ids:
        msg = _get_message_from_raw_source(message_id)

        # Get tags
        tag_cmd = ["notmuch", "search", "--output=tags", f"id:{message_id}"]
        tag_stdout, _ = run_command(tag_cmd)
        tags = [t.strip() for t in tag_stdout.decode().strip().split("\n") if t.strip()]

        results.append(
            SearchResult(
                id=message_id,
                subject=msg.get("Subject", "") or "[No Subject]",
                from_address=msg.get("From", "") or "[Unknown Sender]",
                to_address=msg.get("To", ""),
                date=msg.get("Date", ""),
                tags=tags,
            )
        )

    return results


def _get_message_from_raw_source(message_id: str) -> EmailMessage:
    """Fetches the raw source of an email from notmuch and parses it into an EmailMessage object."""
    raw_email_bytes, _ = run_command(
        ["notmuch", "show", "--format=raw", f"id:{message_id}"]
    )
    parser = BytesParser(policy=policy.default)
    return parser.parsebytes(raw_email_bytes)


# Initialize email reply parser
reply_parser = EmailReplyParser()


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace for token efficiency while preserving readability."""
    if not text:
        return ""

    # Collapse excessive newlines (preserve paragraph structure)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    # Remove trailing whitespace from lines
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Compress multiple spaces to single space
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def optimize_email_content(msg: EmailMessage, mode: str = "full") -> dict:
    """
    Optimized email content extraction using expert-recommended libraries.

    Args:
        msg: EmailMessage object
        mode: "headers", "summary", or "full"

    Returns:
        dict with body, attachments, and body_format
    """
    attachments = []

    # Extract attachments
    for part in msg.walk():
        if part.get_filename():
            attachment_info = f"{part.get_filename()} ({part.get_content_type()})"
            attachments.append(attachment_info)

    if mode == "headers":
        return {
            "body": "",
            "attachments": sorted(set(attachments)),
            "body_format": "headers_only",
        }

    # Get best content part
    body_part = msg.get_body(preferencelist=("plain", "html"))

    if not body_part:
        # Fallback: try to extract from multipart
        if not msg.is_multipart() and not msg.is_attachment():
            content = msg.get_content()
        else:
            content = ""
    else:
        content = body_part.get_content()
        content_type = body_part.get_content_type()

        if content_type == "text/html":
            # Use optimized HTML processing pipeline
            content = process_html_content(content)
            body_format = "html"
        else:
            body_format = "text"

    if not content:
        return {
            "body": "",
            "attachments": sorted(set(attachments)),
            "body_format": "empty",
        }

    # Apply email-reply-parser for quote stripping and clean content extraction
    clean_content = reply_parser.parse_reply(content)

    # Final normalization
    clean_content = ftfy.fix_text(clean_content)
    clean_content = normalize_whitespace(clean_content)

    # Apply length limits based on mode
    if mode == "summary" and len(clean_content) > 2000:
        clean_content = (
            clean_content[:2000] + "\n\n[Content truncated for summary mode]"
        )

    return {
        "body": clean_content,
        "attachments": sorted(set(attachments)),
        "body_format": body_format if "body_format" in locals() else "text",
    }


def process_html_content(html_content: str) -> str:
    """
    Process HTML content using selectolax + inscriptis for optimal token efficiency.
    """
    if not html_content:
        return ""

    # Parse with selectolax (faster than BeautifulSoup)
    tree = HTMLParser(html_content)

    # Remove common email cruft
    selectors_to_remove = [
        "script",
        "style",
        "meta",
        "link",
        "head",
        "noscript",
        "iframe",
        # Hidden content
        '[style*="display:none"]',
        '[style*="visibility:hidden"]',
        '[style*="opacity:0"]',
        '[style*="font-size:0"]',
        "[hidden]",
        '[aria-hidden="true"]',
        # Tracking and marketing
        'img[width="1"]',
        'img[height="1"]',
        'img[src*="tracking"]',
        'img[src*="open"]',
        'img[src*="fls.doubleclick.net"]',
        'img[src*="googletagmanager"]',
        # Email client quote blocks
        ".gmail_quote",
        ".OutlookMessageHeader",
        ".yahoo_quoted",
        'blockquote[type="cite"]',
        'div[style*="border-left:1px #ccc solid"]',
        # Unsubscribe and footer content
        ".unsubscribe",
        ".unsubscribe-link",
        'a[href*="unsubscribe"]',
        'a[href*="optout"]',
        ".disclaimer",
        ".legal",
        "footer",
        "nav",
    ]

    for selector in selectors_to_remove:
        for node in tree.css(selector):
            node.decompose()

    # Get cleaned HTML
    cleaned_html = tree.body.html if tree.body else tree.html

    # Convert to clean text with inscriptis
    return get_text(cleaned_html)


def _save_email_files(
    msg, message_id: str, body_content: str, body_format: str, save_path: Path
) -> list[str]:
    """Save email body and attachments to files."""
    saved_files = []
    save_path.mkdir(parents=True, exist_ok=True)

    # Create safe base filename from message_id
    safe_id = re.sub(r'[\\/*?:"<>|@]', "_", message_id)[:50]

    # Save body as txt or html
    body_ext = ".html" if body_format == "html" else ".txt"
    body_file = save_path / f"{safe_id}_body{body_ext}"
    body_file.write_text(body_content)
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
) -> list[EmailContent]:
    """Internal implementation of email display."""
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
        reconstructed_msg = _get_message_from_raw_source(message_id)

        # Use optimized content extraction
        extracted_data = optimize_email_content(reconstructed_msg, mode=mode)
        body_content = extracted_data["body"]
        body_format = extracted_data["body_format"]
        attachments = extracted_data["attachments"]

        # Extract headers
        subject = reconstructed_msg.get("Subject", "")
        from_address = reconstructed_msg.get("From", "")
        to_address = reconstructed_msg.get("To", "")
        date = reconstructed_msg.get("Date", "")

        # Get tags
        tag_cmd = ["notmuch", "search", "--output=tags", f"id:{message_id}"]
        tag_stdout, _ = run_command(tag_cmd)
        tags = [
            tag.strip()
            for tag in tag_stdout.decode().strip().split("\n")
            if tag.strip()
        ]

        # Save files if requested
        saved_files = []
        if save_path:
            saved_files = _save_email_files(
                reconstructed_msg, message_id, body_content, body_format, save_path
            )

        results.append(
            EmailContent(
                id=message_id,
                subject=subject or "[No Subject]",
                from_address=from_address or "[Unknown Sender]",
                to_address=to_address or "[Unknown Recipient]",
                date=date or "[Unknown Date]",
                tags=tags,
                body_markdown=body_content,
                body_format=body_format,
                attachments=attachments,
                saved_files=saved_files,
            )
        )
    return results


@mcp.tool(
    description="""Display email content with optimized token efficiency. Uses advanced libraries (email-reply-parser, selectolax, inscriptis) for clean text extraction with minimal token usage. Supports progressive rendering modes to control output verbosity. Optionally saves body and attachments to files."""
)
def show(
    query: str = Field(
        ...,
        description="A notmuch query to select the email(s) to display. Typically an 'id:<message-id>' query for a single email.",
    ),
    mode: str = Field(
        default="full",
        description="Rendering mode: 'headers' (metadata only), 'summary' (first 2000 chars), or 'full' (complete optimized content)",
    ),
    limit: int | None = Field(
        default=None,
        description="Maximum number of emails to return (helps prevent token overflow). If None, returns all emails.",
    ),
    include_excluded: bool = Field(
        default=False,
        description="Include emails with excluded tags (spam, deleted) that are normally hidden by notmuch.",
    ),
    save_attachments_to: str = Field(
        default="",
        description="Directory to save email body and attachments to. Body saved as .txt/.html, attachments saved with original filenames. Paths returned in saved_files field.",
    ),
) -> list[EmailContent]:
    """Show email content with optimized token-efficient processing."""
    return _show_email(
        query, mode, limit, include_excluded, save_to=save_attachments_to
    )


@mcp.tool(
    description="""Add or remove tags from emails by message ID. Primary method for organizing emails in notmuch."""
)
def tag(
    message_id: str = Field(
        ..., description="The notmuch message ID of the email to modify."
    ),
    add_tags: list[str] = Field(
        default_factory=list, description="A list of tags to add to the email."
    ),
    remove_tags: list[str] = Field(
        default_factory=list, description="A list of tags to remove from the email."
    ),
) -> TagResult:
    """Add or remove tags from a specific email using notmuch."""
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


@mcp.tool(
    description="Moves emails to an existing maildir folder (e.g., 'Trash', 'Archive'). Automatically finds the correct folder within the same email account (e.g., 'Hermes/Archive' for emails from 'Hermes/INBOX'). Will not create new folders - only moves to existing ones."
)
def move(
    message_ids: list[str] = Field(
        ...,
        description="A list of notmuch message IDs for the emails to be moved.",
        min_length=1,
    ),
    destination_folder: str = Field(
        ...,
        description="The destination maildir folder name (e.g., 'Trash', 'Archive'). Must be an existing folder. The tool will find the appropriate folder within the same email account.",
    ),
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

    # Fetch each message directly (more efficient than _show_email)
    messages = []
    for mid in thread_message_ids:
        try:
            msg = _get_message_from_raw_source(mid)
            # Get body without quote stripping for full thread context
            body_part = msg.get_body(preferencelist=("plain", "html"))
            if body_part:
                content = body_part.get_content()
                if body_part.get_content_type() == "text/html":
                    content = process_html_content(content)
                body = normalize_whitespace(ftfy.fix_text(content))
            else:
                body = ""

            messages.append(
                (
                    msg.get("Date", "[Unknown Date]"),
                    msg.get("From", "[Unknown Sender]"),
                    msg.get("Subject", "[No Subject]"),
                    body,
                )
            )
        except Exception:
            continue  # Skip messages that fail to parse

    return messages
