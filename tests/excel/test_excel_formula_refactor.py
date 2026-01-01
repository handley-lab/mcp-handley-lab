"""Tests for Excel formula refactoring operations."""

import io

from mcp_handley_lab.microsoft.excel.ops.cells import set_cell_formula
from mcp_handley_lab.microsoft.excel.ops.formula_refactor import (
    CellRef,
    parse_formula_references,
    shift_formula,
    shift_reference,
    update_formulas_after_delete,
    update_formulas_after_insert,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestParseFormulaReferences:
    """Tests for parse_formula_references."""

    def test_parse_simple_ref(self) -> None:
        """Parse simple cell reference."""
        refs = parse_formula_references("=A1")
        assert len(refs) == 1
        assert refs[0].col == "A"
        assert refs[0].row == 1
        assert refs[0].col_abs is False
        assert refs[0].row_abs is False

    def test_parse_absolute_ref(self) -> None:
        """Parse absolute cell reference."""
        refs = parse_formula_references("=$A$1")
        assert len(refs) == 1
        assert refs[0].col_abs is True
        assert refs[0].row_abs is True

    def test_parse_mixed_ref(self) -> None:
        """Parse mixed absolute/relative reference."""
        refs = parse_formula_references("=$A1")
        assert len(refs) == 1
        assert refs[0].col_abs is True
        assert refs[0].row_abs is False

        refs = parse_formula_references("=A$1")
        assert len(refs) == 1
        assert refs[0].col_abs is False
        assert refs[0].row_abs is True

    def test_parse_multiple_refs(self) -> None:
        """Parse formula with multiple references."""
        refs = parse_formula_references("=A1+B2*C3")
        assert len(refs) == 3
        cols = [r.col for r in refs]
        assert cols == ["A", "B", "C"]

    def test_parse_range_refs(self) -> None:
        """Parse range references."""
        refs = parse_formula_references("=SUM(A1:B10)")
        assert len(refs) == 2
        assert refs[0].col == "A"
        assert refs[0].row == 1
        assert refs[1].col == "B"
        assert refs[1].row == 10

    def test_parse_cross_sheet_ref(self) -> None:
        """Parse cross-sheet reference."""
        refs = parse_formula_references("=Sheet2!A1")
        assert len(refs) == 1
        assert refs[0].sheet == "Sheet2"
        assert refs[0].col == "A"
        assert refs[0].row == 1

    def test_parse_quoted_sheet_ref(self) -> None:
        """Parse reference with quoted sheet name."""
        refs = parse_formula_references("='My Sheet'!B5")
        assert len(refs) == 1
        assert refs[0].sheet == "My Sheet"
        assert refs[0].col == "B"
        assert refs[0].row == 5

    def test_parse_escaped_apostrophe_sheet_ref(self) -> None:
        """Parse reference with escaped apostrophe in sheet name."""
        refs = parse_formula_references("='O''Brien'!A1")
        assert len(refs) == 1
        assert refs[0].sheet == "O'Brien"  # unescaped
        assert refs[0].col == "A"
        assert refs[0].row == 1

    def test_parse_complex_formula(self) -> None:
        """Parse complex formula with mixed references."""
        refs = parse_formula_references("=IF(A1>0,Sheet2!$B$5,C3)")
        assert len(refs) == 3
        # A1
        assert refs[0].sheet is None
        assert refs[0].col == "A"
        assert refs[0].row == 1
        # Sheet2!$B$5
        assert refs[1].sheet == "Sheet2"
        assert refs[1].col == "B"
        assert refs[1].col_abs is True
        # C3
        assert refs[2].col == "C"


class TestCellRef:
    """Tests for CellRef dataclass."""

    def test_to_string_simple(self) -> None:
        """Simple reference converts back to string."""
        ref = CellRef(sheet=None, col="A", row=1, col_abs=False, row_abs=False)
        assert ref.to_string() == "A1"

    def test_to_string_absolute(self) -> None:
        """Absolute reference converts correctly."""
        ref = CellRef(sheet=None, col="B", row=5, col_abs=True, row_abs=True)
        assert ref.to_string() == "$B$5"

    def test_to_string_mixed(self) -> None:
        """Mixed reference converts correctly."""
        ref = CellRef(sheet=None, col="C", row=10, col_abs=True, row_abs=False)
        assert ref.to_string() == "$C10"

    def test_to_string_with_sheet(self) -> None:
        """Reference with sheet converts correctly."""
        ref = CellRef(sheet="Sheet2", col="A", row=1, col_abs=False, row_abs=False)
        assert ref.to_string() == "Sheet2!A1"

    def test_to_string_quoted_sheet(self) -> None:
        """Reference with space in sheet name gets quoted."""
        ref = CellRef(sheet="My Sheet", col="A", row=1, col_abs=False, row_abs=False)
        assert ref.to_string() == "'My Sheet'!A1"

    def test_to_string_sheet_with_apostrophe(self) -> None:
        """Reference with apostrophe in sheet name gets escaped."""
        ref = CellRef(sheet="O'Brien", col="A", row=1, col_abs=False, row_abs=False)
        assert ref.to_string() == "'O''Brien'!A1"

    def test_to_string_sheet_with_leading_digit(self) -> None:
        """Reference with leading digit in sheet name gets quoted."""
        ref = CellRef(sheet="2024 Data", col="A", row=1, col_abs=False, row_abs=False)
        assert ref.to_string() == "'2024 Data'!A1"


class TestShiftReference:
    """Tests for shift_reference."""

    def test_shift_row_down(self) -> None:
        """Shift reference down."""
        ref = CellRef(sheet=None, col="A", row=5, col_abs=False, row_abs=False)
        shifted = shift_reference(ref, row_delta=3)
        assert shifted.row == 8

    def test_shift_row_up(self) -> None:
        """Shift reference up."""
        ref = CellRef(sheet=None, col="A", row=5, col_abs=False, row_abs=False)
        shifted = shift_reference(ref, row_delta=-2)
        assert shifted.row == 3

    def test_shift_col_right(self) -> None:
        """Shift reference right."""
        ref = CellRef(sheet=None, col="B", row=1, col_abs=False, row_abs=False)
        shifted = shift_reference(ref, col_delta=2)
        assert shifted.col == "D"

    def test_shift_col_left(self) -> None:
        """Shift reference left."""
        ref = CellRef(sheet=None, col="D", row=1, col_abs=False, row_abs=False)
        shifted = shift_reference(ref, col_delta=-2)
        assert shifted.col == "B"

    def test_shift_absolute_row_unchanged(self) -> None:
        """Absolute row reference not shifted."""
        ref = CellRef(sheet=None, col="A", row=5, col_abs=False, row_abs=True)
        shifted = shift_reference(ref, row_delta=3)
        assert shifted.row == 5  # unchanged

    def test_shift_absolute_col_unchanged(self) -> None:
        """Absolute column reference not shifted."""
        ref = CellRef(sheet=None, col="B", row=1, col_abs=True, row_abs=False)
        shifted = shift_reference(ref, col_delta=2)
        assert shifted.col == "B"  # unchanged

    def test_shift_invalid_returns_none(self) -> None:
        """Invalid shift (row < 1) returns None."""
        ref = CellRef(sheet=None, col="A", row=2, col_abs=False, row_abs=False)
        shifted = shift_reference(ref, row_delta=-5)
        assert shifted is None

    def test_shift_target_sheet_filters(self) -> None:
        """Only shift refs on target sheet."""
        ref = CellRef(sheet="Sheet2", col="A", row=1, col_abs=False, row_abs=False)
        # Different sheet - should not shift
        shifted = shift_reference(ref, row_delta=5, target_sheet="Sheet1")
        assert shifted.row == 1  # unchanged

        # Same sheet - should shift
        shifted = shift_reference(ref, row_delta=5, target_sheet="Sheet2")
        assert shifted.row == 6


class TestShiftFormula:
    """Tests for shift_formula."""

    def test_shift_simple_formula(self) -> None:
        """Shift simple formula references."""
        result = shift_formula("=A1+B2", row_delta=5)
        assert result == "=A6+B7"

    def test_shift_preserves_absolute(self) -> None:
        """Absolute references preserved."""
        result = shift_formula("=$A$1+B2", row_delta=5)
        assert result == "=$A$1+B7"

    def test_shift_invalid_becomes_ref_error(self) -> None:
        """Invalid shift becomes #REF!."""
        result = shift_formula("=A1", row_delta=-5)
        assert result == "=#REF!"

    def test_shift_col_delta(self) -> None:
        """Shift column delta."""
        result = shift_formula("=B1+C2", col_delta=2)
        assert result == "=D1+E2"


class TestUpdateFormulasAfterInsert:
    """Tests for update_formulas_after_insert."""

    def test_insert_row_shifts_refs(self) -> None:
        """Inserting rows shifts formula references."""
        pkg = ExcelPackage.new()
        # Set a formula in A10 that references A5
        set_cell_formula(pkg, "Sheet1", "A10", "A5")

        count = update_formulas_after_insert(
            pkg, "Sheet1", index=3, count=2, is_row=True
        )

        # A5 should become A7 (shifted by 2)
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        from mcp_handley_lab.microsoft.excel.constants import qn

        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "A7"
        assert count == 1

    def test_insert_col_shifts_refs(self) -> None:
        """Inserting columns shifts formula references."""
        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "E1", "C1")

        update_formulas_after_insert(pkg, "Sheet1", index=2, count=1, is_row=False)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        # C1 should become D1 (shifted by 1)
        assert formula == "D1"

    def test_insert_shifts_absolute_refs(self) -> None:
        """Absolute references ARE shifted on structural insert (unlike copy/fill)."""
        pkg = ExcelPackage.new()
        # $A$5 is at/after insertion point (row 3), should shift to $A$7
        set_cell_formula(pkg, "Sheet1", "A10", "$A$5")

        update_formulas_after_insert(pkg, "Sheet1", index=3, count=2, is_row=True)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        # Structural insert shifts all refs, including absolute
        assert formula == "$A$7"

    def test_insert_preserves_absolute_before_insertion(self) -> None:
        """Absolute refs before insertion point are not shifted."""
        pkg = ExcelPackage.new()
        # $A$1 is before insertion point (row 3), should NOT shift
        set_cell_formula(pkg, "Sheet1", "A10", "$A$1")

        update_formulas_after_insert(pkg, "Sheet1", index=3, count=2, is_row=True)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "$A$1"  # unchanged (before insertion)

    def test_insert_col_shifts_absolute_col(self) -> None:
        """Insert column shifts absolute column ref."""
        pkg = ExcelPackage.new()
        # $C$1 at/after insertion point (col 2=B), should shift to $D$1
        set_cell_formula(pkg, "Sheet1", "E1", "$C$1")

        update_formulas_after_insert(pkg, "Sheet1", index=2, count=1, is_row=False)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "$D$1"

    def test_insert_col_shifts_mixed_ref(self) -> None:
        """Insert column shifts mixed ref with absolute column."""
        pkg = ExcelPackage.new()
        # $C1 (absolute col, relative row) should shift to $D1
        set_cell_formula(pkg, "Sheet1", "E1", "$C1")

        update_formulas_after_insert(pkg, "Sheet1", index=2, count=1, is_row=False)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "$D1"


