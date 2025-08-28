"""
Mathematica MCP Tool - Production Version

Provides MCP tools for interacting with Wolfram Mathematica through a persistent kernel session.
Enables LLM-driven mathematical workflows with true REPL behavior and variable persistence.
"""

import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from wolframclient.evaluation import WolframLanguageSession
from wolframclient.language import wlexpr

from mcp_handley_lab.shared.models import OperationResult, ServerInfo

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Mathematica Tool")

# Global session management with thread safety
_session: WolframLanguageSession | None = None
_evaluation_count = 0
_session_lock = threading.RLock()
_kernel_path = "/usr/bin/WolframKernel"
_result_history: list[Any] = []  # Store all results for %, %%, %n references
_input_history: list[str] = []  # Store input expressions for notebook reconstruction


class MathematicaResult(BaseModel):
    """Result of a Mathematica evaluation."""

    result: str = Field(description="The formatted result of the evaluation")
    raw_result: str = Field(description="The raw Wolfram Language result")
    success: bool = Field(description="Whether the evaluation succeeded")
    evaluation_count: int = Field(description="Number of evaluations in this session")
    expression: str = Field(description="The original expression that was evaluated")
    format_used: str = Field(description="The output format that was used")
    error: str | None = Field(None, description="Error message if evaluation failed")
    note: str | None = Field(None, description="Additional notes about the evaluation")


class SessionInfo(BaseModel):
    """Information about the current Mathematica session."""

    active: bool = Field(description="Whether the kernel session is active")
    evaluation_count: int = Field(description="Number of evaluations performed")
    version: str | None = Field(None, description="Wolfram kernel version")
    memory_used: str | None = Field(None, description="Memory currently in use")
    kernel_id: str | None = Field(None, description="Kernel process ID")
    kernel_path: str = Field(description="Path to the Wolfram kernel")
    uptime_seconds: float | None = Field(None, description="Session uptime in seconds")
    last_evaluation: str | None = Field(None, description="Last expression evaluated")


def _get_session() -> WolframLanguageSession:
    """Get or create the global Wolfram session with thread safety."""
    global _session, _evaluation_count

    with _session_lock:
        if _session is None:
            try:
                logger.info("Starting Wolfram kernel session...")
                _session = WolframLanguageSession(_kernel_path)
                _evaluation_count = 0

                # Initialize session settings for better REPL behavior
                _session.evaluate(wlexpr("$HistoryLength = 100"))
                _session.evaluate(wlexpr("SetOptions[$Output, PageWidth -> Infinity]"))

                # Note: % references have proven unreliable in wolframclient
                # Instead, we provide Python-side state management for chaining operations
                logger.info(
                    "✅ Session configured for LLM workflows with Python-side state management"
                )

                logger.info("✅ Wolfram session started successfully")

            except Exception as e:
                logger.error(f"❌ Failed to start Wolfram session: {e}")
                _session = None
                raise RuntimeError(f"Could not start Wolfram session: {e}") from e

    return _session


def _to_input_form(expr_obj) -> str:
    """
    Convert a Wolfram expression object back to parseable InputForm string.

    This is crucial because str(expr_obj) gives Python representation like 'wl.Plus(...)'
    which the kernel cannot parse. InputForm gives us parseable Wolfram code.
    """
    if expr_obj is None:
        return "Null"

    # Use the session to convert to InputForm string
    with _session_lock:
        if _session is not None:
            try:
                # Use ToString with InputForm to get a proper string representation
                input_form_str = _session.evaluate(
                    wlexpr(f"ToString[{expr_obj}, InputForm]")
                )
                return str(input_form_str)
            except Exception as e:
                logger.warning(f"Failed to convert to InputForm: {e}")
                return str(expr_obj)
    return str(expr_obj)


