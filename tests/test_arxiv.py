"""Tests for ArXiv tool."""

import gzip
import os
import tarfile
import tempfile
from io import BytesIO
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcp_handley_lab.arxiv.tool import download, list_files, search, server_info


def create_mock_tar_archive():
    """Create a mock tar archive with test files."""
    # Create a tar archive in memory
    tar_buffer = BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode='w') as tar:
        # Add a tex file
        tex_info = tarfile.TarInfo('paper.tex')
        tex_content = b'\\documentclass{article}\n\\begin{document}\nHello ArXiv!\n\\end{document}'
        tex_info.size = len(tex_content)
        tar.addfile(tex_info, BytesIO(tex_content))

        # Add a bib file
        bib_info = tarfile.TarInfo('references.bib')
        bib_content = b'@article{example2024,\n  title={Example Paper},\n  author={Author}\n}'
        bib_info.size = len(bib_content)
        tar.addfile(bib_info, BytesIO(bib_content))

        # Add a bbl file
        bbl_info = tarfile.TarInfo('paper.bbl')
        bbl_content = b'\\begin{thebibliography}{1}\n\\bibitem{example} Example reference\n\\end{thebibliography}'
        bbl_info.size = len(bbl_content)
        tar.addfile(bbl_info, BytesIO(bbl_content))

        # Add a non-text file
        img_info = tarfile.TarInfo('figure.png')
        img_content = b'\x89PNG\x0d\x0a'  # PNG header
        img_info.size = len(img_content)
        tar.addfile(img_info, BytesIO(img_content))

    tar_buffer.seek(0)
    return tar_buffer.getvalue()


def create_mock_pdf():
    """Create a mock PDF content."""
    return b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n%%EOF'


