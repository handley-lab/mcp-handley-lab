# Test fixtures

Correct, minimal documentation is best. Omission is preferable to an
unsupported or obsolete claim. Incorrect documentation is worst.

This directory mixes local fixtures with opt-in email integration fixtures.
Tracked files contain no secret values, but the email configurations name the
`handleylab@gmail.com` test account, read credentials from explicit environment
variables, and include historical absolute paths that callers must replace with
their controlled test directories.

Never install these files as user configuration or aim them at personal mail.
Unit tests must isolate filesystem and process boundaries. A Gmail/OAuth
integration test is a separate live test: provide its documented test-account
credentials explicitly and treat the resulting network activity as part of the
claim being measured.
