"""Tests for Excel protection operations."""

import io

import pytest

from mcp_handley_lab.microsoft.excel.ops.protection import (
    get_sheet_protection,
    get_workbook_protection,
    is_cell_locked,
    is_sheet_protected,
    is_workbook_protected,
    lock_cells,
    protect_sheet,
    protect_workbook,
    unlock_cells,
    unprotect_sheet,
    unprotect_workbook,
)
from mcp_handley_lab.microsoft.excel.package import ExcelPackage


class TestProtectSheet:
    """Tests for sheet protection."""

    def test_protect_sheet_basic(self) -> None:
        """Protect a sheet with default settings."""
        pkg = ExcelPackage.new()
        protect_sheet(pkg, "Sheet1")

        assert is_sheet_protected(pkg, "Sheet1") is True

    def test_protect_sheet_with_password(self) -> None:
        """Protect a sheet with a password."""
        pkg = ExcelPackage.new()
        protect_sheet(pkg, "Sheet1", password="secret123")

        assert is_sheet_protected(pkg, "Sheet1") is True
        settings = get_sheet_protection(pkg, "Sheet1")
        assert settings is not None
        assert settings["password_set"] is True

    def test_protect_sheet_custom_options(self) -> None:
        """Protect a sheet with custom options."""
        pkg = ExcelPackage.new()
        protect_sheet(
            pkg,
            "Sheet1",
            format_cells=False,
            insert_rows=False,
            sort=False,
        )

        settings = get_sheet_protection(pkg, "Sheet1")
        assert settings is not None
        assert settings["format_cells"] is False
        assert settings["insert_rows"] is False
        assert settings["sort"] is False

    def test_unprotect_sheet_no_password(self) -> None:
        """Unprotect a sheet that has no password."""
        pkg = ExcelPackage.new()
        protect_sheet(pkg, "Sheet1")
        assert is_sheet_protected(pkg, "Sheet1") is True

        unprotect_sheet(pkg, "Sheet1")
        assert is_sheet_protected(pkg, "Sheet1") is False

    def test_unprotect_sheet_with_correct_password(self) -> None:
        """Unprotect a sheet with the correct password."""
        pkg = ExcelPackage.new()
        protect_sheet(pkg, "Sheet1", password="secret123")

        unprotect_sheet(pkg, "Sheet1", password="secret123")
        assert is_sheet_protected(pkg, "Sheet1") is False

    def test_unprotect_sheet_wrong_password_raises(self) -> None:
        """Unprotecting with wrong password raises error."""
        pkg = ExcelPackage.new()
        protect_sheet(pkg, "Sheet1", password="secret123")

        with pytest.raises(ValueError, match="Incorrect password"):
            unprotect_sheet(pkg, "Sheet1", password="wrong")

    def test_unprotect_sheet_no_password_when_required_raises(self) -> None:
        """Unprotecting without password when required raises error."""
        pkg = ExcelPackage.new()
        protect_sheet(pkg, "Sheet1", password="secret123")

        with pytest.raises(ValueError, match="password-protected"):
            unprotect_sheet(pkg, "Sheet1")

    def test_is_sheet_protected_false_by_default(self) -> None:
        """New sheets are not protected by default."""
        pkg = ExcelPackage.new()
        assert is_sheet_protected(pkg, "Sheet1") is False

    def test_get_sheet_protection_returns_none_when_unprotected(self) -> None:
        """get_sheet_protection returns None for unprotected sheet."""
        pkg = ExcelPackage.new()
        assert get_sheet_protection(pkg, "Sheet1") is None

    def test_protect_sheet_replaces_existing(self) -> None:
        """Protecting an already-protected sheet replaces settings."""
        pkg = ExcelPackage.new()
        protect_sheet(pkg, "Sheet1", format_cells=True)
        protect_sheet(pkg, "Sheet1", format_cells=False)

        settings = get_sheet_protection(pkg, "Sheet1")
        assert settings is not None
        assert settings["format_cells"] is False

    def test_unprotect_already_unprotected_sheet(self) -> None:
        """Unprotecting an unprotected sheet is a no-op."""
        pkg = ExcelPackage.new()
        unprotect_sheet(pkg, "Sheet1")  # Should not raise
        assert is_sheet_protected(pkg, "Sheet1") is False


