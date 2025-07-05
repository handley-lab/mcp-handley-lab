"""Unit tests for GitHub CI Monitor tool."""

import json
from unittest.mock import patch

import pytest
from mcp_handley_lab.github.tool import (
    monitor_pr_checks,
    server_info,
)


class TestGitHubCIMonitor:
    """Test GitHub CI Monitor functionality."""

    @patch("mcp_handley_lab.github.tool._run_gh_command")
    def test_server_info_success(self, mock_run_gh):
        """Test server info success."""
        mock_run_gh.side_effect = [
            "gh version 2.32.1 (2023-07-25)",
            "✓ Logged in to github.com as user",
        ]

        result = server_info()

        assert "GitHub CI Monitor Server Status" in result
        assert "2.32.1" in result
        assert "Logged in to github.com" in result
        assert "monitor_pr_checks:" in result
        assert "gh pr merge" in result

    @patch("mcp_handley_lab.github.tool._run_gh_command")
    def test_server_info_not_found(self, mock_run_gh):
        """Test server info when gh not found."""
        mock_run_gh.side_effect = FileNotFoundError("gh: command not found")

        with pytest.raises(RuntimeError, match="gh command not found"):
            server_info()

    @patch("time.sleep")  # Mock sleep to speed up tests
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool._run_gh_command")
    def test_monitor_pr_checks_all_passed(self, mock_run_gh, mock_time, mock_sleep):
        """Test monitoring when all checks pass."""
        # Mock time progression
        mock_time.side_effect = [0, 5, 10]  # Start, first check, done

        # Mock successful checks
        test_data = [
            {"name": "test", "state": "success"},
            {"name": "build", "state": "success"},
        ]
        mock_run_gh.return_value = json.dumps(test_data)

        result = monitor_pr_checks(25)

        assert "Starting CI monitoring for PR #25" in result
        assert "2/2 passed, 0 failed, 0 pending" in result
        assert "All checks passed! Ready to merge." in result
        assert "gh pr merge 25 --squash" in result

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool._run_gh_command")
    def test_monitor_pr_checks_failed_check(self, mock_run_gh, mock_time, mock_sleep):
        """Test monitoring when checks fail."""
        mock_time.side_effect = [0, 5, 10]  # Start, check, done

        test_data = [
            {"name": "test", "state": "success"},
            {"name": "build", "state": "failure"},
        ]
        mock_run_gh.return_value = json.dumps(test_data)

        result = monitor_pr_checks(25)

        assert "1/2 passed, 1 failed, 0 pending" in result
        assert "1 check(s) failed - monitoring stopped" in result

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool._run_gh_command")
    def test_monitor_pr_checks_pending_then_timeout(
        self, mock_run_gh, mock_time, mock_sleep
    ):
        """Test monitoring with pending checks that timeout."""
        # Mock time progression that exceeds timeout - provide enough values
        # First call: start_time, then checks during loop, then timeout check
        mock_time.side_effect = [
            0,
            10,
            35,
            65,
            70,
        ]  # Start, check1, sleep check, check2, final timeout check

        test_data = [{"name": "test", "state": "pending"}]
        mock_run_gh.return_value = json.dumps(test_data)

        result = monitor_pr_checks(25, timeout_minutes=1)  # 1 minute timeout

        assert "0/1 passed, 0 failed, 1 pending" in result
        assert "Waiting for 1 pending check(s)" in result
        assert "Monitoring timed out after 1 minutes" in result

    def test_monitor_pr_checks_invalid_parameters(self):
        """Test invalid parameters for monitor_pr_checks."""
        with pytest.raises(
            ValueError,
            match="timeout_minutes and check_interval_seconds must be positive",
        ):
            monitor_pr_checks(25, timeout_minutes=0)

        with pytest.raises(
            ValueError,
            match="timeout_minutes and check_interval_seconds must be positive",
        ):
            monitor_pr_checks(25, check_interval_seconds=-1)

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool._run_gh_command")
    def test_monitor_pr_checks_no_checks(self, mock_run_gh, mock_time, mock_sleep):
        """Test monitoring when no checks exist."""
        mock_time.side_effect = [0, 10, 35, 65, 70]  # Will timeout
        mock_run_gh.return_value = "[]"  # No checks

        result = monitor_pr_checks(25, timeout_minutes=1)

        assert "No checks found for this PR" in result
        assert "Monitoring timed out" in result

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool._run_gh_command")
    def test_monitor_pr_checks_json_parse_error(
        self, mock_run_gh, mock_time, mock_sleep
    ):
        """Test monitoring with JSON parse error."""
        mock_time.side_effect = [0, 10, 35, 65, 70]  # Will timeout
        mock_run_gh.return_value = "invalid json"

        result = monitor_pr_checks(25, timeout_minutes=1)

        assert "Failed to parse check status" in result
        assert "Monitoring timed out" in result

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool._run_gh_command")
    def test_monitor_pr_checks_custom_timing(self, mock_run_gh, mock_time, mock_sleep):
        """Test monitoring with custom timeout and interval."""
        mock_time.side_effect = [0, 5, 10]

        test_data = [{"name": "test", "state": "success"}]
        mock_run_gh.return_value = json.dumps(test_data)

        result = monitor_pr_checks(25, timeout_minutes=60, check_interval_seconds=60)

        assert "Timeout: 60 minutes" in result
        assert "Check interval: 60 seconds" in result
        assert "All checks passed!" in result


class TestGitHubCIMonitorErrorHandling:
    """Test error handling for GitHub CI Monitor."""

    def test_run_gh_command_error(self):
        """Test _run_gh_command error handling."""
        from mcp_handley_lab.github.tool import _run_gh_command

        # Mock run_command to raise an error
        with patch("mcp_handley_lab.github.tool.run_command") as mock_run:
            mock_run.side_effect = RuntimeError("Command failed")

            with pytest.raises(RuntimeError, match="GitHub CLI command failed"):
                _run_gh_command(["--version"])

    @patch("mcp_handley_lab.github.tool._run_gh_command")
    def test_server_info_error_handling(self, mock_run_gh):
        """Test server_info error handling."""
        mock_run_gh.side_effect = RuntimeError("gh error")

        with pytest.raises(RuntimeError):
            server_info()
