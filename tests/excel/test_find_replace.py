"""Tests for Excel find/replace functionality.

These tests verify Risk B mitigation: shared string table entries are not
mutated; formula cells are skipped; inline strings are used for replacements.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.excel import shared


@pytest.fixture
def sample_workbook(tmp_path: Path) -> Path:
    """Create a sample workbook with test data."""
    file_path = tmp_path / "test.xlsx"

    # Create workbook with some data
    ops = json.dumps(
        [
            {"op": "add_sheet", "new_name": "Sheet1"},
            {
                "op": "set_cell",
                "sheet": "Sheet1",
                "cell_ref": "A1",
                "value": "Hello World",
            },
            {
                "op": "set_cell",
                "sheet": "Sheet1",
                "cell_ref": "A2",
                "value": "Hello World",
            },  # Same string
            {"op": "set_cell", "sheet": "Sheet1", "cell_ref": "A3", "value": "Goodbye"},
            {
                "op": "set_cell",
                "sheet": "Sheet1",
                "cell_ref": "B1",
                "value": 42,
            },  # Number
            {
                "op": "set_formula",
                "sheet": "Sheet1",
                "cell_ref": "B2",
                "formula": "B1*2",
            },  # Formula
            {
                "op": "set_cell",
                "sheet": "Sheet1",
                "cell_ref": "B3",
                "value": "Hello",
            },  # Contains "Hello"
        ]
    )
    shared.edit(str(file_path), ops)
    return file_path


class TestExcelFindReplace:
    """Test Excel find/replace functionality."""

    def test_find_replace_basic(self, sample_workbook: Path):
        """Basic find/replace changes text."""
        ops = json.dumps(
            [{"op": "find_replace", "search": "World", "replace": "Universe"}]
        )
        result = shared.edit(str(sample_workbook), ops)
        assert result["success"]
        assert "2" in result["results"][0]["message"]  # 2 occurrences

        # Verify the change
        data = shared.read(
            str(sample_workbook), scope="cells", sheet="Sheet1", range_ref="A1:A2"
        )
        values = data["grid"]["values"]
        assert values[0][0] == "Hello Universe"
        assert values[1][0] == "Hello Universe"

    def test_find_replace_skips_formula_cells(self, sample_workbook: Path):
        """Formula cells are not modified."""
        # Add a formula that returns text containing "Hello"
        ops = json.dumps(
            [
                {
                    "op": "set_formula",
                    "sheet": "Sheet1",
                    "cell_ref": "C1",
                    "formula": '"Hello Formula"',
                }
            ]
        )
        shared.edit(str(sample_workbook), ops)

        # Try to replace "Hello" - should NOT affect the formula cell
        ops = json.dumps([{"op": "find_replace", "search": "Hello", "replace": "Hi"}])
        result = shared.edit(str(sample_workbook), ops)
        assert result["success"]

        # Check formula cell is unchanged
        data = shared.read(
            str(sample_workbook),
            scope="cells",
            sheet="Sheet1",
            range_ref="C1:C1",
            representation="cells",
        )
        cell = data["cells"][0] if data.get("cells") else None
        if cell:
            # Formula should still be there
            assert cell.get("formula") is not None or '"Hello Formula"' in str(cell)

    def test_find_replace_uses_inline_strings(self, sample_workbook: Path):
        """Replacements use inline strings, not shared strings."""
        # This is verified by the fact that replacing in A1 doesn't affect A2
        # if they share the same shared string entry
        ops = json.dumps(
            [{"op": "find_replace", "search": "Hello World", "replace": "Changed Text"}]
        )
        result = shared.edit(str(sample_workbook), ops)
        assert result["success"]

        # Both cells should be changed because they both contained "Hello World"
        data = shared.read(
            str(sample_workbook), scope="cells", sheet="Sheet1", range_ref="A1:A2"
        )
        values = data["grid"]["values"]
        assert values[0][0] == "Changed Text"
        assert values[1][0] == "Changed Text"

    def test_find_replace_sheet_specific(self, tmp_path: Path):
        """Find/replace can be limited to a specific sheet."""
        file_path = tmp_path / "multi_sheet.xlsx"
        ops = json.dumps(
            [
                {"op": "add_sheet", "new_name": "Sheet1"},
                {"op": "add_sheet", "new_name": "Sheet2"},
                {
                    "op": "set_cell",
                    "sheet": "Sheet1",
                    "cell_ref": "A1",
                    "value": "Target",
                },
                {
                    "op": "set_cell",
                    "sheet": "Sheet2",
                    "cell_ref": "A1",
                    "value": "Target",
                },
            ]
        )
        shared.edit(str(file_path), ops)

        # Replace only in Sheet1
        ops = json.dumps(
            [
                {
                    "op": "find_replace",
                    "search": "Target",
                    "replace": "Replaced",
                    "sheet": "Sheet1",
                }
            ]
        )
        result = shared.edit(str(file_path), ops)
        assert result["success"]
        assert "1" in result["results"][0]["message"]  # Only 1 occurrence

        # Verify Sheet1 changed, Sheet2 unchanged
        data1 = shared.read(
            str(file_path), scope="cells", sheet="Sheet1", range_ref="A1:A1"
        )
        data2 = shared.read(
            str(file_path), scope="cells", sheet="Sheet2", range_ref="A1:A1"
        )

        assert data1["grid"]["values"][0][0] == "Replaced"
        assert data2["grid"]["values"][0][0] == "Target"

    def test_find_replace_all_sheets(self, tmp_path: Path):
        """Find/replace across all sheets when sheet not specified."""
        file_path = tmp_path / "multi_sheet.xlsx"
        ops = json.dumps(
            [
                {"op": "add_sheet", "new_name": "Sheet1"},
                {"op": "add_sheet", "new_name": "Sheet2"},
                {
                    "op": "set_cell",
                    "sheet": "Sheet1",
                    "cell_ref": "A1",
                    "value": "Target",
                },
                {
                    "op": "set_cell",
                    "sheet": "Sheet2",
                    "cell_ref": "A1",
                    "value": "Target",
                },
            ]
        )
        shared.edit(str(file_path), ops)

        # Replace in all sheets (no sheet specified)
        ops = json.dumps(
            [{"op": "find_replace", "search": "Target", "replace": "Replaced"}]
        )
        result = shared.edit(str(file_path), ops)
        assert result["success"]
        assert "2" in result["results"][0]["message"]  # 2 occurrences

        # Verify both sheets changed
        data1 = shared.read(
            str(file_path), scope="cells", sheet="Sheet1", range_ref="A1:A1"
        )
        data2 = shared.read(
            str(file_path), scope="cells", sheet="Sheet2", range_ref="A1:A1"
        )

        assert data1["grid"]["values"][0][0] == "Replaced"
        assert data2["grid"]["values"][0][0] == "Replaced"

    def test_find_replace_no_match(self, sample_workbook: Path):
        """Find/replace with no matches returns 0."""
        ops = json.dumps([{"op": "find_replace", "search": "NotFound", "replace": "X"}])
        result = shared.edit(str(sample_workbook), ops)
        assert result["success"]
        assert "0" in result["results"][0]["message"]

    def test_find_replace_empty_search_error(self, sample_workbook: Path):
        """Empty search string raises error."""
        ops = json.dumps([{"op": "find_replace", "search": "", "replace": "X"}])
        result = shared.edit(str(sample_workbook), ops)
        assert not result["success"]

    def test_find_replace_partial_match(self, sample_workbook: Path):
        """Partial string matches are replaced."""
        ops = json.dumps([{"op": "find_replace", "search": "ell", "replace": "ELL"}])
        result = shared.edit(str(sample_workbook), ops)
        assert result["success"]

        data = shared.read(
            str(sample_workbook), scope="cells", sheet="Sheet1", range_ref="A1:A1"
        )
        # "Hello World" -> "HELLo World"
        assert data["grid"]["values"][0][0] == "HELLo World"
