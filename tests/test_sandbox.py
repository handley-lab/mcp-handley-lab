"""Tests for loop namespace sandboxing."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from mcp_handley_lab.loop.sandbox import (
    default_mounts,
    sandbox_cmd,
    write_launcher_script,
)

# --- Unit tests: pure functions ---


class TestDefaultMounts:
    def test_system_mounts_all_ro(self):
        mounts = default_mounts("claude")
        for guest in ("/usr", "/bin", "/lib"):
            if guest in mounts:
                assert mounts[guest][1] == "ro"

    def test_claude_backend_mounts(self):
        mounts = default_mounts("claude")
        home = str(os.path.expanduser("~"))
        claude_dir = f"{home}/.claude"
        if os.path.exists(claude_dir):
            assert mounts[claude_dir][1] == "rw"

    def test_unknown_backend_only_system(self):
        mounts = default_mounts("unknown")
        home = str(os.path.expanduser("~"))
        # No backend-specific mounts
        assert not any(guest.startswith(home) for guest in mounts)

    def test_only_existing_paths(self):
        mounts = default_mounts("claude")
        for _guest, (host, _mode) in mounts.items():
            assert os.path.exists(host)


class TestSandboxCmd:
    def setup_method(self):
        write_launcher_script()

    def test_returns_wrapped_cmd_and_none_cwd(self):
        cmd, cwd = sandbox_cmd(
            ["echo", "hi"],
            "/workspace",
            {"/workspace": ["/tmp", "rw"]},
            "claude",
        )
        assert cwd is None
        assert cmd[0] == sys.executable
        assert "sandbox_launcher.py" in cmd[1]
        # Config file path is argv[2]
        assert cmd[2].endswith(".json")

    def test_config_file_written(self):
        cmd, _ = sandbox_cmd(
            ["echo", "hi"],
            "/workspace",
            {"/workspace": ["/tmp", "rw"]},
            "claude",
        )
        config_path = cmd[2]
        assert os.path.exists(config_path)
        config = json.loads(Path(config_path).read_text())
        assert config["cmd"] == ["echo", "hi"]
        assert config["cwd"] == "/workspace"
        assert "/workspace" in config["mounts"]
        os.unlink(config_path)

    def test_caller_overrides_defaults(self):
        """Caller mount spec wins over defaults for same guest path."""
        cmd, _ = sandbox_cmd(
            ["true"],
            "/",
            {"/usr": ["/tmp", "rw"]},
            "claude",
        )
        config = json.loads(Path(cmd[2]).read_text())
        # /usr should be rw (caller override), not ro (default)
        assert config["mounts"]["/usr"][1] == "rw"
        os.unlink(cmd[2])

    def test_empty_cwd_defaults_to_root(self):
        cmd, _ = sandbox_cmd(
            ["true"],
            "",
            {"/workspace": ["/tmp", "rw"]},
            "claude",
        )
        config = json.loads(Path(cmd[2]).read_text())
        assert config["cwd"] == "/"
        os.unlink(cmd[2])

    def test_env_included_when_provided(self):
        cmd, _ = sandbox_cmd(
            ["true"],
            "/",
            {"/workspace": ["/tmp", "rw"]},
            "claude",
            env={"FOO": "bar"},
        )
        config = json.loads(Path(cmd[2]).read_text())
        assert config["env"] == {"FOO": "bar"}
        os.unlink(cmd[2])

    def test_env_omitted_when_none(self):
        cmd, _ = sandbox_cmd(
            ["true"],
            "/",
            {"/workspace": ["/tmp", "rw"]},
            "claude",
        )
        config = json.loads(Path(cmd[2]).read_text())
        assert "env" not in config
        os.unlink(cmd[2])

    def test_rejects_relative_guest_path(self):
        with pytest.raises(ValueError, match="absolute"):
            sandbox_cmd(["true"], "/", {"relative": ["/tmp", "rw"]}, "claude")

    def test_rejects_dotdot_guest_path(self):
        with pytest.raises(ValueError, match="\\.\\."):
            sandbox_cmd(["true"], "/", {"/foo/../bar": ["/tmp", "rw"]}, "claude")

    def test_rejects_bad_mode(self):
        with pytest.raises(ValueError, match="mode"):
            sandbox_cmd(["true"], "/", {"/foo": ["/tmp", "wx"]}, "claude")

    def test_rejects_nonexistent_host_path(self):
        with pytest.raises(FileNotFoundError):
            sandbox_cmd(
                ["true"],
                "/",
                {"/foo": ["/nonexistent/path/xyz", "rw"]},
                "claude",
            )


class TestWriteLauncherScript:
    def test_writes_executable(self):
        path = write_launcher_script()
        assert path.exists()
        assert path.stat().st_mode & 0o700 == 0o700

    def test_idempotent(self):
        p1 = write_launcher_script()
        p2 = write_launcher_script()
        assert p1 == p2


# --- Integration tests: actual namespace isolation ---


def _has_user_namespaces():
    """Check if unprivileged user namespaces are fully functional.

    Tests unshare + setgroups/uid_map/gid_map writes, since some CI environments
    allow unshare but block /proc/self/setgroups writes.
    """
    try:
        script = (
            "import os\n"
            "os.unshare(os.CLONE_NEWUSER)\n"
            "open('/proc/self/setgroups', 'w').write('deny\\n')\n"
            "open('/proc/self/uid_map', 'w').write(f'0 {os.getuid()} 1\\n')\n"
            "open('/proc/self/gid_map', 'w').write(f'0 {os.getgid()} 1\\n')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


@pytest.mark.skipif(
    not _has_user_namespaces(),
    reason="unprivileged user namespaces not available",
)
class TestSandboxIntegration:
    """Run real commands inside a sandbox and verify isolation."""

    def setup_method(self):
        write_launcher_script()
        self.host_dir = tempfile.mkdtemp(prefix="sandbox-test-")
        # Create a file the sandbox can see
        with open(os.path.join(self.host_dir, "visible.txt"), "w") as f:
            f.write("hello from host")

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.host_dir, ignore_errors=True)

    def _run_sandboxed(self, shell_cmd, guest_cwd="/workspace"):
        cmd, _ = sandbox_cmd(
            ["bash", "-c", shell_cmd],
            guest_cwd,
            {"/workspace": [self.host_dir, "rw"]},
            "claude",
        )
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10)

    def test_cwd_is_guest_path(self):
        proc = self._run_sandboxed("pwd")
        assert proc.stdout.strip() == "/workspace"

    def test_mounted_dir_visible(self):
        proc = self._run_sandboxed("cat /workspace/visible.txt")
        assert proc.stdout.strip() == "hello from host"

    def test_root_only_has_mounted_paths(self):
        proc = self._run_sandboxed("ls /")
        entries = set(proc.stdout.strip().split())
        # Must have our mount + essential dirs
        assert "workspace" in entries
        assert "proc" in entries
        assert "dev" in entries
        assert "tmp" in entries
        # Must NOT have unmounted host dirs
        assert "var" not in entries
        assert "srv" not in entries
        assert "sys" not in entries
        assert "run" not in entries
        assert "boot" not in entries

    def test_unmounted_paths_invisible(self):
        proc = self._run_sandboxed("ls /home/will/.ssh 2>&1")
        assert proc.returncode != 0

    def test_system_mounts_readonly(self):
        proc = self._run_sandboxed("touch /usr/bin/evil 2>&1")
        assert proc.returncode != 0
        assert "Read-only" in proc.stdout or "Read-only" in proc.stderr

    def test_workspace_writable(self):
        proc = self._run_sandboxed(
            "echo test > /workspace/new.txt && cat /workspace/new.txt"
        )
        assert proc.stdout.strip() == "test"
        # Verify it appeared on the host
        assert Path(self.host_dir, "new.txt").read_text().strip() == "test"

    def test_user_defined_ro_mount(self):
        """User-defined ro mounts from tmpfs paths must work (issue #259)."""
        extra = tempfile.mkdtemp(prefix="sandbox-extra-")
        with open(os.path.join(extra, "data.txt"), "w") as f:
            f.write("readonly content")
        cmd, _ = sandbox_cmd(
            ["bash", "-c", "cat /extra/data.txt && touch /extra/nope 2>&1"],
            "/workspace",
            {"/workspace": [self.host_dir, "rw"], "/extra": [extra, "ro"]},
            "claude",
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert "readonly content" in proc.stdout
        assert "Read-only" in proc.stdout or "Read-only" in proc.stderr

    def test_etc_shadow_not_accessible(self):
        proc = self._run_sandboxed("cat /etc/shadow 2>&1")
        assert proc.returncode != 0

    def test_env_passed_through(self):
        cmd, _ = sandbox_cmd(
            ["bash", "-c", "echo $MY_VAR"],
            "/",
            {"/workspace": [self.host_dir, "rw"]},
            "claude",
            env={**os.environ, "MY_VAR": "sandbox_value"},
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        assert proc.stdout.strip() == "sandbox_value"
