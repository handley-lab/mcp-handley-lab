# Security Policy

## Disclaimer

**⚠️ USE AT YOUR OWN RISK**

This software is provided "as-is" without any warranties or guarantees of security. Users assume full responsibility for:

- **API key security**: This toolkit handles API keys for various services (OpenAI, Gemini, etc.)
- **Data privacy**: Tools may send data to external APIs and services
- **System access**: Some tools execute system commands and file operations
- **Network requests**: Tools make HTTP requests to external services

## Beta Software Notice

This is beta software under active development. Security considerations include:

- **Evolving codebase**: Security practices may not be fully mature
- **External dependencies**: Relies on numerous third-party packages and services
- **Limited security review**: Code has not undergone comprehensive security auditing
- **Experimental features**: Some functionality may have unvetted security implications

## Best Practices for Users

### API Key Management
- Store API keys in environment variables, not in code
- Use separate API keys for testing vs production
- Monitor API usage and costs regularly
- Revoke keys immediately if compromised

### Data Handling
- Be aware that prompts and data may be sent to external AI services
- Don't include sensitive information in prompts or file inputs
- Review tool behavior before using with confidential data
- Understand each tool's data transmission patterns

### System Security
- Run in isolated environments when possible
- Review file permissions and access patterns
- Monitor network traffic if handling sensitive data
- Keep dependencies updated

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT** create a public GitHub issue
2. Email: wh260@cam.ac.uk with subject: "MCP Security Issue"
3. Include:
   - Description of the vulnerability
   - Steps to reproduce (if applicable)
   - Your assessment of impact and severity
   - Suggested remediation (if you have ideas)

We will respond as quickly as possible, but please note this is a research project with limited resources.

## Supported Versions

Only the latest version receives security attention:

| Version | Supported |
|---------|-----------|
| Latest (main branch) | ✅ |
| Previous versions | ❌ |

## No Security Guarantees

This project makes **NO GUARANTEES** about:
- Data confidentiality or integrity
- Protection against malicious inputs
- Secure handling of credentials
- Prevention of data leakage to external services
- Compliance with security frameworks or standards

**Use this software only if you accept these risks.**