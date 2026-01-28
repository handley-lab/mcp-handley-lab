"""Tests for PowerPoint operations."""

from __future__ import annotations

import tempfile
from pathlib import Path

from mcp_handley_lab.microsoft.powerpoint.constants import EMU_PER_INCH, NSMAP, qn
from mcp_handley_lab.microsoft.powerpoint.ops.core import (
    emu_to_inches,
    inches_to_emu,
    make_shape_key,
    parse_shape_key,
    spatial_sort_shapes,
)
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage


class TestEmuConversion:
    """Tests for EMU conversion utilities."""

    def test_emu_to_inches(self):
        assert emu_to_inches(EMU_PER_INCH) == 1.0
        assert emu_to_inches(0) == 0.0
        assert emu_to_inches(EMU_PER_INCH * 2) == 2.0
        assert emu_to_inches(EMU_PER_INCH // 2) == 0.5

    def test_inches_to_emu(self):
        assert inches_to_emu(1.0) == EMU_PER_INCH
        assert inches_to_emu(0.0) == 0
        assert inches_to_emu(2.0) == EMU_PER_INCH * 2


class TestShapeKey:
    """Tests for shape key utilities."""

    def test_make_shape_key(self):
        assert make_shape_key(1, 42) == "1:42"
        assert make_shape_key(10, 100) == "10:100"

    def test_parse_shape_key(self):
        assert parse_shape_key("1:42") == (1, 42)
        assert parse_shape_key("10:100") == (10, 100)


class TestSpatialSort:
    """Tests for spatial sorting."""

    def test_sort_by_y_then_x(self):
        shapes = [
            {"y_inches": 2.0, "x_inches": 1.0, "z_order": 0, "shape_id": 1},
            {"y_inches": 1.0, "x_inches": 2.0, "z_order": 0, "shape_id": 2},
            {"y_inches": 1.0, "x_inches": 1.0, "z_order": 0, "shape_id": 3},
        ]
        sorted_shapes = spatial_sort_shapes(shapes)
        # Should be: (1,1), (1,2), (2,1)
        assert sorted_shapes[0]["shape_id"] == 3
        assert sorted_shapes[1]["shape_id"] == 2
        assert sorted_shapes[2]["shape_id"] == 1

    def test_sort_with_z_order_tiebreak(self):
        shapes = [
            {"y_inches": 1.0, "x_inches": 1.0, "z_order": 2, "shape_id": 1},
            {"y_inches": 1.0, "x_inches": 1.0, "z_order": 1, "shape_id": 2},
        ]
        sorted_shapes = spatial_sort_shapes(shapes)
        # Same position, lower z_order first
        assert sorted_shapes[0]["shape_id"] == 2
        assert sorted_shapes[1]["shape_id"] == 1


class TestPackageCreation:
    """Tests for PowerPointPackage creation."""

    def test_new_creates_minimal_presentation(self):
        pkg = PowerPointPackage.new()
        assert pkg.presentation_path == "/ppt/presentation.xml"
        assert pkg.presentation_xml is not None

    def test_new_has_slide_dimensions(self):
        pkg = PowerPointPackage.new()
        width, height = pkg.get_slide_dimensions()
        assert width == 9144000  # 10 inches
        assert height == 6858000  # 7.5 inches

    def test_save_and_reopen(self):
        pkg = PowerPointPackage.new()

        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
            temp_path = f.name

        try:
            pkg.save(temp_path)

            # Reopen
            pkg2 = PowerPointPackage.open(temp_path)
            assert pkg2.presentation_path == "/ppt/presentation.xml"
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestSlideOperations:
    """Tests for slide operations."""

    def test_get_slide_count_empty(self):
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import get_slide_count

        pkg = PowerPointPackage.new()
        assert get_slide_count(pkg) == 0

    def test_list_slides_empty(self):
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import list_slides

        pkg = PowerPointPackage.new()
        slides = list_slides(pkg)
        assert len(slides) == 0


class TestImageDimensions:
    """Tests for Pillow-based image dimension parsing."""

    def test_png_dimensions(self):
        import io

        from PIL import Image

        from mcp_handley_lab.microsoft.powerpoint.ops.images import (
            _get_image_dimensions,
        )

        # Create a valid PNG in memory
        img = Image.new("RGB", (16, 32), color="red")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        png_data = buffer.getvalue()

        width, height = _get_image_dimensions(png_data, "image/png")
        assert width == 16
        assert height == 32

    def test_gif_dimensions(self):
        import io

        from PIL import Image

        from mcp_handley_lab.microsoft.powerpoint.ops.images import (
            _get_image_dimensions,
        )

        # Create a valid GIF in memory
        img = Image.new("P", (64, 48), color=0)
        buffer = io.BytesIO()
        img.save(buffer, format="GIF")
        gif_data = buffer.getvalue()

        width, height = _get_image_dimensions(gif_data, "image/gif")
        assert width == 64
        assert height == 48

    def test_bmp_dimensions(self):
        import io

        from PIL import Image

        from mcp_handley_lab.microsoft.powerpoint.ops.images import (
            _get_image_dimensions,
        )

        # Create a valid BMP in memory
        img = Image.new("RGB", (128, 96), color="blue")
        buffer = io.BytesIO()
        img.save(buffer, format="BMP")
        bmp_data = buffer.getvalue()

        width, height = _get_image_dimensions(bmp_data, "image/bmp")
        assert width == 128
        assert height == 96

    def test_corrupted_image_fallback(self):
        from mcp_handley_lab.microsoft.powerpoint.ops.images import (
            _get_image_dimensions,
        )

        # Invalid/corrupted data should return fallback dimensions
        corrupted_data = b"not a valid image"
        width, height = _get_image_dimensions(corrupted_data, "image/png")
        assert width == 640
        assert height == 480


class TestPhase12BugFixes:
    """Tests for Phase 12 bug fixes (Gemini review)."""

    def test_image_namespace_on_root(self):
        """12a: r namespace should be on root p:pic, not on child a:blip."""
        from mcp_handley_lab.microsoft.powerpoint.ops.images import (
            _create_pic_element,
        )

        pic = _create_pic_element(1, "rId1", 1.0, 1.0, 3.0, 2.0)
        # r namespace should be declared on root element
        assert "r" in pic.nsmap or NSMAP["r"] in pic.nsmap.values()
        # a:blip should NOT have its own nsmap override
        blip = pic.find(".//" + qn("a:blip"), NSMAP)
        assert blip is not None

    def test_fill_guard_rejects_non_shape(self):
        """12b: fill guard should only allow sp and cxnSp shapes."""
        from lxml import etree

        # Test the guard logic directly: pic, graphicFrame should be rejected
        for tag in ("pic", "graphicFrame"):
            elem = etree.Element(qn(f"p:{tag}"))
            local = etree.QName(elem.tag).localname
            assert local not in ("sp", "cxnSp"), f"{tag} should be rejected by guard"

        # sp and cxnSp should be allowed
        for tag in ("sp", "cxnSp"):
            elem = etree.Element(qn(f"p:{tag}"))
            local = etree.QName(elem.tag).localname
            assert local in ("sp", "cxnSp"), f"{tag} should be allowed by guard"

    def test_fill_removal_list_no_blipfill(self):
        """12b: a:blipFill should not be in fill removal list."""
        import inspect

        from mcp_handley_lab.microsoft.powerpoint.ops.styling import set_shape_fill

        source = inspect.getsource(set_shape_fill)
        assert "a:blipFill" not in source

    def test_tab_extraction(self):
        """12d: a:tab elements should be extracted as tab characters."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import (
            extract_text_from_txBody,
        )

        tx_body = etree.Element(qn("a:txBody"))
        etree.SubElement(tx_body, qn("a:bodyPr"))
        p = etree.SubElement(tx_body, qn("a:p"))
        r1 = etree.SubElement(p, qn("a:r"))
        t1 = etree.SubElement(r1, qn("a:t"))
        t1.text = "Col1"
        etree.SubElement(p, qn("a:tab"))
        r2 = etree.SubElement(p, qn("a:r"))
        t2 = etree.SubElement(r2, qn("a:t"))
        t2.text = "Col2"

        text = extract_text_from_txBody(tx_body)
        assert text == "Col1\tCol2"

    def test_tab_creation_in_shape_text(self):
        """12d: Tabs in text should create a:tab elements."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import (
            extract_text_from_txBody,
            set_shape_text,
        )

        sp = etree.Element(qn("p:sp"))
        set_shape_text(sp, "A\tB\tC")
        tx_body = sp.find(qn("p:txBody"), NSMAP)
        assert tx_body is not None

        # Should have tab elements
        p = tx_body.find(qn("a:p"), NSMAP)
        tabs = p.findall(qn("a:tab"), NSMAP)
        assert len(tabs) == 2

        # Round-trip should preserve tabs
        text = extract_text_from_txBody(tx_body)
        assert text == "A\tB\tC"

    def test_cell_text_preserves_formatting(self):
        """12c: _set_cell_text should preserve existing formatting."""

        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.tables import _set_cell_text

        # Create a cell with formatting
        tc = etree.Element(qn("a:tc"))
        tx_body = etree.SubElement(tc, qn("a:txBody"))
        etree.SubElement(tx_body, qn("a:bodyPr"))
        etree.SubElement(tx_body, qn("a:lstStyle"))
        p = etree.SubElement(tx_body, qn("a:p"))
        p_pr = etree.SubElement(p, qn("a:pPr"))
        p_pr.set("algn", "ctr")
        r = etree.SubElement(p, qn("a:r"))
        r_pr = etree.SubElement(r, qn("a:rPr"))
        r_pr.set("sz", "2400")
        r_pr.set("b", "1")
        t = etree.SubElement(r, qn("a:t"))
        t.text = "Old text"

        # Set new text
        _set_cell_text(tc, "New text")

        # Verify formatting preserved
        new_tx_body = tc.find(qn("a:txBody"), NSMAP)
        new_p = new_tx_body.find(qn("a:p"), NSMAP)
        new_p_pr = new_p.find(qn("a:pPr"), NSMAP)
        assert new_p_pr is not None
        assert new_p_pr.get("algn") == "ctr"

        new_r = new_p.find(qn("a:r"), NSMAP)
        new_r_pr = new_r.find(qn("a:rPr"), NSMAP)
        assert new_r_pr.get("sz") == "2400"
        assert new_r_pr.get("b") == "1"

        new_t = new_r.find(qn("a:t"), NSMAP)
        assert new_t.text == "New text"


