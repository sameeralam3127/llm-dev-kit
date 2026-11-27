# Security remediation roadmap

Track implementation in [security issue #168](https://github.com/sameeralam3127/llm-dev-kit/issues/168). Finding IDs refer to the audit inventory.

| Phase | Findings | Work and acceptance criteria |
| --- | --- | --- |
| 0 · Administrator setup | SEC-001 | Issue short-lived, email-bound setup codes through the interactive operator command. Verify upgrades reject earlier codes, failed attempts leave a valid code usable, and only one registration can spend it. Check that no credential reaches application, container, or CI logs. |
| 1 · Error handling and data boundaries | SEC-002 through SEC-005 | Map internal failures to safe messages before logging, persistence, and serialization. Authorize retrieval and cache hits against the current principal and provider policy. Enforce an explicit outbound inference policy for the legacy stack. Verify with synthetic credentials, separate principals, and mock model endpoints. |
| 2 · Hosted and tenant controls | SEC-006 through SEC-008, SEC-013 through SEC-017, SEC-020 | Add service-level quotas and closed enrollment, document and test TLS and trusted proxy headers, enforce provenance ownership, minimize OAuth token storage, scope MCP credentials, verify erasure, remove anonymous administration, and split audit writer and migration roles. Verify upgrades and concurrent requests using synthetic data. |
| 3 · Supply chain | SEC-009 through SEC-012, SEC-019 | Pin runtime images and segment service networks. Lock dependency graphs, constrain build hooks and contexts, and patch affected versions. Verify exact release manifests, image digests, provenance, and compatible builds. |
| 4 · Model output and audit closure | SEC-018 | Treat retrieved text as untrusted input and verify rendering restrictions. Finish pending review and runtime checks from the audit inventory. |

## First implementation pass

- **SEC-001.** Added operator-issued setup codes and kept the existing database upgrade path. Verified setup, rotation, single use, and absence of synthetic codes in application output.
- **SEC-002.** Added safe error handling across Python and web boundaries. Verified provider failure and interrupted streams with a local mock. Production log retention and historical copies require separate operational checks.
- **SEC-019.** Excluded dotenv variants from both Docker build contexts. Verified with synthetic files and network-disabled BuildKit builds.

## Next phases

- Deliver cache isolation and outbound inference policy together in Phase 1 so a cached answer cannot bypass admission.
- Set closed enrollment in Phase 2 after the first administrator can be provisioned with enrollment disabled.
- Continue independent Phase 3 supply-chain changes in parallel with application work.
