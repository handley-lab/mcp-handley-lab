#!/usr/bin/env python3
import re
import subprocess
import sys

import tomli as tomllib


def get_git_file_content(ref, path):
    """Gets file content from a specific git ref (e.g., 'origin/master')."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def get_pyproject_version(content):
    """Parses TOML content and returns the version."""
    data = tomllib.loads(content)
    return data.get("project", {}).get("version")


def get_pkgbuild_version(content):
    """Parses PKGBUILD content for pkgver."""
    for line in content.splitlines():
        if line.strip().startswith("pkgver="):
            return line.split("=")[1].strip()
    return None


def suggest_next_version(current_version):
    """Suggests next version options based on current version."""
    if not current_version:
        return []

    # Parse version like 0.0.0a24
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)a(\d+)$", current_version)
    if match:
        major, minor, patch, alpha = map(int, match.groups())
        return [
            f"For breaking changes:  major bump (e.g., {major + 1}.0.0)",
            f"For new features:      minor bump (e.g., {major}.{minor + 1}.0)",
            f"For bug fixes:         patch bump (e.g., {major}.{minor}.{patch + 1})",
            f"For small changes:     alpha bump (e.g., {major}.{minor}.{patch}a{alpha + 1})",
        ]
    else:
        return ["Please bump version appropriately based on changes"]


def main():
    # 1. Read local files
    try:
        with open("pyproject.toml", "rb") as f:
            local_pyproject_content = f.read().decode("utf-8")
        with open("PKGBUILD") as f:
            local_pkgbuild_content = f.read()
    except FileNotFoundError:
        print(
            "Error: pyproject.toml or PKGBUILD not found. Are you in the project root?",
            file=sys.stderr,
        )
        return 1

    # 2. Extract and verify local versions
    local_version = get_pyproject_version(local_pyproject_content)
    pkgbuild_version = get_pkgbuild_version(local_pkgbuild_content)

    if not local_version:
        print("Error: Could not extract version from pyproject.toml", file=sys.stderr)
        return 1

    if local_version != pkgbuild_version:
        print("❌ Error: Version mismatch in your working files!", file=sys.stderr)
        print(f"   pyproject.toml: {local_version}", file=sys.stderr)
        print(f"   PKGBUILD:       {pkgbuild_version}", file=sys.stderr)
        print("Please make them consistent before committing.", file=sys.stderr)
        return 1

    # 3. Fetch and compare with origin/master
    print("Fetching latest from origin/master...")
    result = subprocess.run(["git", "fetch", "origin", "master"], capture_output=True)
    if result.returncode != 0:
        print(
            "❌ Error: Could not fetch from origin. Network or git issue detected.",
            file=sys.stderr,
        )
        print(f"Git fetch failed with exit code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(f"Error details: {result.stderr.decode()}", file=sys.stderr)
        print("Please fix the git/network issue and try again.", file=sys.stderr)
        return 1

    master_content = get_git_file_content("origin/master", "pyproject.toml")
    if not master_content:
        print("✅ Master version not found or not available - proceeding")
        return 0

    master_version = get_pyproject_version(master_content)
    print(f"Current version: {local_version}")
    print(f"Master version:  {master_version}")

    # 4. The core check
    if local_version == master_version and master_version:
        print("\n❌ VERSION BUMP REQUIRED\n", file=sys.stderr)
        print(
            f"Current version ({local_version}) matches origin/master.", file=sys.stderr
        )
        print(
            "Please bump the version in both files based on your changes:\n",
            file=sys.stderr,
        )

        # Show intelligent suggestions
        suggestions = suggest_next_version(local_version)
        for suggestion in suggestions:
            print(f"  {suggestion}", file=sys.stderr)

        print("\nUpdate both files:", file=sys.stderr)
        print('  - pyproject.toml (version = "X.Y.ZaN")', file=sys.stderr)
        print("  - PKGBUILD (pkgver=X.Y.ZaN)", file=sys.stderr)
        return 1

    print(
        f"✅ Version ({local_version}) differs from master or master not available - proceeding"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
