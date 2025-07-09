"""Notmuch email search and indexing provider."""

import json

import html2text
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
    if not output:
        return []
    return [line.strip() for line in output.split("\n") if line.strip()]


@mcp.tool(
    description="""Display complete email content by message ID or notmuch query. Returns a structured object with headers and a clean, Markdown-formatted body for optimal LLM understanding."""
)
def show(query: str) -> list[EmailContent]:
    """
    Show email content using notmuch show, parsing the best available body part.
    It prefers HTML content and converts it to Markdown.
    """
    # Use --format=json to get structured data, including MIME parts
    cmd = ["notmuch", "show", "--format=json", "--include-html", query]

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()

    if not output:
        return []

    try:
        # notmuch can return multiple JSON objects for a multi-message query
        emails_json = json.loads(output)
    except json.JSONDecodeError:
        # Handle cases where output might not be valid JSON
        return []

    # Ensure emails_json is a list
    if not isinstance(emails_json, list):
        emails_json = [emails_json]

    results = []
    h = html2text.HTML2Text()
    h.body_width = 0  # Don't wrap lines

    for thread in emails_json:
        for message_list in thread:
            for email_data in message_list:
                # Skip entries that are not dictionaries (e.g., nested lists)
                if not isinstance(email_data, dict):
                    continue

                # Skip entries without headers (these are typically metadata)
                if not email_data.get("headers"):
                    continue

                # Extract headers
                headers = email_data.get("headers", {})
                subject = headers.get("Subject", "No Subject")
                from_address = headers.get("From", "No Sender")
                to_address = headers.get("To", "No Recipient")
                date = headers.get("Date", "No Date")
                message_id = email_data.get("id", "No ID")
                tags = email_data.get("tags", [])

                # Find the best body content
                body_parts = email_data.get("body", [])
                html_part = None
                text_part = None
                attachments = []

                for part in body_parts:
                    content_type = part.get("content-type", "")
                    if "text/html" in content_type and not html_part:
                        html_part = part.get("content", "")
                    elif "text/plain" in content_type and not text_part:
                        text_part = part.get("content", "")
                    else:
                        # Basic attachment detection
                        filename = part.get("filename")
                        if filename:
                            attachments.append(
                                f"{filename} ({part.get('content-type')})"
                            )

                body_markdown = ""
                body_format = "none"

                if html_part:
                    body_markdown = h.handle(html_part)
                    body_format = "html"
                elif text_part:
                    body_markdown = text_part
                    body_format = "text"
                else:
                    body_markdown = "[No readable body found in this email]"

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
    if not output:
        return []
    return sorted([tag.strip() for tag in output.split("\n") if tag.strip()])


@mcp.tool(
    description="""Retrieve notmuch configuration settings. Shows all settings or specific key. Useful for troubleshooting database path, user info, and tagging rules."""
)
def config(key: str | None = None) -> str:
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
    description="""Add or remove tags from emails by message ID. Primary method for organizing emails in notmuch. Supports comma-separated tag lists."""
)
def tag(
    message_id: str, add_tags: str | None = None, remove_tags: str | None = None
) -> TagResult:
    """Add or remove tags from a specific email using notmuch."""
    if not add_tags and not remove_tags:
        raise ValueError("Must specify either add_tags or remove_tags")

    cmd = ["notmuch", "tag"]

    if add_tags:
        for tag in add_tags.split(","):
            tag = tag.strip()
            if tag:
                cmd.append(f"+{tag}")

    if remove_tags:
        for tag in remove_tags.split(","):
            tag = tag.strip()
            if tag:
                cmd.append(f"-{tag}")

    cmd.append(f"id:{message_id}")

    stdout, stderr = run_command(cmd)
    added_list = [tag.strip() for tag in add_tags.split(",")] if add_tags else []
    removed_list = (
        [tag.strip() for tag in remove_tags.split(",")] if remove_tags else []
    )

    return TagResult(
        message_id=message_id, added_tags=added_list, removed_tags=removed_list
    )
