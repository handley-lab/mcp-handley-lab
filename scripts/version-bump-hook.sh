#!/bin/bash

# Pre-commit hook to automatically bump version when needed
# Compares current version against origin/master to determine if bump is required

set -e

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" || ! -f "PKGBUILD" ]]; then
    echo "Error: pyproject.toml or PKGBUILD not found. Are you in the project root?"
    exit 1
fi

# Fetch latest from origin to ensure we have up-to-date master
echo "Fetching latest from origin..."
git fetch origin master >/dev/null 2>&1 || {
    echo "Warning: Could not fetch from origin. Proceeding with local comparison."
}

# Extract current version from working directory
current_version=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
if [[ -z "$current_version" ]]; then
    echo "Error: Could not extract version from pyproject.toml"
    exit 1
fi

# Extract version from origin/master
master_version=""
if git show origin/master:pyproject.toml >/dev/null 2>&1; then
    master_version=$(git show origin/master:pyproject.toml | grep '^version = ' | sed 's/version = "\(.*\)"/\1/')
fi

echo "Current version: $current_version"
echo "Master version: ${master_version:-"(not found)"}"

# If versions are the same, we need to fail and ask for manual bump
if [[ "$current_version" == "$master_version" && -n "$master_version" ]]; then
    echo ""
    echo "❌ VERSION BUMP REQUIRED"
    echo ""
    echo "Current version ($current_version) matches origin/master."
    echo "Please bump the version in both files based on your changes:"
    echo ""
    echo "For breaking changes:  major bump (e.g., 1.0.0)"
    echo "For new features:      minor bump (e.g., 0.1.0)" 
    echo "For bug fixes:         patch bump (e.g., 0.0.1)"
    echo "For small changes:     alpha bump (e.g., 0.0.0a$(( $(echo $current_version | sed 's/.*a//') + 1 )))"
    echo ""
    echo "Update both files:"
    echo "  - pyproject.toml (version = \"X.Y.ZaN\")"
    echo "  - PKGBUILD (pkgver=X.Y.ZaN)"
    echo ""
    exit 1
else
    echo "✅ Version already differs from master or master not available - proceeding"
fi

# Final verification: ensure both files have matching versions
pyproject_version=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
pkgbuild_version=$(grep '^pkgver=' PKGBUILD | sed 's/pkgver=//')

if [[ "$pyproject_version" != "$pkgbuild_version" ]]; then
    echo "Error: Version mismatch!"
    echo "pyproject.toml: $pyproject_version"
    echo "PKGBUILD: $pkgbuild_version"
    exit 1
fi

echo "✅ Version consistency verified: $pyproject_version"