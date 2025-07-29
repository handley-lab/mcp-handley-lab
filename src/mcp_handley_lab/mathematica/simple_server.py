"""
Simplified Mathematica MCP Server - Working Version

This version keeps it simple and avoids the hanging issues.
"""

import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language import wlexpr

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Mathematica Tool")

# Global session - simple approach
_session: Optional[WolframLanguageSession] = None
_evaluation_count = 0


def get_session():
    """Get or create the global Wolfram session."""
    global _session, _evaluation_count
    
    if _session is None:
        try:
            _session = WolframLanguageSession('/usr/bin/WolframKernel')
            _evaluation_count = 0
            logger.info("✅ Wolfram session started")
        except Exception as e:
            logger.error(f"❌ Failed to start Wolfram session: {e}")
            raise RuntimeError(f"Could not start Wolfram session: {e}")
    
    return _session


@mcp.tool()
def evaluate(
    expression: str = Field(description="Wolfram Language expression to evaluate"),
    output_format: str = Field(default="Raw", description="Output format: 'Raw', 'InputForm', or 'OutputForm'")
) -> dict:
    """
    Evaluate a Wolfram Language expression in the persistent session.
    
    Examples:
    - Basic: "2 + 2"
    - Variables: "x = 5; y = x^2"
    - Functions: "Factor[x^4 - 1]"
    - Solve: "Solve[x^2 + 3*x + 2 == 0, x]"
    """
    global _evaluation_count
    
    try:
        session = get_session()
        
        # Evaluate the expression
        result = session.evaluate(wlexpr(expression))
        _evaluation_count += 1
        
        # Format based on output_format choice
        if output_format == "Raw":
            formatted_result = str(result)
        elif output_format == "InputForm":
            try:
                formatted_result = session.evaluate(wlexpr(f'ToString[{result}, InputForm]'))
            except:
                formatted_result = str(result)
        elif output_format == "OutputForm":
            try:
                formatted_result = session.evaluate(wlexpr(f'ToString[{result}, OutputForm]'))
            except:
                formatted_result = str(result)
        else:
            formatted_result = str(result)
        
        return {
            "result": formatted_result,
            "raw_result": str(result),
            "success": True,
            "evaluation_count": _evaluation_count,
            "expression": expression,
            "format_used": output_format
        }
        
    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        return {
            "result": f"Error: {str(e)}",
            "raw_result": None,
            "success": False,
            "evaluation_count": _evaluation_count,
            "expression": expression,
            "format_used": output_format,
            "error": str(e)
        }


@mcp.tool()
def session_info() -> dict:
    """Get information about the current Mathematica session."""
    global _evaluation_count
    
    try:
        if _session is None:
            return {
                "active": False,
                "evaluation_count": _evaluation_count,
                "message": "Session not started"
            }
        
        # Get basic session info
        version = _session.evaluate(wlexpr('$Version'))
        memory = _session.evaluate(wlexpr('MemoryInUse[]'))
        
        return {
            "active": True,
            "evaluation_count": _evaluation_count,
            "version": str(version),
            "memory_used": str(memory),
            "kernel_path": "/usr/bin/WolframKernel"
        }
        
    except Exception as e:
        return {
            "active": False,
            "evaluation_count": _evaluation_count,
            "error": str(e)
        }


@mcp.tool()
def clear_session() -> dict:
    """Clear all user-defined variables in the session."""
    try:
        session = get_session()
        
        # Clear user-defined symbols
        session.evaluate(wlexpr('ClearAll[Evaluate[Names["Global`*"]]]'))
        
        return {
            "success": True,
            "message": "Session variables cleared",
            "evaluation_count": _evaluation_count
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to clear session: {str(e)}",
            "error": str(e)
        }


@mcp.tool()
def restart_kernel() -> dict:
    """Restart the Mathematica kernel completely."""
    global _session, _evaluation_count
    
    try:
        # Close existing session
        if _session:
            _session.terminate()
        
        # Reset and create new session
        _session = None
        _evaluation_count = 0
        
        # Start new session
        get_session()
        
        return {
            "success": True,
            "message": "Kernel restarted successfully",
            "evaluation_count": _evaluation_count
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to restart kernel: {str(e)}",
            "error": str(e)
        }


# Initialize session when module loads
try:
    get_session()
except Exception as e:
    logger.warning(f"Could not initialize session on startup: {e}")


if __name__ == "__main__":
    mcp.run()