"""Integration tests for Mutt tools using real filesystem operations."""
import shutil
import tempfile
from pathlib import Path

import pytest
from mcp_handley_lab.email.mutt.tool import mcp as mutt_mcp
from mcp_handley_lab.email.mutt_aliases.tool import mcp as aliases_mcp


@pytest.fixture
def temp_mutt_config(tmp_path, monkeypatch):
    """Create temporary mutt configuration for testing."""
    # Create temporary mutt config directory
    mutt_config_dir = tmp_path / ".mutt"
    mutt_config_dir.mkdir()
    
    # Create temporary addressbook file
    addressbook = mutt_config_dir / "addressbook"
    addressbook.write_text("")
    
    # Mock the mutt config to point to our temp addressbook
    def mock_run_command(cmd, timeout=None):
        if "mutt -Q alias_file" in " ".join(cmd):
            return (f'alias_file="{addressbook}"'.encode(), b"")
        elif "mutt -v" in " ".join(cmd):
            return (b"Mutt 2.2.14 (test) (2025-01-01)\n", b"")
        elif "mutt -Q mailboxes" in " ".join(cmd):
            return (b'mailboxes="INBOX Sent Drafts Trash"', b"")
        else:
            raise RuntimeError(f"Unexpected command: {cmd}")
    
    monkeypatch.setattr("mcp_handley_lab.email.mutt_aliases.tool.run_command", mock_run_command)
    monkeypatch.setattr("mcp_handley_lab.email.mutt.tool.run_command", mock_run_command)
    
    return {"addressbook": addressbook, "config_dir": mutt_config_dir}


@pytest.mark.integration
class TestMuttContactManagement:
    """Integration tests for Mutt contact management using real filesystem."""

    @pytest.mark.asyncio
    async def test_add_contact_individual(self, temp_mutt_config):
        """Test adding an individual contact to real file."""
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "john_doe",
            "email": "john@example.com", 
            "name": "John Doe"
        })
        assert "error" not in response, response.get("error")
        result = response
        
        assert "Added contact: john_doe (John Doe)" in result["message"]
        
        # Verify the contact was actually written to the file
        addressbook_content = temp_mutt_config["addressbook"].read_text()
        assert 'alias john_doe "John Doe" <john@example.com>' in addressbook_content

    @pytest.mark.asyncio
    async def test_add_contact_group(self, temp_mutt_config):
        """Test adding a group contact to real file."""
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "gw_team",
            "email": "alice@cam.ac.uk,bob@cam.ac.uk",
            "name": "GW Project Team"
        })
        assert "error" not in response, response.get("error")
        result = response
        
        assert "Added contact: gw_team (GW Project Team)" in result["message"]
        
        # Verify the group contact was written correctly
        addressbook_content = temp_mutt_config["addressbook"].read_text()
        assert 'alias gw_team "GW Project Team" <alice@cam.ac.uk,bob@cam.ac.uk>' in addressbook_content

    @pytest.mark.asyncio
    async def test_add_contact_no_name(self, temp_mutt_config):
        """Test adding contact without name to real file."""
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "simple",
            "email": "test@example.com"
        })
        assert "error" not in response, response.get("error")
        result = response
        
        assert "Added contact: simple (test@example.com)" in result["message"]
        
        # Verify the simple contact format
        addressbook_content = temp_mutt_config["addressbook"].read_text()
        assert "alias simple test@example.com" in addressbook_content

    @pytest.mark.asyncio
    async def test_remove_contact_success(self, temp_mutt_config):
        """Test successfully removing a contact from real file."""
        # First add some contacts
        temp_mutt_config["addressbook"].write_text(
            'alias john_doe "John Doe" <john@example.com>\n'
            'alias gw_team "GW Team" <alice@cam.ac.uk>\n'
        )
        
        _, response = await aliases_mcp.call_tool("remove_contact", {
            "alias": "john_doe"
        })
        assert "error" not in response, response.get("error")
        result = response
        
        assert "Removed contact: john_doe" in result["message"]
        
        # Verify the contact was actually removed
        addressbook_content = temp_mutt_config["addressbook"].read_text()
        assert "john_doe" not in addressbook_content
        assert "gw_team" in addressbook_content  # Other contact should remain

    @pytest.mark.asyncio
    async def test_remove_contact_not_found(self, temp_mutt_config):
        """Test removing a contact that doesn't exist."""
        from mcp.server.fastmcp.exceptions import ToolError
        
        # Start with a contact file that doesn't contain our target
        temp_mutt_config["addressbook"].write_text(
            'alias gw_team "GW Team" <alice@cam.ac.uk>\n'
        )
        
        with pytest.raises(ToolError, match="Contact 'nonexistent' not found"):
            await aliases_mcp.call_tool("remove_contact", {
                "alias": "nonexistent"
            })


