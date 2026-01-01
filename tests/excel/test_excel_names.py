"""Tests for Excel named range operations."""

import io

import pytest

from mcp_handley_lab.microsoft.excel.constants import qn
from mcp_handley_lab.microsoft.excel.ops.names import (
    create_name,
    delete_name,
    get_name,
    list_names,
    update_name,
)
from mcp_handley_lab.microsoft.excel.ops.sheets import add_sheet
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestListNames:
    """Tests for list_names."""

    def test_list_names_empty(self) -> None:
        """New workbook has no defined names."""
        pkg = ExcelPackage.new()

        names = list_names(pkg)

        assert names == []

    def test_list_names_after_create(self) -> None:
        """List names returns created names."""
        pkg = ExcelPackage.new()
        create_name(pkg, "MyRange", "'Sheet1'!$A$1:$A$10")

        names = list_names(pkg)

        assert len(names) == 1
        assert names[0].name == "MyRange"
        assert names[0].refers_to == "'Sheet1'!$A$1:$A$10"

    def test_list_names_multiple(self) -> None:
        """List multiple names."""
        pkg = ExcelPackage.new()
        create_name(pkg, "Range1", "'Sheet1'!$A$1")
        create_name(pkg, "Range2", "'Sheet1'!$B$1")
        create_name(pkg, "Range3", "'Sheet1'!$C$1")

        names = list_names(pkg)

        assert len(names) == 3
        name_set = {n.name for n in names}
        assert name_set == {"Range1", "Range2", "Range3"}


class TestGetName:
    """Tests for get_name."""

    def test_get_name_found(self) -> None:
        """Get existing name returns NameInfo."""
        pkg = ExcelPackage.new()
        create_name(pkg, "TaxRate", "=0.07")

        name = get_name(pkg, "TaxRate")

        assert name.name == "TaxRate"
        assert name.refers_to == "=0.07"
        assert name.scope is None

    def test_get_name_not_found(self) -> None:
        """Get non-existent name raises KeyError."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="Name not found"):
            get_name(pkg, "NonExistent")

    def test_get_name_with_scope(self) -> None:
        """Get name with local scope."""
        pkg = ExcelPackage.new()
        create_name(pkg, "LocalRange", "'Sheet1'!$A$1", scope="Sheet1")

        name = get_name(pkg, "LocalRange", scope="Sheet1")

        assert name.name == "LocalRange"
        assert name.scope == "Sheet1"

    def test_get_name_scope_mismatch(self) -> None:
        """Get name with wrong scope raises KeyError."""
        pkg = ExcelPackage.new()
        create_name(pkg, "LocalRange", "'Sheet1'!$A$1", scope="Sheet1")

        # Try to get as global - should fail
        with pytest.raises(KeyError, match="Name not found"):
            get_name(pkg, "LocalRange")  # No scope = global


class TestCreateName:
    """Tests for create_name."""

    def test_create_name_global(self) -> None:
        """Create global (workbook-scoped) name."""
        pkg = ExcelPackage.new()

        name = create_name(pkg, "GlobalRange", "'Sheet1'!$A$1:$B$10")

        assert name.name == "GlobalRange"
        assert name.refers_to == "'Sheet1'!$A$1:$B$10"
        assert name.scope is None
        assert name.id is not None

    def test_create_name_local(self) -> None:
        """Create local (sheet-scoped) name."""
        pkg = ExcelPackage.new()

        name = create_name(pkg, "LocalRange", "$A$1:$C$5", scope="Sheet1")

        assert name.name == "LocalRange"
        assert name.scope == "Sheet1"

        # Verify in XML
        workbook = pkg.workbook_xml
        defined_names = workbook.find(qn("x:definedNames"))
        dn = defined_names.find(qn("x:definedName"))
        assert dn.get("localSheetId") == "0"  # Sheet1 is index 0

    def test_create_name_with_comment(self) -> None:
        """Create name with comment."""
        pkg = ExcelPackage.new()

        name = create_name(
            pkg, "Documented", "'Sheet1'!$A$1", comment="This is a test range"
        )

        assert name.comment == "This is a test range"

        # Verify in XML
        workbook = pkg.workbook_xml
        defined_names = workbook.find(qn("x:definedNames"))
        dn = defined_names.find(qn("x:definedName"))
        assert dn.get("comment") == "This is a test range"

    def test_create_name_formula(self) -> None:
        """Create name with formula reference."""
        pkg = ExcelPackage.new()

        name = create_name(pkg, "TaxRate", "=0.0725")

        assert name.refers_to == "=0.0725"

    def test_create_name_same_name_different_scope(self) -> None:
        """Same name in different scopes is allowed."""
        pkg = ExcelPackage.new()
        add_sheet(pkg, "Sheet2")

        # Global and local with same name
        name1 = create_name(pkg, "MyRange", "'Sheet1'!$A$1")
        name2 = create_name(pkg, "MyRange", "'Sheet1'!$B$1", scope="Sheet1")

        assert name1.scope is None
        assert name2.scope == "Sheet1"

        names = list_names(pkg)
        assert len(names) == 2

    def test_create_name_persists(self) -> None:
        """Created name persists through save/load."""
        pkg = ExcelPackage.new()
        create_name(pkg, "Persistent", "'Sheet1'!$A$1:$Z$100", comment="Test comment")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        name = get_name(pkg2, "Persistent")
        assert name.refers_to == "'Sheet1'!$A$1:$Z$100"
        assert name.comment == "Test comment"


class TestUpdateName:
    """Tests for update_name."""

    def test_update_name_refers_to(self) -> None:
        """Update refers_to of a name."""
        pkg = ExcelPackage.new()
        create_name(pkg, "MyRange", "'Sheet1'!$A$1")

        updated = update_name(pkg, "MyRange", refers_to="'Sheet1'!$A$1:$A$100")

        assert updated.refers_to == "'Sheet1'!$A$1:$A$100"

        # Verify change persisted
        name = get_name(pkg, "MyRange")
        assert name.refers_to == "'Sheet1'!$A$1:$A$100"

    def test_update_name_comment(self) -> None:
        """Update comment of a name."""
        pkg = ExcelPackage.new()
        create_name(pkg, "MyRange", "'Sheet1'!$A$1", comment="Original")

        updated = update_name(pkg, "MyRange", comment="Updated comment")

        assert updated.comment == "Updated comment"

    def test_update_name_clear_comment(self) -> None:
        """Clear comment by setting to empty string."""
        pkg = ExcelPackage.new()
        create_name(pkg, "MyRange", "'Sheet1'!$A$1", comment="Has comment")

        updated = update_name(pkg, "MyRange", comment="")

        assert updated.comment is None

    def test_update_name_not_found(self) -> None:
        """Update non-existent name raises KeyError."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="Name not found"):
            update_name(pkg, "NonExistent", refers_to="'Sheet1'!$A$1")

    def test_update_name_with_scope(self) -> None:
        """Update local-scoped name."""
        pkg = ExcelPackage.new()
        create_name(pkg, "LocalRange", "$A$1", scope="Sheet1")

        updated = update_name(pkg, "LocalRange", refers_to="$B$1", scope="Sheet1")

        assert updated.refers_to == "$B$1"
        assert updated.scope == "Sheet1"


