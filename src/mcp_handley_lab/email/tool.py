"""Email client MCP tool integrating msmtp, offlineimap, and notmuch."""
import asyncio
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Email")


async def _run_command(
    cmd: list[str], input_text: str | None = None, cwd: str | None = None
) -> str:
    """Run a shell command and return output."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if input_text else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stdout, stderr = await process.communicate(
            input=input_text.encode() if input_text else None
        )

        if process.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            raise RuntimeError(f"Command '{' '.join(cmd)}' failed: {error_msg}")

        return stdout.decode().strip()
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Command '{cmd[0]}' not found. Please install {cmd[0]}."
        ) from e


def _parse_msmtprc(config_file: str = None) -> list[str]:
    """Parse msmtp config to extract account names."""
    msmtprc_path = Path(config_file) if config_file else Path.home() / ".msmtprc"
    if not msmtprc_path.exists():
        return []

    accounts = []
    with open(msmtprc_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("account ") and not line.startswith("account default"):
                account_name = line.split()[1]
                accounts.append(account_name)

    return accounts


@mcp.tool(description="Send an email using msmtp.")
async def send(
    to: str,
    subject: str,
    body: str,
    account: str | None = None,
    cc: str | None = None,
    bcc: str | None = None,
) -> str:
    """Send an email using msmtp with existing ~/.msmtprc configuration."""
    # Create email message
    email_content = f"To: {to}\n"
    email_content += f"Subject: {subject}\n"

    if cc:
        email_content += f"Cc: {cc}\n"
    if bcc:
        email_content += f"Bcc: {bcc}\n"

    email_content += "\n"  # Empty line separates headers from body
    email_content += body

    # Build msmtp command
    cmd = ["msmtp"]
    if account:
        cmd.extend(["-a", account])

    # Add recipients
    recipients = [to]
    if cc:
        recipients.extend([addr.strip() for addr in cc.split(",")])
    if bcc:
        recipients.extend([addr.strip() for addr in bcc.split(",")])

    cmd.extend(recipients)

    # Send email
    await _run_command(cmd, input_text=email_content)

    return f"Email sent successfully to {to}" + (
        f" (account: {account})" if account else ""
    )


@mcp.tool(description="List available msmtp accounts from ~/.msmtprc.")
async def list_accounts(config_file: str = None) -> str:
    """List available msmtp accounts by parsing msmtp config."""
    accounts = _parse_msmtprc(config_file)

    if not accounts:
        return "No msmtp accounts found in ~/.msmtprc"

    return "Available msmtp accounts:\n" + "\n".join(
        f"- {account}" for account in accounts
    )


@mcp.tool(description="Synchronize emails using offlineimap with one-time sync.")
async def sync(account: str | None = None) -> str:
    """Run offlineimap to synchronize emails."""
    cmd = ["offlineimap", "-o1"]  # -o1 for one-time sync

    if account:
        cmd.extend(["-a", account])

    try:
        output = await _run_command(cmd)
        return f"Email sync completed successfully\n{output}"
    except RuntimeError as e:
        # offlineimap often returns non-zero exit codes even on success
        # Check if it's a real error or just a warning
        if "ERROR" in str(e).upper():
            raise e
        return f"Email sync completed with warnings\n{str(e)}"


@mcp.tool(description="Get offlineimap sync status and information.")
async def sync_status(config_file: str = None) -> str:
    """Check offlineimap sync status."""
    # Check if offlineimap config exists
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    if not config_path.exists():
        return "No offlineimap configuration found at ~/.offlineimaprc"

    # Run dry-run to check configuration
    output = await _run_command(["offlineimap", "--dry-run", "-o1"])
    return f"Offlineimap configuration valid:\n{output}"


@mcp.tool(description="Get information about configured email repositories.")
async def repo_info(config_file: str = None) -> str:
    """Get information about configured offlineimap repositories."""
    output = await _run_command(["offlineimap", "--info"])
    return f"Repository information:\n{output}"


@mcp.tool(description="Preview what would be synced without actually syncing.")
async def sync_preview(account: str | None = None) -> str:
    """Preview email sync operations without making changes."""
    cmd = ["offlineimap", "--dry-run", "-o1"]

    if account:
        cmd.extend(["-a", account])

    output = await _run_command(cmd)
    return f"Sync preview{' for account ' + account if account else ''}:\n{output}"


@mcp.tool(description="Perform quick sync without updating message flags.")
async def quick_sync(account: str | None = None) -> str:
    """Perform quick email sync without updating flags."""
    cmd = ["offlineimap", "-q", "-o1"]

    if account:
        cmd.extend(["-a", account])

    try:
        output = await _run_command(cmd)
        return f"Quick sync completed successfully\n{output}"
    except RuntimeError as e:
        # offlineimap often returns non-zero exit codes even on success
        if "ERROR" in str(e).upper():
            raise e
        return f"Quick sync completed with warnings\n{str(e)}"


@mcp.tool(description="Sync specific folders only.")
async def sync_folders(folders: str, account: str | None = None) -> str:
    """Sync only specified folders."""
    cmd = ["offlineimap", "-o1", "-f", folders]

    if account:
        cmd.extend(["-a", account])

    try:
        output = await _run_command(cmd)
        return f"Folder sync completed successfully\n{output}"
    except RuntimeError as e:
        if "ERROR" in str(e).upper():
            raise e
        return f"Folder sync completed with warnings\n{str(e)}"


@mcp.tool(description="Search emails using notmuch.")
async def search(query: str, limit: int = 20) -> str:
    """Search emails using notmuch query syntax."""
    cmd = ["notmuch", "search", "--limit", str(limit), query]

    output = await _run_command(cmd)
    if not output:
        return f"No emails found matching query: {query}"
    return f"Search results for '{query}':\n{output}"


@mcp.tool(description="Show email content for a specific message ID or query.")
async def show(query: str, part: str | None = None) -> str:
    """Show email content using notmuch show."""
    cmd = ["notmuch", "show"]

    # Add format options for plain text
    cmd.extend(["--format=text"])

    if part:
        cmd.extend(["--part", part])

    cmd.append(query)

    output = await _run_command(cmd)
    return output


@mcp.tool(description="Create a new notmuch database or update existing one.")
async def new() -> str:
    """Index newly received emails with notmuch new."""
    output = await _run_command(["notmuch", "new"])
    return f"Notmuch database updated:\n{output}"


@mcp.tool(description="List all tags in the notmuch database.")
async def list_tags() -> str:
    """List all tags in the notmuch database."""
    output = await _run_command(["notmuch", "search", "--output=tags", "*"])
    if not output:
        return "No tags found in the database"
    tags = sorted(output.split("\n"))
    return "Available tags:\n" + "\n".join(f"- {tag}" for tag in tags if tag)


@mcp.tool(description="Get configuration information from notmuch.")
async def config(key: str | None = None) -> str:
    """Get notmuch configuration values."""
    cmd = ["notmuch", "config", "list"]

    if key:
        cmd = ["notmuch", "config", "get", key]

    output = await _run_command(cmd)
    if key:
        return f"{key} = {output}"
    return f"Notmuch configuration:\n{output}"


@mcp.tool(description="Count emails matching a notmuch query.")
async def count(query: str) -> str:
    """Count emails matching a notmuch query."""
    cmd = ["notmuch", "count", query]

    count_result = await _run_command(cmd)
    return f"Found {count_result} emails matching '{query}'"


@mcp.tool(description="Add or remove tags from emails using notmuch.")
async def tag(
    message_id: str, add_tags: str | None = None, remove_tags: str | None = None
) -> str:
    """Add or remove tags from a specific email using notmuch."""
    if not add_tags and not remove_tags:
        raise ValueError("Must specify either add_tags or remove_tags")

    cmd = ["notmuch", "tag"]

    # Add tags to add
    if add_tags:
        for tag in add_tags.split(","):
            tag = tag.strip()
            if tag:
                cmd.append(f"+{tag}")

    # Add tags to remove
    if remove_tags:
        for tag in remove_tags.split(","):
            tag = tag.strip()
            if tag:
                cmd.append(f"-{tag}")

    # Add message ID
    cmd.append(f"id:{message_id}")

    await _run_command(cmd)
    changes = []
    if add_tags:
        changes.append(f"added: {add_tags}")
    if remove_tags:
        changes.append(f"removed: {remove_tags}")

    return f"Tags updated for message {message_id} ({', '.join(changes)})"


@mcp.tool(description="Check email tool server status and verify tool availability.")
async def server_info(config_file: str = None) -> str:
    """Check the status of email tools and their configurations."""
    status = ["Email Tool Server Status:"]

    # Check msmtp
    try:
        msmtp_version = (await _run_command(["msmtp", "--version"])).split("\n")[0]
        accounts = _parse_msmtprc()
        status.append(f"✓ msmtp: {msmtp_version}")
        status.append(f"  Accounts: {len(accounts)} configured")
    except RuntimeError as e:
        status.append(f"✗ msmtp: {e}")

    # Check offlineimap
    try:
        offlineimap_version = (await _run_command(["offlineimap", "--version"])).split(
            "\n"
        )[0]
        config_path = (
            Path(config_file) if config_file else Path.home() / ".offlineimaprc"
        )
        config_exists = config_path.exists()
        status.append(f"✓ offlineimap: {offlineimap_version}")
        status.append(f"  Config: {'found' if config_exists else 'not found'}")
    except RuntimeError as e:
        status.append(f"✗ offlineimap: {e}")

    # Check notmuch
    try:
        notmuch_version = await _run_command(["notmuch", "--version"])
        status.append(f"✓ notmuch: {notmuch_version}")

        # Check if notmuch database exists
        try:
            db_info = await _run_command(["notmuch", "count", "*"])
            status.append(f"  Database: {db_info} messages indexed")
        except RuntimeError:
            status.append("  Database: not initialized or accessible")
    except RuntimeError as e:
        status.append(f"✗ notmuch: {e}")

    return "\n".join(status)


if __name__ == "__main__":
    mcp.run()
