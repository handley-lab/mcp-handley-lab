"""End-to-end workflow integration tests for Mutt.

Tests complete workflows combining CLI + filesystem operations.
Focuses on real-world usage scenarios and cross-component integration.
"""

import pytest

from mcp_handley_lab.email.mutt.tool import mcp as mutt_mcp
from mcp_handley_lab.email.mutt_aliases.tool import mcp as aliases_mcp


@pytest.fixture
def full_mutt_workflow_environment(tmp_path, monkeypatch):
    """Create complete mutt environment for end-to-end workflow testing."""
    # Create temp mutt directory structure
    mutt_dir = tmp_path / ".mutt"
    mutt_dir.mkdir()

    # Create addressbook file
    addressbook = mutt_dir / "addressbook"
    addressbook.touch()

    # Create mutt configuration file
    muttrc = mutt_dir / "muttrc"
    muttrc.write_text(
        f"""
# Test mutt configuration
set alias_file="{addressbook}"
set folder="~/Mail"
set record="~/Mail/sent"
set postponed="~/Mail/drafts"
set spoolfile="~/Mail/inbox"

# Test mailboxes
mailboxes "INBOX" "Sent" "Drafts" "Trash" "Archive"
"""
    )

    # Mock CLI commands to use our test environment
    def mock_run_command(cmd, timeout=None, input_data=None):
        if "mutt -Q alias_file" in " ".join(cmd):
            return (f'alias_file="{addressbook}"'.encode(), b"")
        elif "mutt -Q mailboxes" in " ".join(cmd):
            return (b'mailboxes="INBOX Sent Drafts Trash Archive"', b"")
        elif "mutt -v" in " ".join(cmd):
            return (b"Mutt 2.2.14 (test) (2025-01-01)\n", b"")
        else:
            return (b"", b"")

    # Patch both tools
    monkeypatch.setattr(
        "mcp_handley_lab.email.mutt_aliases.tool.run_command", mock_run_command
    )
    monkeypatch.setattr("mcp_handley_lab.email.mutt.tool.run_command", mock_run_command)

    return {"mutt_dir": mutt_dir, "addressbook": addressbook, "muttrc": muttrc}


