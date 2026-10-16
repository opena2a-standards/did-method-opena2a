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

## Use cases

### A partner's agent calls your service and you have never met

Your service receives a request from software that says it is the dispatch agent at a partner company. There is no shared directory between the two companies, so you have nothing to look the name up in, and a name accepted on its own say-so hands an impostor whatever that agent is allowed to do.

`did:opena2a` gives the agent a name that resolves. An HTTP `GET` against the registry that issued the name returns a DID Document carrying the subject's keys and the endpoints where its trust record lives, so the receiving side has something to check instead of something to believe.

What you can do today: resolve the reference registry's own DID (`jq .` only formats the reply).

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

Where it stops today: the reference resolver still emits the 0.1 document shape. For a resource DID it publishes the registry's signing key and not the subject's own key, so a verifier cannot yet use the resolved document to check that the caller holds the key behind the name.

The reference resolver also answers every `did:opena2a:registry:<authority>` DID with this same document: `curl -s https://api.oa2a.org/api/v1/did/did:opena2a:registry:example.com | jq -r .id` prints `did:opena2a:registry:opena2a.org`. A verifier rejects that answer by checking the resolved `id` against the DID it requested (spec Section 6.5).

### An agent connects to a tool it did not write

An agent is about to call an MCP server it found in a package registry. It has no way to ask who that server is or what is known about it, so it connects and acts on whatever comes back, and a poisoned tool result can turn the agent against the person it works for.

MCP servers are a `did:opena2a` resource type. The resolved document carries service endpoints for trust lookup, a signed trust proof and a trust badge, so the agent can read the registry's record of the server before the call.

What you can do today:

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

Where it stops today: a `did:opena2a` identifier does not say which registry issued it, and the reference deployment does not yet emit the `issuingRegistry` resolution metadata that revision 0.2 defines, so a verifier pins its registry by configuration.

What you can check yourself: the specification is [`did-method-opena2a.md`](./did-method-opena2a.md); the 0.2 document shapes are in [`examples/`](./examples/); the method is registered in the W3C DID Extensions registry ([w3c/did-extensions#717](https://github.com/w3c/did-extensions/pull/717)); the resolver above is live at `api.oa2a.org`; and `did:opena2a` identifiers appear in byte-pinned fixtures of the suites under [Conformance](#conformance), each with Go and Python reference verifiers.

The use cases in full, with each suite's fixture count: [`docs/use-cases.md`](./docs/use-cases.md).

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

The registry replies with a DID Document, `Content-Type: application/did+ld+json`, and a 5-minute cache header (spec Section 4.2).

## Examples

See [`examples/`](./examples/) for DID Documents in the 0.2 shape, one per resource type the reference deployment serves (`agent`, `mcp_server`, `ai_tool`, `llm`, `skill`) plus the registry self-DID. A resolved document still differs from its example where 0.2 differs from what the reference resolver emits. The registry key values are placeholders.

[`examples/conformance/`](./examples/conformance/) holds two identifiers the conformance suites carry that the deployment does not serve (both answer `404`). `python3 scripts/check_examples.py` checks the file set, the 0.2 shape and the service URL encoding; with `--live` it also resolves each DID against the reference deployment and compares its `service` and keys. It exits 1 on a difference.

What `python3 scripts/check_examples.py --live` prints ([full output](./docs/captures/check-examples-live.txt)):

```
examples match: 6 served, 2 conformance, resolved against the reference deployment
```

How each example compares with what the deployment returns: [`docs/examples.md`](./docs/examples.md).

## Conformance

Three conformance suites carry `did:opena2a:` identifiers in byte-stable test fixtures:

- [`atx-conformance`][atx]: Agent Trust eXtension (ATX) credentials
- [`atp-conformance`][atp]: Agent Trust Protocol
- [`aip-conformance`][aip]: Agent Identity Protocol

Each suite ships reference verifiers in Go and Python. Fixture bytes are pinned by each suite's `MANIFEST.sha256`, and both verifiers must reproduce every fixture's pinned expected verdict. Signature coverage differs by suite:

- ATX: both verifiers verify Ed25519 and ML-DSA-65 hybrid signatures.
- ATP: the Go verifier verifies Ed25519 and ML-DSA-65; the Python verifier verifies Ed25519 and records an ML-DSA-65 signature as present without verifying it, leaving full hybrid verification to the Go verifier.
- AIP: both verifiers verify Ed25519 only, and no AIP fixture carries an ML-DSA-65 signature.

The ATX suite additionally pins RFC 8785 (JCS) canonical-bytes agreement across independent Go, Python, and TypeScript canonicalizers (`jcs-vectors/`).

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
- [`docs/trust-model.md`](./docs/trust-model.md): how a registry-mediated method compares with self-certifying and ledger-anchored methods
- [`docs/status.md`](./docs/status.md): the specification's revision and registration, and what the reference deployment does not yet follow
- [`CHANGELOG.md`](./CHANGELOG.md): changes by revision
- [`CONTRIBUTING.md`](./CONTRIBUTING.md): how a change is proposed and reviewed, and the syntax check to run
- [`MAINTAINERS.md`](./MAINTAINERS.md): the specification's editors
- W3C DID Core: <https://www.w3.org/TR/did-core/>
- W3C DID Extensions registry: <https://github.com/w3c/did-extensions>
- OpenA2A Registry reference deployment, discovery document (live): <https://api.oa2a.org/.well-known/opena2a>. The registry source is private; spec Section 8 says what a public reader can check.

## License

This specification is licensed under [Apache-2.0](./LICENSE).

[registry]: ./did-method-opena2a.md#8-reference-implementations
[did-core]: https://www.w3.org/TR/did-core/
[atx]: https://github.com/opena2a-standards/atx-conformance
[atp]: https://github.com/opena2a-standards/atp-conformance
[aip]: https://github.com/opena2a-standards/aip-conformance
