"""Unit tests for Mutt filesystem operations in isolation.

Tests address book file manipulation without CLI interaction.
Focuses on pure file I/O logic, parsing, and data transformation.
"""
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from mcp_handley_lab.email.mutt_aliases.tool import (
    _find_contact_fuzzy,
    _get_all_contacts,
    _parse_alias_line,
)
from mcp_handley_lab.shared.models import MuttContact


class TestMuttAliasFileParsing:
    """Test address book file parsing logic in isolation."""

    def test_parse_alias_line_individual_contact(self):
        """Test parsing individual contact alias lines."""
        line = 'alias john_doe "John Doe" <john@example.com>'
        result = _parse_alias_line(line)

        assert isinstance(result, MuttContact)
        assert result.alias == "john_doe"
        assert result.name == "John Doe"
        assert result.email == "john@example.com"

    def test_parse_alias_line_simple_format(self):
        """Test parsing simple alias format without name."""
        line = "alias simple test@example.com"
        result = _parse_alias_line(line)

        assert isinstance(result, MuttContact)
        assert result.alias == "simple"
        assert result.name == ""
        assert result.email == "test@example.com"

    def test_parse_alias_line_group_contact(self):
        """Test parsing group contact with multiple emails."""
        line = 'alias team "Project Team" <alice@example.com,bob@example.com>'
        result = _parse_alias_line(line)

        assert isinstance(result, MuttContact)
        assert result.alias == "team"
        assert result.name == "Project Team"
        assert result.email == "alice@example.com,bob@example.com"

    def test_parse_alias_line_invalid_format(self):
        """Test handling of invalid alias line formats."""
        invalid_lines = [
            "not an alias line",
            "alias",  # No email
            "# comment line",
            "",  # Empty line
            "alias incomplete",  # Incomplete format
        ]

        for line in invalid_lines:
            with pytest.raises(ValueError):
                _parse_alias_line(line)

    def test_parse_alias_line_special_characters(self):
        """Test parsing aliases with special characters in names/emails."""
        line = 'alias test_user "Test User (Manager)" <test.user+work@example.com>'
        result = _parse_alias_line(line)

        assert isinstance(result, MuttContact)
        assert result.alias == "test_user"
        assert result.name == "Test User (Manager)"
        assert result.email == "test.user+work@example.com"


class TestMuttAddressBookReading:
    """Test address book file reading operations."""

    def test_get_all_contacts_mixed_formats(self):
        """Test reading address book with mixed alias formats."""
        file_content = """# Comment line
alias john_doe "John Doe" <john@example.com>
alias simple test@example.com

# Another comment
alias team "Project Team" <alice@example.com,bob@example.com>
invalid line that should be ignored
alias another_simple another@example.com
"""

        with patch("builtins.open", mock_open(read_data=file_content)), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                contacts = _get_all_contacts()

        # Should parse only valid alias lines
        assert len(contacts) == 4

        # Check first contact (named format)
        assert contacts[0].alias == "john_doe"
        assert contacts[0].name == "John Doe"
        assert contacts[0].email == "john@example.com"

        # Check second contact (simple format)
        assert contacts[1].alias == "simple"
        assert contacts[1].name == ""
        assert contacts[1].email == "test@example.com"

        # Check third contact (group format)
        assert contacts[2].alias == "team"
        assert contacts[2].name == "Project Team"
        assert contacts[2].email == "alice@example.com,bob@example.com"

    def test_get_all_contacts_empty_file(self):
        """Test reading empty address book file."""
        with patch("builtins.open", mock_open(read_data="")), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                contacts = _get_all_contacts()

        assert contacts == []

    def test_get_all_contacts_comments_only(self):
        """Test reading file with only comments and empty lines."""
        file_content = """# This is a comment
# Another comment

# Yet another comment
"""

        with patch("builtins.open", mock_open(read_data=file_content)), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                contacts = _get_all_contacts()

        assert contacts == []

    def test_get_all_contacts_nonexistent_file(self):
        """Test behavior when address book file doesn't exist."""
        with patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/nonexistent/path")
            with patch.object(Path, "exists", return_value=False):
                contacts = _get_all_contacts()

        assert contacts == []


