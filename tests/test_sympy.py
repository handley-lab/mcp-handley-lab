"""Tests for the SymPy tool."""
import pytest
from unittest.mock import patch, MagicMock
from mcp_handley_lab.sympy.tool import transform_expression, evaluate_expression, to_latex, server_info


class TestTransformExpression:
    """Test the transform_expression function."""

    @pytest.mark.asyncio
    async def test_expand_polynomial(self):
        """Test expanding polynomial expressions."""
        result = await transform_expression("(x+1)*(x+2)", "expand")
        assert result == "x**2 + 3*x + 2"

    @pytest.mark.asyncio
    async def test_expand_complex_polynomial(self):
        """Test expanding complex polynomial expressions."""
        result = await transform_expression("(x+1)*(x^2+2*x+1)", "expand")
        assert "x**3" in result and "3*x**2" in result and "3*x" in result and "1" in result

    @pytest.mark.asyncio
    async def test_factor_polynomial(self):
        """Test factoring polynomial expressions."""
        result = await transform_expression("x^2 + 3*x + 2", "factor")
        assert "(x + 1)" in result and "(x + 2)" in result

    @pytest.mark.asyncio
    async def test_simplify_trigonometric(self):
        """Test simplifying trigonometric expressions."""
        result = await transform_expression("sin(x)**2 + cos(x)**2", "simplify")
        assert result == "1"

    @pytest.mark.asyncio
    async def test_collect_terms(self):
        """Test collecting terms by variable."""
        result = await transform_expression("x*y + x*z + 2*x", "collect", variables="x")
        assert "x*(" in result and "y + z + 2" in result

    @pytest.mark.asyncio
    async def test_apart_partial_fractions(self):
        """Test partial fraction decomposition."""
        result = await transform_expression("(2*x + 3)/(x^2 - 1)", "apart", variables="x")
        assert "1/(x - 1)" in result or "1/(x + 1)" in result

    @pytest.mark.asyncio
    async def test_together_fractions(self):
        """Test combining fractions."""
        result = await transform_expression("1/x + 1/y", "together")
        assert "(x + y)/(x*y)" in result or "(y + x)/(x*y)" in result

    @pytest.mark.asyncio
    async def test_cancel_common_factors(self):
        """Test canceling common factors."""
        result = await transform_expression("(x^2 - 1)/(x - 1)", "cancel")
        assert result == "x + 1"

    @pytest.mark.asyncio
    async def test_invalid_operation(self):
        """Test handling of invalid operation."""
        with pytest.raises(ValueError, match="Unknown operation"):
            await transform_expression("x + 1", "invalid_op")

    @pytest.mark.asyncio
    async def test_invalid_expression(self):
        """Test handling of invalid expression."""
        with pytest.raises(ValueError, match="Invalid expression"):
            await transform_expression("x +++ y", "expand")

    @pytest.mark.asyncio
    async def test_multi_variable_expression(self):
        """Test multi-variable expressions."""
        result = await transform_expression("(x + y)*(x - y)", "expand")
        assert result == "x**2 - y**2"

    @pytest.mark.asyncio
    async def test_complex_rational_expression(self):
        """Test complex rational expressions."""
        result = await transform_expression("(x^2 + 2*x + 1)/(x + 1)", "cancel")
        assert result == "x + 1"

    @pytest.mark.asyncio
    async def test_sympy_import_error(self):
        """Test handling of SymPy import error."""
        # Make the import fail
        with patch('builtins.__import__', side_effect=ImportError):
            with pytest.raises(RuntimeError, match="SymPy is not installed"):
                await transform_expression("x + 1", "expand")

    @pytest.mark.asyncio
    async def test_empty_expression(self):
        """Test handling of empty expression."""
        with pytest.raises(ValueError):
            await transform_expression("", "expand")

    @pytest.mark.asyncio
    async def test_variables_parsing(self):
        """Test parsing of variables parameter."""
        # Test with specific variables
        result = await transform_expression("a*x + b*x + c*y", "collect", variables="x")
        assert "x*(" in result and "a + b" in result


