"""Shared fixtures for Laplace Engine tests.

verify.verify / run_backing now log telemetry, so every test must run against an
isolated state dir - never the user's real ~/.mcp-gerard/laplace.
"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_laplace_state(tmp_path, monkeypatch):
    monkeypatch.setenv("LAPLACE_STATE", str(tmp_path / "_lap_state"))
    yield
