# Changelog

Every release of LLM Dev Kit, newest first. Versions follow
[Semantic Versioning](https://semver.org): `fix:` commits make a patch
release, `feat:` a minor one, and a breaking change a major one. Entries are
written by [release-please](https://github.com/googleapis/release-please) from
the [Conventional Commits](https://www.conventionalcommits.org) on `main`.

## [1.1.0](https://github.com/sameeralam3127/llm-dev-kit/compare/v1.0.0...v1.1.0) (2026-11-22)


### Features

* **auth:** make the first admin need a one-time setup code ([#106](https://github.com/sameeralam3127/llm-dev-kit/issues/106)) ([1fcade8](https://github.com/sameeralam3127/llm-dev-kit/commit/1fcade842fc83d83d86cce577bf7b50916476205))
* merge v3 secure core groundwork ([347a39c](https://github.com/sameeralam3127/llm-dev-kit/commit/347a39cd09d3b3cb4559e4c53f8fe0e0b43c4aab))


### Bug fixes

* **auth:** ALLOW_REGISTRATION=false also stops GitHub and SSO sign-ups ([2d8ec50](https://github.com/sameeralam3127/llm-dev-kit/commit/2d8ec501396d64b152a02b70417082a7a9649aab))
* **auth:** ALLOW_REGISTRATION=false also stops GitHub and SSO sign-ups ([6df70b1](https://github.com/sameeralam3127/llm-dev-kit/commit/6df70b11a093096e54ba7cffe836c7beaa1fb87b))
* **auth:** prevent open redirect via backslash in callbackUrl (issue [#57](https://github.com/sameeralam3127/llm-dev-kit/issues/57)) ([340ed82](https://github.com/sameeralam3127/llm-dev-kit/commit/340ed82de5f6649d44d60b2e0269595c1ad65ef7))
* **auth:** rate limit password sign-in before bcrypt runs ([0fc1b13](https://github.com/sameeralam3127/llm-dev-kit/commit/0fc1b13b8132ad6d0c802b36e477c4b009a03d5f))
* **auth:** rate limit password sign-in before bcrypt runs ([0bff687](https://github.com/sameeralam3127/llm-dev-kit/commit/0bff687cb730f3ac6eb038486fc874d90e5df689))
* **auth:** refuse ALLOW_LEGACY_ANONYMOUS unless the gateway is loopback ([#107](https://github.com/sameeralam3127/llm-dev-kit/issues/107)) ([cc9a7d6](https://github.com/sameeralam3127/llm-dev-kit/commit/cc9a7d6f552576e7bc43f50c84581ce5a3629ba6))
* **chat:** stop simultaneous sends to one chat failing or sharing positions ([#115](https://github.com/sameeralam3127/llm-dev-kit/issues/115)) ([deb27cd](https://github.com/sameeralam3127/llm-dev-kit/commit/deb27cde4921312704ebdbc0a0828de128bbe3ca))
* **deps:** bump the web-minor-and-patch group in /web with 30 updates ([#118](https://github.com/sameeralam3127/llm-dev-kit/issues/118)) ([c1be56d](https://github.com/sameeralam3127/llm-dev-kit/commit/c1be56d0ce08fb0a0d1c5a1150da2598e79c669b))
* **deps:** bump the web-minor-and-patch group in /web with 9 updates ([#148](https://github.com/sameeralam3127/llm-dev-kit/issues/148)) ([d69f69b](https://github.com/sameeralam3127/llm-dev-kit/commit/d69f69b197c661542a8eadaad2b38b36eaa0ff85))
* **deps:** raise floors for five Python packages with published advisories ([9fd0451](https://github.com/sameeralam3127/llm-dev-kit/commit/9fd04516f8840d94f71004a60979b8f3af0e99c3))
* **deps:** raise floors for five Python packages with published advisories ([7e45a44](https://github.com/sameeralam3127/llm-dev-kit/commit/7e45a449d5fc0b74d14eed20c22c3cdfe1bca5a2))
* **deps:** update litellm requirement from &lt;1.107.0,&gt;=1.106.3 to &gt;=1.106.3,&lt;1.111.0 in /services/plugins/litellm ([dbe718b](https://github.com/sameeralam3127/llm-dev-kit/commit/dbe718b877dd5aa7ba96b6c18af32be4b50fc3d7))
* **deps:** update litellm requirement in /services/plugins/litellm ([d745c24](https://github.com/sameeralam3127/llm-dev-kit/commit/d745c24d62405daffe14df74770a11043713d5c3))
* **dev:** default OLLAMA_HOST to host.docker.internal; down removes orphans ([e04b6c0](https://github.com/sameeralam3127/llm-dev-kit/commit/e04b6c013b0fb21e357cdc50e7c9929e6aa91a4c)), closes [#7](https://github.com/sameeralam3127/llm-dev-kit/issues/7)
* **dev:** default OLLAMA_HOST to host.docker.internal; make down removes orphans ([96f3b03](https://github.com/sameeralam3127/llm-dev-kit/commit/96f3b03a43066d10c143b80e182fd0ce4d80651d))
* **gateway:** real status codes for web API routes, and send the client address to web ([79160fa](https://github.com/sameeralam3127/llm-dev-kit/commit/79160fa1db190ead9c47920f32400949449acc84))
* **gateway:** return real 502/503/504 for the web app's API routes ([17d64a6](https://github.com/sameeralam3127/llm-dev-kit/commit/17d64a61173ecc74d1fa34ba6da0e5039d444ca9))
* **gateway:** send the client's address to web and Keycloak ([f6da3e0](https://github.com/sameeralam3127/llm-dev-kit/commit/f6da3e06ef59e089a4df4b53f107c2f61860e155))
* **identity:** rate limit only invalid keys at the token exchange ([#108](https://github.com/sameeralam3127/llm-dev-kit/issues/108)) ([71d7393](https://github.com/sameeralam3127/llm-dev-kit/commit/71d739319a0aff8464c2d1da799d54c49c694773))
* **ingest:** limit PDF pages, text and parse time, and cap chunks ([#112](https://github.com/sameeralam3127/llm-dev-kit/issues/112)) ([7c32828](https://github.com/sameeralam3127/llm-dev-kit/commit/7c32828ab292b960e6a7ba8755e2563bbfb76ea1))
* keep LiteLLM model map local by default ([220dead](https://github.com/sameeralam3127/llm-dev-kit/commit/220dead49c261068fefdccc802020878f34dfd9b))
* **llm:** accept only bounded temperature and max_tokens on /generate ([#109](https://github.com/sameeralam3127/llm-dev-kit/issues/109)) ([8b3fd32](https://github.com/sameeralam3127/llm-dev-kit/commit/8b3fd32a3f421a1205573fe678570a1a4a1dc84e))
* **rag:** report failed /v1 streams as errors, never as finished answers ([#113](https://github.com/sameeralam3127/llm-dev-kit/issues/113)) ([5044d80](https://github.com/sameeralam3127/llm-dev-kit/commit/5044d80aafc95851a1b689e1959acaf9cb04cf07))
* **rag:** tie the answer cache to the document set and surface retrieval failures ([9572969](https://github.com/sameeralam3127/llm-dev-kit/commit/95729696f0333a7ae2604314d451ce5b3a3be953))
* **rag:** tie the answer cache to the document set and surface retrieval failures ([f03e263](https://github.com/sameeralam3127/llm-dev-kit/commit/f03e263d37ea9fdf99cdd10c39bd8475afa187d7))
* **security:** resolve actionable CodeQL alerts ([#154](https://github.com/sameeralam3127/llm-dev-kit/issues/154)) ([7c94e89](https://github.com/sameeralam3127/llm-dev-kit/commit/7c94e892d3c97ddc1554c45828c79a92693cff80))
* **web:** add a nonce-based CSP and cross-origin isolation headers ([#110](https://github.com/sameeralam3127/llm-dev-kit/issues/110)) ([18b48a3](https://github.com/sameeralam3127/llm-dev-kit/commit/18b48a31db6a80c4776ae9f54610c041ea32d729))
* **web:** upgrade vulnerable frontend dependencies ([8fd3d2d](https://github.com/sameeralam3127/llm-dev-kit/commit/8fd3d2d6b1133fd3407df4ba8da780e0d14582e9))


### Performance

* **compose:** show the app in 3 s instead of 16 s on startup ([c449954](https://github.com/sameeralam3127/llm-dev-kit/commit/c44995448cd0009dc8b3197810ed1019dc6daf1e))
* **compose:** show the app in 3 s instead of 16 s on startup ([07f91f9](https://github.com/sameeralam3127/llm-dev-kit/commit/07f91f9031c7dd927e1ef377c3ef8d428442a973))


### Documentation

* add a contributing guide for newcomers ([272fd05](https://github.com/sameeralam3127/llm-dev-kit/commit/272fd057ccef76baaca829c60c3c8ae7ca5c3c82))
* add a security policy and code of conduct ([#111](https://github.com/sameeralam3127/llm-dev-kit/issues/111)) ([c9d882d](https://github.com/sameeralam3127/llm-dev-kit/commit/c9d882dabe05e20e8ff9ac159e99c5e8d9482fb1))
* bring the README and roadmap up to date, with admin console screenshots ([27d78b3](https://github.com/sameeralam3127/llm-dev-kit/commit/27d78b355a7a060cecb1aa1a483486d7f241b54b))
* clarify architecture and contribution roadmap ([972689f](https://github.com/sameeralam3127/llm-dev-kit/commit/972689fc9d1d282c1b86a535814493b0701352c4))
* let the commits pick every version (strict semver) ([6cc8491](https://github.com/sameeralam3127/llm-dev-kit/commit/6cc8491b9daaad72fc53073fe903e71681f025ab))
* let the commits pick every version (strict semver) ([57b4ca7](https://github.com/sameeralam3127/llm-dev-kit/commit/57b4ca7da1eecf94a30b8e9038d6b32087a67793))
* link the reranking row to its issue ([4019e65](https://github.com/sameeralam3127/llm-dev-kit/commit/4019e653d4eae050951431441efc6a76ebb01713))
* **readme:** add the v1 and v3 architecture diagrams as images ([fa69628](https://github.com/sameeralam3127/llm-dev-kit/commit/fa69628fe57828e55223291f2443d5fb58e2f8bd))
* **readme:** add the v1 and v3 architecture diagrams as images ([a33c605](https://github.com/sameeralam3127/llm-dev-kit/commit/a33c605edf53ac5f244b33da7f08789fbfc94bb2))
* **readme:** show where state lives and where the architecture is heading ([4548db0](https://github.com/sameeralam3127/llm-dev-kit/commit/4548db048d06fde97f6136f80d3259a2ecebbe3a))
* **readme:** show where state lives and where the architecture is heading ([93a727d](https://github.com/sameeralam3127/llm-dev-kit/commit/93a727d9ab65e9b489d8362edc0cb5580ca15d5f))
* record the review's verified findings in the architecture and roadmap ([338a2d6](https://github.com/sameeralam3127/llm-dev-kit/commit/338a2d6567bf4e048208041cd66dc279398daa4c))
* record the review's verified findings in the architecture and roadmap ([c7e1f5f](https://github.com/sameeralam3127/llm-dev-kit/commit/c7e1f5f0ff039c08eecc2e684cd94aa4b902f3da))
* remove issue references from the README; treat [#35](https://github.com/sameeralam3127/llm-dev-kit/issues/35), [#36](https://github.com/sameeralam3127/llm-dev-kit/issues/36), [#37](https://github.com/sameeralam3127/llm-dev-kit/issues/37) as v1 fixes ([d93f557](https://github.com/sameeralam3127/llm-dev-kit/commit/d93f557aa9a192b57073732c4af8690b210a32b5))
* remove issue references from the README; treat [#35](https://github.com/sameeralam3127/llm-dev-kit/issues/35), [#36](https://github.com/sameeralam3127/llm-dev-kit/issues/36), [#37](https://github.com/sameeralam3127/llm-dev-kit/issues/37) as v1 fixes ([954a405](https://github.com/sameeralam3127/llm-dev-kit/commit/954a405d3fb52ba64bcfcc265a85b00fa0cefec2))
* say the cache and retrieval limit is fixed, not "fixed in this change" ([e526432](https://github.com/sameeralam3127/llm-dev-kit/commit/e5264324afff85d4ec12ffd89dfe6b59df6b8fe3))
* sharpen the README and make the repo inviting for contributors ([2c2f6ec](https://github.com/sameeralam3127/llm-dev-kit/commit/2c2f6ecbee4f7cd08f1d46776cb6a18dde656ba5))
* sharpen the README's pitch and invite contributors ([5f800c0](https://github.com/sameeralam3127/llm-dev-kit/commit/5f800c0c990b835be412189161c7cd4df3619fcc))
* streamline contributor issue map ([991d321](https://github.com/sameeralam3127/llm-dev-kit/commit/991d3213ed4c8fcd8afaf1cf2477a29f1cc8e884))
* tidy the repository root and bring the README up to date for 1.1.0 ([#153](https://github.com/sameeralam3127/llm-dev-kit/issues/153)) ([3753e27](https://github.com/sameeralam3127/llm-dev-kit/commit/3753e278174df1a0e0b8b0535b3d2c2b4394b712))

## [1.0.0](https://github.com/sameeralam3127/llm-dev-kit/releases/tag/v1.0.0) (2026-10-25)

The first release: chat grounded in your PDFs, accounts, roles, API keys,
single sign-on, the admin console, an OpenAI-compatible `/v1` and an MCP
server. The v3 secure core (`core_api`, `ingest_worker`, `model_gateway`) is in
the repository but not yet started by Compose. See the
[release notes](https://github.com/sameeralam3127/llm-dev-kit/releases/tag/v1.0.0).
