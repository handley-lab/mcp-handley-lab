# Google Calendar Setup

The Google Calendar tool requires OAuth 2.0 credentials to access your calendar data securely.

## Prerequisites

You'll need API keys for the Google Calendar tool. Add these to your environment:

```bash
export GOOGLE_CREDENTIALS_FILE="~/.config/google/credentials.json"
export GOOGLE_TOKEN_FILE="~/.config/google/token.json"
```

## Setup Steps

### 1. Enable the Google Calendar API

- Go to the [Google Cloud Console](https://console.cloud.google.com/)
- Create a new project or select an existing one
- In the navigation menu, go to **APIs & Services > Library**
- Search for "Google Calendar API" and enable it

### 2. Create OAuth 2.0 Credentials

- Go to **APIs & Services > Credentials**
- Click **+ CREATE CREDENTIALS** and select **OAuth client ID**
- If prompted, configure the consent screen. Select **External** and provide an app name, user support email, and developer contact information
- For the **Application type**, select **Desktop app**
- Click **Create**

### 3. Download and Save Credentials

- A dialog will appear with your credentials. Click **DOWNLOAD JSON**
- Save this file to the path you specified in `GOOGLE_CREDENTIALS_FILE` in your configuration (e.g., `~/.config/google/credentials.json`)

### 4. First-time Authentication

- The first time you run the `mcp-google-calendar` tool, it will open a browser window asking you to authorize access to your Google Calendar
- Complete the authorization flow. The tool will then create and save a token file at the path specified by `GOOGLE_TOKEN_FILE` (e.g., `~/.config/google/token.json`) for future, non-interactive use

## Troubleshooting

### Common Issues

- **Permission denied**: Ensure the credentials file is readable
- **Token expired**: Delete the token file and re-authenticate
- **API not enabled**: Verify the Google Calendar API is enabled in your project

### File Locations

The tool expects these files:
- Credentials: `~/.config/google/credentials.json` (or path in `GOOGLE_CREDENTIALS_FILE`)
- Token: `~/.config/google/token.json` (or path in `GOOGLE_TOKEN_FILE`)

Make sure the directories exist and are writable.
