# Contributing

Thanks for helping with LLM Dev Kit. This guide covers how to set up a
development environment, which checks to run, and how to prepare a pull request.
For what the project does and how it is laid out, see the [README](README.md)
and [ARCHITECTURE.md](ARCHITECTURE.md).

## Set up

You need Python 3.12 and Node 22.12 or newer. Docker is needed for the
Postgres-backed tests and for running the full stack.

**Python services**

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt       # ldk_core and every plugin, editable
```

**Web app**

```bash
cd web && npm install
cp .env.example .env                      # then set AUTH_SECRET
npm run dev                               # http://localhost:3000
```

**Hot reload in Docker:**
`docker compose -f docker-compose.yml -f compose.dev.yml up --build`.

## Run the checks

CI runs the same checks as these commands. Run them before you open a pull
request.

```bash
ruff check services tests && ruff format --check services tests
mypy
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest

cd web
npm run typecheck && npm run lint && npm test && npm run build
```

`make check` runs lint, type checks and every Python and web test in one step
(from an activated virtualenv). `make test-python` and `make test-web` run one
side only. `make e2e` and `make smoke` exercise a running Compose stack; see the
[Testing section of the README](README.md#testing).

CI has four jobs, defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

| Job | Checks |
| --- | --- |
| `python` | ruff, mypy, pytest against a real Chroma and a real Postgres with pgvector |
| `web` | typecheck, lint, Vitest, production build |
| `images` | Builds every image and proves each one starts |
| `stack` | Starts the full Compose stack and runs `scripts/smoke.sh` against it |

## Pull requests

- **One change per pull request.** Keep unrelated fixes and refactors for their
  own pull requests.
- **Use a Conventional Commit title**, for example `fix: ...`, `feat: ...` or
  `docs: ...`. [release-please](https://github.com/googleapis/release-please)
  builds versions and the [changelog](CHANGELOG.md) from these. `fix:` makes a
  patch release, `feat:` a minor one, and `feat!:` or a `BREAKING CHANGE:`
  footer a major one. `docs:`, `test:`, `ci:` and `chore:` make no release. See
  [Releases and versions](README.md#releases-and-versions).
- **Fill in the pull request template:** what changed and why, how you tested
  it, and what you did not verify.
- **Add or update tests** for behaviour you change.

## Architecture rule: use the plugin registry

Services get implementations (models, vector stores, loaders and so on) only
from the plugin registry in `ldk_core`. A service must not import an
`ldk_plugin_*` package directly. `tests/test_architecture.py` fails if one does,
so a new implementation is added as a plugin under `services/plugins/` and
looked up through the registry.

## Reporting bugs and requesting features

Use the issue templates. For a bug, include the steps to reproduce, what you
expected, what happened, the output of `docker compose ps`, and the logs. Every
response carries an `X-Request-ID` header; include the request id from the logs
so the call can be found.
