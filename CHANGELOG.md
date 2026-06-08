# Changelog

All notable changes to the `did:opena2a` method specification will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/) for the specification version.

## [Unreleased]

### Added

- README: new "Trust model" section comparing self-certifying, ledger-anchored, and registry-mediated DID methods so implementers can choose deliberately.
- Spec §6.7 Trust-model axis: short cross-reference to the README comparison; classifies `did:opena2a` as registry-mediated alongside §6.6 centralization risk.

## [0.1.0] — 2026-05-28

### Added

- Initial draft specification of the `did:opena2a` DID method.
- ABNF syntax for `did:opena2a:<resource-type>:<resource-id>[#fragment]`.
- Non-normative enumeration of currently-recognized resource types: `registry`, `authority`, `publisher`, `agent`, `mcp_server`, `ai_tool`, `llm`, `skill`.
- Documentation of all four method operations (Create, Read, Update, Deactivate) as backed by the OpenA2A Registry HTTP API.
- Security and privacy considerations, including honest discussion of the registry-mediated trust model and centralization risk.
- Reference implementation links to `opena2a-org/opena2a-registry` and the three conformance suites (ATX, ATP, AIP).
- DID Document examples for each registered resource type.
