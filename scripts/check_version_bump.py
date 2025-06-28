#!/usr/bin/env python3
"""Check if the version number has been increased compared to master branch."""

import re
import subprocess
import sys
from pathlib import Path
from packaging import version

def get_version_from_file(file_path: Path) -> str:
    """Extract version from pyproject.toml or PKGBUILD."""
    if not file_path.exists():
        raise FileNotFoundError(f"{file_path} not found")
    
    content = file_path.read_text()
    
    if file_path.name == "PKGBUILD":
        match = re.search(r'pkgver=([^\s]+)', content)
    else:
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        
    if not match:
        raise ValueError(f"Version not found in {file_path}")
    
    return match.group(1)

def get_master_version_from_file(file_name: str) -> str:
    """Get the version from master branch for a specific file."""
    try:
        result = subprocess.run(
            ["git", "show", f"origin/master:{file_name}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        if file_name == "PKGBUILD":
            match = re.search(r'pkgver=([^\s]+)', result.stdout)
        else:
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', result.stdout)
            
        if not match:
            raise ValueError(f"Version not found in origin/master:{file_name}")
        
        return match.group(1)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get master version from {file_name}: {e}")

def check_version_increased() -> bool:
    """Check if current version is greater than master version."""
    version_files = ["pyproject.toml", "PKGBUILD"]
    all_consistent = True
    
    for file_name in version_files:
        file_path = Path(file_name)
        if not file_path.exists():
            print(f"⚠️  {file_name} not found, skipping...")
            continue
            
        try:
            current_version = get_version_from_file(file_path)
            master_version = get_master_version_from_file(file_name)
            
            print(f"{file_name}:")
            print(f"  Current version: {current_version}")
            print(f"  Master version:  {master_version}")
            
            if current_version == master_version:
                print(f"  ❌ Version has not been increased in {file_name}!")
                all_consistent = False
                continue
            
            try:
                if version.parse(current_version) > version.parse(master_version):
                    print(f"  ✅ Version properly increased in {file_name}")
                else:
                    print(f"  ❌ Version decreased or invalid in {file_name}!")
                    all_consistent = False
            except Exception as e:
                print(f"  ⚠️  Could not parse versions in {file_name}: {e}")
                print(f"  Assuming version change is intentional for {file_name}")
                
        except Exception as e:
            print(f"❌ Error checking {file_name}: {e}")
            all_consistent = False
    
    if not all_consistent:
        print("\n❌ Please bump versions in all files before merging.")
        return False
    
    print("\n✅ All versions have been properly increased!")
    return True

def main():
    """Main entry point."""
    print("Checking if version has been increased...")
    
    if not check_version_increased():
        sys.exit(1)
    
    print("\n🎉 Version check passed!")

if __name__ == "__main__":
    main()