def _format_result(
    session: WolframLanguageSession, raw_result: Any, output_format: str
) -> str:
    """Format a raw Wolfram result into a string based on the desired format."""
    if output_format == "Raw":
        return str(raw_result)

    # For other formats, ask the kernel to convert to string
    format_func = {
        "InputForm": "InputForm",
        "OutputForm": "OutputForm",
        "TeXForm": "TeXForm",
    }.get(output_format)

    if format_func:
        if format_func == "TeXForm":
            return str(session.evaluate(wlexpr(f"ToString[TeXForm[{raw_result}]]")))
        return str(session.evaluate(wlexpr(f"ToString[{raw_result}, {format_func}]")))

    return str(raw_result)


def _preprocess_percent_references(expression: str) -> str:
    """
    Robust preprocessing of % references using regex-based substitution.

    Handles:
    - % (last result)
    - %% (second to last)
    - %%% (third to last, etc.)
    - %n (result n, e.g., %5)

    This bypasses wolframclient's problematic % handling by doing substitution
    in Python before the expression is parsed.
    """
    global _result_history

    if not _result_history or "%" not in expression:
        return expression

    processed_expression = expression

    # Handle %n references (e.g., %5, %12)
    def replace_numbered(match):
        index = int(match.group(1))
        if 1 <= index <= len(_result_history):
            # Wolfram is 1-indexed, Python lists are 0-indexed
            result_obj = _result_history[index - 1]
            return f"({_to_input_form(result_obj)})"
        return match.group(0)  # Return original if index out of bounds

    processed_expression = re.sub(r"%(\d+)", replace_numbered, processed_expression)

    # Handle %%... references (%, %%, %%%)
    def replace_sequential(match):
        count = len(match.group(0))
        if 1 <= count <= len(_result_history):
            # % is history[-1], %% is history[-2], etc.
            result_obj = _result_history[-count]
            return f"({_to_input_form(result_obj)})"
        return match.group(0)  # Return original if not enough history

    # Match one or more % not preceded by a digit
    processed_expression = re.sub(
        r"(?<!\d)(%)+", replace_sequential, processed_expression
    )

    if processed_expression != expression:
        logger.debug(
            f"Preprocessed % references: '{expression}' -> '{processed_expression}'"
        )

    return processed_expression


def _ensure_session_active() -> bool:
    """Ensure the session is active and responsive."""
    global _session

    with _session_lock:
        if _session is None:
            return False

        try:
            # Test session responsiveness with a simple evaluation
            _session.evaluate(wlexpr("1"))
            return True
        except Exception as e:
            logger.warning(f"Session unresponsive, will restart: {e}")
            _session = None
            return False


@mcp.tool()
def evaluate(
    expression: str = Field(description="Wolfram Language expression to evaluate"),
    output_format: str = Field(
        default="Raw",
        description=(
            "Output format for the result. "
            "'Raw': Python's string representation of the result object. "
            "'InputForm': A string of valid Wolfram Language code. "
            "'OutputForm': Standard human-readable formatted output. "
            "'TeXForm': LaTeX representation for documents."
        ),
    ),
    store_context: str | None = Field(
        None, description="Optional key to store this result for later reference"
    ),
) -> MathematicaResult:
    """
    Evaluate a Wolfram Language expression in the persistent session.

    This is the main tool for LLM-driven mathematical workflows. The session persists
    across multiple tool calls, allowing for true REPL behavior where variables,
    functions, and results are maintained between evaluations.

    Examples:
    - Basic math: "2 + 2"
    - Define variables: "x = 5; y = x^2"
    - Mathematical operations: "Factor[x^4 - 1]"
    - Solve equations: "Solve[x^2 + 3*x + 2 == 0, x]"
    - Integration: "Integrate[x^2 + 3*x + 1, x]"
    - Use persistent variables: "Expand[myExpression]"

    Note: % references are fully supported through Python-side preprocessing.
    Use % for last result, %% for second-to-last, %n for result n, etc.

    The session maintains all variables and definitions across calls, enabling
    complex mathematical workflows where LLMs can build on previous calculations.
    """
    global _evaluation_count

    with _session_lock:
        # Ensure session is active
        session = _get_session() if not _ensure_session_active() else _session

        logger.debug(f"Evaluating: {expression}")

        # Preprocess % references before evaluation
        processed_expression = _preprocess_percent_references(expression)

        # Evaluate the processed expression
        raw_result = session.evaluate(wlexpr(processed_expression))
        _evaluation_count += 1

        # Store result in history for % references
        global _result_history, _input_history
        _result_history.append(raw_result)
        _input_history.append(expression)  # Store input for notebook reconstruction

        # Format the result based on requested format
        formatted_result = _format_result(session, raw_result, output_format)

        logger.debug(f"✅ Evaluation successful: {formatted_result}")

        return MathematicaResult(
            result=formatted_result,
            raw_result=str(raw_result),
            success=True,
            evaluation_count=_evaluation_count,
            expression=expression,
            format_used=output_format,
        )


