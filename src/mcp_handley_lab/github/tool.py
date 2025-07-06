#!/usr/bin/env python3

import json
import time

from mcp.server.fastmcp import FastMCP

from mcp_handley_lab.common.process import run_command

mcp = FastMCP("GitHub CI Monitor")


@mcp.tool(
    description="Continuously monitors the CI checks for a GitHub pull request, providing live updates. Specify the `pr_number` to watch. The tool reports the status of each check and automatically exits when all checks pass, any check fails, or the `timeout_minutes` is reached. Returns a log of the monitoring session."
)
def monitor_pr_checks(
    pr_number: int,
    timeout_minutes: int = 30,
    check_interval_seconds: int = 30,
) -> str:
    """Monitor CI checks for a PR with live status updates."""
    if timeout_minutes <= 0 or check_interval_seconds <= 0:
        raise ValueError("timeout_minutes and check_interval_seconds must be positive")

    timeout_seconds = timeout_minutes * 60
    start_time = time.time()
    check_count = 0
    status_log = []

    status_log.append(f"Starting CI monitoring for PR #{pr_number}")
    status_log.append(f"Timeout: {timeout_minutes} minutes")
    status_log.append(f"Check interval: {check_interval_seconds} seconds")
    status_log.append("=" * 50)

    monitoring_finished = False

    while time.time() - start_time < timeout_seconds and not monitoring_finished:
        check_count += 1
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        status_log.append(f"[{current_time}] Check #{check_count}")

        # Get current status in JSON format for parsing
        stdout, stderr = run_command(
            ["gh", "pr", "checks", str(pr_number), "--json", "state,name"]
        )
        checks_data = json.loads(stdout.decode("utf-8").strip())

        if not checks_data:
            status_log.append("  No checks found for this PR")
        else:
            # Analyze check status
            total_checks = len(checks_data)
            passed_checks = sum(
                1
                for check in checks_data
                if check.get("state") in ["success", "SUCCESS"]
            )
            failed_checks = sum(
                1
                for check in checks_data
                if check.get("state") in ["failure", "FAILURE"]
            )
            pending_checks = sum(
                1
                for check in checks_data
                if check.get("state")
                in ["pending", "PENDING", "in_progress", "IN_PROGRESS"]
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
                status_log.append(f"  Use `gh pr checks {pr_number}` to see details")
                monitoring_finished = True
                break
            elif pending_checks == 0 and passed_checks == total_checks:
                status_log.append("  ✅ All checks passed! Ready to merge.")
                status_log.append(f"  Use `gh pr merge {pr_number} --squash` to merge")
                monitoring_finished = True
                break
            else:
                status_log.append(f"  ⏳ Waiting for {pending_checks} pending check(s)")

        # Wait before next check if not done and still within timeout
        if time.time() - start_time < timeout_seconds and not monitoring_finished:
            status_log.append(f"  Waiting {check_interval_seconds} seconds...")
            time.sleep(check_interval_seconds)

    # Check if we timed out
    if not monitoring_finished and time.time() - start_time >= timeout_seconds:
        status_log.append(f"⏰ Monitoring timed out after {timeout_minutes} minutes")
        status_log.append(f"  Use `gh pr checks {pr_number}` to check current status")

    status_log.append("=" * 50)
    status_log.append("Monitoring complete")

    return "\n".join(status_log)


@mcp.tool(
    description="Check GitHub CI Monitor server status and gh command availability"
)
def server_info() -> str:
    """Check server status and GitHub CLI availability."""
    # Check gh version
    stdout, stderr = run_command(["gh", "--version"])
    version = stdout.decode("utf-8").strip()

    # Check authentication status
    stdout, stderr = run_command(["gh", "auth", "status"])
    auth_status = stdout.decode("utf-8").strip()

    # Extract first line of auth status
    first_auth_line = auth_status.split('\n')[0] if auth_status else 'Unknown'

    return f"""GitHub CI Monitor Server Status
==================================
Status: Connected and ready
GitHub CLI Version: {version.split()[0] if version else 'Unknown'}
Authentication: {first_auth_line}

Available Functions:
- monitor_pr_checks: Monitor CI status with live updates

Use native gh CLI for other operations:
- gh pr checks 25      # Check current status
- gh pr merge 25       # Merge PR #25
- gh pr list           # List open PRs
- gh pr view 25        # View PR details"""


if __name__ == "__main__":
    mcp.run()
