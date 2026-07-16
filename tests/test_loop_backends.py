"""Tests for loop tmux backend helpers."""

import sys

from mcp_handley_lab.loop.backends import _venv_stripped_path


class TestVenvStrippedPath:
    def test_system_python_path_untouched(self, monkeypatch):
        """Under system Python (sys.prefix == sys.base_prefix) PATH must pass through.

        Regression test for #371: sys.prefix is '/usr' outside a venv, so
        prefix-stripping emptied PATH entirely and every spawned window died.
        """
        monkeypatch.setattr(sys, "prefix", "/usr")
        monkeypatch.setattr(sys, "base_prefix", "/usr")
        assert (
            _venv_stripped_path("/usr/local/bin:/usr/bin") == "/usr/local/bin:/usr/bin"
        )

    def test_venv_entries_stripped(self, monkeypatch):
        monkeypatch.setattr(sys, "prefix", "/home/user/.venv")
        monkeypatch.setattr(sys, "base_prefix", "/usr")
        assert (
            _venv_stripped_path("/home/user/.venv/bin:/usr/local/bin:/usr/bin")
            == "/usr/local/bin:/usr/bin"
        )
