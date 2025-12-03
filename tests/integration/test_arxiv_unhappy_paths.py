"""Systematic unhappy path tests for ArXiv integration.

Tests error scenarios including service downtime, corrupted downloads,
network failures, and edge cases not covered by basic integration tests.
"""

import httpx
import pytest

from mcp_handley_lab.arxiv.tool import download, server_info


@pytest.mark.integration
class TestArxivInvalidInputs:
    """Test invalid input scenarios for ArXiv integration."""

    def test_malformed_arxiv_ids(self):
        """Test handling of various malformed ArXiv IDs."""
        malformed_ids = [
            "",  # Empty ID
            "not-an-arxiv-id",  # Invalid format
            "1234.5678.9999",  # Too many parts
            "9999.99999",  # Out of range
            "cs/0123456",  # Wrong old format
            "math-ph/0123456789",  # Too long old format
            "2023.13.0001",  # Invalid month
            "2023.00.0001",  # Invalid month (zero)
            "1990.01.0001",  # Too old (before ArXiv existed)
            "3000.01.0001",  # Too far in future
            "special-chars-!@#",  # Special characters
            "2301.07041v99999",  # Invalid version
            "2301.07041v-1",  # Negative version
        ]

        for arxiv_id in malformed_ids:
            with pytest.raises(httpx.HTTPStatusError):
                download(arxiv_id=arxiv_id, format="src", output_path="-")

    def test_invalid_format_parameters(self):
        """Test handling of invalid format parameters."""
        valid_arxiv_id = "2301.07041"  # Known valid ID

        invalid_formats = [
            "",  # Empty format
            "invalid",  # Invalid format name
            "PDF",  # Wrong case
            "source",  # Wrong name (should be 'src')
            "latex",  # Wrong name (should be 'tex')
            "123",  # Numeric
            "src,pdf",  # Multiple formats
        ]

        for invalid_format in invalid_formats:
            with pytest.raises(ValueError, match="Invalid format"):
                download(
                    arxiv_id=valid_arxiv_id,
                    format=invalid_format,
                    output_path="-",
                )

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    def test_empty_output_path_handling(self):
        """Test handling of empty or invalid output paths."""
        valid_arxiv_id = "2301.07041"

        # Empty output path - should use default behavior (creates file)
        result = download(arxiv_id=valid_arxiv_id, format="src", output_path="")

        # Should handle empty path gracefully (use default)
        assert result.arxiv_id == valid_arxiv_id


@pytest.mark.integration
class TestArxivNetworkAndServiceErrors:
    """Test network connectivity and ArXiv service error scenarios."""

    @pytest.mark.live
    def test_nonexistent_arxiv_paper(self):
        """Test handling of ArXiv papers that don't exist."""
        # Use well-formed but non-existent ArXiv ID
        nonexistent_id = "9999.99999"

        with pytest.raises(httpx.HTTPStatusError):
            download(arxiv_id=nonexistent_id, format="src", output_path="-")

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    def test_output_file_permission_errors(self, tmp_path):
        """Test handling of output file permission errors."""
        valid_arxiv_id = "2301.07041"

        # Create directory without write permissions
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)  # Read and execute only

        output_file = readonly_dir / "arxiv_output"

        try:
            with pytest.raises((PermissionError, OSError)):
                download(
                    arxiv_id=valid_arxiv_id,
                    format="src",
                    output_path=str(output_file),
                )
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    def test_output_directory_creation(self, tmp_path):
        """Test automatic directory creation for output files."""
        valid_arxiv_id = "2301.07041"

        # Output path in non-existent directory
        nested_path = tmp_path / "nested" / "deep" / "directory"

        # Should either create directory or provide clear error
        try:
            result = download(
                arxiv_id=valid_arxiv_id,
                format="src",
                output_path=str(nested_path),
            )

            # If successful, directory should exist
            assert nested_path.exists()
            assert result.arxiv_id == valid_arxiv_id

        except (FileNotFoundError, OSError) as e:
            # Directory creation errors are acceptable
            assert any(
                keyword in str(e).lower()
                for keyword in ["directory", "not found", "no such", "path", "create"]
            )


