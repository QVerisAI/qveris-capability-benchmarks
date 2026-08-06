# Security Policy

## Reporting a vulnerability

Do not open a public issue for suspected credential exposure, unsafe evidence,
remote code execution, or another vulnerability. Report it privately through
[GitHub Security Advisories](https://github.com/QVerisAI/qveris-capability-benchmarks/security/advisories/new).

Include affected versions or commits, reproduction steps, impact, and any proposed
mitigation. Do not include live credentials or unredacted personal data.

## Reporting a conduct incident

Use the same private GitHub Security Advisory form and start the title with
`Conduct Report:`. Include the relevant project space, approximate time, behavior,
and any supporting material that can be shared safely. Maintainers will restrict
the report to people needed for impartial review, acknowledge it privately, and
keep the reporter's identity confidential unless disclosure is legally required.

Reports involving a maintainer will be handled by another uninvolved QVeris
maintainer. Retaliation against reporters or participants in an investigation is a
separate violation of the Code of Conduct.

## Supported versions

Until the first stable release, security fixes target the default branch only.

## Repository safety boundary

Credentials must be injected at runtime and raw provider artifacts remain private
by default. If sensitive material is committed, rotate or revoke the credential
first, then report the exposure so repository history and published artifacts can
be assessed.