class TestArxivTool:
    """Test cases for ArXiv tool functions."""

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    async def test_download_src_format(self, mock_get_source):
        """Test downloading source format."""
        mock_get_source.return_value = create_mock_tar_archive()

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, 'test_paper')
            result = await download('2301.07041', format='src', output_path=save_path)

            assert 'ArXiv source saved to directory:' in result
            assert save_path in result
            assert '4 files' in result

            # Verify files were extracted
            assert os.path.exists(save_path)
            assert os.path.exists(os.path.join(save_path, 'paper.tex'))
            assert os.path.exists(os.path.join(save_path, 'references.bib'))

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    async def test_download_tex_format(self, mock_get_source):
        """Test downloading tex format (tex, bib, bbl only)."""
        mock_get_source.return_value = create_mock_tar_archive()

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, 'test_paper')
            result = await download('2301.07041', format='tex', output_path=save_path)

            assert 'ArXiv LaTeX files saved to directory:' in result
            assert save_path in result
            assert 'paper.tex' in result
            assert 'references.bib' in result
            assert 'paper.bbl' in result

            # Verify only tex/bib/bbl files were extracted
            assert os.path.exists(save_path)
            assert os.path.exists(os.path.join(save_path, 'paper.tex'))
            assert os.path.exists(os.path.join(save_path, 'references.bib'))
            assert os.path.exists(os.path.join(save_path, 'paper.bbl'))
            assert not os.path.exists(os.path.join(save_path, 'figure.png'))

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool.httpx.AsyncClient')
    async def test_download_pdf_format(self, mock_client):
        """Test downloading PDF format."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = create_mock_pdf()
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, 'test.pdf')
            result = await download('2301.07041', format='pdf', output_path=save_path)

            assert 'ArXiv PDF saved to:' in result
            assert save_path in result
            assert 'MB' in result

            # Verify PDF was saved
            assert os.path.exists(save_path)
            with open(save_path, 'rb') as f:
                content = f.read()
                assert content.startswith(b'%PDF')

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    async def test_download_src_stdout(self, mock_get_source):
        """Test downloading with stdout output."""
        mock_get_source.return_value = create_mock_tar_archive()

        result = await download('2301.07041', format='src', output_path='-')

        assert 'ArXiv source files for 2301.07041:' in result
        assert 'paper.tex' in result
        assert 'references.bib' in result
        assert 'figure.png' in result
        assert 'bytes' in result

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    async def test_download_tex_stdout(self, mock_get_source):
        """Test downloading tex format with stdout output."""
        mock_get_source.return_value = create_mock_tar_archive()

        result = await download('2301.07041', format='tex', output_path='-')

        assert 'ArXiv LaTeX files for 2301.07041:' in result
        assert 'paper.tex' in result
        assert 'references.bib' in result
        assert 'paper.bbl' in result
        # Should not include non-tex files
        assert 'figure.png' not in result

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool.httpx.AsyncClient')
    async def test_download_pdf_stdout(self, mock_client):
        """Test downloading PDF with stdout output."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = create_mock_pdf()
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        result = await download('2301.07041', format='pdf', output_path='-')

        assert 'ArXiv PDF for 2301.07041:' in result
        assert 'MB' in result
        assert 'Use output_path to save to file' in result

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    async def test_download_default_output_path(self, mock_get_source):
        """Test download with default output path."""
        mock_get_source.return_value = create_mock_tar_archive()

        with tempfile.TemporaryDirectory():
            original_cwd = os.getcwd()
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                try:
                    result = await download('2301.07041', format='src')
                    assert 'ArXiv source saved to directory: 2301.07041' in result
                    assert os.path.exists('2301.07041')
                finally:
                    os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_download_invalid_format(self):
        """Test download with invalid format."""
        with pytest.raises(ValueError, match="Invalid format 'invalid'"):
            await download('2301.07041', format='invalid')

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool.httpx.AsyncClient')
    async def test_download_network_error(self, mock_client):
        """Test download with network error."""
        mock_client_instance = AsyncMock()
        mock_client_instance.get.side_effect = Exception('Network error')
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        with pytest.raises(RuntimeError, match='Error fetching ArXiv'):
            await download('2301.07041', format='pdf')

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    async def test_list_files_success(self, mock_get_source):
        """Test successful file listing."""
        mock_get_source.return_value = create_mock_tar_archive()

        files = await list_files('2301.07041')

        assert isinstance(files, list)
        assert 'paper.tex' in files
        assert 'references.bib' in files
        assert 'paper.bbl' in files
        assert 'figure.png' in files
        assert len(files) == 4

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    async def test_list_files_network_error(self, mock_get_source):
        """Test file listing with network error."""
        mock_get_source.side_effect = RuntimeError('Error fetching ArXiv data: Network error')

        with pytest.raises(RuntimeError, match='Error fetching ArXiv data'):
            await list_files('2301.07041')

    @pytest.mark.asyncio
    async def test_server_info(self):
        """Test server info function."""
        info = await server_info()

        assert info['name'] == 'ArXiv Tool'
        assert 'description' in info
        assert 'functions' in info
        assert isinstance(info['functions'], list)
        assert len(info['functions']) == 4  # search, download, list_files, server_info
        assert 'supported_formats' in info
        assert 'src' in info['supported_formats']
        assert 'pdf' in info['supported_formats']
        assert 'tex' in info['supported_formats']
        assert 'example_usage' in info
        assert 'caching' in info
        assert 'tex_format_includes' in info
        assert '.tex' in info['tex_format_includes']
        assert '.bib' in info['tex_format_includes']
        assert '.bbl' in info['tex_format_includes']
        assert 'search_features' in info
        assert 'field_prefixes' in info['search_features']
        assert 'ti:' in info['search_features']['field_prefixes']


