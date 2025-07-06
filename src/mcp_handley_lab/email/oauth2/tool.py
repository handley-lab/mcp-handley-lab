"""OAuth2 authentication provider for email services."""
from mcp_handley_lab.email.common import mcp


@mcp.tool(name="oauth2_setup_m365", description="""Start Microsoft 365 OAuth2 authentication - Step 1 of 2-step process.

Initiates the OAuth2 authorization code flow for Microsoft 365 email access. This is the first step in a two-step authentication process.

Key Parameters:
- client_id: Microsoft app client ID (defaults to Thunderbird's public client)
- client_secret: Microsoft app client secret (defaults to Thunderbird's)

Behavior:
- Generates authorization URL for Microsoft 365 login
- Uses secure authorization code flow
- Requires user interaction in web browser
- Returns URL that must be opened in browser

Two-Step Process:
1. **setup_m365_oauth2**: Generate authorization URL (this tool)
2. **complete_m365_oauth2**: Exchange authorization code for tokens

Examples:
```python
# Start OAuth2 setup (Step 1)
setup_m365_oauth2()

# After user completes browser login:
# complete_m365_oauth2(redirect_url="http://localhost?code=...")
```

Note: Uses Thunderbird's client credentials by default for broad compatibility.""")
def setup_m365_oauth2(
    client_id: str = "08162f7c-0fd2-4200-a84a-f25a4db0b584",
    client_secret: str = "TxRBilcHdC6WGBee]fs?QR:SJ8nI[g82"
) -> str:
    """Start Microsoft 365 OAuth2 setup using authorization code flow.
    
    Uses Thunderbird's client credentials by default.
    Returns authorization URL - complete with oauth2_complete_m365.
    """
    from msal import ConfidentialClientApplication
    
    scopes = ['https://outlook.office365.com/IMAP.AccessAsUser.All']
    redirect_uri = "http://localhost"
    
    app = ConfidentialClientApplication(client_id, client_credential=client_secret)
    auth_url = app.get_authorization_request_url(scopes, redirect_uri=redirect_uri)
    
    return f"""OAuth2 Authorization Code Setup:

Claude should now open the following URL in your default browser:
{auth_url}

After you complete the login process, you will be redirected to a page showing "This site can't be reached" - this is expected! Copy the entire URL from the address bar (it contains your authorization code) and provide it to complete the OAuth2 setup with oauth2_complete_m365."""


@mcp.tool(name="oauth2_complete_m365", description="""Complete Microsoft 365 OAuth2 authentication - Step 2 of 2-step process.

Exchanges the authorization code for access and refresh tokens, completing the OAuth2 flow. This is the second step in the two-step authentication process.

Key Parameters:
- redirect_url: Complete URL from browser after login (contains authorization code)
- client_id: Microsoft app client ID (must match Step 1)
- client_secret: Microsoft app client secret (must match Step 1)

Behavior:
- Extracts authorization code from redirect URL
- Exchanges code for access and refresh tokens
- Generates ready-to-use offlineimap configuration
- Provides refresh token for long-term authentication

Token Exchange Process:
1. Parse authorization code from redirect URL
2. Contact Microsoft token endpoint
3. Receive access and refresh tokens
4. Extract refresh token for persistent authentication

Examples:
```python
# Complete OAuth2 setup (Step 2)
complete_m365_oauth2(
    redirect_url="http://localhost?code=0.ARoA6WgJJ9X2qk..."
)

# The redirect URL comes from browser address bar after login
# It will look like: http://localhost?code=LONG_CODE_HERE&state=...
```

Returns ready-to-use configuration for .offlineimaprc file.""")
def complete_m365_oauth2(
    redirect_url: str,
    client_id: str = "08162f7c-0fd2-4200-a84a-f25a4db0b584",
    client_secret: str = "TxRBilcHdC6WGBee]fs?QR:SJ8nI[g82"
) -> str:
    """Complete Microsoft 365 OAuth2 setup using the redirect URL from browser.
    
    Args:
        redirect_url: The complete URL from the browser after login (contains authorization code)
        client_id: Microsoft app client ID (defaults to Thunderbird's)
        client_secret: Microsoft app client secret (defaults to Thunderbird's)
    
    Returns the refresh token configuration for offlineimap.
    """
    from msal import ConfidentialClientApplication, SerializableTokenCache
    
    scopes = ['https://outlook.office365.com/IMAP.AccessAsUser.All']
    redirect_uri = "http://localhost"
    
    # Extract authorization code from redirect URL
    code_start = redirect_url.find('code=') + 5
    code_end = redirect_url.find('&', code_start) if '&' in redirect_url[code_start:] else len(redirect_url)
    auth_code = redirect_url[code_start:code_end]
    
    cache = SerializableTokenCache()
    app = ConfidentialClientApplication(client_id, client_credential=client_secret, token_cache=cache)
    
    # Exchange authorization code for tokens
    auth_result = app.acquire_token_by_authorization_code(auth_code, scopes, redirect_uri=redirect_uri)
    
    # Extract refresh token
    refresh_token = cache.find('RefreshToken')[0]['secret']
    
    return f"""✅ OAuth2 setup completed successfully!

Refresh token: {refresh_token}

Configuration needed for your .offlineimaprc file in the repository section:
auth_mechanisms = XOAUTH2
oauth2_request_url = https://login.microsoftonline.com/common/oauth2/v2.0/token
oauth2_client_id = {client_id}
oauth2_client_secret = {client_secret}
oauth2_refresh_token = {refresh_token}

Claude should offer to update the .offlineimaprc file automatically with this configuration.

To update your .offlineimaprc file, add these lines to the [Repository Your-Remote-Name] section:

```
[Repository Your-Remote-Name]
type = IMAP
remotehost = outlook.office365.com
remoteport = 993
remoteuser = your.email@domain.com
ssl = yes
auth_mechanisms = XOAUTH2
oauth2_request_url = https://login.microsoftonline.com/common/oauth2/v2.0/token
oauth2_client_id = {client_id}
oauth2_client_secret = {client_secret}
oauth2_refresh_token = {refresh_token}
```"""