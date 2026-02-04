"""Tests for Excel document properties."""

import json

import pytest

from mcp_handley_lab.microsoft.excel.package import ExcelPackage
from mcp_handley_lab.microsoft.excel.shared import edit, read


@pytest.fixture
def workbook(tmp_path):
    """Create a temporary Excel workbook."""
    file_path = tmp_path / "test.xlsx"
    pkg = ExcelPackage.new()
    pkg.save(str(file_path))
    return str(file_path)


class TestReadProperties:
    """Tests for reading document properties."""

    def test_read_properties_scope(self, workbook):
        """Test reading properties scope."""
        result = read(workbook, scope="properties")
        assert result["scope"] == "properties"
        assert "properties" in result

    def test_read_properties_has_core_fields(self, workbook):
        """Test properties contain core fields."""
        result = read(workbook, scope="properties")
        props = result["properties"]
        assert "title" in props
        assert "author" in props
        assert "subject" in props
        assert "keywords" in props
        assert "category" in props
        assert "comments" in props
        assert "created" in props
        assert "modified" in props
        assert "revision" in props
        assert "last_modified_by" in props

    def test_read_properties_custom_properties_empty(self, workbook):
        """Test custom properties starts empty."""
        result = read(workbook, scope="properties")
        props = result["properties"]
        assert "custom_properties" in props
        assert props["custom_properties"] == []


class TestSetProperty:
    """Tests for setting core properties."""

    def test_set_title(self, workbook):
        """Test setting title."""
        result = edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_property",
                        "property_name": "title",
                        "property_value": "Test Workbook",
                    }
                ]
            ),
        )
        assert result["success"] is True

        # Verify
        props = read(workbook, scope="properties")["properties"]
        assert props["title"] == "Test Workbook"

    def test_set_author(self, workbook):
        """Test setting author."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_property",
                        "property_name": "author",
                        "property_value": "Test Author",
                    }
                ]
            ),
        )
        props = read(workbook, scope="properties")["properties"]
        assert props["author"] == "Test Author"

    def test_set_subject(self, workbook):
        """Test setting subject."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_property",
                        "property_name": "subject",
                        "property_value": "Test Subject",
                    }
                ]
            ),
        )
        props = read(workbook, scope="properties")["properties"]
        assert props["subject"] == "Test Subject"

    def test_set_keywords(self, workbook):
        """Test setting keywords."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_property",
                        "property_name": "keywords",
                        "property_value": "excel, test, mcp",
                    }
                ]
            ),
        )
        props = read(workbook, scope="properties")["properties"]
        assert props["keywords"] == "excel, test, mcp"

    def test_set_multiple_properties(self, workbook):
        """Test setting multiple properties sequentially."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_property",
                        "property_name": "title",
                        "property_value": "My Title",
                    }
                ]
            ),
        )
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_property",
                        "property_name": "author",
                        "property_value": "My Author",
                    }
                ]
            ),
        )
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_property",
                        "property_name": "subject",
                        "property_value": "My Subject",
                    }
                ]
            ),
        )

        props = read(workbook, scope="properties")["properties"]
        assert props["title"] == "My Title"
        assert props["author"] == "My Author"
        assert props["subject"] == "My Subject"


