#!/usr/bin/env python3
"""
Version bump script with semantic versioning support.

Usage:
    python scripts/bump_version.py patch    # 0.0.0b5 -> 0.0.1
    python scripts/bump_version.py minor    # 0.0.0b5 -> 0.1.0
    python scripts/bump_version.py major    # 0.0.0b5 -> 1.0.0
    python scripts/bump_version.py alpha    # 0.0.0b5 -> 0.0.0b6
    python scripts/bump_version.py beta     # 0.0.0a5 -> 0.0.0b1
    python scripts/bump_version.py rc       # 0.0.0b5 -> 0.0.0rc1
    python scripts/bump_version.py release  # 0.0.0b5 -> 0.0.0
"""
import argparse
import re
import sys
from pathlib import Path

try:
    import tomli as tomllib
except ImportError:
    import tomllib


def parse_version(version_str):
    """Parse a semantic version string into components."""
    # Match patterns like: 1.2.3, 1.2.3a4, 1.2.3b5, 1.2.3rc1
    pattern = r"^(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$"
    match = re.match(pattern, version_str)

    if not match:
        raise ValueError(f"Invalid version format: {version_str}")

    major, minor, patch, pre_type, pre_num = match.groups()

    return {
        "major": int(major),
        "minor": int(minor),
        "patch": int(patch),
        "pre_type": pre_type,
        "pre_num": int(pre_num) if pre_num else None,
    }


def format_version(version_parts):
    """Format version parts back into a string."""
    base = f"{version_parts['major']}.{version_parts['minor']}.{version_parts['patch']}"

    if version_parts["pre_type"] and version_parts["pre_num"] is not None:
        return f"{base}{version_parts['pre_type']}{version_parts['pre_num']}"

    return base


def bump_version(current_version, bump_type):
    """Bump version according to semantic versioning rules."""
    parts = parse_version(current_version)

    if bump_type == "auto":
        # Auto-detect minimal bump based on current version
        if parts["pre_type"] in ("a", "b", "rc"):
            parts["pre_num"] += 1
        else:
            # No pre-release, do patch bump
            parts["patch"] += 1

    elif bump_type == "major":
        parts["major"] += 1
        parts["minor"] = 0
        parts["patch"] = 0
        parts["pre_type"] = None
        parts["pre_num"] = None

    elif bump_type == "minor":
        parts["minor"] += 1
        parts["patch"] = 0
        parts["pre_type"] = None
        parts["pre_num"] = None

    elif bump_type == "patch":
        parts["patch"] += 1
        parts["pre_type"] = None
        parts["pre_num"] = None

    elif bump_type == "alpha":
        if parts["pre_type"] == "a":
            parts["pre_num"] += 1
        else:
            # If not already alpha, start with a1
            parts["pre_type"] = "a"
            parts["pre_num"] = 1

    elif bump_type == "beta":
        if parts["pre_type"] == "b":
            parts["pre_num"] += 1
        else:
            # Upgrade from alpha or start with b1
            parts["pre_type"] = "b"
            parts["pre_num"] = 1

    elif bump_type == "rc":
        if parts["pre_type"] == "rc":
            parts["pre_num"] += 1
        else:
            # Upgrade from alpha/beta or start with rc1
            parts["pre_type"] = "rc"
            parts["pre_num"] = 1

    elif bump_type == "release":
        # Remove pre-release components
        parts["pre_type"] = None
        parts["pre_num"] = None

    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

    return format_version(parts)


def get_current_version():
    """Get current version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")

    if not pyproject_path.exists():
        raise FileNotFoundError(
            "pyproject.toml not found. Are you in the project root?"
        )

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    version = data.get("project", {}).get("version")
    if not version:
        raise ValueError("Version not found in pyproject.toml")

    return version


def update_pyproject_toml(new_version):
    """Update version in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")

    with open(pyproject_path) as f:
        content = f.read()

    # Replace version line
    updated_content = re.sub(
        r'^version = "[^"]*"', f'version = "{new_version}"', content, flags=re.MULTILINE
    )

    with open(pyproject_path, "w") as f:
        f.write(updated_content)


def update_pkgbuild(new_version):
    """Update version in PKGBUILD."""
    pkgbuild_path = Path("PKGBUILD")

    if not pkgbuild_path.exists():
        print("Warning: PKGBUILD not found, skipping")
        return

    with open(pkgbuild_path) as f:
        content = f.read()

    # Replace pkgver line
    updated_content = re.sub(
        r"^pkgver=.*", f"pkgver={new_version}", content, flags=re.MULTILINE
    )

    with open(pkgbuild_path, "w") as f:
        f.write(updated_content)


def main():
    parser = argparse.ArgumentParser(
        description="Bump version using semantic versioning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "bump_type",
        nargs="?",
        default="auto",
        choices=["major", "minor", "patch", "alpha", "beta", "rc", "release", "auto"],
        help="Type of version bump to perform (default: auto - minimal available bump)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    try:
        current_version = get_current_version()
        new_version = bump_version(current_version, args.bump_type)

        print(f"Current version: {current_version}")
        print(f"New version:     {new_version}")

        if args.dry_run:
            print("\n(Dry run - no files were changed)")
            return 0

        # Update files
        print("\nUpdating pyproject.toml...")
        update_pyproject_toml(new_version)

        print("Updating PKGBUILD...")
        update_pkgbuild(new_version)

        print(f"\n✅ Version bumped from {current_version} to {new_version}")
        print("\nFiles updated:")
        print("  - pyproject.toml")
        print("  - PKGBUILD")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
