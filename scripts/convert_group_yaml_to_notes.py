#!/usr/bin/env python3
"""Convert Handley Lab group YAML data to structured notes.

This script converts the research group data from handley-lab.github.io
into the mcp-handley-lab notes system using direct Python imports.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import yaml

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Import after path manipulation to find local modules
from mcp_handley_lab.notes.manager import NotesManager  # noqa: E402


def load_group_data(yaml_path: str) -> dict[str, Any]:
    """Load and parse the group YAML file."""
    with open(os.path.expanduser(yaml_path), encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_person_path(person_data: dict[str, Any]) -> str:
    """Determine note path based on role priority.

    COIs (collaborators) go to people/
    All other group members go to people/group/
    """
    if "coi" in person_data:
        return "people"
    return "people/group"


def extract_current_role(person_data: dict[str, Any]) -> str:
    """Determine the person's current/most recent role."""
    role_priority = ["pi", "postdoc", "phd", "mphil", "partiii", "summer", "coi"]

    for role in role_priority:
        if role in person_data:
            role_info = person_data[role]
            # Check if role is current (no end date or recent end)
            if isinstance(role_info, dict) and role_info.get("end") is None:
                return role
            # If has end date, check if it's recent (last year)
            if isinstance(role_info, dict) and role_info.get("end"):
                # Could add date logic here, for now treat as former
                continue

    # Return the highest priority role found
    for role in role_priority:
        if role in person_data:
            return role

    return "unknown"


def determine_status(person_data: dict[str, Any], current_role: str) -> str:
    """Determine if person is current or former."""
    role_data = person_data.get(current_role, {})

    if isinstance(role_data, dict):
        # If no end date, assume current
        if role_data.get("end") is None:
            return "current"
        # If has end date, they're former
        if role_data.get("end"):
            return "former"

    # Default to current for COIs and unclear cases
    return "current" if current_role == "coi" else "former"


def extract_research_areas(person_data: dict[str, Any]) -> list[str]:
    """Extract research area tags from thesis titles and other data."""
    areas = []

    # Extract from thesis titles
    for role in ["phd", "mphil", "partiii"]:
        role_data = person_data.get(role, {})
        if isinstance(role_data, dict):
            thesis = role_data.get("thesis", "")
            if thesis and isinstance(thesis, str):
                # Extract key terms from thesis titles
                thesis_lower = thesis.lower()
                if any(
                    term in thesis_lower
                    for term in ["machine learning", "ml", "neural", "bayesian"]
                ):
                    areas.append("ml")
                if any(
                    term in thesis_lower
                    for term in ["cosmo", "universe", "inflation", "cmb"]
                ):
                    areas.append("cosmology")
                if any(term in thesis_lower for term in ["21cm", "21-cm", "radio"]):
                    areas.append("radio-cosmology")
                if any(
                    term in thesis_lower
                    for term in ["nested sampling", "inference", "mcmc"]
                ):
                    areas.append("inference")
                if any(
                    term in thesis_lower for term in ["climate", "ode", "differential"]
                ):
                    areas.append("differential-equations")

    return list(set(areas))  # Remove duplicates


def generate_tags(person_data: dict[str, Any]) -> list[str]:
    """Generate tags for a person based on their data."""
    tags = ["person"]

    # Add location tag
    path = get_person_path(person_data)
    if path == "people/group":
        tags.append("group")
    else:
        tags.append("external")

    # Add role tags
    current_role = extract_current_role(person_data)
    tags.append(current_role)

    # Add status tag
    status = determine_status(person_data, current_role)
    tags.append(status)

    # Add research area tags
    research_areas = extract_research_areas(person_data)
    tags.extend(research_areas)

    return tags


def extract_properties(name: str, person_data: dict[str, Any]) -> dict[str, Any]:
    """Extract structured properties from person data."""
    properties = {
        "name": name,
        "roles": {},
        "current_role": extract_current_role(person_data),
        "status": determine_status(person_data, extract_current_role(person_data)),
    }

    # Extract role information
    for role in ["pi", "coi", "postdoc", "phd", "mphil", "partiii", "summer"]:
        if role in person_data:
            role_data = person_data[role]
            if isinstance(role_data, dict):
                role_info = {}
                for key in ["start", "end", "thesis"]:
                    if key in role_data:
                        role_info[key] = role_data[key]

                # Handle supervisors (will convert to UUIDs later)
                if "supervisors" in role_data:
                    role_info["supervisor_names"] = role_data["supervisors"]

                properties["roles"][role] = role_info

    # Add image URL
    if "image" in person_data:
        properties["image_url"] = person_data["image"]

    # Add links
    if "links" in person_data:
        properties["links"] = person_data["links"]

    # Add destinations (career moves)
    if "destination" in person_data:
        properties["destinations"] = person_data["destination"]

    return properties


