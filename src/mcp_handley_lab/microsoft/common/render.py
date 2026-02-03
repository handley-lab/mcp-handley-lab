"""Render Office documents (Word, PowerPoint, Visio) to PNG images or PDF using libreoffice."""

import subprocess
import tempfile
from pathlib import Path


def _find_pdf_output(output_dir: Path, input_stem: str) -> Path:
    """Find the PDF output file in the output directory."""
    expected_pdf = output_dir / f"{input_stem}.pdf"
    if expected_pdf.exists():
        return expected_pdf

    pdfs = list(output_dir.glob("*.pdf"))
    if len(pdfs) == 0:
        raise RuntimeError(
            "LibreOffice conversion produced no output. "
            "The document may be corrupted or contain unsupported features."
        )
    if len(pdfs) > 1:
        raise RuntimeError(
            f"LibreOffice conversion produced multiple PDFs: {[p.name for p in pdfs]}"
        )
    return pdfs[0]


def _convert_to_pdf(file_path: Path, output_dir: Path, timeout: int) -> Path:
    """Convert an Office document to PDF using libreoffice."""
    try:
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--nologo",
                "--norestore",
                "--nolockcheck",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "libreoffice not found. Install LibreOffice and ensure 'libreoffice' is on PATH."
        ) from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"PDF conversion timed out after {timeout}s. "
            "Document may be too complex or contain large embedded images."
        ) from None
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        if "compress" in stderr.lower() or "image" in stderr.lower():
            hint = "Large embedded images may cause this. Try compressing images before insertion."
        else:
            hint = "Check document for corruption or unsupported features."
        raise RuntimeError(f"PDF conversion failed: {stderr.strip()}\n{hint}") from None
    return _find_pdf_output(output_dir, file_path.stem)


def convert_to_pdf(file_path: str, timeout: int = 120) -> bytes:
    """Convert an Office document to PDF using libreoffice."""
    doc_path = Path(file_path).resolve()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pdf_path = _convert_to_pdf(doc_path, tmp, timeout)
        return pdf_path.read_bytes()


def render_pages_to_images(
    file_path: str,
    pages: list[int],
    dpi: int = 150,
    max_pages: int = 5,
    timeout: int = 120,
) -> list[tuple[int, bytes]]:
    """Render Office document pages/slides to PNG images.

    Args:
        file_path: Path to the Office document (.docx, .docm, .pptx, .pptm, .ppsx)
        pages: List of 1-based page/slide numbers to render
        dpi: Resolution in dots per inch (72-300, default: 150)
        max_pages: Maximum number of pages allowed (default: 5)
        timeout: Maximum time in seconds for PDF conversion (default: 120)

    Returns:
        List of (page_number, png_bytes) tuples

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If file type not supported, pages empty, too many pages,
                   DPI out of range, or page out of bounds
        RuntimeError: If libreoffice/pdftoppm not found or conversion fails
    """
    if not pages:
        raise ValueError("pages is required")

    unique_pages = sorted(set(pages))
    if len(unique_pages) > max_pages:
        raise ValueError(
            f"max {max_pages} pages allowed; requested {len(unique_pages)}"
        )

    dpi_int = round(dpi)
    doc_path = Path(file_path).resolve()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pdf_path = _convert_to_pdf(doc_path, tmp, timeout)

        result = []
        for page_num in unique_pages:
            png_prefix = tmp / f"page{page_num}"
            try:
                subprocess.run(
                    [
                        "pdftoppm",
                        "-png",
                        "-r",
                        str(dpi_int),
                        "-f",
                        str(page_num),
                        "-l",
                        str(page_num),
                        str(pdf_path),
                        str(png_prefix),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"pdftoppm failed: {e.stderr}") from e
            except subprocess.TimeoutExpired as e:
                raise RuntimeError(f"Page {page_num} render timed out") from e

            # pdftoppm creates files with zero-padded page numbers based on total
            # page count: page1-1.png (1-9 pages), page1-01.png (10-99 pages), etc.
            # Use glob to find the actual output file.
            png_files = list(tmp.glob(f"page{page_num}-*.png"))
            if not png_files:
                raise ValueError(
                    f"Page {page_num} out of bounds. "
                    "The document may have fewer pages than requested."
                )
            result.append((page_num, png_files[0].read_bytes()))

        return result
