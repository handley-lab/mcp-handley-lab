A mail client must 
a) send emails (msmtp)
b) receive emails (offlineimap -o1)
c) display emails (mutt)
d) search emails (notmuch)

I want to implement this as an mcp.

## notmuch-mutt Integration

The key bridge between notmuch (search/indexing) and mutt (display/interaction) is `notmuch-mutt`, which:

1. **Creates temporary maildirs** with search results as symlinks to actual messages
2. **Populates `~/.cache/notmuch/mutt/results/`** with matching emails
3. **Allows mutt to open these results** as a regular maildir for full email interaction

### Key Operations:

- **`notmuch-mutt search <terms>`**: Search emails and create results maildir
- **`notmuch-mutt thread < message`**: Reconstruct full thread for a message
- **`notmuch-mutt tag < message`**: Add/remove tags from messages

### Current Mutt Macros:

- **F8**: Interactive search - prompts for search terms, opens results in mutt
- **F9**: Thread reconstruction - shows full conversation thread for current message  
- **F6**: Tag management - removes "inbox" tag from current message

### Workflow:

1. User hits F8 in mutt, enters search terms
2. `notmuch-mutt` searches the notmuch database
3. Creates symlinks in `~/.cache/notmuch/mutt/results/`
4. Mutt switches to this temporary maildir
5. User gets full mutt interface for reading/replying/managing search results

This approach provides the best of both worlds:
- **Fast, powerful search** via notmuch indexing
- **Rich email interaction** via mutt's interface
- **Seamless integration** without leaving mutt

## msmtp (Email Sending)

SMTP client for sending emails through various providers with authentication support.

### Configuration:

Located in `~/.msmtprc` with account-specific settings:

- **Hermes**: Office365 with OAuth2 authentication (`wh260@cam.ac.uk`)
- **PolyChord**: Gmail with GPG-encrypted password (`will.handley@polychord.co.uk`)
- **Gmail**: Gmail with GPG-encrypted password (`williamjameshandley@gmail.com`)
- **BrandRadar**: Custom SMTP server (`w.handley@brandradar.co.uk`)
- **CambridgeMachines**: ProtonMail bridge (`Will.Handley@cambridge-machines.com`)

### Key Features:

- **Multiple account support** with different authentication methods
- **OAuth2 integration** for modern email providers
- **GPG password encryption** for security
- **TLS/SSL support** with certificate validation
- **Account selection** via `-a` flag or automatic from address matching

### Integration with Mutt:

Mutt uses msmtp as its sendmail replacement via account-specific configurations:
```
set sendmail = "msmtp -a Hermes"
```

Account switching is handled by folder hooks that set the appropriate msmtp account based on the current mailbox.

## offlineimap (Email Receiving)

IMAP synchronization tool that downloads emails from remote servers to local Maildir format.

### Key Operations:

- **`offlineimap -o`**: One-time sync (no daemon mode)
- **`offlineimap -a AccountName`**: Sync specific account only
- **`offlineimap -u quiet`**: Quiet mode with minimal output

### Configuration:

Located in `~/.offlineimaprc` with:
- **Account definitions** for each email provider
- **Local Maildir paths** (typically `~/mail/AccountName/`)
- **Remote IMAP settings** with authentication
- **Folder filtering** and mapping rules

### Maildir Structure:

Creates local directory structure like:
```
~/mail/
├── Hermes/
│   ├── INBOX/
│   ├── Sent Items/
│   ├── Archive/
│   └── ...
├── Gmail/
│   ├── INBOX/
│   ├── [Google Mail].Sent Mail/
│   └── ...
```

### Integration:

- **Mutt** reads from these local Maildirs for fast access
- **Notmuch** indexes the downloaded emails for search
- **Periodic sync** keeps local copy current with server

## mutt (Email Display/Interaction)

Terminal-based email client providing rich email interaction capabilities.

### Configuration Files:

- **`~/.muttrc`**: Main configuration with account switching logic
- **`~/.mutt/AccountName`**: Account-specific settings (from, sendmail, folders)
- **`~/.mutt/macros`**: Keyboard shortcuts and automation
- **`~/.mutt/AccountName_signature`**: Account-specific email signatures

### Key Features:

- **Folder hooks**: Automatically switch settings based on current mailbox
- **Account switching**: Seamless switching between email accounts
- **Signature management**: Account-specific signatures with proper formatting
- **Address book**: Built-in contact management with alias expansion
- **Macro system**: Powerful automation via keyboard shortcuts

### Integration Points:

- **msmtp**: Uses via `set sendmail` for outgoing mail
- **Maildir**: Reads local email storage created by offlineimap
- **notmuch-mutt**: F8/F9 macros for search and thread reconstruction
- **External tools**: urlscan, gpg, task integration via macros