def convert_person_to_note(
    manager: NotesManager,
    name: str,
    person_data: dict[str, Any],
    scope: str = "global",
    dry_run: bool = False,
) -> str | None:
    """Convert a single person to a note."""
    try:
        path = get_person_path(person_data)
        properties = extract_properties(name, person_data)
        tags = generate_tags(person_data)

        if dry_run:
            print(f"Would create note for {name}:")
            print(f"  Path: {path}")
            print(f"  Tags: {tags}")
            print(f"  Current role: {properties['current_role']}")
            print(f"  Status: {properties['status']}")
            return None
        else:
            note_uuid = manager.create_note(
                path=path, title=name, properties=properties, tags=tags, scope=scope
            )
            print(f"Created note for {name} -> {note_uuid}")
            return note_uuid

    except Exception as e:
        print(f"Error converting {name}: {e}")
        return None


def build_name_to_uuid_mapping(manager: NotesManager) -> dict[str, str]:
    """Build a mapping from person names to their note UUIDs."""
    mapping = {}

    # Get all person notes
    notes = manager.find(tags=["person"])

    for note in notes:
        name = note.properties.get("name")
        if name:
            mapping[name] = note.id

    return mapping


def add_supervisor_relationships(manager: NotesManager, dry_run: bool = False):
    """Add supervisor-student UUID relationships to existing notes."""
    name_to_uuid = build_name_to_uuid_mapping(manager)

    # Get all person notes
    notes = manager.find(tags=["person"])

    for note in notes:
        updated_properties = note.properties.copy()
        relationships_added = False

        # Process supervisor relationships
        for role_data in note.properties.get("roles", {}).values():
            if "supervisor_names" in role_data:
                supervisor_names = role_data["supervisor_names"]
                supervisor_uuids = []

                for supervisor_name in supervisor_names:
                    if supervisor_name in name_to_uuid:
                        supervisor_uuids.append(name_to_uuid[supervisor_name])
                    else:
                        print(
                            f"Warning: Supervisor '{supervisor_name}' not found for {note.title}"
                        )

                if supervisor_uuids:
                    # Add to student's record
                    if "supervisors" not in updated_properties:
                        updated_properties["supervisors"] = []
                    updated_properties["supervisors"].extend(supervisor_uuids)
                    relationships_added = True

                    # Add to supervisors' records
                    for supervisor_uuid in supervisor_uuids:
                        supervisor_note = manager.get_note(supervisor_uuid)
                        if supervisor_note:
                            supervisor_props = supervisor_note.properties.copy()
                            if "students" not in supervisor_props:
                                supervisor_props["students"] = []
                            if note.id not in supervisor_props["students"]:
                                supervisor_props["students"].append(note.id)

                                if not dry_run:
                                    manager.update_note(
                                        supervisor_uuid, properties=supervisor_props
                                    )
                                    print(
                                        f"Added student {note.title} to supervisor {supervisor_note.title}"
                                    )

        # Update student's note with supervisor UUIDs
        if relationships_added:
            # Remove duplicate supervisor UUIDs
            if "supervisors" in updated_properties:
                updated_properties["supervisors"] = list(
                    set(updated_properties["supervisors"])
                )

            if not dry_run:
                manager.update_note(note.id, properties=updated_properties)
                print(f"Updated supervisors for {note.title}")


def main():
    """Main conversion function."""
    parser = argparse.ArgumentParser(description="Convert group YAML to notes")
    parser.add_argument(
        "--yaml-path",
        default="~/code/handley-lab.github.io/assets/group/group.yaml",
        help="Path to the group YAML file",
    )
    parser.add_argument(
        "--scope",
        choices=["global", "local"],
        default="global",
        help="Storage scope for notes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--relationships-only",
        action="store_true",
        help="Only update supervisor-student relationships",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip people who already have notes",
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of people to convert (for testing)"
    )

    args = parser.parse_args()

    # Load group data
    try:
        group_data = load_group_data(args.yaml_path)
        print(f"Loaded {len(group_data)} people from {args.yaml_path}")
    except Exception as e:
        print(f"Error loading YAML file: {e}")
        return 1

    # Initialize notes manager (disable semantic search to avoid hanging)
    try:
        # Use a simpler storage directory for testing
        storage_dir = ".mcp_handley_lab"
        manager = NotesManager(local_storage_dir=storage_dir)
        print(f"Initialized notes manager with storage: {storage_dir}")
    except Exception as e:
        print(f"Error initializing notes manager: {e}")
        import traceback

        traceback.print_exc()
        return 1

    if args.relationships_only:
        # Only update relationships
        print("Updating supervisor-student relationships...")
        add_supervisor_relationships(manager, args.dry_run)
        return 0

    # Convert each person to a note
    successful_conversions = 0
    failed_conversions = 0

    items = list(group_data.items())
    if args.limit:
        items = items[: args.limit]
        print(f"Limited to first {args.limit} people")

    for name, person_data in items:
        if args.skip_existing:
            # Check if note already exists
            existing_notes = manager.find(text=name)
            if any(note.title == name for note in existing_notes):
                print(f"Skipping {name} (already exists)")
                continue

        result = convert_person_to_note(
            manager, name, person_data, args.scope, args.dry_run
        )
        if result:
            successful_conversions += 1
        else:
            failed_conversions += 1

    print("\nConversion summary:")
    print(f"  Successful: {successful_conversions}")
    print(f"  Failed: {failed_conversions}")
    print(f"  Total: {len(group_data)}")

    if not args.dry_run and successful_conversions > 0:
        print("\nAdding supervisor-student relationships...")
        add_supervisor_relationships(manager, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
