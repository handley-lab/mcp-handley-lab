"""GitHub CI monitoring and auto-merge tool.

Provides automated CI monitoring and merge capabilities that aren't available
natively in the GitHub CLI. For basic GitHub operations, use `gh` directly.
"""

import json
import time

from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.common.process import run_command

mcp = FastMCP("GitHub CI Monitor")


def _run_gh_command(args: list[str]) -> str:
    """Run a GitHub CLI command and return output."""
    cmd = ["gh"] + args
    try:
        stdout, stderr = run_command(cmd)
        return stdout.decode("utf-8").strip()
    except Exception as e:
        # Propagate the error from run_command
        raise RuntimeError(f"GitHub CLI command failed: {e}") from e


@mcp.tool(
    description="""Monitor CI checks for a pull request continuously.

This provides functionality not available in the native GitHub CLI - continuous
monitoring of CI status with live updates. Use `gh pr merge` manually when ready.

Key Parameters:
- pr_number: The pull request number to monitor
- timeout_minutes: Maximum time to monitor before giving up (default: 30)
- check_interval_seconds: How often to check status (default: 30)

Features:
- Live status updates with timestamps
- Detailed check-by-check reporting
- Automatic completion when all checks pass or any fail
- Timeout protection to prevent infinite loops

Examples:
```python
# Monitor PR #25 with default settings
monitor_pr_checks(pr_number=25)

# Monitor for up to 1 hour, checking every minute
monitor_pr_checks(pr_number=25, timeout_minutes=60, check_interval_seconds=60)
```

Note: This tool only monitors. Use `gh pr merge --squash` or similar to actually
merge when you see all checks pass.
"""
)
def monitor_pr_checks(
    pr_number: int, timeout_minutes: int = 30, check_interval_seconds: int = 30
) -> str:
    """Monitor CI checks for a PR with live status updates."""

    if timeout_minutes <= 0 or check_interval_seconds <= 0:
        raise ValueError("timeout_minutes and check_interval_seconds must be positive")

    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    check_count = 0

    status_log = [f"Starting CI monitoring for PR #{pr_number}"]
    status_log.append(f"Timeout: {timeout_minutes} minutes")
    status_log.append(f"Check interval: {check_interval_seconds} seconds")
    status_log.append("=" * 50)

    try:
        monitoring_finished = False

        while time.time() - start_time < timeout_seconds and not monitoring_finished:
            check_count += 1
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            status_log.append(f"[{current_time}] Check #{check_count}")

            try:
                # Get current status in JSON format for parsing
                result = _run_gh_command(["pr", "checks", str(pr_number), "--json"])
                checks_data = json.loads(result)

                if not checks_data:
                    status_log.append("  No checks found for this PR")
                else:
                    # Analyze check status
                    total_checks = len(checks_data)
                    passed_checks = sum(
                        1 for check in checks_data if check.get("state") == "success"
                    )
                    failed_checks = sum(
                        1 for check in checks_data if check.get("state") == "failure"
                    )
                    pending_checks = sum(
                        1
                        for check in checks_data
                        if check.get("state") in ["pending", "in_progress"]
                    )

                    status_log.append(
                        f"  Checks: {passed_checks}/{total_checks} passed, {failed_checks} failed, {pending_checks} pending"
                    )

                    # Log individual check statuses
                    for check in checks_data:
                        name = check.get("name", "unknown")
                        state = check.get("state", "unknown")
                        status_log.append(f"    {name}: {state}")

                    # Check if we're done monitoring
                    if failed_checks > 0:
                        status_log.append(
                            f"  ❌ {failed_checks} check(s) failed - monitoring stopped"
                        )
                        status_log.append(
                            "  Use `gh pr checks {pr_number}` to see details"
                        )
                        monitoring_finished = True
                        break
                    elif pending_checks == 0 and passed_checks == total_checks:
                        status_log.append("  ✅ All checks passed! Ready to merge.")
                        status_log.append(
                            f"  Use `gh pr merge {pr_number} --squash` to merge"
                        )
                        monitoring_finished = True
                        break
                    else:
                        status_log.append(
                            f"  ⏳ Waiting for {pending_checks} pending check(s)"
                        )

            except json.JSONDecodeError as e:
                status_log.append(f"  ❌ Failed to parse check status: {e}")
            except Exception as e:
                status_log.append(f"  ❌ Error checking status: {e}")

            # Wait before next check if not done and still within timeout
            if time.time() - start_time < timeout_seconds and not monitoring_finished:
                status_log.append(f"  Waiting {check_interval_seconds} seconds...")
                time.sleep(check_interval_seconds)

        # Check if we timed out
        if not monitoring_finished and time.time() - start_time >= timeout_seconds:
            status_log.append(
                f"⏰ Monitoring timed out after {timeout_minutes} minutes"
            )
            status_log.append(
                f"  Use `gh pr checks {pr_number}` to check current status"
            )

    except KeyboardInterrupt:
        status_log.append("🛑 Monitoring interrupted by user")
    except Exception as e:
        status_log.append(f"❌ Monitoring failed: {e}")

    status_log.append("=" * 50)
    status_log.append("Monitoring complete")

    return "\n".join(status_log)


@mcp.tool(
    description="Checks GitHub CI Monitor server status and gh command availability. Returns gh version information and authentication status. Use this to verify gh is installed and authenticated before monitoring PRs."
)
def server_info() -> str:
    """Get server status and gh version."""
    try:
        # Check gh version
        version = _run_gh_command(["--version"])

        # Check authentication status
        try:
            auth_status = _run_gh_command(["auth", "status"])
        except Exception:
            auth_status = "Not authenticated or no access"

        return f"""GitHub CI Monitor Server Status
==================================
Status: Connected and ready
GitHub CLI Version: {version.split()[2] if len(version.split()) > 2 else version}

Authentication Status:
{auth_status}

Available tools:
- monitor_pr_checks: Monitor CI checks for a PR with live updates
- server_info: Get server status and version information

For other GitHub operations, use the native `gh` CLI:
- gh pr status          # Check your PRs
- gh pr checks 25       # Check CI status for PR #25
- gh pr merge 25        # Merge PR #25
- gh pr list           # List open PRs
- gh pr view 25        # View PR details"""

    except FileNotFoundError as e:
        raise RuntimeError("gh command not found - GitHub CLI must be installed") from e
    except Exception as e:
        raise RuntimeError(f"Failed to get server info: {e}") from e


if __name__ == "__main__":
    mcp.run()
