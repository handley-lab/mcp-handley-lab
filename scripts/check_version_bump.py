#!/usr/bin/env python3
"""Check if the version number has been increased compared to master branch."""

import re
import subprocess
import sys
from pathlib import Path
from packaging import version

def get_version_from_file(file_path: Path) -> str:
    """Extract version from pyproject.toml."""
    if not file_path.exists():
        raise FileNotFoundError(f"{file_path} not found")
    
    content = file_path.read_text()
    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError(f"Version not found in {file_path}")
    
    return match.group(1)

def get_master_version() -> str:
    """Get the version from master branch."""
    try:
        # Get pyproject.toml content from master branch
        result = subprocess.run(
            ["git", "show", "origin/master:pyproject.toml"],
            capture_output=True,
            text=True,
            check=True
        )
        
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', result.stdout)
        if not match:
            raise ValueError("Version not found in origin/master:pyproject.toml")
        
        return match.group(1)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get master version: {e}")

def check_version_increased() -> bool:
    """Check if current version is greater than master version."""
    try:
        current_version = get_version_from_file(Path("pyproject.toml"))
        master_version = get_master_version()
        
        print(f"Current version: {current_version}")
        print(f"Master version:  {master_version}")
        
        if current_version == master_version:
            print("❌ Version has not been increased!")
            print("   Please bump the version in pyproject.toml before merging.")
            return False
        
        try:
            if version.parse(current_version) > version.parse(master_version):
                print("✅ Version has been properly increased!")
                return True
            else:
                print("❌ Version has been decreased or is invalid!")
                print("   Please ensure the new version is higher than the master version.")
                return False
        except Exception as e:
            print(f"⚠️  Could not parse versions for comparison: {e}")
            print("   Assuming version change is intentional.")
            return True
            
    except Exception as e:
        print(f"❌ Error checking version: {e}")
        return False

def main():
    """Main entry point."""
    print("Checking if version has been increased...")
    
    if not check_version_increased():
        sys.exit(1)
    
    print("\n🎉 Version check passed!")

if __name__ == "__main__":
    main()