class TestSetCustomProperty:
    """Tests for setting custom properties."""

    def test_set_custom_property_string(self, workbook):
        """Test setting a string custom property."""
        result = edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Department",
                        "property_value": "Engineering",
                        "property_type": "string",
                    }
                ]
            ),
        )
        assert result["success"] is True

        # Verify
        props = read(workbook, scope="properties")["properties"]
        custom = props["custom_properties"]
        assert len(custom) == 1
        assert custom[0]["name"] == "Department"
        assert custom[0]["value"] == "Engineering"
        assert custom[0]["type"] == "string"

    def test_set_custom_property_int(self, workbook):
        """Test setting an integer custom property."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Version",
                        "property_value": "42",
                        "property_type": "int",
                    }
                ]
            ),
        )

        props = read(workbook, scope="properties")["properties"]
        custom = props["custom_properties"]
        assert len(custom) == 1
        assert custom[0]["name"] == "Version"
        assert custom[0]["value"] == "42"
        assert custom[0]["type"] == "int"

    def test_set_custom_property_bool(self, workbook):
        """Test setting a boolean custom property."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Reviewed",
                        "property_value": "true",
                        "property_type": "bool",
                    }
                ]
            ),
        )

        props = read(workbook, scope="properties")["properties"]
        custom = props["custom_properties"]
        assert len(custom) == 1
        assert custom[0]["name"] == "Reviewed"
        assert custom[0]["value"] == "True"
        assert custom[0]["type"] == "bool"

    def test_set_custom_property_float(self, workbook):
        """Test setting a float custom property."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Score",
                        "property_value": "3.14159",
                        "property_type": "float",
                    }
                ]
            ),
        )

        props = read(workbook, scope="properties")["properties"]
        custom = props["custom_properties"]
        assert len(custom) == 1
        assert custom[0]["name"] == "Score"
        assert custom[0]["value"] == "3.14159"
        assert custom[0]["type"] == "float"

    def test_set_multiple_custom_properties(self, workbook):
        """Test setting multiple custom properties."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Prop1",
                        "property_value": "Value1",
                    }
                ]
            ),
        )
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Prop2",
                        "property_value": "Value2",
                    }
                ]
            ),
        )
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Prop3",
                        "property_value": "Value3",
                    }
                ]
            ),
        )

        props = read(workbook, scope="properties")["properties"]
        custom = props["custom_properties"]
        assert len(custom) == 3
        names = [p["name"] for p in custom]
        assert "Prop1" in names
        assert "Prop2" in names
        assert "Prop3" in names

    def test_update_existing_custom_property(self, workbook):
        """Test updating an existing custom property."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Status",
                        "property_value": "Draft",
                    }
                ]
            ),
        )
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Status",
                        "property_value": "Final",
                    }
                ]
            ),
        )

        props = read(workbook, scope="properties")["properties"]
        custom = props["custom_properties"]
        assert len(custom) == 1
        assert custom[0]["name"] == "Status"
        assert custom[0]["value"] == "Final"

    def test_set_custom_property_datetime(self, workbook):
        """Test setting a datetime custom property."""

        # The common helper expects a timezone-aware datetime for filetime type
        # But our tool interface takes strings - the common helper handles conversion
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "ReviewDate",
                        "property_value": "2025-01-15T10:30:00Z",
                        "property_type": "datetime",
                    }
                ]
            ),
        )

        props = read(workbook, scope="properties")["properties"]
        custom = props["custom_properties"]
        assert len(custom) == 1
        assert custom[0]["name"] == "ReviewDate"
        assert custom[0]["type"] == "datetime"
        # Value is stored and returned as the string we passed
        assert "2025-01-15" in custom[0]["value"]


class TestDeleteCustomProperty:
    """Tests for deleting custom properties."""

    def test_delete_custom_property(self, workbook):
        """Test deleting a custom property."""
        # Create
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "ToDelete",
                        "property_value": "value",
                    }
                ]
            ),
        )

        # Delete
        result = edit(
            workbook,
            ops=json.dumps(
                [{"op": "delete_custom_property", "property_name": "ToDelete"}]
            ),
        )
        assert result["success"] is True

        # Verify gone
        props = read(workbook, scope="properties")["properties"]
        assert len(props["custom_properties"]) == 0

    def test_delete_custom_property_not_found(self, workbook):
        """Test deleting non-existent property raises error."""
        with pytest.raises(KeyError, match="not found"):
            edit(
                workbook,
                ops=json.dumps(
                    [{"op": "delete_custom_property", "property_name": "DoesNotExist"}]
                ),
            )

    def test_delete_preserves_other_properties(self, workbook):
        """Test deleting one property preserves others."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Keep1",
                        "property_value": "value1",
                    }
                ]
            ),
        )
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Delete",
                        "property_value": "value2",
                    }
                ]
            ),
        )
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Keep2",
                        "property_value": "value3",
                    }
                ]
            ),
        )

        edit(
            workbook,
            ops=json.dumps(
                [{"op": "delete_custom_property", "property_name": "Delete"}]
            ),
        )

        props = read(workbook, scope="properties")["properties"]
        custom = props["custom_properties"]
        assert len(custom) == 2
        names = [p["name"] for p in custom]
        assert "Keep1" in names
        assert "Keep2" in names
        assert "Delete" not in names


