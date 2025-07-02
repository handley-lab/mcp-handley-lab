"""SymPy tool for symbolic mathematics via MCP."""
import asyncio
from typing import Optional, Union, Dict, Any
from pydantic import constr
from mcp.server.fastmcp import FastMCP
from ..common.exceptions import UserCancelledError

mcp = FastMCP("SymPy Tool")


def _safe_sympy_operation(operation_func, *args, **kwargs):
    """Safely execute a SymPy operation with error handling."""
    try:
        return operation_func(*args, **kwargs)
    except asyncio.CancelledError:
        raise UserCancelledError("SymPy operation was cancelled by user")
    except Exception as e:
        raise ValueError(f"SymPy error: {str(e)}")


def _parse_expression(expression: str):
    """Parse a string expression into a SymPy expression."""
    try:
        import sympy as sp
        # Use sympify with evaluate=False to handle complex expressions
        return sp.sympify(expression, evaluate=False)
    except Exception as e:
        raise ValueError(f"Invalid expression '{expression}': {str(e)}")


def _parse_variables(variables: Optional[str]) -> list:
    """Parse comma-separated variable string into list of SymPy symbols."""
    if not variables:
        return []
    
    import sympy as sp
    try:
        var_names = [v.strip() for v in variables.split(',')]
        return [sp.Symbol(name) for name in var_names if name]
    except Exception as e:
        raise ValueError(f"Invalid variables '{variables}': {str(e)}")


@mcp.tool(description="""Transforms symbolic mathematical expressions using various algebraic operations.

Expression Input: Mathematical expressions in standard notation:
- Polynomials: `x^2 + 2*x + 1`, `(x+1)*(x+2)`, `x**2 + y**2`
- Rational functions: `(x^2 + 1)/(x - 1)`, `1/x + 1/y`
- Trigonometric: `sin(x)*cos(x)`, `tan(x) + cot(x)`
- Exponential/logarithmic: `exp(x)*log(x)`, `sqrt(x)`

Transformation Operations:
- `expand`: Distribute products and expand expressions
  - Example: `(x+1)*(x+2)` → `x^2 + 3*x + 2`
- `simplify`: Simplify complex expressions using various techniques
  - Example: `sin(x)**2 + cos(x)**2` → `1`
- `factor`: Factor polynomials and expressions
  - Example: `x^2 + 3*x + 2` → `(x + 1)*(x + 2)`
- `collect`: Collect terms with respect to specified variables
  - Example: `x*y + x*z + 2*x` → `x*(y + z + 2)` (collecting by x)
- `apart`: Partial fraction decomposition
  - Example: `(x+1)/(x^2-1)` → `1/2/(x-1) + 1/2/(x+1)`
- `together`: Combine fractions over a common denominator
  - Example: `1/x + 1/y` → `(x + y)/(x*y)`
- `cancel`: Cancel common factors in rational expressions
  - Example: `(x^2-1)/(x-1)` → `x + 1`

Variables Parameter: Comma-separated list of variables to focus operations on.
- Example: "x,y" for multi-variable expressions
- Default: Auto-detect variables in expression

Error Handling:
- Raises ValueError for invalid expression syntax
- Raises ValueError for unsupported operations
- Provides specific error messages for debugging

Examples:
```python
# Expand polynomial products
transform_expression("(x+1)*(x^2+2*x+1)", "expand")
# Returns: x^3 + 3*x^2 + 3*x + 1

# Simplify complex expressions
transform_expression("sin(x)**2 + cos(x)**2", "simplify") 
# Returns: 1

# Factor polynomials
transform_expression("x^2 + 5*x + 6", "factor")
# Returns: (x + 2)*(x + 3)

# Collect terms
transform_expression("x*y + x*z + 2*x", "collect", variables="x")
# Returns: x*(y + z + 2)

# Partial fractions
transform_expression("(2*x + 3)/(x^2 - 1)", "apart", variables="x")
# Returns: 1/(x - 1) + 1/(x + 1)
```""")
async def transform_expression(
    expression: constr(min_length=1), 
    operation: constr(min_length=1),
    variables: Optional[str] = None
) -> str:
    """Transform a mathematical expression using SymPy operations."""
    
    # Import SymPy inside the function to handle import errors gracefully
    try:
        import sympy as sp
    except ImportError:
        raise RuntimeError("SymPy is not installed. Please install it with: pip install sympy")
    
    # Parse the expression
    expr = _parse_expression(expression)
    
    # Parse variables if provided
    var_list = _parse_variables(variables)
    
    # Map operation names to SymPy functions
    operations = {
        'expand': lambda e, v: _safe_sympy_operation(sp.expand, e),
        'simplify': lambda e, v: _safe_sympy_operation(sp.simplify, e),
        'factor': lambda e, v: _safe_sympy_operation(sp.factor, e),
        'collect': lambda e, v: _safe_sympy_operation(sp.collect, e, v[0] if v else list(e.free_symbols)[0] if e.free_symbols else sp.Symbol('x')),
        'apart': lambda e, v: _safe_sympy_operation(sp.apart, e, v[0] if v else list(e.free_symbols)[0] if e.free_symbols else sp.Symbol('x')),
        'together': lambda e, v: _safe_sympy_operation(sp.together, e),
        'cancel': lambda e, v: _safe_sympy_operation(sp.cancel, e)
    }
    
    if operation not in operations:
        available_ops = ', '.join(operations.keys())
        raise ValueError(f"Unknown operation '{operation}'. Available operations: {available_ops}")
    
    # Perform the operation
    try:
        result = operations[operation](expr, var_list)
        return str(result)
    except Exception as e:
        if "cancelled" in str(e).lower():
            raise UserCancelledError("Expression transformation was cancelled by user")
        raise ValueError(f"Failed to perform '{operation}' on expression: {str(e)}")


