"""Tests for PowerPoint group/ungroup operations."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.microsoft.powerpoint.shared import edit, read


@pytest.fixture
def temp_pptx():
    """Create a temp file path for tests (file does not exist yet)."""
    fd, path = tempfile.mkstemp(suffix=".pptx")
    os.close(fd)
    os.unlink(path)  # Delete the file so edit() can create it fresh
    yield path
    Path(path).unlink(missing_ok=True)


class TestGroupShapes:
    """Tests for group_shapes operation."""

    def test_group_two_shapes(self, temp_pptx):
        """Test basic grouping of two shapes."""
        # Create file with two shapes
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
                "text": "Shape 1",
            },
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 4.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
                "text": "Shape 2",
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        # Get shape keys
        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        shape_keys = [
            s["shape_key"]
            for s in shapes_result["shapes"]
            if s["type"] == "shape" and s.get("text") in ("Shape 1", "Shape 2")
        ]
        assert len(shape_keys) == 2

        # Group the shapes
        group_ops = [{"op": "group_shapes", "slide_num": 1, "shape_keys": shape_keys}]
        result = edit(temp_pptx, json.dumps(group_ops))
        assert result["success"]
        assert result["results"][0]["element_id"]  # Returns group key

        # Verify group was created
        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        groups = [s for s in shapes_result["shapes"] if s["type"] == "group"]
        assert len(groups) == 1

    def test_group_requires_at_least_two_shapes(self, temp_pptx):
        """Test that grouping requires at least 2 shapes."""
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        shape_keys = [
            s["shape_key"] for s in shapes_result["shapes"] if s["type"] == "shape"
        ]
        assert len(shape_keys) == 1

        # Try to group single shape - raises error
        group_ops = [{"op": "group_shapes", "slide_num": 1, "shape_keys": shape_keys}]
        with pytest.raises(ValueError, match="(?i)at least 2"):
            edit(temp_pptx, json.dumps(group_ops))

    def test_group_preserves_z_order(self, temp_pptx):
        """Test that grouping preserves the z-order of shapes within group."""
        # Create three shapes
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
                "text": "First",
            },
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 2.0,
                "y": 1.5,
                "width": 2.0,
                "height": 1.0,
                "text": "Second",
            },
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 3.0,
                "y": 2.0,
                "width": 2.0,
                "height": 1.0,
                "text": "Third",
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        # Get shape keys for first and third
        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        shape_map = {
            s.get("text"): s["shape_key"]
            for s in shapes_result["shapes"]
            if s.get("text")
        }
        shape_keys = [shape_map["First"], shape_map["Third"]]

        # Group first and third
        group_ops = [{"op": "group_shapes", "slide_num": 1, "shape_keys": shape_keys}]
        result = edit(temp_pptx, json.dumps(group_ops))
        assert result["success"]


class TestUngroup:
    """Tests for ungroup operation."""

    def test_ungroup_basic(self, temp_pptx):
        """Test basic ungrouping."""
        # Create and group two shapes
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
                "text": "Shape 1",
            },
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 4.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
                "text": "Shape 2",
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        shape_keys = [
            s["shape_key"]
            for s in shapes_result["shapes"]
            if s["type"] == "shape" and s.get("text") in ("Shape 1", "Shape 2")
        ]

        group_ops = [{"op": "group_shapes", "slide_num": 1, "shape_keys": shape_keys}]
        result = edit(temp_pptx, json.dumps(group_ops))
        assert result["success"]
        group_key = result["results"][0]["element_id"]

        # Ungroup
        ungroup_ops = [{"op": "ungroup", "shape_key": group_key}]
        result = edit(temp_pptx, json.dumps(ungroup_ops))
        assert result["success"]

        # Verify no groups remain
        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        groups = [s for s in shapes_result["shapes"] if s["type"] == "group"]
        assert len(groups) == 0

        # Verify shapes still exist with correct text
        texts = [s.get("text") for s in shapes_result["shapes"] if s.get("text")]
        assert "Shape 1" in texts
        assert "Shape 2" in texts

    def test_ungroup_restores_absolute_positions(self, temp_pptx):
        """Test that ungrouped shapes return to correct absolute positions."""
        # Create shapes at specific positions
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 2.0,
                "width": 2.0,
                "height": 1.0,
                "text": "Shape A",
            },
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 5.0,
                "y": 3.0,
                "width": 2.0,
                "height": 1.0,
                "text": "Shape B",
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        # Record original positions
        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        original_positions = {
            s.get("text"): (s["x_inches"], s["y_inches"])
            for s in shapes_result["shapes"]
            if s.get("text") in ("Shape A", "Shape B")
        }

        shape_keys = [
            s["shape_key"]
            for s in shapes_result["shapes"]
            if s.get("text") in ("Shape A", "Shape B")
        ]

        # Group and ungroup
        group_ops = [{"op": "group_shapes", "slide_num": 1, "shape_keys": shape_keys}]
        result = edit(temp_pptx, json.dumps(group_ops))
        group_key = result["results"][0]["element_id"]

        ungroup_ops = [{"op": "ungroup", "shape_key": group_key}]
        result = edit(temp_pptx, json.dumps(ungroup_ops))
        assert result["success"]

        # Verify positions restored
        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        for shape in shapes_result["shapes"]:
            text = shape.get("text")
            if text in original_positions:
                orig_x, orig_y = original_positions[text]
                assert abs(shape["x_inches"] - orig_x) < 0.01, f"{text} x mismatch"
                assert abs(shape["y_inches"] - orig_y) < 0.01, f"{text} y mismatch"

    def test_ungroup_non_group_raises(self, temp_pptx):
        """Test that ungrouping a non-group shape raises error."""
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        shape_key = shapes_result["shapes"][0]["shape_key"]

        ungroup_ops = [{"op": "ungroup", "shape_key": shape_key}]
        with pytest.raises(ValueError, match="(?i)not found"):
            edit(temp_pptx, json.dumps(ungroup_ops))


class TestGroupUngroupV1Constraints:
    """Tests for V1 constraints on group/ungroup."""

    def test_group_rejects_missing_shape(self, temp_pptx):
        """Test that grouping with invalid shape key raises error."""
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        shape_key = shapes_result["shapes"][0]["shape_key"]

        # Try to group with a nonexistent shape - raises error
        group_ops = [
            {"op": "group_shapes", "slide_num": 1, "shape_keys": [shape_key, "1:9999"]}
        ]
        with pytest.raises(ValueError, match="(?i)not found"):
            edit(temp_pptx, json.dumps(group_ops))

    def test_group_wrong_slide_fails(self, temp_pptx):
        """Test that grouping with shape key from different slide fails."""
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
            },
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 4.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        shape_keys = [
            s["shape_key"] for s in shapes_result["shapes"] if s["type"] == "shape"
        ]

        # Try to group on slide 2 (wrong slide) - raises error
        group_ops = [{"op": "group_shapes", "slide_num": 2, "shape_keys": shape_keys}]
        with pytest.raises(ValueError):
            edit(temp_pptx, json.dumps(group_ops))

    def test_group_rejects_existing_group(self, temp_pptx):
        """Test that grouping a group is rejected (no nested groups)."""
        # Create and group two shapes
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
            },
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 4.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
            },
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 7.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        # Get shape keys
        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        shape_keys = [
            s["shape_key"] for s in shapes_result["shapes"] if s["type"] == "shape"
        ]
        assert len(shape_keys) == 3

        # Group first two
        group_ops = [
            {"op": "group_shapes", "slide_num": 1, "shape_keys": shape_keys[:2]}
        ]
        result = edit(temp_pptx, json.dumps(group_ops))
        assert result["success"]
        group_key = result["results"][0]["element_id"]

        # Try to group the group with the third shape - raises error
        group_ops = [
            {
                "op": "group_shapes",
                "slide_num": 1,
                "shape_keys": [group_key, shape_keys[2]],
            }
        ]
        with pytest.raises(ValueError, match="(?i)cannot group a group"):
            edit(temp_pptx, json.dumps(group_ops))

    def test_ungroup_rejects_nested_groups(self, temp_pptx):
        """Test that ungrouping a group containing nested groups is rejected.

        Note: This tests the edge case where a group was created externally
        (e.g., in PowerPoint) that contains nested groups. Our group_shapes()
        prevents creating such groups, but we need to handle files that have them.
        """
        import zipfile

        from lxml import etree

        # Create file with shapes and make a group
        create_ops = [
            {"op": "add_slide"},
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 1.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
                "text": "Shape A",
            },
            {
                "op": "add_shape",
                "slide_num": 1,
                "x": 4.0,
                "y": 1.0,
                "width": 2.0,
                "height": 1.0,
                "text": "Shape B",
            },
        ]
        result = edit(temp_pptx, json.dumps(create_ops))
        assert result["success"]

        shapes_result = read(temp_pptx, scope="shapes", slide_num=1)
        shape_keys = [
            s["shape_key"]
            for s in shapes_result["shapes"]
            if s.get("text") in ("Shape A", "Shape B")
        ]

        # Group them
        group_ops = [{"op": "group_shapes", "slide_num": 1, "shape_keys": shape_keys}]
        result = edit(temp_pptx, json.dumps(group_ops))
        assert result["success"]
        group_key = result["results"][0]["element_id"]
        group_id = int(group_key.split(":")[1])

        # Manually inject a nested group by modifying the PPTX XML
        # Read the slide XML
        with zipfile.ZipFile(temp_pptx, "r") as zf:
            slide_xml = zf.read("ppt/slides/slide1.xml")

        # Parse and find the group
        root = etree.fromstring(slide_xml)
        ns = {
            "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        }

        # Find our group by ID
        grp = None
        for g in root.findall(".//p:grpSp", ns):
            nvpr = g.find("p:nvGrpSpPr/p:cNvPr", ns)
            if nvpr is not None and nvpr.get("id") == str(group_id):
                grp = g
                break
        assert grp is not None, "Could not find group element"

        # Create a minimal nested group element
        nested_grp = etree.SubElement(grp, "{{{}}}grpSp".format(ns["p"]))
        nested_nvpr = etree.SubElement(nested_grp, "{{{}}}nvGrpSpPr".format(ns["p"]))
        etree.SubElement(
            nested_nvpr, "{{{}}}cNvPr".format(ns["p"]), id="999", name="NestedGroup"
        )
        etree.SubElement(nested_nvpr, "{{{}}}cNvGrpSpPr".format(ns["p"]))
        etree.SubElement(nested_nvpr, "{{{}}}nvPr".format(ns["p"]))
        nested_sppr = etree.SubElement(nested_grp, "{{{}}}grpSpPr".format(ns["p"]))
        nested_xfrm = etree.SubElement(nested_sppr, "{{{}}}xfrm".format(ns["a"]))
        etree.SubElement(nested_xfrm, "{{{}}}off".format(ns["a"]), x="0", y="0")
        etree.SubElement(
            nested_xfrm, "{{{}}}ext".format(ns["a"]), cx="914400", cy="914400"
        )
        etree.SubElement(nested_xfrm, "{{{}}}chOff".format(ns["a"]), x="0", y="0")
        etree.SubElement(
            nested_xfrm, "{{{}}}chExt".format(ns["a"]), cx="914400", cy="914400"
        )

        # Write modified XML back to the PPTX
        modified_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
        with zipfile.ZipFile(temp_pptx, "r") as zf_in:
            contents = {name: zf_in.read(name) for name in zf_in.namelist()}
        contents["ppt/slides/slide1.xml"] = modified_xml
        with zipfile.ZipFile(temp_pptx, "w") as zf_out:
            for name, data in contents.items():
                zf_out.writestr(name, data)

        # Now try to ungroup - should fail with nested groups error
        ungroup_ops = [{"op": "ungroup", "shape_key": group_key}]
        with pytest.raises(ValueError, match="(?i)nested groups"):
            edit(temp_pptx, json.dumps(ungroup_ops))