@mcp.tool()
def session_info() -> SessionInfo:
    """
    Get comprehensive information about the current Mathematica session.

    Returns details about the active session including version, memory usage,
    evaluation count, and session health. Useful for monitoring session state
    and debugging mathematical workflows.
    """
    global _evaluation_count

    with _session_lock:
        try:
            if _session is None:
                return SessionInfo(
                    active=False,
                    evaluation_count=_evaluation_count,
                    kernel_path=_kernel_path,
                )

            # Get session details from Wolfram
            version = str(_session.evaluate(wlexpr("$Version")))
            memory_used = str(_session.evaluate(wlexpr("MemoryInUse[]")))
            kernel_id = str(_session.evaluate(wlexpr("$ProcessID")))

            return SessionInfo(
                active=True,
                evaluation_count=_evaluation_count,
                version=version,
                memory_used=memory_used,
                kernel_id=kernel_id,
                kernel_path=_kernel_path,
            )

        except Exception as e:
            logger.error(f"Failed to get session info: {e}")
            return SessionInfo(
                active=False,
                evaluation_count=_evaluation_count,
                kernel_path=_kernel_path,
            )


@mcp.tool()
def clear_session(
    keep_builtin: bool = Field(
        True,
        description="If True, preserve built-in Wolfram functions. If False, clear everything.",
    ),
) -> OperationResult:
    """
    Clear user-defined variables and symbols from the session.

    This resets the mathematical workspace while keeping the kernel running
    and preserving built-in Wolfram functions. Useful for starting fresh
    calculations or clearing memory when the session becomes cluttered.

    Args:
        keep_builtin: If True (default), only clears user-defined symbols.
                     If False, performs a more complete reset.

    Returns:
        Operation result with success status and session information.
    """
    global _evaluation_count

    with _session_lock:
        try:
            session = _get_session() if not _ensure_session_active() else _session

            if keep_builtin:
                # Clear only user-defined symbols in Global context
                session.evaluate(wlexpr('ClearAll[Evaluate[Names["Global`*"]]]'))
                message = "Cleared user-defined variables"
            else:
                # More aggressive clearing
                session.evaluate(wlexpr('ClearAll["Global`*"]'))
                session.evaluate(wlexpr("$HistoryLength = 100"))
                message = "Cleared all symbols and reset session"

            # Clear Python-side history in both cases
            global _result_history, _input_history
            _result_history.clear()
            _input_history.clear()

            logger.info(f"✅ {message}")

            return OperationResult(
                status="success",
                message=message,
                data={"evaluation_count": _evaluation_count},
            )

        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
            return OperationResult(
                status="error",
                message=f"Failed to clear session: {str(e)}",
                data={"error": str(e)},
            )


@mcp.tool()
def restart_kernel() -> OperationResult:
    """
    Completely restart the Mathematica kernel.

    This terminates the current kernel process and starts a fresh one.
    All variables, functions, and session state will be lost. Use this
    when the kernel becomes unresponsive or when you need a completely
    clean mathematical environment.

    Returns:
        Operation result with success status and new session information.
    """
    global _session, _evaluation_count, _result_history

    with _session_lock:
        try:
            # Terminate existing session
            if _session:
                try:
                    _session.terminate()
                    logger.info("Previous session terminated")
                except Exception as e:
                    logger.warning(f"Error terminating previous session: {e}")

            # Reset state
            _session = None
            _evaluation_count = 0
            _result_history.clear()
            _input_history.clear()

            # Start new session
            _get_session()

            return OperationResult(
                status="success",
                message="Kernel restarted successfully",
                data={
                    "evaluation_count": _evaluation_count,
                    "kernel_path": _kernel_path,
                },
            )

        except Exception as e:
            logger.error(f"Failed to restart kernel: {e}")
            return OperationResult(
                status="error",
                message=f"Failed to restart kernel: {str(e)}",
                data={"error": str(e)},
            )


