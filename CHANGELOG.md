# Changelog

Every release of LLM Dev Kit, newest first. Versions follow
[Semantic Versioning](https://semver.org): `fix:` commits make a patch
release, `feat:` a minor one, and a breaking change a major one. Entries are
written by [release-please](https://github.com/googleapis/release-please) from
the [Conventional Commits](https://www.conventionalcommits.org) on `main`.

## [1.0.1](https://github.com/sameeralam3127/llm-dev-kit/compare/v1.0.0...v1.0.1) (2026-11-05)


### Bug fixes

* **auth:** prevent open redirect via backslash in callbackUrl (issue [#57](https://github.com/sameeralam3127/llm-dev-kit/issues/57)) ([340ed82](https://github.com/sameeralam3127/llm-dev-kit/commit/340ed82de5f6649d44d60b2e0269595c1ad65ef7))
* keep LiteLLM model map local by default ([220dead](https://github.com/sameeralam3127/llm-dev-kit/commit/220dead49c261068fefdccc802020878f34dfd9b))


### Performance

* **compose:** show the app in 3 s instead of 16 s on startup ([c449954](https://github.com/sameeralam3127/llm-dev-kit/commit/c44995448cd0009dc8b3197810ed1019dc6daf1e))
* **compose:** show the app in 3 s instead of 16 s on startup ([07f91f9](https://github.com/sameeralam3127/llm-dev-kit/commit/07f91f9031c7dd927e1ef377c3ef8d428442a973))


### Documentation

* bring the README and roadmap up to date, with admin console screenshots ([27d78b3](https://github.com/sameeralam3127/llm-dev-kit/commit/27d78b355a7a060cecb1aa1a483486d7f241b54b))
* let the commits pick every version (strict semver) ([6cc8491](https://github.com/sameeralam3127/llm-dev-kit/commit/6cc8491b9daaad72fc53073fe903e71681f025ab))
* let the commits pick every version (strict semver) ([57b4ca7](https://github.com/sameeralam3127/llm-dev-kit/commit/57b4ca7da1eecf94a30b8e9038d6b32087a67793))

## [1.0.0](https://github.com/sameeralam3127/llm-dev-kit/releases/tag/v1.0.0) (2026-10-25)

The first release: chat grounded in your PDFs, accounts, roles, API keys,
single sign-on, the admin console, an OpenAI-compatible `/v1` and an MCP
server. The v3 secure core (`core_api`, `ingest_worker`, `model_gateway`) is in
the repository but not yet started by Compose. See the
[release notes](https://github.com/sameeralam3127/llm-dev-kit/releases/tag/v1.0.0).
