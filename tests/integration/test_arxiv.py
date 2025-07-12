import os
import tempfile

import pytest
from mcp_handley_lab.arxiv.tool import download, list_files, search, server_info


class TestArxivIntegration:
    """Integration tests for ArXiv tool using VCR cassettes."""

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    @pytest.mark.integration
    def test_real_arxiv_paper_src_single_file(self):
        """Test with a real ArXiv paper that's a single gzipped file."""
        # Use a very small ArXiv paper (8KB source) - single gzipped file
        arxiv_id = "0704.0005"  # Small paper with minimal source

        # Test listing files
        files = list_files(arxiv_id)
        assert isinstance(files, list)
        assert len(files) == 1
        assert f"{arxiv_id}.tex" in files

        # Test downloading source with stdout
        result = download(arxiv_id, format="src", output_path="-")
        assert result.arxiv_id == arxiv_id
        assert result.format == "src"
        assert result.output_path == "-"
        assert result.size_bytes > 0
        assert f"{arxiv_id}.tex" in result.files

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    @pytest.mark.integration
    def test_real_arxiv_paper_src_tar_archive(self):
        """Test with a real ArXiv paper that's a tar archive."""
        # Use the first ArXiv paper - it's a tar archive with multiple files
        arxiv_id = "0704.0001"  # First paper on ArXiv (tar archive)

        # Test listing files
        files = list_files(arxiv_id)
        assert isinstance(files, list)
        assert len(files) > 1  # Multiple files in tar archive

        # Test downloading source with stdout
        result = download(arxiv_id, format="src", output_path="-")
        assert result.arxiv_id == arxiv_id
        assert result.format == "src"
        assert result.output_path == "-"
        assert f"ArXiv source files for {arxiv_id}" in result.message
        assert result.size_bytes > 0

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    @pytest.mark.integration
    def test_real_arxiv_paper_pdf(self):
        """Test with a real ArXiv paper PDF download."""
        arxiv_id = "0704.0001"  # Use first paper for PDF test

        # Test PDF info with stdout
        result = download(arxiv_id, format="pdf", output_path="-")
        assert result.arxiv_id == arxiv_id
        assert result.format == "pdf"
        assert result.output_path == "-"
        assert f"ArXiv PDF for {arxiv_id}" in result.message
        assert result.size_bytes > 0

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    @pytest.mark.integration
    def test_invalid_arxiv_id(self):
        """Test with invalid ArXiv ID."""
        import httpx

        with pytest.raises(httpx.HTTPStatusError):
            list_files("invalid-id-99999999")

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    @pytest.mark.integration
    def test_real_arxiv_search(self):
        """Test real ArXiv search functionality."""
        # Search for a specific topic
        results = search("machine learning", max_results=5)

        assert isinstance(results, list)
        assert len(results) <= 5

        if len(results) > 0:
            # Check first result structure
            result = results[0]
            assert hasattr(result, "id")
            assert hasattr(result, "title")
            assert hasattr(result, "authors")
            assert hasattr(result, "summary")
            assert hasattr(result, "published")
            assert hasattr(result, "categories")
            assert hasattr(result, "pdf_url")
            assert hasattr(result, "abs_url")

            # Check data types
            assert isinstance(result.id, str)
            assert isinstance(result.title, str)
            assert isinstance(result.authors, list)
            assert isinstance(result.summary, str)
            assert isinstance(result.categories, list)
            assert result.pdf_url.startswith("http")
            assert result.abs_url.startswith("http")

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    @pytest.mark.integration
    def test_arxiv_download_formats(self):
        """Test different download formats with VCR."""
        arxiv_id = "0704.0001"

        # Test src format
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, "test_paper")
            result = download(arxiv_id, format="src", output_path=save_path)
            assert result.arxiv_id == arxiv_id
            assert result.format == "src"
            assert result.output_path == save_path
            assert (
                "ArXiv source" in result.message
                and "saved to directory:" in result.message
            )
            assert os.path.exists(save_path)

        # Test tex format
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = os.path.join(temp_dir, "test_tex")
            result = download(arxiv_id, format="tex", output_path=save_path)
            assert result.arxiv_id == arxiv_id
            assert result.format == "tex"
            assert result.output_path == save_path
            assert (
                "ArXiv LaTeX files saved to directory:" in result.message
                or "single .tex file" in result.message
            )
            assert os.path.exists(save_path)

    def test_server_info(self):
        """Test server info function (no VCR needed for local function)."""
        info = server_info()

        assert info.name == "ArXiv Tool"
        assert info.version == "1.0.0"
        assert info.status == "active"
        assert "search" in str(info.capabilities)
        assert "download" in str(info.capabilities)
        assert "list_files" in str(info.capabilities)
        assert "server_info" in str(info.capabilities)
        assert "src,pdf,tex" in info.dependencies["supported_formats"]
        assert "pdf" in info.dependencies["supported_formats"]
        assert "tex" in info.dependencies["supported_formats"]

    def test_download_invalid_format(self):
        """Test download with invalid format (no VCR needed for validation)."""
        with pytest.raises(ValueError, match="Invalid format 'invalid'"):
            download("2301.07041", format="invalid")
