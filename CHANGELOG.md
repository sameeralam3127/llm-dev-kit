# Changelog

Every release of LLM Dev Kit, newest first. Versions follow
[Semantic Versioning](https://semver.org): `fix:` commits make a patch
release, `feat:` a minor one, and a breaking change a major one. Entries are
written by [release-please](https://github.com/googleapis/release-please) from
the [Conventional Commits](https://www.conventionalcommits.org) on `main`.

## [1.1.0](https://github.com/sameeralam3127/llm-dev-kit/compare/v1.0.0...v1.1.0) (2026-11-20)


### Features

* merge v3 secure core groundwork ([347a39c](https://github.com/sameeralam3127/llm-dev-kit/commit/347a39cd09d3b3cb4559e4c53f8fe0e0b43c4aab))


### Bug fixes

* **auth:** prevent open redirect via backslash in callbackUrl (issue [#57](https://github.com/sameeralam3127/llm-dev-kit/issues/57)) ([340ed82](https://github.com/sameeralam3127/llm-dev-kit/commit/340ed82de5f6649d44d60b2e0269595c1ad65ef7))
* **deps:** raise floors for five Python packages with published advisories ([9fd0451](https://github.com/sameeralam3127/llm-dev-kit/commit/9fd04516f8840d94f71004a60979b8f3af0e99c3))
* **deps:** raise floors for five Python packages with published advisories ([7e45a44](https://github.com/sameeralam3127/llm-dev-kit/commit/7e45a449d5fc0b74d14eed20c22c3cdfe1bca5a2))
* **dev:** default OLLAMA_HOST to host.docker.internal; down removes orphans ([e04b6c0](https://github.com/sameeralam3127/llm-dev-kit/commit/e04b6c013b0fb21e357cdc50e7c9929e6aa91a4c)), closes [#7](https://github.com/sameeralam3127/llm-dev-kit/issues/7)
* **dev:** default OLLAMA_HOST to host.docker.internal; make down removes orphans ([96f3b03](https://github.com/sameeralam3127/llm-dev-kit/commit/96f3b03a43066d10c143b80e182fd0ce4d80651d))
* **gateway:** real status codes for web API routes, and send the client address to web ([79160fa](https://github.com/sameeralam3127/llm-dev-kit/commit/79160fa1db190ead9c47920f32400949449acc84))
* **gateway:** return real 502/503/504 for the web app's API routes ([17d64a6](https://github.com/sameeralam3127/llm-dev-kit/commit/17d64a61173ecc74d1fa34ba6da0e5039d444ca9))
* **gateway:** send the client's address to web and Keycloak ([f6da3e0](https://github.com/sameeralam3127/llm-dev-kit/commit/f6da3e06ef59e089a4df4b53f107c2f61860e155))
* keep LiteLLM model map local by default ([220dead](https://github.com/sameeralam3127/llm-dev-kit/commit/220dead49c261068fefdccc802020878f34dfd9b))
* **rag:** tie the answer cache to the document set and surface retrieval failures ([9572969](https://github.com/sameeralam3127/llm-dev-kit/commit/95729696f0333a7ae2604314d451ce5b3a3be953))
* **rag:** tie the answer cache to the document set and surface retrieval failures ([f03e263](https://github.com/sameeralam3127/llm-dev-kit/commit/f03e263d37ea9fdf99cdd10c39bd8475afa187d7))
* **web:** upgrade vulnerable frontend dependencies ([8fd3d2d](https://github.com/sameeralam3127/llm-dev-kit/commit/8fd3d2d6b1133fd3407df4ba8da780e0d14582e9))


### Performance

* **compose:** show the app in 3 s instead of 16 s on startup ([c449954](https://github.com/sameeralam3127/llm-dev-kit/commit/c44995448cd0009dc8b3197810ed1019dc6daf1e))
* **compose:** show the app in 3 s instead of 16 s on startup ([07f91f9](https://github.com/sameeralam3127/llm-dev-kit/commit/07f91f9031c7dd927e1ef377c3ef8d428442a973))


### Documentation

* bring the README and roadmap up to date, with admin console screenshots ([27d78b3](https://github.com/sameeralam3127/llm-dev-kit/commit/27d78b355a7a060cecb1aa1a483486d7f241b54b))
* clarify architecture and contribution roadmap ([972689f](https://github.com/sameeralam3127/llm-dev-kit/commit/972689fc9d1d282c1b86a535814493b0701352c4))
* let the commits pick every version (strict semver) ([6cc8491](https://github.com/sameeralam3127/llm-dev-kit/commit/6cc8491b9daaad72fc53073fe903e71681f025ab))
* let the commits pick every version (strict semver) ([57b4ca7](https://github.com/sameeralam3127/llm-dev-kit/commit/57b4ca7da1eecf94a30b8e9038d6b32087a67793))
* **readme:** add the v1 and v3 architecture diagrams as images ([fa69628](https://github.com/sameeralam3127/llm-dev-kit/commit/fa69628fe57828e55223291f2443d5fb58e2f8bd))
* **readme:** add the v1 and v3 architecture diagrams as images ([a33c605](https://github.com/sameeralam3127/llm-dev-kit/commit/a33c605edf53ac5f244b33da7f08789fbfc94bb2))
* **readme:** show where state lives and where the architecture is heading ([4548db0](https://github.com/sameeralam3127/llm-dev-kit/commit/4548db048d06fde97f6136f80d3259a2ecebbe3a))
* **readme:** show where state lives and where the architecture is heading ([93a727d](https://github.com/sameeralam3127/llm-dev-kit/commit/93a727d9ab65e9b489d8362edc0cb5580ca15d5f))
* record the review's verified findings in the architecture and roadmap ([338a2d6](https://github.com/sameeralam3127/llm-dev-kit/commit/338a2d6567bf4e048208041cd66dc279398daa4c))
* record the review's verified findings in the architecture and roadmap ([c7e1f5f](https://github.com/sameeralam3127/llm-dev-kit/commit/c7e1f5f0ff039c08eecc2e684cd94aa4b902f3da))
* remove issue references from the README; treat [#35](https://github.com/sameeralam3127/llm-dev-kit/issues/35), [#36](https://github.com/sameeralam3127/llm-dev-kit/issues/36), [#37](https://github.com/sameeralam3127/llm-dev-kit/issues/37) as v1 fixes ([d93f557](https://github.com/sameeralam3127/llm-dev-kit/commit/d93f557aa9a192b57073732c4af8690b210a32b5))
* remove issue references from the README; treat [#35](https://github.com/sameeralam3127/llm-dev-kit/issues/35), [#36](https://github.com/sameeralam3127/llm-dev-kit/issues/36), [#37](https://github.com/sameeralam3127/llm-dev-kit/issues/37) as v1 fixes ([954a405](https://github.com/sameeralam3127/llm-dev-kit/commit/954a405d3fb52ba64bcfcc265a85b00fa0cefec2))
* say the cache and retrieval limit is fixed, not "fixed in this change" ([e526432](https://github.com/sameeralam3127/llm-dev-kit/commit/e5264324afff85d4ec12ffd89dfe6b59df6b8fe3))
* streamline contributor issue map ([991d321](https://github.com/sameeralam3127/llm-dev-kit/commit/991d3213ed4c8fcd8afaf1cf2477a29f1cc8e884))

## [1.0.0](https://github.com/sameeralam3127/llm-dev-kit/releases/tag/v1.0.0) (2026-10-25)

The first release: chat grounded in your PDFs, accounts, roles, API keys,
single sign-on, the admin console, an OpenAI-compatible `/v1` and an MCP
server. The v3 secure core (`core_api`, `ingest_worker`, `model_gateway`) is in
the repository but not yet started by Compose. See the
[release notes](https://github.com/sameeralam3127/llm-dev-kit/releases/tag/v1.0.0).
