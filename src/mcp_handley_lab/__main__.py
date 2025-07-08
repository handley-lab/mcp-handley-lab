"""Unified entry point for all MCP tools."""
import importlib
import sys
from pathlib import Path


def get_available_tools():
    """Discover available tools by finding directories with tool.py files."""
    tools_dir = Path(__file__).parent

    tool_files = sorted(tools_dir.rglob("tool.py"))

    tools = []
    for tool_file in tool_files:
        relative_path = tool_file.parent.relative_to(tools_dir)
        tools.append(".".join(relative_path.parts))

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

    module_path = f"mcp_handley_lab.{tool_name}.tool"
    tool_module = importlib.import_module(module_path)

    if hasattr(tool_module, "mcp"):
        tool_module.mcp.run()
    else:
        print(f"Error: Tool '{tool_name}' does not have an MCP server instance.")
        sys.exit(1)


if __name__ == "__main__":
    main()
