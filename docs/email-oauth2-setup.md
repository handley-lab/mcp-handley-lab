# Microsoft 365 OAuth2 Setup for Email

This guide explains how to set up OAuth2 authentication for Microsoft 365 (Outlook/Office 365) email accounts with offlineimap.

## Why OAuth2?

Microsoft disabled basic authentication (username/password) for IMAP access. You now need OAuth2 tokens to sync email from Outlook/Office 365 accounts.

## Prerequisites

- Python 3.10+
- MSAL library: `pip install msal`
- offlineimap configured for your account

## Setup Process

### Step 1: Generate Authorization URL

Run this Python script to get a Microsoft login URL:

```python
from msal import ConfidentialClientApplication

# Thunderbird's public client credentials (safe to use)
client_id = "08162f7c-0fd2-4200-a84a-f25a4db0b584"
client_secret = "TxRBilcHdC6WGBee]fs?QR:SJ8nI[g82"
scopes = ["https://outlook.office365.com/IMAP.AccessAsUser.All"]

app = ConfidentialClientApplication(client_id, client_credential=client_secret)
auth_url = app.get_authorization_request_url(scopes, redirect_uri="http://localhost")
print(f"Open this URL in your browser:\n{auth_url}")
```

### Step 2: Authenticate in Browser

1. Open the printed URL in your web browser
2. Log in with your Microsoft 365 account
3. Grant the requested permissions
4. You'll be redirected to a page showing "This site can't be reached" - this is expected

### Step 3: Extract the Refresh Token

Copy the full URL from your browser's address bar and run:

```python
from msal import ConfidentialClientApplication, SerializableTokenCache

# Paste your redirect URL here
redirect_url = "http://localhost/?code=..."  # Your full URL

client_id = "08162f7c-0fd2-4200-a84a-f25a4db0b584"
client_secret = "TxRBilcHdC6WGBee]fs?QR:SJ8nI[g82"
scopes = ["https://outlook.office365.com/IMAP.AccessAsUser.All"]

# Extract authorization code from URL
code_start = redirect_url.find("code=") + 5
code_end = redirect_url.find("&", code_start) if "&" in redirect_url[code_start:] else len(redirect_url)
auth_code = redirect_url[code_start:code_end]

# Exchange code for tokens
cache = SerializableTokenCache()
app = ConfidentialClientApplication(client_id, client_credential=client_secret, token_cache=cache)
app.acquire_token_by_authorization_code(auth_code, scopes, redirect_uri="http://localhost")

refresh_token = cache.find("RefreshToken")[0]["secret"]
print(f"Refresh token:\n{refresh_token}")
```

### Step 4: Configure offlineimap

Add or update your `~/.offlineimaprc` with the OAuth2 settings:

```ini
[Repository YourAccountName-Remote]
type = IMAP
remotehost = outlook.office365.com
remoteport = 993
remoteuser = your.email@domain.com
ssl = yes
auth_mechanisms = XOAUTH2
oauth2_request_url = https://login.microsoftonline.com/common/oauth2/v2.0/token
oauth2_client_id = 08162f7c-0fd2-4200-a84a-f25a4db0b584
oauth2_client_secret = TxRBilcHdC6WGBee]fs?QR:SJ8nI[g82
oauth2_refresh_token = <your-token-from-step-3>
```

Replace:
- `YourAccountName-Remote` with your repository name
- `your.email@domain.com` with your email address
- `YOUR_REFRESH_TOKEN_HERE` with the refresh token from Step 3

### Step 5: Test the Configuration

```bash
offlineimap --dry-run -a YourAccountName
```

## Token Expiry

Refresh tokens are long-lived but can expire if:
- Not used for 90 days
- Password changed
- Admin revokes access

If sync fails with authentication errors, repeat the setup process to get a new token.

## About the Client Credentials

The client ID and secret used here are Thunderbird's public OAuth2 credentials. They're safe to use and widely deployed. You can also register your own Azure AD application if preferred.

## Troubleshooting

**"AUTHENTICATE failed"**: Token expired or invalid. Re-run the setup.

**"Invalid client"**: Check client_id and client_secret are correct.

**"Consent required"**: Your organization may require admin consent. Contact your IT administrator.