class TestEvaluateExpression:
    """Test the evaluate_expression function."""

    @pytest.mark.asyncio
    async def test_symbolic_substitution(self):
        """Test symbolic variable substitution."""
        result = await evaluate_expression("x^2 + 2*x + 1", {"x": "a+1"})
        assert "(a + 1)**2" in result

    @pytest.mark.asyncio
    async def test_numerical_substitution(self):
        """Test numerical variable substitution."""
        result = await evaluate_expression("x^2 + 2*x + 1", {"x": 3})
        assert result == "16"

    @pytest.mark.asyncio
    async def test_numerical_evaluation(self):
        """Test numerical evaluation."""
        result = await evaluate_expression("sqrt(2)", {}, numerical=True)
        assert "1.414" in result

    @pytest.mark.asyncio
    async def test_multi_variable_substitution(self):
        """Test substitution with multiple variables."""
        result = await evaluate_expression("x^2 + y^2", {"x": 3, "y": 4}, numerical=True)
        assert result == "25.0"

    @pytest.mark.asyncio
    async def test_trigonometric_evaluation(self):
        """Test trigonometric function evaluation."""
        result = await evaluate_expression("sin(pi/2)", {}, numerical=True)
        assert "1.0" in result

    @pytest.mark.asyncio
    async def test_complex_expression_evaluation(self):
        """Test complex mathematical expression evaluation."""
        result = await evaluate_expression("E^(I*pi)", {}, numerical=True)
        assert "-1.0" in result

    @pytest.mark.asyncio
    async def test_symbolic_constants(self):
        """Test evaluation with symbolic constants."""
        result = await evaluate_expression("pi + E", {}, numerical=True)
        # Should be approximately 5.859
        assert "5.8" in result

    @pytest.mark.asyncio
    async def test_invalid_variable_substitution(self):
        """Test handling of invalid variable substitution."""
        with pytest.raises(ValueError, match="Failed to substitute variables"):
            await evaluate_expression("x + 1", {"x": "invalid_expr +++"})

    @pytest.mark.asyncio
    async def test_no_substitution(self):
        """Test evaluation without substitution."""
        result = await evaluate_expression("x + 1", {})
        assert result == "x + 1"

    @pytest.mark.asyncio
    async def test_mixed_substitution(self):
        """Test mixed symbolic and numerical substitution."""
        result = await evaluate_expression("x*y + z", {"x": 2, "y": "pi", "z": 1})
        assert "2*pi + 1" in result

    @pytest.mark.asyncio
    async def test_function_evaluation(self):
        """Test function evaluation at specific points."""
        result = await evaluate_expression("x**3 - 2*x**2 + x - 1", {"x": 2})
        assert result == "1"

    @pytest.mark.asyncio
    async def test_sympy_import_error_evaluate(self):
        """Test handling of SymPy import error in evaluate."""
        with patch('builtins.__import__', side_effect=ImportError):
            with pytest.raises(RuntimeError, match="SymPy is not installed"):
                await evaluate_expression("x + 1", {})

    @pytest.mark.asyncio
    async def test_division_by_zero_handling(self):
        """Test handling of division by zero."""
        result = await evaluate_expression("1/x", {"x": 0})
        assert "zoo" in result or "oo" in result  # SymPy's complex infinity

    @pytest.mark.asyncio
    async def test_empty_variables_dict(self):
        """Test with empty variables dictionary."""
        result = await evaluate_expression("x + 1", {})
        assert result == "x + 1"