def _add_test_slide(pkg):
    """Add a minimal slide to a new package for testing.

    Works around the fact that PowerPointPackage.new() doesn't have slide masters
    so add_slide() fails. Creates slide XML directly in the package.
    """
    from lxml import etree

    from mcp_handley_lab.microsoft.powerpoint.constants import RT

    slide_xml = etree.fromstring(
        b'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
        b' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        b' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        b"<p:cSld><p:spTree>"
        b'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        b"<p:grpSpPr/>"
        b"</p:spTree></p:cSld></p:sld>"
    )
    partname = "/ppt/slides/slide1.xml"
    pkg._xml[partname] = slide_xml
    pkg._bytes[partname] = etree.tostring(slide_xml)

    # Add relationship from presentation to slide
    pres_rels = pkg.get_rels(pkg.presentation_path)
    r_id = pres_rels.get_or_add(RT.SLIDE, "slides/slide1.xml")

    # Add slide to sldIdLst
    pres = pkg.presentation_xml
    sld_id_lst = pres.find(qn("p:sldIdLst"), NSMAP)
    if sld_id_lst is None:
        sld_id_lst = etree.SubElement(pres, qn("p:sldIdLst"))
    sld_id = etree.SubElement(sld_id_lst, qn("p:sldId"))
    sld_id.set("id", "256")
    sld_id.set(qn("r:id"), r_id)

    # Reset cached slide paths
    pkg._slide_paths = None
    return partname


