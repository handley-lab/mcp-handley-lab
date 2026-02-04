"""Tests for Word formatting and JSON parameter parsing fixes.

Tests for GitHub issues:
- #217: formatting parameter must be JSON string, not dict
- #218: append op ignores formatting.style
- #215: append op cannot create tables
"""

import json
import tempfile
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.microsoft.word.constants import qn
from mcp_handley_lab.microsoft.word.package import WordPackage
from mcp_handley_lab.microsoft.word.shared import (
    _parse_bool_param,
    _parse_json_param,
)
from mcp_handley_lab.microsoft.word.tool import mcp


def _ops(operations: list[dict]) -> str:
    """Helper to convert operation list to ops JSON string."""
    return json.dumps(operations)


class TestParseJsonParam:
    """Tests for the _parse_json_param helper function."""

    def test_dict_passthrough(self):
        """Dict is returned as-is."""
        d = {"key": "value"}
        result = _parse_json_param(d, "test")
        assert result == d
        assert result is d  # Same object

    def test_list_passthrough(self):
        """List is returned as-is when expected_type=list."""
        lst = [1, 2, 3]
        result = _parse_json_param(lst, "test", list)
        assert result == lst
        assert result is lst

    def test_string_parsed_to_dict(self):
        """JSON string is parsed to dict."""
        result = _parse_json_param('{"key": "value"}', "test")
        assert result == {"key": "value"}

    def test_string_parsed_to_list(self):
        """JSON string is parsed to list when expected_type=list."""
        result = _parse_json_param("[1, 2, 3]", "test", list)
        assert result == [1, 2, 3]

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        assert _parse_json_param("", "test") is None
        assert _parse_json_param("", "test", list) is None

    def test_none_returns_none(self):
        """None returns None."""
        assert _parse_json_param(None, "test") is None

    def test_falsy_zero_returns_none(self):
        """Falsy values like 0 return None."""
        assert _parse_json_param(0, "test") is None

    def test_invalid_json_raises(self):
        """Invalid JSON raises ValueError with field name."""
        with pytest.raises(ValueError, match="test must be valid JSON"):
            _parse_json_param("{invalid json}", "test")

    def test_wrong_type_after_parse_raises(self):
        """Parsing to wrong type raises ValueError."""
        with pytest.raises(ValueError, match="test must be dict, got list"):
            _parse_json_param("[1, 2, 3]", "test", dict)

    def test_wrong_native_type_raises(self):
        """Native value of wrong type raises ValueError."""
        with pytest.raises(ValueError, match="test must be dict.*got list"):
            _parse_json_param([1, 2, 3], "test", dict)

    def test_tuple_of_types(self):
        """Accepts tuple of types."""
        # Dict accepted
        assert _parse_json_param({"a": 1}, "test", (dict, list)) == {"a": 1}
        # List accepted
        assert _parse_json_param([1, 2], "test", (dict, list)) == [1, 2]
        # String parsed to dict
        assert _parse_json_param('{"a": 1}', "test", (dict, list)) == {"a": 1}
        # String parsed to list
        assert _parse_json_param("[1, 2]", "test", (dict, list)) == [1, 2]


class TestParseBoolParam:
    """Tests for the _parse_bool_param helper function."""

    def test_bool_passthrough(self):
        """Boolean is returned as-is."""
        assert _parse_bool_param(True, "test") is True
        assert _parse_bool_param(False, "test") is False

    def test_string_true_values(self):
        """String 'true', '1', 'yes' return True."""
        assert _parse_bool_param("true", "test") is True
        assert _parse_bool_param("TRUE", "test") is True
        assert _parse_bool_param("True", "test") is True
        assert _parse_bool_param("1", "test") is True
        assert _parse_bool_param("yes", "test") is True
        assert _parse_bool_param("YES", "test") is True

    def test_string_false_values(self):
        """String 'false', '0', 'no' return False."""
        assert _parse_bool_param("false", "test") is False
        assert _parse_bool_param("FALSE", "test") is False
        assert _parse_bool_param("0", "test") is False
        assert _parse_bool_param("no", "test") is False

    def test_invalid_string_raises(self):
        """Invalid string raises ValueError."""
        with pytest.raises(ValueError, match="test must be boolean"):
            _parse_bool_param("maybe", "test")

    def test_invalid_type_raises(self):
        """Invalid type raises ValueError."""
        with pytest.raises(ValueError, match="test must be boolean"):
            _parse_bool_param(123, "test")


