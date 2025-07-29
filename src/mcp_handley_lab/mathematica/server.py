"""
Mathematica MCP Server

Provides MCP tools for interacting with Wolfram Mathematica through a persistent kernel session.
Enables LLM-driven mathematical workflows with true REPL behavior.
"""

import logging
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from .kernel_manager import get_kernel_manager, initialize_kernel, shutdown_kernel


logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Mathematica Tool")


class EvaluationResult(BaseModel):
    """Result of a Mathematica evaluation."""
    result: str = Field(description="The formatted result of the evaluation")
    success: bool = Field(description="Whether the evaluation succeeded")
    evaluation_count: int = Field(description="Number of evaluations in this session")
    expression: str = Field(description="The original expression that was evaluated")
    format_used: str = Field(description="The output format that was used")
    error: Optional[str] = Field(None, description="Error message if evaluation failed")


class SessionInfo(BaseModel):
    """Information about the current Mathematica session."""
    active: bool = Field(description="Whether the kernel session is active")
    evaluation_count: int = Field(description="Number of evaluations performed")
    version: Optional[str] = Field(None, description="Wolfram kernel version")
    memory_used: Optional[str] = Field(None, description="Memory currently in use")
    kernel_id: Optional[str] = Field(None, description="Kernel process ID")
    context_keys: List[str] = Field(default_factory=list, description="Available context keys")
    kernel_path: Optional[str] = Field(None, description="Path to the Wolfram kernel")
    default_format: Optional[str] = Field(None, description="Default output format")
    error: Optional[str] = Field(None, description="Error message if session info unavailable")


@mcp.tool()
def evaluate(
    expression: str = Field(description="Wolfram Language expression to evaluate"),
    output_format: str = Field(
        default="OutputForm", 
        description="Output format: 'OutputForm', 'InputForm', 'TeXForm', 'TraditionalForm', or 'Raw'"
    ),
    store_context: Optional[str] = Field(
        None, 
        description="Optional key to store this result in session context for later reference"
    )
) -> EvaluationResult:
    """
    Evaluate a Wolfram Language expression in the persistent kernel session.
    
    This is the main tool for LLM-driven mathematical workflows. The session persists
    across multiple tool calls, allowing for true REPL behavior where variables,
    functions, and results are maintained between evaluations.
    
    Examples:
    - Basic math: "2 + 2"
    - Define variables: "x = 5; y = x^2"
    - Use history: "Expand[%]" (% refers to the last result)
    - Complex operations: "Factor[x^4 - 1]"
    - Solve equations: "Solve[x^2 + 3*x + 2 == 0, x]"
    - Integration: "Integrate[x^2 + 3*x + 1, x]"
    - Plot functions: "Plot[Sin[x], {x, 0, 2*Pi}]"
    """
    manager = get_kernel_manager()
    
    try:
        result = manager.evaluate(
            expression=expression,
            output_format=output_format,
            store_context=store_context
        )
        
        return EvaluationResult(
            result=result['formatted'],
            success=result['success'],
            evaluation_count=result['evaluation_count'],
            expression=result['expression'],
            format_used=result['format_used'],
            error=result.get('error')
        )
        
    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        return EvaluationResult(
            result=f"Error: {str(e)}",
            success=False,
            evaluation_count=0,
            expression=expression,
            format_used=output_format,
            error=str(e)
        )


@mcp.tool()
def session_info() -> SessionInfo:
    """
    Get information about the current Mathematica kernel session.
    
    Returns details about the active session including version, memory usage,
    evaluation count, and available context keys. Useful for monitoring
    session health and debugging.
    """
    manager = get_kernel_manager()
    
    try:
        info = manager.get_session_info()
        return SessionInfo(**info)
    except Exception as e:
        logger.error(f"Session info error: {e}")
        return SessionInfo(
            active=False,
            evaluation_count=0,
            error=str(e)
        )


