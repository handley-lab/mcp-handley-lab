"""Render Word documents to PNG images or PDF using libreoffice."""

import subprocess
import tempfile
from pathlib import Path


def _convert_to_pdf(doc_path: Path, output_dir: Path, profile_dir: Path) -> Path:
    """Convert a Word document to PDF using libreoffice."""
    # Try libreoffice, fall back to soffice (macOS)
    for cmd in ("libreoffice", "soffice"):
        try:
            subprocess.run(
                [
                    cmd,
                    "--headless",
                    "--nologo",
                    "--norestore",
                    "--nolockcheck",
                    f"-env:UserInstallation={profile_dir.as_uri()}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(output_dir),
                    str(doc_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            break
        except FileNotFoundError:
            continue  # Try next command
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("libreoffice timed out after 120s") from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"libreoffice conversion failed: {e.stderr[:500]}"
            ) from e
    else:
        raise FileNotFoundError("libreoffice/soffice not found")

    # Find the output PDF
    pdf_files = list(output_dir.glob("*.pdf"))
    return pdf_files[0]


def render_to_pdf(file_path: str) -> bytes:
    """Render a Word document to PDF."""
    doc_path = Path(file_path).resolve()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        profile_dir = tmp / "profile"
        profile_dir.mkdir()
        pdf_path = _convert_to_pdf(doc_path, tmp, profile_dir)
        return pdf_path.read_bytes()


def render_to_images(
    file_path: str,
    pages: list[int],
    dpi: int = 150,
) -> list[tuple[int, bytes]]:
    """Render a Word document to PNG images.

    Args:
        file_path: Path to the .docx file
        pages: 1-based page numbers to render (required, max 5)
        dpi: Resolution (default 150, max 300)

    Returns:
        List of (page_number, png_bytes) tuples.
    """
    if not pages:
        raise ValueError("pages is required and cannot be empty")
    unique_pages = sorted(set(pages))
    if len(unique_pages) > 5:
        raise ValueError(f"max 5 pages allowed; you requested {len(unique_pages)}")

    doc_path = Path(file_path).resolve()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        profile_dir = tmp / "profile"
        profile_dir.mkdir()

        pdf_path = _convert_to_pdf(doc_path, tmp, profile_dir)

        # Render only the requested pages
        result = []
        for page_num in unique_pages:
            png_prefix = tmp / f"p{page_num}"
            try:
                subprocess.run(
                    [
                        "pdftoppm",
                        "-png",
                        "-r",
                        str(dpi),
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
            except subprocess.TimeoutExpired as e:
                raise RuntimeError(
                    f"pdftoppm timed out rendering page {page_num}"
                ) from e
            except subprocess.CalledProcessError as e:
                raise RuntimeError(
                    f"pdftoppm failed for page {page_num}: {e.stderr[:500]}"
                ) from e

            # pdftoppm outputs p{N}-{page}.png
            expected_png = tmp / f"p{page_num}-{page_num}.png"
            if expected_png.exists():
                result.append((page_num, expected_png.read_bytes()))
            else:
                # Fallback for edge cases
                png_files = list(tmp.glob(f"p{page_num}-*.png"))
                if not png_files:
                    raise RuntimeError(f"page {page_num} not in document")
                result.append((page_num, png_files[0].read_bytes()))

        return result