@mcp.tool()
def apply_to_last(
    operation: str = Field(
        description="Wolfram Language operation to apply to the last result (e.g., 'Factor', 'Expand', 'Solve[# == 0, x]')"
    ),
) -> MathematicaResult:
    """
    Apply a Wolfram Language operation to the last evaluation result.

    This tool provides a reliable way to chain operations. Use '#' as a placeholder
    for the last result within the operation string. For simple function names like
    'Factor', the '#' is not needed.

    Examples:
    - "Factor" - factors the last result
    - "Expand" - expands the last result
    - "Solve[# == 0, x]" - solves equation where last result equals 0 (recommended pattern)
    - "Plot[#, {x, -2, 2}]" - plots the last result

    Alternative to % references for operation chaining.
    """
    global _evaluation_count, _result_history

    with _session_lock:
        try:
            session = _get_session() if not _ensure_session_active() else _session

            if not _result_history:
                return MathematicaResult(
                    result="Error: No previous result available",
                    raw_result="",
                    success=False,
                    evaluation_count=_evaluation_count,
                    expression=operation,
                    format_used="Raw",
                    error="No previous result stored",
                    note="Use the 'evaluate' tool first to generate a result",
                )

            last_result = _result_history[-1]
            logger.debug(f"Applying '{operation}' to last result: {last_result}")

            # Apply the operation to the last result
            last_result_str = _to_input_form(last_result)

            if "#" in operation:
                operation_expr = operation.replace("#", last_result_str)
            else:
                operation_expr = f"{operation}[{last_result_str}]"

            raw_result = session.evaluate(wlexpr(operation_expr))
            _evaluation_count += 1
            _result_history.append(raw_result)  # Add to history
            global _input_history
            _input_history.append(
                f"{operation} applied to previous result"
            )  # Store operation for notebook

            # Use Raw format by default for consistency
            formatted_result = str(raw_result)

            logger.debug(f"✅ Applied operation successfully: {formatted_result}")

            return MathematicaResult(
                result=formatted_result,
                raw_result=str(raw_result),
                success=True,
                evaluation_count=_evaluation_count,
                expression=f"{operation} applied to previous result",
                format_used="Raw",
                note="Result stored for further chaining operations",
            )

        except Exception as e:
            logger.error(f"❌ Operation application failed: {e}")
            return MathematicaResult(
                result=f"Error: {str(e)}",
                raw_result="",
                success=False,
                evaluation_count=_evaluation_count,
                expression=operation,
                format_used="Raw",
                error=str(e),
            )


