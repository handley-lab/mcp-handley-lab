"""ArXiv source code retrieval MCP server."""

import gzip
import os
import tarfile
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal
from xml.etree import ElementTree

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_handley_lab.shared.models import ServerInfo


class DownloadResult(BaseModel):
    """Result of downloading an ArXiv paper."""

    message: str = Field(
        ...,
        description="A summary message describing the result of the download operation.",
    )
    arxiv_id: str = Field(
        ..., description="The ArXiv ID of the paper that was downloaded."
    )
    format: str = Field(
        ...,
        description="The format of the downloaded content (e.g., 'src', 'pdf', 'tex').",
    )
    output_path: str = Field(
        ...,
        description="The path where the content was saved, or '-' if printed to stdout.",
    )
    size_bytes: int = Field(
        ..., description="The total size of the downloaded content in bytes."
    )
    files: list[str] = Field(
        default_factory=list,
        description="A list of file names included in the downloaded archive.",
    )


class ArxivPaper(BaseModel):
    """
    ArXiv paper metadata.
    Fields may be omitted or truncated depending on the parameters used in the search tool.
    """

    id: str = Field(..., description="The ArXiv ID of the paper (e.g., '2301.07041').")
    title: str | None = Field(default=None, description="The title of the paper.")
    authors: list[str] | None = Field(
        default=None, description="List of authors' names. May be truncated."
    )
    summary: str | None = Field(
        default=None, description="Abstract or summary of the paper. May be truncated."
    )
    published: str | None = Field(
        default=None, description="Publication date in YYYY-MM-DD format."
    )
    categories: list[str] | None = Field(
        default=None, description="ArXiv subject categories (e.g., ['cs.AI', 'cs.LG'])."
    )
    pdf_url: str | None = Field(
        default=None, description="Direct URL to download the PDF version."
    )
    abs_url: str | None = Field(
        default=None, description="URL to the ArXiv abstract page."
    )


mcp = FastMCP("ArXiv Tool")


def _get_cached_source(arxiv_id: str) -> bytes | None:
    """Get cached source archive if it exists."""
    cache_file = Path(tempfile.gettempdir()) / f"arxiv_{arxiv_id}.tar"
    try:
        return cache_file.read_bytes()
    except FileNotFoundError:
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
    description="Downloads an ArXiv paper by its ID or lists its source files. Formats: 'src' (all source), 'pdf', 'tex' (LaTeX files only). To list source files without saving, set format to 'src' and output_path to '-'. Returns structured operation result."
)
def download(
    arxiv_id: str = Field(
        ...,
        description="The unique ArXiv identifier for the paper (e.g., '2301.07041').",
    ),
    format: str = Field(
        "src",
        description="The format of the paper to download. Valid options are 'src', 'pdf', or 'tex'.",
    ),
    output_path: str = Field(
        "",
        description="Path to save the content. For 'pdf' format: saves as a single file. For 'src' and 'tex' formats: creates a directory with this name and extracts files into it. If empty, defaults to '<arxiv_id>.pdf' for pdf or '<arxiv_id>' for source formats. Use '-' to list file info to stdout instead of saving.",
    ),
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


def _parse_arxiv_entry(entry: ElementTree.Element) -> dict[str, Any]:
    """Parse a single ArXiv entry from the Atom feed."""
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    def find_text(path, default=""):
        elem = entry.find(path, ns)
        return (
            elem.text.strip().replace("\n", " ")
            if elem is not None and elem.text
            else default
        )

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


def _apply_field_filtering(
    paper_dict: dict[str, Any],
    include_fields: list[str] | None,
) -> dict[str, Any]:
    """
    Apply field filtering to a paper dictionary.

    If include_fields is None, returns all fields.
    If include_fields is provided, returns only those fields (plus 'id' which is always included).
    """
    if include_fields is None:
        # Return all fields
        return paper_dict

    # Use specified fields, ensuring 'id' is always included
    included_fields = set(include_fields)
    included_fields.add("id")

    # Filter the paper dictionary
    return {k: v for k, v in paper_dict.items() if k in included_fields}


@mcp.tool(
    description="Searches ArXiv for papers. Supports advanced syntax (e.g., 'au:Hinton', 'ti:attention'). Use include_fields to limit output for context window management."
)
def search(
    query: str = Field(
        ...,
        description="The search query. Supports field prefixes (au, ti, abs, co) and boolean operators (AND, OR, ANDNOT).",
    ),
    max_results: int = Field(
        50,
        description="The maximum number of results to return.",
    ),
    start: int = Field(
        0, description="The starting index for the search results, used for pagination."
    ),
    sort_by: Literal["relevance", "lastUpdatedDate", "submittedDate"] = Field(
        "relevance",
        description="Sorting criteria. Options: 'relevance', 'lastUpdatedDate', 'submittedDate'.",
    ),
    sort_order: Literal["ascending", "descending"] = Field(
        "descending",
        description="Sorting order. Options: 'ascending' or 'descending'.",
    ),
    include_fields: list[
        Literal[
            "id",
            "title",
            "authors",
            "summary",
            "published",
            "categories",
            "pdf_url",
            "abs_url",
        ]
    ]
    | None = Field(
        None,
        description="Specific fields to include in results. If not provided, all fields are included. Available: id, title, authors, summary, published, categories, pdf_url, abs_url.",
    ),
    max_authors: int | None = Field(
        5,
        ge=1,
        description="Max authors to return per paper. If more, a summary is added. Set to null for no limit.",
    ),
    max_summary_len: int | None = Field(
        1000,
        ge=1,
        description="Max summary length (characters). Truncates with '...'. Set to null for no limit.",
    ),
) -> list[ArxivPaper]:
    """
    Searches ArXiv and returns a list of papers with configurable output limiting.
    """
    base_url = "http://export.arxiv.org/api/query"

    params = {
        "search_query": query,  # httpx handles encoding
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }

    try:
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(base_url, params=params)
            response.raise_for_status()
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError:
        raise ValueError(
            "Failed to parse response from ArXiv API. The service may be down or returning invalid data."
        ) from None
    except httpx.HTTPStatusError as e:
        raise ConnectionError(
            f"ArXiv API error: {e.response.status_code} - {e.response.text}"
        ) from e
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    results = []
    for entry in root.findall("atom:entry", ns):
        paper_dict = _parse_arxiv_entry(entry)

        # Apply field-specific limits (truncation)
        if (
            paper_dict["authors"]
            and max_authors is not None
            and len(paper_dict["authors"]) > max_authors
        ):
            num_remaining = len(paper_dict["authors"]) - max_authors
            paper_dict["authors"] = paper_dict["authors"][:max_authors]
            paper_dict["authors"].append(f"... and {num_remaining} more")

        if (
            paper_dict["summary"]
            and max_summary_len is not None
            and len(paper_dict["summary"]) > max_summary_len
        ):
            end = paper_dict["summary"].rfind(" ", 0, max_summary_len)
            paper_dict["summary"] = (
                paper_dict["summary"][: end if end != -1 else max_summary_len] + "..."
            )

        # Apply field filtering
        final_paper_dict = _apply_field_filtering(paper_dict, include_fields)

        results.append(ArxivPaper(**final_paper_dict))

    return results


@mcp.tool(
    description="Checks ArXiv tool status and lists available functions. Use this to discover server capabilities."
)
def server_info() -> ServerInfo:
    return ServerInfo(
        name="ArXiv Tool",
        version="1.0.0",
        status="active",
        capabilities=["search", "download", "server_info"],
        dependencies={
            "httpx": "latest",
            "pydantic": "latest",
            "supported_formats": "src,pdf,tex",
        },
    )