@pytest.mark.integration
class TestMuttContactWorkflows:
    """Test complete contact management workflows."""

    @pytest.mark.asyncio
    async def test_gw_project_contact_workflow(self, full_mutt_workflow_environment):
        """Test complete GW project contact management workflow."""
        env = full_mutt_workflow_environment

        # Step 1: Add core team members
        team_members = [
            ("alice_gw", "alice@cam.ac.uk", "Alice Smith"),
            ("bob_gw", "bob@cam.ac.uk", "Bob Johnson"),
            ("carol_gw", "carol@cam.ac.uk", "Carol Wilson"),
        ]

        for alias, email, name in team_members:
            _, response = await aliases_mcp.call_tool(
                "add_contact", {"alias": alias, "email": email, "name": name}
            )
            assert "error" not in response, response.get("error")

        # Step 2: Create team distribution list
        team_emails = ",".join([email for _, email, _ in team_members])
        _, response = await aliases_mcp.call_tool(
            "add_contact",
            {"alias": "gw_team", "email": team_emails, "name": "GW Project Team"},
        )
        assert "error" not in response, response.get("error")

        # Step 3: Verify all contacts in addressbook
        addressbook_content = env["addressbook"].read_text()
        for alias, email, name in team_members:
            assert alias in addressbook_content
            assert email in addressbook_content
            assert name in addressbook_content

        # Verify team list
        assert 'alias gw_team "GW Project Team"' in addressbook_content
        assert team_emails in addressbook_content

        # Step 4: Test contact lookup/search workflow
        _, search_response = await aliases_mcp.call_tool(
            "find_contact", {"query": "gw"}
        )
        assert "error" not in search_response, search_response.get("error")
        results = search_response["matches"]

        # Should find all GW-related contacts
        found_aliases = [contact["alias"] for contact in results]
        assert "alice_gw" in found_aliases
        assert "bob_gw" in found_aliases
        assert "carol_gw" in found_aliases
        assert "gw_team" in found_aliases

    @pytest.mark.asyncio
    async def test_contact_lifecycle_workflow(self, full_mutt_workflow_environment):
        """Test complete contact lifecycle: add, update, search, remove."""
        env = full_mutt_workflow_environment

        # Phase 1: Add initial contacts
        initial_contacts = [
            ("john_doe", "john@company.com", "John Doe"),
            ("jane_smith", "jane@company.com", "Jane Smith"),
            ("project_leads", "john@company.com,jane@company.com", "Project Leads"),
        ]

        for alias, email, name in initial_contacts:
            _, response = await aliases_mcp.call_tool(
                "add_contact", {"alias": alias, "email": email, "name": name}
            )
            assert "error" not in response, response.get("error")

        # Phase 2: Verify searchability
        _, search_response = await aliases_mcp.call_tool(
            "find_contact", {"query": "company"}
        )
        assert "error" not in search_response, search_response.get("error")
        results = search_response["matches"]

        # Should find all company contacts
        assert len(results) >= 3
        company_aliases = [contact["alias"] for contact in results]
        assert "john_doe" in company_aliases
        assert "jane_smith" in company_aliases
        assert "project_leads" in company_aliases

        # Phase 3: Remove individual contact (simulating person leaving)
        _, remove_response = await aliases_mcp.call_tool(
            "remove_contact", {"alias": "john_doe"}
        )
        assert "error" not in remove_response, remove_response.get("error")

        # Phase 4: Verify removal and remaining contacts
        addressbook_content = env["addressbook"].read_text()
        assert "john_doe" not in addressbook_content
        assert "jane_smith" in addressbook_content
        assert "project_leads" in addressbook_content  # Group should remain

        # Phase 5: Update group to remove departed member
        _, update_response = await aliases_mcp.call_tool(
            "remove_contact", {"alias": "project_leads"}
        )
        assert "error" not in update_response, update_response.get("error")

        # Re-add updated group
        _, add_response = await aliases_mcp.call_tool(
            "add_contact",
            {
                "alias": "project_leads",
                "email": "jane@company.com",
                "name": "Project Leads",
            },
        )
        assert "error" not in add_response, add_response.get("error")

        # Final verification
        final_content = env["addressbook"].read_text()
        assert "john_doe" not in final_content
        assert "jane_smith" in final_content
        assert 'alias project_leads "Project Leads" <jane@company.com>' in final_content

    @pytest.mark.asyncio
    async def test_mutt_integration_workflow(self, full_mutt_workflow_environment):
        """Test workflow integrating mutt tool with contact management."""
        env = full_mutt_workflow_environment

        # Step 1: Set up contacts for email workflow
        _, response = await aliases_mcp.call_tool(
            "add_contact",
            {
                "alias": "support",
                "email": "support@company.com",
                "name": "Support Team",
            },
        )
        assert "error" not in response, response.get("error")

        # Step 2: Test server info integration
        _, server_response = await mutt_mcp.call_tool("server_info", {})
        assert "error" not in server_response, server_response.get("error")
        server_info = server_response

        assert server_info["name"] == "Mutt Tool"
        assert server_info["status"] == "active"
        assert "Mutt" in server_info["version"]

        # Step 3: Test folder listing integration
        _, folder_response = await mutt_mcp.call_tool("list_folders", {})
        assert "error" not in folder_response, folder_response.get("error")
        folders = folder_response["result"]

        # Should include configured folders
        assert isinstance(folders, list)
        assert "INBOX" in folders
        assert "Sent" in folders
        assert "Drafts" in folders

        # Step 4: Verify contact is available for email workflows
        addressbook_content = env["addressbook"].read_text()
        assert (
            'alias support "Support Team" <support@company.com>' in addressbook_content
        )