@mcp.tool()
def convert_latex(
    latex_expression: str = Field(
        description="LaTeX mathematical expression to convert"
    ),
    output_format: str = Field(
        default="OutputForm",
        description=(
            "Output format for the converted result. "
            "'Raw': Python's string representation of the result object. "
            "'InputForm': A string of valid Wolfram Language code. "
            "'OutputForm': Standard human-readable formatted output. "
            "'TeXForm': LaTeX representation for documents."
        ),
    ),
) -> MathematicaResult:
    """
    Convert LaTeX mathematical expressions to Wolfram Language and evaluate them.

    This tool attempts to parse LaTeX mathematical notation (common in ArXiv papers)
    and convert it to executable Wolfram Language expressions. Useful for processing
    mathematical content from academic papers and integrating them into workflows.

    Examples:
    - Simple: "x^2 + 3x + 1"
    - Fractions: "\\frac{x^2}{2} + \\frac{3x}{4}"
    - Integrals: "\\int x^2 dx"
    - Sums: "\\sum_{i=1}^{n} i^2"
    - Limits: "\\lim_{x \\to 0} \\frac{\\sin x}{x}"

    Note: Works best for standard mathematical notation. LaTeX parsing has limitations
    and may struggle with complex layouts or custom macros. Complex expressions may need manual conversion.
    """
    global _evaluation_count

    with _session_lock:
        try:
            session = _get_session() if not _ensure_session_active() else _session

            # Attempt to convert LaTeX to Wolfram Language
            try:
                # First try direct ToExpression with TeXForm
                conversion_expr = f'ToExpression["{latex_expression}", TeXForm]'
                raw_result = session.evaluate(wlexpr(conversion_expr))
                _evaluation_count += 1

                logger.debug(f"✅ LaTeX conversion successful: {raw_result}")

            except Exception as e:
                logger.info(
                    f"Direct LaTeX parsing failed, trying manual conversion: {e}"
                )

                # Try manual preprocessing for common LaTeX patterns
                manual_expr = (
                    latex_expression.replace(r"\frac{", "Divide[")
                    .replace(r"}{", ",")
                    .replace(r"}", "]")
                    .replace(r"\int", "Integrate")
                    .replace(r"\sum", "Sum")
                    .replace(r"\lim", "Limit")
                    .replace(r"\sin", "Sin")
                    .replace(r"\cos", "Cos")
                    .replace(r"\tan", "Tan")
                    .replace(r"\log", "Log")
                    .replace(r"\exp", "Exp")
                )

                raw_result = session.evaluate(wlexpr(f'ToExpression["{manual_expr}"]'))
                _evaluation_count += 1

                logger.debug(f"✅ Manual LaTeX conversion successful: {raw_result}")

            # Format the result
            formatted_result = _format_result(session, raw_result, output_format)

            return MathematicaResult(
                result=formatted_result,
                raw_result=str(raw_result),
                success=True,
                evaluation_count=_evaluation_count,
                expression=f"LaTeX: {latex_expression}",
                format_used=output_format,
            )

        except Exception as e:
            logger.error(f"LaTeX conversion failed: {e}")
            return MathematicaResult(
                result=f"Error converting LaTeX: {str(e)}",
                raw_result="",
                success=False,
                evaluation_count=_evaluation_count,
                expression=latex_expression,
                format_used=output_format,
                error=str(e),
            )


@mcp.tool()
def save_notebook(
    filepath: str = Field(description="Path where to save the notebook file"),
    format: str = Field(
        "md",
        description="Output format: 'md' (markdown), 'wl' (wolfram script), 'wls' (wolfram script with outputs)",
    ),
    title: str = Field(
        "Mathematica Session", description="Title for the saved notebook"
    ),
) -> OperationResult:
    """
    Save the current session with complete input/output history in human-readable format.

    Preserves all evaluations, results, and session state for restoration after Claude restarts.
    The saved notebook contains both the input expressions and their corresponding outputs.

    Supported formats:
    - 'md': GitHub-friendly markdown with In/Out blocks (most readable)
    - 'wl': Executable Wolfram Language script (for restoration)
    - 'wls': Wolfram script with output comments (readable + executable)
    """
    try:
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Choose format handler
        if format == "md":
            _save_as_markdown(filepath, title, timestamp)
        elif format == "wl":
            _save_as_wolfram_script(filepath, title, timestamp)
        elif format == "wls":
            _save_as_wolfram_script_with_outputs(filepath, title, timestamp)
        else:
            return OperationResult(
                status="error",
                message=f"Unsupported format: {format}. Use 'md', 'wl', or 'wls'.",
                data={"supported_formats": ["md", "wl", "wls"]},
            )

        return OperationResult(
            status="success",
            message=f"Notebook saved to {filepath} in {format} format",
            data={
                "filepath": filepath,
                "format": format,
                "evaluations": len(_input_history),
                "timestamp": timestamp,
            },
        )

    except Exception as e:
        return OperationResult(
            status="error",
            message=f"Failed to save notebook: {str(e)}",
            data={"filepath": filepath, "format": format},
        )