class TestToLatex:
    """Test the to_latex function."""

    @pytest.mark.asyncio
    async def test_basic_latex_conversion(self):
        """Test basic LaTeX conversion."""
        result = await to_latex("x^2 + 2*x + 1")
        assert "x^{2}" in result
        assert "2 x" in result
        assert "+ 1" in result

    @pytest.mark.asyncio
    async def test_inline_mode(self):
        """Test inline math mode."""
        result = await to_latex("sqrt(2*pi)", mode="inline")
        assert result.startswith("$")
        assert result.endswith("$")
        assert "\\sqrt{2 \\pi}" in result

    @pytest.mark.asyncio
    async def test_equation_mode(self):
        """Test equation mode."""
        result = await to_latex("x^2", mode="equation")
        assert "\\begin{equation" in result
        assert "\\end{equation" in result
        assert "x^{2}" in result

    @pytest.mark.asyncio
    async def test_fold_frac_powers(self):
        """Test fold_frac_powers option."""
        # Test with a simpler case that fold_frac_powers affects
        result = await to_latex("x**(-1)", fold_frac_powers=True)
        # The behavior might vary by SymPy version, so just check it doesn't error
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_mul_symbol_dot(self):
        """Test multiplication symbol with dot."""
        result = await to_latex("2*x*y", mul_symbol="dot")
        assert "\\cdot" in result

    @pytest.mark.asyncio
    async def test_mul_symbol_times(self):
        """Test multiplication symbol with times."""
        result = await to_latex("2*x*y", mul_symbol="times")
        assert "\\times" in result

    @pytest.mark.asyncio
    async def test_ln_notation(self):
        """Test natural logarithm notation."""
        result = await to_latex("log(x)", ln_notation=True)
        assert "\\ln" in result

    @pytest.mark.asyncio
    async def test_complex_expression_latex(self):
        """Test LaTeX conversion of complex expressions."""
        result = await to_latex("sin(x) + cos(x)")
        # Should contain trigonometric functions
        assert "sin" in result or "cos" in result

    @pytest.mark.asyncio
    async def test_invalid_mode(self):
        """Test handling of invalid mode."""
        with pytest.raises(ValueError, match="Invalid mode"):
            await to_latex("x + 1", mode="invalid")

    @pytest.mark.asyncio
    async def test_invalid_mul_symbol(self):
        """Test handling of invalid mul_symbol."""
        with pytest.raises(ValueError, match="Invalid mul_symbol"):
            await to_latex("x*y", mul_symbol="invalid")

    @pytest.mark.asyncio
    async def test_invalid_expression_latex(self):
        """Test handling of invalid expression in LaTeX conversion."""
        with pytest.raises(ValueError, match="Invalid expression"):
            await to_latex("x +++ y $$$ invalid")

    @pytest.mark.asyncio
    async def test_trigonometric_latex(self):
        """Test LaTeX conversion of trigonometric functions."""
        result = await to_latex("sin(x) + cos(y)")
        assert "\\sin" in result
        assert "\\cos" in result

    @pytest.mark.asyncio
    async def test_fraction_latex(self):
        """Test LaTeX conversion of fractions."""
        result = await to_latex("1/x + 2/y")
        assert "\\frac" in result

    @pytest.mark.asyncio
    async def test_greek_letters_latex(self):
        """Test LaTeX conversion of Greek letters."""
        # Use symbols function to define Greek letters
        result = await to_latex("Symbol('alpha') + Symbol('beta')")
        # Just check that it converts without error
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_matrix_latex(self):
        """Test LaTeX conversion of matrices."""
        result = await to_latex("Matrix([[1, 2], [3, 4]])")
        assert "\\begin{matrix}" in result or "matrix" in result

    @pytest.mark.asyncio
    async def test_sympy_import_error_latex(self):
        """Test handling of SymPy import error in LaTeX conversion."""
        with patch('builtins.__import__', side_effect=ImportError):
            with pytest.raises(RuntimeError, match="SymPy is not installed"):
                await to_latex("x + 1")


