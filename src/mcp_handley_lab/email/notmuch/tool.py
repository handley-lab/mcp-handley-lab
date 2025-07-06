"""Notmuch email search and indexing provider."""
from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


@mcp.tool(description="""Search emails using notmuch with powerful query syntax.

Supports the full notmuch query language for precise email filtering and search.

Query Syntax:
- Simple terms: 'subject:meeting' or 'from:alice@example.com'
- Date ranges: 'date:2024-01-01..2024-01-31'
- Boolean operators: 'from:alice AND subject:project'
- Tag filtering: 'tag:inbox AND NOT tag:spam'
- Attachment search: 'attachment:*.pdf'
- Body content: 'body:"quarterly report"'

Examples:
```python
# Find unread emails from specific sender
search("from:boss@company.com AND tag:unread")

# Search for emails with attachments in date range
search("date:2024-01-01..2024-01-31 AND attachment:*")

# Find project emails not in archive
search("subject:project AND NOT tag:archive")

# Search in email body for specific terms
search('body:"quarterly report" OR body:"Q4 results"')
```""")
def search(query: str, limit: int = 20) -> str:
    """Search emails using notmuch query syntax."""
    cmd = ["notmuch", "search", "--limit", str(limit), query]

    stdout, stderr = run_command(cmd)
    output = stdout.decode().strip()
    if not output:
        return f"Search results for '{query}':\n(no matches)"
    return f"Search results for '{query}':\n{output}"


@mcp.tool(description="""Display full email content including headers, body, and attachments.

Shows the complete email message with all metadata, headers, and content. Can display specific parts of multipart messages.

Key Parameters:
- query: Message ID, thread ID, or notmuch query to identify the email
- part: Optional MIME part number to display specific attachments or content sections

Behavior:
- Returns complete email with headers, body, and attachment information
- Handles multipart messages with proper MIME part separation
- Shows attachment names and types without downloading content
- Displays in human-readable text format

Examples:
```python
# Show complete email by message ID
show("id:20241201.123456@example.com")

# Show latest email from specific sender
show("from:alice@example.com")

# Display specific attachment part
show("id:20241201.123456@example.com", part="2")

# Show first email in thread
show("thread:0000000000000001")
```""")
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


@mcp.tool(description="""Index newly received emails and update the notmuch database.

Scans configured mail directories for new emails and adds them to the notmuch database. This must be run after receiving new emails to make them searchable.

Behavior:
- Scans all configured mail directories for new messages
- Adds new emails to the searchable database index
- Updates tags based on initial tagging rules
- Reports statistics on newly indexed messages
- Required after email synchronization to make messages searchable

Examples:
```python
# Index newly received emails
new()

# Typical workflow:
# 1. Run email sync (offlineimap/fetchmail)
# 2. Run notmuch new to index new messages
# 3. Search and manage indexed emails
```

Note: This should be run after email synchronization tools like offlineimap to ensure new messages are searchable.""")
def new() -> str:
    """Index newly received emails with notmuch new."""
    stdout, stderr = run_command(["notmuch", "new"])
    output = stdout.decode().strip()
    return f"Notmuch database updated:\n{output}"


@mcp.tool(description="""List all tags currently used in the notmuch database.

Returns a comprehensive list of all tags that have been applied to emails in the database. Useful for understanding your tagging system and available filters.

Behavior:
- Scans entire database for unique tags
- Returns alphabetically sorted list
- Includes both system tags (inbox, unread, sent) and custom tags
- Shows tag usage statistics if available

Common Tags:
- inbox: New messages (usually auto-applied)
- unread: Unread messages
- sent: Sent messages
- draft: Draft messages
- spam: Spam messages
- archive: Archived messages
- flagged: Flagged/starred messages

Examples:
```python
# List all available tags
list_tags()

# Common usage:
# 1. List tags to understand your email organization
# 2. Use tags in search queries
# 3. Plan tag management strategy
```""")
def list_tags() -> str:
    """List all tags in the notmuch database."""
    stdout, stderr = run_command(["notmuch", "search", "--output=tags", "*"])
    output = stdout.decode().strip()
    if not output:
        return "Available tags:\n(none found)"
    tags = sorted(output.split("\n"))
    return "Available tags:\n" + "\n".join(f"- {tag}" for tag in tags if tag)


@mcp.tool(description="""Retrieve notmuch configuration settings and database information.

Displays notmuch configuration values, database paths, and system settings. Useful for troubleshooting and understanding your email setup.

Key Parameters:
- key: Optional specific configuration key to retrieve (e.g., 'database.path', 'user.name')

Behavior:
- Without key: Shows all configuration settings
- With key: Shows specific configuration value
- Includes database path, user information, and indexing settings
- Useful for debugging configuration issues

Common Configuration Keys:
- database.path: Location of notmuch database
- user.name: Your name for email headers
- user.primary_email: Primary email address
- user.other_email: Additional email addresses
- new.tags: Tags applied to new messages

Examples:
```python
# Show all configuration
config()

# Get specific setting
config("database.path")

# Check user configuration
config("user.name")
config("user.primary_email")

# View tagging rules
config("new.tags")
```""")
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


@mcp.tool(description="""Count emails matching a notmuch query without retrieving content.

Provides fast counting of emails matching search criteria. Useful for statistics, monitoring, and query validation without the overhead of fetching full results.

Key Parameters:
- query: Same query syntax as search() function

Behavior:
- Returns numerical count only (no email content)
- Much faster than search() for large result sets
- Useful for monitoring email volumes and trends
- Can be used to validate query syntax before full search

Examples:
```python
# Count unread emails
count("tag:unread")

# Count emails from specific sender
count("from:boss@company.com")

# Count emails in date range
count("date:2024-01-01..2024-01-31")

# Count emails with attachments
count("attachment:*")

# Monitor email volumes
count("date:today")
count("date:yesterday")
```

Useful for:
- Email volume monitoring
- Query validation before full search
- Performance optimization for large mailboxes
- Generating email statistics""")
def count(query: str) -> str:
    """Count emails matching a notmuch query."""
    cmd = ["notmuch", "count", query]

    stdout, stderr = run_command(cmd)
    count_result = stdout.decode().strip()
    return f"Found {count_result} emails matching '{query}'"


@mcp.tool(description="""Add or remove tags from emails for organization and workflow management.

Modifies tags on emails to organize, categorize, and manage your email workflow. Tags are the primary method for email organization in notmuch.

Key Parameters:
- message_id: Email message ID to modify
- add_tags: Comma-separated list of tags to add
- remove_tags: Comma-separated list of tags to remove

Behavior:
- Modifies tags on specified email message
- Can add and remove tags in single operation
- Changes are immediate and permanent
- Supports batch operations with multiple tags

Tag Management Strategy:
- inbox: For new, unprocessed emails
- unread: For unread messages
- archive: For processed emails
- flagged: For important emails
- project-name: For project-specific emails
- todo: For emails requiring action

Examples:
```python
# Mark email as read and archive
tag("20241201.123456@example.com", 
    remove_tags="unread,inbox", 
    add_tags="archive")

# Flag important email
tag("20241201.123456@example.com", 
    add_tags="flagged,important")

# Organize by project
tag("20241201.123456@example.com", 
    add_tags="project-alpha,todo")

# Remove spam tag
tag("20241201.123456@example.com", 
    remove_tags="spam")
```""")
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


