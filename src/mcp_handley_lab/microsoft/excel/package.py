"""ExcelPackage - Excel-specific wrapper around OpcPackage.

Provides convenience properties and methods for working with .xlsx files.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from lxml import etree

from mcp_handley_lab.microsoft.excel.constants import CT, NSMAP, RT, qn
from mcp_handley_lab.microsoft.opc.package import OpcPackage

# Default content types for Excel files
_EXCEL_DEFAULTS = {
    "rels": "application/vnd.openxmlformats-package.relationships+xml",
    "xml": "application/xml",
    "png": "image/png",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "emf": "image/x-emf",
    "wmf": "image/x-wmf",
}


class SharedStrings:
    """Shared strings table for Excel workbook.

    Excel stores repeated strings once in a shared table for efficiency.
    Cells reference strings by index into this table.
    """

    def __init__(self) -> None:
        self._strings: list[str] = []
        self._index: dict[str, int] = {}  # string -> index for O(1) lookup
        self._dirty = False

    def __len__(self) -> int:
        return len(self._strings)

    def __getitem__(self, idx: int) -> str:
        return self._strings[idx]

    def get_or_add(self, text: str) -> int:
        """Get index for string, adding if not present. Returns index."""
        if text in self._index:
            return self._index[text]
        idx = len(self._strings)
        self._strings.append(text)
        self._index[text] = idx
        self._dirty = True
        return idx

    def add(self, text: str) -> int:
        """Add string and return its index. Always appends (index-stable).

        Use this for editing existing workbooks to preserve index stability.
        For new workbooks where deduplication is desired, use get_or_add().
        """
        idx = len(self._strings)
        self._strings.append(text)
        # Update index only if this is a new string (preserves first-occurrence mapping)
        if text not in self._index:
            self._index[text] = idx
        self._dirty = True
        return idx

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    @classmethod
    def from_xml(cls, xml_bytes: bytes) -> SharedStrings:
        """Parse sharedStrings.xml.

        Index maps to first occurrence of each string value to maintain
        stability - cells reference indices, so duplicates must preserve
        their original positions.
        """
        sst = cls()
        root = etree.fromstring(xml_bytes)
        # Each <si> element contains a string item
        for si in root.findall(qn("x:si")):
            # Simple case: <t>text</t>
            t = si.find(qn("x:t"))
            if t is not None and t.text:
                text = t.text
            else:
                # Rich text: <r><t>part1</t></r><r><t>part2</t></r>
                parts = []
                for r in si.findall(qn("x:r")):
                    t = r.find(qn("x:t"))
                    if t is not None and t.text:
                        parts.append(t.text)
                text = "".join(parts)
            idx = len(sst._strings)
            sst._strings.append(text)
            # Only set index for first occurrence (preserve index stability)
            if text not in sst._index:
                sst._index[text] = idx
        return sst

    def to_xml(self) -> bytes:
        """Serialize to sharedStrings.xml.

        count = total entries in the table (may include duplicates)
        uniqueCount = number of unique string values
        """
        unique_count = len(set(self._strings))
        root = etree.Element(
            qn("x:sst"),
            nsmap={None: NSMAP["x"]},
            count=str(len(self._strings)),
            uniqueCount=str(unique_count),
        )
        for text in self._strings:
            si = etree.SubElement(root, qn("x:si"))
            t = etree.SubElement(si, qn("x:t"))
            t.text = text
            # Preserve whitespace if needed
            if text and (text[0].isspace() or text[-1].isspace()):
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        return etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", standalone=True
        )


class ExcelPackage(OpcPackage):
    """Excel-specific wrapper around OpcPackage.

    Provides convenience properties for common Excel parts and
    handles shared strings management.
    """

    def __init__(self) -> None:
        super().__init__(_EXCEL_DEFAULTS)
        self._shared_strings: SharedStrings | None = None
        self._workbook_path: str | None = None

    # === Workbook discovery ===

    @property
    def workbook_path(self) -> str:
        """Get workbook.xml path by resolving package relationships."""
        if self._workbook_path is None:
            pkg_rels = self.get_pkg_rels()
            rId = pkg_rels.rId_for_reltype(RT.OFFICE_DOCUMENT)
            if rId is None:
                raise ValueError("No workbook relationship found in package")
            self._workbook_path = self.resolve_rel_target("", rId)
        return self._workbook_path

    @property
    def workbook_xml(self) -> etree._Element:
        """Get parsed workbook.xml."""
        return self.get_xml(self.workbook_path)

    # === Sheet discovery ===

    def get_sheet_paths(self) -> list[tuple[str, str, str]]:
        """Get list of (name, rId, partname) for all sheets.

        Resolves sheet references via workbook relationships.
        """
        workbook = self.workbook_xml
        sheets = workbook.find(qn("x:sheets"))
        if sheets is None:
            return []

        result = []
        for sheet in sheets.findall(qn("x:sheet")):
            name = sheet.get("name", "")
            rId = sheet.get(qn("r:id"), "")
            if rId:
                partname = self.resolve_rel_target(self.workbook_path, rId)
                result.append((name, rId, partname))
        return result

    def get_sheet_xml(self, sheet_name: str) -> etree._Element:
        """Get parsed worksheet.xml by sheet name."""
        for name, _rId, partname in self.get_sheet_paths():
            if name == sheet_name:
                return self.get_xml(partname)
        raise KeyError(f"Sheet not found: {sheet_name}")

    def get_sheet_xml_by_index(self, idx: int) -> etree._Element:
        """Get parsed worksheet.xml by 0-based index."""
        return self.get_xml(self.get_sheet_paths()[idx][2])

    # === Shared strings ===

    @property
    def shared_strings(self) -> SharedStrings:
        """Get shared strings table, loading lazily from package."""
        if self._shared_strings is None:
            # Find shared strings via workbook relationships
            wb_rels = self.get_rels(self.workbook_path)
            rId = wb_rels.rId_for_reltype(RT.SHARED_STRINGS)
            if rId:
                ss_path = self.resolve_rel_target(self.workbook_path, rId)
                if self.has_part(ss_path):
                    self._shared_strings = SharedStrings.from_xml(
                        self.get_bytes(ss_path)
                    )
                else:
                    self._shared_strings = SharedStrings()
            else:
                self._shared_strings = SharedStrings()
        return self._shared_strings

    def _ensure_shared_strings_relationship(self) -> str:
        """Ensure shared strings part exists with relationship. Returns partname."""
        ss_path = "/xl/sharedStrings.xml"
        wb_rels = self.get_rels(self.workbook_path)
        if wb_rels.rId_for_reltype(RT.SHARED_STRINGS) is None:
            self.relate_to(self.workbook_path, "sharedStrings.xml", RT.SHARED_STRINGS)
        return ss_path

    # === Styles ===

    @property
    def styles_xml(self) -> etree._Element | None:
        """Get parsed styles.xml, or None if not present."""
        wb_rels = self.get_rels(self.workbook_path)
        rId = wb_rels.rId_for_reltype(RT.STYLES)
        if rId:
            styles_path = self.resolve_rel_target(self.workbook_path, rId)
            if self.has_part(styles_path):
                return self.get_xml(styles_path)
        return None

    # === Calculation chain ===

    def drop_calc_chain(self) -> None:
        """Remove calcChain.xml to force Excel to recalculate.

        Call this after any cell edit that might affect formulas.
        Removes both the part and its relationship to avoid dangling refs.
        """
        wb_rels = self.get_rels(self.workbook_path)
        rId = wb_rels.rId_for_reltype(RT.CALC_CHAIN)
        if rId:
            calc_path = self.resolve_rel_target(self.workbook_path, rId)
            self.drop_part(calc_path)
            self.remove_rel(self.workbook_path, rId)

    # === Saving ===

    def save(self, file: str | Path | BinaryIO) -> None:
        """Save package, including shared strings if modified."""
        # Write shared strings if dirty
        if self._shared_strings is not None and self._shared_strings.is_dirty:
            ss_path = self._ensure_shared_strings_relationship()
            self.set_bytes(
                ss_path, self._shared_strings.to_xml(), CT.SML_SHARED_STRINGS
            )
            self._shared_strings.mark_clean()

        super().save(file)

    # === Factory methods ===

    @classmethod
    def open(cls, file: str | Path | BinaryIO) -> ExcelPackage:
        """Open an existing .xlsx file."""
        pkg = cls()
        if isinstance(file, str | Path):
            with open(file, "rb") as f:
                pkg._load_from_stream(f)
        else:
            pkg._load_from_stream(file)
        return pkg

    @classmethod
    def new(cls) -> ExcelPackage:
        """Create a new empty workbook with minimal required parts.

        Creates:
        - xl/workbook.xml with one sheet reference
        - xl/worksheets/sheet1.xml (empty but valid)
        - xl/styles.xml (minimal to avoid repair warnings)
        - docProps/core.xml (avoids warnings in some viewers)
        """
        pkg = cls()

        # Package relationship to workbook
        pkg.relate_from_package("xl/workbook.xml", RT.OFFICE_DOCUMENT)
        pkg._workbook_path = "/xl/workbook.xml"

        # Create workbook.xml
        workbook = etree.Element(
            qn("x:workbook"),
            nsmap={None: NSMAP["x"], "r": NSMAP["r"]},
        )
        sheets = etree.SubElement(workbook, qn("x:sheets"))
        etree.SubElement(
            sheets,
            qn("x:sheet"),
            name="Sheet1",
            sheetId="1",
            attrib={qn("r:id"): "rId1"},
        )
        pkg.set_xml("/xl/workbook.xml", workbook, CT.SML_SHEET_MAIN)

        # Workbook relationship to sheet
        pkg.relate_to("/xl/workbook.xml", "worksheets/sheet1.xml", RT.WORKSHEET)

        # Create worksheet.xml
        worksheet = etree.Element(
            qn("x:worksheet"),
            nsmap={None: NSMAP["x"]},
        )
        etree.SubElement(worksheet, qn("x:sheetData"))
        pkg.set_xml("/xl/worksheets/sheet1.xml", worksheet, CT.SML_WORKSHEET)

        # Create minimal styles.xml (required to avoid "Repaired Records" warning)
        styles = etree.Element(
            qn("x:styleSheet"),
            nsmap={None: NSMAP["x"]},
        )
        # Minimal font
        fonts = etree.SubElement(styles, qn("x:fonts"), count="1")
        font = etree.SubElement(fonts, qn("x:font"))
        etree.SubElement(font, qn("x:sz"), val="11")
        etree.SubElement(font, qn("x:name"), val="Calibri")

        # Minimal fill
        fills = etree.SubElement(styles, qn("x:fills"), count="2")
        fill1 = etree.SubElement(fills, qn("x:fill"))
        etree.SubElement(fill1, qn("x:patternFill"), patternType="none")
        fill2 = etree.SubElement(fills, qn("x:fill"))
        etree.SubElement(fill2, qn("x:patternFill"), patternType="gray125")

        # Minimal border
        borders = etree.SubElement(styles, qn("x:borders"), count="1")
        border = etree.SubElement(borders, qn("x:border"))
        for side in ("left", "right", "top", "bottom", "diagonal"):
            etree.SubElement(border, qn(f"x:{side}"))

        # Cell style formats
        cellStyleXfs = etree.SubElement(styles, qn("x:cellStyleXfs"), count="1")
        etree.SubElement(
            cellStyleXfs, qn("x:xf"), numFmtId="0", fontId="0", fillId="0", borderId="0"
        )

        # Cell formats
        cellXfs = etree.SubElement(styles, qn("x:cellXfs"), count="1")
        etree.SubElement(
            cellXfs,
            qn("x:xf"),
            numFmtId="0",
            fontId="0",
            fillId="0",
            borderId="0",
            xfId="0",
        )

        pkg.set_xml("/xl/styles.xml", styles, CT.SML_STYLES)
        pkg.relate_to("/xl/workbook.xml", "styles.xml", RT.STYLES)

        # Create core properties (optional but reduces warnings)
        core = etree.Element(
            "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}coreProperties",
            nsmap={
                "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
                "dc": "http://purl.org/dc/elements/1.1/",
                "dcterms": "http://purl.org/dc/terms/",
            },
        )
        pkg.set_xml("/docProps/core.xml", core, CT.OPC_CORE_PROPERTIES)
        pkg.relate_from_package("docProps/core.xml", RT.CORE_PROPERTIES)

        return pkg
