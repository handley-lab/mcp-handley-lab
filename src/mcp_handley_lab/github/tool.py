#!/usr/bin/env python3

import json
import time
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.shared.models import ServerInfo


class CheckStatus(BaseModel):
    """Individual check status."""

    name: str
    state: str


class MonitorResult(BaseModel):
    """Result of monitoring PR checks."""

    final_status: Literal["success", "failure", "timeout"]
    passed_checks: int
    failed_checks: int
    pending_checks: int
    total_checks: int
    log: str
    check_details: list[CheckStatus]


mcp = FastMCP("GitHub CI Monitor")


@mcp.tool(
    description="Continuously monitors the CI checks for a GitHub pull request, providing live updates. Specify the `pr_number` to watch. The tool reports the status of each check and automatically exits when all checks pass, any check fails, or the `timeout_minutes` is reached. Returns a log of the monitoring session."
)
def monitor_pr_checks(
    pr_number: int,
    timeout_minutes: int = 30,
    check_interval_seconds: int = 30,
) -> MonitorResult:
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
    passed_checks = 0
    failed_checks = 0
    pending_checks = 0
    total_checks = 0
    checks_data = []

    while time.time() - start_time < timeout_seconds and not monitoring_finished:
        check_count += 1
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        status_log.append(f"[{current_time}] Check #{check_count}")

        stdout, stderr = run_command(
            ["gh", "pr", "checks", str(pr_number), "--json", "state,name"]
        )
        checks_data = json.loads(stdout.decode("utf-8").strip())

        if not checks_data:
            status_log.append("  No checks found for this PR")
        else:
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

            for check in checks_data:
                name = check.get("name", "unknown")
                state = check.get("state", "unknown")
                status_log.append(f"    {name}: {state}")

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

        if time.time() - start_time < timeout_seconds and not monitoring_finished:
            status_log.append(f"  Waiting {check_interval_seconds} seconds...")
            time.sleep(check_interval_seconds)

    if not monitoring_finished and time.time() - start_time >= timeout_seconds:
        status_log.append(f"⏰ Monitoring timed out after {timeout_minutes} minutes")
        status_log.append(f"  Use `gh pr checks {pr_number}` to check current status")

    status_log.append("=" * 50)
    status_log.append("Monitoring complete")

    # Determine final status
    if monitoring_finished:
        final_status = "failure" if failed_checks > 0 else "success"
    else:
        final_status = "timeout"

    # Get final check details
    final_check_details = [
        CheckStatus(
            name=check.get("name", "unknown"), state=check.get("state", "unknown")
        )
        for check in checks_data
    ]

    return MonitorResult(
        final_status=final_status,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        pending_checks=pending_checks,
        total_checks=total_checks,
        log="\n".join(status_log),
        check_details=final_check_details,
    )


@mcp.tool(
    description="Check GitHub CI Monitor server status and gh command availability"
)
def server_info() -> ServerInfo:
    """Check server status and GitHub CLI availability."""
    stdout, stderr = run_command(["gh", "--version"])
    version = stdout.decode("utf-8").strip()

    stdout, stderr = run_command(["gh", "auth", "status"])
    auth_status = stdout.decode("utf-8").strip()

    first_auth_line = auth_status.split("\n")[0] if auth_status else "Unknown"

    return ServerInfo(
        name="GitHub CI Monitor",
        version=version.split()[0] if version else "Unknown",
        status="active",
        capabilities=[
            "monitor_pr_checks - Monitor CI status with live updates",
            "server_info - Get server status",
        ],
        dependencies={
            "gh": version.split()[0] if version else "Unknown",
            "auth_status": first_auth_line,
        },
    )


if __name__ == "__main__":
    mcp.run()
