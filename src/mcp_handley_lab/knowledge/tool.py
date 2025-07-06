"""Knowledge management tool for personal knowledge bases."""
from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import constr

from .manager import KnowledgeManager

mcp = FastMCP("Knowledge Management Tool")

# Global knowledge manager instance
knowledge_manager = KnowledgeManager()


# MCP Resources for read-only access
@mcp.resource("knowledge://")
def list_knowledge_types() -> str:
    """List available knowledge types in the knowledge base."""
    entries = knowledge_manager.list_entries()

    if not entries:
        return "No knowledge entries found. Create some entries first."

    # Count by type
    type_counts = {}
    for entry in entries:
        type_counts[entry.type] = type_counts.get(entry.type, 0) + 1

    result = "**Available Knowledge Types:**\n\n"
    for entry_type, count in sorted(type_counts.items()):
        result += f"- **{entry_type}**: {count} entries\n"
        result += f"  Access with: `knowledge://{entry_type}`\n\n"

    result += "**Quick Access:**\n"
    result += "- `knowledge://people` - All people\n"
    result += "- `knowledge://projects` - All projects\n"
    result += "- `knowledge://search?q=QUERY` - Search entries\n"

    return result


@mcp.resource("knowledge://{entry_type}")
def list_entries_by_type(entry_type: str) -> str:
    """List all entries of a specific type."""
    entries = knowledge_manager.list_entries(entry_type=entry_type)

    if not entries:
        return f"No {entry_type} entries found."

    result = f"**{entry_type.title()} Entries** ({len(entries)} found)\n\n"

    for entry in sorted(entries, key=lambda x: x.name):
        result += f"**{entry.name}** (ID: {entry.id})\n"

        # Show key fields based on type
        if entry_type == "person":
            # Show current roles and email
            if hasattr(entry, "get_current_roles"):
                current_roles = entry.get_current_roles()
                if current_roles:
                    roles = [r.get("role", "unknown") for r in current_roles]
                    result += f"  Current Role: {', '.join(set(roles))}\n"

            email = entry.get_field("email")
            if email:
                result += f"  Email: {email}\n"

        elif entry_type == "project":
            # Show status and participants
            status = entry.get_field("status", "unknown")
            result += f"  Status: {status}\n"

            if hasattr(entry, "get_participants"):
                participants = entry.get_participants()
                if participants:
                    result += f"  Participants: {', '.join(participants[:3])}"
                    if len(participants) > 3:
                        result += f" (+{len(participants) - 3} more)"
                    result += "\n"

        # Show tags
        if entry.tags:
            result += f"  Tags: {', '.join(entry.tags)}\n"

        result += f"  Access: `knowledge://{entry_type}/{entry.id}`\n\n"

    return result


@mcp.resource("knowledge://{entry_type}/{entry_id}")
def get_entry_details(entry_type: str, entry_id: str) -> str:
    """Get detailed information about a specific entry."""
    entry = knowledge_manager.get_entry(entry_id)

    if not entry:
        return f"Entry {entry_id} not found."

    if entry.type != entry_type:
        return f"Entry {entry_id} is of type '{entry.type}', not '{entry_type}'."

    result = f"# {entry.name}\n\n"
    result += f"**Type:** {entry.type}  \n"
    result += f"**ID:** {entry.id}  \n"
    result += f"**Created:** {entry.created_at.strftime('%Y-%m-%d %H:%M')}  \n"
    result += f"**Updated:** {entry.updated_at.strftime('%Y-%m-%d %H:%M')}  \n"

    if entry.tags:
        result += f"**Tags:** {', '.join(entry.tags)}  \n"

    result += "\n## Details\n\n"

    # Show structured data
    if entry.data:
        for key, value in entry.data.items():
            if key == "roles" and isinstance(value, list):
                result += f"**{key.title()}:**\n"
                for role in value:
                    result += f"- {role.get('role', 'unknown')} "
                    if role.get("start"):
                        result += f"({role['start']}"
                        if role.get("end"):
                            result += f" - {role['end']}"
                        else:
                            result += " - present"
                        result += ")"
                    result += "\n"

                    if role.get("supervisors"):
                        result += f"  Supervisors: {', '.join(role['supervisors'])}\n"
                result += "\n"
            elif isinstance(value, list):
                result += f"**{key.title()}:** {', '.join(str(v) for v in value)}  \n"
            elif isinstance(value, dict):
                result += f"**{key.title()}:**\n"
                for sub_key, sub_value in value.items():
                    result += f"- {sub_key}: {sub_value}\n"
                result += "\n"
            else:
                result += f"**{key.title()}:** {value}  \n"

    return result


