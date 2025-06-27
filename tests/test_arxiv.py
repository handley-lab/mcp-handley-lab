"""Tests for ArXiv tool."""

import os
import tarfile
import tempfile
from io import BytesIO
from unittest.mock import Mock, patch

import pytest

from mcp_handley_lab.arxiv.tool import download, list_files, server_info


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

    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    def test_download_src_format(self, mock_get_source):
        """Test downloading source format."""
        mock_get_source.return_value = create_mock_tar_archive()

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, 'test_paper')
            result = download('2301.07041', format='src', output_path=save_path)

            assert 'ArXiv source saved to directory:' in result
            assert save_path in result
            assert '4 files' in result

            # Verify files were extracted
            assert os.path.exists(save_path)
            assert os.path.exists(os.path.join(save_path, 'paper.tex'))
            assert os.path.exists(os.path.join(save_path, 'references.bib'))

    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    def test_download_tex_format(self, mock_get_source):
        """Test downloading tex format (tex, bib, bbl only)."""
        mock_get_source.return_value = create_mock_tar_archive()

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, 'test_paper')
            result = download('2301.07041', format='tex', output_path=save_path)

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

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    def test_download_pdf_format(self, mock_get):
        """Test downloading PDF format."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = create_mock_pdf()
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, 'test.pdf')
            result = download('2301.07041', format='pdf', output_path=save_path)

            assert 'ArXiv PDF saved to:' in result
            assert save_path in result
            assert 'MB' in result

            # Verify PDF was saved
            assert os.path.exists(save_path)
            with open(save_path, 'rb') as f:
                content = f.read()
                assert content.startswith(b'%PDF')

    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    def test_download_src_stdout(self, mock_get_source):
        """Test downloading with stdout output."""
        mock_get_source.return_value = create_mock_tar_archive()

        result = download('2301.07041', format='src', output_path='-')

        assert 'ArXiv source files for 2301.07041:' in result
        assert 'paper.tex' in result
        assert 'references.bib' in result
        assert 'figure.png' in result
        assert 'bytes' in result

    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    def test_download_tex_stdout(self, mock_get_source):
        """Test downloading tex format with stdout output."""
        mock_get_source.return_value = create_mock_tar_archive()

        result = download('2301.07041', format='tex', output_path='-')

        assert 'ArXiv LaTeX files for 2301.07041:' in result
        assert 'paper.tex' in result
        assert 'references.bib' in result
        assert 'paper.bbl' in result
        # Should not include non-tex files
        assert 'figure.png' not in result

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    def test_download_pdf_stdout(self, mock_get):
        """Test downloading PDF with stdout output."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = create_mock_pdf()
        mock_get.return_value = mock_response

        result = download('2301.07041', format='pdf', output_path='-')

        assert 'ArXiv PDF for 2301.07041:' in result
        assert 'MB' in result
        assert 'Use output_path to save to file' in result

    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    def test_download_default_output_path(self, mock_get_source):
        """Test download with default output path."""
        mock_get_source.return_value = create_mock_tar_archive()

        with tempfile.TemporaryDirectory():
            original_cwd = os.getcwd()
            with tempfile.TemporaryDirectory() as temp_dir:
                os.chdir(temp_dir)
                try:
                    result = download('2301.07041', format='src')
                    assert 'ArXiv source saved to directory: 2301.07041' in result
                    assert os.path.exists('2301.07041')
                finally:
                    os.chdir(original_cwd)

    def test_download_invalid_format(self):
        """Test download with invalid format."""
        with pytest.raises(ValueError, match="Invalid format 'invalid'"):
            download('2301.07041', format='invalid')

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    def test_download_network_error(self, mock_get):
        """Test download with network error."""
        mock_get.side_effect = Exception('Network error')

        with pytest.raises(RuntimeError, match='Error fetching ArXiv'):
            download('2301.07041', format='pdf')

    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    def test_list_files_success(self, mock_get_source):
        """Test successful file listing."""
        mock_get_source.return_value = create_mock_tar_archive()

        files = list_files('2301.07041')

        assert isinstance(files, list)
        assert 'paper.tex' in files
        assert 'references.bib' in files
        assert 'paper.bbl' in files
        assert 'figure.png' in files
        assert len(files) == 4

    @patch('mcp_handley_lab.arxiv.tool._get_source_archive')
    def test_list_files_network_error(self, mock_get_source):
        """Test file listing with network error."""
        mock_get_source.side_effect = RuntimeError('Error fetching ArXiv data: Network error')

        with pytest.raises(RuntimeError, match='Error fetching ArXiv data'):
            list_files('2301.07041')

    def test_server_info(self):
        """Test server info function."""
        info = server_info()

        assert info['name'] == 'ArXiv Tool'
        assert 'version' in info
        assert 'description' in info
        assert 'functions' in info
        assert isinstance(info['functions'], list)
        assert len(info['functions']) == 3  # download, list_files, server_info
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


class TestArxivCaching:
    """Test caching functionality."""

    @patch('mcp_handley_lab.arxiv.tool.requests.get')
    @patch('mcp_handley_lab.arxiv.tool._get_cached_source')
    @patch('mcp_handley_lab.arxiv.tool._cache_source')
    def test_caching_behavior(self, mock_cache, mock_get_cached, mock_get):
        """Test that caching works correctly."""
        # First call - no cache
        mock_get_cached.return_value = None
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.content = create_mock_tar_archive()
        mock_get.return_value = mock_response

        files = list_files('2301.07041')

        # Should have called requests.get and _cache_source
        mock_get.assert_called_once()
        mock_cache.assert_called_once()
        assert len(files) == 4

        # Reset mocks for second call
        mock_get.reset_mock()
        mock_cache.reset_mock()
        mock_get_cached.return_value = create_mock_tar_archive()

        files2 = list_files('2301.07041')

        # Should not have called requests.get again, only used cache
        mock_get.assert_not_called()
        mock_cache.assert_not_called()
        assert len(files2) == 4


class TestArxivIntegration:
    """Integration tests for ArXiv tool (require network access)."""

    @pytest.mark.integration
    def test_real_arxiv_paper_src(self):
        """Test with a real ArXiv paper source download."""
        # Use a small, simple paper
        arxiv_id = '0704.0001'  # First paper on ArXiv

        try:
            # Test listing files
            files = list_files(arxiv_id)
            assert isinstance(files, list)
            assert len(files) > 0

            # Test downloading source with stdout
            result = download(arxiv_id, format='src', output_path='-')
            assert f'ArXiv source files for {arxiv_id}:' in result
            assert len(result) > 0

        except Exception as e:
            pytest.skip(f"Network test failed: {e}")

    @pytest.mark.integration
    def test_real_arxiv_paper_pdf(self):
        """Test with a real ArXiv paper PDF download."""
        arxiv_id = '0704.0001'

        try:
            # Test PDF info with stdout
            result = download(arxiv_id, format='pdf', output_path='-')
            assert f'ArXiv PDF for {arxiv_id}:' in result
            assert 'MB' in result

        except Exception as e:
            pytest.skip(f"Network test failed: {e}")

    @pytest.mark.integration
    def test_invalid_arxiv_id(self):
        """Test with invalid ArXiv ID."""
        with pytest.raises(RuntimeError):
            list_files('invalid-id-99999999')
