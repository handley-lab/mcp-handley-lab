"""Data validation operations for Excel.

Data validation allows adding dropdown lists, input restrictions, and error alerts to cells.
"""

from __future__ import annotations

import hashlib

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.models import ValidationInfo
from mcp_handley_lab.microsoft.excel.ops.core import (
    get_sheet_path as _get_sheet_path,
)
from mcp_handley_lab.microsoft.excel.ops.core import (
    insert_sheet_element,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


def _make_validation_id(sheet_name: str, ref: str) -> str:
    """Generate content-addressed ID for a validation rule."""
    content = f"{sheet_name}:{ref}"
    hash_val = hashlib.sha1(content.encode()).hexdigest()[:8]
    safe_sheet = sheet_name.replace(" ", "_")
    safe_ref = ref.replace(":", "")
    return f"validation_{safe_sheet}_{safe_ref}_{hash_val}"


def list_validations(pkg: ExcelPackage, sheet_name: str) -> list[ValidationInfo]:
    """List all data validation rules on a sheet.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.

    Returns: List of ValidationInfo for each validation rule.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    data_validations = sheet_xml.find(qn("x:dataValidations"))
    if data_validations is None:
        return []

    result = []
    for dv in data_validations.findall(qn("x:dataValidation")):
        ref = dv.get("sqref", "")
        val_type = dv.get("type", "")

        # Parse formulas
        formula1 = None
        formula1_el = dv.find(qn("x:formula1"))
        if formula1_el is not None and formula1_el.text:
            formula1 = formula1_el.text

        formula2 = None
        formula2_el = dv.find(qn("x:formula2"))
        if formula2_el is not None and formula2_el.text:
            formula2 = formula2_el.text

        # Parse boolean attributes
        allow_blank = dv.get("allowBlank", "1") == "1"
        show_dropdown = dv.get("showDropDown") != "1"  # Inverted - 1 means HIDE

        result.append(
            ValidationInfo(
                id=_make_validation_id(sheet_name, ref),
                ref=ref,
                type=val_type,
                operator=dv.get("operator"),
                formula1=formula1,
                formula2=formula2,
                allow_blank=allow_blank,
                show_dropdown=show_dropdown,
                error_title=dv.get("errorTitle"),
                error_message=dv.get("error"),
                prompt_title=dv.get("promptTitle"),
                prompt=dv.get("prompt"),
            )
        )

    return result


def add_validation(
    pkg: ExcelPackage,
    sheet_name: str,
    ref: str,
    val_type: str,
    formula1: str | None = None,
    formula2: str | None = None,
    operator: str | None = None,
    allow_blank: bool = True,
    show_dropdown: bool = True,
    error_title: str | None = None,
    error_message: str | None = None,
    prompt_title: str | None = None,
    prompt: str | None = None,
) -> ValidationInfo:
    """Add a data validation rule to cells.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        ref: Range reference (e.g., "A1:A10").
        val_type: Validation type (list, whole, decimal, date, time, textLength, custom).
        formula1: First constraint value/formula.
            For 'list': comma-separated values like '"Option1,Option2,Option3"'
            For numeric: value or cell reference
        formula2: Second constraint (for between/notBetween operators).
        operator: Comparison operator (between, notBetween, equal, notEqual,
            greaterThan, lessThan, greaterThanOrEqual, lessThanOrEqual).
        allow_blank: Allow blank cells (default True).
        show_dropdown: Show dropdown arrow for list type (default True).
        error_title: Title for error alert dialog.
        error_message: Message for error alert dialog.
        prompt_title: Title for input prompt.
        prompt: Message for input prompt.

    Returns: ValidationInfo for the created rule.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)

    # Find or create dataValidations element
    data_validations = sheet_xml.find(qn("x:dataValidations"))
    if data_validations is None:
        # Create dataValidations element at correct OOXML position
        data_validations = etree.Element(qn("x:dataValidations"))
        insert_sheet_element(sheet_xml, "dataValidations", data_validations)

    # Create the dataValidation element
    dv = etree.SubElement(data_validations, qn("x:dataValidation"))
    dv.set("sqref", ref)
    dv.set("type", val_type)

    if operator:
        dv.set("operator", operator)

    if allow_blank:
        dv.set("allowBlank", "1")

    # Note: showDropDown="1" means HIDE the dropdown (inverted logic)
    if not show_dropdown:
        dv.set("showDropDown", "1")

    if error_title:
        dv.set("errorTitle", error_title)
        dv.set("showErrorMessage", "1")

    if error_message:
        dv.set("error", error_message)
        dv.set("showErrorMessage", "1")

    if prompt_title:
        dv.set("promptTitle", prompt_title)
        dv.set("showInputMessage", "1")

    if prompt:
        dv.set("prompt", prompt)
        dv.set("showInputMessage", "1")

    # Add formula elements
    if formula1 is not None:
        formula1_el = etree.SubElement(dv, qn("x:formula1"))
        formula1_el.text = formula1

    if formula2 is not None:
        formula2_el = etree.SubElement(dv, qn("x:formula2"))
        formula2_el.text = formula2

    # Update count attribute
    count = len(data_validations.findall(qn("x:dataValidation")))
    data_validations.set("count", str(count))

    pkg.mark_xml_dirty(_get_sheet_path(pkg, sheet_name))

    return ValidationInfo(
        id=_make_validation_id(sheet_name, ref),
        ref=ref,
        type=val_type,
        operator=operator,
        formula1=formula1,
        formula2=formula2,
        allow_blank=allow_blank,
        show_dropdown=show_dropdown,
        error_title=error_title,
        error_message=error_message,
        prompt_title=prompt_title,
        prompt=prompt,
    )


def remove_validation(pkg: ExcelPackage, sheet_name: str, ref: str) -> None:
    """Remove a data validation rule.

    Args:
        pkg: Excel package.
        sheet_name: Target sheet name.
        ref: Range reference to remove validation from.

    Raises: KeyError if validation not found.
    """
    sheet_xml = pkg.get_sheet_xml(sheet_name)
    data_validations = sheet_xml.find(qn("x:dataValidations"))
    if data_validations is None:
        raise KeyError(f"Validation not found: {ref}")

    # Find matching validation
    for dv in data_validations.findall(qn("x:dataValidation")):
        if dv.get("sqref") == ref:
            data_validations.remove(dv)

            # Update count or remove empty container
            remaining = len(data_validations.findall(qn("x:dataValidation")))
            if remaining == 0:
                sheet_xml.remove(data_validations)
            else:
                data_validations.set("count", str(remaining))

            pkg.mark_xml_dirty(_get_sheet_path(pkg, sheet_name))
            return

    raise KeyError(f"Validation not found: {ref}")