@pytest.mark.integration  
class TestMuttFolderManagement:
    """Integration tests for Mutt folder management."""

    @pytest.mark.asyncio
    async def test_list_folders_success(self, temp_mutt_config):
        """Test successfully listing folders."""
        _, response = await mutt_mcp.call_tool("list_folders", {})
        assert "error" not in response, response.get("error")
        result = response
        
        # Should return the mocked folder list
        assert isinstance(result, list)
        assert "INBOX" in result
        assert "Sent" in result
        assert "Drafts" in result
        assert "Trash" in result


@pytest.mark.integration
class TestMuttServerInfo:
    """Integration tests for Mutt server info."""

    @pytest.mark.asyncio
    async def test_server_info_success(self, temp_mutt_config):
        """Test successful server info retrieval."""
        _, response = await mutt_mcp.call_tool("server_info", {})
        assert "error" not in response, response.get("error")
        result = response
        
        assert result["name"] == "Mutt Tool"
        assert "Mutt 2.2.14" in result["version"]
        assert result["status"] == "active"
        assert "compose" in result["capabilities"]
        assert "server_info" in result["capabilities"]


@pytest.mark.integration
class TestMuttContactWorkflows:
    """Integration tests for real-world contact management workflows."""

    @pytest.mark.asyncio
    async def test_gw_project_workflow(self, temp_mutt_config):
        """Test adding GW project team contact workflow."""
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "gw_team",
            "email": "alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk",
            "name": "GW Project Team"
        })
        assert "error" not in response, response.get("error")
        result = response
        
        assert "Added contact: gw_team (GW Project Team)" in result["message"]
        
        # Verify the alias format is correct for mutt
        addressbook_content = temp_mutt_config["addressbook"].read_text()
        expected_alias = 'alias gw_team "GW Project Team" <alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk>'
        assert expected_alias in addressbook_content

    @pytest.mark.asyncio  
    async def test_contact_lifecycle_workflow(self, temp_mutt_config):
        """Test complete contact lifecycle: add, verify, update, remove."""
        # Add initial contact
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "test_user",
            "email": "test@example.com",
            "name": "Test User"
        })
        assert "error" not in response, response.get("error")
        
        # Verify it exists in the file
        addressbook_content = temp_mutt_config["addressbook"].read_text()
        assert 'alias test_user "Test User" <test@example.com>' in addressbook_content
        
        # Add another contact
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "another_user", 
            "email": "another@example.com",
            "name": "Another User"
        })
        assert "error" not in response, response.get("error")
        
        # Verify both exist
        addressbook_content = temp_mutt_config["addressbook"].read_text()
        assert "test_user" in addressbook_content
        assert "another_user" in addressbook_content
        
        # Remove the first contact
        _, response = await aliases_mcp.call_tool("remove_contact", {
            "alias": "test_user"
        })
        assert "error" not in response, response.get("error")
        
        # Verify only the second contact remains
        addressbook_content = temp_mutt_config["addressbook"].read_text()
        assert "test_user" not in addressbook_content
        assert "another_user" in addressbook_content


@pytest.mark.integration
class TestMuttErrorHandling:
    """Integration tests for Mutt error handling scenarios."""

    @pytest.mark.asyncio
    async def test_add_contact_validation_errors(self, temp_mutt_config):
        """Test input validation for add_contact."""
        from mcp.server.fastmcp.exceptions import ToolError
        
        # Test empty alias
        with pytest.raises(ToolError, match="Both alias and email are required"):
            await aliases_mcp.call_tool("add_contact", {
                "alias": "",
                "email": "test@example.com"
            })
        
        # Test empty email
        with pytest.raises(ToolError, match="Both alias and email are required"):
            await aliases_mcp.call_tool("add_contact", {
                "alias": "test",
                "email": ""
            })

    @pytest.mark.asyncio
    async def test_remove_contact_validation_errors(self, temp_mutt_config):
        """Test input validation for remove_contact."""
        from mcp.server.fastmcp.exceptions import ToolError
        
        # Test empty alias
        with pytest.raises(ToolError, match="Alias is required"):
            await aliases_mcp.call_tool("remove_contact", {
                "alias": ""
            })


@pytest.mark.skipif(not shutil.which("mutt"), reason="mutt CLI not found")
@pytest.mark.integration
class TestMuttRealCLI:
    """Integration tests using the real mutt CLI when available."""

    @pytest.mark.asyncio
    async def test_server_info_real_mutt(self):
        """Test server info with real mutt installation."""
        # Remove mocking for this test - use real mutt
        # This will only run if mutt is actually installed
        try:
            _, response = await mutt_mcp.call_tool("server_info", {})
            assert "error" not in response, response.get("error")
            result = response
            
            assert result["name"] == "Mutt Tool"
            assert result["status"] == "active"
            assert "Mutt" in result["version"]  # Should contain actual mutt version
        except Exception as e:
            # If mutt isn't properly configured, that's OK for this test
            if "not found" in str(e) or "configuration" in str(e).lower():
                pytest.skip(f"Mutt not properly configured: {e}")
            else:
                raise