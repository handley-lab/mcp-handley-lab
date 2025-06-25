"""Integration tests for JQ tool.

These tests verify real jq CLI interactions and file operations.
Run with: pytest tests/integration/test_jq_integration.py -v
"""
import json
import pytest
import tempfile
from pathlib import Path
from mcp_handley_lab.jq.tool import query, edit, read, validate, format, server_info


class TestJQIntegration:
    """Integration tests for JQ tool using real jq CLI."""

    @pytest.fixture
    def sample_json_data(self):
        """Sample JSON data for testing."""
        return {
            "users": [
                {"name": "Alice", "age": 30, "city": "New York"},
                {"name": "Bob", "age": 25, "city": "San Francisco"}
            ],
            "total": 2,
            "metadata": {
                "version": "1.0",
                "created": "2024-01-01"
            }
        }

    @pytest.fixture
    def json_file(self, sample_json_data, tmp_path):
        """Create a temporary JSON file."""
        json_file = tmp_path / "test_data.json"
        json_file.write_text(json.dumps(sample_json_data, indent=2))
        return json_file

    def test_server_info_integration(self):
        """Test that jq CLI is available and returns version info."""
        try:
            result = server_info()
            assert "JQ Tool Server Status" in result
            assert "Connected and ready" in result
            assert "JQ Version:" in result
        except RuntimeError as e:
            pytest.skip(f"jq CLI not available: {e}")

    def test_query_with_json_string(self):
        """Test querying JSON string data."""
        json_data = '{"name": "test", "value": 42}'
        
        # Test identity filter
        result = query(json_data, ".")
        parsed = json.loads(result)
        assert parsed["name"] == "test"
        assert parsed["value"] == 42

        # Test field extraction
        result = query(json_data, ".name")
        assert result == '"test"'

        # Test raw output
        result = query(json_data, ".name", raw_output=True)
        assert result == "test"

        # Test compact output
        result = query(json_data, ".", compact=True)
        assert "\n" not in result
        assert "name" in result and "value" in result

    def test_query_with_file_path(self, json_file):
        """Test querying JSON file."""
        # Test reading from file
        result = query(str(json_file), ".total")
        assert result == "2"

        # Test array operations
        result = query(str(json_file), ".users | length")
        assert result == "2"

        # Test nested field access
        result = query(str(json_file), ".metadata.version", raw_output=True)
        assert result == "1.0"

        # Test array element access
        result = query(str(json_file), ".users[0].name", raw_output=True)
        assert result == "Alice"

    def test_query_complex_filters(self, json_file):
        """Test complex jq filters."""
        # Test select filter
        result = query(str(json_file), '.users[] | select(.age > 27) | .name', raw_output=True)
        assert "Alice" in result

        # Test map operation
        result = query(str(json_file), '[.users[].name]')
        names = json.loads(result)
        assert names == ["Alice", "Bob"]

        # Test conditional
        result = query(str(json_file), '.users[] | if .age > 27 then .name else empty end', raw_output=True)
        assert result == "Alice"

    def test_read_file(self, json_file):
        """Test reading and pretty-printing JSON file."""
        result = read(str(json_file))
        
        # Should be pretty-printed JSON
        assert "users" in result
        assert "Alice" in result
        assert "\n" in result  # Should have newlines for pretty printing

        # Test with filter
        result = read(str(json_file), ".users")
        users = json.loads(result)
        assert len(users) == 2
        assert users[0]["name"] == "Alice"

    def test_validate_valid_json(self, json_file):
        """Test validating valid JSON."""
        # Test with file
        result = validate(str(json_file))
        assert result == "JSON is valid"

        # Test with string
        result = validate('{"valid": true}')
        assert result == "JSON is valid"

    def test_validate_invalid_json(self):
        """Test validating invalid JSON."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            validate('{"invalid": json}')

        with pytest.raises(ValueError, match="Invalid JSON"):
            validate('{missing_quotes: true}')

    def test_format_json(self, sample_json_data):
        """Test formatting JSON data."""
        compact_json = json.dumps(sample_json_data, separators=(',', ':'))
        
        # Test pretty formatting
        result = format(compact_json)
        assert "\n" in result
        assert "  " in result  # Should have indentation

        # Test compact formatting - use compact JSON as input
        result = format(compact_json, compact=True)
        assert "\n" not in result or result.count("\n") <= 1

        # Test sort keys
        result = format('{"b": 2, "a": 1}', sort_keys=True)
        lines = result.split('\n')
        # Find the lines with keys
        key_lines = [line for line in lines if '": ' in line]
        assert '"a"' in key_lines[0]  # 'a' should come before 'b'
        assert '"b"' in key_lines[1]

    def test_edit_file_in_place(self, json_file):
        """Test editing JSON file in-place."""
        original_content = json_file.read_text()
        
        # Test updating a field
        result = edit(str(json_file), '.total = 3')
        assert "Successfully edited" in result
        assert "backup saved" in result.lower()
        
        # Verify the change
        modified_data = json.loads(json_file.read_text())
        assert modified_data["total"] == 3
        
        # Verify backup was created
        backup_file = json_file.with_suffix(json_file.suffix + ".bak")
        assert backup_file.exists()
        backup_data = json.loads(backup_file.read_text())
        assert backup_data["total"] == 2

    def test_edit_without_backup(self, json_file):
        """Test editing without creating backup."""
        result = edit(str(json_file), '.metadata.version = "2.0"', backup=False)
        assert "Successfully edited" in result
        # Check that backup message is not in the result (avoid filename confusion)
        assert "(backup saved to" not in result
        
        # Verify no backup was created
        backup_file = json_file.with_suffix(json_file.suffix + ".bak")
        assert not backup_file.exists()
        
        # Verify the change
        modified_data = json.loads(json_file.read_text())
        assert modified_data["metadata"]["version"] == "2.0"

    def test_edit_add_array_element(self, json_file):
        """Test adding element to array."""
        result = edit(str(json_file), '.users += [{"name": "Charlie", "age": 35, "city": "Boston"}]')
        assert "Successfully edited" in result
        
        modified_data = json.loads(json_file.read_text())
        assert len(modified_data["users"]) == 3
        assert modified_data["users"][2]["name"] == "Charlie"

    def test_edit_delete_field(self, json_file):
        """Test deleting field."""
        result = edit(str(json_file), 'del(.metadata.created)')
        assert "Successfully edited" in result
        
        modified_data = json.loads(json_file.read_text())
        assert "created" not in modified_data["metadata"]
        assert "version" in modified_data["metadata"]  # Other fields should remain

    def test_error_handling_invalid_filter(self, json_file):
        """Test error handling for invalid jq filters."""
        with pytest.raises(ValueError, match="jq error"):
            query(str(json_file), "invalid_filter_syntax")

    def test_error_handling_nonexistent_file(self):
        """Test error handling for non-existent files."""
        with pytest.raises(ValueError, match="jq error"):
            query("/nonexistent/file.json", ".")

    def test_error_handling_edit_invalid_syntax(self, json_file):
        """Test error handling for invalid edit syntax."""
        with pytest.raises(ValueError, match="jq error"):
            edit(str(json_file), "invalid syntax")

    def test_comprehensive_workflow(self, tmp_path):
        """Test a complete workflow with multiple operations."""
        # Create initial data
        data_file = tmp_path / "workflow.json"
        initial_data = {
            "products": [
                {"id": 1, "name": "Widget", "price": 10.0},
                {"id": 2, "name": "Gadget", "price": 20.0}
            ],
            "stats": {"total_value": 30.0}
        }
        data_file.write_text(json.dumps(initial_data))
        
        # Validate the file
        assert validate(str(data_file)) == "JSON is valid"
        
        # Query product count
        count = query(str(data_file), ".products | length")
        assert count == "2"
        
        # Add a new product
        edit(str(data_file), '.products += [{"id": 3, "name": "Doodad", "price": 15.0}]')
        
        # Update total value
        edit(str(data_file), '.stats.total_value = (.products | map(.price) | add)')
        
        # Verify final state
        final_data = json.loads(read(str(data_file)))
        assert len(final_data["products"]) == 3
        assert final_data["stats"]["total_value"] == 45.0
        
        # Format and verify structure
        formatted = format(str(data_file), sort_keys=True)
        assert '"id"' in formatted
        assert '"name"' in formatted