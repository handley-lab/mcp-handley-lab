"""Unified entry point for all MCP tools."""
import importlib
import sys
import traceback
from pathlib import Path


def get_available_tools():
    """Discover available tools by finding directories with tool.py files."""
    tools_dir = Path(__file__).parent

    # Use rglob to find all 'tool.py' files recursively
    tool_files = sorted(tools_dir.rglob("tool.py"))

    tools = []
    for tool_file in tool_files:
        # Calculate the relative path from tools_dir to the parent directory of tool.py
        # e.g., 'src/mcp_handley_lab/agent/tool.py' -> 'agent'
        # 'src/mcp_handley_lab/llm/gemini/tool.py' -> 'llm.gemini'
        relative_path = tool_file.parent.relative_to(tools_dir)

        # Convert path segments to dot-separated module name
        tools.append(".".join(relative_path.parts))

    # Filter out any empty strings that might result from edge cases
    return sorted(t for t in tools if t)


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
        if hasattr(tool_module, "mcp"):
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
    except KeyboardInterrupt:
        print("\nTool execution cancelled by user.")
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception:
        print(
            f"An unexpected error occurred while running tool '{tool_name}':",
            file=sys.stderr,
        )
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
