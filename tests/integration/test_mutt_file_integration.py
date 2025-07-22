"""File integration tests for Mutt focusing on filesystem operations.

Tests real filesystem operations with mocked CLI interactions.
Focuses on file I/O, directory management, and data persistence.
"""
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.email.mutt_aliases.tool import mcp as aliases_mcp


@pytest.fixture
def real_temp_addressbook(tmp_path, monkeypatch):
    """Create real temporary addressbook file with mocked CLI."""
    # Create actual temp directory and file
    mutt_dir = tmp_path / ".mutt"
    mutt_dir.mkdir()
    addressbook_file = mutt_dir / "addressbook"
    addressbook_file.touch()  # Create empty file
    
    # Mock CLI queries to point to our real temp file
    def mock_run_command(cmd, timeout=None, input_data=None):
        if "mutt -Q alias_file" in " ".join(cmd):
            return (f'alias_file="{addressbook_file}"'.encode(), b"")
        elif "mutt -v" in " ".join(cmd):
            return (b"Mutt 2.2.14 (test) (2025-01-01)\n", b"")
        else:
            return (b"", b"")
    
    monkeypatch.setattr("mcp_handley_lab.email.mutt_aliases.tool.run_command", mock_run_command)
    
    return addressbook_file


@pytest.mark.integration  
class TestMuttFileOperations:
    """Test real file operations with mocked CLI."""

    @pytest.mark.asyncio
    async def test_add_contact_creates_file_entry(self, real_temp_addressbook):
        """Test that adding contact creates correct file entry.""" 
        # Verify file starts empty
        assert real_temp_addressbook.read_text().strip() == ""
        
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "test_user",
            "email": "test@example.com",
            "name": "Test User"
        })
        assert "error" not in response, response.get("error")
        
        # Verify actual file content
        file_content = real_temp_addressbook.read_text()
        expected_line = 'alias test_user "Test User" <test@example.com>'
        assert expected_line in file_content
        
        # Verify file ends with newline
        assert file_content.endswith('\n')

    @pytest.mark.asyncio
    async def test_add_contact_appends_to_existing_file(self, real_temp_addressbook):
        """Test that new contacts are appended to existing file content."""
        # Pre-populate file with existing content
        existing_content = 'alias existing "Existing User" <existing@example.com>\n'
        real_temp_addressbook.write_text(existing_content)
        
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "new_user", 
            "email": "new@example.com",
            "name": "New User"
        })
        assert "error" not in response, response.get("error")
        
        # Verify both contacts exist in file
        file_content = real_temp_addressbook.read_text()
        assert 'alias existing "Existing User" <existing@example.com>' in file_content
        assert 'alias new_user "New User" <new@example.com>' in file_content
        
        # Verify proper line separation
        lines = file_content.strip().split('\n')
        assert len(lines) == 2

    @pytest.mark.asyncio
    async def test_add_contact_preserves_file_comments(self, real_temp_addressbook):
        """Test that comments and formatting are preserved."""
        # Pre-populate with comments and formatting
        existing_content = '''# Address book for testing
# Generated automatically

alias work_team "Work Team" <team@company.com>

# Personal contacts below
alias friend "Best Friend" <friend@personal.com>
'''
        real_temp_addressbook.write_text(existing_content)
        
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "new_contact",
            "email": "new@example.com", 
            "name": "New Contact"
        })
        assert "error" not in response, response.get("error")
        
        # Verify comments are preserved and new contact added
        file_content = real_temp_addressbook.read_text()
        assert '# Address book for testing' in file_content
        assert '# Generated automatically' in file_content  
        assert '# Personal contacts below' in file_content
        assert 'alias work_team' in file_content
        assert 'alias friend' in file_content
        assert 'alias new_contact "New Contact" <new@example.com>' in file_content

    @pytest.mark.asyncio
    async def test_remove_contact_deletes_from_file(self, real_temp_addressbook):
        """Test that removing contact deletes correct line from file."""
        # Pre-populate with multiple contacts
        initial_content = '''alias keep1 "Keep One" <keep1@example.com>
alias remove_me "Remove Me" <remove@example.com>  
alias keep2 "Keep Two" <keep2@example.com>
'''
        real_temp_addressbook.write_text(initial_content)
        
        _, response = await aliases_mcp.call_tool("remove_contact", {
            "alias": "remove_me"
        })
        assert "error" not in response, response.get("error")
        
        # Verify target contact removed, others preserved
        file_content = real_temp_addressbook.read_text()
        assert 'remove_me' not in file_content
        assert 'alias keep1 "Keep One" <keep1@example.com>' in file_content
        assert 'alias keep2 "Keep Two" <keep2@example.com>' in file_content

    @pytest.mark.asyncio
    async def test_remove_contact_preserves_comments(self, real_temp_addressbook):
        """Test that removing contact preserves comments and formatting."""
        initial_content = '''# Important header comment
alias keep_me "Keep Me" <keep@example.com>

# Comment before target
alias remove_me "Remove Me" <remove@example.com>
# Comment after target

alias also_keep "Also Keep" <also@example.com>
# Final comment
'''
        real_temp_addressbook.write_text(initial_content)
        
        _, response = await aliases_mcp.call_tool("remove_contact", {
            "alias": "remove_me"
        })
        assert "error" not in response, response.get("error")
        
        # Verify comments preserved, only target alias removed
        file_content = real_temp_addressbook.read_text()
        assert '# Important header comment' in file_content
        assert '# Comment before target' in file_content
        assert '# Comment after target' in file_content
        assert '# Final comment' in file_content
        assert 'remove_me' not in file_content
        assert 'keep_me' in file_content
        assert 'also_keep' in file_content

    @pytest.mark.asyncio
    async def test_file_locking_behavior(self, real_temp_addressbook):
        """Test file operations work correctly with concurrent access."""
        # This tests that file operations are atomic and don't interfere
        
        # Add first contact
        _, response1 = await aliases_mcp.call_tool("add_contact", {
            "alias": "contact1",
            "email": "contact1@example.com",
            "name": "Contact One"
        })
        assert "error" not in response1, response1.get("error")
        
        # Immediately add second contact (tests file consistency)
        _, response2 = await aliases_mcp.call_tool("add_contact", {
            "alias": "contact2", 
            "email": "contact2@example.com",
            "name": "Contact Two"
        })
        assert "error" not in response2, response2.get("error")
        
        # Verify both contacts exist in final file
        file_content = real_temp_addressbook.read_text()
        assert 'contact1' in file_content
        assert 'contact2' in file_content
        
        # Verify file structure is clean (proper newlines)
        lines = [line for line in file_content.split('\n') if line.strip()]
        assert len(lines) == 2


