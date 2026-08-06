# Security Policy

## Reporting a vulnerability

Do not open a public issue for suspected credential exposure, unsafe evidence,
remote code execution, or another vulnerability. Report it privately through
[GitHub Security Advisories](https://github.com/QVerisAI/qveris-capability-benchmarks/security/advisories/new).

Include affected versions or commits, reproduction steps, impact, and any proposed
mitigation. Do not include live credentials or unredacted personal data.

## Supported versions

Until the first stable release, security fixes target the default branch only.

## Repository safety boundary

Credentials must be injected at runtime and raw provider artifacts remain private
by default. If sensitive material is committed, rotate or revoke the credential
first, then report the exposure so repository history and published artifacts can
be assessed.