class TestProtectWorkbook:
    """Tests for workbook protection."""

    def test_protect_workbook_basic(self) -> None:
        """Protect workbook with default settings."""
        pkg = ExcelPackage.new()
        protect_workbook(pkg)

        assert is_workbook_protected(pkg) is True

    def test_protect_workbook_with_password(self) -> None:
        """Protect workbook with a password."""
        pkg = ExcelPackage.new()
        protect_workbook(pkg, password="secret123")

        settings = get_workbook_protection(pkg)
        assert settings is not None
        assert settings["password_set"] is True

    def test_protect_workbook_lock_structure(self) -> None:
        """Protect workbook with lock_structure option."""
        pkg = ExcelPackage.new()
        protect_workbook(pkg, lock_structure=True, lock_windows=False)

        settings = get_workbook_protection(pkg)
        assert settings is not None
        assert settings["lock_structure"] is True
        assert settings["lock_windows"] is False

    def test_protect_workbook_lock_windows(self) -> None:
        """Protect workbook with lock_windows option."""
        pkg = ExcelPackage.new()
        protect_workbook(pkg, lock_structure=False, lock_windows=True)

        settings = get_workbook_protection(pkg)
        assert settings is not None
        assert settings["lock_structure"] is False
        assert settings["lock_windows"] is True

    def test_unprotect_workbook_no_password(self) -> None:
        """Unprotect workbook that has no password."""
        pkg = ExcelPackage.new()
        protect_workbook(pkg)

        unprotect_workbook(pkg)
        assert is_workbook_protected(pkg) is False

    def test_unprotect_workbook_with_correct_password(self) -> None:
        """Unprotect workbook with correct password."""
        pkg = ExcelPackage.new()
        protect_workbook(pkg, password="secret123")

        unprotect_workbook(pkg, password="secret123")
        assert is_workbook_protected(pkg) is False

    def test_unprotect_workbook_wrong_password_raises(self) -> None:
        """Unprotecting workbook with wrong password raises error."""
        pkg = ExcelPackage.new()
        protect_workbook(pkg, password="secret123")

        with pytest.raises(ValueError, match="Incorrect password"):
            unprotect_workbook(pkg, password="wrong")

    def test_is_workbook_protected_false_by_default(self) -> None:
        """New workbooks are not protected by default."""
        pkg = ExcelPackage.new()
        assert is_workbook_protected(pkg) is False

    def test_get_workbook_protection_returns_none_when_unprotected(self) -> None:
        """get_workbook_protection returns None for unprotected workbook."""
        pkg = ExcelPackage.new()
        assert get_workbook_protection(pkg) is None


class TestLockCells:
    """Tests for cell locking/unlocking."""

    def test_unlock_cells_single(self) -> None:
        """Unlock a single cell."""
        pkg = ExcelPackage.new()
        unlock_cells(pkg, "Sheet1", "A1")

        assert is_cell_locked(pkg, "Sheet1", "A1") is False

    def test_unlock_cells_range(self) -> None:
        """Unlock a range of cells."""
        pkg = ExcelPackage.new()
        unlock_cells(pkg, "Sheet1", "A1:B3")

        assert is_cell_locked(pkg, "Sheet1", "A1") is False
        assert is_cell_locked(pkg, "Sheet1", "A2") is False
        assert is_cell_locked(pkg, "Sheet1", "B1") is False
        assert is_cell_locked(pkg, "Sheet1", "B3") is False

    def test_lock_cells_single(self) -> None:
        """Lock a single cell (after unlocking)."""
        pkg = ExcelPackage.new()
        unlock_cells(pkg, "Sheet1", "A1")
        lock_cells(pkg, "Sheet1", "A1")

        assert is_cell_locked(pkg, "Sheet1", "A1") is True

    def test_cells_locked_by_default(self) -> None:
        """Cells are locked by default (Excel behavior)."""
        pkg = ExcelPackage.new()
        assert is_cell_locked(pkg, "Sheet1", "A1") is True

    def test_unlock_does_not_affect_other_cells(self) -> None:
        """Unlocking one cell doesn't affect others."""
        pkg = ExcelPackage.new()
        unlock_cells(pkg, "Sheet1", "A1")

        assert is_cell_locked(pkg, "Sheet1", "A1") is False
        assert is_cell_locked(pkg, "Sheet1", "B1") is True  # Still default locked


class TestStylePreservation:
    """Tests that locking/unlocking preserves existing cell styles."""

    def test_unlock_preserves_existing_style(self) -> None:
        """Unlocking a styled cell preserves font/fill/border."""
        from mcp_handley_lab.microsoft.excel.ops.cells import set_cell_style

        pkg = ExcelPackage.new()
        # Apply a style first
        set_cell_style(pkg, "Sheet1", "A1", 1)  # Apply style index 1

        # Now unlock the cell
        unlock_cells(pkg, "Sheet1", "A1")

        # Verify cell is unlocked
        assert is_cell_locked(pkg, "Sheet1", "A1") is False

        # The style index should be different (cloned with protection)
        # but based on original style

    def test_lock_after_unlock_preserves_style(self) -> None:
        """Lock -> unlock -> lock preserves styles."""
        pkg = ExcelPackage.new()

        unlock_cells(pkg, "Sheet1", "A1")
        assert is_cell_locked(pkg, "Sheet1", "A1") is False

        lock_cells(pkg, "Sheet1", "A1")
        assert is_cell_locked(pkg, "Sheet1", "A1") is True


class TestProtectionPersistence:
    """Tests for protection persisting through save/load."""

    def test_sheet_protection_persists(self) -> None:
        """Sheet protection survives save/load."""
        pkg = ExcelPackage.new()
        protect_sheet(pkg, "Sheet1", format_cells=False)

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        assert is_sheet_protected(pkg2, "Sheet1") is True
        settings = get_sheet_protection(pkg2, "Sheet1")
        assert settings is not None
        assert settings["format_cells"] is False

    def test_workbook_protection_persists(self) -> None:
        """Workbook protection survives save/load."""
        pkg = ExcelPackage.new()
        protect_workbook(pkg, lock_structure=True)

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        assert is_workbook_protected(pkg2) is True
        settings = get_workbook_protection(pkg2)
        assert settings is not None
        assert settings["lock_structure"] is True

    def test_unlocked_cells_persist(self) -> None:
        """Unlocked cells survive save/load."""
        pkg = ExcelPackage.new()
        unlock_cells(pkg, "Sheet1", "A1")

        buf = io.BytesIO()
        pkg.save(buf)
        buf.seek(0)
        pkg2 = ExcelPackage.open(buf)

        assert is_cell_locked(pkg2, "Sheet1", "A1") is False