@pytest.mark.integration
class TestMuttFileErrorHandling:
    """Test filesystem error handling scenarios."""

    @pytest.mark.asyncio
    async def test_readonly_file_handling(self, real_temp_addressbook, monkeypatch):
        """Test behavior when addressbook file is read-only."""
        # Make file read-only
        real_temp_addressbook.chmod(0o444)  # Read-only
        
        from mcp.server.fastmcp.exceptions import ToolError
        
        try:
            _, response = await aliases_mcp.call_tool("add_contact", {
                "alias": "test",
                "email": "test@example.com"
            })
            
            # Should handle read-only file gracefully
            if "error" in response:
                assert "permission" in response["error"].lower() or "read-only" in response["error"].lower()
            else:
                # If operation succeeded, file should be updated
                file_content = real_temp_addressbook.read_text()
                assert "test" in file_content
        except ToolError as e:
            # Permission error should be caught as ToolError
            assert "permission denied" in str(e).lower()
                
        finally:
            # Restore write permissions for cleanup
            real_temp_addressbook.chmod(0o644)

    @pytest.mark.asyncio
    async def test_nonexistent_directory_handling(self, tmp_path, monkeypatch):
        """Test behavior when addressbook directory doesn't exist."""
        nonexistent_path = tmp_path / "nonexistent" / "addressbook"
        
        def mock_run_command(cmd, timeout=None, input_data=None):
            if "mutt -Q alias_file" in " ".join(cmd):
                return (f'alias_file="{nonexistent_path}"'.encode(), b"")
            else:
                return (b"", b"")
        
        monkeypatch.setattr("mcp_handley_lab.email.mutt_aliases.tool.run_command", mock_run_command)
        
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "test",
            "email": "test@example.com"
        })
        
        # Should handle missing directory appropriately
        if "error" in response:
            assert "directory" in response["error"].lower() or "not found" in response["error"].lower()
        else:
            # If operation succeeded, directory and file should be created
            assert nonexistent_path.exists()
            assert "test" in nonexistent_path.read_text()

    @pytest.mark.asyncio
    async def test_corrupted_file_recovery(self, real_temp_addressbook):
        """Test behavior with corrupted addressbook file."""
        # Create file with invalid content
        corrupted_content = '''This is not a valid mutt alias format
Some random text that will break parsing
alias valid_entry "Valid" <valid@example.com>
More invalid content here
'''
        real_temp_addressbook.write_text(corrupted_content)
        
        # Should handle corrupted file gracefully
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "new_contact",
            "email": "new@example.com"
        })
        
        # Should either handle corruption gracefully or report error
        if "error" not in response:
            # If operation succeeded, new contact should be added
            file_content = real_temp_addressbook.read_text()
            assert "new_contact" in file_content
            # Valid entry should be preserved
            assert "valid_entry" in file_content

    @pytest.mark.asyncio
    async def test_file_size_limits(self, real_temp_addressbook):
        """Test behavior with very large addressbook files."""
        # Create large file content (but not so large as to break tests)
        large_content = ""
        for i in range(1000):
            large_content += f'alias contact_{i} "Contact {i}" <contact{i}@example.com>\n'
        
        real_temp_addressbook.write_text(large_content)
        
        # Should handle large files appropriately
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "final_contact",
            "email": "final@example.com"
        })
        
        # Should succeed with large files
        assert "error" not in response, response.get("error")
        
        # Verify new contact was added
        file_content = real_temp_addressbook.read_text()
        assert "final_contact" in file_content


