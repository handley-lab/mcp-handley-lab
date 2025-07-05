"""OAuth2 authentication provider for email services."""
import configparser
from pathlib import Path

from mcp_handley_lab.email.common import mcp


def _parse_offlineimaprc(config_file: str = None) -> dict:
    """Parse offlineimap config to extract account configurations."""
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    if not config_path.exists():
        return {}

    config = configparser.ConfigParser()
    config.read(config_path)
    
    accounts = {}
    
    # Find all accounts in general section
    if config.has_section('general') and config.has_option('general', 'accounts'):
        account_names = [name.strip() for name in config.get('general', 'accounts').split(',')]
        
        for account_name in account_names:
            account_section = f"Account {account_name}"
            if config.has_section(account_section):
                remote_repo = config.get(account_section, 'remoterepository', fallback=None)
                if remote_repo and config.has_section(f"Repository {remote_repo}"):
                    accounts[account_name] = {
                        'remote_repo': remote_repo,
                        'section': f"Repository {remote_repo}"
                    }
    
    return accounts


def _get_m365_oauth2_config(account_name: str, config_file: str = None) -> dict:
    """Get Microsoft 365 OAuth2 configuration for a specific account."""
    config_path = Path(config_file) if config_file else Path.home() / ".offlineimaprc"
    if not config_path.exists():
        raise FileNotFoundError(f"offlineimap configuration not found at {config_path}")

    config = configparser.ConfigParser()
    config.read(config_path)
    
    accounts = _parse_offlineimaprc(config_file)
    if account_name not in accounts:
        raise ValueError(f"Account '{account_name}' not found in offlineimap configuration")
    
    repo_section = accounts[account_name]['section']
    if not config.has_section(repo_section):
        raise ValueError(f"Repository section '{repo_section}' not found")
    
    # Check if this is an OAuth2 configured account
    if not config.has_option(repo_section, 'auth_mechanisms'):
        return {}
    
    auth_mech = config.get(repo_section, 'auth_mechanisms')
    if 'XOAUTH2' not in auth_mech:
        return {}
    
    oauth2_config = {}
    oauth2_fields = [
        'oauth2_request_url',
        'oauth2_client_id', 
        'oauth2_client_secret',
        'oauth2_refresh_token',
        'remoteuser',
        'remotehost'
    ]
    
    for field in oauth2_fields:
        if config.has_option(repo_section, field):
            oauth2_config[field] = config.get(repo_section, field)
    
    return oauth2_config


def _refresh_m365_oauth2_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Refresh Microsoft 365 OAuth2 access token using MSAL."""
    try:
        from msal import ConfidentialClientApplication
    except ImportError:
        raise RuntimeError("msal library not available. Install with: pip install msal")
    
    # Create MSAL app
    app = ConfidentialClientApplication(
        client_id,
        client_credential=client_secret
    )
    
    # Acquire token using refresh token
    result = app.acquire_token_by_refresh_token(
        refresh_token,
        scopes=['https://outlook.office365.com/IMAP.AccessAsUser.All']
    )
    
    if 'error' in result:
        raise RuntimeError(f"Failed to refresh OAuth2 token: {result.get('error_description', result.get('error'))}")
    
    return result['access_token']


def _setup_m365_oauth2_interactive(client_id: str, client_secret: str) -> str:
    """Interactive Microsoft 365 OAuth2 setup to get refresh token."""
    try:
        from msal import ConfidentialClientApplication, SerializableTokenCache
    except ImportError:
        raise RuntimeError("msal library not available. Install with: pip install msal")
    
    redirect_uri = "http://localhost"
    scopes = ['https://outlook.office365.com/IMAP.AccessAsUser.All']
    
    # Use cache to extract the refresh token
    cache = SerializableTokenCache()
    app = ConfidentialClientApplication(
        client_id, 
        client_credential=client_secret, 
        token_cache=cache
    )
    
    # Get authorization URL
    url = app.get_authorization_request_url(scopes, redirect_uri=redirect_uri)
    
    return f"""To set up OAuth2 authentication:

1. Navigate to this URL in your web browser:
{url}

2. Complete the login process
3. After login, you'll be redirected to a blank page with a URL containing a 'code' parameter
4. Copy the entire redirect URL and use it with the get_m365_oauth2_token function

Example redirect URL format:
http://localhost/?code=M.C123_BL2...&state=...

