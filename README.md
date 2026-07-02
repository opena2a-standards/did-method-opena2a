> **OpenA2A specs** · **did:opena2a** · [AIP](https://github.com/opena2a-standards/agent-identity-protocol) · [ATX](https://github.com/opena2a-standards/atx-spec) · [ATP](https://github.com/opena2a-standards/agent-trust-protocol) · [AAP](https://github.com/opena2a-standards/agent-authorization-protocol) · [AIM](https://github.com/opena2a-org/agent-identity-management) · [all specs ↗](https://specs.opena2a.org)

# did-method-opena2a

The `did:opena2a` Decentralized Identifier method specification.

**W3C registration:** a provisional entry is filed for review at [w3c/did-extensions#717](https://github.com/w3c/did-extensions/pull/717).

A `did:opena2a` DID names a resource registered in an [OpenA2A Registry][registry] — an agent, an MCP server, an authority, a publisher, an AI tool, an LLM, a skill, or the registry itself. Resolution returns a [W3C DID Document][did-core] whose verification key is the Registry's Ed25519 signing key and whose service endpoints expose trust lookup, signed trust proofs, and trust badges.

```
did:opena2a:registry:opena2a.org
did:opena2a:authority:opena2a.org
did:opena2a:agent:agent_conformance_test_001
did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem
```

## Specification

The full specification is in [`did-method-opena2a.md`](./did-method-opena2a.md).

## Trust model

`did:opena2a` is a **registry-mediated** DID method. Resolution is performed by HTTP against an OpenA2A Registry; the verification key for every resolved DID is the Registry's Ed25519 signing key; the trust a verifier places in a `did:opena2a` DID is exactly the trust the verifier places in the Registry resolver it has configured.

This is one design point on a broader axis that implementers comparing agent-identity options should be aware of:

| Anchor                                 | Resolution surface                          | Trust assumption                                              | Key rotation                                                |
| -------------------------------------- | ------------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------- |
| Self-certifying (e.g. `did:key`, `did:peer`) | None; the identifier IS the key             | The key holder                                                | Identifier changes when key changes                          |
| Ledger-anchored (e.g. distributed ledgers, append-only logs) | Public ledger or log read                    | The ledger's consensus and any verifier-side log auditor       | Per-method (revocation registries, rotation operations)      |
| **Registry-mediated (`did:opena2a`)**  | **HTTP `GET` against an OpenA2A Registry**  | **The configured Registry resolver (single or federated)**    | **Registry-side key rotation, with a 7-day overlap window**  |

Each anchor solves a different operational problem. Self-certifying methods give you portable identifiers with no resolution dependency. Ledger-anchored methods give you a write surface that is independent of any one operator. Registry-mediated methods give you a resolution surface that returns more than a key (trust score, signed proofs, scan history, badge endpoints) at the cost of trusting a specific operator.

The choice is deliberate. `did:opena2a` exists because the OpenA2A Registry was already the canonical place where agent reputation, attestation, and supply-chain context lived, and a DID method gave verifiers a single, byte-stable way to ask the Registry "what do you know about this resource?" If you do not need the Registry's resolution payload, you do not need this method.

For the security-considerations view of the same axis (centralization risk, key rotation, transport authentication), see §6.6 and §6.7 of [`did-method-opena2a.md`](./did-method-opena2a.md).

## Status

- **Version:** 0.1 (draft)
- **Status:** Provisional — pending W3C DID Method Registry review
- **License:** Apache License, Version 2.0 (see [`LICENSE`](./LICENSE))

This specification is being submitted to the [W3C DID Method Registry][did-spec-registries] for inclusion in the public method index.

## Resolution

A `did:opena2a` DID is resolved by HTTP `GET` against an OpenA2A Registry:

```
curl https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org
```

The Registry replies with a DID Document in `application/did+ld+json` and a 5-minute cache header.

## Examples

See [`examples/`](./examples/) for byte-stable DID Documents covering each registered resource type. These examples are exercised by the three OpenA2A conformance suites (ATX, ATP, AIP).

## Conformance

Three independent conformance suites publish byte-stable test fixtures for `did:opena2a:` identifiers:

- [`atx-conformance`][atx] — Agent Trust eXtension (ATX) credentials
- [`atp-conformance`][atp] — Agent Trust Protocol
- [`aip-conformance`][aip] — Agent Identity Protocol

Each suite ships reference verifiers in Go (full hybrid Ed25519 + ML-DSA-65) and Python (Ed25519; ML-DSA-65 signatures are presence-checked, with full verification delegated to the Go verifier). Fixture bytes are pinned by each suite's `MANIFEST.sha256`, and both verifiers must reproduce every fixture's pinned expected verdict. The ATX suite additionally pins RFC 8785 (JCS) canonical-bytes agreement across independent Go, Python, and TypeScript canonicalizers (`jcs-vectors/`).

## Contributing

Editorial corrections, clarifications, and link fixes are welcome via pull request. Substantive changes (changes to the ABNF, the operation surface, the DID Document shape, or the security model) require a version bump, editor review, and a 7-day quiet period per §9 of the spec.

This specification is licensed under [Apache-2.0](./LICENSE). By contributing, you agree your contributions are likewise licensed under Apache-2.0. The W3C registry entry that cites this specification is governed separately by the [W3C Patent Policy][w3c-pp] and [Document License][w3c-dl].

## References

- W3C DID Core: <https://www.w3.org/TR/did-core/>
- W3C DID Method Registry: <https://github.com/w3c/did-spec-registries>
- OpenA2A Registry: <https://github.com/opena2a-org/opena2a-registry>

[registry]: https://github.com/opena2a-org/opena2a-registry
[did-core]: https://www.w3.org/TR/did-core/
[did-spec-registries]: https://github.com/w3c/did-spec-registries
[atx]: https://github.com/opena2a-standards/atx-conformance
[atp]: https://github.com/opena2a-standards/atp-conformance
[aip]: https://github.com/opena2a-standards/aip-conformance
[w3c-pp]: https://www.w3.org/Consortium/Patent-Policy-20040205/
[w3c-dl]: https://www.w3.org/Consortium/Legal/copyright-documents
