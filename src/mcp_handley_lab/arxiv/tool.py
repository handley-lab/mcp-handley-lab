"""ArXiv source code retrieval MCP server."""

import os
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

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
    # Check cache first
    cached = _get_cached_source(arxiv_id)
    if cached:
        return cached

    # Download and cache
    url = f'https://arxiv.org/src/{arxiv_id}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        _cache_source(arxiv_id, response.content)
        return response.content
    except Exception as e:
        raise RuntimeError(f'Error fetching ArXiv data: {e}')

@mcp.tool()
def download(arxiv_id: str, format: str = 'src', output_path: str = None) -> str:
    """
    Download ArXiv paper in specified format.
    
    Args:
        arxiv_id: ArXiv paper ID (e.g., "2301.07041")
        format: Download format - 'src' (source archive), 'pdf' (PDF file), or 'tex' (LaTeX files only)
        output_path: Output path ('-' for stdout listing, defaults to arxiv_id/arxiv_id.pdf)
    
    Returns:
        Download status and file information
    """
    if format not in ['src', 'pdf', 'tex']:
        raise ValueError(f"Invalid format '{format}'. Must be 'src', 'pdf', or 'tex'")

    # Determine default output path
    if output_path is None:
        if format == 'pdf':
            output_path = f'{arxiv_id}.pdf'
        else:
            output_path = arxiv_id

    if format == 'pdf':
        url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'

        try:
            response = requests.get(url)
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f'Error fetching ArXiv PDF: {e}')

        if output_path == '-':
            # Return file info for stdout
            size_mb = len(response.content) / (1024 * 1024)
            return f'ArXiv PDF for {arxiv_id}: {size_mb:.2f} MB\\nUse output_path to save to file'
        else:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            size_mb = len(response.content) / (1024 * 1024)
            return f'ArXiv PDF saved to: {output_path} ({size_mb:.2f} MB)'

    else:  # src or tex format
        content = _get_source_archive(arxiv_id)
        tar_stream = BytesIO(content)

        try:
            with tarfile.open(fileobj=tar_stream, mode='r') as tar:
                if output_path == '-':
                    # List files for stdout
                    files = []
                    for member in tar.getmembers():
                        if member.isfile():
                            if format == 'tex':
                                # Include .tex, .bib, .bbl files for tex format
                                if not any(member.name.endswith(ext) for ext in ['.tex', '.bib', '.bbl']):
                                    continue
                            files.append(f'{member.name} ({member.size} bytes)')

                    if format == 'tex':
                        return f'ArXiv LaTeX files for {arxiv_id}:\\n' + '\\n'.join(files)
                    else:
                        return f'ArXiv source files for {arxiv_id}:\\n' + '\\n'.join(files)
                else:
                    # Save to directory
                    os.makedirs(output_path, exist_ok=True)

                    if format == 'tex':
                        # Extract .tex, .bib, .bbl files
                        extracted_files = []
                        for member in tar.getmembers():
                            if member.isfile() and any(member.name.endswith(ext) for ext in ['.tex', '.bib', '.bbl']):
                                tar.extract(member, path=output_path, filter='data')
                                extracted_files.append(member.name)
                        return f'ArXiv LaTeX files saved to directory: {output_path}\\nFiles: {", ".join(extracted_files)}'
                    else:
                        # Extract all files (src format)
                        tar.extractall(path=output_path, filter='data')
                        file_count = len([m for m in tar.getmembers() if m.isfile()])
                        return f'ArXiv source saved to directory: {output_path} ({file_count} files)'
        except tarfile.TarError as e:
            raise ValueError(f'Error extracting tar archive: {e}')

@mcp.tool()
def list_files(arxiv_id: str) -> list[str]:
    """
    List all files in an ArXiv source archive.
    
    Args:
        arxiv_id: ArXiv paper ID (e.g., "2301.07041")
    
    Returns:
        List of filenames in the archive
    """
    content = _get_source_archive(arxiv_id)
    tar_stream = BytesIO(content)
    filenames = []

    try:
        with tarfile.open(fileobj=tar_stream, mode='r') as tar:
            for member in tar.getmembers():
                if member.isfile():
                    filenames.append(member.name)
    except tarfile.TarError as e:
        raise ValueError(f'Error reading tar archive: {e}')

    return filenames


@mcp.tool()
def server_info() -> dict[str, Any]:
    """
    Get information about the ArXiv tool server.
    
    Returns:
        Server information including available functions
    """
    return {
        "name": "ArXiv Tool",
        "version": "2.0.0",
        "description": "Tool for downloading ArXiv papers in multiple formats",
        "functions": [
            "download - Download ArXiv papers in src/pdf/tex format",
            "list_files - List files in ArXiv source archive",
            "server_info - Get server information"
        ],
        "supported_formats": ["src", "pdf", "tex"],
        "example_usage": {
            "download_src": "download('2301.07041', format='src')",
            "download_pdf": "download('2301.07041', format='pdf')",
            "download_tex": "download('2301.07041', format='tex')",
            "download_to_stdout": "download('2301.07041', output_path='-')",
            "list": "list_files('2301.07041')"
        },
        "caching": "Source archives cached in /tmp for performance",
        "tex_format_includes": [".tex", ".bib", ".bbl"]
    }

def main():
    """Run the ArXiv MCP server."""
    mcp.run()

if __name__ == "__main__":
    main()