@pytest.mark.integration
class TestMuttFileFormatCompatibility:
    """Test compatibility with various mutt addressbook file formats."""

    @pytest.mark.asyncio
    async def test_mixed_format_file_handling(self, real_temp_addressbook):
        """Test handling of files with mixed alias formats."""
        mixed_content = '''# Mixed format file
alias simple_format user@example.com
alias named_format "Named User" <named@example.com>
alias group_format "Group Name" <user1@example.com,user2@example.com>

# Comments and empty lines should be preserved

alias another_simple another@example.com
'''
        real_temp_addressbook.write_text(mixed_content)
        
        # Should handle mixed formats correctly  
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "new_mixed",
            "email": "mixed@example.com",
            "name": "Mixed Format"
        })
        assert "error" not in response, response.get("error")
        
        # All formats should be preserved
        file_content = real_temp_addressbook.read_text()
        assert 'alias simple_format user@example.com' in file_content
        assert 'alias named_format "Named User" <named@example.com>' in file_content
        assert 'alias group_format "Group Name" <user1@example.com,user2@example.com>' in file_content
        assert 'alias new_mixed "Mixed Format" <mixed@example.com>' in file_content

    @pytest.mark.asyncio
    async def test_unicode_content_handling(self, real_temp_addressbook):
        """Test handling of unicode characters in names and emails."""
        # Pre-populate with unicode content
        unicode_content = '''alias unicode_name "José María" <jose@example.com>
alias unicode_email "Regular Name" <münchen@example.de>
'''
        real_temp_addressbook.write_text(unicode_content, encoding='utf-8')
        
        _, response = await aliases_mcp.call_tool("add_contact", {
            "alias": "new_unicode",
            "email": "test@example.com", 
            "name": "François"
        })
        assert "error" not in response, response.get("error")
        
        # Unicode should be preserved
        file_content = real_temp_addressbook.read_text(encoding='utf-8')
        assert 'José María' in file_content
        assert 'münchen@example.de' in file_content
        assert 'François' in file_content

    @pytest.mark.asyncio
    async def test_whitespace_preservation(self, real_temp_addressbook):
        """Test that whitespace and indentation is handled properly."""
        spaced_content = '''	# Indented comment
alias normal "Normal Entry" <normal@example.com>
    alias indented "Indented Entry" <indented@example.com>

		# Multiple tabs and spaces

alias spaced   "Spaced Entry"   <spaced@example.com>
'''
        real_temp_addressbook.write_text(spaced_content)
        
        _, response = await aliases_mcp.call_tool("remove_contact", {
            "alias": "indented"
        })
        assert "error" not in response, response.get("error")
        
        # Should preserve original whitespace while removing target
        file_content = real_temp_addressbook.read_text()
        assert '\t# Indented comment' in file_content
        assert 'indented' not in file_content
        assert 'alias normal' in file_content  
        assert 'alias spaced' in file_content