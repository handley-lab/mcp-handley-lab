# CI Test Setup for Email Integration

## Current Configuration Status ✅

The CI is now configured to run email integration tests with the following setup:

### System Dependencies Installed
- `msmtp` - SMTP client for sending emails
- `offlineimap3` - IMAP client for syncing emails
- `notmuch` - Email indexing and search
- `mutt` - Email client

### Required Secrets
The following GitHub repository secrets need to be configured:

1. **GMAIL_TEST_PASSWORD** - App password for handleylab@gmail.com test account
2. **GOOGLE_MAPS_API_KEY** - API key for Google Maps integration tests

### Test Configuration Files
- `/tests/fixtures/email/msmtprc` - Configured to use `$GMAIL_TEST_PASSWORD`
- `/tests/fixtures/email/offlineimaprc` - Configured to use `get_test_password()` function
- `/tests/fixtures/email/offlineimap_test.py` - Helper function that reads `$GMAIL_TEST_PASSWORD`

## Setting Up Gmail Test Account

### Option 1: Use Dedicated Test Gmail Account (Current)

1. **Create Gmail account**: Use existing `handleylab@gmail.com` or create new test account
2. **Enable 2FA**: Required for app passwords
3. **Generate app password**:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail" application
4. **Add to GitHub Secrets**:
   - Repository Settings → Secrets and variables → Actions
   - Add `GMAIL_TEST_PASSWORD` with the app password

### Option 2: Alternative Email Providers

For reduced Gmail dependency, consider:

```ini
# Outlook.com alternative
[Repository HandleyLab-Remote]
type = IMAP
remotehost = outlook.office365.com
remoteuser = testaccount@outlook.com
remotepasseval = get_test_password()
ssl = yes
```

## Test Behavior

### With GMAIL_TEST_PASSWORD Set
- Email integration tests run with real Gmail infrastructure
- Tests send actual emails and verify receipt
- Complete send-receive-sync cycle validation

### Without GMAIL_TEST_PASSWORD Set
- Email integration tests are skipped with message:
  ```
  "Gmail test credentials not available (set GMAIL_TEST_PASSWORD)"
  ```
- Other tests continue normally

## Local Development

To run email integration tests locally:

```bash
export GMAIL_TEST_PASSWORD="your-app-password"
python -m pytest tests/integration/test_email_integration.py -v
```

## Security Considerations

- **App passwords only**: Never use real Gmail passwords
- **Dedicated test account**: Don't use personal email accounts
- **Test email cleanup**: Tests automatically delete sent emails after verification
- **Rate limiting**: Gmail has sending limits for app passwords (~100 emails/day)

## Troubleshooting

### Common Issues
1. **"Account not found"**: Check GMAIL_TEST_PASSWORD is set correctly
2. **"Authentication failed"**: Verify app password hasn't expired
3. **"Python file not found"**: Ensure tests run from correct working directory
4. **"IMAP connection failed"**: Check Gmail IMAP is enabled for the account

### Debug Commands
```bash
# Test msmtp config
msmtp -C tests/fixtures/email/msmtprc --pretend

# Test offlineimap config
offlineimap -c tests/fixtures/email/offlineimaprc --dry-run

# Check notmuch database
notmuch count '*'
```
