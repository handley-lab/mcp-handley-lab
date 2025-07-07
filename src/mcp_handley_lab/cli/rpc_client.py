"""JSON-RPC client for communicating with MCP tools."""
import json
import subprocess
import time
from typing import Dict, Any, Optional, List
import click


class MCPToolClient:
    """Client for communicating with MCP tools via JSON-RPC."""
    
    def __init__(self, tool_name: str, command: str):
        self.tool_name = tool_name
        self.command = command
        self.process: Optional[subprocess.Popen] = None
        self._initialized = False
    
    def start_tool_server(self) -> bool:
        """Start the MCP tool server process."""
        try:
            # Start the tool server process using the command
            self.process = subprocess.Popen(
                [self.command],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0
            )
            
            # Give the process a moment to start
            time.sleep(0.1)
            
            # Check if process is still running
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                click.echo(f"Process {self.tool_name} exited early. Stderr: {stderr}", err=True)
                return False
            
            # Initialize the server
            if not self._initialize_server():
                self.cleanup()
                return False
                
            self._initialized = True
            return True
            
        except Exception as e:
            click.echo(f"Failed to start {self.tool_name} server: {e}", err=True)
            return False
    
    def _initialize_server(self) -> bool:
        """Send initialization messages to the MCP server."""
        try:
            # Send initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "mcp-cli", "version": "1.0.0"}
                }
            }
            
            self.process.stdin.write(json.dumps(init_request) + "\n")
            self.process.stdin.flush()
            
            # Read response with timeout
            response_line = self.process.stdout.readline()
            if not response_line:
                stderr = self.process.stderr.read() if self.process.stderr else "No stderr"
                click.echo(f"No response from {self.tool_name}. Stderr: {stderr}", err=True)
                return False
                
            try:
                response = json.loads(response_line.strip())
            except json.JSONDecodeError as e:
                click.echo(f"Invalid JSON response from {self.tool_name}: {response_line}. Error: {e}", err=True)
                return False
                
            if "error" in response:
                click.echo(f"Initialization error: {response['error']}", err=True)
                return False
            
            # Send initialized notification
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            self.process.stdin.write(json.dumps(initialized_notification) + "\n")
            self.process.stdin.flush()
            
            return True
            
        except Exception as e:
            click.echo(f"Failed to initialize {self.tool_name}: {e}", err=True)
            stderr = self.process.stderr.read() if self.process and self.process.stderr else "No stderr"
            if stderr:
                click.echo(f"Stderr: {stderr}", err=True)
            return False
    
    def _ensure_initialized(self) -> bool:
        """Starts the tool server if not already running. Returns success."""
        if not self._initialized:
            return self.start_tool_server()
        return True
    
    def list_tools(self) -> Optional[List[Dict[str, Any]]]:
        """Get list of available tools from the server."""
        if not self._ensure_initialized():
            return None
        
        try:
            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            
            response_line = self.process.stdout.readline()
            if not response_line:
                return None
                
            response = json.loads(response_line.strip())
            if "error" in response:
                click.echo(f"Error listing tools: {response['error']}", err=True)
                return None
                
            return response.get("result", {}).get("tools", [])
            
        except Exception as e:
            click.echo(f"Failed to list tools from {self.tool_name}: {e}", err=True)
            return None
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call a specific tool function."""
        if not self._ensure_initialized():
            return None
        
        try:
            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            
            response_line = self.process.stdout.readline()
            if not response_line:
                return None
                
            response = json.loads(response_line.strip())
            return response
            
        except Exception as e:
            click.echo(f"Failed to call {tool_name}: {e}", err=True)
            return None
    
    def cleanup(self):
        """Clean up the server process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            except:
                pass
            finally:
                self.process = None
                self._initialized = False


# Global clients dictionary
_CLIENTS: Dict[str, MCPToolClient] = {}


def get_tool_client(tool_name: str, command: str) -> MCPToolClient:
    """Get or create a client for a tool."""
    if tool_name not in _CLIENTS:
        _CLIENTS[tool_name] = MCPToolClient(tool_name, command)
    return _CLIENTS[tool_name]


def cleanup_clients():
    """Clean up all clients."""
    for client in _CLIENTS.values():
        client.cleanup()
    _CLIENTS.clear()