class TestArxivSearch:
    """Test cases for ArXiv search functionality."""

    def create_mock_search_response(self):
        """Create a mock XML response from ArXiv API."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <link href="http://arxiv.org/api/query?search_query=all:electron&amp;id_list=&amp;start=0&amp;max_results=2" rel="self" type="application/atom+xml"/>
  <title type="html">ArXiv Query: search_query=all:electron&amp;id_list=&amp;start=0&amp;max_results=2</title>
  <id>http://arxiv.org/api/query?search_query=all:electron&amp;id_list=&amp;start=0&amp;max_results=2</id>
  <updated>2024-06-25T00:00:00-04:00</updated>
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">2</opensearch:totalResults>
  <opensearch:startIndex xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:startIndex>
  <opensearch:itemsPerPage xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">2</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2301.07041v1</id>
    <updated>2023-01-17T18:39:18Z</updated>
    <published>2023-01-17T18:39:18Z</published>
    <title>Test Paper on Electrons</title>
    <summary>This is a test paper about electrons and their properties.</summary>
    <author>
      <name>John Doe</name>
    </author>
    <author>
      <name>Jane Smith</name>
    </author>
    <arxiv:doi xmlns:arxiv="http://arxiv.org/schemas/atom">10.1000/182</arxiv:doi>
    <link title="doi" href="http://dx.doi.org/10.1000/182" rel="related"/>
    <arxiv:comment xmlns:arxiv="http://arxiv.org/schemas/atom">5 pages, 2 figures</arxiv:comment>
    <arxiv:journal_ref xmlns:arxiv="http://arxiv.org/schemas/atom">Phys. Rev. A 1, 1 (2023)</arxiv:journal_ref>
    <link href="http://arxiv.org/abs/2301.07041v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2301.07041v1.pdf" rel="related" type="application/pdf"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="physics.atom-ph" scheme="http://arxiv.org/schemas/atom"/>
    <category term="physics.atom-ph" scheme="http://arxiv.org/schemas/atom"/>
    <category term="quant-ph" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2301.07042v1</id>
    <updated>2023-01-17T18:40:00Z</updated>
    <published>2023-01-17T18:40:00Z</published>
    <title>Another Electron Study</title>
    <summary>This paper studies electron behavior in quantum systems.</summary>
    <author>
      <name>Alice Johnson</name>
    </author>
    <link href="http://arxiv.org/abs/2301.07042v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2301.07042v1.pdf" rel="related" type="application/pdf"/>
    <arxiv:primary_category xmlns:arxiv="http://arxiv.org/schemas/atom" term="quant-ph" scheme="http://arxiv.org/schemas/atom"/>
    <category term="quant-ph" scheme="http://arxiv.org/schemas/atom"/>
  </entry>
</feed>"""

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    def test_search_basic(self, mock_get):
        """Test basic search functionality."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = self.create_mock_search_response().encode()
        mock_get.return_value = mock_response

        results = search('electron')

        assert len(results) == 2
        assert results[0]['id'] == '2301.07041'
        assert results[0]['title'] == 'Test Paper on Electrons'
        assert 'John Doe' in results[0]['authors']
        assert 'Jane Smith' in results[0]['authors']
        assert results[0]['published'] == '2023-01-17'
        assert 'physics.atom-ph' in results[0]['categories']
        assert 'quant-ph' in results[0]['categories']
        assert results[0]['pdf_url'] == 'http://arxiv.org/pdf/2301.07041v1.pdf'
        assert results[0]['abs_url'] == 'http://arxiv.org/abs/2301.07041v1'

        assert results[1]['id'] == '2301.07042'
        assert results[1]['title'] == 'Another Electron Study'
        assert 'Alice Johnson' in results[1]['authors']

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    def test_search_with_parameters(self, mock_get):
        """Test search with custom parameters."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = self.create_mock_search_response().encode()
        mock_get.return_value = mock_response

        results = search('ti:transformer AND cat:cs.AI', max_results=5, start=10, sort_by='submittedDate')

        # Check that request was made with correct parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0][0]
        assert 'search_query=ti%3Atransformer+AND+cat%3Acs.AI' in call_args
        assert 'max_results=5' in call_args
        assert 'start=10' in call_args
        assert 'sortBy=submittedDate' in call_args

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    def test_search_max_results_limit(self, mock_get):
        """Test that max_results is capped at 100."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = self.create_mock_search_response().encode()
        mock_get.return_value = mock_response

        search('electron', max_results=150)

        call_args = mock_get.call_args[0][0]
        assert 'max_results=100' in call_args

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    def test_search_network_error(self, mock_get):
        """Test search with network error."""
        mock_get.side_effect = Exception('Network error')

        with pytest.raises(RuntimeError, match='Error fetching ArXiv search results'):
            search('electron')

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    def test_search_invalid_xml(self, mock_get):
        """Test search with invalid XML response."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = b'invalid xml content'
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match='Error parsing ArXiv API response'):
            search('electron')

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    def test_search_empty_results(self, mock_get):
        """Test search with no results."""
        empty_response = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title type="html">ArXiv Query: search_query=nonexistent&amp;start=0&amp;max_results=10</title>
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">0</opensearch:totalResults>
</feed>"""
        
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = empty_response.encode()
        mock_get.return_value = mock_response

        results = search('nonexistent')
        assert len(results) == 0

    def test_parse_arxiv_entry_missing_fields(self):
        """Test parsing entry with missing optional fields."""
        from mcp_handley_lab.arxiv.tool import _parse_arxiv_entry
        from xml.etree import ElementTree as ET

        # Create minimal entry
        minimal_entry = """<entry xmlns="http://www.w3.org/2005/Atom">
    <id>http://arxiv.org/abs/2301.07041v1</id>
    <title>Minimal Entry</title>
    <summary>Basic summary</summary>
