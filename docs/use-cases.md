# Use cases

This page opens with who reads the specification and where each reader's question is answered, then gives each use case with what you can do today and where it stops.

## Who reads this

Each row names a reader, the question that brings them here and the text that answers it. A `did-method-opena2a.md:N` reference is the line in the specification at the commit that added this table; the section link stays stable when lines move.

| Reader | The question they bring | Where it is answered |
|---|---|---|
| Security leader or CISO | What does relying on a registry-issued identifier expose us to, and what must our verifiers do about it? | [You have to decide whether to rely on a registry-issued identifier](#you-have-to-decide-whether-to-rely-on-a-registry-issued-identifier); the trust root of [Section 6.1](../did-method-opena2a.md#61-trust-root) (`did-method-opena2a.md:399`); availability and centralization risk, [Section 6.6](../did-method-opena2a.md#66-availability-and-centralization-risk) (`did-method-opena2a.md:429`); personal data, [Section 7.3](../did-method-opena2a.md#73-personally-identifiable-information) (`did-method-opena2a.md:460`) |
| IAM professional or identity architect | How does this method relate to `did:web`, `did:key` and the identity systems I run, and which key in a resolved document proves what? | [Your identity team asks which key in a resolved document proves what](#your-identity-team-asks-which-key-in-a-resolved-document-proves-what); the verification relationships of [Section 5.1.1](../did-method-opena2a.md#511-verification-relationships) (`did-method-opena2a.md:372`); the scope relative to AIP in [Status of this document](../did-method-opena2a.md#status-of-this-document) (`did-method-opena2a.md:31`); the trust-model axis, [Section 6.7](../did-method-opena2a.md#67-trust-model-axis) (`did-method-opena2a.md:439`) and [`docs/trust-model.md`](trust-model.md) |
| Platform or security engineer | How do I resolve and verify a DID, and what does a failure look like? | [A partner's agent calls your service](#a-partners-agent-calls-your-service-and-you-have-never-met); [An agent connects to a tool it did not write](#an-agent-connects-to-a-tool-it-did-not-write); Read (resolve), [Section 4.2](../did-method-opena2a.md#42-read-resolve) (`did-method-opena2a.md:243`); transport, [Section 6.2](../did-method-opena2a.md#62-resolver-authentication-and-transport) (`did-method-opena2a.md:405`); key revocation, [Section 6.4](../did-method-opena2a.md#64-key-revocation) (`did-method-opena2a.md:417`) |
| Agent developer or implementer | What do I implement first, and how do I check it? | the syntax of [Section 3.1](../did-method-opena2a.md#31-syntax-abnf) (`did-method-opena2a.md:84`); the resolution vectors of [Section 8.5](../did-method-opena2a.md#85-resolution-vectors-informative) (`did-method-opena2a.md:520`); the public reference resolver, [Section 8.6](../did-method-opena2a.md#86-public-reference-resolver-informative) (`did-method-opena2a.md:524`) |
| GRC, audit or compliance reader | Which controls does it support, and what can an auditor test? | The specification maps to no control framework. The requirements an auditor can test are the verifier rules of [Section 6.1](../did-method-opena2a.md#61-trust-root) (`did-method-opena2a.md:403`) and [Section 6.5](../did-method-opena2a.md#65-forgeability-of-the-did-string-itself) (`did-method-opena2a.md:427`), and the rule that a DID Document carries no personal contact data, [Section 7.3](../did-method-opena2a.md#73-personally-identifiable-information) (`did-method-opena2a.md:462`). Correlation across one publisher's DIDs is intended and public, [Section 7.4](../did-method-opena2a.md#74-correlation-across-resources) (`did-method-opena2a.md:464`) |
| Standards reviewer (IETF or AIW participant) | Is the method registered, how does it differ from other DID methods, and how are changes made? | [Status of this document](../did-method-opena2a.md#status-of-this-document) (`did-method-opena2a.md:23`); [Section 6.7](../did-method-opena2a.md#67-trust-model-axis) (`did-method-opena2a.md:439`) and [`docs/trust-model.md`](trust-model.md); the change process of [Section 9](../did-method-opena2a.md#9-versioning-and-change-process) (`did-method-opena2a.md:539`); [`docs/status.md`](status.md) |

### The readers

- **Security leader or CISO**
  - Who: accountable for the organization's security risk, and for which agents and vendors may act on its systems.
  - Why they open it: agents and tools from partners arrive named by `did:opena2a` identifiers, and the organization must decide whether to accept a registry's word for who they are.
  - What they decide: which registries to pin, what verifiers must check before they trust a resolution, and what an outage of the registry means for the organization.
  - How they verify: the verifier rules of Section 6.1, the resolution vectors in this repository, and Section 6.6 on availability.
- **IAM professional or identity architect**
  - Who: runs the identity systems the organization already has, such as OAuth 2.0 and OpenID Connect, X.509 certificates, workload identity such as SPIFFE, DIDs and privileged access management.
  - Why they open it: they need to place a registry-mediated DID method beside `did:web`, `did:key` and the systems they run.
  - What they decide: which DID methods to accept for which purpose, and which key in a resolved document a verifier may use for a proof of possession.
  - How they verify: Section 5.1.1 against the documents in [`examples/`](../examples/), and [`docs/trust-model.md`](trust-model.md).
- **Platform or security engineer**
  - Who: deploys, operates and monitors the components that check agents at runtime, and is paged when they fail.
  - Why they open it: they run the resolver client, its cache and its pinning, and need to know how resolution fails.
  - What they decide: which registry to pin, how long to cache a resolution (the registry sends five minutes), and how often to refresh the registry's discovery document (at least daily, Section 6.4).
  - How they verify: `python3 scripts/check_vectors.py`, and `python3 scripts/check_examples.py --live` against the reference deployment.
- **Agent developer or implementer**
  - Who: writes a resolver, a registry or a verifier that handles `did:opena2a` identifiers.
  - Why they open it: they have to parse, canonicalize and resolve identifiers the same way other implementations do.
  - What they decide: how to parse and canonicalize an identifier, and which document shape to emit.
  - How they verify: `python3 scripts/check_did_syntax.py`, the resolution vectors, and the public reference resolver of Section 8.6.
- **GRC, audit or compliance reader**
  - Who: maps controls to evidence and reads the records an auditor asks for.
  - Why they open it: an auditor asks what an agent's identifier proves, and whether resolving it exposes personal data.
  - What they decide: which verifier rules to test, and whether the public correlation of one publisher's DIDs is acceptable.
  - How they verify: Sections 6.1, 6.5, 7.3 and 7.4.
- **Standards reviewer (IETF or AIW participant)**
  - Who: a participant in an IETF or AIW discussion who judges whether a problem needs new work.
  - Why they open it: to judge a registry-mediated DID method registered in the W3C DID Extensions registry, and how it differs from self-certifying and ledger-anchored methods.
  - What they decide: whether to review or implement it, and what to ask the editors to change.
  - How they verify: the registration ([w3c/did-extensions#717](https://github.com/w3c/did-extensions/pull/717)), [`docs/trust-model.md`](trust-model.md) and the change process of Section 9.

## A partner's agent calls your service and you have never met

Your service receives a request from software that says it is the dispatch agent at a partner company. There is no shared directory between the two companies, so you have nothing to look the name up in, and a name accepted on its own say-so hands an impostor whatever that agent is allowed to do. Your customers carry the damage, because it is their orders and records the impostor touches.

`did:opena2a` gives the agent a name that resolves. An HTTP `GET` against the registry that issued the name returns a DID Document carrying the subject's keys and the endpoints where its trust record lives, so the receiving side has something to check instead of something to believe.

What you can do today: resolve the reference registry's own DID.

```sh
curl https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org
```

Where it stops today: the reference deployment's resolver still emits the 0.1 document shape. For a resource DID it publishes the registry's signing key and not the subject's own key, so a verifier cannot yet use the resolved document to check that the caller holds the key behind the name. `did:opena2a:registry:example.com`, which names another registry, gets `404`: `curl -s -w ' %{http_code}\n' https://api.oa2a.org/api/v1/did/did:opena2a:registry:example.com` prints `{"error":"resource not found: registry/example.com"} 404` (measured 2026-10-21), where on 2026-10-12 the deployment answered it with this same document. A verifier still checks the resolved `id` against the DID it requested and rejects the resolution when they differ (spec Section 6.5).

Who acts: the platform or security engineer whose service receives the call.

Spec text: resolution by HTTP `GET` against the issuing registry, [Section 4.2](../did-method-opena2a.md#42-read-resolve) (`did-method-opena2a.md:243`); the verifier rules of [Section 6.1](../did-method-opena2a.md#61-trust-root) (`did-method-opena2a.md:403`); and the resolved-`id` check of [Section 6.5](../did-method-opena2a.md#65-forgeability-of-the-did-string-itself) (`did-method-opena2a.md:427`).

## An agent connects to a tool it did not write

An agent is about to call an MCP server it found in a package registry. It has no way to ask who that server is or what is known about it, so it connects and acts on whatever comes back, and a poisoned tool result can turn the agent against the person it works for.

MCP servers are a `did:opena2a` resource type. The resolved document carries service endpoints for trust lookup, a signed trust proof and a trust badge, so the agent can read the registry's record of the server before the call.

What you can do today:

```sh
curl "https://api.oa2a.org/api/v1/did/did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem"
```

Where it stops today: a `did:opena2a` identifier does not say which registry issued it, and the reference deployment does not yet emit the `issuingRegistry` resolution metadata that revision 0.2 defines, so a verifier pins its registry by configuration.

Who acts: the developer whose agent calls the tool, or the platform team that runs the agent.

Spec text: the resource types, `mcp_server` among them, of [Section 3.2](../did-method-opena2a.md#32-resource-type-registry) (`did-method-opena2a.md:129`); the service endpoints of a resolved document, [Section 5.2](../did-method-opena2a.md#52-service) (`did-method-opena2a.md:381`); and the issuing-registry rule of [Section 3.5](../did-method-opena2a.md#35-issuing-registry) (`did-method-opena2a.md:219`).

## You have to decide whether to rely on a registry-issued identifier

Agents and tools from outside your organization now arrive with `did:opena2a` names. Accepting one means trusting the registry that issued it to say who it belongs to. You have to decide on what terms your organization accepts that, and what happens when the registry is wrong, compromised or down.

Who acts: the security leader, with the engineers who run the verifiers.

Without the specification: a name in a request is accepted on its own say-so, or each team decides for itself which directory to believe and how far.

What the specification does: a `did:opena2a` string is not, by itself, evidence of anything, and a consumer MUST NOT treat a bare DID string in untrusted input as authoritative without the full resolve-and-verify process ([Section 6.5](../did-method-opena2a.md#65-forgeability-of-the-did-string-itself), `did-method-opena2a.md:425`). Verifiers MUST pin the registry they trust, MUST verify its discovery document over HTTPS, MUST check the issuing registry from resolution metadata, and MUST check that the resolved document's `id` is the canonical form of the DID they requested ([Section 6.1](../did-method-opena2a.md#61-trust-root), `did-method-opena2a.md:403`). Compromise of a registry's signing key lets an attacker forge trust proofs for every DID that registry issued (`did-method-opena2a.md:401`). The specification does not claim that the method is fully decentralized: a sustained outage of a registry run as a single deployment leaves the DIDs it issued unresolvable beyond five minutes of cached resolution, except those whose trust proofs an offline bundle carries ([Section 6.6](../did-method-opena2a.md#66-availability-and-centralization-risk), `did-method-opena2a.md:429`). A DID Document MUST NOT carry contact emails, real names or other personal contact data ([Section 7.3](../did-method-opena2a.md#73-personally-identifiable-information), `did-method-opena2a.md:462`).

What to require, in the specification's terms: verifiers that pin the registries you chose and make the four checks of Section 6.1, a plan for a registry outage, and no personal contact data in the documents your own registry publishes.

How to see it work: the repository's resolution vectors include a substitution, in which a request for an unregistered registry DID was answered with the document of the resolving registry's own DID, and the reference check rejects it. From a clone of this repository:

```sh
python3 scripts/check_vectors.py
```

Output on 2026-10-30, at the commit that added this use case:

```
ok    vectors/registry-self.json: accept
ok    vectors/registry-substitution.json: reject resolved-id-mismatch
2 vectors, 0 failures
```

Out of scope: squatting on a resource name is mitigated upstream of this specification ([Section 6.3](../did-method-opena2a.md#63-resource-squatting-and-impersonation), `did-method-opena2a.md:409`). The specification says how to check a registry's answer, not which registries deserve trust. The reference deployment emits no `issuingRegistry` metadata, so a verifier pins its registry by configuration, as the use case above says.

## Your identity team asks which key in a resolved document proves what

Your identity team already works with DIDs, for example `did:web` names for its own services. It is asked to accept `did:opena2a` names for agents and tools, and needs to know what a resolved document lets a verifier prove and how this method relates to the ones it already uses.

Who acts: the IAM professional or identity architect.

Without the specification: a resolved document is a list of keys, and a verifier that accepts any key in it for any purpose can be shown a registry's signature as if it were the agent's own proof.

What the specification does: every document binds each key to a purpose ([Section 5.1.1](../did-method-opena2a.md#511-verification-relationships), `did-method-opena2a.md:372`). `authentication` lists the subject's own keys only, and a verifier that checks a proof of possession MUST use one of them and MUST NOT accept the registry key for that purpose (`did-method-opena2a.md:376`). `assertionMethod` lists the registry key only, and a verifier that checks a signed trust proof MUST use a key listed there (`did-method-opena2a.md:377`). The method is ecosystem-scoped and used at the ATP and ATX layer; an AIP identity provider issues its own provider-scoped `did:web` identifiers and does not serve `did:opena2a` ([Status of this document](../did-method-opena2a.md#status-of-this-document), `did-method-opena2a.md:31`). It is registry-mediated, one point on an axis that also holds self-certifying methods such as `did:key` and ledger-anchored methods, and an implementation SHOULD pick the anchor that matches the guarantee it needs ([Section 6.7](../did-method-opena2a.md#67-trust-model-axis), `did-method-opena2a.md:445`; [`docs/trust-model.md`](trust-model.md)).

How to see it work: the conformance agent in [`examples/conformance/`](../examples/conformance/) carries both relationships, each with its own key. From a clone of this repository:

```sh
jq '{id, authentication, assertionMethod}' examples/conformance/agent.json
```

Output on 2026-10-30:

```
{
  "id": "did:opena2a:agent:agent_conformance_test_001",
  "authentication": [
    "did:opena2a:agent:agent_conformance_test_001#key-1"
  ],
  "assertionMethod": [
    "did:opena2a:agent:agent_conformance_test_001#registry-key"
  ]
}
```

The examples for the resource types the reference deployment serves list only the registry key, under `assertionMethod`, and have no `authentication` member, so for those resources there is no key a verifier may use for a proof of possession.

Out of scope: the specification defines no mapping onto OAuth 2.0, OpenID Connect, SPIFFE or X.509 certificates. It names resources and publishes their keys; proving that a caller holds the key behind a name is the job of the protocol that checks the proof, such as the AIP challenge-response that Section 5.1.1 cites.

## What you can check yourself

What you can check yourself: the specification is [`did-method-opena2a.md`](../did-method-opena2a.md); the 0.2 document shapes are in [`examples/`](../examples/); the method is registered in the W3C DID Extensions registry ([w3c/did-extensions#717](https://github.com/w3c/did-extensions/pull/717)); the resolver above is live at `api.oa2a.org`; and `did:opena2a` identifiers appear in byte-pinned fixtures of [atx-conformance](https://github.com/opena2a-standards/atx-conformance) (all 25 fixtures), [atp-conformance](https://github.com/opena2a-standards/atp-conformance) (all 14 fixtures) and [aip-conformance](https://github.com/opena2a-standards/aip-conformance) (the 4 challenge-response fixtures of its 7; the 3 trust-score fixtures carry none), each with Go and Python reference verifiers.
