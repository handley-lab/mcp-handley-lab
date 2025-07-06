"""Integration tests for the MCP CLI."""
import pytest
import subprocess
import tempfile
import json
from pathlib import Path


@pytest.mark.integration
class TestCLIIntegration:
    """Integration tests that run the actual CLI without mocking."""
    
    def test_cli_help_integration(self):
        """Test CLI help command integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert "MCP CLI - Unified command-line interface" in result.stdout
        assert "--list-tools" in result.stdout
        assert "mcp-cli jq --help" in result.stdout
    
    def test_list_tools_integration(self):
        """Test --list-tools integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "--list-tools"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert "Available tools:" in result.stdout
        assert "jq" in result.stdout
        assert "vim" in result.stdout
        assert "arxiv" in result.stdout
        assert "Total:" in result.stdout
    
    def test_jq_tool_help_integration(self):
        """Test jq tool-specific help integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert "MCP CLI - jq tool" in result.stdout
        assert "Available functions:" in result.stdout
        assert "query" in result.stdout
        assert "validate" in result.stdout
        assert "Examples:" in result.stdout
    
    def test_jq_list_functions_integration(self):
        """Test jq --list-functions integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "--list-functions"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert "Functions in jq:" in result.stdout
        assert "query - " in result.stdout
        assert "validate - " in result.stdout
        assert "edit - " in result.stdout
    
    def test_jq_help_function_integration(self):
        """Test jq --help-function integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "--help-function", "query"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert "Function: query" in result.stdout
        assert "Description:" in result.stdout
        assert "Parameters:" in result.stdout
        assert "--data" in result.stdout
        assert "Usage:" in result.stdout
    
    def test_jq_execution_integration(self):
        """Test actual jq tool execution integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "query", 
             'data={"test": "value"}', "filter=.test"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert '"value"' in result.stdout
    
    def test_jq_positional_params_integration(self):
        """Test jq with positional parameters integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "query", 
             '{"test": "value"}', '.test'],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert '"value"' in result.stdout
    
    def test_jq_validate_integration(self):
        """Test jq validate function integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "validate",
             'data={"valid": "json"}'],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert "JSON is valid" in result.stdout
    
    def test_jq_server_info_integration(self):
        """Test jq server_info function integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "server_info"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert "JQ Tool Server Status" in result.stdout
        assert "Status: Connected and ready" in result.stdout
        assert "JQ Version:" in result.stdout
    
    def test_jq_json_output_integration(self):
        """Test jq with JSON output format integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "query",
             'data={"test": "value"}', "filter=.test", "--json-output"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        # Should be valid JSON
        output_data = json.loads(result.stdout.strip())
        assert "content" in output_data
    
    def test_params_from_json_integration(self):
        """Test --params-from-json integration."""
        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"data": '{"test": "value"}', "filter": ".test"}, f)
            json_file = f.name
        
        try:
            result = subprocess.run(
                ["python", "-m", "mcp_handley_lab.cli.main", "jq", "query",
                 "--params-from-json", json_file],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent
            )
            
            assert result.returncode == 0
            assert '"value"' in result.stdout
        finally:
            Path(json_file).unlink()
    
    def test_nonexistent_tool_integration(self):
        """Test error handling for nonexistent tool."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "nonexistent", "function"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 1
        assert "Tool 'nonexistent' not found" in result.stderr
    
    def test_nonexistent_function_integration(self):
        """Test error handling for nonexistent function."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "nonexistent"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 1
        assert "Function 'nonexistent' not found in jq" in result.stderr
    
    def test_tool_without_function_integration(self):
        """Test error when tool specified without function."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 1
        assert "Usage: mcp-cli jq <function>" in result.stderr
        assert "Use 'mcp-cli jq --list-functions'" in result.stderr


@pytest.mark.integration
class TestPerformanceIntegration:
    """Performance integration tests."""
    
    def test_help_performance(self):
        """Test that help commands are fast."""
        import time
        
        start_time = time.time()
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        end_time = time.time()
        
        assert result.returncode == 0
        # Should complete in under 200ms
        assert (end_time - start_time) < 0.2
    
    def test_list_tools_performance(self):
        """Test that --list-tools is fast."""
        import time
        
        start_time = time.time()
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "--list-tools"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        end_time = time.time()
        
        assert result.returncode == 0
        # Should complete in under 100ms (our performance target)
        assert (end_time - start_time) < 0.1
    
    def test_tool_help_performance(self):
        """Test that tool-specific help is reasonably fast."""
        import time
        
        start_time = time.time()
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        end_time = time.time()
        
        assert result.returncode == 0
        # Should complete in under 200ms
        assert (end_time - start_time) < 0.2


@pytest.mark.integration
@pytest.mark.slow
class TestArxivIntegration:
    """Integration tests for ArXiv tool (marked as slow)."""
    
    def test_arxiv_help_integration(self):
        """Test ArXiv tool help integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "arxiv", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent
        )
        
        assert result.returncode == 0
        assert "MCP CLI - arxiv tool" in result.stdout
        assert "search" in result.stdout
        assert "download" in result.stdout
    
    def test_arxiv_search_integration(self):
        """Test ArXiv search integration (network dependent)."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "arxiv", "search", 
             "au:Handley", "max_results=2"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
            timeout=30  # Network operations can be slow
        )
        
        # Should succeed if network is available
        if result.returncode == 0:
            assert "id" in result.stdout
            assert "title" in result.stdout
            assert "authors" in result.stdout
        else:
            # Network issues are acceptable in CI
            pytest.skip("Network unavailable for ArXiv integration test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])