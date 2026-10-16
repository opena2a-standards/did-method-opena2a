# Conformance

Three conformance suites carry `did:opena2a:` identifiers in byte-stable test fixtures:

- [`atx-conformance`][atx]: Agent Trust eXtension (ATX) credentials
- [`atp-conformance`][atp]: Agent Trust Protocol
- [`aip-conformance`][aip]: Agent Identity Protocol

Each suite ships reference verifiers in Go and Python. Fixture bytes are pinned by each suite's `MANIFEST.sha256`, and both verifiers must reproduce every fixture's pinned expected verdict. Signature coverage differs by suite:

- ATX: both verifiers verify Ed25519 and ML-DSA-65 hybrid signatures.
- ATP: the Go verifier verifies Ed25519 and ML-DSA-65; the Python verifier verifies Ed25519 and records an ML-DSA-65 signature as present without verifying it, leaving full hybrid verification to the Go verifier.
- AIP: both verifiers verify Ed25519 only, and no AIP fixture carries an ML-DSA-65 signature.

The ATX suite additionally pins RFC 8785 (JCS) canonical-bytes agreement across independent Go, Python, and TypeScript canonicalizers (`jcs-vectors/`).

Each suite's fixture count is in [`use-cases.md`](./use-cases.md), and spec Section 8.2 of [`did-method-opena2a.md`](../did-method-opena2a.md#82-conformance-suites) records when the coverage was measured.

[atx]: https://github.com/opena2a-standards/atx-conformance
[atp]: https://github.com/opena2a-standards/atp-conformance
[aip]: https://github.com/opena2a-standards/aip-conformance
