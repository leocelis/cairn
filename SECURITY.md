# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest release on `main` | ✓ Security updates |
| Previous releases | No security backports |

---

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.** Disclosing
a vulnerability publicly before a fix is available puts all Cairn users at risk.
Please follow responsible disclosure.

### Preferred: GitHub Security Advisories

Navigate to the [Security tab](https://github.com/leocelis/cairn/security) and
click **"Report a vulnerability."** This creates a private draft advisory visible
only to the maintainer and keeps the report private until a fix is coordinated.

### Alternative: Email

Send details to **[hello@leocelis.com](mailto:hello@leocelis.com)** with the
subject line **"[SECURITY] Cairn vulnerability report"**.

---

## What to Include

1. **Description** — what the vulnerability is and what it allows.
2. **Steps to reproduce** — a minimal reproducible case.
3. **Affected versions** — which version(s) you observed it in.

---

## Scope notes

Cairn's core is a **pure-stdlib, offline, deterministic** library: it makes no
network calls, spawns no subprocess, and imports no database or model SDK on the
default path. That surface deliberately excludes most classic vulnerability
classes. Areas that are in scope and worth scrutiny:

- **Deserialization** — `load_entities()` parses JSON produced by `dump_entities()`;
  report any way a crafted document escapes the value model or causes unsafe behavior.
- **openCypher compilation** — `compile_traversal()` inlines only a validated integer
  `depth`; all user strings are bound as `$params`. Report any injection path.
- **Caller-supplied callables** — embedders, LLM arbiters, and DB drivers enter as
  callables the caller provides; their own security is the caller's responsibility,
  but report any way Cairn mishandles their output.

Third-party research cited in `docs/` is informational and out of scope.
