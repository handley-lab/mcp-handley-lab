"""Integration tests for the MCP CLI."""
import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
class TestCLIIntegration:
    """Integration tests that run the actual CLI without mocking."""

    def test_cli_help_integration(self):
        """Test CLI help command integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0
        assert "mcp-cli - Unified command-line interface for MCP tools" in result.stdout
        assert "--list-tools" in result.stdout
        assert "mcp-cli arxiv --help" in result.stdout

    def test_list_tools_integration(self):
        """Test --list-tools integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "--list-tools"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
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
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0
        assert "NAME" in result.stdout
        assert "jq" in result.stdout
        assert "FUNCTIONS" in result.stdout
        assert "query" in result.stdout
        assert "validate" in result.stdout
        assert "EXAMPLES" in result.stdout

    def test_jq_execution_integration(self):
        """Test actual jq tool execution integration."""
        # Use a temp file to avoid JSON auto-parsing issues
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
            f.write('{"test": "value"}')
            f.flush()  # Ensure content is written

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "query",
                    f"data={f.name}",
                    "filter=.test",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0
            # Check that the OperationResult contains the expected value
            output = json.loads(result.stdout)
            result_json = json.loads(output["content"][0]["text"])
            assert '"value"' in result_json["message"]

    def test_jq_positional_params_integration(self):
        """Test jq with positional parameters integration."""
        # Use a temp file to avoid JSON auto-parsing issues
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
            f.write('{"test": "value"}')
            f.flush()  # Ensure content is written

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "query",
                    f.name,
                    ".test",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0
            # Check that the OperationResult contains the expected value
            output = json.loads(result.stdout)
            result_json = json.loads(output["content"][0]["text"])
            assert '"value"' in result_json["message"]

    def test_jq_validate_integration(self):
        """Test jq validate function integration."""
        # Use a temp file to avoid JSON auto-parsing issues
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
            f.write('{"valid": "json"}')
            f.flush()  # Ensure content is written

            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "validate",
                    f"data={f.name}",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0
            assert "JSON is valid" in result.stdout

    def test_jq_edit_integration(self):
        """Test jq edit function integration."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "original_value", "other": "data"}, f)
            f.flush()
            temp_path = f.name

        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "edit",
                    f"file_path={temp_path}",
                    'filter=.test = "new_value"',
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0
            assert "success" in result.stdout.lower() or "updated" in result.stdout.lower()
            
            # Verify the file was actually edited
            with open(temp_path) as f:
                updated_data = json.load(f)
                assert updated_data["test"] == "new_value"
                assert updated_data["other"] == "data"  # Other data preserved
                
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_jq_format_integration(self):
        """Test jq format function integration."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"b": 2, "a": 1}, f)
            f.flush()
            temp_path = f.name
        
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "format",
                    f"data={temp_path}",
                    "compact=false",
                    "sort_keys=true",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0
            # Should format with proper indentation and sorted keys
            output = json.loads(result.stdout)
            result_json = json.loads(output["content"][0]["text"])
            formatted = result_json["message"]
            assert "{\n" in formatted  # Non-compact format
            assert '"a"' in formatted and '"b"' in formatted
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_jq_format_compact_integration(self):
        """Test jq format with compact option integration."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "value"}, f)
            f.flush()
            temp_path = f.name
        
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "format",
                    f"data={temp_path}",
                    "compact=true",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0
            output = json.loads(result.stdout)
            result_json = json.loads(output["content"][0]["text"])
            formatted = result_json["message"]
            # Compact format should not have newlines
            assert "\n" not in formatted.strip()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_jq_read_integration(self):
        """Test jq read function integration."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "read_value", "nested": {"key": "nested_value"}}, f)
            f.flush()
            temp_path = f.name

        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "read",
                    f"file_path={temp_path}",
                    "filter=.nested.key",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0
            output = json.loads(result.stdout)
            result_json = json.loads(output["content"][0]["text"])
            assert '"nested_value"' in result_json["message"]
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_jq_query_raw_output_integration(self):
        """Test jq query with raw output option integration."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"message": "hello world"}, f)
            f.flush()
            temp_path = f.name
        
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "query",
                    f"data={temp_path}",
                    "filter=.message",
                    "raw_output=true",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0
            output = json.loads(result.stdout)
            result_json = json.loads(output["content"][0]["text"])
            # Raw output should not have quotes around strings
            assert "hello world" in result_json["message"]
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_jq_query_compact_integration(self):
        """Test jq query with compact option integration."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"array": [1, 2, 3]}, f)
            f.flush()
            temp_path = f.name
        
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "query",
                    f"data={temp_path}",
                    "filter=.array",
                    "compact=true",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0
            output = json.loads(result.stdout)
            result_json = json.loads(output["content"][0]["text"])
            # Compact output should be on single line
            assert "[1,2,3]" in result_json["message"] or "[1, 2, 3]" in result_json["message"]
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_jq_validate_invalid_json_integration(self):
        """Test jq validate with invalid JSON integration."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "mcp_handley_lab.cli.main",
                "jq",
                "validate",
                'data={"invalid": json}',  # Invalid JSON
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0  # CLI succeeds but reports error in JSON
        output = json.loads(result.stdout)
        assert output.get("isError") is True
        assert "error" in output["content"][0]["text"].lower() or "expecting" in output["content"][0]["text"].lower()

    def test_jq_server_info_integration(self):
        """Test jq server_info function integration."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "server_info"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0
        # Parse the JSON output to check ServerInfo structure
        output = json.loads(result.stdout)
        assert "content" in output
        assert len(output["content"]) > 0
        server_info_json = json.loads(output["content"][0]["text"])
        assert server_info_json["name"] == "JQ Tool"
        assert server_info_json["status"] == "active"
        assert "jq" in server_info_json["dependencies"]

    def test_jq_json_output_integration(self):
        """Test jq with JSON output format integration."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "mcp_handley_lab.cli.main",
                "jq",
                "query",
                'data={"test": "value"}',
                "filter=.test",
                "--json-output",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0
        # Should be valid JSON
        output_data = json.loads(result.stdout.strip())
        assert "content" in output_data

    def test_params_from_json_integration(self):
        """Test --params-from-json integration."""
        import tempfile

        # Create temporary JSON data file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as data_f:
            data_f.write('{"test": "value"}')
            data_f.flush()  # Ensure content is written

            # Create temporary params JSON file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as params_f:
                json.dump({"data": data_f.name, "filter": ".test"}, params_f)
                params_f.flush()  # Ensure content is written

                result = subprocess.run(
                    [
                        "python",
                        "-m",
                        "mcp_handley_lab.cli.main",
                        "jq",
                        "query",
                        "--params-from-json",
                        params_f.name,
                    ],
                    capture_output=True,
                    text=True,
                    cwd=Path(__file__).parent.parent.parent,
                )

                assert result.returncode == 0
                # Check that the OperationResult contains the expected value
                output = json.loads(result.stdout)
                result_json = json.loads(output["content"][0]["text"])
                assert '"value"' in result_json["message"]

    def test_nonexistent_tool_integration(self):
        """Test error handling for nonexistent tool."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "nonexistent", "function"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 1
        assert "Tool 'nonexistent' not found" in result.stderr

    def test_nonexistent_function_integration(self):
        """Test error handling for nonexistent function."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "nonexistent"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 1
        assert "Function 'nonexistent' not found in jq" in result.stderr

    def test_tool_without_function_integration(self):
        """Test error when tool specified without function."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 1
        assert "Usage: mcp-cli jq <function>" in result.stderr
        assert "Use 'mcp-cli jq --help'" in result.stderr

    def test_invalid_parameter_types_integration(self):
        """Test error handling for invalid parameter types."""
        # Test with non-boolean value for boolean parameter
        result = subprocess.run(
            [
                "python",
                "-m",
                "mcp_handley_lab.cli.main",
                "jq",
                "query",
                'data={"test": "value"}',
                "filter=.test",
                "compact=maybe",  # Invalid boolean value
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # MCP tools return structured errors in JSON format
        assert result.returncode == 0  # CLI succeeds but reports error in JSON
        output = json.loads(result.stdout)
        assert output.get("isError") is True
        assert "validation error" in output["content"][0]["text"].lower()

    def test_missing_required_parameters_integration(self):
        """Test error handling for missing required parameters."""
        # Test jq query without data parameter
        result = subprocess.run(
            [
                "python",
                "-m",
                "mcp_handley_lab.cli.main",
                "jq",
                "query",
                "filter=.test",  # Missing data parameter
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # MCP tools return structured errors in JSON format
        assert result.returncode == 0  # CLI succeeds but reports error in JSON
        output = json.loads(result.stdout)
        assert output.get("isError") is True
        assert "validation error" in output["content"][0]["text"].lower()

    def test_file_not_found_integration(self):
        """Test error handling for non-existent files."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "mcp_handley_lab.cli.main",
                "jq",
                "read",
                "file_path=/nonexistent/path/file.json",
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0  # CLI succeeds but reports error in JSON
        output = json.loads(result.stdout)
        assert output.get("isError") is True
        assert "error" in output["content"][0]["text"].lower() or "not found" in output["content"][0]["text"].lower()

    def test_malformed_json_file_integration(self):
        """Test error handling for malformed JSON files."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"incomplete": json malformed')  # Malformed JSON
            f.flush()
            temp_path = f.name

        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "read",
                    f"file_path={temp_path}",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0  # CLI succeeds but reports error in JSON
            output = json.loads(result.stdout)
            assert output.get("isError") is True
            assert "error" in output["content"][0]["text"].lower() or "invalid" in output["content"][0]["text"].lower()

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_invalid_jq_filter_integration(self):
        """Test error handling for invalid jq filter expressions."""
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "value"}, f)
            f.flush()
            temp_path = f.name
        
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "query",
                    f"data={temp_path}",
                    "filter=.invalid.syntax.[",  # Invalid jq filter
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            assert result.returncode == 0  # CLI succeeds but reports error in JSON
            output = json.loads(result.stdout)
            assert output.get("isError") is True
            assert "error" in output["content"][0]["text"].lower()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_permission_denied_integration(self):
        """Test error handling for permission denied scenarios."""
        # Try to edit a file in a directory we can't write to
        result = subprocess.run(
            [
                "python",
                "-m",
                "mcp_handley_lab.cli.main",
                "jq",
                "edit",
                "file_path=/root/protected.json",  # Permission denied
                'filter=.test = "value"',
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        assert result.returncode == 0  # CLI succeeds but reports error in JSON
        output = json.loads(result.stdout)
        assert output.get("isError") is True
        assert ("permission" in output["content"][0]["text"].lower() or 
                "error" in output["content"][0]["text"].lower())

    def test_network_tool_offline_integration(self):
        """Test error handling for network-dependent tools when offline."""
        # Test ArXiv tool with invalid ID (should fail fast)
        result = subprocess.run(
            [
                "python",
                "-m",
                "mcp_handley_lab.cli.main",
                "arxiv",
                "download",
                "arxiv_id=invalid.9999.99999",  # Invalid ArXiv ID format
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
            timeout=30,  # Don't wait too long
        )

        # Should fail with network error or invalid ID error
        assert result.returncode == 0  # CLI succeeds but reports error in JSON
        output = json.loads(result.stdout)
        assert output.get("isError") is True
        assert ("error" in output["content"][0]["text"].lower() or 
                "invalid" in output["content"][0]["text"].lower() or
                "not found" in output["content"][0]["text"].lower())

    def test_tool_with_no_arguments_integration(self):
        """Test tools called with no arguments at all."""
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )

        # Should show help, not crash
        assert result.returncode in [0, 1]  # Help might exit with 0 or 1
        assert "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_very_large_input_integration(self):
        """Test handling of very large input data."""
        import tempfile
        
        # Create large JSON string (but not so large as to cause timeout)
        large_data = {"items": [{"id": i, "data": "x" * 100} for i in range(100)]}
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(large_data, f)
            f.flush()
            temp_path = f.name
        
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "query",
                    f"data={temp_path}",
                    "filter=.items | length",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
                timeout=10,  # Reasonable timeout
            )

            # Should handle large input gracefully
            if result.returncode == 0:
                output = json.loads(result.stdout)
                if not output.get("isError"):
                    result_json = json.loads(output["content"][0]["text"])
                    assert "100" in result_json["message"]
                else:
                    # If it fails, should fail gracefully with structured error
                    assert "error" in output["content"][0]["text"].lower()
            else:
                # Unexpected CLI failure
                assert False, f"Unexpected CLI failure: {result.stderr}"
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_special_characters_in_parameters_integration(self):
        """Test handling of special characters in parameters."""
        import tempfile
        
        # Create a JSON file with special characters
        special_json = '{"key": "value with spaces", "unicode": "café", "symbols": "!@#$%"}'
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(special_json)
            f.flush()
            temp_path = f.name
        
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "mcp_handley_lab.cli.main",
                    "jq",
                    "read",
                    f"file_path={temp_path}",
                    "filter=.unicode",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )

            # Should handle special characters properly
            assert result.returncode == 0
            output = json.loads(result.stdout)
            if not output.get("isError"):
                result_json = json.loads(output["content"][0]["text"])
                assert "café" in result_json["message"]
            else:
                # If encoding issues, should fail gracefully with structured error
                assert "error" in output["content"][0]["text"].lower()
                
        finally:
            Path(temp_path).unlink(missing_ok=True)


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
            cwd=Path(__file__).parent.parent.parent,
        )
        end_time = time.time()

        assert result.returncode == 0
        # Should complete in under 2 seconds (adjusted for CI environments)
        assert (end_time - start_time) < 2.0

    def test_list_tools_performance(self):
        """Test that --list-tools is fast."""
        import time

        start_time = time.time()
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "--list-tools"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )
        end_time = time.time()

        assert result.returncode == 0
        # Should complete in under 1 second (adjusted for CI environments)
        assert (end_time - start_time) < 1.0

    def test_tool_help_performance(self):
        """Test that tool-specific help is reasonably fast."""
        import time

        start_time = time.time()
        result = subprocess.run(
            ["python", "-m", "mcp_handley_lab.cli.main", "jq", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,
        )
        end_time = time.time()

        assert result.returncode == 0
        # Should complete in under 2 seconds (adjusted for CI environments)
        assert (end_time - start_time) < 2.0


