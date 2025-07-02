"""Custom exceptions for MCP tools."""


class UserCancelledError(Exception):
    """Raised when a tool execution is cancelled by the user."""
    pass