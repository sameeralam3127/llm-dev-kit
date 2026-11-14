# Changelog

Every release of LLM Dev Kit, newest first. Versions follow
[Semantic Versioning](https://semver.org): `fix:` commits make a patch
release, `feat:` a minor one, and a breaking change a major one. Entries are
written by [release-please](https://github.com/googleapis/release-please) from
the [Conventional Commits](https://www.conventionalcommits.org) on `main`.

## [1.1.0](https://github.com/sameeralam3127/llm-dev-kit/compare/v1.0.0...v1.1.0) (2026-11-14)


### Features

* merge v3 secure core groundwork ([347a39c](https://github.com/sameeralam3127/llm-dev-kit/commit/347a39cd09d3b3cb4559e4c53f8fe0e0b43c4aab))


### Bug fixes

* **auth:** prevent open redirect via backslash in callbackUrl (issue [#57](https://github.com/sameeralam3127/llm-dev-kit/issues/57)) ([340ed82](https://github.com/sameeralam3127/llm-dev-kit/commit/340ed82de5f6649d44d60b2e0269595c1ad65ef7))
* **dev:** default OLLAMA_HOST to host.docker.internal; down removes orphans ([e04b6c0](https://github.com/sameeralam3127/llm-dev-kit/commit/e04b6c013b0fb21e357cdc50e7c9929e6aa91a4c)), closes [#7](https://github.com/sameeralam3127/llm-dev-kit/issues/7)
* **dev:** default OLLAMA_HOST to host.docker.internal; make down removes orphans ([96f3b03](https://github.com/sameeralam3127/llm-dev-kit/commit/96f3b03a43066d10c143b80e182fd0ce4d80651d))
* keep LiteLLM model map local by default ([220dead](https://github.com/sameeralam3127/llm-dev-kit/commit/220dead49c261068fefdccc802020878f34dfd9b))
* **web:** upgrade vulnerable frontend dependencies ([8fd3d2d](https://github.com/sameeralam3127/llm-dev-kit/commit/8fd3d2d6b1133fd3407df4ba8da780e0d14582e9))


### Performance

* **compose:** show the app in 3 s instead of 16 s on startup ([c449954](https://github.com/sameeralam3127/llm-dev-kit/commit/c44995448cd0009dc8b3197810ed1019dc6daf1e))
* **compose:** show the app in 3 s instead of 16 s on startup ([07f91f9](https://github.com/sameeralam3127/llm-dev-kit/commit/07f91f9031c7dd927e1ef377c3ef8d428442a973))


### Documentation

* bring the README and roadmap up to date, with admin console screenshots ([27d78b3](https://github.com/sameeralam3127/llm-dev-kit/commit/27d78b355a7a060cecb1aa1a483486d7f241b54b))
* clarify architecture and contribution roadmap ([972689f](https://github.com/sameeralam3127/llm-dev-kit/commit/972689fc9d1d282c1b86a535814493b0701352c4))
* let the commits pick every version (strict semver) ([6cc8491](https://github.com/sameeralam3127/llm-dev-kit/commit/6cc8491b9daaad72fc53073fe903e71681f025ab))
* let the commits pick every version (strict semver) ([57b4ca7](https://github.com/sameeralam3127/llm-dev-kit/commit/57b4ca7da1eecf94a30b8e9038d6b32087a67793))
* record the review's verified findings in the architecture and roadmap ([338a2d6](https://github.com/sameeralam3127/llm-dev-kit/commit/338a2d6567bf4e048208041cd66dc279398daa4c))
* record the review's verified findings in the architecture and roadmap ([c7e1f5f](https://github.com/sameeralam3127/llm-dev-kit/commit/c7e1f5f0ff039c08eecc2e684cd94aa4b902f3da))
* remove issue references from the README; treat [#35](https://github.com/sameeralam3127/llm-dev-kit/issues/35), [#36](https://github.com/sameeralam3127/llm-dev-kit/issues/36), [#37](https://github.com/sameeralam3127/llm-dev-kit/issues/37) as v1 fixes ([d93f557](https://github.com/sameeralam3127/llm-dev-kit/commit/d93f557aa9a192b57073732c4af8690b210a32b5))
* remove issue references from the README; treat [#35](https://github.com/sameeralam3127/llm-dev-kit/issues/35), [#36](https://github.com/sameeralam3127/llm-dev-kit/issues/36), [#37](https://github.com/sameeralam3127/llm-dev-kit/issues/37) as v1 fixes ([954a405](https://github.com/sameeralam3127/llm-dev-kit/commit/954a405d3fb52ba64bcfcc265a85b00fa0cefec2))
* streamline contributor issue map ([991d321](https://github.com/sameeralam3127/llm-dev-kit/commit/991d3213ed4c8fcd8afaf1cf2477a29f1cc8e884))

## [1.0.0](https://github.com/sameeralam3127/llm-dev-kit/releases/tag/v1.0.0) (2026-10-25)

The first release: chat grounded in your PDFs, accounts, roles, API keys,
single sign-on, the admin console, an OpenAI-compatible `/v1` and an MCP
server. The v3 secure core (`core_api`, `ingest_worker`, `model_gateway`) is in
the repository but not yet started by Compose. See the
[release notes](https://github.com/sameeralam3127/llm-dev-kit/releases/tag/v1.0.0).
