"""Unified entry point for all MCP tools."""
import sys
import runpy
import importlib
from pathlib import Path


def get_available_tools():
    """Discover available tools by finding directories with tool.py files."""
    tools_dir = Path(__file__).parent
    tools = []
    
    # Check direct tool directories
    for item in tools_dir.iterdir():
        if item.is_dir() and (item / "tool.py").exists():
            tools.append(item.name)
    
    # Check LLM subdirectories
    llm_dir = tools_dir / "llm"
    if llm_dir.exists():
        for item in llm_dir.iterdir():
            if item.is_dir() and (item / "tool.py").exists():
                tools.append(f"llm.{item.name}")
    
    return sorted(tools)


def show_help():
    """Display help message with available tools."""
    tools = get_available_tools()
    
    print("Usage: python -m mcp_handley_lab <tool_name>")
    print("\nAvailable tools:")
    for tool in tools:
        print(f"  - {tool}")
    
    print("\nExamples:")
    print("  python -m mcp_handley_lab jq")
    print("  python -m mcp_handley_lab llm.gemini") 
    print("  python -m mcp_handley_lab google_calendar")


def main():
    """Main entry point."""
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help", "help"]:
        show_help()
        sys.exit(0)
    
    tool_name = sys.argv[1]
    
    # Try to import and run the tool
    try:
        module_path = f"mcp_handley_lab.{tool_name}.tool"
        tool_module = importlib.import_module(module_path)
        
        # Run the tool's main function
        if hasattr(tool_module, 'mcp'):
            tool_module.mcp.run()
        else:
            print(f"Error: Tool '{tool_name}' does not have an MCP server instance.")
            sys.exit(1)
            
    except ModuleNotFoundError:
        available_tools = get_available_tools()
        print(f"Error: Tool '{tool_name}' not found.")
        print(f"Available tools: {', '.join(available_tools)}")
        print("Use 'python -m mcp_handley_lab --help' for more information.")
        sys.exit(1)
    except Exception as e:
        print(f"Error running tool '{tool_name}': {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()