Use the 'get_m365_oauth2_token' function with the authorization code to complete setup."""


@mcp.tool(name="oauth2_setup_m365", description="Set up Microsoft 365 OAuth2 authentication interactively.")
def setup_m365_oauth2(
    client_id: str = "08162f7c-0fd2-4200-a84a-f25a4db0b584",
    client_secret: str = "TxRBilcHdC6WGBee]fs?QR:SJ8nI[g82"
) -> str:
    """Interactive setup for Microsoft 365 OAuth2 authentication.
    
    Uses Thunderbird's public client credentials by default.
    Returns instructions for completing the OAuth2 flow.
    """
    return _setup_m365_oauth2_interactive(client_id, client_secret)


@mcp.tool(name="oauth2_get_m365_token", description="Complete Microsoft 365 OAuth2 setup with authorization code.")
def get_m365_oauth2_token(
    authorization_code: str,
    client_id: str = "08162f7c-0fd2-4200-a84a-f25a4db0b584", 
    client_secret: str = "TxRBilcHdC6WGBee]fs?QR:SJ8nI[g82"
) -> str:
    """Complete OAuth2 setup by exchanging authorization code for refresh token.
    
    Args:
        authorization_code: The authorization code from the redirect URL
        client_id: Microsoft app client ID (defaults to Thunderbird's)
        client_secret: Microsoft app client secret (defaults to Thunderbird's)
    
    Returns the refresh token for use in offlineimap configuration.
    """
    try:
        from msal import ConfidentialClientApplication, SerializableTokenCache
    except ImportError:
        raise RuntimeError("msal library not available. Install with: pip install msal")
    
    redirect_uri = "http://localhost"
    scopes = ['https://outlook.office365.com/IMAP.AccessAsUser.All']
    
    # Use cache to extract the refresh token
    cache = SerializableTokenCache()
    app = ConfidentialClientApplication(
        client_id, 
        client_credential=client_secret, 
        token_cache=cache
    )
    
    # Exchange authorization code for tokens
    result = app.acquire_token_by_authorization_code(
        authorization_code, 
        scopes, 
        redirect_uri=redirect_uri
    )
    
    if 'error' in result:
        raise RuntimeError(f"Failed to get access token: {result.get('error_description', result.get('error'))}")
    
    # Extract refresh token from cache
    refresh_tokens = cache.find('RefreshToken')
    if not refresh_tokens:
        raise RuntimeError("No refresh token found in response")
    
    refresh_token = refresh_tokens[0]['secret']
    
    return f"""OAuth2 setup completed successfully!

Refresh token: {refresh_token}

Add this to your .offlineimaprc file in the repository section:
auth_mechanisms = XOAUTH2
oauth2_request_url = https://login.microsoftonline.com/common/oauth2/v2.0/token
oauth2_client_id = {client_id}
oauth2_client_secret = {client_secret}
oauth2_refresh_token = {refresh_token}"""


@mcp.tool(name="oauth2_refresh_m365_credentials", description="Refresh Microsoft 365 OAuth2 access token for an account.")
def refresh_m365_credentials(account: str, config_file: str = None) -> str:
    """Refresh OAuth2 access token for a configured Microsoft 365 account.
    
    Args:
        account: Name of the account in offlineimap configuration
        config_file: Path to offlineimap config file (defaults to ~/.offlineimaprc)
    
    Returns current access token status and new token if refreshed.
    """
    oauth2_config = _get_m365_oauth2_config(account, config_file)
    
    if not oauth2_config:
        raise ValueError(f"Account '{account}' is not configured for Microsoft 365 OAuth2")
    
    required_fields = ['oauth2_client_id', 'oauth2_client_secret', 'oauth2_refresh_token']
    missing_fields = [field for field in required_fields if field not in oauth2_config]
    
    if missing_fields:
        raise ValueError(f"Missing OAuth2 configuration fields: {', '.join(missing_fields)}")
    
    try:
        access_token = _refresh_m365_oauth2_token(
            oauth2_config['oauth2_client_id'],
            oauth2_config['oauth2_client_secret'], 
            oauth2_config['oauth2_refresh_token']
        )
        
        return f"""OAuth2 credentials refreshed successfully for account '{account}'

Access token: {access_token[:50]}...

Current configuration:
- User: {oauth2_config.get('remoteuser', 'not configured')}
- Host: {oauth2_config.get('remotehost', 'not configured')}
- Client ID: {oauth2_config['oauth2_client_id']}

The access token is valid for approximately 1 hour."""
        
    except Exception as e:
        raise RuntimeError(f"Failed to refresh OAuth2 credentials: {str(e)}")


@mcp.tool(name="oauth2_list_m365_accounts", description="List accounts with Microsoft 365 OAuth2 configuration.")
def list_m365_oauth2_accounts(config_file: str = None) -> str:
    """List all offlineimap accounts configured with Microsoft 365 OAuth2.
    
    Args:
        config_file: Path to offlineimap config file (defaults to ~/.offlineimaprc)
    
    Returns list of accounts with OAuth2 configuration details.
    """
    accounts = _parse_offlineimaprc(config_file)
    
    if not accounts:
        return "No offlineimap accounts found in configuration."
    
    oauth2_accounts = []
    
    for account_name in accounts:
        try:
            oauth2_config = _get_m365_oauth2_config(account_name, config_file)
            if oauth2_config:
                oauth2_accounts.append({
                    'name': account_name,
                    'user': oauth2_config.get('remoteuser', 'not configured'),
                    'host': oauth2_config.get('remotehost', 'not configured'),
                    'client_id': oauth2_config.get('oauth2_client_id', 'not configured'),
                    'has_refresh_token': bool(oauth2_config.get('oauth2_refresh_token'))
                })
        except Exception:
            continue
    
    if not oauth2_accounts:
        return f"Found {len(accounts)} offlineimap accounts, but none are configured for Microsoft 365 OAuth2."
    
    result = f"Microsoft 365 OAuth2 configured accounts ({len(oauth2_accounts)}/{len(accounts)}):\n\n"
    
    for account in oauth2_accounts:
        result += f"Account: {account['name']}\n"
        result += f"  User: {account['user']}\n"
        result += f"  Host: {account['host']}\n"
        result += f"  Client ID: {account['client_id']}\n"
        result += f"  Refresh Token: {'✓ configured' if account['has_refresh_token'] else '✗ missing'}\n\n"
    
    return result


@mcp.tool(name="oauth2_validate_m365", description="Validate Microsoft 365 OAuth2 configuration for an account.")
def validate_m365_oauth2(account: str, config_file: str = None) -> str:
    """Validate Microsoft 365 OAuth2 configuration and test token refresh.
    
    Args:
        account: Name of the account in offlineimap configuration
        config_file: Path to offlineimap config file (defaults to ~/.offlineimaprc)
    
    Returns validation results and any issues found.
    """
    try:
        oauth2_config = _get_m365_oauth2_config(account, config_file)
        
        if not oauth2_config:
            return f"❌ Account '{account}' is not configured for Microsoft 365 OAuth2"
        
        required_fields = [
            'oauth2_client_id',
            'oauth2_client_secret', 
            'oauth2_refresh_token',
            'oauth2_request_url',
            'remoteuser',
            'remotehost'
        ]
        
        missing_fields = [field for field in required_fields if field not in oauth2_config]
        
        validation_results = []
        
        if missing_fields:
            validation_results.append(f"❌ Missing configuration fields: {', '.join(missing_fields)}")
        else:
            validation_results.append("✓ All required OAuth2 fields are configured")
        
        # Validate request URL
        expected_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        if oauth2_config.get('oauth2_request_url') != expected_url:
            validation_results.append(f"⚠️  Unexpected OAuth2 request URL: {oauth2_config.get('oauth2_request_url')}")
        else:
            validation_results.append("✓ OAuth2 request URL is correct")
        
        # Validate host for M365
        if oauth2_config.get('remotehost') != 'outlook.office365.com':
            validation_results.append(f"⚠️  Unexpected host for M365: {oauth2_config.get('remotehost')}")
        else:
            validation_results.append("✓ Remote host is configured for Microsoft 365")
        
        # Test token refresh if all required fields are present
        if not missing_fields:
            try:
                access_token = _refresh_m365_oauth2_token(
                    oauth2_config['oauth2_client_id'],
                    oauth2_config['oauth2_client_secret'],
                    oauth2_config['oauth2_refresh_token']
                )
                validation_results.append("✓ OAuth2 token refresh successful")
                validation_results.append(f"  Access token: {access_token[:50]}...")
            except Exception as e:
                validation_results.append(f"❌ OAuth2 token refresh failed: {str(e)}")
        
        return f"Microsoft 365 OAuth2 validation for account '{account}':\n\n" + "\n".join(validation_results)
        
    except Exception as e:
        return f"❌ Validation failed: {str(e)}"


