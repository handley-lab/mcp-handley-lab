"""Run the Tool Chainer server."""
from .tool import mcp

def main():
    """Entry point for the Tool Chainer server."""
    mcp.run()

if __name__ == "__main__":
    main()