class TestDeleteName:
    """Tests for delete_name."""

    def test_delete_name(self) -> None:
        """Delete existing name."""
        pkg = ExcelPackage.new()
        create_name(pkg, "ToDelete", "'Sheet1'!$A$1")

        delete_name(pkg, "ToDelete")

        with pytest.raises(KeyError):
            get_name(pkg, "ToDelete")

    def test_delete_name_not_found(self) -> None:
        """Delete non-existent name raises KeyError."""
        pkg = ExcelPackage.new()

        with pytest.raises(KeyError, match="Name not found"):
            delete_name(pkg, "NonExistent")

    def test_delete_name_with_scope(self) -> None:
        """Delete local-scoped name."""
        pkg = ExcelPackage.new()
        create_name(pkg, "LocalRange", "$A$1", scope="Sheet1")

        delete_name(pkg, "LocalRange", scope="Sheet1")

        with pytest.raises(KeyError):
            get_name(pkg, "LocalRange", scope="Sheet1")

    def test_delete_name_removes_empty_container(self) -> None:
        """Deleting last name removes definedNames element."""
        pkg = ExcelPackage.new()
        create_name(pkg, "OnlyName", "'Sheet1'!$A$1")

        delete_name(pkg, "OnlyName")

        workbook = pkg.workbook_xml
        assert workbook.find(qn("x:definedNames")) is None

    def test_delete_name_preserves_others(self) -> None:
        """Deleting one name preserves others."""
        pkg = ExcelPackage.new()
        create_name(pkg, "Keep1", "'Sheet1'!$A$1")
        create_name(pkg, "Delete", "'Sheet1'!$B$1")
        create_name(pkg, "Keep2", "'Sheet1'!$C$1")

        delete_name(pkg, "Delete")

        names = list_names(pkg)
        assert len(names) == 2
        name_set = {n.name for n in names}
        assert name_set == {"Keep1", "Keep2"}


class TestNameInfo:
    """Tests for NameInfo model."""

    def test_name_info_has_id(self) -> None:
        """NameInfo has content-addressed ID."""
        pkg = ExcelPackage.new()

        name = create_name(pkg, "TestName", "'Sheet1'!$A$1")

        assert name.id is not None
        assert name.id.startswith("name_")

    def test_name_info_id_unique_by_scope(self) -> None:
        """Same name in different scopes has different IDs."""
        pkg = ExcelPackage.new()

        name1 = create_name(pkg, "MyRange", "'Sheet1'!$A$1")
        name2 = create_name(pkg, "MyRange", "'Sheet1'!$B$1", scope="Sheet1")

        assert name1.id != name2.id
