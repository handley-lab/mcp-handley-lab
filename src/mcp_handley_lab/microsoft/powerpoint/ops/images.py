"""Image operations for PowerPoint."""

from __future__ import annotations

import io
import mimetypes
from pathlib import Path

from lxml import etree
from PIL import Image

from mcp_handley_lab.microsoft.powerpoint.constants import NSMAP, RT, qn
from mcp_handley_lab.microsoft.powerpoint.models import ImageInfo
from mcp_handley_lab.microsoft.powerpoint.ops.core import (
    emu_to_inches,
    get_shape_id,
    inches_to_emu,
)
from mcp_handley_lab.microsoft.powerpoint.package import PowerPointPackage

# Map MIME types to PowerPoint-compatible extensions
MIME_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpeg",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/x-emf": ".emf",
    "image/x-wmf": ".wmf",
}


def add_image(
    pkg: PowerPointPackage,
    slide_num: int,
    image_path: str,
    x: float = 1.0,
    y: float = 1.0,
    width: float | None = None,
    height: float | None = None,
) -> str:
    """Add an image to a slide.

    Args:
        pkg: PowerPoint package
        slide_num: Target slide number
        image_path: Path to image file
        x: X position in inches (default 1.0)
        y: Y position in inches (default 1.0)
        width: Width in inches (default: auto from image)
        height: Height in inches (default: auto from image)

    Returns:
        Shape key for the new image (slide_num:shape_id)
    """
    # Read image file
    path = Path(image_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image_data = path.read_bytes()

    # Determine MIME type and extension
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type not in MIME_TO_EXT:
        raise ValueError(f"Unsupported image type: {mime_type}")
    ext = MIME_TO_EXT[mime_type]

    # Get image dimensions if width/height not specified
    if width is None or height is None:
        img_width, img_height = _get_image_dimensions(image_data, mime_type)
        if width is None and height is None:
            # Auto-size: use image dimensions at 96 DPI
            width = img_width / 96.0
            height = img_height / 96.0
        elif width is None:
            # Calculate width from height preserving aspect ratio
            width = height * (img_width / img_height)
        else:
            # Calculate height from width preserving aspect ratio
            height = width * (img_height / img_width)

    # Store image in package
    media_path = pkg.next_partname("/ppt/media/image", ext)
    pkg.set_bytes(media_path, image_data, mime_type)

    # Get slide XML and spTree
    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no spTree")

    # Add relationship from slide to image
    slide_rels = pkg.get_rels(slide_partname)
    rId = slide_rels.get_or_add(RT.IMAGE, media_path)

    # Get next shape ID
    max_id = 0
    for sp in sp_tree.findall(".//" + qn("p:cNvPr"), NSMAP):
        id_str = sp.get("id", "0")
        if id_str.isdigit():
            max_id = max(max_id, int(id_str))
    new_id = max_id + 1

    # Create p:pic element
    pic = _create_pic_element(new_id, rId, x, y, width, height)
    sp_tree.append(pic)

    pkg.mark_xml_dirty(slide_partname)
    pkg._dirty_rels.add(slide_partname)

    return f"{slide_num}:{new_id}"


def _create_pic_element(
    shape_id: int,
    rId: str,
    x: float,
    y: float,
    width: float,
    height: float,
) -> etree._Element:
    """Create a p:pic element for an image."""
    pic = etree.Element(
        qn("p:pic"), nsmap={"p": NSMAP["p"], "a": NSMAP["a"], "r": NSMAP["r"]}
    )

    # nvPicPr (non-visual picture properties)
    nvPicPr = etree.SubElement(pic, qn("p:nvPicPr"))
    cNvPr = etree.SubElement(nvPicPr, qn("p:cNvPr"))
    cNvPr.set("id", str(shape_id))
    cNvPr.set("name", f"Picture {shape_id - 1}")
    cNvPicPr = etree.SubElement(nvPicPr, qn("p:cNvPicPr"))
    # Lock aspect ratio for fidelity
    etree.SubElement(cNvPicPr, qn("a:picLocks"), noChangeAspect="1")
    etree.SubElement(nvPicPr, qn("p:nvPr"))

    # blipFill (image reference and fill mode)
    blipFill = etree.SubElement(pic, qn("p:blipFill"))
    blip = etree.SubElement(blipFill, qn("a:blip"))
    blip.set(qn("r:embed"), rId)
    stretch = etree.SubElement(blipFill, qn("a:stretch"))
    etree.SubElement(stretch, qn("a:fillRect"))

    # spPr (shape properties - position and size)
    spPr = etree.SubElement(pic, qn("p:spPr"))
    xfrm = etree.SubElement(spPr, qn("a:xfrm"))
    off = etree.SubElement(xfrm, qn("a:off"))
    off.set("x", str(inches_to_emu(x)))
    off.set("y", str(inches_to_emu(y)))
    ext = etree.SubElement(xfrm, qn("a:ext"))
    ext.set("cx", str(inches_to_emu(width)))
    ext.set("cy", str(inches_to_emu(height)))

    # Preset geometry (rectangle)
    prstGeom = etree.SubElement(spPr, qn("a:prstGeom"))
    prstGeom.set("prst", "rect")
    etree.SubElement(prstGeom, qn("a:avLst"))

    return pic


def _get_image_dimensions(data: bytes, mime_type: str) -> tuple[int, int]:
    """Get image dimensions (width, height) in pixels using Pillow.

    Args:
        data: Raw image bytes
        mime_type: MIME type (unused, kept for API compatibility)

    Returns:
        (width, height) tuple in pixels

    Raises:
        ValueError: If image cannot be parsed or has invalid dimensions
    """
    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid image dimensions: {width}x{height}")
        return width, height


def list_images(
    pkg: PowerPointPackage, slide_num: int | None = None
) -> list[ImageInfo]:
    """List all images in the presentation or on a specific slide.

    Args:
        pkg: PowerPoint package
        slide_num: Optional slide number to filter by

    Returns:
        List of ImageInfo objects
    """
    images = []
    slide_paths = pkg.get_slide_paths()

    for num, _rid, partname in slide_paths:
        if slide_num is not None and num != slide_num:
            continue

        slide_xml = pkg.get_xml(partname)
        sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
        if sp_tree is None:
            continue

        slide_rels = pkg.get_rels(partname)

        for pic in sp_tree.findall(qn("p:pic"), NSMAP):
            pic_id = get_shape_id(pic)
            if pic_id is None:
                continue

            # Get image name
            cNvPr = pic.find(qn("p:nvPicPr") + "/" + qn("p:cNvPr"), NSMAP)
            name = cNvPr.get("name") if cNvPr is not None else None

            # Get image relationship to determine content type
            content_type = "image/unknown"
            blipFill = pic.find(qn("p:blipFill"), NSMAP)
            if blipFill is not None:
                blip = blipFill.find(qn("a:blip"), NSMAP)
                if blip is not None:
                    rId = blip.get(qn("r:embed"))
                    if rId and rId in slide_rels:
                        media_path = pkg.resolve_rel_target(partname, rId)
                        content_type = (
                            pkg.get_content_type(media_path) or "image/unknown"
                        )

            # Get position and size
            spPr = pic.find(qn("p:spPr"), NSMAP)
            x, y, width, height = 0.0, 0.0, 0.0, 0.0
            if spPr is not None:
                xfrm = spPr.find(qn("a:xfrm"), NSMAP)
                if xfrm is not None:
                    off = xfrm.find(qn("a:off"), NSMAP)
                    if off is not None:
                        x = emu_to_inches(int(off.get("x", "0")))
                        y = emu_to_inches(int(off.get("y", "0")))
                    ext = xfrm.find(qn("a:ext"), NSMAP)
                    if ext is not None:
                        width = emu_to_inches(int(ext.get("cx", "0")))
                        height = emu_to_inches(int(ext.get("cy", "0")))

            images.append(
                ImageInfo(
                    shape_key=f"{num}:{pic_id}",
                    shape_id=pic_id,
                    name=name,
                    content_type=content_type,
                    x_inches=x,
                    y_inches=y,
                    width_inches=width,
                    height_inches=height,
                )
            )

    return images


def delete_image(pkg: PowerPointPackage, slide_num: int, shape_id: int) -> None:
    """Delete an image from a slide.

    Args:
        pkg: PowerPoint package
        slide_num: Slide number
        shape_id: Shape ID of the image to delete

    Raises:
        ValueError: If slide has no shape tree or image not found
    """
    slide_partname = pkg.get_slide_partname(slide_num)
    slide_xml = pkg.get_slide_xml(slide_num)
    sp_tree = slide_xml.find(qn("p:cSld") + "/" + qn("p:spTree"), NSMAP)
    if sp_tree is None:
        raise ValueError(f"Slide {slide_num} has no shape tree")

    # Find the p:pic element with matching shape_id
    for pic in sp_tree.findall(qn("p:pic"), NSMAP):
        pic_id = get_shape_id(pic)
        if pic_id == shape_id:
            # Get the image relationship to potentially clean up
            blipFill = pic.find(qn("p:blipFill"), NSMAP)
            if blipFill is not None:
                blip = blipFill.find(qn("a:blip"), NSMAP)
                if blip is not None:
                    rId = blip.get(qn("r:embed"))
                    if rId:
                        # Remove the relationship (image file cleanup is optional)
                        slide_rels = pkg.get_rels(slide_partname)
                        slide_rels.remove(rId)
                        pkg._dirty_rels.add(slide_partname)

            sp_tree.remove(pic)
            pkg.mark_xml_dirty(slide_partname)
            return

    raise ValueError(f"Image {shape_id} not found on slide {slide_num}")
