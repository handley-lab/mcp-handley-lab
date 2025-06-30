"""Tests for mutt tool."""
import pytest
from unittest.mock import Mock, patch, mock_open
import tempfile
import os
from pathlib import Path

from mcp_handley_lab.mutt.tool import (
    add_contact, 
    list_contacts, 
    remove_contact,
    list_folders,
    server_info
)


class TestMuttContactManagement:
    """Test mutt contact management functions."""
    
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    def test_add_contact_individual(self, mock_home, mock_file):
        """Test adding an individual contact."""
        mock_home.return_value = Path("/home/test")
        
        result = add_contact("john_doe", "john@example.com", "John Doe")
        
        assert "Added contact: john_doe (John Doe)" in result
        mock_file.assert_called_once()
        mock_file().write.assert_called_once_with('alias john_doe "John Doe" <john@example.com>\n')
    
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    def test_add_contact_group(self, mock_home, mock_file):
        """Test adding a group contact."""
        mock_home.return_value = Path("/home/test")
        
        result = add_contact("gw_team", "alice@cam.ac.uk,bob@cam.ac.uk", "GW Project Team")
        
        assert "Added contact: gw_team (GW Project Team)" in result
        mock_file().write.assert_called_once_with('alias gw_team "GW Project Team" <alice@cam.ac.uk,bob@cam.ac.uk>\n')
    
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    def test_add_contact_no_name(self, mock_home, mock_file):
        """Test adding contact without name."""
        mock_home.return_value = Path("/home/test")
        
        result = add_contact("simple", "test@example.com")
        
        assert "Added contact: simple (test@example.com)" in result
        mock_file().write.assert_called_once_with('alias simple test@example.com\n')
    
    def test_add_contact_validation(self):
        """Test input validation for add_contact."""
        with pytest.raises(ValueError, match="Both alias and email are required"):
            add_contact("", "test@example.com")
        
        with pytest.raises(ValueError, match="Both alias and email are required"):
            add_contact("test", "")
    
    @patch("builtins.open", new_callable=mock_open, read_data='alias john_doe "John Doe" <john@example.com>\nalias gw_team "GW Team" <alice@cam.ac.uk>\n')
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    def test_list_contacts_all(self, mock_home, mock_exists, mock_file):
        """Test listing all contacts."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = True
        
        result = list_contacts()
        
        assert "Mutt contacts:" in result
        assert "alias john_doe" in result
        assert "alias gw_team" in result
    
    @patch("builtins.open", new_callable=mock_open, read_data='alias john_doe "John Doe" <john@example.com>\nalias gw_team "GW Team" <alice@cam.ac.uk>\n')
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    def test_list_contacts_filtered(self, mock_home, mock_exists, mock_file):
        """Test listing contacts with pattern filter."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = True
        
        result = list_contacts(pattern="gw")
        
        assert "Mutt contacts:" in result
        assert "alias gw_team" in result
        assert "alias john_doe" not in result
    
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    def test_list_contacts_no_file(self, mock_home, mock_exists):
        """Test listing contacts when no file exists."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = False
        
        result = list_contacts()
        
        assert "No mutt alias file found" in result
    
    @patch("builtins.open", new_callable=mock_open, read_data='alias john_doe "John Doe" <john@example.com>\nalias gw_team "GW Team" <alice@cam.ac.uk>\n')
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    def test_remove_contact_success(self, mock_home, mock_exists, mock_file):
        """Test successfully removing a contact."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = True
        
        # Mock readlines and write
        mock_file.return_value.readlines.return_value = [
            'alias john_doe "John Doe" <john@example.com>\n',
            'alias gw_team "GW Team" <alice@cam.ac.uk>\n'
        ]
        
        result = remove_contact("john_doe")
        
        assert "Removed contact: john_doe" in result
        # Should write back only the gw_team line
        mock_file.return_value.writelines.assert_called_once_with(['alias gw_team "GW Team" <alice@cam.ac.uk>\n'])
    
    @patch("mcp_handley_lab.mutt.tool._find_contact_fuzzy")
    @patch("builtins.open", new_callable=mock_open, read_data='alias gw_team "GW Team" <alice@cam.ac.uk>\n')
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    def test_remove_contact_not_found(self, mock_home, mock_exists, mock_file, mock_fuzzy):
        """Test removing a contact that doesn't exist."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = True
        
        mock_file.return_value.readlines.return_value = ['alias gw_team "GW Team" <alice@cam.ac.uk>\n']
        mock_fuzzy.return_value = []  # No fuzzy matches found
        
        result = remove_contact("nonexistent")
        
        assert "Contact 'nonexistent' not found" in result
    
    def test_remove_contact_validation(self):
        """Test input validation for remove_contact."""
        with pytest.raises(ValueError, match="Alias is required"):
            remove_contact("")


class TestMuttFolderManagement:
    """Test mutt folder management functions."""
    
    @patch("subprocess.run")
    def test_list_folders_success(self, mock_run):
        """Test successfully listing folders."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = 'mailboxes="INBOX Sent Archive Trash Projects/GW"'
        
        result = list_folders()
        
        assert "Available mailboxes:" in result
        assert "- INBOX" in result
        assert "- Projects/GW" in result
    
    @patch("subprocess.run")
    def test_list_folders_no_config(self, mock_run):
        """Test listing folders when no config found."""
        mock_run.return_value.returncode = 1
        
        result = list_folders()
        
        assert "Could not retrieve mailbox list" in result
    
    @patch("subprocess.run")
    def test_list_folders_empty(self, mock_run):
        """Test listing folders when no mailboxes configured."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = 'mailboxes=""'
        
        result = list_folders()
        
        assert "No mailboxes found" in result


class TestMuttServerInfo:
    """Test mutt server info function."""
    
    @patch("subprocess.run")
    def test_server_info_success(self, mock_run):
        """Test successful server info retrieval."""
        mock_run.return_value.stdout = "Mutt 2.2.14 (516568dc) (2025-02-20)\nOther info..."
        
        result = server_info()
        
        assert "Mutt Tool Server Status" in result
        assert "Mutt 2.2.14" in result
        assert "compose_email" in result
        assert "add_contact" in result
    
    @patch("subprocess.run")
    def test_server_info_mutt_not_found(self, mock_run):
        """Test server info when mutt not installed."""
        mock_run.side_effect = FileNotFoundError()
        
        with pytest.raises(RuntimeError, match="mutt command not found"):
            server_info()


class TestMuttContactWorkflows:
    """Test real-world contact management workflows."""
    
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.home")
    def test_gw_project_workflow(self, mock_home, mock_file):
        """Test adding GW project team contact."""
        mock_home.return_value = Path("/home/test")
        
        # Add GW team
        result = add_contact(
            "gw_team", 
            "alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk",
            "GW Project Team"
        )
        
        assert "Added contact: gw_team (GW Project Team)" in result
        
        # Verify the alias format is correct for mutt
        expected_alias = 'alias gw_team "GW Project Team" <alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk>\n'
        mock_file().write.assert_called_once_with(expected_alias)
    
    @patch("builtins.open", new_callable=mock_open, read_data='alias gw_team "GW Team" <alice@cam.ac.uk,bob@cam.ac.uk>\nalias research_group "Research" <prof@cam.ac.uk>\n')
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.home")
    def test_project_contact_discovery(self, mock_home, mock_exists, mock_file):
        """Test finding project-related contacts."""
        mock_home.return_value = Path("/home/test")
        mock_exists.return_value = True
        
        # Search for GW-related contacts
        result = list_contacts(pattern="gw")
        
        assert "alias gw_team" in result
        assert "alias research_group" not in result
        
        # Search for research contacts
        result = list_contacts(pattern="research")
        
        assert "alias research_group" in result
        assert "alias gw_team" not in result