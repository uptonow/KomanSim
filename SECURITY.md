# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Do NOT report security vulnerabilities through public GitHub issues.**

Please report via:
- **Email**: wshkye@gmail.com
- **Private Security Advisory**: Create a private security advisory on GitHub (if you have access)

Include: description, steps to reproduce, potential impact, and your contact information.

We will acknowledge within 48 hours and provide an initial assessment within 7 days.

## Security Considerations

This open-source release includes SDK + CLI only (no server/API components). All operations are local to the user's machine.

**Best practices:**
- Keep dependencies updated
- Validate job configs before running
- Secure local registry at `~/.simdata/` with appropriate file permissions
- Be careful when sharing configs with absolute paths or sensitive information

## Security Updates

Security updates are released as patch versions and documented in CHANGELOG.md.
