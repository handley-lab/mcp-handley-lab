#!/usr/bin/env python3
"""Test helper functions for OfflineIMAP authentication."""

import os


def get_test_password():
    """Get password from environment variable for CI testing."""
    password = os.environ.get("GMAIL_TEST_PASSWORD")
    if not password:
        raise ValueError("GMAIL_TEST_PASSWORD environment variable not set")
    return password
