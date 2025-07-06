# Notes MCP Server Setup

## Persistent HTTP Server

The notes tool now supports running as a persistent HTTP server for dramatically improved performance.

### Performance Comparison

| Mode | First Call | Subsequent Calls | Memory | Features |
|------|------------|------------------|---------|----------|
| **Stdio (current)** | 1000ms+ | 1000ms+ | Low | Basic |
| **HTTP (new)** | 1000ms | **~10ms** | Medium | File watching, caching |

## Setup

### 1. Start the Persistent Server

```bash
# Default: localhost:8765
python scripts/start-notes-server.py

# Or with custom host/port
NOTES_SERVER_HOST=0.0.0.0 NOTES_SERVER_PORT=9000 python scripts/start-notes-server.py
```

### 2. Update Claude Code Configuration

Update your MCP settings to use the HTTP server instead of stdio:

**Before (stdio):**
```json
{
  "mcpServers": {
    "notes": {
      "command": "python",
      "args": ["-m", "mcp_handley_lab.notes"]
    }
  }
}
```

**After (HTTP):**
```json
{
  "mcpServers": {
    "notes": {
      "url": "http://localhost:8765"
    }
  }
}
```

### 3. Restart Claude Desktop

After changing the configuration, restart Claude Desktop to pick up the new server connection.

## Features

### ✅ Enabled with HTTP Server

- **Instant responses** after initial load
- **Real-time file watching** - changes to YAML files are detected automatically
- **Persistent state** - loaded notes stay in memory
- **Background optimization** - semantic search indexing
- **Logging & monitoring** - server activity is logged

### ⚠️ Stdio Mode Still Supported

The original stdio mode continues to work for compatibility, but performance will be slower.

## Monitoring

The server logs all activity:

```
2024-01-15 10:30:00 - INFO - 🚀 Notes server starting up...
2024-01-15 10:30:01 - INFO - ✅ Loaded 42 notes into memory
2024-01-15 10:30:01 - INFO - 👀 Watching global notes: /home/user/.mcp_handley_lab/notes
2024-01-15 10:30:01 - INFO - 🎉 Notes server ready!
2024-01-15 10:30:15 - INFO - 📝 New note detected: /home/user/.mcp_handley_lab/notes/new-idea.yaml
```

## Troubleshooting

### Server Won't Start

1. Check if port is already in use: `lsof -i :8765`
2. Try a different port: `NOTES_SERVER_PORT=9000 python scripts/start-notes-server.py`
3. Check logs for error messages

### Claude Code Can't Connect

1. Ensure server is running and shows "Notes server ready!"
2. Verify URL in MCP configuration matches server host:port
3. Restart Claude Desktop after configuration changes
4. Check firewall settings if using custom host

### File Changes Not Detected

1. Check logs for "Watching" messages on startup
2. Ensure note directories exist and are writable
3. File watching may not work on network drives - use local storage

## Development

For development, you can run both modes:
- HTTP server for interactive testing
- Stdio mode for automated testing

The same tool functions work in both modes.
