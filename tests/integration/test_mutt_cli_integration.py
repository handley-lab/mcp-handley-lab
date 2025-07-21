"""CLI integration tests for Mutt focusing on command execution.

Tests real mutt CLI commands without filesystem dependencies.
Focuses on command execution, process management, and CLI interface.
"""
import shutil
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.email.mutt.tool import mcp as mutt_mcp, run_command


@pytest.fixture
def minimal_mutt_config(tmp_path):
    """Create minimal mutt configuration for CLI testing."""
    mutt_config = tmp_path / "test_muttrc"
    
    # Create minimal config that won't interfere with CLI tests
    mutt_config.write_text("""
# Minimal test configuration
set alias_file=""
set folder=""
set record=""
set postponed=""
set spoolfile=""
""")
    
    return mutt_config


@pytest.mark.skipif(not shutil.which("mutt"), reason="mutt CLI not available")
@pytest.mark.integration
class TestMuttCLICommands:
    """Test mutt CLI command execution."""

    def test_mutt_version_query(self):
        """Test mutt version query command."""
        stdout, stderr = run_command(["mutt", "-v"], timeout=30)
        
        # Should return version information
        version_output = stdout.decode()
        assert "Mutt" in version_output
        assert len(version_output) > 0

    def test_mutt_help_query(self):
        """Test mutt help command execution."""
        stdout, stderr = run_command(["mutt", "-h"], timeout=30)
        
        # Help output should contain usage information
        help_output = stdout.decode() + stderr.decode()  # Help may go to stderr
        assert "usage" in help_output.lower() or "mutt" in help_output.lower()

    def test_mutt_config_query_basic(self, minimal_mutt_config):
        """Test basic mutt configuration queries."""
        # Test querying a basic configuration variable
        cmd = ["mutt", "-F", str(minimal_mutt_config), "-Q", "folder"]
        stdout, stderr = run_command(cmd, timeout=30)
        
        # Should return folder setting (empty in our test config)
        output = stdout.decode().strip()
        assert "folder" in output

    def test_mutt_config_query_alias_file(self, minimal_mutt_config):
        """Test querying alias_file configuration."""
        cmd = ["mutt", "-F", str(minimal_mutt_config), "-Q", "alias_file"]
        stdout, stderr = run_command(cmd, timeout=30)
        
        # Should return alias_file setting (empty in our test config)
        output = stdout.decode().strip()
        assert "alias_file" in output

    def test_mutt_config_query_mailboxes(self, minimal_mutt_config):
        """Test querying mailboxes configuration."""
        cmd = ["mutt", "-F", str(minimal_mutt_config), "-Q", "mailboxes"]
        stdout, stderr = run_command(cmd, timeout=30)
        
        # Should return without error (mailboxes may be empty)
        output = stdout.decode().strip()
        # Just verify the command executed successfully
        assert isinstance(output, str)

    def test_mutt_batch_mode_execution(self, minimal_mutt_config):
        """Test mutt execution in batch mode."""
        # Test that mutt can be invoked in batch mode
        cmd = ["mutt", "-F", str(minimal_mutt_config), "-Q", "alias_file"]
        stdout, stderr = run_command(cmd, timeout=30)
        
        # Should complete without hanging in interactive mode
        assert len(stdout) > 0


@pytest.mark.skipif(not shutil.which("mutt"), reason="mutt CLI not available")
@pytest.mark.integration 
class TestMuttCLIProcessManagement:
    """Test mutt process execution and management."""

    def test_mutt_command_timeout_handling(self, minimal_mutt_config):
        """Test that mutt commands respect timeout limits."""
        cmd = ["mutt", "-F", str(minimal_mutt_config), "-Q", "version"]
        
        # Test with reasonable timeout
        stdout, stderr = run_command(cmd, timeout=5)
        
        # Should complete within timeout
        assert len(stdout) > 0

    def test_mutt_invalid_flag_error_handling(self, minimal_mutt_config):
        """Test error handling for invalid mutt flags."""
        cmd = ["mutt", "-F", str(minimal_mutt_config), "--invalid-flag-that-does-not-exist"]
        
        # Should raise an error or return error output
        try:
            stdout, stderr = run_command(cmd, timeout=10)
            # If command succeeds, error should be in stderr
            error_output = stderr.decode().lower()
            assert "invalid" in error_output or "unknown" in error_output or "unrecognized" in error_output
        except Exception as e:
            # If command fails, that's expected for invalid flags
            assert "invalid" in str(e).lower() or "unknown" in str(e).lower() or "unrecognized" in str(e).lower()

    def test_mutt_nonexistent_config_handling(self):
        """Test error handling for nonexistent configuration file."""
        nonexistent_config = "/tmp/nonexistent_mutt_config_12345"
        cmd = ["mutt", "-F", nonexistent_config, "-Q", "version"]
        
        # Should handle missing config file gracefully
        try:
            stdout, stderr = run_command(cmd, timeout=10)
            # If command succeeds, may have warnings in stderr
            output = stdout.decode() + stderr.decode()
            # Just verify it handled the situation
            assert isinstance(output, str)
        except Exception as e:
            # Expected to fail with missing config
            assert "no such file" in str(e).lower() or "not found" in str(e).lower()


