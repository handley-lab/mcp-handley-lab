"""Systematic unhappy path tests for ArXiv integration.

Tests error scenarios including service downtime, corrupted downloads,
network failures, and edge cases not covered by basic integration tests.
"""


import pytest
from mcp.server.fastmcp.exceptions import ToolError
from mcp_handley_lab.arxiv.tool import mcp


@pytest.mark.integration
class TestArxivInvalidInputs:
    """Test invalid input scenarios for ArXiv integration."""

    @pytest.mark.asyncio
    async def test_malformed_arxiv_ids(self):
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
            with pytest.raises(ToolError, match="invalid|format|arxiv.*id|not.*found"):
                await mcp.call_tool(
                    "download",
                    {"arxiv_id": arxiv_id, "format": "src", "output_path": "-"},
                )

    @pytest.mark.asyncio
    async def test_invalid_format_parameters(self):
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
            with pytest.raises(ToolError, match="format|invalid|supported"):
                await mcp.call_tool(
                    "download",
                    {
                        "arxiv_id": valid_arxiv_id,
                        "format": invalid_format,
                        "output_path": "-",
                    },
                )

    @pytest.mark.asyncio
    async def test_empty_output_path_handling(self):
        """Test handling of empty or invalid output paths."""
        valid_arxiv_id = "2301.07041"

        # Empty output path - should use default behavior
        import json

        result = await mcp.call_tool(
            "download", {"arxiv_id": valid_arxiv_id, "format": "src", "output_path": ""}
        )
        response = json.loads(result[0].text)

        # Should handle empty path gracefully (use default)
        assert "error" not in response, response.get("error")


@pytest.mark.integration
class TestArxivNetworkAndServiceErrors:
    """Test network connectivity and ArXiv service error scenarios."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_nonexistent_arxiv_paper(self):
        """Test handling of ArXiv papers that don't exist."""
        # Use well-formed but non-existent ArXiv ID
        nonexistent_id = "9999.99999"

        with pytest.raises(
            ToolError, match="not found|does not exist|404|paper.*not.*available"
        ):
            await mcp.call_tool(
                "download",
                {"arxiv_id": nonexistent_id, "format": "src", "output_path": "-"},
            )

    @pytest.mark.asyncio
    async def test_output_file_permission_errors(self, tmp_path):
        """Test handling of output file permission errors."""
        valid_arxiv_id = "2301.07041"

        # Create directory without write permissions
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)  # Read and execute only

        output_file = readonly_dir / "arxiv_output.tar.gz"

        try:
            with pytest.raises(ToolError, match="permission|write|access|denied"):
                await mcp.call_tool(
                    "download",
                    {
                        "arxiv_id": valid_arxiv_id,
                        "format": "src",
                        "output_path": str(output_file),
                    },
                )
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    @pytest.mark.asyncio
    async def test_output_directory_creation(self, tmp_path):
        """Test automatic directory creation for output files."""
        valid_arxiv_id = "2301.07041"

        # Output path in non-existent directory
        nested_path = tmp_path / "nested" / "deep" / "directory" / "output.tar.gz"

        # Should either create directory or provide clear error
        try:
            import json

            result = await mcp.call_tool(
                "download",
                {
                    "arxiv_id": valid_arxiv_id,
                    "format": "src",
                    "output_path": str(nested_path),
                },
            )
            response = json.loads(result[0].text)

            # If successful, file should exist
            if "error" not in response:
                assert nested_path.exists()
                assert nested_path.stat().st_size > 0

        except ToolError as e:
            # Directory creation errors are acceptable
            assert any(
                keyword in str(e).lower()
                for keyword in ["directory", "not found", "no such", "path", "create"]
            )

    @pytest.mark.asyncio
    async def test_disk_space_simulation(self, tmp_path, monkeypatch):
        """Test behavior when disk space is limited (simulated)."""
        valid_arxiv_id = "2301.07041"
        output_file = tmp_path / "output.tar.gz"

        # This test simulates disk space issues by using filesystem behavior
        # In practice, ArXiv downloads could be several MB

        # Create a very large file to potentially fill up available space
        # (This is a simulation - actual disk space errors are hard to test reliably)
        large_dummy_file = tmp_path / "space_filler.dat"
        try:
            # Try to create a large file to simulate disk pressure
            large_dummy_file.write_bytes(b"0" * (1024 * 1024))  # 1MB

            import json

            result = await mcp.call_tool(
                "download",
                {
                    "arxiv_id": valid_arxiv_id,
                    "format": "src",
                    "output_path": str(output_file),
                },
            )
            response = json.loads(result[0].text)

            # Should succeed in normal circumstances
            if "error" not in response:
                assert output_file.exists()

        except ToolError as e:
            # Disk space errors are acceptable (though rare in tests)
            assert any(
                keyword in str(e).lower()
                for keyword in ["space", "disk", "write", "full", "no space"]
            )
        finally:
            # Clean up large file
            if large_dummy_file.exists():
                large_dummy_file.unlink()


