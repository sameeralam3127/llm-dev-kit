# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report it privately
through GitHub instead:

**[Report a vulnerability](https://github.com/sameeralam3127/llm-dev-kit/security/advisories/new)**
(the repository's **Security** tab → **Report a vulnerability**).

Only the maintainer can see the report. A useful report includes:

- what an attacker can do, and what they need first (an account, a role,
  network access to the stack);
- the steps to reproduce it, ideally against a fresh `docker compose up`;
- the version or commit you tested;
- any fix you would suggest.

## What happens next

This project has one maintainer, so responses are best effort. You can
usually expect:

- an acknowledgement within about a week;
- an assessment of the report, and a plan if it is confirmed;
- a fix in a release, with a GitHub security advisory that credits you
  unless you would rather not be named.

Please give the fix time to ship before you disclose the problem publicly.

## Supported versions

Security fixes land on `main` and ship in the next release. Only the latest
release gets them; there are no backports to older versions.

| Version | Supported |
| --- | --- |
| Latest release | Yes |
| Older releases | No; upgrade to the latest |
| The `v3` branch (in development) | Reports welcome; fixed before it is released |

## Scope

In scope: this repository's code, its Docker Compose stack and its published
images. Out of scope: problems in Ollama, the cloud model providers or other
third-party software, unless the way this project uses them makes the problem
worse. Running the stack with settings the documentation warns against (for
example `ALLOW_LEGACY_ANONYMOUS=true`) is also out of scope.
