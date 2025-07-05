"""MSMTP email sending provider."""
from pathlib import Path

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


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
def send(
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
    input_bytes = email_content.encode()
    stdout, stderr = run_command(cmd, input_data=input_bytes)

    return f"Email sent successfully to {to}" + (
        f" (account: {account})" if account else ""
    )


@mcp.tool(description="List available msmtp accounts from ~/.msmtprc.")
def list_accounts(config_file: str = None) -> str:
    """List available msmtp accounts by parsing msmtp config."""
    accounts = _parse_msmtprc(config_file)

    if not accounts:
        return "Available msmtp accounts:\n(none configured)"

    return "Available msmtp accounts:\n" + "\n".join(
        f"- {account}" for account in accounts
    )


