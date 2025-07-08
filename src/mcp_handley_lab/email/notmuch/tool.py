"""Notmuch email search and indexing provider."""
from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


@mcp.tool(
    description="""Search emails using notmuch query language. Supports sender, subject, date ranges, tags, attachments, and body content filtering with boolean operators."""
)
def search(query: str, limit: int = 20) -> str:
    """Search emails using notmuch query syntax."""
    cmd = ["notmuch", "search", "--limit", str(limit), query]

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    if not output:
        return f"Search results for '{query}':\n(no matches)"
    return f"Search results for '{query}':\n{output}"


@mcp.tool(
    description="""Display complete email content by message ID, thread ID, or notmuch query. Supports specific MIME parts for multipart messages."""
)
def show(query: str, part: str | None = None) -> str:
    """Show email content using notmuch show."""
    cmd = ["notmuch", "show"]

    cmd.extend(["--format=text"])

    if part:
        cmd.extend(["--part", part])

    cmd.append(query)

    stdout, stderr = run_command(cmd)
    return stdout.decode().strip()


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
def list_tags() -> str:
    """List all tags in the notmuch database."""
    stdout, stderr = run_command(["notmuch", "search", "--output=tags", "*"])
    output = stdout.decode().strip()
    if not output:
        return "Available tags:\n(none found)"
    tags = sorted(output.split("\n"))
    return "Available tags:\n" + "\n".join(f"- {tag}" for tag in tags if tag)


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
def count(query: str) -> str:
    """Count emails matching a notmuch query."""
    cmd = ["notmuch", "count", query]

    stdout, stderr = run_command(cmd)
    count_result = stdout.decode().strip()
    return f"Found {count_result} emails matching '{query}'"


@mcp.tool(
    description="""Add or remove tags from emails by message ID. Primary method for organizing emails in notmuch. Supports comma-separated tag lists."""
)
def tag(
    message_id: str, add_tags: str | None = None, remove_tags: str | None = None
) -> str:
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
    changes = []
    if add_tags:
        changes.append(f"added: {add_tags}")
    if remove_tags:
        changes.append(f"removed: {remove_tags}")

    return f"Tags updated for message {message_id} ({', '.join(changes)})"