@mcp.resource("knowledge://search/{q}")
def search_knowledge_base(q: str) -> str:
    """Search the knowledge base with a query parameter."""
    if not q:
        return "Please provide a search query"

    entries = knowledge_manager.search_entries(q)

    if not entries:
        return f"No entries found matching '{q}'."

    result = f"# Search Results for '{q}'\n\n"
    result += f"Found {len(entries)} matching entries:\n\n"

    # Group results by type
    by_type = {}
    for entry in entries:
        if entry.type not in by_type:
            by_type[entry.type] = []
        by_type[entry.type].append(entry)

    for entry_type, type_entries in sorted(by_type.items()):
        result += f"## {entry_type.title()}s\n\n"
        for entry in sorted(type_entries, key=lambda x: x.name):
            result += f"- **{entry.name}** - `knowledge://{entry.type}/{entry.id}`\n"
            if entry.tags:
                result += f"  Tags: {', '.join(entry.tags)}\n"
        result += "\n"

    return result


@mcp.tool(
    description="Create a new knowledge entry of any type (person, project, note, etc.)"
)
def create_entry(
    entry_type: str,
    name: constr(min_length=1),
    data: dict[str, Any] = None,
    tags: list[str] = None,
    scope: str = "local",
) -> str:
    """Create a new knowledge entry in global or local scope."""
    if data is None:
        data = {}
    if tags is None:
        tags = []
    if scope not in ("global", "local"):
        return "❌ Scope must be 'global' or 'local'"

    try:
        entry_id = knowledge_manager.create_entry(entry_type, name, data, tags, scope)
        return f"✅ Created {entry_type} entry '{name}' in {scope} scope with ID: {entry_id}"
    except ValueError as e:
        return f"❌ Error: {e}"


@mcp.tool(description="Update an existing knowledge entry with new data or tags")
def update_entry(
    entry_id: str, data: dict[str, Any] = None, tags: list[str] = None
) -> str:
    """Update an existing knowledge entry."""
    success = knowledge_manager.update_entry(entry_id, data, tags)
    if success:
        return f"✅ Updated entry {entry_id}"
    else:
        return f"❌ Entry {entry_id} not found"


@mcp.tool(description="Delete a knowledge entry by ID")
def delete_entry(entry_id: str) -> str:
    """Delete a knowledge entry."""
    success = knowledge_manager.delete_entry(entry_id)
    if success:
        return f"✅ Deleted entry {entry_id}"
    else:
        return f"❌ Entry {entry_id} not found"


@mcp.tool(description="Get details of a specific knowledge entry by ID")
def get_entry(entry_id: str) -> str:
    """Get a specific knowledge entry."""
    entry = knowledge_manager.get_entry(entry_id)
    if not entry:
        return f"❌ Entry {entry_id} not found"

    scope = knowledge_manager.get_entry_scope(entry_id)
    result = f"**{entry.name}** ({entry.type}) [{scope or 'unknown'} scope]\n"
    result += f"ID: {entry.id}\n"
    result += f"Created: {entry.created_at.strftime('%Y-%m-%d')}\n"
    result += f"Updated: {entry.updated_at.strftime('%Y-%m-%d')}\n"

    if entry.tags:
        result += f"Tags: {', '.join(entry.tags)}\n"

    if entry.data:
        result += "\n**Data:**\n"
        for key, value in entry.data.items():
            if isinstance(value, list):
                result += f"- {key}: {', '.join(str(v) for v in value)}\n"
            else:
                result += f"- {key}: {value}\n"

    return result