@pytest.mark.integration
class TestMuttErrorRecoveryWorkflows:
    """Test error recovery and resilience workflows."""

    @pytest.mark.asyncio
    async def test_contact_conflict_resolution_workflow(
        self, full_mutt_workflow_environment
    ):
        """Test workflow for handling contact conflicts and duplicates."""
        env = full_mutt_workflow_environment

        # Step 1: Add initial contact
        _, response = await aliases_mcp.call_tool(
            "add_contact",
            {"alias": "john", "email": "john@oldcompany.com", "name": "John Old"},
        )
        assert "error" not in response, response.get("error")

        # Step 2: Try to add conflicting contact with same alias
        _, conflict_response = await aliases_mcp.call_tool(
            "add_contact",
            {"alias": "john", "email": "john@newcompany.com", "name": "John New"},
        )

        # Should handle conflict (either error or update)
        if "error" in conflict_response:
            # If tool prevents duplicates, that's valid
            assert (
                "exist" in conflict_response["error"].lower()
                or "duplicate" in conflict_response["error"].lower()
            )
        else:
            # If tool updates/appends, verify behavior
            addressbook_content = env["addressbook"].read_text()
            # Should handle the conflict appropriately
            assert "john" in addressbook_content

        # Step 3: Resolution - remove old contact first
        _, remove_response = await aliases_mcp.call_tool(
            "remove_contact", {"alias": "john"}
        )
        assert "error" not in remove_response, remove_response.get("error")

        # Step 4: Add new contact
        _, new_response = await aliases_mcp.call_tool(
            "add_contact",
            {"alias": "john", "email": "john@newcompany.com", "name": "John New"},
        )
        assert "error" not in new_response, new_response.get("error")

        # Final verification
        final_content = env["addressbook"].read_text()
        assert "john@newcompany.com" in final_content
        assert "john@oldcompany.com" not in final_content

    @pytest.mark.asyncio
    async def test_batch_contact_operations_workflow(
        self, full_mutt_workflow_environment
    ):
        """Test workflow for batch contact operations."""
        env = full_mutt_workflow_environment

        # Step 1: Batch add multiple contacts
        contacts_to_add = [
            ("dept_head", "head@dept.edu", "Department Head"),
            ("secretary", "secretary@dept.edu", "Department Secretary"),
            ("researcher1", "r1@dept.edu", "Researcher One"),
            ("researcher2", "r2@dept.edu", "Researcher Two"),
            ("researcher3", "r3@dept.edu", "Researcher Three"),
        ]

        added_contacts = []
        for alias, email, name in contacts_to_add:
            _, response = await aliases_mcp.call_tool(
                "add_contact", {"alias": alias, "email": email, "name": name}
            )
            if "error" not in response:
                added_contacts.append(alias)
            else:
                # Log but continue with batch operation
                print(f"Warning: Failed to add {alias}: {response.get('error')}")

        # Step 2: Verify batch addition
        addressbook_content = env["addressbook"].read_text()
        for alias in added_contacts:
            assert alias in addressbook_content

        # Step 3: Batch search verification
        _, search_response = await aliases_mcp.call_tool(
            "find_contact", {"query": "dept"}
        )
        assert "error" not in search_response, search_response.get("error")
        results = search_response["matches"]

        # Should find all department contacts
        found_aliases = [contact["alias"] for contact in results]
        for alias in added_contacts:
            if "dept" in alias or "dept.edu" in env["addressbook"].read_text():
                assert alias in found_aliases or any(
                    "dept" in contact["email"] for contact in results
                )

        # Step 4: Create department distribution list
        dept_emails = ",".join([email for _, email, _ in contacts_to_add])
        _, group_response = await aliases_mcp.call_tool(
            "add_contact",
            {"alias": "dept_all", "email": dept_emails, "name": "Department All"},
        )
        assert "error" not in group_response, group_response.get("error")

        # Final verification of complete workflow
        final_content = env["addressbook"].read_text()
        assert "dept_all" in final_content
        assert dept_emails in final_content


