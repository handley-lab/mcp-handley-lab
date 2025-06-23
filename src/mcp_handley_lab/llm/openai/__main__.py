"""Run the OpenAI tool server."""
from .tool import mcp

def main():
    """Entry point for the OpenAI tool server."""
    mcp.run()

if __name__ == "__main__":
    main()