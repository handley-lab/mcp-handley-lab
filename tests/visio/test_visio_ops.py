"""Unit tests for Visio operations.

Tests core cell extraction, shape parsing, page listing,
connection parsing, and master resolution using programmatic .vsdx fixtures.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from lxml import etree

from mcp_handley_lab.microsoft.visio.constants import (
    CT,
    NS_VISIO_2012,
    RT,
    find_v,
    findall_v,
    qn,
)
from mcp_handley_lab.microsoft.visio.ops.core import (
    extract_shape_text,
    get_all_cells,
    get_cell_float,
    get_cell_formula,
    get_cell_value,
    get_section_rows,
    make_shape_key,
    parse_shape_key,
)
from mcp_handley_lab.microsoft.visio.package import VisioPackage

NS = NS_VISIO_2012
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _el(
    tag: str, attrib: dict | None = None, text: str | None = None
) -> etree._Element:
    """Create an element in the Visio 2012 namespace."""
    el = etree.Element(f"{{{NS}}}{tag}", attrib=attrib or {})
    if text:
        el.text = text
    return el


def _sub(
    parent: etree._Element,
    tag: str,
    attrib: dict | None = None,
    text: str | None = None,
) -> etree._Element:
    el = etree.SubElement(parent, f"{{{NS}}}{tag}", attrib=attrib or {})
    if text:
        el.text = text
    return el


def _build_minimal_vsdx(
    num_pages: int = 1,
    shapes_per_page: list[list[dict]] | None = None,
    masters: list[dict] | None = None,
    connects: list[list[dict]] | None = None,
    page_names: list[str] | None = None,
    page_dimensions: list[tuple[float, float]] | None = None,
    background_pages: list[int] | None = None,
) -> io.BytesIO:
    """Build a minimal valid .vsdx in memory.

    Args:
        num_pages: Number of pages
        shapes_per_page: List of shape dicts per page. Each shape dict has:
            id, name, type (optional), pin_x, pin_y, width, height,
            text (optional), master (optional), begin_x/end_x/begin_y/end_y (for connectors)
        masters: List of master dicts: {id, name, name_u (optional)}
        connects: List of connect dicts per page: {from_sheet, to_sheet, from_cell}
        page_names: Names for each page
        page_dimensions: (width, height) in inches per page
        background_pages: 0-based indices of pages that are backgrounds
    """
    buf = io.BytesIO()

    if shapes_per_page is None:
        shapes_per_page = [[] for _ in range(num_pages)]
    if page_names is None:
        page_names = [f"Page-{i + 1}" for i in range(num_pages)]
    if page_dimensions is None:
        page_dimensions = [(8.5, 11.0)] * num_pages
    if background_pages is None:
        background_pages = []
    if connects is None:
        connects = [[] for _ in range(num_pages)]

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Content Types
        ct_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        ct_xml += '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        ct_xml += f'<Override PartName="/visio/document.xml" ContentType="{CT.VSD_DOCUMENT}"/>'
        ct_xml += f'<Override PartName="/visio/pages/pages.xml" ContentType="{CT.VSD_PAGES}"/>'
        for i in range(num_pages):
            ct_xml += f'<Override PartName="/visio/pages/page{i + 1}.xml" ContentType="{CT.VSD_PAGE}"/>'
        if masters:
            ct_xml += f'<Override PartName="/visio/masters/masters.xml" ContentType="{CT.VSD_MASTERS}"/>'
            for m in masters:
                ct_xml += f'<Override PartName="/visio/masters/master{m["id"]}.xml" ContentType="{CT.VSD_MASTER}"/>'
        ct_xml += '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        ct_xml += '<Default Extension="xml" ContentType="application/xml"/>'
        ct_xml += "</Types>"
        z.writestr("[Content_Types].xml", ct_xml)

        # Package rels
        pkg_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        pkg_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        pkg_rels += f'<Relationship Id="rId1" Type="{RT.DOCUMENT}" Target="visio/document.xml"/>'
        pkg_rels += "</Relationships>"
        z.writestr("_rels/.rels", pkg_rels)

        # Document.xml
        doc = _el("VisioDocument")
        z.writestr(
            "visio/document.xml",
            etree.tostring(doc, xml_declaration=True, encoding="UTF-8"),
        )

        # Document rels
        doc_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        doc_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        doc_rels += (
            f'<Relationship Id="rId1" Type="{RT.PAGES}" Target="pages/pages.xml"/>'
        )
        if masters:
            doc_rels += f'<Relationship Id="rId2" Type="{RT.MASTERS}" Target="masters/masters.xml"/>'
        doc_rels += "</Relationships>"
        z.writestr("visio/_rels/document.xml.rels", doc_rels)

        # Pages.xml
        pages = _el("Pages")
        for i in range(num_pages):
            attrib = {
                "ID": str(i),
                "Name": page_names[i],
                "NameU": page_names[i],
                f"{{{NS_REL}}}id": f"rId{i + 1}",
            }
            if i in background_pages:
                attrib["Background"] = "1"
            page_el = _sub(pages, "Page", attrib)
            # PageSheet with dimensions
            page_sheet = _sub(page_el, "PageSheet")
            w, h = page_dimensions[i]
            _sub(page_sheet, "Cell", {"N": "PageWidth", "V": str(w), "U": "IN"})
            _sub(page_sheet, "Cell", {"N": "PageHeight", "V": str(h), "U": "IN"})

        z.writestr(
            "visio/pages/pages.xml",
            etree.tostring(pages, xml_declaration=True, encoding="UTF-8"),
        )

        # Pages rels
        pages_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        pages_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        for i in range(num_pages):
            pages_rels += f'<Relationship Id="rId{i + 1}" Type="{RT.PAGE}" Target="page{i + 1}.xml"/>'
        pages_rels += "</Relationships>"
        z.writestr("visio/pages/_rels/pages.xml.rels", pages_rels)

        # Individual page XMLs
        for i in range(num_pages):
            page_contents = _el("PageContents")

            # Add Connect elements before Shapes
            for conn in connects[i]:
                conn_attrib = {
                    "FromSheet": str(conn["from_sheet"]),
                    "ToSheet": str(conn["to_sheet"]),
                }
                if "from_cell" in conn:
                    conn_attrib["FromCell"] = conn["from_cell"]
                else:
                    conn_attrib["FromCell"] = "BeginX"
                if "from_part" in conn:
                    conn_attrib["FromPart"] = str(conn["from_part"])
                _sub(page_contents, "Connect", conn_attrib)

            shapes_container = _sub(page_contents, "Shapes")
            for shape_dict in shapes_per_page[i]:
                shape_attrib = {
                    "ID": str(shape_dict["id"]),
                    "Name": shape_dict.get("name", f"Shape.{shape_dict['id']}"),
                    "NameU": shape_dict.get("name", f"Shape.{shape_dict['id']}"),
                }
                if "type" in shape_dict:
                    shape_attrib["Type"] = shape_dict["type"]
                if "master" in shape_dict:
                    shape_attrib["Master"] = str(shape_dict["master"])

                shape_el = _sub(shapes_container, "Shape", shape_attrib)

                # Add position cells
                if "pin_x" in shape_dict:
                    _sub(
                        shape_el,
                        "Cell",
                        {"N": "PinX", "V": str(shape_dict["pin_x"]), "U": "IN"},
                    )
                if "pin_y" in shape_dict:
                    _sub(
                        shape_el,
                        "Cell",
                        {"N": "PinY", "V": str(shape_dict["pin_y"]), "U": "IN"},
                    )
                if "width" in shape_dict:
                    _sub(
                        shape_el,
                        "Cell",
                        {"N": "Width", "V": str(shape_dict["width"]), "U": "IN"},
                    )
                if "height" in shape_dict:
                    _sub(
                        shape_el,
                        "Cell",
                        {"N": "Height", "V": str(shape_dict["height"]), "U": "IN"},
                    )

                # Connector endpoints
                if "begin_x" in shape_dict:
                    _sub(
                        shape_el,
                        "Cell",
                        {"N": "BeginX", "V": str(shape_dict["begin_x"]), "U": "IN"},
                    )
                if "begin_y" in shape_dict:
                    _sub(
                        shape_el,
                        "Cell",
                        {"N": "BeginY", "V": str(shape_dict["begin_y"]), "U": "IN"},
                    )
                if "end_x" in shape_dict:
                    _sub(
                        shape_el,
                        "Cell",
                        {"N": "EndX", "V": str(shape_dict["end_x"]), "U": "IN"},
                    )
                if "end_y" in shape_dict:
                    _sub(
                        shape_el,
                        "Cell",
                        {"N": "EndY", "V": str(shape_dict["end_y"]), "U": "IN"},
                    )

                # Text
                if "text" in shape_dict:
                    text_el = _sub(shape_el, "Text")
                    text_el.text = shape_dict["text"]

                # Property section (shape data)
                if "properties" in shape_dict:
                    section = _sub(shape_el, "Section", {"N": "Property"})
                    for prop in shape_dict["properties"]:
                        row = _sub(section, "Row", {"N": prop.get("row_name", "")})
                        if "label" in prop:
                            _sub(row, "Cell", {"N": "Label", "V": prop["label"]})
                        if "value" in prop:
                            _sub(row, "Cell", {"N": "Value", "V": prop["value"]})
                        if "prompt" in prop:
                            _sub(row, "Cell", {"N": "Prompt", "V": prop["prompt"]})

                # Group children
                if "children" in shape_dict:
                    child_shapes = _sub(shape_el, "Shapes")
                    for child in shape_dict["children"]:
                        child_attrib = {
                            "ID": str(child["id"]),
                            "Name": child.get("name", f"Shape.{child['id']}"),
                        }
                        child_el = _sub(child_shapes, "Shape", child_attrib)
                        if "pin_x" in child:
                            _sub(
                                child_el,
                                "Cell",
                                {"N": "PinX", "V": str(child["pin_x"]), "U": "IN"},
                            )
                        if "pin_y" in child:
                            _sub(
                                child_el,
                                "Cell",
                                {"N": "PinY", "V": str(child["pin_y"]), "U": "IN"},
                            )
                        if "width" in child:
                            _sub(
                                child_el,
                                "Cell",
                                {"N": "Width", "V": str(child["width"]), "U": "IN"},
                            )
                        if "height" in child:
                            _sub(
                                child_el,
                                "Cell",
                                {"N": "Height", "V": str(child["height"]), "U": "IN"},
                            )
                        if "text" in child:
                            text_el = _sub(child_el, "Text")
                            text_el.text = child["text"]

            z.writestr(
                f"visio/pages/page{i + 1}.xml",
                etree.tostring(page_contents, xml_declaration=True, encoding="UTF-8"),
            )

        # Masters
        if masters:
            masters_el = _el("Masters")
            for m in masters:
                m_attrib = {
                    "ID": str(m["id"]),
                    "Name": m.get("name", f"Master.{m['id']}"),
                    "NameU": m.get("name_u", m.get("name", f"Master.{m['id']}")),
                    f"{{{NS_REL}}}id": f"rId{m['id']}",
                }
                _sub(masters_el, "Master", m_attrib)
            z.writestr(
                "visio/masters/masters.xml",
                etree.tostring(masters_el, xml_declaration=True, encoding="UTF-8"),
            )

            # Masters rels
            masters_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            masters_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            for m in masters:
                masters_rels += f'<Relationship Id="rId{m["id"]}" Type="{RT.MASTER}" Target="master{m["id"]}.xml"/>'
            masters_rels += "</Relationships>"
            z.writestr("visio/masters/_rels/masters.xml.rels", masters_rels)

            # Individual master XMLs
            for m in masters:
                master_contents = _el("MasterContents")
                master_shapes = _sub(master_contents, "Shapes")
                # Add one dummy shape per master
                _sub(master_shapes, "Shape", {"ID": "1", "Name": "MasterShape"})
                z.writestr(
                    f"visio/masters/master{m['id']}.xml",
                    etree.tostring(
                        master_contents, xml_declaration=True, encoding="UTF-8"
                    ),
                )

    buf.seek(0)
    return buf


# =============================================================================
# Core cell extraction tests
# =============================================================================


class TestCoreOps:
    def test_get_cell_value(self):
        shape = _el("Shape")
        _sub(shape, "Cell", {"N": "PinX", "V": "2.5", "U": "IN"})
        _sub(shape, "Cell", {"N": "PinY", "V": "3.0", "U": "IN"})

        assert get_cell_value(shape, "PinX") == "2.5"
        assert get_cell_value(shape, "PinY") == "3.0"
        assert get_cell_value(shape, "Width") is None

    def test_get_cell_formula(self):
        shape = _el("Shape")
        _sub(shape, "Cell", {"N": "PinX", "V": "2.5", "F": "Width*0.5"})

        assert get_cell_formula(shape, "PinX") == "Width*0.5"
        assert get_cell_formula(shape, "PinY") is None

    def test_get_cell_float(self):
        shape = _el("Shape")
        _sub(shape, "Cell", {"N": "PinX", "V": "2.5"})
        _sub(shape, "Cell", {"N": "Label", "V": "not-a-number"})

        assert get_cell_float(shape, "PinX") == 2.5
        assert get_cell_float(shape, "Label") is None
        assert get_cell_float(shape, "Missing") is None

    def test_get_all_cells(self):
        shape = _el("Shape")
        _sub(shape, "Cell", {"N": "PinX", "V": "2.5", "U": "IN", "F": "=1+1.5"})
        _sub(shape, "Cell", {"N": "Width", "V": "4.0"})

        cells = get_all_cells(shape)
        assert len(cells) == 2
        assert cells[0]["name"] == "PinX"
        assert cells[0]["value"] == "2.5"
        assert cells[0]["formula"] == "=1+1.5"
        assert cells[0]["unit"] == "IN"
        assert cells[1]["name"] == "Width"
        assert cells[1]["unit"] is None

    def test_get_section_rows(self):
        shape = _el("Shape")
        section = _sub(shape, "Section", {"N": "Property"})
        row = _sub(section, "Row", {"N": "Prop1", "IX": "0"})
        _sub(row, "Cell", {"N": "Label", "V": "Cost"})
        _sub(row, "Cell", {"N": "Value", "V": "100"})

        rows = get_section_rows(shape, "Property")
        assert len(rows) == 1
        assert rows[0]["name"] == "Prop1"
        assert rows[0]["index"] == 0
        assert rows[0]["cells"]["Label"]["value"] == "Cost"
        assert rows[0]["cells"]["Value"]["value"] == "100"

    def test_get_section_rows_missing(self):
        shape = _el("Shape")
        rows = get_section_rows(shape, "Property")
        assert rows == []

    def test_extract_shape_text(self):
        shape = _el("Shape")
        text_el = _sub(shape, "Text")
        text_el.text = "Hello "
        cp = _sub(text_el, "cp", {"IX": "0"})
        cp.tail = "World"

        assert extract_shape_text(shape) == "Hello World"

    def test_extract_shape_text_empty(self):
        shape = _el("Shape")
        assert extract_shape_text(shape) is None

    def test_extract_shape_text_whitespace(self):
        shape = _el("Shape")
        text_el = _sub(shape, "Text")
        text_el.text = "   "
        assert extract_shape_text(shape) is None

    def test_make_parse_shape_key(self):
        key = make_shape_key(1, 42)
        assert key == "1:42"
        page, sid = parse_shape_key(key)
        assert page == 1
        assert sid == 42


# =============================================================================
# Namespace helpers
# =============================================================================


class TestNamespaceHelpers:
    def test_qn(self):
        assert qn("v:Shape") == f"{{{NS_VISIO_2012}}}Shape"

    def test_qn_unknown_prefix(self):
        with pytest.raises(ValueError, match="Unknown namespace prefix"):
            qn("unknown:Tag")

    def test_find_v_2012(self):
        root = _el("Root")
        _sub(root, "Child")
        result = find_v(root, "Child")
        assert result is not None

    def test_find_v_2011_fallback(self):
        ns11 = "http://schemas.microsoft.com/office/visio/2011/1/core"
        root = etree.Element(f"{{{ns11}}}Root")
        etree.SubElement(root, f"{{{ns11}}}Child")
        result = find_v(root, "Child")
        assert result is not None

    def test_findall_v_union(self):
        ns11 = "http://schemas.microsoft.com/office/visio/2011/1/core"
        root = etree.Element("Root")
        etree.SubElement(root, f"{{{NS_VISIO_2012}}}Shape", ID="1")
        etree.SubElement(root, f"{{{ns11}}}Shape", ID="2")
        result = findall_v(root, "Shape")
        assert len(result) == 2


# =============================================================================
# Package tests
# =============================================================================


class TestVisioPackage:
    def test_open_minimal(self):
        buf = _build_minimal_vsdx()
        pkg = VisioPackage.open(buf)
        assert pkg.document_path == "/visio/document.xml"

    def test_pages_path(self):
        buf = _build_minimal_vsdx()
        pkg = VisioPackage.open(buf)
        assert pkg.pages_path == "/visio/pages/pages.xml"

    def test_get_page_paths(self):
        buf = _build_minimal_vsdx(num_pages=2)
        pkg = VisioPackage.open(buf)
        paths = pkg.get_page_paths()
        assert len(paths) == 2
        assert paths[0][0] == 1  # page number
        assert paths[1][0] == 2

    def test_get_page_xml(self):
        buf = _build_minimal_vsdx(
            num_pages=1,
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 2.0,
                        "pin_y": 3.0,
                        "width": 1.5,
                        "height": 1.0,
                        "text": "Hello",
                    },
                ]
            ],
        )
        pkg = VisioPackage.open(buf)
        page_xml = pkg.get_page_xml(1)
        assert page_xml is not None

    def test_get_page_xml_invalid(self):
        buf = _build_minimal_vsdx()
        pkg = VisioPackage.open(buf)
        with pytest.raises(KeyError):
            pkg.get_page_xml(99)

    def test_reject_vsd(self, tmp_path):
        path = tmp_path / "test.vsd"
        path.write_bytes(b"dummy")
        with pytest.raises(ValueError, match="Legacy .vsd format"):
            VisioPackage.open(str(path))

    def test_reject_unsupported_extension(self, tmp_path):
        path = tmp_path / "test.docx"
        path.write_bytes(b"dummy")
        with pytest.raises(ValueError, match="Unsupported file format"):
            VisioPackage.open(str(path))

    def test_masters_path(self):
        buf = _build_minimal_vsdx(masters=[{"id": 1, "name": "Rectangle"}])
        pkg = VisioPackage.open(buf)
        assert pkg.masters_path == "/visio/masters/masters.xml"

    def test_masters_path_none(self):
        buf = _build_minimal_vsdx()
        pkg = VisioPackage.open(buf)
        assert pkg.masters_path is None

    def test_get_master_paths(self):
        buf = _build_minimal_vsdx(
            masters=[
                {"id": 1, "name": "Rectangle"},
                {"id": 2, "name": "Circle"},
            ]
        )
        pkg = VisioPackage.open(buf)
        paths = pkg.get_master_paths()
        assert len(paths) == 2

    def test_get_master_xml(self):
        buf = _build_minimal_vsdx(masters=[{"id": 1, "name": "Rectangle"}])
        pkg = VisioPackage.open(buf)
        xml = pkg.get_master_xml(1)
        assert xml is not None

    def test_get_master_xml_missing(self):
        buf = _build_minimal_vsdx(masters=[{"id": 1, "name": "Rectangle"}])
        pkg = VisioPackage.open(buf)
        assert pkg.get_master_xml(99) is None


# =============================================================================
# Page operations tests
# =============================================================================


class TestPageOps:
    def test_list_pages(self):
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        buf = _build_minimal_vsdx(
            num_pages=2,
            page_names=["Design", "Layout"],
            page_dimensions=[(11.0, 8.5), (8.5, 11.0)],
        )
        pkg = VisioPackage.open(buf)
        pages = list_pages(pkg)

        assert len(pages) == 2
        assert pages[0].name == "Design"
        assert pages[0].number == 1
        assert pages[0].width_inches == 11.0
        assert pages[0].height_inches == 8.5
        assert pages[1].name == "Layout"

    def test_list_pages_background(self):
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        buf = _build_minimal_vsdx(num_pages=2, background_pages=[1])
        pkg = VisioPackage.open(buf)
        pages = list_pages(pkg)

        assert not pages[0].is_background
        assert pages[1].is_background

    def test_get_page_dimensions(self):
        from mcp_handley_lab.microsoft.visio.ops.pages import get_page_dimensions

        buf = _build_minimal_vsdx(page_dimensions=[(11.0, 8.5)])
        pkg = VisioPackage.open(buf)
        w, h = get_page_dimensions(pkg, 1)
        assert w == 11.0
        assert h == 8.5

    def test_page_shape_count(self):
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "A",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "B",
                        "pin_x": 3.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        pages = list_pages(pkg)
        assert pages[0].shape_count == 2


# =============================================================================
# Shape operations tests
# =============================================================================


class TestShapeOps:
    def test_list_shapes(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box1",
                        "pin_x": 2.0,
                        "pin_y": 5.0,
                        "width": 1.5,
                        "height": 1.0,
                        "text": "Hello",
                    },
                    {
                        "id": 2,
                        "name": "Box2",
                        "pin_x": 5.0,
                        "pin_y": 3.0,
                        "width": 2.0,
                        "height": 1.0,
                        "text": "World",
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        shapes = list_shapes(pkg, 1)

        assert len(shapes) == 2
        assert shapes[0].text == "Hello" or shapes[0].text == "World"
        # All shapes have reading_order assigned
        orders = [s.reading_order for s in shapes]
        assert orders == [0, 1]

    def test_shape_type_detection(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Rect",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "Conn",
                        "begin_x": 0.0,
                        "begin_y": 0.0,
                        "end_x": 5.0,
                        "end_y": 5.0,
                    },
                    {
                        "id": 3,
                        "name": "Grp",
                        "type": "Group",
                        "pin_x": 3.0,
                        "pin_y": 3.0,
                        "width": 2.0,
                        "height": 2.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        shapes = list_shapes(pkg, 1)

        types_by_name = {s.name: s.type for s in shapes}
        assert types_by_name["Rect"] == "shape"
        assert types_by_name["Conn"] == "connector"
        assert types_by_name["Grp"] == "group"

    def test_connector_endpoints(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Conn",
                        "begin_x": 1.0,
                        "begin_y": 2.0,
                        "end_x": 5.0,
                        "end_y": 6.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        shapes = list_shapes(pkg, 1)

        conn = shapes[0]
        assert conn.type == "connector"
        assert conn.begin_x == 1.0
        assert conn.begin_y == 2.0
        assert conn.end_x == 5.0
        assert conn.end_y == 6.0

    def test_master_reference(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "master": 1,
                    },
                ]
            ],
            masters=[{"id": 1, "name": "Rectangle", "name_u": "Rectangle"}],
        )
        pkg = VisioPackage.open(buf)
        shapes = list_shapes(pkg, 1)

        assert shapes[0].master_id == 1
        assert shapes[0].master_name == "Rectangle"

    def test_group_children(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Group1",
                        "type": "Group",
                        "pin_x": 3.0,
                        "pin_y": 3.0,
                        "width": 4.0,
                        "height": 4.0,
                        "children": [
                            {
                                "id": 2,
                                "name": "Child1",
                                "pin_x": 1.0,
                                "pin_y": 1.0,
                                "width": 0.5,
                                "height": 0.5,
                                "text": "C1",
                            },
                            {
                                "id": 3,
                                "name": "Child2",
                                "pin_x": 2.0,
                                "pin_y": 2.0,
                                "width": 0.5,
                                "height": 0.5,
                                "text": "C2",
                            },
                        ],
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        shapes = list_shapes(pkg, 1)

        assert len(shapes) == 3  # Group + 2 children
        children = [s for s in shapes if s.parent_id == 1]
        assert len(children) == 2

    def test_get_text_in_reading_order(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import get_text_in_reading_order

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Top",
                        "pin_x": 1.0,
                        "pin_y": 10.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "First",
                    },
                    {
                        "id": 2,
                        "name": "Bottom",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Second",
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        text = get_text_in_reading_order(pkg, 1)

        # Top shape (y=10) should come first since flipped Y puts it at top
        assert "First" in text
        assert "Second" in text
        lines = text.split("\n\n")
        assert lines[0] == "First"
        assert lines[1] == "Second"


# =============================================================================
# Connection tests
# =============================================================================


class TestConnectionOps:
    def test_list_connections(self):
        from mcp_handley_lab.microsoft.visio.ops.connections import list_connections

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Start",
                        "pin_x": 1.0,
                        "pin_y": 5.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "End",
                        "pin_x": 5.0,
                        "pin_y": 5.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 3,
                        "name": "Connector",
                        "begin_x": 1.5,
                        "begin_y": 5.0,
                        "end_x": 4.5,
                        "end_y": 5.0,
                    },
                ]
            ],
            connects=[
                [
                    {"from_sheet": 3, "to_sheet": 1, "from_cell": "BeginX"},
                    {"from_sheet": 3, "to_sheet": 2, "from_cell": "EndX"},
                ]
            ],
        )
        pkg = VisioPackage.open(buf)
        conns = list_connections(pkg, 1)

        assert len(conns) == 1
        conn = conns[0]
        assert conn.connector_id == 3
        assert conn.from_shape_id == 1
        assert conn.from_shape_name == "Start"
        assert conn.to_shape_id == 2
        assert conn.to_shape_name == "End"

    def test_no_connections(self):
        from mcp_handley_lab.microsoft.visio.ops.connections import list_connections

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Lonely",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        conns = list_connections(pkg, 1)
        assert conns == []


# =============================================================================
# Master tests
# =============================================================================


class TestMasterOps:
    def test_list_masters(self):
        from mcp_handley_lab.microsoft.visio.ops.masters import list_masters

        buf = _build_minimal_vsdx(
            masters=[
                {"id": 1, "name": "Rectangle", "name_u": "Rectangle"},
                {"id": 2, "name": "Circle", "name_u": "Circle"},
            ]
        )
        pkg = VisioPackage.open(buf)
        masters = list_masters(pkg)

        assert len(masters) == 2
        assert masters[0].master_id == 1
        assert masters[0].name == "Rectangle"
        assert masters[0].name_u == "Rectangle"
        assert masters[0].shape_count == 1  # dummy shape from fixture

    def test_resolve_master_name(self):
        from mcp_handley_lab.microsoft.visio.ops.masters import resolve_master_name

        buf = _build_minimal_vsdx(
            masters=[
                {"id": 1, "name": "Rect"},
                {"id": 5, "name": "Diamond", "name_u": "Diamond"},
            ]
        )
        pkg = VisioPackage.open(buf)
        names = resolve_master_name(pkg)

        assert names[1] == "Rect"
        assert names[5] == "Diamond"

    def test_no_masters(self):
        from mcp_handley_lab.microsoft.visio.ops.masters import list_masters

        buf = _build_minimal_vsdx()
        pkg = VisioPackage.open(buf)
        assert list_masters(pkg) == []


# =============================================================================
# Shape data and cells tests
# =============================================================================


class TestShapeDataOps:
    def test_get_shape_data(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import get_shape_data

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "properties": [
                            {
                                "row_name": "Prop1",
                                "label": "Cost",
                                "value": "100",
                                "prompt": "Enter cost",
                            },
                            {"row_name": "Prop2", "label": "Status", "value": "Active"},
                        ],
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        props = get_shape_data(pkg, 1, 1)

        assert len(props) == 2
        assert props[0].label == "Cost"
        assert props[0].value == "100"
        assert props[0].prompt == "Enter cost"
        assert props[1].label == "Status"

    def test_get_shape_data_missing_shape(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import get_shape_data

        buf = _build_minimal_vsdx(shapes_per_page=[[]])
        pkg = VisioPackage.open(buf)
        with pytest.raises(ValueError, match="Shape 99 not found"):
            get_shape_data(pkg, 1, 99)

    def test_get_shape_cells(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import get_shape_cells

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 2.5,
                        "pin_y": 3.0,
                        "width": 1.0,
                        "height": 0.5,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        cells = get_shape_cells(pkg, 1, 1)

        cell_names = {c.name for c in cells}
        assert "PinX" in cell_names
        assert "PinY" in cell_names
        assert "Width" in cell_names
        assert "Height" in cell_names


# =============================================================================
# Tool integration test
# =============================================================================


class TestVisioTool:
    def test_read_meta(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx(num_pages=2, masters=[{"id": 1, "name": "Rect"}])
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = read(str(path), scope="meta")
        assert result["scope"] == "meta"
        assert result["meta"]["page_count"] == 2
        assert result["meta"]["master_count"] == 1

    def test_read_pages(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx(
            num_pages=2,
            page_names=["Flow", "Detail"],
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = read(str(path), scope="pages")
        assert result["scope"] == "pages"
        assert len(result["pages"]) == 2
        assert result["pages"][0]["name"] == "Flow"

    def test_read_shapes(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 2.0,
                        "pin_y": 5.0,
                        "width": 1.5,
                        "height": 1.0,
                        "text": "Hello",
                    },
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = read(str(path), scope="shapes", page_num=1)
        assert result["scope"] == "shapes"
        assert len(result["shapes"]) == 1
        assert result["shapes"][0]["text"] == "Hello"

    def test_read_text(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "A",
                        "pin_x": 1.0,
                        "pin_y": 10.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Top",
                    },
                    {
                        "id": 2,
                        "name": "B",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Bottom",
                    },
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = read(str(path), scope="text", page_num=1)
        assert result["scope"] == "text"
        assert "Top" in result["text"]
        assert "Bottom" in result["text"]

    def test_read_connections(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "A",
                        "pin_x": 1.0,
                        "pin_y": 5.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "B",
                        "pin_x": 5.0,
                        "pin_y": 5.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 3,
                        "name": "Link",
                        "begin_x": 1.5,
                        "begin_y": 5.0,
                        "end_x": 4.5,
                        "end_y": 5.0,
                    },
                ]
            ],
            connects=[
                [
                    {"from_sheet": 3, "to_sheet": 1, "from_cell": "BeginX"},
                    {"from_sheet": 3, "to_sheet": 2, "from_cell": "EndX"},
                ]
            ],
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = read(str(path), scope="connections", page_num=1)
        assert result["scope"] == "connections"
        assert len(result["connections"]) == 1

    def test_read_masters(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx(masters=[{"id": 1, "name": "Rect"}])
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = read(str(path), scope="masters")
        assert result["scope"] == "masters"
        assert len(result["masters"]) == 1
        assert result["masters"][0]["name"] == "Rect"

    def test_read_shape_data(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "properties": [
                            {"row_name": "Prop1", "label": "Cost", "value": "50"}
                        ],
                    },
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = read(str(path), scope="shape_data", page_num=1, shape_id=1)
        assert result["scope"] == "shape_data"
        assert len(result["shape_data"]) == 1
        assert result["shape_data"][0]["label"] == "Cost"

    def test_read_shape_cells(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 2.5,
                        "pin_y": 3.0,
                        "width": 1.0,
                        "height": 0.5,
                    },
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = read(str(path), scope="shape_cells", page_num=1, shape_id=1)
        assert result["scope"] == "shape_cells"
        cell_names = {c["name"] for c in result["shape_cells"]}
        assert "PinX" in cell_names

    def test_read_requires_page_num(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        with pytest.raises(ValueError, match="page_num required"):
            read(str(path), scope="shapes")

    def test_read_requires_shape_id(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import read

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        with pytest.raises(ValueError, match="shape_id required"):
            read(str(path), scope="shape_data", page_num=1)


# =============================================================================
# Additional edge case tests (from review feedback)
# =============================================================================


class TestNamespace2011EndToEnd:
    """Test that documents using the 2011 namespace variant parse correctly."""

    def _build_2011_vsdx(self) -> io.BytesIO:
        """Build a .vsdx using the 2011 namespace throughout."""
        ns11 = "http://schemas.microsoft.com/office/visio/2011/1/core"
        ns_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            ct_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            ct_xml += '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            ct_xml += f'<Override PartName="/visio/document.xml" ContentType="{CT.VSD_DOCUMENT}"/>'
            ct_xml += f'<Override PartName="/visio/pages/pages.xml" ContentType="{CT.VSD_PAGES}"/>'
            ct_xml += f'<Override PartName="/visio/pages/page1.xml" ContentType="{CT.VSD_PAGE}"/>'
            ct_xml += '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            ct_xml += '<Default Extension="xml" ContentType="application/xml"/>'
            ct_xml += "</Types>"
            z.writestr("[Content_Types].xml", ct_xml)

            pkg_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            pkg_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            pkg_rels += f'<Relationship Id="rId1" Type="{RT.DOCUMENT}" Target="visio/document.xml"/>'
            pkg_rels += "</Relationships>"
            z.writestr("_rels/.rels", pkg_rels)

            doc = etree.Element(f"{{{ns11}}}VisioDocument")
            z.writestr(
                "visio/document.xml",
                etree.tostring(doc, xml_declaration=True, encoding="UTF-8"),
            )

            doc_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            doc_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            doc_rels += (
                f'<Relationship Id="rId1" Type="{RT.PAGES}" Target="pages/pages.xml"/>'
            )
            doc_rels += "</Relationships>"
            z.writestr("visio/_rels/document.xml.rels", doc_rels)

            # Pages.xml in 2011 namespace
            pages = etree.Element(f"{{{ns11}}}Pages")
            page_el = etree.SubElement(
                pages,
                f"{{{ns11}}}Page",
                ID="0",
                Name="Page-1",
                attrib={f"{{{ns_rel}}}id": "rId1"},
            )
            page_sheet = etree.SubElement(page_el, f"{{{ns11}}}PageSheet")
            etree.SubElement(
                page_sheet, f"{{{ns11}}}Cell", N="PageWidth", V="8.5", U="IN"
            )
            etree.SubElement(
                page_sheet, f"{{{ns11}}}Cell", N="PageHeight", V="11.0", U="IN"
            )
            z.writestr(
                "visio/pages/pages.xml",
                etree.tostring(pages, xml_declaration=True, encoding="UTF-8"),
            )

            pages_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            pages_rels += '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            pages_rels += (
                f'<Relationship Id="rId1" Type="{RT.PAGE}" Target="page1.xml"/>'
            )
            pages_rels += "</Relationships>"
            z.writestr("visio/pages/_rels/pages.xml.rels", pages_rels)

            # Page contents in 2011 namespace
            page_contents = etree.Element(f"{{{ns11}}}PageContents")
            shapes_container = etree.SubElement(page_contents, f"{{{ns11}}}Shapes")
            shape_el = etree.SubElement(
                shapes_container, f"{{{ns11}}}Shape", ID="1", Name="Box2011"
            )
            etree.SubElement(shape_el, f"{{{ns11}}}Cell", N="PinX", V="4.0", U="IN")
            etree.SubElement(shape_el, f"{{{ns11}}}Cell", N="PinY", V="5.0", U="IN")
            etree.SubElement(shape_el, f"{{{ns11}}}Cell", N="Width", V="2.0", U="IN")
            etree.SubElement(shape_el, f"{{{ns11}}}Cell", N="Height", V="1.0", U="IN")
            text_el = etree.SubElement(shape_el, f"{{{ns11}}}Text")
            text_el.text = "Hello from 2011"
            z.writestr(
                "visio/pages/page1.xml",
                etree.tostring(page_contents, xml_declaration=True, encoding="UTF-8"),
            )

        buf.seek(0)
        return buf

    def test_2011_shapes_parse(self):
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        buf = self._build_2011_vsdx()
        pkg = VisioPackage.open(buf)
        shapes = list_shapes(pkg, 1)

        assert len(shapes) == 1
        assert shapes[0].name == "Box2011"
        assert shapes[0].text == "Hello from 2011"

    def test_2011_pages_list(self):
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        buf = self._build_2011_vsdx()
        pkg = VisioPackage.open(buf)
        pages = list_pages(pkg)

        assert len(pages) == 1
        assert pages[0].name == "Page-1"
        assert pages[0].width_inches == 8.5


class TestFromPartFallback:
    """Test connection parsing with FromPart instead of FromCell."""

    def test_from_part_9_12(self):
        """FromPart=9 maps to begin, FromPart=12 maps to end."""
        from mcp_handley_lab.microsoft.visio.ops.connections import list_connections

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Start",
                        "pin_x": 1.0,
                        "pin_y": 5.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "End",
                        "pin_x": 5.0,
                        "pin_y": 5.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 3,
                        "name": "Conn",
                        "begin_x": 1.5,
                        "begin_y": 5.0,
                        "end_x": 4.5,
                        "end_y": 5.0,
                    },
                ]
            ],
            connects=[
                [
                    {
                        "from_sheet": 3,
                        "to_sheet": 1,
                        "from_cell": "other",
                        "from_part": 9,
                    },
                    {
                        "from_sheet": 3,
                        "to_sheet": 2,
                        "from_cell": "other",
                        "from_part": 12,
                    },
                ]
            ],
        )
        pkg = VisioPackage.open(buf)
        conns = list_connections(pkg, 1)

        assert len(conns) == 1
        conn = conns[0]
        assert conn.connector_id == 3
        assert conn.from_shape_id == 1
        assert conn.from_shape_name == "Start"
        assert conn.to_shape_id == 2
        assert conn.to_shape_name == "End"

    def test_unknown_from_cell_no_from_part(self):
        """Unknown FromCell without FromPart falls back to first-available slots."""
        from mcp_handley_lab.microsoft.visio.ops.connections import list_connections

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Start",
                        "pin_x": 1.0,
                        "pin_y": 5.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "End",
                        "pin_x": 5.0,
                        "pin_y": 5.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 3,
                        "name": "Conn",
                        "begin_x": 1.5,
                        "begin_y": 5.0,
                        "end_x": 4.5,
                        "end_y": 5.0,
                    },
                ]
            ],
            connects=[
                [
                    {"from_sheet": 3, "to_sheet": 1, "from_cell": "other"},
                    {"from_sheet": 3, "to_sheet": 2, "from_cell": "other"},
                ]
            ],
        )
        pkg = VisioPackage.open(buf)
        conns = list_connections(pkg, 1)

        assert len(conns) == 1
        conn = conns[0]
        assert conn.connector_id == 3
        assert conn.from_shape_id == 1
        assert conn.to_shape_id == 2


class TestConnectionsGroupedShapes:
    """Test that connections resolve names for shapes nested in groups."""

    def test_grouped_shape_name_resolved(self):
        from mcp_handley_lab.microsoft.visio.ops.connections import list_connections

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Group1",
                        "type": "Group",
                        "pin_x": 3.0,
                        "pin_y": 3.0,
                        "width": 4.0,
                        "height": 4.0,
                        "children": [
                            {
                                "id": 10,
                                "name": "ChildA",
                                "pin_x": 1.0,
                                "pin_y": 1.0,
                                "width": 0.5,
                                "height": 0.5,
                            },
                            {
                                "id": 11,
                                "name": "ChildB",
                                "pin_x": 2.0,
                                "pin_y": 2.0,
                                "width": 0.5,
                                "height": 0.5,
                            },
                        ],
                    },
                    {
                        "id": 20,
                        "name": "Connector1",
                        "begin_x": 1.0,
                        "begin_y": 1.0,
                        "end_x": 2.0,
                        "end_y": 2.0,
                    },
                ]
            ],
            connects=[
                [
                    {"from_sheet": 20, "to_sheet": 10, "from_cell": "BeginX"},
                    {"from_sheet": 20, "to_sheet": 11, "from_cell": "EndX"},
                ]
            ],
        )
        pkg = VisioPackage.open(buf)
        conns = list_connections(pkg, 1)

        assert len(conns) == 1
        conn = conns[0]
        assert conn.connector_id == 20
        assert conn.from_shape_id == 10
        assert conn.from_shape_name == "ChildA"
        assert conn.to_shape_id == 11
        assert conn.to_shape_name == "ChildB"


class TestTextEdgeCases:
    """Test text extraction edge cases."""

    def test_text_only_in_tails(self):
        """Text where all content is in child tail text, no direct Text.text."""
        shape = _el("Shape", {"ID": "1"})
        text_el = _sub(shape, "Text")
        # No text_el.text set
        cp1 = _sub(text_el, "cp", {"IX": "0"})
        cp1.tail = "First part "
        cp2 = _sub(text_el, "cp", {"IX": "1"})
        cp2.tail = "second part"

        result = extract_shape_text(shape)
        assert result == "First part second part"

    def test_text_multiple_runs(self):
        """Text with multiple formatting runs."""
        shape = _el("Shape", {"ID": "1"})
        text_el = _sub(shape, "Text")
        text_el.text = "Bold: "
        cp1 = _sub(text_el, "cp", {"IX": "0"})
        cp1.tail = "hello "
        tp = _sub(text_el, "tp", {"IX": "0"})
        tp.tail = "world"

        result = extract_shape_text(shape)
        assert result == "Bold: hello world"


class TestNestedGroups:
    """Test deeply nested group structures."""

    def test_groups_of_groups(self):
        """Groups containing groups with shapes inside."""
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "OuterGroup",
                        "type": "Group",
                        "pin_x": 4.0,
                        "pin_y": 5.0,
                        "width": 6.0,
                        "height": 6.0,
                        "children": [
                            {
                                "id": 2,
                                "name": "InnerShape",
                                "pin_x": 1.0,
                                "pin_y": 1.0,
                                "width": 0.5,
                                "height": 0.5,
                                "text": "Nested",
                            },
                        ],
                    },
                    {
                        "id": 10,
                        "name": "TopLevel",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Top",
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        shapes = list_shapes(pkg, 1)

        names = {s.name for s in shapes}
        assert "OuterGroup" in names
        assert "InnerShape" in names
        assert "TopLevel" in names
        assert len(shapes) == 3

        inner = next(s for s in shapes if s.name == "InnerShape")
        assert inner.parent_id == 1


# =============================================================================
# VisioPackage.new() tests
# =============================================================================


class TestVisioPackageNew:
    def test_new_creates_valid_package(self):
        pkg = VisioPackage.new()
        assert pkg.document_path == "/visio/document.xml"
        assert pkg.pages_path == "/visio/pages/pages.xml"
        pages = pkg.get_page_paths()
        assert len(pages) == 1
        assert pages[0][0] == 1  # page number

    def test_new_has_one_page(self):
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        pkg = VisioPackage.new()
        pages = list_pages(pkg)
        assert len(pages) == 1
        assert pages[0].name == "Page-1"
        assert pages[0].width_inches == 8.5
        assert pages[0].height_inches == 11.0

    def test_new_roundtrip_save(self, tmp_path):
        pkg = VisioPackage.new()
        path = tmp_path / "new.vsdx"
        pkg.save(str(path))
        assert path.exists()
        # Reopen and verify
        pkg2 = VisioPackage.open(str(path))
        assert len(pkg2.get_page_paths()) == 1


# =============================================================================
# Edit operation tests
# =============================================================================


class TestEditOps:
    def test_set_shape_text(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import set_shape_text

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Old text",
                    }
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        key = set_shape_text(pkg, 1, 1, "New text")
        assert key == "1:1"
        # Verify the text changed
        text = extract_shape_text(
            find_v(pkg.get_page_xml(1), "Shapes").findall(f"{{{NS}}}Shape")[0]
        )
        assert text == "New text"

    def test_set_shape_text_roundtrip(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.ops.edit import set_shape_text
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Old",
                    }
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        pkg = VisioPackage.open(str(path))
        set_shape_text(pkg, 1, 1, "Updated")
        pkg.save(str(path))

        pkg2 = VisioPackage.open(str(path))
        shapes = list_shapes(pkg2, 1)
        assert shapes[0].text == "Updated"

    def test_set_shape_cell(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import set_shape_cell

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 2.0,
                        "pin_y": 3.0,
                        "width": 1.0,
                        "height": 1.0,
                    }
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        key = set_shape_cell(pkg, 1, 1, "Width", "5.0", unit="IN")
        assert key == "1:1"
        # Verify
        from mcp_handley_lab.microsoft.visio.ops.core import get_cell_value
        from mcp_handley_lab.microsoft.visio.ops.shapes import find_shape_element

        shape_el = find_shape_element(pkg, 1, 1)
        assert get_cell_value(shape_el, "Width") == "5.0"

    def test_set_shape_cell_creates_new(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import set_shape_cell

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    }
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        set_shape_cell(pkg, 1, 1, "FillForegnd", "#FF0000")
        from mcp_handley_lab.microsoft.visio.ops.core import get_cell_value
        from mcp_handley_lab.microsoft.visio.ops.shapes import find_shape_element

        shape_el = find_shape_element(pkg, 1, 1)
        assert get_cell_value(shape_el, "FillForegnd") == "#FF0000"

    def test_set_shape_data(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import set_shape_data

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "properties": [
                            {
                                "row_name": "Prop1",
                                "label": "Cost",
                                "value": "100",
                            }
                        ],
                    }
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        key = set_shape_data(pkg, 1, 1, "Prop1", "200")
        assert key == "1:1"
        # Verify
        from mcp_handley_lab.microsoft.visio.ops.shapes import get_shape_data

        props = get_shape_data(pkg, 1, 1)
        assert props[0].value == "200"

    def test_set_shape_data_missing_row(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import set_shape_data

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    }
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        with pytest.raises(ValueError, match="Property row.*not found"):
            set_shape_data(pkg, 1, 1, "NonExistent", "val")

    def test_delete_shape(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import delete_shape
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Keep",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "Remove",
                        "pin_x": 3.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)
        delete_shape(pkg, 1, 2)
        shapes = list_shapes(pkg, 1)
        assert len(shapes) == 1
        assert shapes[0].name == "Keep"

    def test_delete_shape_not_found(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import delete_shape

        buf = _build_minimal_vsdx(shapes_per_page=[[]])
        pkg = VisioPackage.open(buf)
        with pytest.raises(ValueError, match="Shape 99 not found"):
            delete_shape(pkg, 1, 99)


# =============================================================================
# Page edit operation tests
# =============================================================================


class TestPageEditOps:
    def test_add_page(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import add_page
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        buf = _build_minimal_vsdx(num_pages=1)
        pkg = VisioPackage.open(buf)
        new_num = add_page(pkg, "NewPage")
        assert new_num == 2
        pages = list_pages(pkg)
        assert len(pages) == 2
        assert pages[1].name == "NewPage"

    def test_add_page_default_name(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import add_page
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        buf = _build_minimal_vsdx(num_pages=1)
        pkg = VisioPackage.open(buf)
        add_page(pkg)
        pages = list_pages(pkg)
        assert pages[1].name == "Page-2"

    def test_delete_page(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import delete_page
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        buf = _build_minimal_vsdx(num_pages=2, page_names=["First", "Second"])
        pkg = VisioPackage.open(buf)
        delete_page(pkg, 2)
        pages = list_pages(pkg)
        assert len(pages) == 1
        assert pages[0].name == "First"

    def test_delete_last_page_fails(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import delete_page

        buf = _build_minimal_vsdx(num_pages=1)
        pkg = VisioPackage.open(buf)
        with pytest.raises(ValueError, match="Cannot delete the only page"):
            delete_page(pkg, 1)

    def test_rename_page(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import rename_page
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        buf = _build_minimal_vsdx(num_pages=1, page_names=["Old"])
        pkg = VisioPackage.open(buf)
        rename_page(pkg, 1, "New")
        pages = list_pages(pkg)
        assert pages[0].name == "New"

    def test_rename_page_out_of_range(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import rename_page

        buf = _build_minimal_vsdx(num_pages=1)
        pkg = VisioPackage.open(buf)
        with pytest.raises(ValueError, match="out of range"):
            rename_page(pkg, 5, "Nope")


# =============================================================================
# Edit tool integration tests
# =============================================================================


class TestEditTool:
    def test_edit_set_text(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Old",
                    }
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(
            str(path),
            ops='[{"op": "set_text", "page_num": 1, "shape_id": 1, "text": "New"}]',
        )
        assert result["success"]
        assert result["saved"]
        assert result["succeeded"] == 1

    def test_edit_atomic_rollback(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Original",
                    }
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(
            str(path),
            ops='[{"op": "set_text", "page_num": 1, "shape_id": 1, "text": "Changed"}, '
            '{"op": "set_text", "page_num": 1, "shape_id": 99, "text": "Fail"}]',
            mode="atomic",
        )
        assert not result["success"]
        assert not result["saved"]

    def test_edit_partial_mode(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Old",
                    }
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(
            str(path),
            ops='[{"op": "set_text", "page_num": 1, "shape_id": 1, "text": "OK"}, '
            '{"op": "set_text", "page_num": 1, "shape_id": 99, "text": "Fail"}]',
            mode="partial",
        )
        assert result["success"]
        assert result["saved"]
        assert result["succeeded"] == 1
        assert result["failed"] == 1

    def test_edit_prev_chaining(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Hello",
                    }
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(
            str(path),
            ops='[{"op": "set_text", "page_num": 1, "shape_id": 1, "text": "Step1"}, '
            '{"op": "set_cell", "shape_key": "$prev[0]", "cell_name": "Width", "value": "5.0"}]',
        )
        assert result["success"]
        assert result["succeeded"] == 2

    def test_edit_auto_create(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        path = tmp_path / "new.vsdx"
        assert not path.exists()

        result = edit(
            str(path),
            ops='[{"op": "rename_page", "page_num": 1, "name": "MyDiagram"}]',
        )
        assert result["success"]
        assert result["saved"]
        assert path.exists()

        # Verify content
        from mcp_handley_lab.microsoft.visio.ops.pages import list_pages

        pkg = VisioPackage.open(str(path))
        pages = list_pages(pkg)
        assert pages[0].name == "MyDiagram"

    def test_edit_invalid_json(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(str(path), ops="not json")
        assert not result["success"]
        assert "Invalid JSON" in result["message"]

    def test_edit_empty_ops(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(str(path), ops="[]")
        assert not result["success"]
        assert "empty" in result["message"]

    def test_edit_unknown_op(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(str(path), ops='[{"op": "bogus"}]')
        assert not result["success"]

    def test_edit_add_and_rename_page(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx(num_pages=1)
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(
            str(path),
            ops='[{"op": "add_page", "name": "Second"}, '
            '{"op": "rename_page", "page_num": 1, "name": "First"}]',
        )
        assert result["success"]
        assert result["succeeded"] == 2

    def test_edit_set_property(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit, read

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(
            str(path),
            ops='[{"op": "set_property", "property_name": "title", "property_value": "My Diagram"}]',
        )
        assert result["success"]

        # Verify
        props = read(str(path), scope="properties")
        assert props["properties"]["title"] == "My Diagram"

    def test_edit_set_custom_property(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(
            str(path),
            ops='[{"op": "set_custom_property", "property_name": "Project", "property_value": "Alpha"}]',
        )
        assert result["success"]

    def test_edit_delete_custom_property_not_found(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(
            str(path),
            ops='[{"op": "delete_custom_property", "property_name": "NonExistent"}]',
        )
        assert not result["success"]

    def test_edit_text_normalization(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import edit

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                        "text": "Old",
                    }
                ]
            ]
        )
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        result = edit(
            str(path),
            ops='[{"op": "set_text", "page_num": 1, "shape_id": 1, "text": "Line1\\nLine2"}]',
        )
        assert result["success"]

        # Verify text has actual newline
        from mcp_handley_lab.microsoft.visio.ops.shapes import list_shapes

        pkg = VisioPackage.open(str(path))
        shapes = list_shapes(pkg, 1)
        assert shapes[0].text == "Line1\nLine2"


# =============================================================================
# Render tool tests (mocked)
# =============================================================================


class TestRenderTool:
    def test_render_png(self, tmp_path):
        from unittest.mock import patch

        from mcp_handley_lab.microsoft.visio.tool import render

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with patch(
            "mcp_handley_lab.microsoft.visio.ops.render.render_to_images",
            return_value=[(1, fake_png)],
        ):
            result = render(str(path), pages=[1], dpi=150, output="png")

        assert len(result) == 2
        assert result[0].type == "text"
        assert "Page 1" in result[0].text
        assert result[1].type == "image"
        assert result[1].mimeType == "image/png"

    def test_render_pdf(self, tmp_path):
        from unittest.mock import patch

        from mcp_handley_lab.microsoft.visio.tool import render

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        fake_pdf = b"%PDF-1.4" + b"\x00" * 100

        with patch(
            "mcp_handley_lab.microsoft.visio.ops.render.render_to_pdf",
            return_value=fake_pdf,
        ):
            result = render(str(path), output="pdf")

        assert len(result) == 2
        assert result[0].type == "text"
        assert "PDF" in result[0].text
        assert result[1].mimeType == "application/pdf"

    def test_render_png_requires_pages(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import render

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        with pytest.raises(ValueError, match="pages is required"):
            render(str(path), pages=[], output="png")

    def test_render_dpi_max(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import render

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        with pytest.raises(ValueError, match="dpi max"):
            render(str(path), pages=[1], dpi=500, output="png")

    def test_render_max_5_pages(self, tmp_path):
        from mcp_handley_lab.microsoft.visio.tool import render

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        with pytest.raises(ValueError, match="max 5 pages"):
            render(str(path), pages=[1, 2, 3, 4, 5, 6], output="png")

    def test_render_duplicates_dont_count(self, tmp_path):
        from unittest.mock import patch

        from mcp_handley_lab.microsoft.visio.tool import render

        buf = _build_minimal_vsdx()
        path = tmp_path / "test.vsdx"
        path.write_bytes(buf.getvalue())

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        # 6 entries but only 1 unique page - should not fail
        with patch(
            "mcp_handley_lab.microsoft.visio.ops.render.render_to_images",
            return_value=[(1, fake_png)],
        ):
            result = render(str(path), pages=[1, 1, 1, 1, 1, 1], output="png")
        assert len(result) == 2


# =============================================================================
# Regression tests for set_shape_cell unit clearing
# =============================================================================


class TestSetShapeCellUnitClearing:
    def test_clear_unit_when_not_specified(self):
        from mcp_handley_lab.microsoft.visio.ops.edit import set_shape_cell

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Box",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    }
                ]
            ]
        )
        pkg = VisioPackage.open(buf)

        # Set with unit
        set_shape_cell(pkg, 1, 1, "Width", "5.0", unit="IN")
        from mcp_handley_lab.microsoft.visio.ops.shapes import find_shape_element

        shape_el = find_shape_element(pkg, 1, 1)
        cell = next(c for c in findall_v(shape_el, "Cell") if c.get("N") == "Width")
        assert cell.get("U") == "IN"

        # Set again without unit - should clear U
        set_shape_cell(pkg, 1, 1, "Width", "3.0")
        shape_el = find_shape_element(pkg, 1, 1)
        cell = next(c for c in findall_v(shape_el, "Cell") if c.get("N") == "Width")
        assert cell.get("U") is None
        assert cell.get("V") == "3.0"


# =============================================================================
# Group/Ungroup tests
# =============================================================================


class TestGroupUngroup:
    """Tests for Visio group/ungroup operations."""

    def test_group_two_shapes(self):
        """Test basic grouping of two shapes."""
        from mcp_handley_lab.microsoft.visio.ops.shapes import (
            group_shapes,
            list_shapes,
        )

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Shape1",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "Shape2",
                        "pin_x": 3.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)

        # Group the shapes
        group_id = group_shapes(pkg, 1, [1, 2])

        # Verify group was created
        shapes = list_shapes(pkg, 1)
        groups = [s for s in shapes if s.type == "group"]
        assert len(groups) == 1
        assert groups[0].shape_id == group_id

        # Children should have parent_id set
        children = [s for s in shapes if s.parent_id == group_id]
        assert len(children) == 2

    def test_group_requires_two_shapes(self):
        """Test that grouping requires at least 2 shapes."""
        from mcp_handley_lab.microsoft.visio.ops.shapes import group_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Shape1",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)

        with pytest.raises(ValueError, match="(?i)at least 2"):
            group_shapes(pkg, 1, [1])

    def test_group_rejects_connectors(self):
        """Test that grouping connectors is rejected."""
        from mcp_handley_lab.microsoft.visio.ops.shapes import group_shapes

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Shape1",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "Connector",
                        "begin_x": 1.5,
                        "begin_y": 1.0,
                        "end_x": 2.5,
                        "end_y": 1.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)

        with pytest.raises(ValueError, match="connectors"):
            group_shapes(pkg, 1, [1, 2])

    def test_ungroup_basic(self):
        """Test basic ungrouping."""
        from mcp_handley_lab.microsoft.visio.ops.shapes import (
            group_shapes,
            list_shapes,
            ungroup,
        )

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Shape1",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "Shape2",
                        "pin_x": 3.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)

        # Group then ungroup
        group_id = group_shapes(pkg, 1, [1, 2])
        child_ids = ungroup(pkg, 1, group_id)

        # Verify ungrouped
        assert len(child_ids) == 2
        shapes = list_shapes(pkg, 1)
        groups = [s for s in shapes if s.type == "group"]
        assert len(groups) == 0

        # Children should be at top level now
        top_level = [s for s in shapes if s.parent_id is None]
        assert len(top_level) == 2

    def test_ungroup_non_group_fails(self):
        """Test that ungrouping a regular shape fails."""
        from mcp_handley_lab.microsoft.visio.ops.shapes import ungroup

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Shape1",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                ]
            ]
        )
        pkg = VisioPackage.open(buf)

        with pytest.raises(ValueError, match="not a group"):
            ungroup(pkg, 1, 1)

    def test_group_via_tool(self):
        """Test group/ungroup via edit tool."""
        import json
        import tempfile
        from pathlib import Path

        from mcp_handley_lab.microsoft.visio.tool import edit, read

        buf = _build_minimal_vsdx(
            shapes_per_page=[
                [
                    {
                        "id": 1,
                        "name": "Shape1",
                        "pin_x": 1.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                    {
                        "id": 2,
                        "name": "Shape2",
                        "pin_x": 3.0,
                        "pin_y": 1.0,
                        "width": 1.0,
                        "height": 1.0,
                    },
                ]
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".vsdx", delete=False) as f:
            f.write(buf.getvalue())
            temp_path = f.name

        try:
            # Group via edit
            result = edit(
                temp_path,
                json.dumps(
                    [{"op": "group_shapes", "page_num": 1, "shape_ids": [1, 2]}]
                ),
            )
            assert result["success"]
            group_key = result["results"][0]["element_id"]
            group_id = int(group_key.split(":")[1])

            # Verify via read
            shapes = read(temp_path, scope="shapes", page_num=1)
            groups = [s for s in shapes["shapes"] if s["type"] == "group"]
            assert len(groups) == 1

            # Ungroup via edit
            result = edit(
                temp_path,
                json.dumps([{"op": "ungroup", "page_num": 1, "group_id": group_id}]),
            )
            assert result["success"]

            # Verify no groups
            shapes = read(temp_path, scope="shapes", page_num=1)
            groups = [s for s in shapes["shapes"] if s["type"] == "group"]
            assert len(groups) == 0

        finally:
            Path(temp_path).unlink(missing_ok=True)