class TestUpdateFormulasAfterDelete:
    """Tests for update_formulas_after_delete."""

    def test_delete_row_shifts_refs(self) -> None:
        """Deleting rows shifts formula references."""
        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "A10", "A8")

        count = update_formulas_after_delete(
            pkg, "Sheet1", index=3, count=2, is_row=True
        )

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        # A8 should become A6 (shifted up by 2)
        assert formula == "A6"
        assert count == 1

    def test_delete_ref_to_deleted_becomes_error(self) -> None:
        """Reference to deleted cell becomes #REF!."""
        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "A10", "A3")  # A3 will be deleted

        update_formulas_after_delete(pkg, "Sheet1", index=3, count=1, is_row=True)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "#REF!"

    def test_delete_col_shifts_refs(self) -> None:
        """Deleting columns shifts formula references."""
        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "F1", "D1")

        update_formulas_after_delete(pkg, "Sheet1", index=2, count=1, is_row=False)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        # D1 should become C1 (shifted left by 1)
        assert formula == "C1"

    def test_delete_absolute_before_range_preserved(self) -> None:
        """Absolute ref before deleted range is preserved."""
        pkg = ExcelPackage.new()
        # $A$1 is before deleted range (rows 3-4)
        set_cell_formula(pkg, "Sheet1", "A10", "$A$1")

        update_formulas_after_delete(pkg, "Sheet1", index=3, count=2, is_row=True)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "$A$1"  # unchanged (before deleted range)

    def test_delete_absolute_after_range_shifted(self) -> None:
        """Absolute ref after deleted range is shifted."""
        pkg = ExcelPackage.new()
        # $A$8 is after deleted range (rows 3-4), should shift to $A$6
        set_cell_formula(pkg, "Sheet1", "A10", "$A$8")

        update_formulas_after_delete(pkg, "Sheet1", index=3, count=2, is_row=True)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        # Structural delete shifts all refs after deletion, including absolute
        assert formula == "$A$6"

    def test_delete_absolute_in_range_becomes_ref_error(self) -> None:
        """Absolute ref to deleted cell becomes #REF!."""
        pkg = ExcelPackage.new()
        # $A$3 is in deleted range (rows 3-4)
        set_cell_formula(pkg, "Sheet1", "A10", "$A$3")

        update_formulas_after_delete(pkg, "Sheet1", index=3, count=2, is_row=True)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "#REF!"  # deleted cell

    def test_delete_col_shifts_absolute_col(self) -> None:
        """Delete column shifts absolute column ref after deletion."""
        pkg = ExcelPackage.new()
        # $D$1 is after deletion point (col 2=B), should shift to $C$1
        set_cell_formula(pkg, "Sheet1", "F1", "$D$1")

        update_formulas_after_delete(pkg, "Sheet1", index=2, count=1, is_row=False)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "$C$1"

    def test_delete_col_absolute_in_range_becomes_ref_error(self) -> None:
        """Delete column makes absolute ref in deleted range become #REF!."""
        pkg = ExcelPackage.new()
        # $B$1 is in deleted range (col 2)
        set_cell_formula(pkg, "Sheet1", "F1", "$B$1")

        update_formulas_after_delete(pkg, "Sheet1", index=2, count=1, is_row=False)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "#REF!"


