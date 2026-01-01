"""Tests for Excel data validation operations."""

import io

import pytest

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.validation import (
    add_validation,
    list_validations,
    remove_validation,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestListValidations:
    """Tests for list_validations."""

    def test_list_validations_empty(self) -> None:
        """New sheet has no validations."""
        pkg = ExcelPackage.new()

        validations = list_validations(pkg, "Sheet1")

        assert validations == []

    def test_list_validations_after_add(self) -> None:
        """List validations returns added rules."""
        pkg = ExcelPackage.new()
        add_validation(pkg, "Sheet1", "A1:A10", "list", formula1='"Yes,No,Maybe"')

        validations = list_validations(pkg, "Sheet1")

        assert len(validations) == 1
        assert validations[0].ref == "A1:A10"
        assert validations[0].type == "list"

    def test_list_validations_multiple(self) -> None:
        """List multiple validations."""
        pkg = ExcelPackage.new()
        add_validation(pkg, "Sheet1", "A1:A10", "list", formula1='"A,B,C"')
        add_validation(
            pkg, "Sheet1", "B1:B10", "whole", operator="greaterThan", formula1="0"
        )
        add_validation(
            pkg,
            "Sheet1",
            "C1:C10",
            "decimal",
            operator="between",
            formula1="0",
            formula2="100",
        )

        validations = list_validations(pkg, "Sheet1")

        assert len(validations) == 3


class TestAddValidation:
    """Tests for add_validation."""

    def test_add_validation_list(self) -> None:
        """Add dropdown list validation."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg, "Sheet1", "A1:A10", "list", formula1='"Option1,Option2,Option3"'
        )

        assert validation.ref == "A1:A10"
        assert validation.type == "list"
        assert validation.formula1 == '"Option1,Option2,Option3"'
        assert validation.show_dropdown is True

        # Verify in XML
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        dvs = sheet_xml.find(qn("x:dataValidations"))
        assert dvs is not None
        assert dvs.get("count") == "1"

    def test_add_validation_whole_number(self) -> None:
        """Add whole number validation with operator."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg,
            "Sheet1",
            "B1:B20",
            "whole",
            operator="greaterThanOrEqual",
            formula1="1",
        )

        assert validation.type == "whole"
        assert validation.operator == "greaterThanOrEqual"
        assert validation.formula1 == "1"

    def test_add_validation_between(self) -> None:
        """Add validation with between operator (two formulas)."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg,
            "Sheet1",
            "C1:C10",
            "decimal",
            operator="between",
            formula1="0",
            formula2="100",
        )

        assert validation.operator == "between"
        assert validation.formula1 == "0"
        assert validation.formula2 == "100"

    def test_add_validation_with_error_message(self) -> None:
        """Add validation with error alert."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg,
            "Sheet1",
            "A1:A5",
            "whole",
            operator="greaterThan",
            formula1="0",
            error_title="Invalid Input",
            error_message="Please enter a positive number",
        )

        assert validation.error_title == "Invalid Input"
        assert validation.error_message == "Please enter a positive number"

        # Verify in XML
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        dv = sheet_xml.find(qn("x:dataValidations")).find(qn("x:dataValidation"))
        assert dv.get("errorTitle") == "Invalid Input"
        assert dv.get("error") == "Please enter a positive number"
        assert dv.get("showErrorMessage") == "1"

    def test_add_validation_with_prompt(self) -> None:
        """Add validation with input prompt."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg,
            "Sheet1",
            "A1:A5",
            "list",
            formula1='"Red,Green,Blue"',
            prompt_title="Select Color",
            prompt="Choose a color from the list",
        )

        assert validation.prompt_title == "Select Color"
        assert validation.prompt == "Choose a color from the list"

        # Verify in XML
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        dv = sheet_xml.find(qn("x:dataValidations")).find(qn("x:dataValidation"))
        assert dv.get("showInputMessage") == "1"

    def test_add_validation_no_blank(self) -> None:
        """Add validation that doesn't allow blanks."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg, "Sheet1", "A1", "list", formula1='"Yes,No"', allow_blank=False
        )

        assert validation.allow_blank is False

    def test_add_validation_hide_dropdown(self) -> None:
        """Add list validation with hidden dropdown."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg, "Sheet1", "A1", "list", formula1='"A,B,C"', show_dropdown=False
        )

        assert validation.show_dropdown is False

        # Verify in XML - showDropDown="1" means HIDE
        sheet_xml = pkg.get_sheet_xml("Sheet1")
        dv = sheet_xml.find(qn("x:dataValidations")).find(qn("x:dataValidation"))
        assert dv.get("showDropDown") == "1"

    def test_add_validation_date(self) -> None:
        """Add date validation."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg,
            "Sheet1",
            "D1:D10",
            "date",
            operator="greaterThan",
            formula1="44197",  # Excel date serial for 2021-01-01
        )

        assert validation.type == "date"

    def test_add_validation_text_length(self) -> None:
        """Add text length validation."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg,
            "Sheet1",
            "E1:E10",
            "textLength",
            operator="lessThanOrEqual",
            formula1="100",
        )

        assert validation.type == "textLength"

    def test_add_validation_custom(self) -> None:
        """Add custom formula validation."""
        pkg = ExcelPackage.new()

        validation = add_validation(
            pkg,
            "Sheet1",
            "A1:A10",
            "custom",
            formula1="=MOD(A1,2)=0",  # Even numbers only
        )

        assert validation.type == "custom"
        assert validation.formula1 == "=MOD(A1,2)=0"

    def test_add_validation_persists(self) -> None:
        """Validation persists through save/load."""
        pkg = ExcelPackage.new()
        add_validation(
            pkg,
            "Sheet1",
            "A1:B5",
            "list",
            formula1='"Apple,Banana,Cherry"',
            error_title="Error",
            error_message="Pick a fruit",
        )

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        validations = list_validations(pkg2, "Sheet1")
        assert len(validations) == 1
        assert validations[0].formula1 == '"Apple,Banana,Cherry"'
        assert validations[0].error_title == "Error"

    def test_add_validation_has_id(self) -> None:
        """ValidationInfo has content-addressed ID."""
        pkg = ExcelPackage.new()

        validation = add_validation(pkg, "Sheet1", "A1:A10", "list", formula1='"A,B"')

        assert validation.id is not None
        assert validation.id.startswith("validation_")


class TestRemoveValidation:
    """Tests for remove_validation."""

    def test_remove_validation(self) -> None:
        """Remove existing validation."""
        pkg = ExcelPackage.new()
        add_validation(pkg, "Sheet1", "A1:A10", "list", formula1='"Yes,No"')

        remove_validation(pkg, "Sheet1", "A1:A10")

        validations = list_validations(pkg, "Sheet1")
        assert validations == []

    def test_remove_validation_not_found(self) -> None:
        """Remove non-existent validation raises KeyError."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="Validation not found"):
            remove_validation(pkg, "Sheet1", "Z1:Z10")

    def test_remove_validation_preserves_others(self) -> None:
        """Removing one validation preserves others."""
        pkg = ExcelPackage.new()
        add_validation(pkg, "Sheet1", "A1:A10", "list", formula1='"A,B"')
        add_validation(
            pkg, "Sheet1", "B1:B10", "whole", operator="greaterThan", formula1="0"
        )
        add_validation(
            pkg, "Sheet1", "C1:C10", "decimal", operator="lessThan", formula1="100"
        )

        remove_validation(pkg, "Sheet1", "B1:B10")

        validations = list_validations(pkg, "Sheet1")
        assert len(validations) == 2
        refs = {v.ref for v in validations}
        assert refs == {"A1:A10", "C1:C10"}

    def test_remove_validation_cleans_up_container(self) -> None:
        """Removing last validation removes dataValidations element."""
        pkg = ExcelPackage.new()
        add_validation(pkg, "Sheet1", "A1", "list", formula1='"X,Y"')

        remove_validation(pkg, "Sheet1", "A1")

        sheet_xml = pkg.get_sheet_xml("Sheet1")
        assert sheet_xml.find(qn("x:dataValidations")) is None


class TestValidationInfo:
    """Tests for ValidationInfo model."""

    def test_validation_info_defaults(self) -> None:
        """ValidationInfo has correct defaults."""
        pkg = ExcelPackage.new()

        validation = add_validation(pkg, "Sheet1", "A1", "list", formula1='"A,B"')

        assert validation.allow_blank is True
        assert validation.show_dropdown is True
        assert validation.operator is None
        assert validation.formula2 is None
        assert validation.error_title is None
        assert validation.error_message is None
        assert validation.prompt_title is None
        assert validation.prompt is None