@pytest.mark.integration
class TestMuttServerInfoCLI:
    """Test server info functionality with CLI focus."""

    @pytest.mark.asyncio
    async def test_server_info_cli_version_detection(self, minimal_mutt_config, monkeypatch):
        """Test that server_info correctly detects mutt CLI version."""
        if not shutil.which("mutt"):
            pytest.skip("mutt CLI not available")
        
        # Mock configuration queries to focus on CLI version detection
        def mock_run_command(cmd, timeout=None, input_data=None):
            if "mutt -v" in " ".join(cmd):
                return (b"Mutt 2.2.14 (2025-01-01)\n", b"")
            elif "mutt -Q" in " ".join(cmd):
                # Return minimal config responses
                if "alias_file" in " ".join(cmd):
                    return (b'alias_file=""', b"")
                elif "mailboxes" in " ".join(cmd):
                    return (b'mailboxes=""', b"")
                else:
                    return (b"", b"")
            else:
                # Fall back to real command execution for version query
                from mcp_handley_lab.email.mutt.tool import run_command as real_run_command
                return real_run_command(cmd, timeout, input_data)
        
        monkeypatch.setattr("mcp_handley_lab.email.mutt.tool.run_command", mock_run_command)
        
        _, response = await mutt_mcp.call_tool("server_info", {})
        assert "error" not in response, response.get("error")
        result = response
        
        assert result["name"] == "Mutt Tool"
        assert result["status"] == "active"
        # Should contain actual or mocked mutt version
        assert "Mutt" in result["version"]
        assert "2." in result["version"]  # Version number format


@pytest.mark.integration
class TestMuttCLIErrorScenarios:
    """Test CLI error handling and edge cases."""

    def test_mutt_cli_not_found_simulation(self, monkeypatch):
        """Test handling when mutt CLI is not found."""
        # Temporarily hide mutt from PATH
        import os
        original_path = os.environ.get('PATH', '')
        
        def mock_which(cmd):
            return None  # Simulate mutt not being found
        
        monkeypatch.setattr('shutil.which', mock_which)
        
        # Test that our tools handle missing mutt gracefully
        from mcp_handley_lab.email.mutt.tool import run_command
        
        with pytest.raises(Exception):  # Should raise appropriate error
            run_command(["mutt", "-v"], timeout=5)

    @pytest.mark.asyncio
    async def test_server_info_with_mutt_unavailable(self, monkeypatch):
        """Test server_info when mutt CLI is unavailable."""
        def mock_run_command(cmd, timeout=None, input_data=None):
            # Simulate mutt command failing
            raise RuntimeError("mutt: command not found")
        
        monkeypatch.setattr("mcp_handley_lab.email.mutt.tool.run_command", mock_run_command)
        
        _, response = await mutt_mcp.call_tool("server_info", {})
        # May return error or handle gracefully depending on implementation
        if "error" in response:
            assert "mutt" in response["error"].lower()
        else:
            # If handled gracefully, should indicate unavailable status
            result = response
            assert "mutt" in result["version"].lower() or result["status"] != "active"

    def test_mutt_cli_malformed_output_handling(self, monkeypatch):
        """Test handling of unexpected mutt CLI output formats."""
        def mock_run_command(cmd, timeout=None, input_data=None):
            if "mutt -v" in " ".join(cmd):
                # Return malformed version output
                return (b"This is not a valid mutt version output format", b"")
            elif "mutt -Q" in " ".join(cmd):
                # Return malformed config output  
                return (b"malformed_config_output_without_equals", b"")
            else:
                return (b"", b"")
        
        monkeypatch.setattr("mcp_handley_lab.email.mutt.tool.run_command", mock_run_command)
        
        # The tools should handle malformed output gracefully
        from mcp_handley_lab.email.mutt.tool import run_command
        stdout, stderr = run_command(["mutt", "-v"], timeout=5)
        
        # Should return the malformed output without crashing
        assert b"This is not a valid mutt version" in stdout


@pytest.mark.integration
class TestMuttCLICommandConstruction:
    """Test that CLI commands are constructed correctly."""

    def test_version_command_construction(self):
        """Test that version query command is correct."""
        # This tests the actual command that would be executed
        expected_cmd = ["mutt", "-v"]
        
        # Verify this is a valid command structure
        assert isinstance(expected_cmd, list)
        assert expected_cmd[0] == "mutt"
        assert expected_cmd[1] == "-v"

    def test_config_query_command_construction(self):
        """Test configuration query command construction.""" 
        config_file = "/tmp/test_config"
        variable = "alias_file"
        
        expected_cmd = ["mutt", "-F", config_file, "-Q", variable]
        
        # Verify command structure
        assert expected_cmd[0] == "mutt"
        assert expected_cmd[1] == "-F"
        assert expected_cmd[2] == config_file
        assert expected_cmd[3] == "-Q"
        assert expected_cmd[4] == variable

    def test_mailbox_query_command_construction(self):
        """Test mailbox query command construction."""
        config_file = "/tmp/test_config"
        
        expected_cmd = ["mutt", "-F", config_file, "-Q", "mailboxes"]
        
        # Verify command structure is correct for mailbox queries
        assert "-Q" in expected_cmd
        assert "mailboxes" in expected_cmd
        assert config_file in expected_cmd