class TestFormulaRefactorPersistence:
    """Tests for formula changes persisting through save/load."""

    def test_shifted_formula_persists(self) -> None:
        """Shifted formula persists through save/load."""
        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "A10", "A5")
        update_formulas_after_insert(pkg, "Sheet1", index=3, count=2, is_row=True)

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg2.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "A7"


class TestIntegrationWithRangeOps:
    """Tests that formula refactoring is integrated with insert/delete operations."""

    def test_insert_rows_updates_formulas(self) -> None:
        """insert_rows from ops/ranges updates formulas."""
        from mcp_handley_lab.microsoft.excel.ops.ranges import insert_rows

        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "A10", "A5")

        insert_rows(pkg, "Sheet1", row_num=3, count=2)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        # A5 should become A7 (shifted down by 2)
        assert formula == "A7"

    def test_delete_rows_updates_formulas(self) -> None:
        """delete_rows from ops/ranges updates formulas."""
        from mcp_handley_lab.microsoft.excel.ops.ranges import delete_rows

        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "A10", "A8")

        delete_rows(pkg, "Sheet1", row_num=3, count=2)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        # A8 should become A6 (shifted up by 2)
        assert formula == "A6"

    def test_insert_columns_updates_formulas(self) -> None:
        """insert_columns from ops/ranges updates formulas."""
        from mcp_handley_lab.microsoft.excel.ops.ranges import insert_columns

        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "E1", "C1")

        insert_columns(pkg, "Sheet1", col_ref="B", count=2)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        # C1 should become E1 (shifted right by 2)
        assert formula == "E1"

    def test_delete_columns_updates_formulas(self) -> None:
        """delete_columns from ops/ranges updates formulas."""
        from mcp_handley_lab.microsoft.excel.ops.ranges import delete_columns

        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "F1", "D1")

        delete_columns(pkg, "Sheet1", col_ref="B", count=2)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        # D1 should become B1 (shifted left by 2)
        assert formula == "B1"

    def test_delete_rows_ref_to_deleted_becomes_error(self) -> None:
        """delete_rows makes refs to deleted cells become #REF!."""
        from mcp_handley_lab.microsoft.excel.ops.ranges import delete_rows

        pkg = ExcelPackage.new()
        set_cell_formula(pkg, "Sheet1", "A10", "A3")

        delete_rows(pkg, "Sheet1", row_num=3, count=1)

        from mcp_handley_lab.microsoft.excel.constants import qn

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        formula = None
        for row in sheet_xml.find(qn("x:sheetData")).findall(qn("x:row")):
            for cell in row.findall(qn("x:c")):
                f = cell.find(qn("x:f"))
                if f is not None and f.text:
                    formula = f.text
        assert formula == "#REF!"
