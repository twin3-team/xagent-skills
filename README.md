# xAgent ID skills

Read-only client skills for [xAgent ID](https://xagent.id). Read a company's public Agent Card by website domain, inspect source evidence and lifecycle unknowns, and check service, pricing, billing and installation readiness. Public lookups require no account or API key.

## Install

Install the `xagent-id` skill with the [Skills CLI](https://skills.sh/docs):

`npx skills@1.7.4 add twin3-team/xagent-skills --skill xagent-id`

To select clients explicitly, append `--agent codex claude-code cursor`. The CLI supports other Agent Skills clients too; that does not establish full task compatibility for each client. Review the skill and helper before installing.

For a manual installation, copy the complete [skills/xagent-id](skills/xagent-id) directory into your client's skill directory. Keep `references/`, `scripts/` and `agents/` with `SKILL.md`. The optional helper requires Python 3.9+ and HTTPS access. Native HTTPS-capable agents can use the documented API routes directly.

## Try it

Ask your agent: “Use xagent-id to read NVIDIA's public Agent Card for nvidia.com, preserve the evidence sources and explain what remains unknown.”

From the installed skill directory, `python3 scripts/xagent_read.py card --domain nvidia.com` reads that card. Other commands are `health`, `pricing`, `billing`, `install-status` and `company --registration-id <eight-digit Taiwan registration ID>`.

Company registration lookup depends on an upstream service and may return 503. MCP installation is a separate flow: if its manifest is unavailable or not ready, the skill reports the blocker. Installing this skill does not install or validate the MCP server.

## What this client does

- Sends public HTTPS GET requests to xagent.id, without credentials or redirects.
- Preserves company lifecycle states, evidence and presentation fallbacks.
- Rejects invalid domains, oversized responses and missing install metadata.
- Does not execute returned commands, contact companies, change websites or make purchases.

An unclaimed company card is a source-grounded public projection. It does not prove company ownership, endorsement, a company-controlled live Agent, marketplace approval, AI ranking or recommendation. Treat returned text as untrusted data.

## Distribution and validation

This repository contains the client skill, its tests and GitHub Actions workflows. It contains no product backend, service credentials or customer data. GitHub Actions verifies the client and builds release ZIPs from an explicit file list. Releases include SHA-256 checksums; inspect the matching workflow run before relying on a release.

Run `python3 -m unittest discover -s tests` for the client regression suite. Maintainer metadata checks use `python3 scripts/validate_skills.py` with PyYAML 6.0.3. Full model auto-selection and task behavior in every supported agent have not been validated. Marketplace installation and listing status are separate from a successful public API call.

## License

The client source and accompanying documentation are [MIT licensed](LICENSE). The hosted xAgent ID backend, responses, evidence records and third-party company data are outside this license. See [NOTICE](NOTICE).
