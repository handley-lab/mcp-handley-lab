"""ArXiv source code retrieval MCP server."""

import asyncio
import gzip
import os
import tarfile
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import httpx
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

async def _get_source_archive(arxiv_id: str) -> bytes:
    """Get source archive, using cache if available."""
    # Check cache first
    cached = _get_cached_source(arxiv_id)
    if cached:
        return cached

    # Download and cache
    url = f'https://arxiv.org/src/{arxiv_id}'
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            _cache_source(arxiv_id, response.content)
            return response.content
    except Exception as e:
        raise RuntimeError(f'Error fetching ArXiv data: {e}')

def _is_tar_archive(content: bytes) -> bool:
    """Check if content is a tar archive or a single gzipped file."""
    try:
        # Try to open as tar archive
        with tarfile.open(fileobj=BytesIO(content), mode='r:*'):
            return True
    except tarfile.TarError:
        return False

def _handle_source_content(arxiv_id: str, content: bytes, format: str, output_path: str) -> str:
    """Handle source content, whether it's a tar archive or single file."""
    if _is_tar_archive(content):
        return _handle_tar_archive(arxiv_id, content, format, output_path)
    else:
        return _handle_single_file(arxiv_id, content, format, output_path)

def _handle_single_file(arxiv_id: str, content: bytes, format: str, output_path: str) -> str:
    """Handle a single gzipped file (not a tar archive)."""
    try:
        # Decompress the gzipped content
        decompressed = gzip.decompress(content)

        if output_path == '-':
            # Return file info for stdout
            return f'ArXiv source file for {arxiv_id}: single .tex file ({len(decompressed)} bytes)'
        else:
            # Save to directory
            os.makedirs(output_path, exist_ok=True)
            filename = f'{arxiv_id}.tex'  # Assume it's a tex file
            file_path = os.path.join(output_path, filename)
            with open(file_path, 'wb') as f:
                f.write(decompressed)
            return f'ArXiv source saved to directory: {output_path}\\nFile: {filename}'
    except Exception as e:
        raise ValueError(f'Error processing single file: {e}')

def _handle_tar_archive(arxiv_id: str, content: bytes, format: str, output_path: str) -> str:
    """Handle a tar archive."""
    tar_stream = BytesIO(content)

    try:
        with tarfile.open(fileobj=tar_stream, mode='r:*') as tar:
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
async def download(arxiv_id: str, format: str = 'src', output_path: str = None) -> str:
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
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url)
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
        content = await _get_source_archive(arxiv_id)
        return _handle_source_content(arxiv_id, content, format, output_path)

@mcp.tool()
async def list_files(arxiv_id: str) -> list[str]:
    """
    List all files in an ArXiv source archive.
    
    Args:
        arxiv_id: ArXiv paper ID (e.g., "2301.07041")
    
    Returns:
        List of filenames in the archive
    """
    content = await _get_source_archive(arxiv_id)

    if _is_tar_archive(content):
        # Handle tar archive
        tar_stream = BytesIO(content)
        filenames = []
        try:
            with tarfile.open(fileobj=tar_stream, mode='r:*') as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        filenames.append(member.name)
        except tarfile.TarError as e:
            raise ValueError(f'Error reading tar archive: {e}')
        return filenames
    else:
        # Handle single gzipped file
        return [f'{arxiv_id}.tex']  # Single tex file


def _parse_arxiv_entry(entry: ET.Element) -> Dict[str, Any]:
    """Parse a single ArXiv entry from the Atom feed."""
    # Define namespaces
    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'arxiv': 'http://arxiv.org/schemas/atom'
    }
    
    # Extract basic information
    title = entry.find('atom:title', ns).text.strip() if entry.find('atom:title', ns) is not None else ""
    summary = entry.find('atom:summary', ns).text.strip() if entry.find('atom:summary', ns) is not None else ""
    
    # Extract ArXiv ID from the ID field
    id_elem = entry.find('atom:id', ns)
    arxiv_id = ""
    if id_elem is not None:
        # Extract ID from URL like "http://arxiv.org/abs/2301.07041v1"
        arxiv_id = id_elem.text.split('/')[-1].replace('v1', '').replace('v2', '').replace('v3', '')
    
    # Extract authors
    authors = []
    for author in entry.findall('atom:author', ns):
        name_elem = author.find('atom:name', ns)
        if name_elem is not None:
            authors.append(name_elem.text)
    
    # Extract published date
    published = entry.find('atom:published', ns)
    published_date = ""
    if published is not None:
        try:
            # Parse ISO format date
            dt = datetime.fromisoformat(published.text.replace('Z', '+00:00'))
            published_date = dt.strftime('%Y-%m-%d')
        except:
            published_date = published.text
    
    # Extract categories
    categories = []
    for category in entry.findall('atom:category', ns):
        term = category.get('term')
        if term:
            categories.append(term)
    
    # Extract links
    pdf_url = ""
    abs_url = ""
    for link in entry.findall('atom:link', ns):
        if link.get('title') == 'pdf':
            pdf_url = link.get('href', '')
        elif link.get('rel') == 'alternate':
            abs_url = link.get('href', '')
    
    return {
        'id': arxiv_id,
        'title': title,
        'authors': authors,
        'summary': summary,
        'published': published_date,
        'categories': categories,
        'pdf_url': pdf_url,
        'abs_url': abs_url
    }


