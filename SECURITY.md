# Security Policy

This repository distributes Codex skills (Markdown instruction files) plus a small set of
helper scripts for linking, validating, and evaluating those skills. It is maintained as a
rolling project on the default branch and does not publish numbered releases.

## Supported Versions

| Scope | Supported |
| --- | --- |
| Latest commit on `main` | :white_check_mark: |
| Numbered releases or older snapshots | :x: |

Security fixes are targeted at the latest commit on `main`. There are no long-term-support
branches; older snapshots do not receive fixes.

---

## Reporting a Vulnerability

Report vulnerabilities privately through GitHub Security Advisories on this repository
(**Security → Report a vulnerability**). Do not open a public issue with details of a
suspected vulnerability.

What to expect:

- You will receive an acknowledgement, normally within a few days.
- If the report is accepted, a fix and a security advisory will be published.
- If the report is declined, the reason will be explained.

---

## Scope

In-scope examples include unsafe path handling in the helper scripts, or repository content
that could allow a malicious repository to escape the project directory, escalate
privileges, or exfiltrate data when the scripts run. The `SKILL.md` files are instructions
consumed by AI agents; treat skill content from untrusted sources as untrusted input
(prompt injection), the same as any other repository content.
