# Use cases

## A partner's agent calls your service and you have never met

Your service receives a request from software that says it is the dispatch agent at a partner company. There is no shared directory between the two companies, so you have nothing to look the name up in, and a name accepted on its own say-so hands an impostor whatever that agent is allowed to do. Your customers carry the damage, because it is their orders and records the impostor touches.

`did:opena2a` gives the agent a name that resolves. An HTTP `GET` against the registry that issued the name returns a DID Document carrying the subject's keys and the endpoints where its trust record lives, so the receiving side has something to check instead of something to believe.

What you can do today: resolve the reference registry's own DID.

```sh
curl https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org
```

Where it stops today: the reference resolver still emits the 0.1 document shape. For a resource DID it publishes the registry's signing key and not the subject's own key, so a verifier cannot yet use the resolved document to check that the caller holds the key behind the name. It also answers every `did:opena2a:registry:<authority>` DID with this same document: `curl -s https://api.oa2a.org/api/v1/did/did:opena2a:registry:example.com | jq -r .id` prints `did:opena2a:registry:opena2a.org` (measured 2026-10-12). A verifier rejects that answer by checking the resolved `id` against the DID it requested (spec Section 6.5).

## An agent connects to a tool it did not write

An agent is about to call an MCP server it found in a package registry. It has no way to ask who that server is or what is known about it, so it connects and acts on whatever comes back, and a poisoned tool result can turn the agent against the person it works for.

MCP servers are a `did:opena2a` resource type. The resolved document carries service endpoints for trust lookup, a signed trust proof and a trust badge, so the agent can read the registry's record of the server before the call.

What you can do today:

```sh
curl "https://api.oa2a.org/api/v1/did/did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem"
```

Where it stops today: a `did:opena2a` identifier does not say which registry issued it, and the reference deployment does not yet emit the `issuingRegistry` resolution metadata that revision 0.2 defines, so a verifier pins its registry by configuration.

What you can check yourself: the specification is [`did-method-opena2a.md`](../did-method-opena2a.md); the 0.2 document shapes are in [`examples/`](../examples/); the method is registered in the W3C DID Extensions registry ([w3c/did-extensions#717](https://github.com/w3c/did-extensions/pull/717)); the resolver above is live at `api.oa2a.org`; and `did:opena2a` identifiers appear in byte-pinned fixtures of [atx-conformance](https://github.com/opena2a-standards/atx-conformance) (all 25 fixtures), [atp-conformance](https://github.com/opena2a-standards/atp-conformance) (all 14 fixtures) and [aip-conformance](https://github.com/opena2a-standards/aip-conformance) (the 4 challenge-response fixtures of its 7; the 3 trust-score fixtures carry none), each with Go and Python reference verifiers.