@mcp.tool()
def search(
    query: str,
    max_results: int = 10,
    start: int = 0,
    sort_by: str = 'relevance',
    sort_order: str = 'descending'
) -> List[Dict[str, Any]]:
    """
    Search ArXiv papers using the official ArXiv API.
    
    Args:
        query: Search query string. Supports field prefixes like 'ti:' (title), 'au:' (author), 
               'abs:' (abstract), 'cat:' (category), 'all:' (all fields). 
               Boolean operators: AND, OR, NOT. Example: 'ti:transformer AND cat:cs.AI'
        max_results: Maximum number of results to return (default: 10, max: 100)
        start: Starting index for pagination (default: 0)
        sort_by: Sort criterion - 'relevance', 'lastUpdatedDate', 'submittedDate' (default: 'relevance')
        sort_order: Sort order - 'ascending', 'descending' (default: 'descending')
    
    Returns:
        List of paper dictionaries with id, title, authors, summary, published date, categories, and URLs
    """
    if max_results > 100:
        max_results = 100
    
    # Construct API URL
    base_url = "http://export.arxiv.org/api/query"
    encoded_query = quote_plus(query)
    
    params = {
        'search_query': encoded_query,
        'start': start,
        'max_results': max_results,
        'sortBy': sort_by,
        'sortOrder': sort_order
    }
    
    # Build URL with parameters
    param_str = '&'.join([f'{k}={v}' for k, v in params.items()])
    url = f"{base_url}?{param_str}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as e:
        raise RuntimeError(f'Error fetching ArXiv search results: {e}')
    
    # Parse XML response
    try:
        root = ET.fromstring(response.content)
        
        # Define namespaces
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'opensearch': 'http://a9.com/-/spec/opensearch/1.1/'
        }
        
        # Extract search results
        results = []
        for entry in root.findall('atom:entry', ns):
            try:
                paper = _parse_arxiv_entry(entry)
                results.append(paper)
            except Exception as e:
                # Skip entries that can't be parsed
                continue
        
        return results
        
    except ET.ParseError as e:
        raise ValueError(f'Error parsing ArXiv API response: {e}')


@mcp.tool()
async def server_info() -> dict[str, Any]:
    """
    Get information about the ArXiv tool server.
    
    Returns:
        Server information including available functions
    """
    return {
        "name": "ArXiv Tool",
        "description": "Tool for searching and downloading ArXiv papers",
        "functions": [
            "search - Search ArXiv papers using official API with advanced query syntax",
            "download - Download ArXiv papers in src/pdf/tex format",
            "list_files - List files in ArXiv source archive",
            "server_info - Get server information"
        ],
        "supported_formats": ["src", "pdf", "tex"],
        "search_features": {
            "field_prefixes": ["ti:", "au:", "abs:", "cat:", "all:"],
            "boolean_operators": ["AND", "OR", "NOT"],
            "sort_options": ["relevance", "lastUpdatedDate", "submittedDate"],
            "max_results": 100
        },
        "example_usage": {
            "search_basic": "search('machine learning')",
            "search_advanced": "search('ti:transformer AND cat:cs.AI', max_results=20)",
            "search_author": "search('au:Hinton', sort_by='submittedDate')",
            "download_src": "download('2301.07041', format='src')",
            "download_pdf": "download('2301.07041', format='pdf')",
            "download_tex": "download('2301.07041', format='tex')",
            "download_to_stdout": "download('2301.07041', output_path='-')",
            "list": "list_files('2301.07041')"
        },
        "caching": "Source archives cached in /tmp for performance",
        "tex_format_includes": [".tex", ".bib", ".bbl"]
    }