@mcp.tool(description="List all entries, optionally filtered by type or tags")
def list_entries(entry_type: str = None, tags: list[str] = None) -> str:
    """List knowledge entries with optional filtering."""
    entries = knowledge_manager.list_entries(entry_type, tags)

    if not entries:
        filter_desc = ""
        if entry_type:
            filter_desc += f" of type '{entry_type}'"
        if tags:
            filter_desc += f" with tags {tags}"
        return f"No entries found{filter_desc}."

    result = f"**Knowledge Entries** ({len(entries)} found)\n\n"

    # Group by type for better organization
    by_type = {}
    for entry in entries:
        if entry.type not in by_type:
            by_type[entry.type] = []
        by_type[entry.type].append(entry)

    for entry_type, type_entries in sorted(by_type.items()):
        result += f"**{entry_type.title()}s:**\n"
        for entry in sorted(type_entries, key=lambda x: x.name):
            result += f"- {entry.name} (ID: {entry.id[:8]}...)\n"
        result += "\n"

    return result


@mcp.tool(
    description="Search entries by text query across names, tags, and data fields"
)
def search_entries(query: str) -> str:
    """Search knowledge entries by text."""
    entries = knowledge_manager.search_entries(query)

    if not entries:
        return f"No entries found matching '{query}'."

    result = f"**Search Results for '{query}'** ({len(entries)} found)\n\n"

    for entry in sorted(entries, key=lambda x: x.name):
        result += f"**{entry.name}** ({entry.type}) - ID: {entry.id[:8]}...\n"
        if entry.tags:
            result += f"  Tags: {', '.join(entry.tags)}\n"
        result += "\n"

    return result


@mcp.tool(description="Get current active people in the knowledge base")
def who_is_current() -> str:
    """Get list of currently active people."""
    people = knowledge_manager.get_people(active_only=True)

    if not people:
        return "No currently active people found."

    result = f"**Current Group Members** ({len(people)} people)\n\n"

    # Group by current role
    by_role = {}
    for person in people:
        current_roles = person.get_current_roles()
        for role_data in current_roles:
            role = role_data.get("role", "unknown")
            if role not in by_role:
                by_role[role] = []
            by_role[role].append(person)

    for role, role_people in sorted(by_role.items()):
        result += f"**{role.title()}s:**\n"
        for person in sorted(role_people, key=lambda x: x.name):
            result += f"- {person.name}\n"
        result += "\n"

    return result


@mcp.tool(description="Get people who were active during a specific year")
def who_was_here(year: int) -> str:
    """Get people who were active in a specific year."""
    people = knowledge_manager.get_people_by_year(year)

    if not people:
        return f"No people found for year {year}."

    result = f"**People Active in {year}** ({len(people)} people)\n\n"

    for person in sorted(people, key=lambda x: x.name):
        # Find roles during that year
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        year_roles = []

        for role_data in person.get_roles():
            if "start" in role_data:
                role_start = (
                    date.fromisoformat(role_data["start"])
                    if isinstance(role_data["start"], str)
                    else role_data["start"]
                )
                role_end = None
                if role_data.get("end"):
                    role_end = (
                        date.fromisoformat(role_data["end"])
                        if isinstance(role_data["end"], str)
                        else role_data["end"]
                    )

                if role_start <= year_end and (
                    role_end is None or role_end >= year_start
                ):
                    year_roles.append(role_data.get("role", "unknown"))

        roles_str = ", ".join(set(year_roles)) if year_roles else "unknown role"
        result += f"- {person.name} ({roles_str})\n"

    return result


@mcp.tool(
    description="Get email addresses, optionally for people active in a specific year"
)
def get_emails(year: int = None) -> str:
    """Get email addresses with optional year filter."""
    emails = knowledge_manager.get_emails(year)

    if not emails:
        year_desc = f" for {year}" if year else ""
        return f"No email addresses found{year_desc}."

    year_desc = f" for {year}" if year else " (current)"
    result = f"**Email Addresses{year_desc}** ({len(emails)} found)\n\n"

    for email in sorted(emails):
        result += f"- {email}\n"

    return result


@mcp.tool(description="Find people by role, optionally in a specific year")
def find_by_role(role: str, year: int = None) -> str:
    """Find people by their role."""
    people = knowledge_manager.get_people_by_role(role, year)

    if not people:
        year_desc = f" in {year}" if year else ""
        return f"No {role}s found{year_desc}."

    year_desc = f" in {year}" if year else " (current)"
    result = f"**{role.title()}s{year_desc}** ({len(people)} found)\n\n"

    for person in sorted(people, key=lambda x: x.name):
        result += f"- {person.name}"
        email = person.get_email()
        if email:
            result += f" ({email})"
        result += "\n"

    return result