class TestPropertiesPersistence:
    """Tests for property persistence across save/load."""

    def test_core_properties_persist(self, workbook):
        """Test core properties persist after save/load."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_property",
                        "property_name": "title",
                        "property_value": "Persistent Title",
                    }
                ]
            ),
        )
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_property",
                        "property_name": "author",
                        "property_value": "Persistent Author",
                    }
                ]
            ),
        )

        # Re-read from disk
        props = read(workbook, scope="properties")["properties"]
        assert props["title"] == "Persistent Title"
        assert props["author"] == "Persistent Author"

    def test_custom_properties_persist(self, workbook):
        """Test custom properties persist after save/load."""
        edit(
            workbook,
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "Persistent",
                        "property_value": "Value",
                    }
                ]
            ),
        )

        # Re-read from disk
        props = read(workbook, scope="properties")["properties"]
        custom = props["custom_properties"]
        assert len(custom) == 1
        assert custom[0]["name"] == "Persistent"
        assert custom[0]["value"] == "Value"


class TestSetPropertyValidation:
    """Tests for set_property validation."""

    def test_invalid_property_name_raises_error(self, workbook):
        """Test that invalid property names raise ValueError."""
        with pytest.raises(ValueError, match="invalid_property"):
            edit(
                workbook,
                ops=json.dumps(
                    [
                        {
                            "op": "set_property",
                            "property_name": "invalid_property",
                            "property_value": "value",
                        }
                    ]
                ),
            )

    def test_valid_property_names_accepted(self, workbook):
        """Test that all documented property names are accepted."""
        valid_names = [
            "title",
            "author",
            "subject",
            "keywords",
            "category",
            "comments",
        ]
        for name in valid_names:
            result = edit(
                workbook,
                ops=json.dumps(
                    [
                        {
                            "op": "set_property",
                            "property_name": name,
                            "property_value": f"test_{name}",
                        }
                    ]
                ),
            )
            assert result["success"] is True


class TestMissingDocProps:
    """Tests for handling missing docProps files."""

    def test_set_custom_property_creates_custom_xml(self, tmp_path):
        """Test that custom.xml is created when missing."""
        import zipfile

        # Create workbook and remove custom.xml if present
        file_path = tmp_path / "test.xlsx"
        pkg = ExcelPackage.new()
        pkg.save(str(file_path))

        # Verify custom.xml doesn't exist initially (new workbooks don't have it)
        with zipfile.ZipFile(file_path, "r") as zf:
            assert "docProps/custom.xml" not in zf.namelist()

        # Set a custom property - should create custom.xml
        edit(
            str(file_path),
            ops=json.dumps(
                [
                    {
                        "op": "set_custom_property",
                        "property_name": "NewProp",
                        "property_value": "NewValue",
                    }
                ]
            ),
        )

        # Verify custom.xml now exists
        with zipfile.ZipFile(file_path, "r") as zf:
            assert "docProps/custom.xml" in zf.namelist()

        # Verify property is readable
        props = read(str(file_path), scope="properties")["properties"]
        assert len(props["custom_properties"]) == 1
        assert props["custom_properties"][0]["name"] == "NewProp"
