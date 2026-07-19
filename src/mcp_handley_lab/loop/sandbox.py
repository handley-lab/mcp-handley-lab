"""Kernel namespace sandboxing for loop.spawn().

Provides filesystem isolation using Linux user + mount namespaces.
The launcher script does unshare/pivot_root then execvp the target command.
No external dependencies — uses os.unshare() + ctypes for mount syscalls.
"""

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

STATE_DIR = Path.home() / ".local" / "state" / "mcp-loop"

# System mounts needed for CLI executables to function (all ro)
_SYSTEM_MOUNTS: dict[str, tuple[str, str]] = {
    "/usr": ("/usr", "ro"),
    "/bin": ("/bin", "ro"),
    "/lib": ("/lib", "ro"),
    "/lib64": ("/lib64", "ro"),
    "/opt": ("/opt", "ro"),
    "/etc/resolv.conf": ("/etc/resolv.conf", "ro"),
    "/etc/ssl": ("/etc/ssl", "ro"),
    "/etc/hosts": ("/etc/hosts", "ro"),
    "/etc/nsswitch.conf": ("/etc/nsswitch.conf", "ro"),
    "/etc/passwd": ("/etc/passwd", "ro"),
    "/etc/group": ("/etc/group", "ro"),
    "/etc/ld.so.cache": ("/etc/ld.so.cache", "ro"),
}


def _backend_mounts(backend: str) -> dict[str, tuple[str, str]]:
    """Return per-backend CLI config mounts (rw — CLIs write session state)."""
    home = str(Path.home())
    return {
        "claude": {
            f"{home}/.claude.json": (f"{home}/.claude.json", "rw"),
            f"{home}/.claude": (f"{home}/.claude", "rw"),
        },
        "gemini": {
            f"{home}/.gemini": (f"{home}/.gemini", "rw"),
        },
        "openai": {
            f"{home}/.codex": (f"{home}/.codex", "rw"),
        },
    }.get(backend, {})


def default_mounts(backend: str) -> dict[str, tuple[str, str]]:
    """Return default mounts for a backend (system + CLI config).

    Returns dict of {guest_path: (host_path, mode)}.
    Only includes paths that actually exist on the host.
    """
    mounts = {}
    for guest, (host, mode) in _SYSTEM_MOUNTS.items():
        if os.path.exists(host):
            mounts[guest] = (host, mode)
    for guest, (host, mode) in _backend_mounts(backend).items():
        if os.path.exists(host):
            mounts[guest] = (host, mode)
    return mounts


# The launcher script is a self-contained Python script that:
# 1. Reads config from a JSON file (passed as argv[1])
# 2. Sets up mount namespace isolation
# 3. Executes the target command
_LAUNCHER_SCRIPT = '''\
#!/usr/bin/env python3
"""Sandbox launcher — sets up mount namespace isolation then execs target command."""
import ctypes
import ctypes.util
import json
import os
import sys
import tempfile

MS_RDONLY = 1
MS_BIND = 4096
MS_REC = 16384
MS_PRIVATE = 1 << 18
MS_REMOUNT = 32
MNT_DETACH = 2

_libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


def _mount(source, target, fstype, flags, data=None):
    src = source.encode() if source else None
    tgt = target.encode()
    fst = fstype.encode() if fstype else None
    ret = _libc.mount(src, tgt, fst, flags, data)
    if ret != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, f"mount({source!r}, {target!r}, {fstype!r}, {flags}): {os.strerror(errno)}")


def _pivot_root(new_root, put_old):
    ret = _libc.pivot_root(new_root.encode(), put_old.encode())
    if ret != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, f"pivot_root({new_root!r}, {put_old!r}): {os.strerror(errno)}")


def _umount2(target, flags):
    ret = _libc.umount2(target.encode(), flags)
    if ret != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, f"umount2({target!r}, {flags}): {os.strerror(errno)}")


def main():
    config_file = sys.argv[1]
    with open(config_file) as f:
        config = json.load(f)
    os.unlink(config_file)

    mounts = config["mounts"]  # {guest: [host, mode]}
    cwd = config.get("cwd", "/")
    cmd = config["cmd"]
    env = config.get("env")

    host_uid = os.getuid()
    host_gid = os.getgid()

    # 1. Create new user + mount namespaces
    os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNS)

    # 2. Write uid/gid mappings
    with open("/proc/self/setgroups", "w") as f:
        f.write("deny\\n")
    with open("/proc/self/uid_map", "w") as f:
        f.write(f"0 {host_uid} 1\\n")
    with open("/proc/self/gid_map", "w") as f:
        f.write(f"0 {host_gid} 1\\n")
    os.setgid(0)
    os.setuid(0)

    # 3. Make all mounts private (prevent propagation)
    _mount(None, "/", None, MS_REC | MS_PRIVATE)

    # 4. Create new root on tmpfs
    new_root = tempfile.mkdtemp(prefix="sandbox-")
    _mount("tmpfs", new_root, "tmpfs", 0)

    # 5. Bind-mount specified paths (sorted by depth for correct ordering)
    sorted_mounts = sorted(mounts.items(), key=lambda x: (x[0].count("/"), x[0]))
    for guest, (host, mode) in sorted_mounts:
        target = os.path.join(new_root, guest.lstrip("/"))
        if os.path.isfile(host):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w"):
                pass  # touch
        else:
            os.makedirs(target, exist_ok=True)
        _mount(host, target, None, MS_BIND | MS_REC)
        if mode == "ro":
            current = os.statvfs(target).f_flag
            _mount(host, target, None, MS_REMOUNT | MS_BIND | MS_REC | current | MS_RDONLY)

    # 6. Essential mounts under new_root
    for d in ("proc", "dev", "tmp"):
        os.makedirs(os.path.join(new_root, d), exist_ok=True)
    # Bind-mount host /proc (fresh procfs requires CLONE_NEWPID which we don't use)
    _mount("/proc", os.path.join(new_root, "proc"), None, MS_BIND | MS_REC)
    _mount("/dev", os.path.join(new_root, "dev"), None, MS_BIND | MS_REC)
    _mount("tmpfs", os.path.join(new_root, "tmp"), "tmpfs", 0)

    # 7. pivot_root
    old_root = os.path.join(new_root, ".old_root")
    os.makedirs(old_root, exist_ok=True)
    os.chdir(new_root)
    _pivot_root(".", ".old_root")

    # 8. Detach old root
    _umount2("/.old_root", MNT_DETACH)
    os.rmdir("/.old_root")

    # 9. chdir to requested working directory
    os.chdir(cwd or "/")

    # 10. exec target command
    if env is not None:
        os.execvpe(cmd[0], cmd, env)
    else:
        os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"sandbox launcher error: {e}", file=sys.stderr)
        sys.exit(1)
'''


