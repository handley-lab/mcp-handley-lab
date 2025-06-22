"""Unit tests for JQ tool."""
import json
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from mcp_handley_lab.jq.tool import (
    query, edit, read, validate, format, server_info, _resolve_data, _run_jq
)


class TestJQTool:
    """Test cases for JQ tool methods."""
    
    @pytest.fixture
    def sample_json(self):
        """Sample JSON data for testing."""
        return {
            "name": "test",
            "version": "1.0",
            "items": [1, 2, 3],
            "nested": {"key": "value"}
        }
    
    @pytest.fixture
    def json_file(self, sample_json, tmp_path):
        """Create a temporary JSON file."""
        file_path = tmp_path / "test.json"
        file_path.write_text(json.dumps(sample_json, indent=2))
        return str(file_path)
    
    def test_query_with_json_string(self):
        """Test query with JSON string input."""
        json_str = '{"numbers": [1, 2, 3, 4, 5]}'
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.return_value = "15"
            result = query(json_str, ".numbers | add")
            assert result == "15"
            mock_run_jq.assert_called_once_with([".numbers | add"], input_text=json_str)
    
    def test_query_with_file(self, json_file):
        """Test query with file path input."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.return_value = '"test"'
            result = query(json_file, ".name")
            assert result == '"test"'
            mock_run_jq.assert_called_once_with([".name", json_file])
    
    def test_query_compact_output(self):
        """Test query with compact output."""
        json_str = '{"a": 1, "b": 2}'
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.return_value = '{"a":1,"b":2}'
            result = query(json_str, ".", compact=True)
            mock_run_jq.assert_called_once_with(["-c", "."], input_text=json_str)
    
    def test_query_raw_output(self):
        """Test query with raw output."""
        json_str = '{"name": "test"}'
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.return_value = "test"
            result = query(json_str, ".name", raw_output=True)
            mock_run_jq.assert_called_once_with(["-r", ".name"], input_text=json_str)
    
    def test_query_error(self):
        """Test query with jq error."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.side_effect = ValueError("jq error: parse error")
            with pytest.raises(ValueError, match="jq error: parse error"):
                query('invalid json', ".")
    
    def test_edit_with_backup(self, json_file):
        """Test edit with backup creation."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.return_value = '{"name": "edited"}'
            result = edit(json_file, '.name = "edited"')
            assert "backup saved to" in result
            assert Path(json_file + ".bak").exists()
    
    def test_edit_without_backup(self, json_file):
        """Test edit without backup."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.return_value = '{"name": "edited"}'
            result = edit(json_file, '.name = "edited"', backup=False)
            assert "Successfully edited" in result
            assert "(backup saved to" not in result
    
    def test_edit_error(self, json_file):
        """Test edit with jq error."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.side_effect = ValueError("jq error: invalid filter")
            with pytest.raises(ValueError, match="jq error: invalid filter"):
                edit(json_file, 'invalid filter')
    
    def test_read(self, json_file):
        """Test read method."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.return_value = '{\n  "name": "test"\n}'
            result = read(json_file)
            assert '"name": "test"' in result
            mock_run_jq.assert_called_once_with([".", json_file])
    
    def test_read_with_filter(self, json_file):
        """Test read with custom filter."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.return_value = '"test"'
            result = read(json_file, ".name")
            assert result == '"test"'
            mock_run_jq.assert_called_once_with([".name", json_file])
    
    def test_read_error(self, json_file):
        """Test read with jq error."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.side_effect = ValueError("jq error: invalid filter")
            with pytest.raises(ValueError, match="jq error: invalid filter"):
                read(json_file, "invalid filter")
    
    def test_validate_valid_json_string(self):
        """Test validate with valid JSON string."""
        result = validate('{"valid": "json"}')
        assert result == "JSON is valid"
    
    def test_validate_valid_json_file(self, json_file):
        """Test validate with valid JSON file."""
        result = validate(json_file)
        assert result == "JSON is valid"
    
    def test_validate_invalid_json(self):
        """Test validate with invalid JSON."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            validate('{invalid json}')
    
    def test_format_pretty(self):
        """Test format with pretty printing."""
        json_str = '{"a":1,"b":2}'
        result = format(json_str)
        assert "{\n" in result
        assert '"a": 1' in result
    
    def test_format_compact(self):
        """Test format with compact output."""
        json_str = '{"a": 1, "b": 2}'
        result = format(json_str, compact=True)
        assert result == '{"a":1,"b":2}'
    
    def test_format_sort_keys(self):
        """Test format with sorted keys."""
        json_str = '{"z": 1, "a": 2}'
        result = format(json_str, sort_keys=True)
        # 'a' should come before 'z'
        assert result.index('"a"') < result.index('"z"')
    
    def test_format_from_file(self, json_file):
        """Test format with file input."""
        result = format(json_file)
        assert "{\n" in result
        assert '"name": "test"' in result
    
    def test_server_info_success(self):
        """Test server_info when jq is available."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.return_value = "jq-1.6"
            result = server_info()
            assert "JQ Tool Server Status" in result
            assert "Connected and ready" in result
            assert "jq-1.6" in result
            assert "Available tools:" in result
            mock_run_jq.assert_called_once_with(["--version"])
    
    def test_server_info_jq_not_found(self):
        """Test server_info when jq is not installed."""
        with patch('mcp_handley_lab.jq.tool._run_jq') as mock_run_jq:
            mock_run_jq.side_effect = RuntimeError("jq command not found. Please install jq.")
            with pytest.raises(RuntimeError, match="jq command not found"):
                server_info()

    def test_resolve_data_with_file(self, json_file):
        """Test _resolve_data with existing file."""
        result = _resolve_data(json_file)
        assert '"name": "test"' in result

    def test_resolve_data_with_string(self):
        """Test _resolve_data with JSON string."""
        json_str = '{"test": "data"}'
        result = _resolve_data(json_str)
        assert result == json_str

    def test_resolve_data_with_nonexistent_file(self):
        """Test _resolve_data with non-existent file path."""
        fake_path = "/does/not/exist.json"
        result = _resolve_data(fake_path)
        assert result == fake_path

    def test_run_jq_success(self):
        """Test _run_jq with successful execution."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="success", stderr="", returncode=0
            )
            result = _run_jq(["."], input_text='{"test": "data"}')
            assert result == "success"

    def test_run_jq_error(self):
        """Test _run_jq with jq error."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="", stderr="parse error", returncode=1
            )
            with pytest.raises(ValueError, match="jq error: parse error"):
                _run_jq(["."], input_text='invalid json')

    def test_run_jq_not_found(self):
        """Test _run_jq when jq command is not found."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            with pytest.raises(RuntimeError, match="jq command not found"):
                _run_jq(["."])