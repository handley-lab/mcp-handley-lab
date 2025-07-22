"""Notmuch email search and indexing provider."""

import json
import os
import re
from pathlib import Path
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from pydantic import BaseModel, Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


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


class TagResult(BaseModel):
    """Result of tag operation."""

    message_id: str = Field(..., description="The notmuch message ID that was tagged.")
    added_tags: list[str] = Field(..., description="A list of tags that were added to the message.")
    removed_tags: list[str] = Field(..., description="A list of tags that were removed from the message.")


class AttachmentExtractionResult(BaseModel):
    """Result of a successful attachment extraction operation."""

    message_id: str = Field(..., description="The notmuch message ID from which attachments were extracted.")
    saved_files: list[str] = Field(
        ...,
        description="A list of absolute paths to the saved attachment files."
    )
    message: str = Field(..., description="Status message describing the extraction result.")


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
    status: str = Field(
        ..., description="A summary of the move operation."
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
        default=20,
        description="The maximum number of message IDs to return.",
        gt=0,
    ),
) -> list[str]:
    """Search emails using notmuch query syntax."""
    cmd = ["notmuch", "search", "--limit", str(limit), query]
    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    return [line.strip() for line in output.split("\n") if line.strip()]


def _get_message_from_raw_source(message_id: str) -> EmailMessage:
    """Fetches the raw source of an email from notmuch and parses it into an EmailMessage object."""
    raw_email_bytes, _ = run_command(
        ["notmuch", "show", "--format=raw", f"id:{message_id}"]
    )
    parser = BytesParser(policy=policy.default)
    return parser.parsebytes(raw_email_bytes)


def parse_email_content(msg: EmailMessage):
    """Parses an EmailMessage to extract the best text body and attachments."""
    body = None
    attachments = []
    html_part = None

    body_part = msg.get_body(preferencelist=("html", "plain"))

    if body_part:
        content = body_part.get_content()

        if body_part.get_content_type() == "text/html":
            html_part = body_part
            soup = BeautifulSoup(content, "html.parser")
            for s in soup(["script", "style"]):
                s.decompose()
            body = md(str(soup), heading_style="ATX")
        else:
            body = content
    elif not msg.is_multipart() and not msg.is_attachment():
        body = msg.get_content()

    for part in msg.walk():
        if part.get_filename() and part is not body_part:
            attachment_info = f"{part.get_filename()} ({part.get_content_type()})"
            attachments.append(attachment_info)

    return {
        "body": body.strip() if body else "",
        "attachments": sorted(set(attachments)),
        "body_format": "html" if html_part else "text",
    }


@mcp.tool(
    description="""Display complete email content by message ID or notmuch query. Returns a structured object with headers and a clean, Markdown-formatted body for optimal LLM understanding."""
)
def show(
    query: str = Field(
        ...,
        description="A notmuch query to select the email(s) to display. Typically an 'id:<message-id>' query for a single email.",
    )
) -> list[EmailContent]:
    """Show email content by fetching raw email sources and parsing with Python's email library."""
    cmd = ["notmuch", "search", "--format=json", "--output=messages", query]
    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    message_ids = json.loads(output)

    results = []
    for message_id in message_ids:
        reconstructed_msg = _get_message_from_raw_source(message_id)

        extracted_data = parse_email_content(reconstructed_msg)
        body_markdown = extracted_data["body"]
        body_format = extracted_data["body_format"]
        attachments = extracted_data["attachments"]

        subject = reconstructed_msg["Subject"]
        from_address = reconstructed_msg["From"]
        to_address = reconstructed_msg["To"]
        date = reconstructed_msg["Date"]

        tag_cmd = ["notmuch", "search", "--output=tags", f"id:{message_id}"]
        tag_stdout, _ = run_command(tag_cmd)
        tags = [
            tag.strip()
            for tag in tag_stdout.decode().strip().split("\n")
            if tag.strip()
        ]

        results.append(
            EmailContent(
                id=message_id,
                subject=subject,
                from_address=from_address,
                to_address=to_address,
                date=date,
                tags=tags,
                body_markdown=body_markdown.strip(),
                body_format=body_format,
                attachments=attachments,
            )
        )
    return results


@mcp.tool(
    description="""Index newly received emails into notmuch database. Required after email sync to make new messages searchable. Updates tags per initial rules."""
)
def new() -> str:
    """Index newly received emails with notmuch new."""
    stdout, stderr = run_command(["notmuch", "new"])
    output = stdout.decode().strip()
    return f"Notmuch database updated:\n{output}"


@mcp.tool(
    description="""List all tags in notmuch database. Shows system tags (inbox, unread, sent) and custom tags. Useful for understanding organization and planning searches."""
)
def list_tags() -> list[str]:
    """List all tags in the notmuch database."""
    stdout, stderr = run_command(["notmuch", "search", "--output=tags", "*"])
    output = stdout.decode().strip()
    return sorted([tag.strip() for tag in output.split("\n") if tag.strip()])