@mcp.tool(description="""Evaluates mathematical expressions by substituting values and optionally converting to numerical form.

Expression Input: Mathematical expressions in standard notation (same as transform_expression).

Variable Substitution: Dictionary mapping variable names to values:
- Symbolic values: `{"x": "2", "y": "pi"}` for exact symbolic computation
- Numerical values: `{"x": 2.5, "y": 3.14159}` for numerical computation
- Mixed: `{"x": 2, "y": "sqrt(2)"}` combines numerical and symbolic

Numerical Evaluation: 
- `numerical=False` (default): Returns exact symbolic result
- `numerical=True`: Converts result to floating-point approximation

Use Cases:
- **Symbolic substitution**: Replace variables with other expressions
- **Numerical evaluation**: Get decimal approximations of exact results
- **Function evaluation**: Substitute values into functions to get specific outputs
- **Expression validation**: Check expression behavior at specific points

Error Handling:
- Raises ValueError for invalid expressions or substitution values
- Raises ValueError for undefined variables in expression
- Handles division by zero and other mathematical errors gracefully

Examples:
```python
# Symbolic substitution
evaluate_expression("x^2 + 2*x + 1", {"x": "a+1"})
# Returns: (a + 1)^2 + 2*(a + 1) + 1

# Numerical evaluation
evaluate_expression("sqrt(2) + pi", {}, numerical=True)
# Returns: 4.555806215962888

# Substitute and evaluate
evaluate_expression("x^2 + y^2", {"x": 3, "y": 4}, numerical=True)
# Returns: 25.0

# Complex expression evaluation
evaluate_expression("sin(pi/4) + cos(pi/4)", {}, numerical=True)
# Returns: 1.4142135623730951

# Function evaluation at specific points
evaluate_expression("x^3 - 2*x^2 + x - 1", {"x": 2})
# Returns: 1

# Symbolic constants
evaluate_expression("E^(I*pi)", {}, numerical=True)
# Returns: -1.0
```""")
async def evaluate_expression(
    expression: constr(min_length=1),
    variables: Optional[Dict[str, Union[str, int, float]]] = None,
    numerical: bool = False
) -> str:
    """Evaluate a mathematical expression with variable substitution."""
    
    # Import SymPy inside the function
    try:
        import sympy as sp
    except ImportError:
        raise RuntimeError("SymPy is not installed. Please install it with: pip install sympy")
    
    # Parse the expression
    expr = _parse_expression(expression)
    
    # Handle variable substitution
    if variables:
        try:
            # Convert substitution values to SymPy expressions
            subs_dict = {}
            for var_name, value in variables.items():
                var_symbol = sp.Symbol(var_name)
                if isinstance(value, str):
                    # Parse string values as SymPy expressions
                    subs_dict[var_symbol] = sp.sympify(value)
                else:
                    # Use numerical values directly
                    subs_dict[var_symbol] = value
            
            # Perform substitution
            expr = _safe_sympy_operation(expr.subs, subs_dict)
            
        except Exception as e:
            raise ValueError(f"Failed to substitute variables: {str(e)}")
    
    # Convert to numerical if requested
    if numerical:
        try:
            result = _safe_sympy_operation(float, expr.evalf())
            return str(result)
        except Exception as e:
            # If direct float conversion fails, try evalf() which returns more precise result
            try:
                result = _safe_sympy_operation(expr.evalf)
                return str(result)
            except Exception as e2:
                raise ValueError(f"Failed to evaluate expression numerically: {str(e2)}")
    
    # Return symbolic result
    return str(expr)


