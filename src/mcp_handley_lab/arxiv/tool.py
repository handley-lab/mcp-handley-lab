"""ArXiv source code retrieval MCP server."""

import gzip
import os
import tarfile
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.shared.models import ServerInfo


class DownloadResult(BaseModel):
    """Result of downloading an ArXiv paper."""

    message: str
    arxiv_id: str
    format: str
    output_path: str
    size_bytes: int
    files: list[str] = Field(default_factory=list)


class ArxivPaper(BaseModel):
    """ArXiv paper metadata."""

    id: str
    title: str
    authors: list[str]
    summary: str
    published: str
    categories: list[str]
    pdf_url: str
    abs_url: str


mcp = FastMCP("ArXiv Tool")


def _get_cached_source(arxiv_id: str) -> bytes | None:
    """Get cached source archive if it exists."""
    cache_file = Path(tempfile.gettempdir()) / f"arxiv_{arxiv_id}.tar"
    if cache_file.exists():
        return cache_file.read_bytes()
    return None


def _cache_source(arxiv_id: str, content: bytes) -> None:
    """Cache source archive for future use."""
    cache_file = Path(tempfile.gettempdir()) / f"arxiv_{arxiv_id}.tar"
    cache_file.write_bytes(content)


def _get_source_archive(arxiv_id: str) -> bytes:
    """Get source archive, using cache if available."""
    cached = _get_cached_source(arxiv_id)
    if cached:
        return cached
    url = f"https://arxiv.org/src/{arxiv_id}"
    with httpx.Client(follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        _cache_source(arxiv_id, response.content)
        return response.content


def _handle_source_content_structured(
    arxiv_id: str, content: bytes, format: str, output_path: str
) -> DownloadResult:
    """Handle source content, trying tar first, then single file."""
    try:
        # Try to handle as tar archive first (most common case)
        return _handle_tar_archive_structured(arxiv_id, content, format, output_path)
    except tarfile.TarError:
        # Not a tar archive, try as single gzipped file
        return _handle_single_file_structured(arxiv_id, content, format, output_path)


def _handle_source_content(
    arxiv_id: str, content: bytes, format: str, output_path: str
) -> str:
    """Handle source content, trying tar first, then single file."""
    try:
        # Try to handle as tar archive first (most common case)
        return _handle_tar_archive(arxiv_id, content, format, output_path)
    except tarfile.TarError:
        # Not a tar archive, try as single gzipped file
        return _handle_single_file(arxiv_id, content, format, output_path)


def _handle_single_file(
    arxiv_id: str, content: bytes, format: str, output_path: str
) -> str:
    """Handle a single gzipped file (not a tar archive)."""
    decompressed = gzip.decompress(content)

    if output_path == "-":
        return f"ArXiv source file for {arxiv_id}: single .tex file ({len(decompressed)} bytes)"
    else:
        os.makedirs(output_path, exist_ok=True)
        filename = f"{arxiv_id}.tex"  # Assume it's a tex file
        file_path = os.path.join(output_path, filename)
        with open(file_path, "wb") as f:
            f.write(decompressed)
        return f"ArXiv source saved to directory: {output_path}\\nFile: {filename}"


def _handle_tar_archive(
    arxiv_id: str, content: bytes, format: str, output_path: str
) -> str:
    """Handle a tar archive."""
    tar_stream = BytesIO(content)

    with tarfile.open(fileobj=tar_stream, mode="r:*") as tar:
        if output_path == "-":
            files = []
            for member in tar.getmembers():
                if member.isfile() and (
                    format != "tex"
                    or any(
                        member.name.endswith(ext) for ext in [".tex", ".bib", ".bbl"]
                    )
                ):
                    files.append(f"{member.name} ({member.size} bytes)")

            if format == "tex":
                return f"ArXiv LaTeX files for {arxiv_id}:\\n" + "\\n".join(files)
            else:
                return f"ArXiv source files for {arxiv_id}:\\n" + "\\n".join(files)
        else:
            os.makedirs(output_path, exist_ok=True)

            if format == "tex":
                extracted_files = []
                for member in tar.getmembers():
                    if member.isfile() and any(
                        member.name.endswith(ext) for ext in [".tex", ".bib", ".bbl"]
                    ):
                        # Use filter='data' for security to prevent path traversal attacks
                        tar.extract(member, path=output_path, filter="data")
                        extracted_files.append(member.name)
                return f'ArXiv LaTeX files saved to directory: {output_path}\\nFiles: {", ".join(extracted_files)}'
            else:
                # Use filter='data' for security to prevent path traversal attacks
                tar.extractall(path=output_path, filter="data")
                file_count = len([m for m in tar.getmembers() if m.isfile()])
                return f"ArXiv source saved to directory: {output_path} ({file_count} files)"


def _handle_single_file_structured(
    arxiv_id: str, content: bytes, format: str, output_path: str
) -> DownloadResult:
    """Handle a single gzipped file (not a tar archive)."""
    # Decompress the gzipped content
    decompressed = gzip.decompress(content)
    filename = f"{arxiv_id}.tex"  # Assume it's a tex file

    if output_path == "-":
        # Return file info for stdout
        return DownloadResult(
            message=f"ArXiv source file for {arxiv_id}: single .tex file",
            arxiv_id=arxiv_id,
            format=format,
            output_path=output_path,
            size_bytes=len(decompressed),
            files=[filename],
        )
    else:
        # Save to directory
        os.makedirs(output_path, exist_ok=True)
        file_path = os.path.join(output_path, filename)
        with open(file_path, "wb") as f:
            f.write(decompressed)
        return DownloadResult(
            message=f"ArXiv source saved to directory: {output_path}",
            arxiv_id=arxiv_id,
            format=format,
            output_path=output_path,
            size_bytes=len(decompressed),
            files=[filename],
        )


def _handle_tar_archive_structured(
    arxiv_id: str, content: bytes, format: str, output_path: str
) -> DownloadResult:
    """Handle a tar archive."""
    tar_stream = BytesIO(content)

    with tarfile.open(fileobj=tar_stream, mode="r:*") as tar:
        if output_path == "-":
            # List files for stdout
            files = []
            total_size = 0
            for member in tar.getmembers():
                if member.isfile() and (
                    format != "tex"
                    or any(
                        member.name.endswith(ext) for ext in [".tex", ".bib", ".bbl"]
                    )
                ):
                    files.append(member.name)
                    total_size += member.size

            message = (
                f"ArXiv {'LaTeX' if format == 'tex' else 'source'} files for {arxiv_id}"
            )
            return DownloadResult(
                message=message,
                arxiv_id=arxiv_id,
                format=format,
                output_path=output_path,
                size_bytes=total_size,
                files=files,
            )
        else:
            # Save to directory
            os.makedirs(output_path, exist_ok=True)
            extracted_files = []
            total_size = 0

            if format == "tex":
                # Extract .tex, .bib, .bbl files
                for member in tar.getmembers():
                    if member.isfile() and any(
                        member.name.endswith(ext) for ext in [".tex", ".bib", ".bbl"]
                    ):
                        tar.extract(member, path=output_path, filter="data")
                        extracted_files.append(member.name)
                        total_size += member.size
            else:
                # Extract all files (src format)
                tar.extractall(path=output_path, filter="data")
                for member in tar.getmembers():
                    if member.isfile():
                        extracted_files.append(member.name)
                        total_size += member.size

            return DownloadResult(
                message=f"ArXiv {'LaTeX' if format == 'tex' else 'source'} files saved to directory: {output_path}",
                arxiv_id=arxiv_id,
                format=format,
                output_path=output_path,
                size_bytes=total_size,
                files=extracted_files,
            )


@mcp.tool(
    description="Downloads an ArXiv paper by its ID in 'src', 'pdf', or 'tex' format. Saves content to `output_path` or lists file info to stdout if `output_path` is '-'. Returns a status message."
)
def download(
    arxiv_id: str, format: str = "src", output_path: str = ""
) -> DownloadResult:
    if format not in ["src", "pdf", "tex"]:
        raise ValueError(f"Invalid format '{format}'. Must be 'src', 'pdf', or 'tex'")

    if not output_path:
        output_path = f"{arxiv_id}.pdf" if format == "pdf" else arxiv_id

    if format == "pdf":
        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        with httpx.Client(follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        size_bytes = len(response.content)
        if output_path == "-":
            # Return file info for stdout
            return DownloadResult(
                message=f"ArXiv PDF for {arxiv_id}: {size_bytes / (1024 * 1024):.2f} MB",
                arxiv_id=arxiv_id,
                format=format,
                output_path=output_path,
                size_bytes=size_bytes,
                files=[f"{arxiv_id}.pdf"],
            )
        else:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return DownloadResult(
                message=f"ArXiv PDF saved to: {output_path}",
                arxiv_id=arxiv_id,
                format=format,
                output_path=output_path,
                size_bytes=size_bytes,
                files=[output_path],
            )

    else:
        content = _get_source_archive(arxiv_id)
        return _handle_source_content_structured(arxiv_id, content, format, output_path)


@mcp.tool(
    description="Lists the file names within an ArXiv paper's source archive. Use this to inspect contents before downloading. Returns a list of file paths."
)
def list_files(arxiv_id: str) -> list[str]:
    content = _get_source_archive(arxiv_id)

    try:
        tar_stream = BytesIO(content)
        filenames = []
        with tarfile.open(fileobj=tar_stream, mode="r:*") as tar:
            for member in tar.getmembers():
                if member.isfile():
                    filenames.append(member.name)
        return filenames
    except tarfile.TarError:
        # Not a valid tar, so try to handle as a single gzipped file
        gzip.decompress(content)
        return [f"{arxiv_id}.tex"]


def _parse_arxiv_entry(entry: ElementTree.Element) -> dict[str, Any]:
    """Parse a single ArXiv entry from the Atom feed."""
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    def find_text(path, default=""):
        elem = entry.find(path, ns)
        return elem.text.strip() if elem is not None and elem.text else default

    title = find_text("atom:title")
    summary = find_text("atom:summary")
    id_text = find_text("atom:id")
    arxiv_id = id_text.split("/")[-1].split("v")[0] if id_text else ""
    authors = [
        author.text
        for author in entry.findall("atom:author/atom:name", ns)
        if author.text
    ]

    published_text = find_text("atom:published")
    dt = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
    published_date = dt.strftime("%Y-%m-%d")

    categories = [
        cat.get("term") for cat in entry.findall("atom:category", ns) if cat.get("term")
    ]

    pdf_url = ""
    abs_url = ""
    for link in entry.findall("atom:link", ns):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
        elif link.get("rel") == "alternate":
            abs_url = link.get("href", "")

    return {
        "id": arxiv_id,
        "title": title,
        "authors": authors,
        "summary": summary,
        "published": published_date,
        "categories": categories,
        "pdf_url": pdf_url,
        "abs_url": abs_url,
    }


@mcp.tool(
    description="Searches ArXiv for papers matching a query. Supports advanced syntax like field prefixes (e.g., 'au:Hinton', 'ti:attention') and boolean operators ('AND', 'OR'). Results can be sorted by relevance or date. Returns a list of papers, each containing metadata like title, authors, and summary."
)
def search(
    query: str,
    max_results: int = 10,
    start: int = 0,
    sort_by: str = "relevance",
    sort_order: str = "descending",
) -> list[dict[str, Any]]:
    if max_results > 100:
        max_results = 100

    base_url = "http://export.arxiv.org/api/query"
    encoded_query = quote_plus(query)

    params = {
        "search_query": encoded_query,
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }

    param_str = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"{base_url}?{param_str}"

    with httpx.Client(follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    root = ElementTree.fromstring(response.content)

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    }

    results = []
    for entry in root.findall("atom:entry", ns):
        paper_dict = _parse_arxiv_entry(entry)
        results.append(ArxivPaper(**paper_dict))

    return results


@mcp.tool(
    description="Checks ArXiv tool status and lists available functions. Use this to discover server capabilities."
)
def server_info() -> ServerInfo:
    return ServerInfo(
        name="ArXiv Tool",
        version="1.0.0",
        status="active",
        capabilities=[
            "search - Search ArXiv papers using official API with advanced query syntax",
            "download - Download ArXiv papers in src/pdf/tex format",
            "list_files - List files in ArXiv source archive",
            "server_info - Get server information",
        ],
        dependencies={
            "httpx": "latest",
            "pydantic": "latest",
            "supported_formats": "src,pdf,tex",
            "caching": "Source archives cached in /tmp for performance",
            "tex_format_includes": ".tex,.bib,.bbl",
        },
    )
