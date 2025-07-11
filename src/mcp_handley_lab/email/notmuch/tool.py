"""Notmuch email search and indexing provider."""

import json
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

    message_id: str
    added_tags: list[str]
    removed_tags: list[str]


@mcp.tool(
    description="""Search emails using notmuch query language. Supports sender, subject, date ranges, tags, attachments, and body content filtering with boolean operators."""
)
def search(query: str, limit: int = 20) -> list[str]:
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
    
    body_part = msg.get_body(preferencelist=('html', 'plain'))

    if body_part:
        content = body_part.get_content()

        if body_part.get_content_type() == 'text/html':
            html_part = body_part
            soup = BeautifulSoup(content, 'html.parser')
            for s in soup(['script', 'style']):
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

    return {"body": body.strip() if body else "", "attachments": sorted(list(set(attachments))), "body_format": "html" if html_part else "text"}


@mcp.tool(
    description="""Display complete email content by message ID or notmuch query. Returns a structured object with headers and a clean, Markdown-formatted body for optimal LLM understanding."""
)
def show(query: str) -> list[EmailContent]:
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

        subject = reconstructed_msg.get("Subject", "No Subject")
        from_address = reconstructed_msg.get("From", "No Sender")
        to_address = reconstructed_msg.get("To", "No Recipient")
        date = reconstructed_msg.get("Date", "No Date")
        
        tag_cmd = ["notmuch", "search", "--output=tags", f"id:{message_id}"]
        tag_stdout, _ = run_command(tag_cmd)
        tags = [tag.strip() for tag in tag_stdout.decode().strip().split("\n") if tag.strip()]

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
def config(key: str = "") -> str:
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
def count(query: str) -> int:
    """Count emails matching a notmuch query."""
    cmd = ["notmuch", "count", query]

    stdout, stderr = run_command(cmd)
    count_result = stdout.decode().strip()
    return int(count_result)


@mcp.tool(
    description="""Add or remove tags from emails by message ID. Primary method for organizing emails in notmuch."""
)
def tag(
    message_id: str, add_tags: list[str] = [], remove_tags: list[str] = []
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
        message_id=message_id, 
        added_tags=add_tags, 
        removed_tags=remove_tags
    )