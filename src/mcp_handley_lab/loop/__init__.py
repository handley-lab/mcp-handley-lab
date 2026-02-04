"""MCP Loop - REPL orchestration with parent-child model.

Uses Unix process model: each loop has loop_id (like PID) and parent_id (like PPID).
No access control - if you know the loop_id, you can operate on it.
"""
