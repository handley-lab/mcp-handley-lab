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


@mcp.tool(description="""Sends an email programmatically and non-interactively using a pre-configured msmtp account.

This tool is ideal for automated notifications or sending emails from scripts without opening an interactive client. It relies on your existing `~/.msmtprc` configuration for server details, authentication, and sender information.

**Key Parameters:**
- `to`: The primary recipient's email address.
- `subject`: The subject line of the email.
- `body`: The plain text content of the email body.
- `account`: (Optional) The specific msmtp account to use for sending, as defined in `~/.msmtprc`. If omitted, the default account is used.
- `cc`: (Optional) Comma-separated list of carbon copy recipients.
- `bcc`: (Optional) Comma-separated list of blind carbon copy recipients.

**Behavior:**
- The email is constructed and piped directly to the `msmtp` command-line tool.
- The command executes synchronously and will raise an error if sending fails (e.g., due to configuration issues or network problems).

**Examples:**
```python
# Send a simple notification.
send(
    to="user@example.com",
    subject="Automated Task Complete",
    body="The nightly backup job has finished successfully."
)

# Send an email using a specific account with a CC.
send(
    to="team-lead@example.com",
    cc="team@example.com",
    subject="[Project X] Weekly Report",
    body="Please find the weekly report attached.",
    account="work_account"
)
```""")
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


@mcp.tool(description="""Lists all available sending accounts configured in your msmtp settings file (`~/.msmtprc`).

Use this tool to discover the valid account names you can use with the `send` tool's `account` parameter. It parses the configuration file and returns a list of all defined accounts, excluding the 'default' entry.

**Key Parameters:**
- `config_file`: (Optional) The path to a custom `msmtprc` file. If omitted, it defaults to `~/.msmtprc`.

**Behavior:**
- Reads the specified configuration file line by line.
- Extracts any line starting with "account" that is not "account default".
- Returns a formatted string listing the account names.

**Examples:**
```python
# List all configured accounts from the default location.
list_accounts()
# Example Output:
# Available msmtp accounts:
# - work_account
# - personal_gmail
```""")
def list_accounts(config_file: str = None) -> str:
    """List available msmtp accounts by parsing msmtp config."""
    accounts = _parse_msmtprc(config_file)

    if not accounts:
        return "Available msmtp accounts:\n(none configured)"

    return "Available msmtp accounts:\n" + "\n".join(
        f"- {account}" for account in accounts
    )


