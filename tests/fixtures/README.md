# Test Email Configuration Files

This directory contains test configuration files for the `handleylab@gmail.com` email account, designed for isolated testing of the email tools.

## Files

### `msmtprc`
MSMTP configuration for sending emails via Gmail SMTP. Based on the user's existing Gmail setup.

**Usage:**
```python
# In email tool tests
send(to="test@example.com", subject="Test", body="Test message", config_file="/path/to/test_configs/msmtprc")
```

### `offlineimaprc` 
OfflineIMAP configuration for syncing emails from Gmail. Uses test mail directory `~/test_mail/HandleyLab`.

**Usage:**
```python
# In email tool tests  
sync(account="HandleyLab", config_file="/path/to/test_configs/offlineimaprc")
```

### `notmuch-config`
Notmuch configuration for email search and tagging. Points to test mail directory.

**Usage:**
```python
# Set NOTMUCH_CONFIG environment variable
search("test query", config_file="/path/to/test_configs/notmuch-config")
```

### `muttrc`
Mutt configuration for interactive email management. Uses test addressbook and directories.

**Usage:**
```python
# In mutt tool tests
compose_email(to="test@example.com", config_file="/path/to/test_configs/muttrc")
```

### `test_addressbook`
Sample mutt addressbook with test contacts for contact management testing.

## Setup for Integration Testing

1. **Authentication**: You'll need to set up authentication for `handleylab@gmail.com`:
   - Gmail app-specific password or OAuth2 tokens
   - Store securely (GPG-encrypted or environment variables)

2. **Directories**: Create test mail directories:
   ```bash
   mkdir -p ~/test_mail/HandleyLab
   mkdir -p ~/.cache/mutt_test
   ```

3. **Tool Usage**: All email and mutt tools accept `config_file` parameters for isolated testing.

## Security Notes

- Test configurations use separate directories to avoid interfering with user's personal email
- Authentication credentials are not included - must be configured separately
- Uses standard Gmail IMAP/SMTP settings compatible with most Gmail accounts