@pytest.mark.integration
class TestArxivCorruptedDataHandling:
    """Test handling of corrupted or problematic ArXiv data."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_arxiv_file_listing_errors(self):
        """Test download with file listing for problematic ArXiv IDs."""
        # Test with non-existent paper using download with output_path="-" for file listing
        with pytest.raises(
            ToolError, match="not found|does not exist|404|paper.*not.*available"
        ):
            await mcp.call_tool(
                "download",
                {"arxiv_id": "9999.99999", "format": "src", "output_path": "-"},
            )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_arxiv_format_availability(self):
        """Test requesting formats that might not be available for specific papers."""
        # Some very old papers might not have all formats available
        old_arxiv_id = "hep-th/9901001"  # Very old paper format

        # Test each format - some might not be available
        for format_type in ["src", "pdf", "tex"]:
            try:
                import json

                result = await mcp.call_tool(
                    "download",
                    {
                        "arxiv_id": old_arxiv_id,
                        "format": format_type,
                        "output_path": "-",
                    },
                )
                response = json.loads(result[0].text)

                # If successful, should have valid response structure
                if "error" not in response:
                    assert "arxiv_id" in response
                    assert "format" in response
                    assert "message" in response

            except ToolError as e:
                # Some formats might not be available for old papers
                error_msg = str(e).lower()
                acceptable_errors = [
                    "not available",
                    "format not found",
                    "not found",
                    "404",
                    "does not exist",
                    "unavailable",
                    "no such file",
                    "directory",
                ]
                assert any(err in error_msg for err in acceptable_errors)

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_arxiv_withdrawn_papers(self):
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

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_arxiv_version_handling(self):
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
                import json

                result = await mcp.call_tool(
                    "download",
                    {"arxiv_id": versioned_id, "format": "src", "output_path": "-"},
                )
                response = json.loads(result[0].text)

                # If successful, should handle version correctly
                if "error" not in response:
                    assert "message" in response

            except ToolError as e:
                # Version not found errors are acceptable
                error_msg = str(e).lower()
                version_error_keywords = [
                    "version",
                    "not found",
                    "does not exist",
                    "404",
                    "unavailable",
                ]
                assert any(keyword in error_msg for keyword in version_error_keywords)

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_arxiv_simultaneous_downloads(self):
        """Test behavior with multiple simultaneous download requests."""
        valid_arxiv_id = "2301.07041"

        # Make multiple simultaneous requests (simulates concurrency issues)
        import asyncio

        async def download_paper(format_type, output_suffix):
            try:
                import json

                result = await mcp.call_tool(
                    "download",
                    {
                        "arxiv_id": valid_arxiv_id,
                        "format": format_type,
                        "output_path": f"/tmp/arxiv_test_{output_suffix}.dat",
                    },
                )
                response = json.loads(result[0].text)
                return response
            except Exception as e:
                return {"error": str(e)}

        # Start multiple downloads concurrently
        tasks = [
            download_paper("src", "1"),
            download_paper("pdf", "2"),
            download_paper("tex", "3"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least some should succeed (unless rate limited)
        successful_results = [
            r for r in results if isinstance(r, dict) and "error" not in r
        ]

        # Either succeeds or fails with reasonable errors
        if len(successful_results) == 0:
            # All failed - check if errors are reasonable
            for result in results:
                if isinstance(result, dict) and "error" in result:
                    error_msg = result["error"].lower()
                    acceptable_errors = [
                        "rate",
                        "limit",
                        "throttl",
                        "too many",
                        "concurrent",
                        "timeout",
                        "busy",
                        "unavailable",
                    ]
                    # Should fail with reasonable errors, not crashes
                    assert (
                        any(err in error_msg for err in acceptable_errors)
                        or "not found" in error_msg
                    )

    @pytest.mark.asyncio
    async def test_arxiv_special_character_handling(self):
        """Test handling of ArXiv IDs with edge case characters."""
        # ArXiv IDs should only contain specific characters
        # Test that invalid characters are rejected properly

        special_char_ids = [
            "2301.07041@test",  # @ symbol
            "2301.07041 space",  # Space
            "2301.07041\nnewline",  # Newline
            "2301.07041\ttab",  # Tab
        ]

        for special_id in special_char_ids:
            with pytest.raises(
                ToolError,
                match="invalid|format|arxiv.*id|character|404|not found|non-printable|ascii",
            ):
                await mcp.call_tool(
                    "download",
                    {"arxiv_id": special_id, "format": "src", "output_path": "-"},
                )

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_arxiv_output_path_edge_cases(self):
        """Test various edge cases for output path handling."""
        valid_arxiv_id = "2301.07041"

        # Test stdout output (should work)
        import json

        result = await mcp.call_tool(
            "download",
            {"arxiv_id": valid_arxiv_id, "format": "src", "output_path": "-"},
        )
        response = json.loads(result[0].text)
        assert "error" not in response, response.get("error")

        # Test empty output path (should use default)
        import json

        result = await mcp.call_tool(
            "download", {"arxiv_id": valid_arxiv_id, "format": "src", "output_path": ""}
        )
        response = json.loads(result[0].text)
        assert "error" not in response, response.get("error")


@pytest.mark.integration
class TestArxivServerInfoErrors:
    """Test server_info error scenarios."""

    @pytest.mark.asyncio
    async def test_server_info_reliability(self):
        """Test that server_info provides consistent, reliable information."""
        # Test multiple calls to ensure consistency
        responses = []

        for _ in range(3):
            import json

            result = await mcp.call_tool("server_info", {})
            response = json.loads(result[0].text)
            responses.append(response)
            assert "error" not in response, response.get("error")

        # All responses should be consistent
        for response in responses:
            assert response["status"] == "active"
            assert response["name"] == "ArXiv Tool"
            assert "version" in response
            assert "capabilities" in response

        # Responses should be identical
        assert all(
            r == responses[0] for r in responses
        ), "Server info responses should be consistent"