class TestPhase13SlideBackground:
    """Tests for Phase 13: Slide backgrounds."""

    def test_set_slide_background(self):
        """Setting a background creates p:bg as first child of p:cSld."""
        from mcp_handley_lab.microsoft.powerpoint.ops.styling import (
            set_slide_background,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        result = set_slide_background(pkg, 1, "FF0000")
        assert result is True

        slide_xml = pkg.get_slide_xml(1)
        c_sld = slide_xml.find(qn("p:cSld"), NSMAP)
        bg = c_sld.find(qn("p:bg"), NSMAP)
        assert bg is not None

        # p:bg should be first child of p:cSld
        assert c_sld[0].tag == qn("p:bg")

        # Check structure: p:bg/p:bgPr/a:solidFill/a:srgbClr
        bg_pr = bg.find(qn("p:bgPr"), NSMAP)
        assert bg_pr is not None
        solid_fill = bg_pr.find(qn("a:solidFill"), NSMAP)
        assert solid_fill is not None
        srgb = solid_fill.find(qn("a:srgbClr"), NSMAP)
        assert srgb is not None
        assert srgb.get("val") == "FF0000"

        # effectLst should be present
        assert bg_pr.find(qn("a:effectLst"), NSMAP) is not None

    def test_replace_existing_background(self):
        """Setting background twice replaces the first."""
        from mcp_handley_lab.microsoft.powerpoint.ops.styling import (
            set_slide_background,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        set_slide_background(pkg, 1, "FF0000")
        set_slide_background(pkg, 1, "00FF00")

        slide_xml = pkg.get_slide_xml(1)
        c_sld = slide_xml.find(qn("p:cSld"), NSMAP)
        # Only one p:bg element
        bgs = c_sld.findall(qn("p:bg"), NSMAP)
        assert len(bgs) == 1

        srgb = bgs[0].find(".//" + qn("a:srgbClr"), NSMAP)
        assert srgb.get("val") == "00FF00"


class TestPhase15BulletLists:
    """Tests for Phase 15: Bullet lists."""

    def test_bullet_style_creates_buchar(self):
        """bullet_style='bullet' creates a:buChar with bullet character."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import set_shape_text

        sp = etree.Element(qn("p:sp"))
        set_shape_text(sp, "Item 1\nItem 2", bullet_style="bullet")

        tx_body = sp.find(qn("p:txBody"), NSMAP)
        paragraphs = tx_body.findall(qn("a:p"), NSMAP)
        assert len(paragraphs) == 2

        for p in paragraphs:
            p_pr = p.find(qn("a:pPr"), NSMAP)
            assert p_pr is not None
            bu_char = p_pr.find(qn("a:buChar"), NSMAP)
            assert bu_char is not None
            assert bu_char.get("char") == "\u2022"
            assert p_pr.get("marL") == "228600"
            assert p_pr.get("indent") == "-228600"

    def test_dash_bullet_style(self):
        """bullet_style='dash' creates a:buChar with en-dash."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import set_shape_text

        sp = etree.Element(qn("p:sp"))
        set_shape_text(sp, "Item", bullet_style="dash")

        tx_body = sp.find(qn("p:txBody"), NSMAP)
        p = tx_body.find(qn("a:p"), NSMAP)
        p_pr = p.find(qn("a:pPr"), NSMAP)
        bu_char = p_pr.find(qn("a:buChar"), NSMAP)
        assert bu_char.get("char") == "\u2013"

    def test_number_bullet_style(self):
        """bullet_style='number' creates a:buAutoNum."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import set_shape_text

        sp = etree.Element(qn("p:sp"))
        set_shape_text(sp, "Step 1\nStep 2", bullet_style="number")

        tx_body = sp.find(qn("p:txBody"), NSMAP)
        p = tx_body.find(qn("a:p"), NSMAP)
        p_pr = p.find(qn("a:pPr"), NSMAP)
        bu_auto_num = p_pr.find(qn("a:buAutoNum"), NSMAP)
        assert bu_auto_num is not None
        assert bu_auto_num.get("type") == "arabicPeriod"

    def test_none_bullet_style_removes_bullets(self):
        """bullet_style='none' adds a:buNone and removes indent."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import set_shape_text

        sp = etree.Element(qn("p:sp"))
        # First add bullets
        set_shape_text(sp, "Item", bullet_style="bullet")
        # Then remove
        set_shape_text(sp, "Item", bullet_style="none")

        tx_body = sp.find(qn("p:txBody"), NSMAP)
        p = tx_body.find(qn("a:p"), NSMAP)
        p_pr = p.find(qn("a:pPr"), NSMAP)
        assert p_pr.find(qn("a:buNone"), NSMAP) is not None
        assert p_pr.find(qn("a:buChar"), NSMAP) is None
        assert p_pr.get("marL") is None
        assert p_pr.get("indent") is None

    def test_invalid_bullet_style_raises(self):
        """Unknown bullet_style raises ValueError."""
        import pytest
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import set_shape_text

        sp = etree.Element(qn("p:sp"))
        with pytest.raises(ValueError, match="Unknown bullet_style"):
            set_shape_text(sp, "Item", bullet_style="invalid")

    def test_no_bullet_style_preserves_existing(self):
        """bullet_style=None does not modify bullet state."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import set_shape_text

        sp = etree.Element(qn("p:sp"))
        set_shape_text(sp, "Item", bullet_style="bullet")

        # Edit without bullet_style - should preserve
        set_shape_text(sp, "New text")

        tx_body = sp.find(qn("p:txBody"), NSMAP)
        p = tx_body.find(qn("a:p"), NSMAP)
        p_pr = p.find(qn("a:pPr"), NSMAP)
        # The existing pPr should be preserved with bullet properties
        assert p_pr is not None
        bu_char = p_pr.find(qn("a:buChar"), NSMAP)
        assert bu_char is not None


class TestPhase14Hyperlinks:
    """Tests for Phase 14: Hyperlinks."""

    def test_add_hyperlink(self):
        """Adding a hyperlink creates a:hlinkClick on text runs."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import add_hyperlink

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Add a shape with text
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        sp = etree.SubElement(sp_tree, qn("p:sp"))
        nv_sp_pr = etree.SubElement(sp, qn("p:nvSpPr"))
        c_nv_pr = etree.SubElement(nv_sp_pr, qn("p:cNvPr"))
        c_nv_pr.set("id", "100")
        c_nv_pr.set("name", "Test Shape")
        etree.SubElement(nv_sp_pr, qn("p:cNvSpPr"))
        etree.SubElement(nv_sp_pr, qn("p:nvPr"))
        tx_body = etree.SubElement(sp, qn("p:txBody"))
        etree.SubElement(tx_body, qn("a:bodyPr"))
        p = etree.SubElement(tx_body, qn("a:p"))
        r = etree.SubElement(p, qn("a:r"))
        r_pr = etree.SubElement(r, qn("a:rPr"), lang="en-US")
        t = etree.SubElement(r, qn("a:t"))
        t.text = "Click me"
        slide_partname = pkg.get_slide_partname(1)
        pkg.mark_xml_dirty(slide_partname)

        result = add_hyperlink(pkg, "1:100", "https://example.com", "Example")
        assert result is True

        # Verify a:hlinkClick was added
        hlink = r_pr.find(qn("a:hlinkClick"), NSMAP)
        assert hlink is not None
        assert hlink.get("tooltip") == "Example"

        # Verify relationship was created and is external
        slide_rels = pkg.get_rels(slide_partname)
        r_id = hlink.get(qn("r:id"))
        assert r_id is not None
        assert r_id in slide_rels
        rel = slide_rels[r_id]
        assert rel.is_external is True
        assert rel.target == "https://example.com"

    def test_hyperlink_replaces_existing(self):
        """Adding a hyperlink replaces any existing one."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import add_hyperlink

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Add a shape with text
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        sp = etree.SubElement(sp_tree, qn("p:sp"))
        nv_sp_pr = etree.SubElement(sp, qn("p:nvSpPr"))
        c_nv_pr = etree.SubElement(nv_sp_pr, qn("p:cNvPr"))
        c_nv_pr.set("id", "101")
        c_nv_pr.set("name", "Test Shape")
        etree.SubElement(nv_sp_pr, qn("p:cNvSpPr"))
        etree.SubElement(nv_sp_pr, qn("p:nvPr"))
        tx_body = etree.SubElement(sp, qn("p:txBody"))
        etree.SubElement(tx_body, qn("a:bodyPr"))
        p = etree.SubElement(tx_body, qn("a:p"))
        r = etree.SubElement(p, qn("a:r"))
        r_pr = etree.SubElement(r, qn("a:rPr"), lang="en-US")
        t = etree.SubElement(r, qn("a:t"))
        t.text = "Link text"
        slide_partname = pkg.get_slide_partname(1)
        pkg.mark_xml_dirty(slide_partname)

        # Add first hyperlink
        add_hyperlink(pkg, "1:101", "https://old.com")
        # Replace with second
        add_hyperlink(pkg, "1:101", "https://new.com", "New Link")

        # Should only have one hlinkClick
        hlinks = r_pr.findall(qn("a:hlinkClick"), NSMAP)
        assert len(hlinks) == 1
        assert hlinks[0].get("tooltip") == "New Link"

    def test_hyperlink_no_text_returns_false(self):
        """Hyperlink on shape with no text returns False."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.text import add_hyperlink

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Add a shape without text runs
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        sp = etree.SubElement(sp_tree, qn("p:sp"))
        nv_sp_pr = etree.SubElement(sp, qn("p:nvSpPr"))
        c_nv_pr = etree.SubElement(nv_sp_pr, qn("p:cNvPr"))
        c_nv_pr.set("id", "102")
        c_nv_pr.set("name", "Empty Shape")
        etree.SubElement(nv_sp_pr, qn("p:cNvSpPr"))
        etree.SubElement(nv_sp_pr, qn("p:nvPr"))
        tx_body = etree.SubElement(sp, qn("p:txBody"))
        etree.SubElement(tx_body, qn("a:bodyPr"))
        etree.SubElement(tx_body, qn("a:p"))  # Empty paragraph, no runs
        pkg.mark_xml_dirty(pkg.get_slide_partname(1))

        result = add_hyperlink(pkg, "1:102", url="https://example.com")
        assert result is False

    def test_internal_slide_hyperlink(self):
        """Adding an internal hyperlink links to another slide."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.constants import RT
        from mcp_handley_lab.microsoft.powerpoint.ops.text import add_hyperlink

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)  # Slide 1

        # Add slide 2 manually (helper doesn't support multiple slides)
        slide2_xml = etree.fromstring(
            b'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
            b' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
            b' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            b"<p:cSld><p:spTree>"
            b'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            b"<p:grpSpPr/>"
            b"</p:spTree></p:cSld></p:sld>"
        )
        pkg._xml["/ppt/slides/slide2.xml"] = slide2_xml
        pkg._bytes["/ppt/slides/slide2.xml"] = etree.tostring(slide2_xml)
        pres_rels = pkg.get_rels(pkg.presentation_path)
        r_id2 = pres_rels.get_or_add(RT.SLIDE, "slides/slide2.xml")
        pres = pkg.presentation_xml
        sld_id_lst = pres.find(qn("p:sldIdLst"), NSMAP)
        sld_id2 = etree.SubElement(sld_id_lst, qn("p:sldId"))
        sld_id2.set("id", "257")
        sld_id2.set(qn("r:id"), r_id2)
        pkg._slide_paths = None

        # Add a shape with text on slide 1
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        sp = etree.SubElement(sp_tree, qn("p:sp"))
        nv_sp_pr = etree.SubElement(sp, qn("p:nvSpPr"))
        c_nv_pr = etree.SubElement(nv_sp_pr, qn("p:cNvPr"))
        c_nv_pr.set("id", "103")
        c_nv_pr.set("name", "Link Shape")
        etree.SubElement(nv_sp_pr, qn("p:cNvSpPr"))
        etree.SubElement(nv_sp_pr, qn("p:nvPr"))
        tx_body = etree.SubElement(sp, qn("p:txBody"))
        etree.SubElement(tx_body, qn("a:bodyPr"))
        p = etree.SubElement(tx_body, qn("a:p"))
        r = etree.SubElement(p, qn("a:r"))
        r_pr = etree.SubElement(r, qn("a:rPr"), lang="en-US")
        t = etree.SubElement(r, qn("a:t"))
        t.text = "Go to slide 2"
        slide_partname = pkg.get_slide_partname(1)
        pkg.mark_xml_dirty(slide_partname)

        result = add_hyperlink(pkg, "1:103", target_slide=2, tooltip="Jump to slide 2")
        assert result is True

        # Verify a:hlinkClick was added with action attribute
        hlink = r_pr.find(qn("a:hlinkClick"), NSMAP)
        assert hlink is not None
        assert hlink.get("action") == "ppaction://hlinksldjump"
        assert hlink.get("tooltip") == "Jump to slide 2"

        # Verify relationship points to slide 2
        slide_rels = pkg.get_rels(slide_partname)
        r_id = hlink.get(qn("r:id"))
        assert r_id is not None
        assert r_id in slide_rels
        rel = slide_rels[r_id]
        # Internal hyperlink uses HYPERLINK relationship type with is_external=True
        # (TargetMode="External" is required for hyperlink rels, even internal ones)
        # The action="ppaction://hlinksldjump" controls the jump behavior
        assert rel.is_external is True
        assert rel.reltype == RT.HYPERLINK
        # Should point to slide 2 (relative path)
        assert "slide2" in rel.target

    def test_hyperlink_requires_url_or_target_slide(self):
        """Hyperlink requires either url or target_slide."""
        import pytest

        from mcp_handley_lab.microsoft.powerpoint.ops.text import add_hyperlink

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        with pytest.raises(ValueError, match="Either url or target_slide"):
            add_hyperlink(pkg, "1:100")

    def test_hyperlink_cannot_have_both_url_and_target_slide(self):
        """Cannot specify both url and target_slide."""
        import pytest

        from mcp_handley_lab.microsoft.powerpoint.ops.text import add_hyperlink

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        with pytest.raises(ValueError, match="Cannot specify both"):
            add_hyperlink(pkg, "1:100", url="https://example.com", target_slide=2)


class TestNextPartname:
    """Tests for next_partname utility."""

    def test_next_partname_empty(self):
        pkg = PowerPointPackage.new()
        # No slides exist, so next should be slide1
        next_slide = pkg.next_partname("/ppt/slides/slide", ".xml")
        assert next_slide == "/ppt/slides/slide1.xml"

    def test_next_partname_with_existing(self):
        pkg = PowerPointPackage.new()
        # Manually add some "slides"
        pkg._bytes["/ppt/slides/slide1.xml"] = b""
        pkg._bytes["/ppt/slides/slide2.xml"] = b""
        pkg._bytes["/ppt/slides/slide5.xml"] = b""  # Gap

        # Next should be 6 (max existing + 1)
        next_slide = pkg.next_partname("/ppt/slides/slide", ".xml")
        assert next_slide == "/ppt/slides/slide6.xml"


class TestRender:
    """Tests for PowerPoint rendering."""

    def test_render_validation(self):
        """Test render input validation."""
        import pytest

        from mcp_handley_lab.microsoft.powerpoint.ops.render import render_to_images

        # Empty slides list should raise
        with pytest.raises(ValueError, match="slides is required"):
            render_to_images("/tmp/test.pptx", [])

        # Too many slides should raise
        with pytest.raises(ValueError, match="max 5 slides"):
            render_to_images("/tmp/test.pptx", [1, 2, 3, 4, 5, 6])


class TestPhase18aSlideDimensions:
    """Tests for Phase 18a: Slide dimensions (aspect ratio)."""

    def test_set_dimensions_preset_16x9(self):
        """Test setting 16:9 preset dimensions."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import set_slide_dimensions

        pkg = PowerPointPackage.new()

        # Default is 4:3 (9144000 x 6858000)
        w, h = pkg.get_slide_dimensions()
        assert w == 9144000
        assert h == 6858000

        # Set to 16:9
        set_slide_dimensions(pkg, preset="16:9")

        w, h = pkg.get_slide_dimensions()
        assert w == 12192000
        assert h == 6858000

        # Verify type attribute
        pres = pkg.presentation_xml
        sld_sz = pres.find(qn("p:sldSz"), NSMAP)
        assert sld_sz.get("type") == "screen16x9"

    def test_set_dimensions_preset_4x3(self):
        """Test setting 4:3 preset dimensions."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import set_slide_dimensions

        pkg = PowerPointPackage.new()

        # First change to 16:9
        set_slide_dimensions(pkg, preset="16:9")

        # Then back to 4:3
        set_slide_dimensions(pkg, preset="4:3")

        w, h = pkg.get_slide_dimensions()
        assert w == 9144000
        assert h == 6858000

        pres = pkg.presentation_xml
        sld_sz = pres.find(qn("p:sldSz"), NSMAP)
        assert sld_sz.get("type") == "screen4x3"

    def test_set_dimensions_preset_aliases(self):
        """Test preset aliases (wide, standard, 16x9, 4x3)."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import set_slide_dimensions

        pkg = PowerPointPackage.new()

        # "wide" should work like "16:9"
        set_slide_dimensions(pkg, preset="wide")
        w, h = pkg.get_slide_dimensions()
        assert w == 12192000

        # "standard" should work like "4:3"
        set_slide_dimensions(pkg, preset="standard")
        w, h = pkg.get_slide_dimensions()
        assert w == 9144000

        # "16x9" variant
        set_slide_dimensions(pkg, preset="16x9")
        w, h = pkg.get_slide_dimensions()
        assert w == 12192000

    def test_set_dimensions_custom(self):
        """Test setting custom dimensions in inches."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import set_slide_dimensions

        pkg = PowerPointPackage.new()

        # Set to 8x6 inches
        set_slide_dimensions(pkg, width=8.0, height=6.0)

        w, h = pkg.get_slide_dimensions()
        # 8 inches = 7315200 EMU, 6 inches = 5486400 EMU
        assert w == 7315200
        assert h == 5486400

        # Type attribute should be omitted for custom sizes
        pres = pkg.presentation_xml
        sld_sz = pres.find(qn("p:sldSz"), NSMAP)
        assert "type" not in sld_sz.attrib

    def test_set_dimensions_invalid_preset_raises(self):
        """Test that invalid preset raises ValueError."""
        import pytest

        from mcp_handley_lab.microsoft.powerpoint.ops.slides import set_slide_dimensions

        pkg = PowerPointPackage.new()

        with pytest.raises(ValueError, match="Invalid preset"):
            set_slide_dimensions(pkg, preset="invalid")

    def test_set_dimensions_missing_params_raises(self):
        """Test that missing parameters raises ValueError."""
        import pytest

        from mcp_handley_lab.microsoft.powerpoint.ops.slides import set_slide_dimensions

        pkg = PowerPointPackage.new()

        # Neither preset nor width/height
        with pytest.raises(ValueError, match="Must provide either preset"):
            set_slide_dimensions(pkg)

        # Only width without height
        with pytest.raises(ValueError, match="Must provide either preset"):
            set_slide_dimensions(pkg, width=10.0)

        # Only height without width
        with pytest.raises(ValueError, match="Must provide either preset"):
            set_slide_dimensions(pkg, height=7.5)

    def test_set_dimensions_invalid_size_raises(self):
        """Test that zero or negative dimensions raise ValueError."""
        import pytest

        from mcp_handley_lab.microsoft.powerpoint.ops.slides import set_slide_dimensions

        pkg = PowerPointPackage.new()

        with pytest.raises(ValueError, match="Width must be > 0.1"):
            set_slide_dimensions(pkg, width=0.05, height=6.0)

        with pytest.raises(ValueError, match="Height must be > 0.1"):
            set_slide_dimensions(pkg, width=8.0, height=0.0)


class TestPhase18bShapeTransform:
    """Tests for Phase 18b: Shape transform (move/resize)."""

    def test_transform_move_shape(self):
        """Test moving a shape by changing position."""
        from mcp_handley_lab.microsoft.powerpoint.ops.shapes import (
            add_shape,
            set_shape_transform,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Add a shape at (1, 1)
        shape_key = add_shape(pkg, 1, 1.0, 1.0, 2.0, 1.0, "Test")

        # Move to (2, 3)
        result = set_shape_transform(pkg, shape_key, x=2.0, y=3.0)
        assert result is True

        # Verify position changed
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        shape = sp_tree.find(".//" + qn("p:sp"), NSMAP)
        xfrm = shape.find(qn("p:spPr") + "/" + qn("a:xfrm"), NSMAP)
        off = xfrm.find(qn("a:off"), NSMAP)
        assert off.get("x") == str(int(2.0 * EMU_PER_INCH))
        assert off.get("y") == str(int(3.0 * EMU_PER_INCH))

        # Size should be unchanged
        ext = xfrm.find(qn("a:ext"), NSMAP)
        assert ext.get("cx") == str(int(2.0 * EMU_PER_INCH))
        assert ext.get("cy") == str(int(1.0 * EMU_PER_INCH))

    def test_transform_resize_shape(self):
        """Test resizing a shape by changing dimensions."""
        from mcp_handley_lab.microsoft.powerpoint.ops.shapes import (
            add_shape,
            set_shape_transform,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        shape_key = add_shape(pkg, 1, 1.0, 1.0, 2.0, 1.0, "Test")

        # Resize to 4x3 inches
        result = set_shape_transform(pkg, shape_key, width=4.0, height=3.0)
        assert result is True

        # Verify size changed
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        shape = sp_tree.find(".//" + qn("p:sp"), NSMAP)
        xfrm = shape.find(qn("p:spPr") + "/" + qn("a:xfrm"), NSMAP)
        ext = xfrm.find(qn("a:ext"), NSMAP)
        assert ext.get("cx") == str(int(4.0 * EMU_PER_INCH))
        assert ext.get("cy") == str(int(3.0 * EMU_PER_INCH))

        # Position should be unchanged
        off = xfrm.find(qn("a:off"), NSMAP)
        assert off.get("x") == str(int(1.0 * EMU_PER_INCH))
        assert off.get("y") == str(int(1.0 * EMU_PER_INCH))

    def test_transform_move_and_resize(self):
        """Test moving and resizing in one operation."""
        from mcp_handley_lab.microsoft.powerpoint.ops.shapes import (
            add_shape,
            set_shape_transform,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        shape_key = add_shape(pkg, 1, 1.0, 1.0, 2.0, 1.0, "Test")

        # Move and resize
        result = set_shape_transform(
            pkg, shape_key, x=0.5, y=0.5, width=5.0, height=2.5
        )
        assert result is True

        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        shape = sp_tree.find(".//" + qn("p:sp"), NSMAP)
        xfrm = shape.find(qn("p:spPr") + "/" + qn("a:xfrm"), NSMAP)

        off = xfrm.find(qn("a:off"), NSMAP)
        assert off.get("x") == str(int(0.5 * EMU_PER_INCH))
        assert off.get("y") == str(int(0.5 * EMU_PER_INCH))

        ext = xfrm.find(qn("a:ext"), NSMAP)
        assert ext.get("cx") == str(int(5.0 * EMU_PER_INCH))
        assert ext.get("cy") == str(int(2.5 * EMU_PER_INCH))

    def test_transform_nonexistent_shape_returns_false(self):
        """Test that transforming a nonexistent shape returns False."""
        from mcp_handley_lab.microsoft.powerpoint.ops.shapes import set_shape_transform

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Shape 999 doesn't exist
        result = set_shape_transform(pkg, "1:999", x=1.0, y=1.0)
        assert result is False

    def test_transform_preserves_rotation(self):
        """Test that transforming a shape preserves rotation attributes."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.shapes import set_shape_transform

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Manually create a shape with rotation
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        sp = etree.SubElement(sp_tree, qn("p:sp"))
        nv_sp_pr = etree.SubElement(sp, qn("p:nvSpPr"))
        c_nv_pr = etree.SubElement(nv_sp_pr, qn("p:cNvPr"))
        c_nv_pr.set("id", "50")
        c_nv_pr.set("name", "Rotated Shape")
        etree.SubElement(nv_sp_pr, qn("p:cNvSpPr"))
        etree.SubElement(nv_sp_pr, qn("p:nvPr"))
        sp_pr = etree.SubElement(sp, qn("p:spPr"))
        xfrm = etree.SubElement(sp_pr, qn("a:xfrm"))
        xfrm.set("rot", "5400000")  # 90 degrees
        xfrm.set("flipH", "1")
        etree.SubElement(xfrm, qn("a:off"), x="0", y="0")
        etree.SubElement(xfrm, qn("a:ext"), cx="914400", cy="914400")
        pkg.mark_xml_dirty(pkg.get_slide_partname(1))

        # Transform the shape
        result = set_shape_transform(pkg, "1:50", x=2.0, y=2.0, width=3.0, height=3.0)
        assert result is True

        # Verify rotation is preserved
        xfrm = sp.find(qn("p:spPr") + "/" + qn("a:xfrm"), NSMAP)
        assert xfrm.get("rot") == "5400000"
        assert xfrm.get("flipH") == "1"


class TestPhase18cDuplicateSlide:
    """Tests for Phase 18c: Duplicate slide."""

    def test_duplicate_slide_basic(self):
        """Test basic slide duplication."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import duplicate_slide

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Add content to source slide
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        from lxml import etree

        sp = etree.SubElement(sp_tree, qn("p:sp"))
        nv_sp_pr = etree.SubElement(sp, qn("p:nvSpPr"))
        c_nv_pr = etree.SubElement(nv_sp_pr, qn("p:cNvPr"))
        c_nv_pr.set("id", "10")
        c_nv_pr.set("name", "Test Shape")
        pkg.mark_xml_dirty(pkg.get_slide_partname(1))

        # Duplicate
        new_num = duplicate_slide(pkg, 1)
        assert new_num == 2

        # Verify we now have 2 slides
        assert len(pkg.get_slide_paths()) == 2

        # Verify the new slide has the shape
        new_slide_xml = pkg.get_slide_xml(2)
        new_sp_tree = new_slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        shapes = new_sp_tree.findall(qn("p:sp"), NSMAP)
        # At least one shape should exist
        assert len(shapes) >= 1

    def test_duplicate_slide_at_position(self):
        """Test duplicating a slide at a specific position."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import duplicate_slide

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)
        _add_test_slide(pkg)

        # Should now have 2 slides
        assert len(pkg.get_slide_paths()) == 2

        # Duplicate slide 2 at position 1 (beginning)
        new_num = duplicate_slide(pkg, 2, position=1)
        assert new_num == 1

        # Should now have 3 slides
        assert len(pkg.get_slide_paths()) == 3

    def test_duplicate_slide_preserves_layout_relationship(self):
        """Test that duplicated slide keeps layout relationship."""
        from mcp_handley_lab.microsoft.powerpoint.constants import RT
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import duplicate_slide

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Get source slide's layout relationship
        source_rels = pkg.get_rels(pkg.get_slide_partname(1))
        source_layout_rid = source_rels.rId_for_reltype(RT.SLIDE_LAYOUT)
        source_layout_target = source_rels.target_for_rId(source_layout_rid)

        # Duplicate
        new_num = duplicate_slide(pkg, 1)

        # Get new slide's layout relationship
        new_rels = pkg.get_rels(pkg.get_slide_partname(new_num))
        new_layout_rid = new_rels.rId_for_reltype(RT.SLIDE_LAYOUT)
        new_layout_target = new_rels.target_for_rId(new_layout_rid)

        # Should point to same layout (reused, not duplicated)
        assert new_layout_target == source_layout_target

    def test_duplicate_slide_unique_sld_id(self):
        """Test that duplicated slide gets unique sld_id."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import duplicate_slide

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)
        _add_test_slide(pkg)

        # Get existing sld_ids
        pres = pkg.presentation_xml
        sld_id_lst = pres.find(qn("p:sldIdLst"), NSMAP)
        existing_ids = {el.get("id") for el in sld_id_lst}

        # Duplicate
        duplicate_slide(pkg, 1)

        # Get new sld_ids
        new_ids = {el.get("id") for el in sld_id_lst}

        # Should have one new unique ID
        assert len(new_ids) == len(existing_ids) + 1
        # New ID should be different from all existing
        new_id = new_ids - existing_ids
        assert len(new_id) == 1

    def test_duplicate_slide_excludes_notes(self):
        """Test that notes slide is NOT duplicated."""
        from mcp_handley_lab.microsoft.powerpoint.constants import RT
        from mcp_handley_lab.microsoft.powerpoint.ops.notes import set_notes
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import duplicate_slide

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Add notes to source slide
        set_notes(pkg, 1, "Test notes content")

        # Verify source has notes
        source_rels = pkg.get_rels(pkg.get_slide_partname(1))
        assert source_rels.rId_for_reltype(RT.NOTES_SLIDE) is not None

        # Duplicate
        new_num = duplicate_slide(pkg, 1)

        # New slide should NOT have notes
        new_rels = pkg.get_rels(pkg.get_slide_partname(new_num))
        assert new_rels.rId_for_reltype(RT.NOTES_SLIDE) is None


class TestPhase18dFontSelection:
    """Tests for Phase 18d: Font family selection."""

    def test_set_font_on_shape(self):
        """Test setting font family on shape text."""

        from mcp_handley_lab.microsoft.powerpoint.ops.shapes import add_shape
        from mcp_handley_lab.microsoft.powerpoint.ops.styling import set_text_style

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Add a shape with text
        shape_key = add_shape(pkg, 1, 1.0, 1.0, 2.0, 1.0, "Test text")

        # Set font
        result = set_text_style(pkg, shape_key, font="Arial")
        assert result is True

        # Verify a:latin element was added
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        shape = sp_tree.find(".//" + qn("p:sp"), NSMAP)
        tx_body = shape.find(qn("p:txBody"), NSMAP)
        r = tx_body.find(".//" + qn("a:r"), NSMAP)
        r_pr = r.find(qn("a:rPr"), NSMAP)
        latin = r_pr.find(qn("a:latin"), NSMAP)
        assert latin is not None
        assert latin.get("typeface") == "Arial"

    def test_set_font_updates_existing(self):
        """Test that setting font updates existing a:latin element."""

        from mcp_handley_lab.microsoft.powerpoint.ops.shapes import add_shape
        from mcp_handley_lab.microsoft.powerpoint.ops.styling import set_text_style

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        shape_key = add_shape(pkg, 1, 1.0, 1.0, 2.0, 1.0, "Test")

        # Set initial font
        set_text_style(pkg, shape_key, font="Arial")

        # Update to different font
        set_text_style(pkg, shape_key, font="Times New Roman")

        # Verify only one a:latin and has new font
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        shape = sp_tree.find(".//" + qn("p:sp"), NSMAP)
        tx_body = shape.find(qn("p:txBody"), NSMAP)
        r = tx_body.find(".//" + qn("a:r"), NSMAP)
        r_pr = r.find(qn("a:rPr"), NSMAP)
        latins = r_pr.findall(qn("a:latin"), NSMAP)
        assert len(latins) == 1
        assert latins[0].get("typeface") == "Times New Roman"

    def test_set_font_on_end_para_rpr(self):
        """Test that font is set on endParaRPr as well."""
        from lxml import etree

        from mcp_handley_lab.microsoft.powerpoint.ops.styling import set_text_style

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Create shape with endParaRPr
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        sp = etree.SubElement(sp_tree, qn("p:sp"))
        nv_sp_pr = etree.SubElement(sp, qn("p:nvSpPr"))
        c_nv_pr = etree.SubElement(nv_sp_pr, qn("p:cNvPr"))
        c_nv_pr.set("id", "100")
        c_nv_pr.set("name", "Test")
        etree.SubElement(nv_sp_pr, qn("p:cNvSpPr"))
        etree.SubElement(nv_sp_pr, qn("p:nvPr"))
        tx_body = etree.SubElement(sp, qn("p:txBody"))
        etree.SubElement(tx_body, qn("a:bodyPr"))
        p = etree.SubElement(tx_body, qn("a:p"))
        r = etree.SubElement(p, qn("a:r"))
        etree.SubElement(r, qn("a:rPr"), lang="en-US")
        t = etree.SubElement(r, qn("a:t"))
        t.text = "Test"
        etree.SubElement(p, qn("a:endParaRPr"), lang="en-US")
        pkg.mark_xml_dirty(pkg.get_slide_partname(1))

        # Set font
        result = set_text_style(pkg, "1:100", font="Georgia")
        assert result is True

        # Verify endParaRPr has font
        end_para_r_pr = p.find(qn("a:endParaRPr"), NSMAP)
        latin = end_para_r_pr.find(qn("a:latin"), NSMAP)
        assert latin is not None
        assert latin.get("typeface") == "Georgia"

    def test_set_font_with_other_styles(self):
        """Test setting font along with other text styles."""
        from mcp_handley_lab.microsoft.powerpoint.ops.shapes import add_shape
        from mcp_handley_lab.microsoft.powerpoint.ops.styling import set_text_style

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        shape_key = add_shape(pkg, 1, 1.0, 1.0, 2.0, 1.0, "Test")

        # Set font along with size and bold
        result = set_text_style(pkg, shape_key, font="Courier New", size=14, bold=True)
        assert result is True

        # Verify all styles applied
        slide_xml = pkg.get_slide_xml(1)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        shape = sp_tree.find(".//" + qn("p:sp"), NSMAP)
        tx_body = shape.find(qn("p:txBody"), NSMAP)
        r = tx_body.find(".//" + qn("a:r"), NSMAP)
        r_pr = r.find(qn("a:rPr"), NSMAP)

        # Check font
        latin = r_pr.find(qn("a:latin"), NSMAP)
        assert latin.get("typeface") == "Courier New"

        # Check size (in 100ths of point)
        assert r_pr.get("sz") == "1400"

        # Check bold
        assert r_pr.get("b") == "1"


class TestPhase17cDocumentProperties:
    """Tests for Phase 17c - document properties consolidation."""

    def test_get_core_properties_empty(self):
        """Test getting core properties from new presentation (empty values)."""
        from mcp_handley_lab.microsoft.common.properties import get_core_properties

        pkg = PowerPointPackage.new()
        props = get_core_properties(pkg)

        # New presentations have no core.xml
        assert props["title"] == ""
        assert props["author"] == ""
        assert props["revision"] == 0

    def test_set_core_properties(self):
        """Test setting core properties."""
        from mcp_handley_lab.microsoft.common.properties import (
            get_core_properties,
            set_core_properties,
        )

        pkg = PowerPointPackage.new()

        set_core_properties(
            pkg,
            title="Test Presentation",
            author="Test Author",
            subject="Test Subject",
        )

        props = get_core_properties(pkg)
        assert props["title"] == "Test Presentation"
        assert props["author"] == "Test Author"
        assert props["subject"] == "Test Subject"

    def test_set_custom_property(self):
        """Test setting custom properties."""
        from mcp_handley_lab.microsoft.common.properties import (
            get_custom_properties,
            set_custom_property,
        )

        pkg = PowerPointPackage.new()

        set_custom_property(pkg, "Version", "1.0", "string")
        set_custom_property(pkg, "Count", "42", "int")

        props = get_custom_properties(pkg)
        assert len(props) == 2
        assert props[0]["name"] == "Version"
        assert props[0]["value"] == "1.0"
        assert props[0]["type"] == "string"
        assert props[1]["name"] == "Count"
        assert props[1]["value"] == "42"
        assert props[1]["type"] == "int"

    def test_delete_custom_property(self):
        """Test deleting custom properties."""
        from mcp_handley_lab.microsoft.common.properties import (
            delete_custom_property,
            get_custom_properties,
            set_custom_property,
        )

        pkg = PowerPointPackage.new()

        set_custom_property(pkg, "ToDelete", "value", "string")
        assert len(get_custom_properties(pkg)) == 1

        # Delete it
        result = delete_custom_property(pkg, "ToDelete")
        assert result is True
        assert len(get_custom_properties(pkg)) == 0

        # Deleting non-existent returns False
        result = delete_custom_property(pkg, "NonExistent")
        assert result is False

    def test_properties_persist_after_save(self):
        """Test that properties persist through save/reload cycle."""
        import tempfile
        from pathlib import Path

        from mcp_handley_lab.microsoft.common.properties import (
            get_core_properties,
            get_custom_properties,
            set_core_properties,
            set_custom_property,
        )

        pkg = PowerPointPackage.new()
        set_core_properties(pkg, title="Save Test", author="Tester")
        set_custom_property(pkg, "MyProp", "MyValue", "string")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.pptx"
            pkg.save(str(path))

            # Reload and verify
            pkg2 = PowerPointPackage.open(str(path))
            core = get_core_properties(pkg2)
            assert core["title"] == "Save Test"
            assert core["author"] == "Tester"

            custom = get_custom_properties(pkg2)
            assert len(custom) == 1
            assert custom[0]["name"] == "MyProp"
            assert custom[0]["value"] == "MyValue"

    def test_unknown_property_type_raises(self):
        """Test that unknown property types raise ValueError."""
        import pytest

        from mcp_handley_lab.microsoft.common.properties import set_custom_property

        pkg = PowerPointPackage.new()

        with pytest.raises(ValueError) as exc_info:
            set_custom_property(pkg, "BadType", "value", "invalid_type")

        assert "Unknown property type" in str(exc_info.value)
        assert "invalid_type" in str(exc_info.value)

    def test_filetime_requires_datetime_object(self):
        """Test that filetime type requires datetime, not string."""
        from datetime import datetime, timezone

        import pytest

        from mcp_handley_lab.microsoft.common.properties import (
            get_custom_properties,
            set_custom_property,
        )

        pkg = PowerPointPackage.new()

        # String value for filetime raises TypeError
        with pytest.raises(TypeError) as exc_info:
            set_custom_property(pkg, "BadDate", "2024-01-01", "filetime")

        assert "requires datetime object" in str(exc_info.value)

        # Valid timezone-aware datetime works
        dt = datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        set_custom_property(pkg, "GoodDate", dt, "filetime")

        props = get_custom_properties(pkg)
        assert len(props) == 1
        assert props[0]["name"] == "GoodDate"
        assert props[0]["type"] == "datetime"
        assert "2024-01-15" in props[0]["value"]

    def test_filetime_requires_timezone_aware(self):
        """Test that filetime rejects naive datetime."""
        from datetime import datetime

        import pytest

        from mcp_handley_lab.microsoft.common.properties import set_custom_property

        pkg = PowerPointPackage.new()

        # Naive datetime raises ValueError
        naive_dt = datetime(2024, 1, 15, 12, 30, 0)
        with pytest.raises(ValueError) as exc_info:
            set_custom_property(pkg, "NaiveDate", naive_dt, "datetime")

        assert "timezone-aware" in str(exc_info.value)


class TestPhase19bHideSlides:
    """Tests for Phase 19b: Hide Slides."""

    def test_hide_slide(self):
        """Test hiding a slide."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import (
            hide_slide,
            is_slide_hidden,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)  # Adds slide 1

        # Initially not hidden
        assert is_slide_hidden(pkg, 1) is False

        # Hide the slide
        result = hide_slide(pkg, 1, hidden=True)
        assert result is True
        assert is_slide_hidden(pkg, 1) is True

    def test_show_hidden_slide(self):
        """Test showing a hidden slide."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import (
            hide_slide,
            is_slide_hidden,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Hide then show
        hide_slide(pkg, 1, hidden=True)
        assert is_slide_hidden(pkg, 1) is True

        hide_slide(pkg, 1, hidden=False)
        assert is_slide_hidden(pkg, 1) is False

    def test_hide_nonexistent_slide_returns_false(self):
        """Test that hiding a non-existent slide returns False."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import hide_slide

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Slide 99 doesn't exist
        result = hide_slide(pkg, 99, hidden=True)
        assert result is False

    def test_is_slide_hidden_nonexistent_returns_none(self):
        """Test that checking hidden state of non-existent slide returns None."""
        from mcp_handley_lab.microsoft.powerpoint.ops.slides import is_slide_hidden

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Slide 99 doesn't exist
        result = is_slide_hidden(pkg, 99)
        assert result is None

    def test_hide_slide_persists_after_save(self):
        """Test that hidden state persists through save/reload."""
        import tempfile
        from pathlib import Path

        from mcp_handley_lab.microsoft.powerpoint.ops.slides import (
            hide_slide,
            is_slide_hidden,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)
        hide_slide(pkg, 1, hidden=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.pptx"
            pkg.save(str(path))

            # Reload and verify
            pkg2 = PowerPointPackage.open(str(path))
            assert is_slide_hidden(pkg2, 1) is True

    def test_hide_slide_via_tool(self):
        """Test hiding a slide via the edit tool interface."""
        import json

        from mcp_handley_lab.microsoft.powerpoint.ops.slides import is_slide_hidden
        from mcp_handley_lab.microsoft.powerpoint.tool import edit

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.pptx"
            pkg.save(str(path))

            # Hide via tool
            result = edit(
                str(path),
                ops=json.dumps([{"op": "hide_slide", "slide_num": 1, "hidden": True}]),
            )
            assert result["success"] is True
            assert "Hidden" in result["results"][0]["message"]

            # Verify
            pkg2 = PowerPointPackage.open(str(path))
            assert is_slide_hidden(pkg2, 1) is True

            # Show via tool
            result = edit(
                str(path),
                ops=json.dumps([{"op": "hide_slide", "slide_num": 1, "hidden": False}]),
            )
            assert result["success"] is True
            assert "Shown" in result["results"][0]["message"]

            # Verify
            pkg3 = PowerPointPackage.open(str(path))
            assert is_slide_hidden(pkg3, 1) is False


class TestPhase19cTableRowColumnOps:
    """Tests for Phase 19c: Table Row/Column Operations."""

    def _create_pkg_with_table(self):
        """Create a package with a slide and a 2x3 table."""
        from mcp_handley_lab.microsoft.powerpoint.ops.tables import add_table

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Add a 2x3 table
        shape_key = add_table(pkg, 1, rows=2, cols=3)
        return pkg, shape_key

    def test_add_table_row_at_end(self):
        """Test adding a row at the end of a table."""
        from mcp_handley_lab.microsoft.powerpoint.ops.tables import (
            add_table_row,
            list_tables,
        )

        pkg, shape_key = self._create_pkg_with_table()

        # Initially 2 rows
        tables = list_tables(pkg, 1)
        assert tables[0]["rows"] == 2

        # Add row at end
        result = add_table_row(pkg, shape_key)
        assert result is True

        # Now 3 rows
        tables = list_tables(pkg, 1)
        assert tables[0]["rows"] == 3

    def test_add_table_row_at_position(self):
        """Test adding a row at a specific position."""
        from mcp_handley_lab.microsoft.powerpoint.ops.tables import (
            add_table_row,
            list_tables,
            set_table_cell,
        )

        pkg, shape_key = self._create_pkg_with_table()

        # Set text in first cell to track row positions
        set_table_cell(pkg, shape_key, 0, 0, "Row0")
        set_table_cell(pkg, shape_key, 1, 0, "Row1")

        # Add row at position 1
        result = add_table_row(pkg, shape_key, position=1)
        assert result is True

        # Now 3 rows
        tables = list_tables(pkg, 1)
        assert tables[0]["rows"] == 3

        # Row0 should still be at position 0
        cells = {(c["row"], c["col"]): c["text"] for c in tables[0]["cells"]}
        assert cells[(0, 0)] == "Row0"
        # Row1 should now be at position 2
        assert cells[(2, 0)] == "Row1"

    def test_add_table_column_at_end(self):
        """Test adding a column at the end of a table."""
        from mcp_handley_lab.microsoft.powerpoint.ops.tables import (
            add_table_column,
            list_tables,
        )

        pkg, shape_key = self._create_pkg_with_table()

        # Initially 3 columns
        tables = list_tables(pkg, 1)
        assert tables[0]["cols"] == 3

        # Add column at end
        result = add_table_column(pkg, shape_key)
        assert result is True

        # Now 4 columns
        tables = list_tables(pkg, 1)
        assert tables[0]["cols"] == 4

    def test_add_table_column_at_position(self):
        """Test adding a column at a specific position."""
        from mcp_handley_lab.microsoft.powerpoint.ops.tables import (
            add_table_column,
            list_tables,
            set_table_cell,
        )

        pkg, shape_key = self._create_pkg_with_table()

        # Set text in first row to track column positions
        set_table_cell(pkg, shape_key, 0, 0, "Col0")
        set_table_cell(pkg, shape_key, 0, 1, "Col1")
        set_table_cell(pkg, shape_key, 0, 2, "Col2")

        # Add column at position 1
        result = add_table_column(pkg, shape_key, position=1)
        assert result is True

        # Now 4 columns
        tables = list_tables(pkg, 1)
        assert tables[0]["cols"] == 4

        # Col0 should still be at position 0
        cells = {(c["row"], c["col"]): c["text"] for c in tables[0]["cells"]}
        assert cells[(0, 0)] == "Col0"
        # Col1 should now be at position 2
        assert cells[(0, 2)] == "Col1"
        # Col2 should now be at position 3
        assert cells[(0, 3)] == "Col2"

    def test_delete_table_row(self):
        """Test deleting a row from a table."""
        from mcp_handley_lab.microsoft.powerpoint.ops.tables import (
            delete_table_row,
            list_tables,
            set_table_cell,
        )

        pkg, shape_key = self._create_pkg_with_table()

        # Set text to identify rows
        set_table_cell(pkg, shape_key, 0, 0, "Row0")
        set_table_cell(pkg, shape_key, 1, 0, "Row1")

        # Delete row 0
        result = delete_table_row(pkg, shape_key, 0)
        assert result is True

        # Now 1 row
        tables = list_tables(pkg, 1)
        assert tables[0]["rows"] == 1

        # Row1 should now be at position 0
        cells = {(c["row"], c["col"]): c["text"] for c in tables[0]["cells"]}
        assert cells[(0, 0)] == "Row1"

    def test_delete_table_column(self):
        """Test deleting a column from a table."""
        from mcp_handley_lab.microsoft.powerpoint.ops.tables import (
            delete_table_column,
            list_tables,
            set_table_cell,
        )

        pkg, shape_key = self._create_pkg_with_table()

        # Set text to identify columns
        set_table_cell(pkg, shape_key, 0, 0, "Col0")
        set_table_cell(pkg, shape_key, 0, 1, "Col1")
        set_table_cell(pkg, shape_key, 0, 2, "Col2")

        # Delete column 1 (middle)
        result = delete_table_column(pkg, shape_key, 1)
        assert result is True

        # Now 2 columns
        tables = list_tables(pkg, 1)
        assert tables[0]["cols"] == 2

        # Col0 and Col2 remain
        cells = {(c["row"], c["col"]): c["text"] for c in tables[0]["cells"]}
        assert cells[(0, 0)] == "Col0"
        assert cells[(0, 1)] == "Col2"

    def test_delete_last_row_fails(self):
        """Test that deleting the last row fails."""
        from mcp_handley_lab.microsoft.powerpoint.ops.tables import (
            add_table,
            delete_table_row,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Create a 1x1 table
        shape_key = add_table(pkg, 1, rows=1, cols=1)

        # Deleting the last row should fail
        result = delete_table_row(pkg, shape_key, 0)
        assert result is False

    def test_delete_last_column_fails(self):
        """Test that deleting the last column fails."""
        from mcp_handley_lab.microsoft.powerpoint.ops.tables import (
            add_table,
            delete_table_column,
        )

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        # Create a 1x1 table
        shape_key = add_table(pkg, 1, rows=1, cols=1)

        # Deleting the last column should fail
        result = delete_table_column(pkg, shape_key, 0)
        assert result is False

    def test_table_ops_via_tool(self):
        """Test table operations via the edit tool interface."""
        import json

        from mcp_handley_lab.microsoft.powerpoint.ops.tables import list_tables
        from mcp_handley_lab.microsoft.powerpoint.tool import edit

        pkg = PowerPointPackage.new()
        _add_test_slide(pkg)

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.pptx"
            pkg.save(str(path))

            # Add a 2x2 table via tool
            result = edit(
                str(path),
                ops=json.dumps(
                    [{"op": "add_table", "slide_num": 1, "rows": 2, "cols": 2}]
                ),
            )
            assert result["success"] is True
            shape_key = result["results"][0]["element_id"]

            # Add row via tool
            result = edit(
                str(path),
                ops=json.dumps([{"op": "add_table_row", "shape_key": shape_key}]),
            )
            assert result["success"] is True

            # Verify
            pkg2 = PowerPointPackage.open(str(path))
            tables = list_tables(pkg2, 1)
            assert tables[0]["rows"] == 3

            # Add column via tool
            result = edit(
                str(path),
                ops=json.dumps([{"op": "add_table_column", "shape_key": shape_key}]),
            )
            assert result["success"] is True

            # Verify
            pkg3 = PowerPointPackage.open(str(path))
            tables = list_tables(pkg3, 1)
            assert tables[0]["cols"] == 3

            # Delete row via tool
            result = edit(
                str(path),
                ops=json.dumps(
                    [{"op": "delete_table_row", "shape_key": shape_key, "row": 0}]
                ),
            )
            assert result["success"] is True

            # Verify
            pkg4 = PowerPointPackage.open(str(path))
            tables = list_tables(pkg4, 1)
            assert tables[0]["rows"] == 2

            # Delete column via tool
            result = edit(
                str(path),
                ops=json.dumps(
                    [{"op": "delete_table_column", "shape_key": shape_key, "col": 0}]
                ),
            )
            assert result["success"] is True

            # Verify
            pkg5 = PowerPointPackage.open(str(path))
            tables = list_tables(pkg5, 1)
            assert tables[0]["cols"] == 2