</entry>"""
        
        entry_elem = ET.fromstring(minimal_entry)
        result = _parse_arxiv_entry(entry_elem)

        assert result['id'] == '2301.07041'
        assert result['title'] == 'Minimal Entry'
        assert result['summary'] == 'Basic summary'
        assert result['authors'] == []
        assert result['categories'] == []
        assert result['pdf_url'] == ''
        assert result['abs_url'] == ''


    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    async def test_download_single_file_to_disk(self, mock_get_source):
        """Test downloading single gzipped file to disk."""
        # Mock single gzipped file content
        tex_content = b'\\documentclass{article}\\nTest content'
        gzipped_content = gzip.compress(tex_content)
        mock_get_source.return_value = gzipped_content

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, 'test_paper')
            result = await download('0704.0005', format='src', output_path=save_path)

            assert 'ArXiv source saved to directory:' in result
            assert save_path in result
            assert 'File: 0704.0005.tex' in result

            # Verify file was saved
            assert os.path.exists(save_path)
            saved_file = os.path.join(save_path, '0704.0005.tex')
            assert os.path.exists(saved_file)
            with open(saved_file, 'rb') as f:
                assert f.read() == tex_content

    def test_tar_archive_extraction_error(self):
        """Test tar archive extraction error handling."""
        from mcp_handley_lab.arxiv.tool import _handle_tar_archive

        # Use corrupted tar data
        corrupted_data = b'corrupted tar data'

        with pytest.raises(ValueError, match='Error extracting tar archive'):
            _handle_tar_archive('test_id', corrupted_data, 'src', '/tmp/test')

    def test_list_files_tar_error(self):
        """Test list_files with corrupted tar that falls back to single file."""
        from mcp_handley_lab.arxiv.tool import _is_tar_archive

        # Use corrupted data that can't be opened as tar but also can't be decompressed
        corrupted_data = b'corrupted data'

        # Verify it's not detected as a tar archive
        assert not _is_tar_archive(corrupted_data)

    @patch('mcp_handley_lab.arxiv.tool.gzip.decompress')
    def test_single_file_decompression_error(self, mock_decompress):
        """Test single file decompression error."""
        from mcp_handley_lab.arxiv.tool import _handle_single_file

        mock_decompress.side_effect = Exception('Decompression failed')

        with pytest.raises(ValueError, match='Error processing single file'):
            _handle_single_file('test_id', b'corrupted gzip data', 'src', '-')


    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    async def test_list_files_tar_error_exception(self, mock_get_source):
        """Test list_files with tar that raises TarError."""
        # Return a mock tar archive
        mock_get_source.return_value = create_mock_tar_archive()

        # Patch _is_tar_archive to return True, and then make the actual tar.open fail
        with patch('mcp_handley_lab.arxiv.tool._is_tar_archive', return_value=True):
            with patch('mcp_handley_lab.arxiv.tool.tarfile.open') as mock_tar_open:
                mock_tar_open.side_effect = tarfile.TarError('Corrupted tar')

                with pytest.raises(ValueError, match='Error reading tar archive'):
                    await list_files('test_id')


class TestArxivCaching:
    """Test caching functionality."""

    @pytest.mark.asyncio
    @patch('mcp_handley_lab.arxiv.tool.httpx.AsyncClient')
    @patch('mcp_handley_lab.arxiv.tool._get_cached_source')
    @patch('mcp_handley_lab.arxiv.tool._cache_source')
    async def test_caching_behavior(self, mock_cache, mock_get_cached, mock_client):
        """Test that caching works correctly."""
        # First call - no cache
        mock_get_cached.return_value = None
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = create_mock_tar_archive()
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        files = await list_files('2301.07041')

        # Should have called httpx client and _cache_source
        mock_client_instance.get.assert_called_once()
        mock_cache.assert_called_once()
        assert len(files) == 4

        # Reset mocks for second call
        mock_client_instance.get.reset_mock()
        mock_cache.reset_mock()
        mock_get_cached.return_value = create_mock_tar_archive()

        files2 = await list_files('2301.07041')

        # Should not have called httpx client again, only used cache
        mock_client_instance.get.assert_not_called()
        mock_cache.assert_not_called()
        assert len(files2) == 4

    def test_real_cache_writing(self):
        """Test actual cache file writing and reading."""
        from pathlib import Path

        from mcp_handley_lab.arxiv.tool import _cache_source, _get_cached_source

        test_id = 'test_cache_12345'
        test_content = b'test cache content'

        # Cache should not exist initially
        assert _get_cached_source(test_id) is None

        # Write to cache
        _cache_source(test_id, test_content)

        # Read from cache
        cached = _get_cached_source(test_id)
        assert cached == test_content

        # Clean up
        cache_file = Path(tempfile.gettempdir()) / f"arxiv_{test_id}.tar"
        cache_file.unlink(missing_ok=True)


class TestArxivIntegration:
    """Integration tests for ArXiv tool using VCR cassettes."""

    @pytest.mark.asyncio
    @pytest.mark.vcr(cassette_library_dir='tests/integration/cassettes')
    @pytest.mark.integration
    async def test_real_arxiv_paper_src_single_file(self):
        """Test with a real ArXiv paper that's a single gzipped file."""
        # Use a very small ArXiv paper (8KB source) - single gzipped file
        arxiv_id = '0704.0005'  # Small paper with minimal source

        # Test listing files
        files = await list_files(arxiv_id)
        assert isinstance(files, list)
        assert len(files) == 1
        assert f'{arxiv_id}.tex' in files

        # Test downloading source with stdout
        result = await download(arxiv_id, format='src', output_path='-')
        assert f'ArXiv source file for {arxiv_id}:' in result
        assert 'single .tex file' in result
        assert 'bytes' in result

    @pytest.mark.asyncio
    @pytest.mark.vcr(cassette_library_dir='tests/integration/cassettes')
    @pytest.mark.integration
    async def test_real_arxiv_paper_src_tar_archive(self):
        """Test with a real ArXiv paper that's a tar archive."""
        # Use the first ArXiv paper - it's a tar archive with multiple files
        arxiv_id = '0704.0001'  # First paper on ArXiv (tar archive)

        # Test listing files
        files = await list_files(arxiv_id)
        assert isinstance(files, list)
        assert len(files) > 1  # Multiple files in tar archive

        # Test downloading source with stdout
        result = await download(arxiv_id, format='src', output_path='-')
        assert f'ArXiv source files for {arxiv_id}:' in result
        assert 'bytes' in result

    @pytest.mark.asyncio
    @pytest.mark.vcr(cassette_library_dir='tests/integration/cassettes')
    @pytest.mark.integration
    async def test_real_arxiv_paper_pdf(self):
        """Test with a real ArXiv paper PDF download."""
        arxiv_id = '0704.0001'  # Use first paper for PDF test

        # Test PDF info with stdout
        result = await download(arxiv_id, format='pdf', output_path='-')
        assert f'ArXiv PDF for {arxiv_id}:' in result
        assert 'MB' in result

    @pytest.mark.asyncio
    @pytest.mark.vcr(cassette_library_dir='tests/integration/cassettes')
    @pytest.mark.integration
    async def test_invalid_arxiv_id(self):
        """Test with invalid ArXiv ID."""
        with pytest.raises(RuntimeError):
            await list_files('invalid-id-99999999')

    @pytest.mark.vcr(cassette_library_dir='tests/integration/cassettes')
    @pytest.mark.integration
    def test_real_arxiv_search(self):
        """Test real ArXiv search functionality."""
        # Search for a specific topic
        results = search('machine learning', max_results=5)
        
        assert isinstance(results, list)
        assert len(results) <= 5
        
        if len(results) > 0:
            # Check first result structure
            result = results[0]
            assert 'id' in result
            assert 'title' in result
            assert 'authors' in result
            assert 'summary' in result
            assert 'published' in result
            assert 'categories' in result
            assert 'pdf_url' in result
            assert 'abs_url' in result
            
            # Check data types
            assert isinstance(result['id'], str)
            assert isinstance(result['title'], str)
            assert isinstance(result['authors'], list)
            assert isinstance(result['summary'], str)
            assert isinstance(result['categories'], list)
            assert result['pdf_url'].startswith('http')
            assert result['abs_url'].startswith('http')
