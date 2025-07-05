"""Notmuch email search and indexing provider."""
from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


@mcp.tool(description="Search emails using notmuch.")
def search(query: str, limit: int = 20) -> str:
    """Search emails using notmuch query syntax."""
    cmd = ["notmuch", "search", "--limit", str(limit), query]

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    if not output:
        return f"Search results for '{query}':\n(no matches)"
    return f"Search results for '{query}':\n{output}"


@mcp.tool(description="Show email content for a specific message ID or query.")
def show(query: str, part: str | None = None) -> str:
    """Show email content using notmuch show."""
    cmd = ["notmuch", "show"]

    # Add format options for plain text
    cmd.extend(["--format=text"])

    if part:
        cmd.extend(["--part", part])

    cmd.append(query)

    stdout, stderr = run_command(cmd)
    return stdout.decode().strip()


@mcp.tool(description="Create a new notmuch database or update existing one.")
def new() -> str:
    """Index newly received emails with notmuch new."""
    stdout, stderr = run_command(["notmuch", "new"])
    output = stdout.decode().strip()
    return f"Notmuch database updated:\n{output}"


@mcp.tool(description="List all tags in the notmuch database.")
def list_tags() -> str:
    """List all tags in the notmuch database."""
    stdout, stderr = run_command(["notmuch", "search", "--output=tags", "*"])
    output = stdout.decode().strip()
    if not output:
        return "Available tags:\n(none found)"
    tags = sorted(output.split("\n"))
    return "Available tags:\n" + "\n".join(f"- {tag}" for tag in tags if tag)


@mcp.tool(description="Get configuration information from notmuch.")
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


@mcp.tool(description="Count emails matching a notmuch query.")
def count(query: str) -> str:
    """Count emails matching a notmuch query."""
    cmd = ["notmuch", "count", query]

    stdout, stderr = run_command(cmd)
    count_result = stdout.decode().strip()
    return f"Found {count_result} emails matching '{query}'"


@mcp.tool(description="Add or remove tags from emails using notmuch.")
def tag(
    message_id: str, add_tags: str | None = None, remove_tags: str | None = None
) -> str:
    """Add or remove tags from a specific email using notmuch."""
    if not add_tags and not remove_tags:
        raise ValueError("Must specify either add_tags or remove_tags")

    cmd = ["notmuch", "tag"]

    # Add tags to add
    if add_tags:
        for tag in add_tags.split(","):
            tag = tag.strip()
            if tag:
                cmd.append(f"+{tag}")

    # Add tags to remove
    if remove_tags:
        for tag in remove_tags.split(","):
            tag = tag.strip()
            if tag:
                cmd.append(f"-{tag}")

    # Add message ID
    cmd.append(f"id:{message_id}")

    stdout, stderr = run_command(cmd)
    changes = []
    if add_tags:
        changes.append(f"added: {add_tags}")
    if remove_tags:
        changes.append(f"removed: {remove_tags}")

    return f"Tags updated for message {message_id} ({', '.join(changes)})"


