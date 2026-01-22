"""Render Word documents to PNG images or PDF using libreoffice."""

import subprocess
import tempfile
from pathlib import Path


def _convert_to_pdf(doc_path: Path, output_dir: Path, profile_dir: Path) -> Path:
    """Convert a Word document to PDF using libreoffice."""
    subprocess.run(
        [
            "libreoffice",
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
    return list(output_dir.glob("*.pdf"))[0]


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
    """Render a Word document to PNG images."""
    if not pages:
        raise ValueError("pages is required")
    unique_pages = sorted(set(pages))
    if len(unique_pages) > 5:
        raise ValueError(f"max 5 pages allowed; requested {len(unique_pages)}")

    doc_path = Path(file_path).resolve()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        profile_dir = tmp / "profile"
        profile_dir.mkdir()

        pdf_path = _convert_to_pdf(doc_path, tmp, profile_dir)

        result = []
        for page_num in unique_pages:
            png_prefix = tmp / f"p{page_num}"
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
            expected_png = tmp / f"p{page_num}-{page_num}.png"
            result.append((page_num, expected_png.read_bytes()))

        return result