def write_launcher_script() -> Path:
    """Write the sandbox launcher script to a stable location.

    Called once at daemon startup. Returns the path to the launcher.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    launcher_path = STATE_DIR / "sandbox_launcher.py"
    launcher_path.write_text(_LAUNCHER_SCRIPT)
    launcher_path.chmod(stat.S_IRWXU)  # 0o700
    return launcher_path


def sandbox_cmd(
    cmd: list[str],
    cwd: str,
    sandbox: dict[str, list[str]],
    backend: str,
    env: dict[str, str] | None = None,
) -> tuple[list[str], None]:
    """Wrap a command to run inside a mount namespace sandbox.

    Args:
        cmd: The command to run inside the sandbox.
        cwd: Working directory inside the sandbox (must be a guest path). Empty → "/".
        sandbox: Caller's mount spec {guest_path: [host_path, mode]}.
        backend: Backend name for default mounts ("claude", "gemini", "openai").
        env: Optional environment dict for the sandboxed process.

    Returns:
        (wrapped_cmd, None) — the wrapped command and cwd=None for Popen.
    """
    # Merge defaults with caller (caller wins)
    merged: dict[str, tuple[str, str]] = default_mounts(backend)
    for guest, spec in sandbox.items():
        merged[guest] = (spec[0], spec[1])

    # Validate
    for guest, (_host, mode) in merged.items():
        if not guest.startswith("/"):
            raise ValueError(f"guest path must be absolute: {guest!r}")
        if ".." in guest.split("/"):
            raise ValueError(f"guest path must not contain '..': {guest!r}")
        if mode not in ("ro", "rw"):
            raise ValueError(f"mode must be 'ro' or 'rw', got {mode!r} for {guest!r}")

    # Resolve host paths
    resolved: dict[str, list[str]] = {}
    for guest, (host, mode) in merged.items():
        resolved_host = str(Path(host).resolve(strict=True))
        resolved[guest] = [resolved_host, mode]

    # Write config to temp file (cwd is a guest path — caller must translate)
    config = {
        "mounts": resolved,
        "cwd": cwd or "/",
        "cmd": cmd,
    }
    if env is not None:
        config["env"] = env

    fd, config_path = tempfile.mkstemp(prefix="sandbox-cfg-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(config, f)

    launcher_path = STATE_DIR / "sandbox_launcher.py"
    return [sys.executable, str(launcher_path), config_path], None


def sandbox_mount(pid: int, source: str, target: str) -> None:
    """Bind-mount source to target inside a sandboxed process's mount namespace.

    Both source and target are guest paths (inside the namespace).
    Uses nsenter to enter the process's user + mount namespaces.
    """
    import subprocess

    nsenter = [
        "nsenter",
        "-U",
        "--preserve-credentials",
        "-m",
        "-r",
        "-t",
        str(pid),
        "--",
    ]
    subprocess.run([*nsenter, "mkdir", "-p", target], check=True, capture_output=True)
    subprocess.run(
        [*nsenter, "mount", "--bind", source, target],
        check=True,
        capture_output=True,
    )