@pytest.mark.integration
class TestArxivCorruptedDataHandling:
    """Test handling of corrupted or problematic ArXiv data."""

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    def test_arxiv_file_listing_errors(self):
        """Test download with file listing for problematic ArXiv IDs."""
        # Test with non-existent paper using download with output_path="-" for file listing
        with pytest.raises(httpx.HTTPStatusError):
            download(arxiv_id="9999.99999", format="src", output_path="-")

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    def test_arxiv_format_availability(self):
        """Test requesting formats that might not be available for specific papers."""
        # Some very old papers might not have all formats available
        old_arxiv_id = "hep-th/9901001"  # Very old paper format

        # Test each format - some might not be available
        for format_type in ["src", "pdf", "tex"]:
            try:
                result = download(
                    arxiv_id=old_arxiv_id,
                    format=format_type,
                    output_path="-",
                )

                # If successful, should have valid response structure
                assert result.arxiv_id is not None
                assert result.format is not None
                assert result.message is not None

            except httpx.HTTPStatusError as e:
                # Some formats might not be available for old papers
                # 404 or 403 errors are acceptable
                assert e.response.status_code in [403, 404]

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    def test_arxiv_withdrawn_papers(self):
        """Test handling of withdrawn ArXiv papers."""
        # Note: This is hard to test reliably since withdrawn papers are rare
        # and specific IDs may change. This test documents the expected behavior.

        # If we had a known withdrawn paper ID, we would test:
        # withdrawn_id = "some.withdrawn.paper"
        # The expectation is that the tool should handle this gracefully
        # either by returning an error or indicating the paper is withdrawn

        # For now, just document this as a test case that should be added
        # if we identify specific withdrawn papers for testing
        pass


@pytest.mark.integration
class TestArxivEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    def test_arxiv_version_handling(self):
        """Test handling of specific ArXiv paper versions."""
        base_arxiv_id = "2301.07041"

        # Test different version specifications
        version_tests = [
            f"{base_arxiv_id}v1",  # Specific version
            f"{base_arxiv_id}v2",  # Different version (may not exist)
            f"{base_arxiv_id}v99",  # Very high version (shouldn't exist)
        ]

        for versioned_id in version_tests:
            try:
                result = download(arxiv_id=versioned_id, format="src", output_path="-")

                # If successful, should handle version correctly
                assert result.message is not None

            except httpx.HTTPStatusError as e:
                # Version not found errors are acceptable (404 or 403)
                assert e.response.status_code in [403, 404]

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    def test_arxiv_simultaneous_downloads(self, tmp_path):
        """Test behavior with multiple sequential download requests."""
        valid_arxiv_id = "2301.07041"

        # Make multiple sequential requests
        results = []
        formats = ["src", "pdf", "tex"]

        for i, format_type in enumerate(formats):
            output_path = tmp_path / f"arxiv_test_{i}"
            try:
                result = download(
                    arxiv_id=valid_arxiv_id,
                    format=format_type,
                    output_path=str(output_path),
                )
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})

        # At least some should succeed
        successful_results = [r for r in results if hasattr(r, "arxiv_id")]

        # Should have at least one success
        assert len(successful_results) >= 1

    def test_arxiv_special_character_handling(self):
        """Test handling of ArXiv IDs with edge case characters."""
        # ArXiv IDs should only contain specific characters
        # Test that invalid characters are rejected properly
        # httpx.InvalidURL is raised for non-printable chars, HTTPStatusError for valid but bad IDs

        special_char_ids = [
            "2301.07041@test",  # @ symbol
            "2301.07041 space",  # Space
            "2301.07041\nnewline",  # Newline
            "2301.07041\ttab",  # Tab
        ]

        for special_id in special_char_ids:
            with pytest.raises((httpx.HTTPStatusError, httpx.InvalidURL)):
                download(arxiv_id=special_id, format="src", output_path="-")

    @pytest.mark.vcr(cassette_library_dir="tests/integration/cassettes")
    def test_arxiv_output_path_edge_cases(self):
        """Test various edge cases for output path handling."""
        valid_arxiv_id = "2301.07041"

        # Test stdout output (should work)
        result = download(arxiv_id=valid_arxiv_id, format="src", output_path="-")
        assert result.arxiv_id == valid_arxiv_id

        # Test empty output path (should use default)
        result = download(arxiv_id=valid_arxiv_id, format="src", output_path="")
        assert result.arxiv_id == valid_arxiv_id


@pytest.mark.integration
class TestArxivServerInfoErrors:
    """Test server_info error scenarios."""

    def test_server_info_reliability(self):
        """Test that server_info provides consistent, reliable information."""
        # Test multiple calls to ensure consistency
        responses = []

        for _ in range(3):
            response = server_info()
            responses.append(response)

        # All responses should be consistent
        for response in responses:
            assert response.status == "active"
            assert response.name == "ArXiv Tool"
            assert response.version is not None
            assert response.capabilities is not None

        # Responses should be identical
        assert all(r == responses[0] for r in responses), (
            "Server info responses should be consistent"
        )
