"""Tests for mutt tool internal logic."""
import pytest
from mcp_handley_lab.email.mutt.tool import _build_mutt_command










class TestMuttCommandConstruction:
    """Test mutt command construction functions."""

    def test_build_mutt_command_attachment_ordering(self):
        """Test that attachments are ordered correctly with temp file."""
        # This test specifically addresses the bug where -i flag was placed after --
        # causing temp file path to be interpreted as recipient address
        cmd = _build_mutt_command(
            to="test@example.com",
            subject="Test Subject",
            attachments=["/path/to/file.pdf"],
            temp_file_path="/tmp/body.txt",
        )

        # Find the positions of key elements
        dash_h_pos = cmd.index("-H")
        temp_file_pos = cmd.index("/tmp/body.txt")
        dash_a_pos = cmd.index("-a")
        attachment_pos = cmd.index("/path/to/file.pdf")
        separator_pos = cmd.index("--")
        recipient_pos = cmd.index("test@example.com")

        # Verify correct ordering: -H comes before -a, and -- comes before recipient
        assert dash_h_pos < dash_a_pos, "'-H' flag should come before '-a' flag"
        assert (
            temp_file_pos < dash_a_pos
        ), "temp file path should come before attachments"
        assert dash_a_pos < separator_pos, "'-a' flag should come before '--' separator"
        assert (
            attachment_pos < separator_pos
        ), "attachment path should come before '--' separator"
        assert (
            separator_pos < recipient_pos
        ), "'--' separator should come before recipient"

    def test_build_mutt_command_no_attachments(self):
        """Test command construction without attachments."""
        cmd = _build_mutt_command(
            to="test@example.com",
            subject="Test Subject",
            temp_file_path="/tmp/body.txt",
        )

        # Should not contain attachment-related flags
        assert "-a" not in cmd
        assert "--" not in cmd
        assert "-H" in cmd
        assert "/tmp/body.txt" in cmd
        assert "test@example.com" in cmd

    def test_build_mutt_command_no_temp_file(self):
        """Test command construction without temp file."""
        cmd = _build_mutt_command(
            to="test@example.com",
            subject="Test Subject",
            attachments=["/path/to/file.pdf"],
        )

        # Should contain attachment flags but no -i flag
        assert "-a" in cmd
        assert "--" in cmd
        assert "/path/to/file.pdf" in cmd
        assert "-i" not in cmd
        assert "test@example.com" in cmd