### Current Macro Setup:

- **F6**: Remove inbox tag via notmuch
- **F8**: Search emails via notmuch-mutt
- **F9**: Reconstruct thread via notmuch-mutt
- **Folder switching**: `gh`, `gp`, `gg`, etc. for quick mailbox navigation

## notmuch (Email Search/Indexing)

Fast email indexer and search engine that creates a database of email metadata and content.

### Key Commands:

- **`notmuch new`**: Index newly received emails
- **`notmuch search <query>`**: Search emails with powerful query syntax
- **`notmuch show <query>`**: Display email content
- **`notmuch count <query>`**: Count matching emails
- **`notmuch tag <operations> <query>`**: Add/remove tags
- **`notmuch config list`**: Show configuration settings

### Search Syntax:

- **`from:user@example.com`**: Search by sender
- **`subject:"meeting notes"`**: Search by subject
- **`tag:inbox AND tag:unread`**: Boolean operations
- **`date:2024-01-01..2024-12-31`**: Date ranges
- **`attachment:filename`**: Search attachments
- **`id:message-id`**: Find specific message by ID

### Tag System:

- **`inbox`**: New emails (equivalent to INBOX folder)
- **`unread`**: Unread status
- **`sent`**: Sent emails
- **Custom tags**: Can add arbitrary tags for organization

### Integration:

- **Automatic indexing**: Triggered after offlineimap sync
- **Mutt integration**: via notmuch-mutt for search/browse
- **Fast search**: Much faster than IMAP search
- **Thread reconstruction**: Groups related emails together

### Database Location:

Typically `~/.cache/notmuch/` or configured via `~/.notmuch-config`

## Email MCP Tool Summary

The email MCP tool provides comprehensive email workflow management with these functions:

### Sending (msmtp)
- **`send`**: Send emails with msmtp
- **`list_accounts`**: Show available msmtp accounts

### Receiving (offlineimap) 
- **`sync`**: Full email synchronization
- **`sync_preview`**: Preview sync without changes
- **`quick_sync`**: Fast sync without flag updates
- **`sync_folders`**: Sync specific folders only
- **`sync_status`**: Check sync configuration
- **`repo_info`**: Repository information

### Searching (notmuch)
- **`search`**: Search emails with query syntax
- **`show`**: Display email content
- **`count`**: Count matching emails
- **`tag`**: Add/remove email tags
- **`new`**: Index newly received emails
- **`list_tags`**: Show all available tags
- **`config`**: Get notmuch configuration

### Interactive Interface (mutt)
- **`compose_email`**: Compose emails with mutt interface
- **`open_mutt`**: Launch full mutt interface
- **`reply_to_email`**: Reply to emails (with reply-all option)
- **`forward_email`**: Forward emails with optional comments
- **`move_email`**: Move/delete emails between folders
- **`list_folders`**: Show available mailboxes
- **`open_folder`**: Open specific mailbox in mutt
- **`add_contact`**: Add contacts to address book
- **`list_contacts`**: Show address book entries

### System Status
- **`server_info`**: Check all tool availability and versions

## Address Book Management

The mutt tool provides enhanced address book management beyond manual mutt aliases:

### Key Features:

- **Programmatic contact addition**: Use `add_contact()` to automatically add contacts
- **Group/project contacts**: Create aliases for teams (e.g., "gw-team" for GW project members)
- **Contact filtering**: Search contacts with `list_contacts(pattern="gw")`
- **MCP integration**: Enables commands like "email the members of the GW project"

### Contact Management:

```python
# Add individual contact
add_contact(
    alias="john_doe",
    email="john.doe@example.com",
    name="John Doe"
)

# Add project team
add_contact(
    alias="gw_team", 
    email="alice@cam.ac.uk,bob@cam.ac.uk,carol@cam.ac.uk",
    name="GW Project Team"
)

# List all contacts
list_contacts()

# Find specific contacts
list_contacts(pattern="gw")
```

### Integration with Email Workflows:

- **Smart addressing**: Use project aliases in `compose_email(to="gw_team")`
- **Group communications**: Reply-all to project discussions
- **Contact discovery**: Find relevant contacts for specific projects
- **Automated population**: Extract contacts from email headers and add to address book

### File Location:

Contacts are stored in `~/.mutt/aliases` and automatically available in mutt's tab completion and addressing system.

### Testing:

Address book functions are fully tested using proper unit tests with mocking (following codebase patterns):
- All file operations mocked to prevent touching real address book
- Comprehensive test coverage for contact management workflows
- Error handling and validation testing
- Project-specific contact scenarios (e.g., GW team management)

Run tests: `python -m pytest tests/test_mutt.py -v`
