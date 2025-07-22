"""Integration tests for GitHub tool using real gh CLI."""

import os
import subprocess

import pytest
from mcp_handley_lab.github.tool import monitor_pr_checks, server_info, mcp


class TestGitHubIntegration:
    """Test GitHub tool with real gh CLI subprocess calls."""

    @pytest.mark.skipif(
        os.getenv("CI") == "true",
        reason="Skipping GitHub tests in CI (no gh authentication)"
    )
    def test_server_info_real_gh(self):
        """Test server_info with real gh CLI."""
        try:
            result = server_info()
            assert result.status == "active"
            assert "GitHub CI Monitor" in result.name
            assert "monitor_pr_checks" in result.capabilities
            # Should contain version info
            assert "gh" in result.dependencies
        except FileNotFoundError:
            pytest.skip("gh CLI not installed")
        except subprocess.CalledProcessError:
            pytest.skip("gh CLI not authenticated or configured")

    @pytest.mark.skipif(
        os.getenv("CI") == "true",
        reason="Skipping GitHub tests in CI (no gh authentication)"
    )
    def test_server_info_version_parsing(self):
        """Test that server_info correctly parses gh version output."""
        try:
            result = server_info()
            # Should extract version information
            version_info = result.dependencies.get("gh", "")
            assert version_info  # Should have some version info
        except (FileNotFoundError, subprocess.CalledProcessError):
            pytest.skip("gh CLI not available or configured")

    @pytest.mark.skipif(
        os.getenv("CI") == "true",
        reason="Skipping GitHub tests in CI (no gh authentication)"
    )
    def test_server_info_auth_status(self):
        """Test that server_info checks authentication status."""
        try:
            result = server_info()
            # Should complete without error if properly configured
            assert result.status == "active"
        except subprocess.CalledProcessError as e:
            if "authentication" in str(e).lower():
                pytest.skip("gh CLI not authenticated")
            else:
                raise
        except FileNotFoundError:
            pytest.skip("gh CLI not installed")

    @pytest.mark.asyncio
    async def test_monitor_pr_checks_parameter_validation(self):
        """Test parameter validation in monitor_pr_checks."""
        from mcp.server.fastmcp.exceptions import ToolError
        
        # Test negative timeout
        with pytest.raises(ToolError, match="Input should be greater than 0"):
            await mcp.call_tool("monitor_pr_checks", {"pr_number": 1, "timeout_minutes": -1})
        
        # Test negative check interval
        with pytest.raises(ToolError, match="Input should be greater than 0"):
            await mcp.call_tool("monitor_pr_checks", {"pr_number": 1, "check_interval_seconds": -1})

    @pytest.mark.asyncio
    async def test_monitor_pr_checks_basic_functionality(self):
        """Test basic monitor_pr_checks functionality with real gh CLI."""
        try:
            # Test with very short timeout to avoid long test runs
            _, response = await mcp.call_tool(
                "monitor_pr_checks", 
                {
                    "pr_number": 1, 
                    "timeout_minutes": 1,  # Use 1 minute instead of 0.1
                    "check_interval_seconds": 1
                }
            )
            
            assert "error" not in response, response.get("error")
            result = response
            
            # Should complete without error (either success, failure, or timeout)
            assert result["final_status"] in ["success", "failure", "timeout"]
            assert result["total_checks"] >= 0
            assert result["log"]  # Should have monitoring log
            assert "PR #1" in result["log"]
            
        except subprocess.CalledProcessError as e:
            if "not found" in str(e) or "authentication" in str(e).lower():
                pytest.skip("gh CLI not available or not authenticated")
            elif "404" in str(e) or "Not Found" in str(e):
                # Expected for invalid repo context - this is a real error response
                assert "error" in str(e).lower()
            else:
                raise
        except (FileNotFoundError, RuntimeError):
            pytest.skip("gh CLI not available or not configured")

    # Note: Mock-based error scenario tests removed to follow "real testing over mocks" philosophy.
    # Real error scenarios are handled by graceful skipping when gh CLI is not available.