@mcp.tool(
    description="""Retrieve notmuch configuration settings. Shows all settings or specific key. Useful for troubleshooting database path, user info, and tagging rules."""
)
def config(
    key: str = Field(
        default="",
        description="An optional specific configuration key to retrieve (e.g., 'database.path'). If omitted, all configurations are listed.",
    )
) -> str:
    """Get notmuch configuration values."""
    cmd = ["notmuch", "config", "list"]

    if key:
        cmd = ["notmuch", "config", "get", key]

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    if key:
        return f"{key} = {output}"
    return f"Notmuch configuration:\n{output}"


@mcp.tool(
    description="""Count emails matching notmuch query without retrieving content. Fast way to validate queries and monitor email volumes."""
)
def count(
    query: str = Field(
        ...,
        description="A valid notmuch search query to count matching emails. Example: 'tag:unread'.",
    )
) -> int:
    """Count emails matching a notmuch query."""
    cmd = ["notmuch", "count", query]

    stdout, stderr = run_command(cmd)
    count_result = stdout.decode().strip()
    return int(count_result)


@mcp.tool(
    description="""Add or remove tags from emails by message ID. Primary method for organizing emails in notmuch."""
)
def tag(
    message_id: str = Field(
        ..., description="The notmuch message ID of the email to modify."
    ),
    add_tags: list[str] = Field(
        default=None, description="A list of tags to add to the email."
    ),
    remove_tags: list[str] = Field(
        default=None, description="A list of tags to remove from the email."
    ),
) -> TagResult:
    """Add or remove tags from a specific email using notmuch."""
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


@mcp.tool(
    description="Extracts and saves one or all attachments from a specific email. If 'filename' is provided, only that attachment is saved. Files are saved to 'output_dir', which defaults to '~/Downloads/email_attachments'. Returns a result object with a list of absolute paths to the saved files."
)
def extract_attachments(
    message_id: str = Field(
        ..., description="The notmuch message ID of the email containing the attachments."
    ),
    output_dir: str = Field(
        default="",
        description="The directory to save attachments to. Defaults to '~/Downloads/email_attachments'.",
    ),
    filename: str = Field(
        default="",
        description="The specific filename of the attachment to extract. If omitted, all attachments are extracted.",
    ),
) -> AttachmentExtractionResult:
    """
    Extracts attachments from an email, failing loudly if the email or attachment isn't found.
    """
    msg = _get_message_from_raw_source(message_id)

    if filename:
        if match := re.match(r"(.+?)\s+\(.+\)", filename):
            filename = match.group(1)

    save_path = Path(output_dir or '~/Downloads/email_attachments').expanduser()
    save_path.mkdir(parents=True, exist_ok=True)

    saved_files = []
    found_attachments = []
    
    for part in msg.walk():
        if part_filename := part.get_filename():
            if not filename or part_filename == filename:
                found_attachments.append(part)

    if filename and not found_attachments:
        raise FileNotFoundError(f"Attachment '{filename}' not found in email id:{message_id}.")
        
    if not found_attachments:
        return AttachmentExtractionResult(
            message_id=message_id,
            saved_files=[],
            message="No attachments found in the email."
        )

    for part in found_attachments:
        part_filename = part.get_filename()
        clean_filename = re.sub(r'[\\/*?:"<>|]', "_", Path(part_filename).name)
        file_path = save_path / clean_filename
        
        counter = 1
        stem, suffix = file_path.stem, file_path.suffix
        while file_path.exists():
            file_path = save_path / f"{stem}_{counter}{suffix}"
            counter += 1
            
        if payload := part.get_payload(decode=True):
            file_path.write_bytes(payload)
            saved_files.append(str(file_path))

    return AttachmentExtractionResult(
        message_id=message_id,
        saved_files=saved_files,
        message=f"Successfully saved {len(saved_files)} attachment(s) to {save_path}.",
    )


@mcp.tool(
    description="Moves emails to a different maildir folder (e.g., 'Trash', 'Archive'). This physically moves the email files on disk and updates the notmuch index. The destination folder will be created if it doesn't exist."
)
def move(
    message_ids: list[str] = Field(
        ...,
        description="A list of notmuch message IDs for the emails to be moved.",
        min_length=1,
    ),
    destination_folder: str = Field(
        ...,
        description="The destination maildir folder name (e.g., 'Trash', 'Archive'). The folder will be created if it doesn't exist.",
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
    
    source_files = [line.strip() for line in stdout.decode().strip().split("\n") if line.strip()]

    if not source_files:
        raise FileNotFoundError(f"No email files found for the given message IDs: {message_ids}")

    # Get maildir root and move files
    db_path_str, _ = run_command(["notmuch", "config", "get", "database.path"])
    maildir_root = Path(db_path_str.decode().strip())
    # Per maildir standard, new mail is placed in the 'new' subfolder
    destination_dir = maildir_root / destination_folder / "new"

    for file_path in source_files:
        source_path = Path(file_path)
        destination_path = destination_dir / source_path.name
        
        # os.renames robustly moves the file and creates intermediate
        # directories (like 'Trash' and 'Trash/new') if they don't exist.
        try:
            os.renames(source_path, destination_path)
        except OSError as e:
            raise OSError(f"Failed to move {source_path} to {destination_path}: {e}") from e

    # Update the notmuch index to discover the moved files
    new()

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
