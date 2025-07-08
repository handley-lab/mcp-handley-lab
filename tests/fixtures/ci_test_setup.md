# CI Test Setup Options

## Option 1: Use Outlook.com (Recommended)

1. Create free Outlook.com account for testing
2. Enable 2FA and generate app password
3. Update test configs:

```ini
# In offlineimaprc
[Repository HandleyLab-Remote]
type = IMAP
remotehost = outlook.office365.com
remoteuser = handleylab@outlook.com
remotepasseval = get_test_password()
ssl = yes
sslcacertfile = /etc/ssl/certs/ca-certificates.crt
```

## Option 2: Use Test IMAP Server

For pure CI testing without real email:

```yaml
# In GitHub Actions
- name: Start test IMAP server
  run: |
    python test_configs/mock_imap_server.py &
    sleep 2

- name: Run tests
  env:
    GMAIL_TEST_PASSWORD: dummy
  run: pytest tests/integration/test_email_integration.py
```

## Option 3: VCR Cassettes Only

Record real interactions once locally, then replay in CI:

```python
# Record cassettes locally with real account
# Then commit cassettes for CI replay
@vcr.use_cassette('test_email_sync.yaml')
def test_sync():
    sync(config_file='test_configs/offlineimaprc')
```

## Environment Variables for CI

```yaml
# .github/workflows/test.yml
env:
  GMAIL_TEST_PASSWORD: ${{ secrets.EMAIL_TEST_PASSWORD }}
  NOTMUCH_CONFIG: ${{ github.workspace }}/test_configs/notmuch-config
```
