import os
import tempfile

import pytest

from mcp_handley_lab.arxiv.tool import download, search, server_info


class TestArxivIntegration:
    """Integration tests for ArXiv tool using VCR cassettes."""

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    @pytest.mark.integration
    def test_real_arxiv_paper_src_single_file(self):
        """Test with a real ArXiv paper that's a single gzipped file."""
        # Use a very small ArXiv paper (8KB source) - single gzipped file
        arxiv_id = "0704.0005"  # Small paper with minimal source

        # Test listing files via download with output_path="-"
        result = download(arxiv_id, format="src", output_path="-")
        assert isinstance(result.files, list)
        assert len(result.files) == 1
        assert f"{arxiv_id}.tex" in result.files

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

        # Test listing files via download with output_path="-"
        result = download(arxiv_id, format="src", output_path="-")
        assert isinstance(result.files, list)
        assert len(result.files) > 1  # Multiple files in tar archive

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
            download("invalid-id-99999999", format="src", output_path="-")

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    @pytest.mark.integration
    def test_real_arxiv_search(self):
        """Test real ArXiv search functionality."""
        # Search for a specific topic using direct function call
        # Note: Must pass all args explicitly since Field() defaults don't work outside MCP
        results = search(
            query="machine learning",
            max_results=5,
            start=0,
            sort_by="relevance",
            sort_order="descending",
            include_fields=[],
            max_authors=5,
            max_summary_len=1000,
        )

        assert isinstance(results, list)
        assert len(results) <= 5

        if len(results) > 0:
            # Check first result structure
            result = results[0]
            assert result.id is not None
            assert result.title is not None
            assert result.authors is not None
            assert result.summary is not None
            assert result.published is not None
            assert result.categories is not None
            assert result.pdf_url is not None
            assert result.abs_url is not None

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
    def test_arxiv_search_field_filtering(self):
        """Test include_fields functionality for context window management."""
        # Test minimal fields (just id and title)
        # Note: Must pass all args explicitly since Field() defaults don't work outside MCP
        results = search(
            query="machine learning",
            max_results=2,
            start=0,
            sort_by="relevance",
            sort_order="descending",
            include_fields=["title"],
            max_authors=5,
            max_summary_len=1000,
        )

        assert len(results) <= 2
        if results:
            result = results[0]
            assert result.id  # Always included
            assert result.title
            # Other fields should be None
            assert result.authors is None
            assert result.summary is None
            assert result.published is None

        # Test summary fields
        results = search(
            query="machine learning",
            max_results=2,
            start=0,
            sort_by="relevance",
            sort_order="descending",
            include_fields=["title", "authors", "published"],
            max_authors=5,
            max_summary_len=1000,
        )

        assert len(results) <= 2
        if results:
            result = results[0]
            assert result.id  # Always included
            assert result.title
            assert result.authors is not None
            assert result.published is not None
            # These should be None (not requested)
            assert result.summary is None
            assert result.categories is None
            assert result.pdf_url is None

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    @pytest.mark.integration
    def test_arxiv_search_truncation(self):
        """Test author and summary truncation features."""
        # Test summary truncation
        # Note: Must pass all args explicitly since Field() defaults don't work outside MCP
        results = search(
            query="machine learning",
            max_results=1,
            start=0,
            sort_by="relevance",
            sort_order="descending",
            include_fields=[],
            max_authors=5,
            max_summary_len=100,
        )

        if results and results[0].summary:
            summary = results[0].summary
            assert len(summary) <= 103  # 100 + "..."
            if len(summary) > 100:
                assert summary.endswith("...")

        # Test author truncation - need a paper with many authors
        results = search(
            query="deep learning collaboration",
            max_results=5,
            start=0,
            sort_by="relevance",
            sort_order="descending",
            include_fields=[],
            max_authors=3,
            max_summary_len=1000,
        )

        for result in results:
            if result.authors and len(result.authors) > 3:
                # Check if truncation message is present
                last_author = result.authors[-1]
                assert "... and" in last_author and "more" in last_author
                # Total should be max_authors + 1 (for the "... and X more" entry)
                assert len(result.authors) == 4

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
        assert "server_info" in str(info.capabilities)
        assert "src,pdf,tex" in info.dependencies["supported_formats"]
        assert "pdf" in info.dependencies["supported_formats"]
        assert "tex" in info.dependencies["supported_formats"]

    def test_download_invalid_format(self):
        """Test download with invalid format (no VCR needed for validation)."""
        with pytest.raises(ValueError, match="Invalid format 'invalid'"):
            download("2301.07041", format="invalid")
