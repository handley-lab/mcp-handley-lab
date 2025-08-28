#!/usr/bin/env python3
"""
Script to scrub OAuth tokens from existing VCR cassette files.
This removes sensitive tokens that were already recorded in cassettes.
"""

import re
import sys
from pathlib import Path


def scrub_oauth_tokens_in_file(file_path: Path) -> bool:
    """
    Scrub OAuth tokens from a single cassette file.
    Returns True if any changes were made.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        original_content = content

        # Pattern 1: OAuth access tokens starting with ya29.
        content = re.sub(
            r'"access_token": "ya29\.[^"]*"',
            '"access_token": "REDACTED_OAUTH_TOKEN"',
            content,
        )

        # Pattern 2: Any long access tokens (high entropy strings)
        content = re.sub(
            r'"access_token": "[A-Za-z0-9._-]{100,}"',
            '"access_token": "REDACTED_OAUTH_TOKEN"',
            content,
        )

        # Pattern 3: JSON response bodies with access tokens (multiline handling)
        content = re.sub(
            r'(\\"access_token\\"\s*:\s*\\")ya29\.[^"]*(\\")',
            r"\1REDACTED_OAUTH_TOKEN\2",
            content,
        )

        # Pattern 4: Long tokens in JSON response bodies
        content = re.sub(
            r'(\\"access_token\\"\s*:\s*\\")[A-Za-z0-9._-]{100,}(\\")',
            r"\1REDACTED_OAUTH_TOKEN\2",
            content,
        )

        if content != original_content:
            file_path.write_text(content, encoding="utf-8")
            return True

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to scrub all VCR cassettes."""
    cassettes_dir = Path("tests/integration/cassettes")

    if not cassettes_dir.exists():
        print(f"Cassettes directory not found: {cassettes_dir}")
        sys.exit(1)

    cassette_files = list(cassettes_dir.rglob("*.yaml"))

    if not cassette_files:
        print("No cassette files found")
        sys.exit(0)

    print(f"Found {len(cassette_files)} cassette files")

    modified_count = 0
    for cassette_file in cassette_files:
        if scrub_oauth_tokens_in_file(cassette_file):
            print(f"✓ Scrubbed tokens from: {cassette_file.name}")
            modified_count += 1
        else:
            print(f"  No tokens found in: {cassette_file.name}")

    print(
        f"\nSummary: Modified {modified_count} out of {len(cassette_files)} cassette files"
    )

    if modified_count > 0:
        print(
            "\n⚠️  Important: Review the changes and re-run your tests to ensure they still pass"
        )
        print("   The scrubbed cassettes will need to be recommitted to git")


if __name__ == "__main__":
    main()