@mcp.tool(description="""Converts mathematical expressions to LaTeX format for typesetting and documentation.

Expression Input: Mathematical expressions in standard notation (same as other SymPy tools).

Output Modes:
- `mode="plain"` (default): Raw LaTeX code without delimiters
- `mode="inline"`: Inline math mode with `$...$` delimiters  
- `mode="equation"`: Display math mode with `\\begin{equation*}...\\end{equation*}`

Formatting Options:
- `fold_frac_powers=True`: Convert negative exponents to fractions (e.g., `x^{-1/2}` → `\\frac{1}{\\sqrt{x}}`)
- `mul_symbol`: Multiplication symbol - "dot" for `\\cdot`, "times" for `\\times`, or None for space
- `ln_notation=True`: Use `\\ln` instead of `\\log` for natural logarithms

Use Cases:
- **Document generation**: Create LaTeX code for papers, reports, and documentation
- **Web display**: Generate LaTeX for MathJax/KaTeX rendering in web pages
- **Presentation slides**: Convert expressions for Beamer or other LaTeX slide systems
- **Academic publishing**: Prepare mathematical expressions for journals and conferences

Error Handling:
- Raises ValueError for invalid expressions
- Raises ValueError for unsupported mode or formatting options
- Handles complex expressions including integrals, derivatives, matrices, and equations

Examples:
```python
# Basic LaTeX conversion
to_latex("x^2 + 2*x + 1")
# Returns: x^{2} + 2 x + 1

# Inline math mode
to_latex("sqrt(2*pi)", mode="inline")
# Returns: $\\sqrt{2 \\pi}$

# Display equation mode
to_latex("integrate(x^2, x)", mode="equation")
# Returns: \\begin{equation*}\\frac{x^{3}}{3}\\end{equation*}

# Fraction formatting
to_latex("x^(-1/2)", fold_frac_powers=True)
# Returns: \\frac{1}{\\sqrt{x}}

# Custom multiplication symbol
to_latex("2*x*y", mul_symbol="dot")
# Returns: 2 \\cdot x \\cdot y

# Complex expressions
to_latex("Matrix([[x, sin(y)], [cos(z), 1]])")
# Returns: \\left[\\begin{matrix}x & \\sin{\\left(y \\right)}\\\\\\cos{\\left(z \\right)} & 1\\end{matrix}\\right]
```""")
async def to_latex(
    expression: constr(min_length=1),
    mode: str = "plain",
    fold_frac_powers: bool = False,
    mul_symbol: Optional[str] = None,
    ln_notation: bool = False
) -> str:
    """Convert a mathematical expression to LaTeX format."""
    
    # Import SymPy inside the function
    try:
        import sympy as sp
    except ImportError:
        raise RuntimeError("SymPy is not installed. Please install it with: pip install sympy")
    
    # Parse the expression
    expr = _parse_expression(expression)
    
    # Validate mode parameter
    valid_modes = ["plain", "inline", "equation"]
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Valid modes: {', '.join(valid_modes)}")
    
    # Validate mul_symbol parameter
    valid_mul_symbols = [None, "dot", "times"]
    if mul_symbol not in valid_mul_symbols:
        raise ValueError(f"Invalid mul_symbol '{mul_symbol}'. Valid options: {', '.join(str(s) for s in valid_mul_symbols)}")
    
    # Generate LaTeX
    try:
        latex_str = _safe_sympy_operation(
            sp.latex, 
            expr,
            mode=mode,
            fold_frac_powers=fold_frac_powers,
            mul_symbol=mul_symbol,
            ln_notation=ln_notation
        )
        return latex_str
    except Exception as e:
        if "cancelled" in str(e).lower():
            raise UserCancelledError("LaTeX conversion was cancelled by user")
        raise ValueError(f"Failed to convert expression to LaTeX: {str(e)}")


@mcp.tool(description="""Checks the status of the SymPy tool server and the availability of the SymPy library.

Use this to verify that the tool is operational before making other requests.

**Input/Output:**
- **Input**: None.
- **Output**: A string containing the server status, SymPy version, and a list of available tools.

**Error Handling:**
- Raises `RuntimeError` if SymPy is not installed.

**Examples:**
```python
# Check the server status.
server_info()
```""")
async def server_info() -> str:
    """Get server status and SymPy version."""
    try:
        import sympy as sp
        version = sp.__version__
        
        return f"""SymPy Tool Server Status
========================
Status: Connected and ready
SymPy Version: {version}

Available tools:
- transform_expression: Algebraic transformations (expand, simplify, factor, etc.)
- evaluate_expression: Variable substitution and numerical evaluation
- to_latex: Convert expressions to LaTeX format for typesetting
- server_info: Get server status

Supported operations:
- expand: Distribute products (e.g., (x+1)*(x+2) → x^2 + 3*x + 2)
- simplify: Simplify expressions (e.g., sin²(x) + cos²(x) → 1)
- factor: Factor polynomials (e.g., x^2 + 3*x + 2 → (x+1)*(x+2))
- collect: Collect terms by variable
- apart: Partial fraction decomposition
- together: Combine fractions
- cancel: Cancel common factors

Mathematical constants available: pi, E, I, oo (infinity)
Functions available: sin, cos, tan, exp, log, sqrt, and many more"""
        
    except ImportError:
        raise RuntimeError("SymPy is not installed. Please install it with: pip install sympy")
    except Exception as e:
        raise RuntimeError(f"Error checking SymPy status: {str(e)}")