@mcp.tool(description="Get all people supervised by a specific person")
def find_supervisees(supervisor: str) -> str:
    """Find all people supervised by a given supervisor."""
    supervisees = knowledge_manager.get_supervisees(supervisor)

    if not supervisees:
        return f"No supervisees found for {supervisor}."

    result = f"**People Supervised by {supervisor}** ({len(supervisees)} found)\n\n"

    for person in sorted(supervisees, key=lambda x: x.name):
        result += f"- {person.name}"

        # Show current role
        current_roles = person.get_current_roles()
        if current_roles:
            roles = [r.get("role", "unknown") for r in current_roles]
            result += f" ({', '.join(set(roles))})"

        result += "\n"

    return result


@mcp.tool(description="Get projects, optionally filtered by active status")
def get_projects(active_only: bool = True) -> str:
    """Get list of projects."""
    projects = knowledge_manager.get_projects(active_only)

    if not projects:
        status_desc = " active" if active_only else ""
        return f"No{status_desc} projects found."

    status_desc = " Active" if active_only else ""
    result = f"**{status_desc} Projects** ({len(projects)} found)\n\n"

    for project in sorted(projects, key=lambda x: x.name):
        result += f"**{project.name}**\n"

        # Show timespan
        timespan = project.get_timespan()
        if timespan:
            end_str = timespan.end.isoformat() if timespan.end else "ongoing"
            result += f"  Period: {timespan.start.isoformat()} - {end_str}\n"

        # Show participants
        participants = project.get_participants()
        if participants:
            result += f"  Participants: {', '.join(participants)}\n"

        result += "\n"

    return result


@mcp.tool(description="Get all people involved in a specific project")
def get_project_participants(project_name: str) -> str:
    """Get participants of a specific project."""
    participants = knowledge_manager.get_project_participants(project_name)

    if not participants:
        return f"No participants found for project '{project_name}'."

    result = f"**Participants in '{project_name}'** ({len(participants)} found)\n\n"

    for person in sorted(participants, key=lambda x: x.name):
        result += f"- {person.name}"

        current_roles = person.get_current_roles()
        if current_roles:
            roles = [r.get("role", "unknown") for r in current_roles]
            result += f" ({', '.join(set(roles))})"

        result += "\n"

    return result


@mcp.tool(description="Check the status of the Knowledge Management Tool server.")
def server_info() -> str:
    """Get server status."""
    all_entries = knowledge_manager.list_entries()
    people = knowledge_manager.get_people(active_only=False)
    projects = knowledge_manager.get_projects(active_only=False)

    # Count by type and scope
    type_counts = {}
    scope_counts = {"global": 0, "local": 0}

    for entry in all_entries:
        type_counts[entry.type] = type_counts.get(entry.type, 0) + 1
        scope = knowledge_manager.get_entry_scope(entry.id)
        if scope in scope_counts:
            scope_counts[scope] += 1

    result = """Knowledge Management Tool Server Status
==========================================
Status: Connected and ready
Global Storage: ~/.mcp_handley_lab/knowledge/
Local Storage: ./.mcp_handley_lab/knowledge/

**Statistics:**
"""

    result += f"Total Entries: {len(all_entries)}\n"
    result += f"- Global: {scope_counts['global']}\n"
    result += f"- Local: {scope_counts['local']}\n"
    result += f"People: {len(people)}\n"
    result += f"Projects: {len(projects)}\n"

    if type_counts:
        result += "\n**By Type:**\n"
        for entry_type, count in sorted(type_counts.items()):
            result += f"- {entry_type}: {count}\n"

    result += """
**Available Tools:**
- create_entry: Create new knowledge entries
- update_entry: Modify existing entries
- delete_entry: Remove entries
- get_entry: Get specific entry details
- list_entries: List entries with filtering
- search_entries: Text search across entries
- who_is_current: Current active people
- who_was_here: People active in specific year
- get_emails: Email addresses with year filter
- find_by_role: People by role and year
- find_supervisees: Academic supervision relationships
- get_projects: Project listings
- get_project_participants: Project team members
- server_info: This status information"""

    return result


if __name__ == "__main__":
    mcp.run()
