# Changelog

All notable changes to the `did:opena2a` method specification will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/) for the specification version.

## [Unreleased]

### Changed

- §3.2 upgraded from "currently registered resource types" (labelled
  non-normative) to the **shared resource-type registry** for the OpenA2A
  spec family: ATX §2/§14, ATP-SPEC §3.1, and AIP examples defer here;
  additions by PR against this repository, mirrored into consumers. The
  registration-governs-issuance / resolvers-must-not-reject rule is retained.
- `a2a_agent` moved from an in-table synonym note to an explicit
  **Deprecated aliases** rule: resolvers SHOULD treat it as `agent`; issuers
  MUST NOT mint new identifiers with it. Companion cleanups: atx-spec#7
  (prefix set in §2/§14, `registry` added there) and agent-trust-protocol#6
  (example tokens).

### Added

- README: new "Trust model" section comparing self-certifying, ledger-anchored, and registry-mediated DID methods so implementers can choose deliberately.
- Spec §6.7 Trust-model axis: short cross-reference to the README comparison; classifies `did:opena2a` as registry-mediated alongside §6.6 centralization risk.

### Fixed

- README and spec §8.2 overstated the reference-verifier coverage ("Go, Rust, TypeScript, and Python ... byte-identical across all four"). Corrected to the actual set: Go (full hybrid Ed25519 + ML-DSA-65) and Python (Ed25519, ML-DSA-65 delegated to Go), with fixture bytes pinned by each suite's `MANIFEST.sha256` and JCS canonical-bytes agreement pinned across Go/Python/TypeScript in `atx-conformance/jcs-vectors/`.
- README and spec §8.2 mis-expanded ATX as "Agent Trust Cross-Verification"; the correct expansion is "Agent Trust eXtension".

## [0.1.0] — 2026-05-28

### Added

- Initial draft specification of the `did:opena2a` DID method.
- ABNF syntax for `did:opena2a:<resource-type>:<resource-id>[#fragment]`.
- Non-normative enumeration of currently-recognized resource types: `registry`, `authority`, `publisher`, `agent`, `mcp_server`, `ai_tool`, `llm`, `skill`.
- Documentation of all four method operations (Create, Read, Update, Deactivate) as backed by the OpenA2A Registry HTTP API.
- Security and privacy considerations, including honest discussion of the registry-mediated trust model and centralization risk.
- Reference implementation links to `opena2a-org/opena2a-registry` and the three conformance suites (ATX, ATP, AIP).
- DID Document examples for each registered resource type.
