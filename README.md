> **OpenA2A specs** · **did:opena2a** · [AIP](https://github.com/opena2a-standards/agent-identity-protocol) · [ATX](https://github.com/opena2a-standards/atx-spec) · [ATP](https://github.com/opena2a-standards/agent-trust-protocol) · [AAP](https://github.com/opena2a-standards/agent-authorization-protocol) · [AIM](https://github.com/opena2a-org/agent-identity-management) · [all specs ↗](https://specs.opena2a.org)

# did-method-opena2a

The `did:opena2a` Decentralized Identifier method specification.

**W3C registration:** registered in the W3C DID Extensions registry, [w3c/did-extensions#717](https://github.com/w3c/did-extensions/pull/717).

A `did:opena2a` DID names a resource registered in an [OpenA2A Registry][registry]: an agent, an MCP server, an authority, a publisher, an AI tool, an LLM, a skill, or the registry itself.

```
did:opena2a:registry:opena2a.org
did:opena2a:authority:opena2a.org
did:opena2a:agent:agent_conformance_test_001
did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem
```

`did:opena2a` is the ecosystem-scoped method of the OpenA2A specification family, used at the ATP and ATX layer. An AIP identity provider issues and resolves its own provider-scoped identifiers, a `did:web` profile, and does not serve `did:opena2a`. The specification's [Status of this document](./did-method-opena2a.md#status-of-this-document) cites the AIP revision and section that say so.

## Specification

The full specification is in [`did-method-opena2a.md`](./did-method-opena2a.md).

## Resolution

Resolution returns a [W3C DID Document][did-core] that carries the subject's own keys under `authentication` and the issuing registry's Ed25519 signing key under `assertionMethod`, and whose service endpoints expose trust lookup, signed trust proofs, and trust badges.

A `did:opena2a` DID is resolved by HTTP `GET` against the registry that issued it. Against the reference deployment:

```sh
curl -si https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org
```

What `curl -si https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org` prints, trimmed ([full output](./docs/captures/resolve-registry-headers.txt)):

```
content-type: application/did+ld+json
...
cache-control: public, max-age=300
```

Resolve the reference registry's own DID (`jq .` only formats the reply):

```sh
curl -s https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org | jq .
```

What `curl -s https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org | jq .` prints, trimmed ([full output](./docs/captures/resolve-registry.txt)):

```
{
...
  "id": "did:opena2a:registry:opena2a.org",
...
  "authentication": [
    "did:opena2a:registry:opena2a.org#signing-key"
  ],
...
  "service": [
    {
      "id": "did:opena2a:registry:opena2a.org#trust-api",
      "type": "TrustAPI",
      "serviceEndpoint": "https://api.oa2a.org/api/v1/trust/query"
    },
...
  ],
...
}
```

MCP servers are a `did:opena2a` resource type:

```sh
curl -s 'https://api.oa2a.org/api/v1/did/did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem' | jq .
```

What `curl -s 'https://api.oa2a.org/api/v1/did/did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem' | jq .` prints, trimmed ([full output](./docs/captures/resolve-mcp-server.txt)):

```
{
...
  "verificationMethod": [
    {
      "id": "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem#registry-key",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:opena2a:registry:opena2a.org",
...
  "service": [
    {
      "id": "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem#trust-lookup",
      "type": "TrustLookup",
...
      "id": "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem#trust-proof",
      "type": "TrustProof",
...
      "id": "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem#badge",
      "type": "TrustBadge",
...
}
```

Where it stops today: the reference resolver still emits the 0.1 document shape and does not yet emit `issuingRegistry` resolution metadata. What a verifier does about each: [`docs/use-cases.md`](./docs/use-cases.md).

## Examples

See [`examples/`](./examples/) for DID Documents in the 0.2 shape, one per resource type the reference deployment serves, plus the registry self-DID. [`examples/conformance/`](./examples/conformance/) holds two identifiers the conformance suites carry. `python3 scripts/check_examples.py --live` resolves each DID against the reference deployment and exits 1 on a difference.

What `python3 scripts/check_examples.py --live` prints ([full output](./docs/captures/check-examples-live.txt)):

```
examples match: 6 served, 2 conformance, resolved against the reference deployment
```

## Conformance

Three conformance suites carry `did:opena2a:` identifiers in byte-stable test fixtures, each with reference verifiers in Go and Python: [`atx-conformance`][atx], [`atp-conformance`][atp] and [`aip-conformance`][aip].

This repository carries resolution vectors for the resolved-`id` check of spec Section 6.5 in [`vectors/`](./vectors/), including a negative vector a verifier must reject. Run the reference check over them with `python3 scripts/check_vectors.py`.

What `python3 scripts/check_vectors.py` prints ([full output](./docs/captures/check-vectors.txt)):

```
ok    vectors/registry-self.json: accept
ok    vectors/registry-substitution.json: reject resolved-id-mismatch
2 vectors, 0 failures
```

## Documentation

- [`did-method-opena2a.md`](./did-method-opena2a.md): the specification
- [`docs/use-cases.md`](./docs/use-cases.md): the use cases in full, with each conformance suite's fixture count
- [`docs/examples.md`](./docs/examples.md): how each example compares with what the reference deployment returns
- [`docs/conformance.md`](./docs/conformance.md): each conformance suite's signature coverage and canonicalization check
- [`docs/trust-model.md`](./docs/trust-model.md): how a registry-mediated method compares with self-certifying and ledger-anchored methods
- [`docs/status.md`](./docs/status.md) and [`CHANGELOG.md`](./CHANGELOG.md): the specification's revision and registration, what the deployment does not yet follow, and changes by revision
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) and [`MAINTAINERS.md`](./MAINTAINERS.md): how a change is proposed and reviewed, the syntax check to run, and the specification's editors
- W3C DID Core: <https://www.w3.org/TR/did-core/>; W3C DID Extensions registry: <https://github.com/w3c/did-extensions>
- OpenA2A Registry reference deployment, discovery document (live): <https://api.oa2a.org/.well-known/opena2a>. The registry source is private; spec Section 8 says what a public reader can check.

## License

This specification is licensed under [Apache-2.0](./LICENSE).

[registry]: ./did-method-opena2a.md#8-reference-implementations
[did-core]: https://www.w3.org/TR/did-core/
[atx]: https://github.com/opena2a-standards/atx-conformance
[atp]: https://github.com/opena2a-standards/atp-conformance
[aip]: https://github.com/opena2a-standards/aip-conformance
