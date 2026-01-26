"""Email client MCP tool for msmtp, offlineimap, and notmuch integration.

Usage:
    from mcp_handley_lab.email import read, update, send, sync

    # Read/search emails
    emails = read(query="tag:inbox", mode="headers", limit=20)

    # Update email tags
    update(message_ids=["abc123"], action="tag", add_tags=["important"])

    # Move emails
    update(message_ids=["abc123"], action="move", destination_folder="Archive")

    # Send email (opens in Mutt for sign-off)
    result = send(to="alice@example.com", subject="Hello", body="Hi there")

    # Sync emails
    result = sync(mode="quick", account="Hermes")
"""

from mcp_handley_lab.email.mutt.shared import send
from mcp_handley_lab.email.notmuch.shared import read, update
from mcp_handley_lab.email.offlineimap.shared import sync

__all__ = ["read", "update", "send", "sync"]
__version__ = "0.1.0"
