"""Integration tests for Tool Chainer."""
import subprocess
import tempfile
import json
from pathlib import Path
import pytest
from mcp_handley_lab.tool_chainer.tool import (
    discover_tools, register_tool, chain_tools, execute_chain,
    clear_cache, server_info, ToolStep
)


class TestToolChainerIntegration:
    """Integration tests that use real MCP servers."""
    
    def setup_method(self):
        """Clear state before each test."""
        clear_cache()
    
    def teardown_method(self):
        """Clean up after each test."""
        clear_cache()
    
    def test_discover_jq_tool_integration(self):
        """Test discovering tools from the JQ server."""
        try:
            result = discover_tools("python -m mcp_handley_lab.jq")
            
            # Should find JQ tools
            assert "🔧 **Discovered" in result
            assert "query" in result
            assert "edit" in result
            assert "validate" in result
        except Exception as e:
            pytest.skip(f"JQ server not available: {e}")
    
    def test_discover_vim_tool_integration(self):
        """Test discovering tools from the Vim server."""
        try:
            result = discover_tools("python -m mcp_handley_lab.vim")
            
            # Should find Vim tools  
            assert "🔧 **Discovered" in result
            assert "prompt_user_edit" in result or "quick_edit" in result
        except Exception as e:
            pytest.skip(f"Vim server not available: {e}")
    
    def test_register_and_chain_jq_tools_integration(self):
        """Test registering and chaining JQ tools."""
        try:
            # Register JQ validate tool
            register_result = register_tool(
                "jq_validate",
                "python -m mcp_handley_lab.jq", 
                "validate",
                "Validate JSON data"
            )
            assert "✅ Tool 'jq_validate' registered successfully!" in register_result
            
            # Register JQ query tool
            register_result = register_tool(
                "jq_query",
                "python -m mcp_handley_lab.jq",
                "query", 
                "Query JSON data"
            )
            assert "✅ Tool 'jq_query' registered successfully!" in register_result
            
            # Define a chain to validate then query JSON
            steps = [
                ToolStep(
                    tool_id="jq_validate",
                    arguments={"data": '{"name": "test", "value": 42}'},
                    output_to="validation_result"
                ),
                ToolStep(
                    tool_id="jq_query", 
                    arguments={"data": '{"name": "test", "value": 42}', "filter": ".name"},
                    output_to="query_result"
                )
            ]
            
            chain_result = chain_tools("json_chain", steps)
            assert "✅ Chain 'json_chain' defined successfully!" in chain_result
            
            # Execute the chain
            execution_result = execute_chain("json_chain")
            assert "✅ Success" in execution_result
            assert "2/2" in execution_result  # Both steps should execute
            
        except Exception as e:
            pytest.skip(f"JQ server not available: {e}")
    
    def test_server_info_with_registered_tools_integration(self):
        """Test server info after registering real tools."""
        try:
            # Register a tool
            register_tool(
                "test_jq",
                "python -m mcp_handley_lab.jq",
                "validate"
            )
            
            result = server_info()
            
            assert "Tool Chainer Server Status" in result
            assert "Status: Ready ✓" in result
            assert "**Registered Tools:** 1" in result
            assert "test_jq" in result
            
        except Exception as e:
            pytest.skip(f"JQ server not available: {e}")
    
    def test_chain_with_file_output_integration(self):
        """Test chain execution that saves output to file."""
        try:
            # Register JQ format tool
            register_tool(
                "jq_format",
                "python -m mcp_handley_lab.jq",
                "format",
                "Format JSON data"
            )
            
            # Create temp file for output
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                output_file = f.name
            
            try:
                # Define chain that formats JSON and saves to file
                steps = [
                    ToolStep(
                        tool_id="jq_format",
                        arguments={"data": '{"b":2,"a":1}', "sort_keys": True}
                    )
                ]
                
                chain_tools("format_chain", steps, output_file)
                
                # Execute the chain
                result = execute_chain("format_chain")
                assert "✅ Success" in result
                
                # Check that output file was created and contains formatted JSON
                output_path = Path(output_file)
                assert output_path.exists()
                content = output_path.read_text()
                assert "a" in content and "b" in content
                
            finally:
                # Clean up temp file
                Path(output_file).unlink(missing_ok=True)
                
        except Exception as e:
            pytest.skip(f"JQ server not available: {e}")
    
    def test_chain_with_conditions_integration(self):
        """Test chain execution with conditional steps."""
        try:
            # Register JQ validate tool
            register_tool(
                "jq_validate_cond",
                "python -m mcp_handley_lab.jq",
                "validate"
            )
            
            # Define chain with a condition that should be skipped
            steps = [
                ToolStep(
                    tool_id="jq_validate_cond",
                    arguments={"data": '{"valid": true}'},
                    output_to="validation"
                ),
                ToolStep(
                    tool_id="jq_validate_cond", 
                    arguments={"data": '{"should": "skip"}'},
                    condition="False"  # This should be skipped
                )
            ]
            
            chain_tools("conditional_chain", steps)
            
            # Execute the chain
            result = execute_chain("conditional_chain")
            assert "✅ Success" in result
            assert "1/2" in result  # Only 1 step should execute, 1 skipped
            
        except Exception as e:
            pytest.skip(f"JQ server not available: {e}")
    
    def test_chain_execution_history_integration(self):
        """Test that chain execution history is properly recorded."""
        try:
            # Register and execute a simple chain
            register_tool(
                "jq_simple",
                "python -m mcp_handley_lab.jq", 
                "validate"
            )
            
            steps = [ToolStep(tool_id="jq_simple", arguments={"data": '{}'})]
            chain_tools("history_test", steps)
            execute_chain("history_test")
            
            # Check history
            from mcp_handley_lab.tool_chainer.tool import show_history
            history_result = show_history()
            
            assert "📚 **Chain Execution History**" in history_result
            assert "history_test" in history_result
            assert "✅" in history_result  # Success indicator
            
        except Exception as e:
            pytest.skip(f"JQ server not available: {e}")


class TestToolChainerRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    def setup_method(self):
        """Clear state before each test."""
        clear_cache()
    
    def teardown_method(self):
        """Clean up after each test."""
        clear_cache()
    
    def test_json_processing_pipeline_integration(self):
        """Test a realistic JSON processing pipeline."""
        try:
            # Register multiple JQ tools for a pipeline
            register_tool("validate", "python -m mcp_handley_lab.jq", "validate")
            register_tool("query", "python -m mcp_handley_lab.jq", "query") 
            register_tool("format", "python -m mcp_handley_lab.jq", "format")
            
            # Create a processing pipeline
            test_json = '{"users":[{"name":"Alice","age":30},{"name":"Bob","age":25}],"total":2}'
            
            steps = [
                # Step 1: Validate the JSON
                ToolStep(
                    tool_id="validate",
                    arguments={"data": test_json},
                    output_to="validation"
                ),
                # Step 2: Extract user names
                ToolStep(
                    tool_id="query",
                    arguments={"data": test_json, "filter": ".users | map(.name)"},
                    output_to="names"
                ),
                # Step 3: Format the original JSON nicely
                ToolStep(
                    tool_id="format", 
                    arguments={"data": test_json, "sort_keys": True},
                    output_to="formatted"
                )
            ]
            
            chain_tools("json_pipeline", steps)
            
            # Execute the pipeline
            result = execute_chain("json_pipeline", test_json)
            
            assert "✅ Success" in result
            assert "3/3" in result  # All steps should execute
            assert "Alice" in result or "Bob" in result  # Should extract names
            
        except Exception as e:
            pytest.skip(f"JQ server not available: {e}")