class TestMuttFuzzySearch:
    """Test fuzzy contact search logic."""

    def test_find_contact_fuzzy_exact_match(self):
        """Test exact alias match in fuzzy search."""
        file_content = """alias john_doe "John Doe" <john@example.com>
alias jane_smith "Jane Smith" <jane@example.com>
"""

        with patch("builtins.open", mock_open(read_data=file_content)), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                matches = _find_contact_fuzzy("john_doe")

        assert len(matches) == 1
        assert matches[0].alias == "john_doe"

    def test_find_contact_fuzzy_partial_alias(self):
        """Test partial alias matching."""
        file_content = """alias john_doe "John Doe" <john@example.com>
alias john_smith "John Smith" <john.smith@example.com>
alias jane_doe "Jane Doe" <jane@example.com>
"""

        with patch("builtins.open", mock_open(read_data=file_content)), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                matches = _find_contact_fuzzy("john")

        # Should find both john_doe and john_smith
        assert len(matches) == 2
        aliases = [m.alias for m in matches]
        assert "john_doe" in aliases
        assert "john_smith" in aliases

    def test_find_contact_fuzzy_name_match(self):
        """Test matching by name content."""
        file_content = """alias jdoe "John Doe" <john@example.com>
alias jsmith "John Smith" <john.smith@example.com>
alias manager "Jane Doe" <jane@example.com>
"""

        with patch("builtins.open", mock_open(read_data=file_content)), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                matches = _find_contact_fuzzy("doe")

        # Should find both John Doe and Jane Doe
        assert len(matches) == 2
        names = [m.name for m in matches]
        assert "John Doe" in names
        assert "Jane Doe" in names

    def test_find_contact_fuzzy_email_match(self):
        """Test matching by email content."""
        file_content = """alias work_john "John Doe" <john@company.com>
alias personal_john "John Doe" <john@personal.com>
alias jane "Jane Smith" <jane@company.com>
"""

        with patch("builtins.open", mock_open(read_data=file_content)), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                matches = _find_contact_fuzzy("company")

        # Should find both company email addresses
        assert len(matches) == 2
        emails = [m.email for m in matches]
        assert "john@company.com" in emails
        assert "jane@company.com" in emails

    def test_find_contact_fuzzy_case_insensitive(self):
        """Test case-insensitive fuzzy matching."""
        file_content = 'alias john_doe "John Doe" <john@example.com>'

        with patch("builtins.open", mock_open(read_data=file_content)), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                # Test different case variations
                for query in ["JOHN", "John", "john", "DOE", "Doe", "doe"]:
                    matches = _find_contact_fuzzy(query)
                    assert len(matches) == 1
                    assert matches[0].alias == "john_doe"

    def test_find_contact_fuzzy_no_matches(self):
        """Test fuzzy search with no matches."""
        file_content = 'alias john_doe "John Doe" <john@example.com>'

        with patch("builtins.open", mock_open(read_data=file_content)), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                matches = _find_contact_fuzzy("nonexistent")

        assert matches == []

    def test_find_contact_fuzzy_max_results_limit(self):
        """Test max_results parameter limits results."""
        # Create many matching contacts
        file_content = "\n".join(
            [f'alias test_{i} "Test User {i}" <test{i}@example.com>' for i in range(20)]
        )

        with patch("builtins.open", mock_open(read_data=file_content)), patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=True):
                matches = _find_contact_fuzzy("test", max_results=5)

        assert len(matches) == 5

    def test_find_contact_fuzzy_empty_contact_list(self):
        """Test fuzzy search with empty contact list."""
        with patch(
            "mcp_handley_lab.email.mutt_aliases.tool.get_mutt_alias_file"
        ) as mock_alias_file:
            mock_alias_file.return_value = Path("/fake/path")
            with patch.object(Path, "exists", return_value=False):
                matches = _find_contact_fuzzy("anything")

        assert matches == []


class TestMuttFileOperations:
    """Test file writing and manipulation operations."""

    def test_contact_file_writing_pattern(self):
        """Test the pattern used for writing contacts to files.

        This tests the expected format without actual file I/O.
        """
        # Test individual contact format
        individual_line = 'alias john_doe "John Doe" <john@example.com>'
        parsed = _parse_alias_line(individual_line)
        assert parsed.alias == "john_doe"

        # Test simple contact format
        simple_line = "alias simple test@example.com"
        parsed = _parse_alias_line(simple_line)
        assert parsed.name == ""  # No name in simple format

        # Test group contact format
        group_line = 'alias team "Project Team" <alice@example.com,bob@example.com>'
        parsed = _parse_alias_line(group_line)
        assert "," in parsed.email  # Multiple emails

    def test_file_content_preservation(self):
        """Test that non-alias lines are preserved during file operations."""
        # This would test the pattern used in actual file manipulation
        original_content = """# Important comment
alias keep_me "Keep Me" <keep@example.com>
# Another comment
alias remove_me "Remove Me" <remove@example.com>

# Final comment
"""

        # Simulate removing the 'remove_me' alias
        lines = original_content.split("\n")
        filtered_lines = [line for line in lines if "remove_me" not in line]
        result_content = "\n".join(filtered_lines)

        # Should preserve comments and other aliases
        assert "# Important comment" in result_content
        assert "keep_me" in result_content
        assert "remove_me" not in result_content
        assert "# Final comment" in result_content