@pytest.fixture
async def temp_docx():
    """Create a temporary docx file path."""
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        path = Path(f.name)
    path.unlink(missing_ok=True)  # Remove so edit() auto-creates
    yield path
    path.unlink(missing_ok=True)


class TestFormattingParameterType:
    """Tests for issue #217: formatting parameter type handling."""

    @pytest.mark.asyncio
    async def test_formatting_as_dict(self, temp_docx):
        """Formatting can be passed as a native dict."""
        # Create document with append and dict formatting
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Test paragraph",
                            "formatting": {"bold": True, "alignment": "center"},
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        # Verify formatting was applied
        pkg = WordPackage.open(str(temp_docx))
        p = pkg.body.find(qn("w:p"))
        assert p is not None

        # Check alignment
        pPr = p.find(qn("w:pPr"))
        assert pPr is not None
        jc = pPr.find(qn("w:jc"))
        assert jc is not None
        assert jc.get(qn("w:val")) == "center"

    @pytest.mark.asyncio
    async def test_formatting_as_string(self, temp_docx):
        """Formatting can be passed as a JSON string."""
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Test paragraph",
                            "formatting": '{"alignment": "right"}',
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        # Verify formatting was applied
        pkg = WordPackage.open(str(temp_docx))
        p = pkg.body.find(qn("w:p"))
        pPr = p.find(qn("w:pPr"))
        jc = pPr.find(qn("w:jc"))
        assert jc.get(qn("w:val")) == "right"


class TestAppendFormattingStyle:
    """Tests for issue #218: append op formatting.style."""

    @pytest.mark.asyncio
    async def test_append_paragraph_with_style(self, temp_docx):
        """Append paragraph applies formatting.style."""
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Styled paragraph",
                            "formatting": {"style": "Heading1"},
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        # Verify style was applied
        pkg = WordPackage.open(str(temp_docx))
        p = pkg.body.find(qn("w:p"))
        pPr = p.find(qn("w:pPr"))
        pStyle = pPr.find(qn("w:pStyle"))
        assert pStyle is not None
        assert pStyle.get(qn("w:val")) == "Heading1"

    @pytest.mark.asyncio
    async def test_append_heading_with_style_override(self, temp_docx):
        """Formatting.style overrides heading_level style."""
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "heading",
                            "content_data": "Override heading",
                            "heading_level": 1,
                            "formatting": {"style": "Title"},
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        # Verify Title style (not Heading1) was applied
        pkg = WordPackage.open(str(temp_docx))
        p = pkg.body.find(qn("w:p"))
        pPr = p.find(qn("w:pPr"))
        pStyle = pPr.find(qn("w:pStyle"))
        assert pStyle is not None
        assert pStyle.get(qn("w:val")) == "Title"

    @pytest.mark.asyncio
    async def test_append_with_style_and_other_formatting(self, temp_docx):
        """Append applies both style and other formatting."""
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_data": "Combined formatting",
                            "formatting": {
                                "style": "Normal",
                                "alignment": "center",
                                "bold": True,
                            },
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        # Verify both style and alignment were applied
        pkg = WordPackage.open(str(temp_docx))
        p = pkg.body.find(qn("w:p"))
        pPr = p.find(qn("w:pPr"))
        assert pPr.find(qn("w:pStyle")) is not None
        assert pPr.find(qn("w:jc")).get(qn("w:val")) == "center"


