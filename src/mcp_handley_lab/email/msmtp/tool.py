"""MSMTP email sending provider."""

from pathlib import Path

from pydantic import BaseModel, Field

from mcp_handley_lab.common.process import run_command
from mcp_handley_lab.email.common import mcp


class SendResult(BaseModel):
    """Result of sending an email."""

    status: str = Field(default="success", description="The status of the send operation, typically 'success'.")
    recipient: str = Field(..., description="The primary recipient's email address (the 'To' field).")
    account_used: str = Field(default="", description="The msmtp account used for sending, if specified.")
    cc_recipients: list[str] = Field(default_factory=list, description="A list of email addresses in the 'Cc' field.")
    bcc_recipients: list[str] = Field(default_factory=list, description="A list of email addresses in the 'Bcc' field.")


def _parse_msmtprc(config_file: str = "") -> list[str]:
    """Parse msmtp config to extract account names."""
    msmtprc_path = Path(config_file) if config_file else Path.home() / ".msmtprc"
    if not msmtprc_path.exists():
        raise FileNotFoundError(f"msmtp configuration not found at {msmtprc_path}")

    accounts = []
    with open(msmtprc_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("account ") and not line.startswith("account default"):
                account_name = line.split()[1]
                accounts.append(account_name)

    return accounts


@mcp.tool(
    description="Send email using msmtp with configured accounts from ~/.msmtprc. Non-interactive automated sending with support for CC/BCC recipients."
)
def send(
    to: str = Field(
        ..., description="The primary recipient's email address."
    ),
    subject: str = Field(..., description="The subject line of the email."),
    body: str = Field(..., description="The main content (body) of the email."),
    account: str = Field(
        default="",
        description="The msmtp account to send from. If empty, the default account is used. Use 'list_accounts' to see options.",
    ),
    cc: str = Field(
        default="",
        description="Comma-separated list of email addresses for CC recipients.",
    ),
    bcc: str = Field(
        default="",
        description="Comma-separated list of email addresses for BCC recipients.",
    ),
) -> SendResult:
    """Send an email using msmtp with existing ~/.msmtprc configuration."""
    email_content = f"To: {to}\n"
    email_content += f"Subject: {subject}\n"

    if cc:
        email_content += f"Cc: {cc}\n"
    if bcc:
        email_content += f"Bcc: {bcc}\n"

    email_content += "\n"
    email_content += body

    cmd = ["msmtp"]
    if account:
        cmd.extend(["-a", account])

    recipients = [to]
    if cc:
        recipients.extend([addr.strip() for addr in cc.split(",")])
    if bcc:
        recipients.extend([addr.strip() for addr in bcc.split(",")])

    cmd.extend(recipients)

    input_bytes = email_content.encode()
    stdout, stderr = run_command(cmd, input_data=input_bytes)

    cc_list = [addr.strip() for addr in cc.split(",")] if cc else []
    bcc_list = [addr.strip() for addr in bcc.split(",")] if bcc else []

    return SendResult(
        recipient=to,
        account_used=account,
        cc_recipients=cc_list,
        bcc_recipients=bcc_list,
    )


@mcp.tool(
    description="List available msmtp accounts from ~/.msmtprc configuration. Use to discover valid account names for the send tool."
)
def list_accounts(
    config_file: str = Field(
        default="",
        description="Optional path to the msmtp configuration file. Defaults to `~/.msmtprc`.",
    )
) -> list[str]:
    """List available msmtp accounts by parsing msmtp config."""
    accounts = _parse_msmtprc(config_file)

    return accounts
