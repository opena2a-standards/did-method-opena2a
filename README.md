> **OpenA2A specs** · **did:opena2a** · [AIP](https://github.com/opena2a-standards/agent-identity-protocol) · [ATX](https://github.com/opena2a-standards/atx-spec) · [ATP](https://github.com/opena2a-standards/agent-trust-protocol) · [AAP](https://github.com/opena2a-standards/agent-authorization-protocol) · [AIM](https://github.com/opena2a-org/agent-identity-management) · [all specs ↗](https://specs.opena2a.org)

# did-method-opena2a

The `did:opena2a` Decentralized Identifier method specification.

A `did:opena2a` DID names a resource registered in an [OpenA2A Registry][registry] — an agent, an MCP server, an authority, a publisher, an AI tool, an LLM, a skill, or the registry itself. Resolution returns a [W3C DID Document][did-core] whose verification key is the Registry's Ed25519 signing key and whose service endpoints expose trust lookup, signed trust proofs, and trust badges.

```
did:opena2a:registry:opena2a.org
did:opena2a:authority:opena2a.org
did:opena2a:agent:agent_conformance_test_001
did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem
```

## Specification

The full specification is in [`did-method-opena2a.md`](./did-method-opena2a.md).

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

- [`atx-conformance`][atx] — Agent Trust Cross-Verification
- [`atp-conformance`][atp] — Agent Trust Protocol
- [`aip-conformance`][aip] — Agent Identity Protocol

Reference verifiers exist in Go, Rust, TypeScript, and Python; each suite produces byte-identical output across all four.

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
