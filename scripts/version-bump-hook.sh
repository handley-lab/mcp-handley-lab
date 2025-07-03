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

# If versions are the same, we need to bump
if [[ "$current_version" == "$master_version" && -n "$master_version" ]]; then
    echo "Version matches master - bumping required"
    
    # Parse version format: 0.0.0a23 -> major.minor.patch.alpha_num
    if [[ $current_version =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)a([0-9]+)$ ]]; then
        major=${BASH_REMATCH[1]}
        minor=${BASH_REMATCH[2]}
        patch=${BASH_REMATCH[3]}
        alpha_num=${BASH_REMATCH[4]}
        
        # Increment alpha version
        new_alpha_num=$((alpha_num + 1))
        new_version="${major}.${minor}.${patch}a${new_alpha_num}"
        
        echo "Bumping version to: $new_version"
        
        # Update pyproject.toml
        sed -i "s/^version = \".*\"/version = \"$new_version\"/" pyproject.toml
        
        # Update PKGBUILD
        sed -i "s/^pkgver=.*/pkgver=$new_version/" PKGBUILD
        
        # Stage the updated files
        git add pyproject.toml PKGBUILD
        
        echo "✅ Version bumped from $current_version to $new_version"
        echo "✅ Updated files staged for commit"
        
    else
        echo "Error: Version format not recognized. Expected format: X.Y.ZaN (e.g., 0.0.0a23)"
        echo "Found: $current_version"
        exit 1
    fi
else
    echo "✅ Version already differs from master or master not available - no bump needed"
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