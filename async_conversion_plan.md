# Async Conversion Plan for MCP Tools

## Context
Converting MCP tools to async to enable concurrent operations and improve I/O efficiency. Starting with the simplest tool first.

## Research Findings
From Gemini analysis, key benefits of async MCP tools:
- **Performance**: Concurrent operations, I/O efficiency, higher throughput
- **Resource efficiency**: Better memory usage, simplified thread management
- **Scalability**: Handle multiple requests, backpressure management
- **Trade-offs**: Implementation complexity, testing challenges

## Target: JQ Tool (First Conversion)

**File**: `src/mcp_handley_lab/jq/tool.py`

**Why JQ tool is ideal for first async conversion**:
- Pure I/O operations (subprocess calls to jq CLI)
- No complex state management
- Minimal dependencies (subprocess, json, pathlib)
- Self-contained in single file
- All functions are independent with clear inputs/outputs

## Detailed Conversion Steps

### 1. Update Imports
```python
# Add to existing imports
import asyncio
```

### 2. Convert `_run_jq` Helper Function
**Current** (sync):
```python
def _run_jq(args: list[str], input_text: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["jq"] + args,
            input=input_text,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise ValueError(f"jq error: {e.stderr.strip()}")
    except FileNotFoundError:
        raise RuntimeError("jq command not found. Please install jq.")
```

**Target** (async):
```python
async def _run_jq(args: list[str], input_text: str | None = None) -> str:
    try:
        process = await asyncio.create_subprocess_exec(
            "jq", *args,
            stdin=asyncio.subprocess.PIPE if input_text else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = await process.communicate(input=input_text)
        
        if process.returncode != 0:
            raise ValueError(f"jq error: {stderr.strip()}")
            
        return stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("jq command not found. Please install jq.")
```

### 3. Convert All Tool Functions to Async

**Functions to convert** (6 total):
1. `query` - Main JSON querying function
2. `edit` - In-place JSON file editing
3. `read` - Read and pretty-print JSON files
4. `validate` - JSON syntax validation
5. `format` - JSON formatting
6. `server_info` - Server status

**Pattern for conversion**:
- Change `def function_name(...)` to `async def function_name(...)`
- Change `_run_jq(...)` calls to `await _run_jq(...)`
- Update any file I/O to async if needed (or keep sync since it's minimal)

### 4. Key Implementation Notes

**Error Handling**: Keep existing exception types (ValueError, RuntimeError) - FastMCP handles conversion to MCP errors automatically.

**File Operations**: The `_resolve_data` helper and file read operations can remain sync since they're fast local operations. Only subprocess calls need to be async.

**FastMCP Compatibility**: FastMCP automatically handles both async and sync tool functions, so the API surface remains identical to clients.

## Testing Strategy

### 1. Verify Existing Unit Tests Pass
```bash
python -m pytest tests/test_jq.py -v
```

### 2. JSON-RPC Functionality Test
Create test script to verify MCP protocol still works:
```python
#!/usr/bin/env python3
import subprocess
import json

def test_async_jq_jsonrpc():
    process = subprocess.Popen(
        ['python', '-m', 'mcp_handley_lab', 'jq'], 
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, text=True, bufsize=0)
    
    try:
        # Initialize
        init_request = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, 
                      "clientInfo": {"name": "test-client", "version": "1.0.0"}}
        }
        process.stdin.write(json.dumps(init_request) + '\n')
        process.stdin.flush()
        response = process.stdout.readline()
        print("Initialize:", response.strip())
        
        # Send initialized notification
        process.stdin.write('{"jsonrpc": "2.0", "method": "notifications/initialized"}\n')
        process.stdin.flush()
        
        # Test query tool
        query_request = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "query", "arguments": {"data": '{"test": "value"}', "filter": ".test"}}
        }
        process.stdin.write(json.dumps(query_request) + '\n')
        process.stdin.flush()
        response = process.stdout.readline()
        print("Query result:", response.strip())
        
        if '"isError":true' in response:
            print("❌ Async conversion failed!")
        else:
            print("✅ Async conversion successful!")
            
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__": test_async_jq_jsonrpc()
```

### 3. Performance Verification
Test concurrent operations to verify async benefits:
```python
import asyncio
import time

async def test_concurrent_queries():
    # Multiple concurrent jq operations should be faster than sequential
    start = time.time()
    # Test with multiple concurrent query calls
    end = time.time()
    print(f"Concurrent operations took: {end - start:.2f}s")
```

## Expected Benefits After Conversion

1. **Multiple JQ operations can run concurrently**
2. **Non-blocking I/O for CLI subprocess calls**
3. **Foundation for converting other tools to async**
4. **Same API surface** - FastMCP handles async/sync transparently

## Verification Checklist

- [ ] All imports updated
- [ ] `_run_jq` helper converted to async subprocess
- [ ] All 6 tool functions converted to `async def`
- [ ] Existing unit tests pass
- [ ] JSON-RPC functionality verified
- [ ] Performance improvement measured (optional)
- [ ] No breaking changes to client API

## Next Tools for Async Conversion

After JQ tool success:
1. **Vim tool** - Interactive operations, could benefit from async
2. **Code2Prompt tool** - CLI subprocess operations
3. **LLM tools** (Gemini/OpenAI) - Network I/O, high async benefit
4. **Google Calendar** - Network API calls
5. **Tool Chainer** - Orchestrates other tools, would benefit from async composition

## Notes

- FastMCP handles async/sync compatibility automatically
- No changes needed to client code
- Error handling patterns remain the same
- This is alpha software - breaking changes acceptable for improvements