@pytest.mark.integration
class TestMuttCrossComponentWorkflows:
    """Test workflows that span multiple mutt tool components."""

    @pytest.mark.asyncio
    async def test_email_composition_preparation_workflow(
        self, full_mutt_workflow_environment
    ):
        """Test preparing contacts for email composition workflow."""
        env = full_mutt_workflow_environment

        # Step 1: Set up contacts for various email scenarios
        email_contacts = [
            ("urgent_contact", "urgent@example.com", "Urgent Contact"),
            ("cc_list", "cc1@example.com,cc2@example.com", "CC List"),
            ("bcc_admin", "admin@example.com", "BCC Admin"),
        ]

        for alias, email, name in email_contacts:
            _, response = await aliases_mcp.call_tool(
                "add_contact", {"alias": alias, "email": email, "name": name}
            )
            assert "error" not in response, response.get("error")

        # Step 2: Verify contacts are available for email tools
        addressbook_content = env["addressbook"].read_text()
        for alias, email, name in email_contacts:
            assert alias in addressbook_content
            assert email in addressbook_content
            assert name in addressbook_content

        # Step 3: Test that folder structure is ready
        _, folder_response = await mutt_mcp.call_tool("list_folders", {})
        assert "error" not in folder_response, folder_response.get("error")
        folders = folder_response["result"]

        # Essential folders should be available
        essential_folders = ["INBOX", "Sent", "Drafts"]
        for folder in essential_folders:
            assert folder in folders

        # Step 4: Test server readiness for email operations
        _, server_response = await mutt_mcp.call_tool("server_info", {})
        assert "error" not in server_response, server_response.get("error")
        server_info = server_response

        assert server_info["status"] == "active"
        assert "compose" in server_info["capabilities"]

    @pytest.mark.asyncio
    async def test_contact_backup_recovery_workflow(
        self, full_mutt_workflow_environment
    ):
        """Test workflow for contact backup and recovery scenarios."""
        env = full_mutt_workflow_environment

        # Step 1: Create initial contact set
        important_contacts = [
            ("critical1", "critical1@important.com", "Critical Contact 1"),
            ("critical2", "critical2@important.com", "Critical Contact 2"),
            ("backup_admin", "admin@backup.com", "Backup Admin"),
        ]

        for alias, email, name in important_contacts:
            _, response = await aliases_mcp.call_tool(
                "add_contact", {"alias": alias, "email": email, "name": name}
            )
            assert "error" not in response, response.get("error")

        # Step 2: Create backup of addressbook content
        original_content = env["addressbook"].read_text()
        backup_content = original_content

        # Step 3: Simulate accidental deletion
        _, remove_response = await aliases_mcp.call_tool(
            "remove_contact", {"alias": "critical1"}
        )
        assert "error" not in remove_response, remove_response.get("error")

        # Verify deletion
        current_content = env["addressbook"].read_text()
        assert "critical1" not in current_content
        assert "critical2" in current_content  # Others should remain

        # Step 4: Recovery simulation - restore from backup
        env["addressbook"].write_text(backup_content)

        # Step 5: Verify recovery
        recovered_content = env["addressbook"].read_text()
        for alias, email, name in important_contacts:
            assert alias in recovered_content
            assert email in recovered_content
            assert name in recovered_content

        # Step 6: Test that tools still work after recovery
        _, search_response = await aliases_mcp.call_tool(
            "find_contact", {"query": "critical"}
        )
        assert "error" not in search_response, search_response.get("error")
        results = search_response["matches"]

        critical_aliases = [contact["alias"] for contact in results]
        assert "critical1" in critical_aliases
        assert "critical2" in critical_aliases
