# Contributing to LLM Dev Kit

Thank you for being here. LLM Dev Kit is a project for learning how a real AI
system fits together by building one, so contributions from beginners are as
welcome as contributions from experienced engineers. If a step below is
unclear, that is a bug in this guide: say so in an issue.

## Ways to help

- **Fix or build something.** Start with an issue labelled
  [`good first issue`](https://github.com/sameeralam3127/llm-dev-kit/labels/good%20first%20issue)
  (small and self-contained) or
  [`learning opportunity`](https://github.com/sameeralam3127/llm-dev-kit/labels/learning%20opportunity)
  (each one teaches a specific AI concept).
- **Improve tests and documentation.** Both are always useful, and a good way
  to learn how a part of the system works.
- **Report a bug or suggest a feature** with the issue forms.
- **Report a security problem privately**, as [SECURITY.md](SECURITY.md)
  describes. Please never put a vulnerability in a public issue.

## Picking an issue

1. Find an issue that interests you. Each `good first issue` says which files
   to read and how you know you are done.
2. Comment on it to say you would like to work on it, with a sentence or two on
   your approach. The maintainer will assign it to you, so two people do not
   build the same thing.
3. Ask questions on the issue at any point. Questions are part of the work.
4. If you can no longer finish, say so on the issue, so it can go to someone
   else. There is no penalty for that.

## Setting up

You need:

- **Python 3.12** and **Node 22.12 or later**
- **Docker** with Compose, to run the stack and the Postgres-backed tests
- **[Ollama](https://ollama.com)**, only if you want real model answers locally

Then, from the repository root:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
make install          # dev tools, ldk_core and every plugin (editable), service dependencies, the web app
cp web/.env.example web/.env   # then set AUTH_SECRET: openssl rand -base64 32
```

Run `make help` to see every target.

### Running the stack

```bash
make up               # build and start everything, waiting until it is healthy
make smoke            # read-only checks of the running stack
make down             # stop it (data volumes are kept)
```

The stack is at <http://localhost:8080>. On first start the web container
prints a setup code (`docker compose logs web`); sign up with it to become the
admin.

For hot reload of the Python services while you work:

```bash
docker compose -f docker-compose.yml -f compose.dev.yml up --build
```

For the web app on its own, `cd web && npm run dev` serves it at
<http://localhost:3000>.

## Running the checks

`make check` runs everything CI runs before a merge, except the image builds:

| Command | Runs |
| --- | --- |
| `make lint` | ruff (Python) and ESLint (web) |
| `make typecheck` | mypy and tsc |
| `make test` | every Python and web test; Postgres-backed tests need Docker running |
| `make test-python` / `make test-web` | one side only |
| `make check` | all of the above |
| `make e2e` | starts the whole stack, then smoke-tests it |

Run `make check` before you open a pull request. CI runs the same checks, plus
image builds and a full-stack smoke test.

## Commit messages and pull request titles

This project uses [Conventional Commits](https://www.conventionalcommits.org/),
and [release-please](https://github.com/googleapis/release-please) reads them
to choose the next version and write the changelog. Pull requests are squash
merged, so **the pull request title becomes the commit** and must follow the
format:

| Prefix | Use it for | Release |
| --- | --- | --- |
| `fix:` | a bug fix | patch (1.1.x) |
| `feat:` | a new feature | minor (1.x.0) |
| `feat!:`, or a `BREAKING CHANGE:` footer | an incompatible change | major |
| `docs:` | documentation only | none |
| `test:` | tests only | none |
| `refactor:` | a change that is neither a fix nor a feature | none |
| `chore:`, `ci:`, `build:` | tooling, CI, dependencies | none |

A scope is optional and names the area: `fix(rag): …`, `feat(web): …`.
Describe what changed and why in plain words.

## Branches and pull requests

1. Fork the repository and create a branch from `main`, named after the change:
   `fix/chat-title-on-edit`, `feat/text-loader`, `docs/contributing`.
2. Keep each pull request to one change. Small pull requests are reviewed
   faster.
3. Add or update tests for what you change, and update the docs it affects.
4. Open the pull request and fill in the template: what changed, the issue it
   closes (`Closes #123`), and how you tested it.
5. CI must pass. A maintainer reviews, may ask for changes, and squash merges.

Please never commit credentials, API keys or `.env` files. The README does not
reference issue numbers; link to the issue tracker or a label instead.

## Adding a plugin

Model providers, embedders, the vector store, document loaders, chunkers,
authentication and MCP tools are all plugins. Each kind has an interface (a
"port") in [`ldk_core.ports`](../services/core/src/ldk_core/ports) and a
contract test suite in
[`ldk_core.testing.contracts`](../services/core/src/ldk_core/testing/contracts).
The fixed-window chunker is the smallest complete example:
[`services/plugins/chunker_fixed`](../services/plugins/chunker_fixed).

1. **Implement the port.** A chunker has a `name` and a
   `chunk(document) -> list[TextChunk]` method
   ([`ports/chunker.py`](../services/core/src/ldk_core/ports/chunker.py)).
   `FixedWindowChunker` in
   [`ldk_plugin_chunker_fixed/__init__.py`](../services/plugins/chunker_fixed/src/ldk_plugin_chunker_fixed/__init__.py)
   is about 90 lines.
2. **Describe it in a manifest.** A JSON file with its kind, name, version,
   description, permissions and a JSON Schema for its configuration:
   [`manifests/chunker.fixed.json`](../services/plugins/chunker_fixed/src/ldk_plugin_chunker_fixed/manifests/chunker.fixed.json).
3. **Export a `Plugin`.** The manifest plus a factory that builds the
   implementation from validated configuration:

   ```python
   def _factory(config: Mapping[str, Any]) -> FixedWindowChunker:
       return FixedWindowChunker(config.get("size", 500), config.get("overlap", 50))

   plugin = Plugin(load_manifest(__name__, "manifests/chunker.fixed.json"), _factory)
   ```

4. **Register the entry point** in the package's
   [`pyproject.toml`](../services/plugins/chunker_fixed/pyproject.toml), named
   `<kind>.<name>`:

   ```toml
   [project.entry-points."llm_dev_kit.plugins"]
   "chunker.fixed" = "ldk_plugin_chunker_fixed:plugin"
   ```

5. **Pass the contract tests.** Subclass the contract for your kind and give it
   your implementation; the suite checks everything every chunker must do:

   ```python
   class TestFixedWindowChunkerContract(ChunkerContract):
       @pytest.fixture
       def chunker(self) -> FixedWindowChunker:
           return FixedWindowChunker()
   ```

   (from [`tests/plugins/test_document_plugins.py`](../tests/plugins/test_document_plugins.py)).
6. **Install it for development** by adding `-e ./services/plugins/<your_plugin>`
   to [`requirements-dev.txt`](../requirements-dev.txt), then `make install`.
7. **Use it in a service.** Services choose plugins by name in code (for
   example `CHUNKER_PLUGIN = "fixed"` in rag-service's `main.py`), and each
   service's image installs the plugins it uses (see the root `Dockerfile`).

Plugins run in-process with the service's permissions. A manifest declares what
a plugin does, but it is disclosure, not a sandbox, so review a plugin before
you install it.

## Code of conduct

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md). Be kind,
assume good faith, and help each other learn.
