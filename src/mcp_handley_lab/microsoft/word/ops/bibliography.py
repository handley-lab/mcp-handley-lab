"""Bibliography and citation operations for Word documents.

Contains functions for:
- Managing bibliography sources (add, read, delete)
- Inserting citation fields
- Inserting bibliography fields
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from lxml import etree

from mcp_handley_lab.microsoft.word.constants import CT, NSMAP, RT, qn

if TYPE_CHECKING:
    from mcp_handley_lab.microsoft.word.package import WordPackage

# Bibliography namespace
NS_BIB = NSMAP["b"]
NS_DS = NSMAP["ds"]

# Default bibliography style
DEFAULT_STYLE = "/APASixthEditionOfficeOnline.xsl"

# Valid source types (subset of OOXML SourceType)
VALID_SOURCE_TYPES = {
    "Book",
    "BookSection",
    "JournalArticle",
    "ArticleInAPeriodical",
    "ConferenceProceedings",
    "Report",
    "SoundRecording",
    "Performance",
    "Art",
    "DocumentFromInternetSite",
    "InternetSite",
    "Film",
    "Interview",
    "Patent",
    "ElectronicSource",
    "Case",
    "Misc",
}

# Field name mapping: OOXML element name -> Python dict key
_FIELD_KEYS = {
    "Year": "year",
    "Publisher": "publisher",
    "City": "city",
    "JournalName": "journal_name",
    "Volume": "volume",
    "Issue": "issue",
    "Pages": "pages",
    "URL": "url",
}


def _find_sources_part(pkg: WordPackage) -> tuple[str, etree._Element] | None:
    """Find existing bibliography sources customXml part.

    Scans package-level relationships (/_rels/.rels) for customXml parts
    with <b:Sources> root.

    Returns:
        Tuple of (part_path, sources_element) or None if not found.
    """
    # Get package-level relationships to find customXml parts
    pkg_rels = pkg.get_pkg_rels()

    for rel in pkg_rels.values():
        if rel.reltype == RT.CUSTOM_XML:
            target = rel.target
            # Normalize path
            part_path = f"/{target}" if not target.startswith("/") else target

            # Try to parse and check root element by namespace URI + localname
            try:
                if not pkg.has_part(part_path):
                    continue
                xml_el = pkg.get_xml(part_path)
                if xml_el is not None and xml_el.tag == f"{{{NS_BIB}}}Sources":
                    return part_path, xml_el
            except (KeyError, etree.XMLSyntaxError):
                continue

    return None


def _create_sources_part(pkg: WordPackage) -> tuple[str, etree._Element]:
    """Create new bibliography sources customXml part.

    Creates:
    - /customXml/item{N}.xml with <b:Sources> root
    - /customXml/itemProps{N}.xml with schema references
    - Relationships from package root and within customXml

    Returns:
        Tuple of (part_path, sources_element).
    """
    # Find next available customXml item number
    n = 1
    while pkg.has_part(f"/customXml/item{n}.xml"):
        n += 1

    item_path = f"/customXml/item{n}.xml"
    props_path = f"/customXml/itemProps{n}.xml"

    # Create sources XML
    sources_el = etree.Element(
        qn("b:Sources"),
        nsmap={"b": NS_BIB},
        attrib={"SelectedStyle": DEFAULT_STYLE},
    )

    # Create itemProps XML
    item_id = "{" + str(uuid.uuid4()).upper() + "}"
    props_el = etree.Element(
        qn("ds:datastoreItem"),
        nsmap={"ds": NS_DS},
        attrib={qn("ds:itemID"): item_id},
    )
    schema_refs = etree.SubElement(props_el, qn("ds:schemaRefs"))
    schema_ref = etree.SubElement(schema_refs, qn("ds:schemaRef"))
    schema_ref.set(qn("ds:uri"), NS_BIB)

    # Add relationship from item to props (using public API)
    pkg.relate_to(item_path, f"itemProps{n}.xml", RT.CUSTOM_XML_PROPS)

    # Add relationship from package root to customXml item
    pkg.relate_from_package(f"customXml/item{n}.xml", RT.CUSTOM_XML)

    # Store all parts using public API (set_xml handles content types)
    pkg.set_xml(item_path, sources_el, CT.CUSTOM_XML)
    pkg.set_xml(props_path, props_el, CT.CUSTOM_XML_PROPS)

    return item_path, sources_el


def _get_or_create_sources(pkg: WordPackage) -> tuple[str, etree._Element]:
    """Get existing or create new bibliography sources part."""
    result = _find_sources_part(pkg)
    if result:
        return result
    return _create_sources_part(pkg)


def add_source(
    pkg: WordPackage,
    tag: str,
    source_type: str,
    title: str,
    authors: list[dict] | None = None,
    year: str | None = None,
    publisher: str | None = None,
    city: str | None = None,
    journal_name: str | None = None,
    volume: str | None = None,
    issue: str | None = None,
    pages: str | None = None,
    url: str | None = None,
) -> str:
    """Add a bibliography source.

    Args:
        pkg: WordPackage
        tag: Unique source tag (e.g., 'Smith2020')
        source_type: Source type (Book, JournalArticle, etc.)
        title: Title of the work
        authors: List of author dicts with 'first', 'last', and optional 'middle'
        year: Publication year
        publisher: Publisher name (for books)
        city: City of publication
        journal_name: Journal name (for articles)
        volume: Volume number
        issue: Issue number
        pages: Page range (e.g., '45-67')
        url: URL (for web sources)

    Returns:
        The tag of the added source.

    Raises:
        ValueError: If tag already exists or source_type is invalid.
    """
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(
            f"Invalid source_type '{source_type}'. Valid: {sorted(VALID_SOURCE_TYPES)}"
        )

    part_path, sources_el = _get_or_create_sources(pkg)

    # Check for duplicate tag
    for source in sources_el.findall(qn("b:Source")):
        existing_tag = source.findtext(qn("b:Tag"), "")
        if existing_tag == tag:
            raise ValueError(f"Source with tag '{tag}' already exists")

    # Create source element
    source_el = etree.SubElement(sources_el, qn("b:Source"))

    # Add required fields
    etree.SubElement(source_el, qn("b:Tag")).text = tag
    etree.SubElement(source_el, qn("b:SourceType")).text = source_type
    etree.SubElement(source_el, qn("b:Title")).text = title

    # Add authors if provided
    if authors:
        author_wrapper = etree.SubElement(source_el, qn("b:Author"))
        author_inner = etree.SubElement(author_wrapper, qn("b:Author"))
        name_list = etree.SubElement(author_inner, qn("b:NameList"))
        for author in authors:
            person = etree.SubElement(name_list, qn("b:Person"))
            if "first" in author:
                etree.SubElement(person, qn("b:First")).text = author["first"]
            if "last" in author:
                etree.SubElement(person, qn("b:Last")).text = author["last"]
            if "middle" in author:
                etree.SubElement(person, qn("b:Middle")).text = author["middle"]

    # Add optional fields
    if year:
        etree.SubElement(source_el, qn("b:Year")).text = year
    if publisher:
        etree.SubElement(source_el, qn("b:Publisher")).text = publisher
    if city:
        etree.SubElement(source_el, qn("b:City")).text = city
    if journal_name:
        etree.SubElement(source_el, qn("b:JournalName")).text = journal_name
    if volume:
        etree.SubElement(source_el, qn("b:Volume")).text = volume
    if issue:
        etree.SubElement(source_el, qn("b:Issue")).text = issue
    if pages:
        etree.SubElement(source_el, qn("b:Pages")).text = pages
    if url:
        etree.SubElement(source_el, qn("b:URL")).text = url

    pkg.mark_xml_dirty(part_path)
    return tag


def delete_source(pkg: WordPackage, tag: str) -> bool:
    """Delete a bibliography source by tag.

    Args:
        pkg: WordPackage
        tag: Source tag to delete

    Returns:
        True if source was deleted, False if not found.
    """
    result = _find_sources_part(pkg)
    if not result:
        return False

    part_path, sources_el = result

    for source in sources_el.findall(qn("b:Source")):
        existing_tag = source.findtext(qn("b:Tag"), "")
        if existing_tag == tag:
            sources_el.remove(source)
            pkg.mark_xml_dirty(part_path)
            return True

    return False


def build_sources(pkg: WordPackage) -> list[dict]:
    """Read all bibliography sources.

    Returns:
        List of source dicts with tag, source_type, title, authors, etc.
    """
    result = _find_sources_part(pkg)
    if not result:
        return []

    _, sources_el = result
    sources = []

    for source in sources_el.findall(qn("b:Source")):
        source_dict = {
            "tag": source.findtext(qn("b:Tag"), ""),
            "source_type": source.findtext(qn("b:SourceType"), ""),
            "title": source.findtext(qn("b:Title"), ""),
        }

        # Extract authors
        author_wrapper = source.find(qn("b:Author"))
        if author_wrapper is not None:
            author_inner = author_wrapper.find(qn("b:Author"))
            if author_inner is not None:
                name_list = author_inner.find(qn("b:NameList"))
                if name_list is not None:
                    authors = []
                    for person in name_list.findall(qn("b:Person")):
                        author = {}
                        first = person.findtext(qn("b:First"))
                        last = person.findtext(qn("b:Last"))
                        middle = person.findtext(qn("b:Middle"))
                        if first:
                            author["first"] = first
                        if last:
                            author["last"] = last
                        if middle:
                            author["middle"] = middle
                        if author:
                            authors.append(author)
                    if authors:
                        source_dict["authors"] = authors

        # Extract optional fields
        for field, key in _FIELD_KEYS.items():
            value = source.findtext(qn(f"b:{field}"))
            if value:
                source_dict[key] = value

        sources.append(source_dict)

    return sources