@mcp.tool() 
def clear_session(
    keep_builtin: bool = Field(
        True, 
        description="If True, preserve built-in Wolfram functions. If False, clear everything."
    )
) -> Dict[str, Any]:
    """
    Clear the Mathematica session variables and history.
    
    This resets the session state while keeping the kernel running. Useful for
    starting fresh calculations or clearing memory when the session becomes
    cluttered with intermediate results.
    
    Args:
        keep_builtin: If True (default), only clears user-defined symbols.
                     If False, performs a complete reset including built-ins.
    
    Returns:
        Success status and session information.
    """
    manager = get_kernel_manager()
    
    try:
        success = manager.clear_session(keep_builtin=keep_builtin)
        info = manager.get_session_info()
        
        return {
            "success": success,
            "message": "Session cleared successfully" if success else "Failed to clear session",
            "session_info": info
        }
        
    except Exception as e:
        logger.error(f"Clear session error: {e}")
        return {
            "success": False,
            "message": f"Error clearing session: {str(e)}",
            "error": str(e)
        }


@mcp.tool()
def restart_kernel() -> Dict[str, Any]:
    """
    Restart the Mathematica kernel session.
    
    This completely stops and restarts the kernel process. All variables,
    functions, and session state will be lost. Use this when the kernel
    becomes unresponsive or when you need a completely fresh start.
    
    Returns:
        Success status and new session information.
    """
    try:
        # Stop current session
        shutdown_kernel()
        
        # Start new session
        success = initialize_kernel()
        
        if success:
            manager = get_kernel_manager()
            info = manager.get_session_info()
            return {
                "success": True,
                "message": "Kernel restarted successfully",
                "session_info": info
            }
        else:
            return {
                "success": False,
                "message": "Failed to restart kernel",
                "error": "Kernel initialization failed"
            }
            
    except Exception as e:
        logger.error(f"Restart kernel error: {e}")
        return {
            "success": False,
            "message": f"Error restarting kernel: {str(e)}",
            "error": str(e)
        }


@mcp.tool()
def convert_latex(
    latex_expression: str = Field(description="LaTeX mathematical expression to convert"),
    output_format: str = Field(
        default="OutputForm", 
        description="Format for the converted result: 'OutputForm', 'InputForm', 'TeXForm'"
    )
) -> EvaluationResult:
    """
    Convert LaTeX mathematical expressions to Wolfram Language and evaluate them.
    
    This tool attempts to parse LaTeX mathematical notation (common in ArXiv papers)
    and convert it to executable Wolfram Language expressions. Useful for processing
    mathematical content from academic papers.
    
    Examples:
    - Simple: "x^2 + 3x + 1"
    - Fractions: "\\frac{x^2}{2} + \\frac{3x}{4}"
    - Integrals: "\\int x^2 dx"
    - Sums: "\\sum_{i=1}^{n} i^2"
    - Limits: "\\lim_{x \\to 0} \\frac{\\sin x}{x}"
    
    Note: LaTeX parsing has limitations. Complex expressions may need manual conversion.
    """
    manager = get_kernel_manager()
    
    try:
        # Attempt to convert LaTeX to Wolfram Language
        conversion_expr = f'ToExpression["{latex_expression}", TeXForm]'
        
        result = manager.evaluate(
            expression=conversion_expr,
            output_format=output_format
        )
        
        if result['success']:
            return EvaluationResult(
                result=result['formatted'],
                success=True,
                evaluation_count=result['evaluation_count'],
                expression=f"LaTeX: {latex_expression} → {conversion_expr}",
                format_used=result['format_used']
            )
        else:
            # If LaTeX parsing failed, try manual preprocessing
            logger.info("LaTeX parsing failed, attempting manual conversion")
            
            # Basic LaTeX to Mathematica conversion
            manual_expr = (latex_expression
                          .replace(r'\frac{', 'Divide[')
                          .replace(r'}{', ',')
                          .replace(r'}', ']')
                          .replace(r'\int', 'Integrate')
                          .replace(r'\sum', 'Sum')
                          .replace(r'\lim', 'Limit'))
            
            manual_result = manager.evaluate(
                expression=f'ToExpression["{manual_expr}"]',
                output_format=output_format
            )
            
            return EvaluationResult(
                result=manual_result['formatted'],
                success=manual_result['success'],
                evaluation_count=manual_result['evaluation_count'],
                expression=f"LaTeX: {latex_expression} → Manual: {manual_expr}",
                format_used=manual_result['format_used'],
                error=manual_result.get('error')
            )
            
    except Exception as e:
        logger.error(f"LaTeX conversion error: {e}")
        return EvaluationResult(
            result=f"Error converting LaTeX: {str(e)}",
            success=False,
            evaluation_count=0,
            expression=latex_expression,
            format_used=output_format,
            error=str(e)
        )


# Initialize kernel when module is loaded
initialize_kernel()


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()