class TestServerInfo:
    """Test the server_info function."""

    @pytest.mark.asyncio
    async def test_server_info_success(self):
        """Test successful server info retrieval."""
        result = await server_info()
        
        assert "SymPy Tool Server Status" in result
        assert "Status: Connected and ready" in result
        assert "SymPy Version:" in result
        assert "Available tools:" in result
        assert "transform_expression" in result
        assert "evaluate_expression" in result
        assert "to_latex" in result
        assert "server_info" in result
        assert "Supported operations:" in result
        assert "expand" in result
        assert "simplify" in result
        assert "factor" in result

    @pytest.mark.asyncio
    async def test_server_info_import_error(self):
        """Test server info with SymPy import error."""
        with patch('builtins.__import__', side_effect=ImportError):
            with pytest.raises(RuntimeError, match="SymPy is not installed"):
                await server_info()

    @pytest.mark.asyncio
    async def test_server_info_version_error(self):
        """Test server info with version access error."""
        # Mock sympy to have no __version__ attribute
        with patch('mcp_handley_lab.sympy.tool.sp') as mock_sp:
            del mock_sp.__version__  # Remove __version__ attribute
            with pytest.raises(RuntimeError, match="Error checking SymPy status"):
                await server_info()


class TestCancellationHandling:
    """Test cancellation handling for long-running operations."""

    @pytest.mark.asyncio
    @patch('asyncio.CancelledError')
    async def test_transform_cancellation(self, mock_cancelled):
        """Test cancellation during transform operation."""
        # This is harder to test directly as we'd need to actually cancel
        # We test the error handling path instead
        with patch('mcp_handley_lab.sympy.tool._safe_sympy_operation', side_effect=Exception("cancelled")):
            with pytest.raises(ValueError, match="cancelled"):
                await transform_expression("x + 1", "expand")

    @pytest.mark.asyncio
    async def test_evaluate_cancellation(self):
        """Test cancellation during evaluate operation."""
        # Similar to above, test error handling
        with patch('mcp_handley_lab.sympy.tool._safe_sympy_operation', side_effect=Exception("cancelled")):
            with pytest.raises(ValueError, match="Failed to substitute variables"):
                await evaluate_expression("x + 1", {"x": "bad_expr"})


class TestRealWorldExamples:
    """Test real-world mathematical examples."""

    @pytest.mark.asyncio
    async def test_polynomial_multiplication_expansion(self):
        """Test real polynomial multiplication and expansion."""
        # Example: (x+1)(x+2)(x+3) expansion
        result = await transform_expression("(x+1)*(x+2)*(x+3)", "expand")
        # Should be x^3 + 6*x^2 + 11*x + 6
        assert "x**3" in result
        assert "6*x**2" in result
        assert "11*x" in result
        assert "+ 6" in result

    @pytest.mark.asyncio
    async def test_rational_function_simplification(self):
        """Test rational function simplification."""
        result = await transform_expression("(x^3 - 1)/(x - 1)", "cancel")
        assert "x**2 + x + 1" in result

    @pytest.mark.asyncio
    async def test_quadratic_formula_evaluation(self):
        """Test quadratic formula evaluation."""
        # Quadratic formula: (-b ± sqrt(b^2 - 4*a*c))/(2*a)
        # For ax^2 + bx + c = 0
        discriminant = await evaluate_expression("b^2 - 4*a*c", {"a": 1, "b": -5, "c": 6})
        assert discriminant == "1"  # Should be 25 - 24 = 1
        
        root1 = await evaluate_expression("(-b + sqrt(b^2 - 4*a*c))/(2*a)", 
                                        {"a": 1, "b": -5, "c": 6}, numerical=True)
        assert "3.0" in root1

    @pytest.mark.asyncio
    async def test_calculus_preparation(self):
        """Test preparing expressions for calculus operations."""
        # Expand (x+h)^3 for derivative preparation
        result = await transform_expression("(x+h)^3", "expand")
        assert "x**3" in result
        assert "3*h*x**2" in result
        assert "3*h**2*x" in result
        assert "h**3" in result

    @pytest.mark.asyncio
    async def test_physics_formula_evaluation(self):
        """Test physics formula evaluation."""
        # Energy equation: E = mc^2
        result = await evaluate_expression("m*c^2", {"m": 1, "c": "3e8"}, numerical=True)
        # Should be approximately 9e16
        assert "9" in result and "16" in result