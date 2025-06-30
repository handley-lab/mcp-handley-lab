# OAuth2 Setup for Gmail Testing

Since App Passwords are not available, you need OAuth2. Here are two options:

## Option 1: Use Gmail's Less Secure App Access (if available)
Sometimes available at: https://myaccount.google.com/lesssecureapps
(But this is also being phased out)

## Option 2: Full OAuth2 Setup

1. **Create OAuth2 Credentials**:
   - Go to https://console.cloud.google.com/
   - Create new project or select existing
   - Enable Gmail API
   - Create OAuth2 Client ID (Desktop application)
   - Download credentials JSON

2. **Use mutt_oauth2.py**:
   ```bash
   # Copy the OAuth2 script
   cp ~/.mutt/mutt_oauth2.py test_configs/
   
   # Initial authorization (interactive)
   python test_configs/mutt_oauth2.py \
     --generate_oauth2_token \
     --client_id=YOUR_CLIENT_ID \
     --client_secret=YOUR_CLIENT_SECRET \
     --refresh_token
   ```

3. **For CI**: Store the refresh token as a GitHub secret

## Option 3: Use XOAUTH2 with existing token

If you have an existing OAuth2 token from your personal Gmail setup, you might be able to:
1. Extract the refresh token
2. Store it as an environment variable
3. Use it for the test account

## Recommendation for CI Testing

Consider using a different email provider for testing that still supports app-specific passwords:
- Fastmail
- ProtonMail Bridge
- Self-hosted mail server (Dovecot)
- Mock IMAP server (greenmail, etc.)