class TestTableCreation:
    """Tests for issue #215: table creation via append."""

    @pytest.mark.asyncio
    async def test_append_empty_table_with_dimensions(self, temp_docx):
        """Create empty table with rows/cols spec."""
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": {"rows": 3, "cols": 4},
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        # Verify table dimensions
        pkg = WordPackage.open(str(temp_docx))
        tbl = pkg.body.find(qn("w:tbl"))
        assert tbl is not None
        rows = tbl.findall(qn("w:tr"))
        assert len(rows) == 3
        for row in rows:
            cells = row.findall(qn("w:tc"))
            assert len(cells) == 4

    @pytest.mark.asyncio
    async def test_append_table_with_dict_as_string(self, temp_docx):
        """Create empty table with JSON string spec."""
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": '{"rows": 2, "cols": 3}',
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        pkg = WordPackage.open(str(temp_docx))
        tbl = pkg.body.find(qn("w:tbl"))
        rows = tbl.findall(qn("w:tr"))
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_append_table_with_data(self, temp_docx):
        """Create table with 2D array data."""
        table_data = [["A", "B"], ["C", "D"]]
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": table_data,
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        # Verify data was populated
        pkg = WordPackage.open(str(temp_docx))
        tbl = pkg.body.find(qn("w:tbl"))
        rows = tbl.findall(qn("w:tr"))
        first_cell = rows[0].find(qn("w:tc"))
        text = "".join(first_cell.itertext())
        assert "A" in text

    @pytest.mark.asyncio
    async def test_append_table_with_style(self, temp_docx):
        """Create table with style applied."""
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "append",
                            "content_type": "table",
                            "content_data": {"rows": 2, "cols": 2},
                            "formatting": {"style": "TableGrid"},
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        # Verify table style was applied
        pkg = WordPackage.open(str(temp_docx))
        tbl = pkg.body.find(qn("w:tbl"))
        tblPr = tbl.find(qn("w:tblPr"))
        tblStyle = tblPr.find(qn("w:tblStyle"))
        assert tblStyle is not None
        assert tblStyle.get(qn("w:val")) == "TableGrid"

    @pytest.mark.asyncio
    async def test_table_invalid_dimensions(self, temp_docx):
        """Invalid table dimensions raise ValueError."""
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {
                    "file_path": str(temp_docx),
                    "ops": _ops(
                        [
                            {
                                "op": "append",
                                "content_type": "table",
                                "content_data": {"rows": 0, "cols": 2},
                            }
                        ]
                    ),
                },
            )
        assert "at least 1 row" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_table_excessive_size(self, temp_docx):
        """Excessively large table raises ValueError."""
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "edit",
                {
                    "file_path": str(temp_docx),
                    "ops": _ops(
                        [
                            {
                                "op": "append",
                                "content_type": "table",
                                "content_data": {"rows": 200, "cols": 200},
                            }
                        ]
                    ),
                },
            )
        assert "exceeds maximum" in str(exc_info.value)


class TestInsertFormatting:
    """Tests for insert_before/insert_after with formatting."""

    @pytest.mark.asyncio
    async def test_insert_before_with_style(self, temp_docx):
        """Insert_before applies formatting.style."""
        # Create initial paragraph
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops([{"op": "append", "content_data": "Original"}]),
            },
        )
        elem_id = result["element_id"]

        # Insert with style
        _, result = await mcp.call_tool(
            "edit",
            {
                "file_path": str(temp_docx),
                "ops": _ops(
                    [
                        {
                            "op": "insert_before",
                            "target_id": elem_id,
                            "content_data": "Inserted",
                            "formatting": {"style": "Heading1"},
                        }
                    ]
                ),
            },
        )
        assert result["success"] is True

        # Verify style was applied to inserted paragraph
        pkg = WordPackage.open(str(temp_docx))
        paragraphs = pkg.body.findall(qn("w:p"))
        # First paragraph should be the inserted one with Heading1 style
        pPr = paragraphs[0].find(qn("w:pPr"))
        pStyle = pPr.find(qn("w:pStyle"))
        assert pStyle.get(qn("w:val")) == "Heading1"