def _save_as_markdown(filepath: str, title: str, timestamp: str) -> dict:
    """Save session as GitHub-friendly markdown with In/Out blocks."""
    global _input_history, _result_history, _evaluation_count

    content = f"""# {title}
*Generated: {timestamp}*
*Kernel: Mathematica 14.2.1*
*Evaluations: {_evaluation_count}*

"""

    # Generate In/Out pairs from our tracked history
    for i in range(len(_input_history)):
        input_expr = _input_history[i]
        if i < len(_result_history):
            output_result = _format_result(
                _get_session(), _result_history[i], "OutputForm"
            )
        else:
            output_result = "No output"

        content += f"""## Evaluation {i + 1}
```mathematica
In[{i + 1}]:= {input_expr}
Out[{i + 1}]= {output_result}
```

"""

    # Add session information
    content += """## Session State
Current variables and functions are preserved in this session.
Use `Names["Global`*"]` in Mathematica to see all defined symbols.

## Restoration
To restore this session, copy and paste the input lines into a new Mathematica notebook.
"""

    # Write to file
    Path(filepath).write_text(content)
    return {"format": "markdown"}


def _save_as_wolfram_script(filepath: str, title: str, timestamp: str) -> dict:
    """Save session as executable Wolfram Language script."""
    global _input_history, _evaluation_count

    content = f"""(* {title} *)
(* Generated: {timestamp} *)
(* Evaluations: {_evaluation_count} *)

"""

    # Add all input expressions as executable code
    for i, input_expr in enumerate(_input_history):
        content += f"""(* Evaluation {i + 1} *)
{input_expr};

"""

    content += """(* End of session *)
Print["Session restored successfully! Variables: ", Length[Names["Global`*"]]];
"""

    Path(filepath).write_text(content)
    return {"format": "wolfram_language"}


def _save_as_wolfram_script_with_outputs(
    filepath: str, title: str, timestamp: str
) -> dict:
    """Save session as Wolfram script with output comments."""
    global _input_history, _result_history, _evaluation_count

    content = f"""(* {title} *)
(* Generated: {timestamp} *)
(* Evaluations: {_evaluation_count} *)

"""

    # Add input/output pairs with comments
    for i in range(len(_input_history)):
        input_expr = _input_history[i]
        if i < len(_result_history):
            output_result = str(_result_history[i])
        else:
            output_result = "No output"

        content += f"""(* Evaluation {i + 1} *)
{input_expr};
(* Result: {output_result} *)

"""

    content += """(* End of session *)
Print["Session restored with outputs preserved in comments"];
Print["Variables available: ", Names["Global`*"]];
"""

    Path(filepath).write_text(content)
    return {"format": "wolfram_language_with_outputs"}


@mcp.tool()
def server_info() -> ServerInfo:
    """
    Get comprehensive information about the Mathematica MCP server.

    Returns server status, capabilities, version information, and dependency status.
    Useful for debugging and verifying server health.
    """
    dependencies = {
        "wolframclient": "required",
        "wolfram_kernel": f"configured at {_kernel_path}",
    }

    status = "active"

    capabilities = [
        "evaluate - Evaluate Wolfram Language expressions with persistent session",
        "apply_to_last - Apply operations to the last evaluation result (alternative to % references)",
        "session_info - Get detailed session information and statistics",
        "clear_session - Clear user-defined variables while keeping kernel alive",
        "restart_kernel - Completely restart the Wolfram kernel process",
        "convert_latex - Convert LaTeX mathematical expressions to Wolfram Language",
        "save_notebook - Save session history as markdown or Wolfram script",
        "server_info - Get server status and capability information",
    ]

    return ServerInfo(
        name="Mathematica Tool",
        version="1.0.0",
        status=status,
        capabilities=capabilities,
        dependencies=dependencies,
    )


# Session will be initialized lazily on first use


if __name__ == "__main__":
    mcp.run()
