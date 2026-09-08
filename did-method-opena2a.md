# The `did:opena2a` DID method specification

**Version:** 0.2 (draft)
**Status:** Registered in the W3C DID Extensions registry (did-extensions #717, merged 2026-07-04)
**License:** Apache License, Version 2.0
**Editor:** Abdel Sy Fane (OpenA2A, <abdelsyfane@gmail.com>)
**Repository:** <https://github.com/opena2a-standards/did-method-opena2a>

---

## Abstract

This specification defines the `did:opena2a` Decentralized Identifier method. A `did:opena2a` identifier names a resource (an agent, an MCP server, an authority, a publisher, an AI tool, an LLM, a skill, or a registry itself) that is registered in an OpenA2A Registry. Resolution returns a W3C DID Document that carries the subject's own keys under `authentication` and the issuing registry's Ed25519 signing key under `assertionMethod`, and whose `service` endpoints expose trust lookup, signed trust proofs, and trust badges for the named resource.

The method is implemented by the OpenA2A Registry (`opena2a-org/opena2a-registry`), and `did:opena2a` identifiers appear in the byte-stable test vectors of three conformance suites:

- Agent Trust eXtension (ATX)
- Agent Trust Protocol (ATP)
- Agent Identity Protocol (AIP)

This document specifies the method's syntax, operations, resolution behaviour, and security and privacy considerations.

## Status of this document

This is revision 0.2 of the `did:opena2a` method specification. The method is registered in the W3C DID Extensions registry ([w3c/did-extensions#717](https://github.com/w3c/did-extensions/pull/717), merged 2026-07-04); the registry entry cites this document. The method has been in production use since OpenA2A Registry migration 102 (Ed25519 trust proofs) and is advertised by the reference deployment's discovery document under `supportedMethods: ["did:opena2a"]` (Section 8.4).

Revision 0.2 changes the DID Document shape (Section 5): the subject's own keys are published under `authentication` and the issuing registry's key under `assertionMethod`. The reference resolver emits the 0.1 shape (a single registry key under both relationships) as of the source read for this revision; see the implementation status notes in Sections 4.2 and 5.1.

Scope relative to the Agent Identity Protocol: `did:opena2a` is the ecosystem-scoped method of the OpenA2A specification family. It names resources listed in a registry and is used at the ATP and ATX layer. An AIP identity provider issues and resolves its own provider-scoped identifiers and does not serve `did:opena2a` (AIP-SPEC 1.0.2-draft, Section 3.2; `draft-fane-opena2a-aip-03`).

Substantive changes to this document are tracked in the repository's `CHANGELOG.md`.

## Table of contents

1. [Introduction](#1-introduction)
2. [Method name](#2-method-name)
3. [Method-specific identifier](#3-method-specific-identifier)
4. [Method operations](#4-method-operations)
5. [DID Document structure](#5-did-document-structure)
6. [Security considerations](#6-security-considerations)
7. [Privacy considerations](#7-privacy-considerations)
8. [Reference implementations](#8-reference-implementations)
9. [Versioning and change process](#9-versioning-and-change-process)
10. [References](#10-references)

## 1. Introduction

OpenA2A is an open ecosystem for agent-to-agent trust. Its core component, the OpenA2A Registry, catalogues software resources that participate in agent-to-agent and human-to-agent interactions: MCP servers, AI tools, LLMs, skills, autonomous agents, the publishers and authorities that vouch for them, and the registry itself. Each catalogued resource is assigned a DID of the form `did:opena2a:<type>:<id>`.

A `did:opena2a` DID is bound to a specific resource type and a specific identifier within that type. Resolving the DID returns a W3C DID Document with two kinds of verification material:

- the subject's own keys, listed under `authentication`, with the subject as controller. A signature verified against one of these keys is a proof of possession by the subject;
- the issuing registry's Ed25519 signing key, listed under `assertionMethod`, with the registry as controller. A signature verified against this key is an assertion the registry makes about the subject (a signed trust proof), not an act of the subject.

The trust model is explicit. A verifier trusts a registry's assertions about a `did:opena2a` subject exactly as much as it trusts the registry that issued the DID, and it pins that registry (Section 6.1). A verifier trusts a proof of possession exactly as much as it trusts the resolved document's binding of the subject key, which in turn rests on the same registry.

The `did:opena2a` method is not a fully decentralized identifier method in the sense of `did:peer` or `did:key`. It is a registry-mediated method that derives its utility from the auditable, public nature of a registry and the byte-stable interoperability surface defined by the OpenA2A conformance suites.

### 1.1 Examples

```
did:opena2a:registry:opena2a.org
did:opena2a:authority:opena2a.org
did:opena2a:authority:gov.uk
did:opena2a:agent:agent_conformance_test_001
did:opena2a:agent:agent_conformance_test_001#key-1
did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem
did:opena2a:publisher:google.com
did:opena2a:llm:openai
did:opena2a:ai_tool:langchain
did:opena2a:skill:web-research
```

## 2. Method name

The method name that shall identify this DID method is: `opena2a`.

A DID that uses this method MUST begin with the following literal prefix: `did:opena2a:`. The prefix is normalized to lowercase. All bytes are US-ASCII.

## 3. Method-specific identifier

### 3.1 Syntax (ABNF)

<!-- opena2a-definition: did-syntax -->
This section and Section 3.1.1 are the one home of the `did:opena2a` string form for the
OpenA2A specification family; ATX, ATP and AAP cite them rather than restate the grammar.

```
opena2a-did       = "did:opena2a:" resource-type ":" resource-id [ "#" fragment ]
resource-type     = ALPHA-LOWER *( ALPHA-LOWER / "_" )
resource-id       = 1*( unreserved / ":" )
fragment          = 1*( unreserved )

ALPHA-LOWER       = %x61-7A          ; a-z
unreserved        = ALPHA / DIGIT / "." / "_" / "-" / "/" / "@"
ALPHA             = %x41-5A / %x61-7A
DIGIT             = %x30-39
```

A `resource-type` is a non-empty, lowercase ASCII alphabetic prefix that may contain underscores. A `resource-id` is one or more characters drawn from the `unreserved` set, with the colon (`:`) permitted to allow path-style identifiers used by some upstream package ecosystems. The fragment component is optional and is used to identify a specific verification method or service endpoint within the DID Document (for example, `#key-1` or `#trust-lookup`).

The `resource-type` is intentionally an open ABNF rule. New resource types are expected to be added to a registry over time without requiring revisions to this specification.

### 3.1.1 Relationship to the DID Core `idchar` production

DID Core restricts the generic `method-specific-id` to the `idchar` set `ALPHA / DIGIT / "." / "-" / "_" / pct-encoded`: the forward slash (`/`) and commercial at (`@`) are not permitted unescaped and would ordinarily be percent-encoded as `%2F` and `%40`. The `did:opena2a` `unreserved` rule in Section 3.1 **intentionally extends** that set to admit `/` and `@` unescaped, so that a DID mirrors the upstream identifier it names (scoped npm package names such as `@modelcontextprotocol/server-filesystem`, and path-style agent and skill ids) without a lossy encoding step. This keeps a `did:opena2a` string human-readable and byte-identical to the identifier a developer already knows.

Signed artifacts (ATX credentials, ATP trust proofs, AAP tokens) MUST carry exactly one form of a `did:opena2a` identifier: the unescaped form above. Verifiers MUST compare identifiers after the normalization of Section 3.3 and MUST NOT normalize an identifier before verifying a signature over bytes that contain it.

This is a deliberate, documented deviation from strict DID Core syntax, recorded here rather than left implicit. The percent-encoded serialization `did:opena2a:mcp_server:%40modelcontextprotocol%2Fserver-filesystem` is the strict-DID-Core-conformant equivalent of the same identifier and denotes the same DID subject; the DID Document `service` endpoint URLs in Section 5 carry the percent-encoded form where a URL context requires it. Consumers that require generic-DID-grammar conformance MAY percent-encode the `resource-id` before parsing; consumers operating within the OpenA2A ecosystem SHOULD accept the unescaped form. Note that the `unreserved` rule name in Section 3.1 is local to this specification and is broader than the identically named RFC 3986 production, which does not include `/` or `@`.

### 3.2 Resource type registry

This section is the **shared resource-type registry** for the OpenA2A
specification family: ATX (core.md Sections 2 and 14), ATP-SPEC (Section 3.1), and AIP-SPEC
example identifiers all defer to this table for the set of registered
`resource-type` values. Additions are made by pull request against this
repository (the same change policy the ATX Section 14 registry table records) and
are mirrored into the consuming specifications.
[`registries/resource-types.json`](./registries/resource-types.json) is generated from this
table by `scripts/gen_registries.py` and checked in CI, so consumers can pin the registry by
commit the way the conformance suites pin schemas.

Registration governs *issuance*, not *resolution*: implementations MUST NOT
reject a DID solely because the `resource-type` slot contains an unregistered
value that otherwise conforms to the ABNF in Section 3.1. Implementations MAY return
a 404 Not Found if the registry has no record of the named resource.

<!-- opena2a-definition: did-resource-types -->
| Resource type    | Description                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------------- |
| `registry`       | An OpenA2A Registry deployment itself. A registry names itself `did:opena2a:registry:<authority>`; the registry that issued a DID is the trust root for that DID (Section 3.5). |
| `authority`      | A naming authority (typically a domain) recognized as a root or delegated trust anchor.       |
| `publisher`      | A vetted publisher of one or more catalogued resources.                                       |
| `agent`          | An autonomous agent (A2A or otherwise) registered with a registry.                            |
| `mcp_server`     | A Model Context Protocol server.                                                              |
| `ai_tool`        | A generic AI tool catalogued in a registry.                                                   |
| `llm`            | A large language model catalogued in a registry.                                              |
| `skill`          | A reusable agent skill.                                                                       |

**Deprecated aliases.** `a2a_agent` is a legacy alias of `agent` that appears
in older fixtures and examples. It is not a registered type: resolvers SHOULD
treat it as `agent` when encountered, and issuers MUST NOT mint new
identifiers with it.

### 3.3 Identifier normalization

Implementations MUST treat the literal prefix `did:opena2a:` and the `resource-type` slot as case-sensitive lowercase. The `resource-id` slot is case-preserving and MUST NOT be lowercased by the resolver, since some resource identifiers (notably scoped npm package names such as `@modelcontextprotocol/server-filesystem`) are case-significant in their upstream ecosystems.

### 3.4 Registry self-identifier

Each registry deployment names itself with a DID of the form `did:opena2a:registry:<authority>`, where `<authority>` is the DNS name under which the registry publishes its discovery document (Section 8.3). A registry SHALL NOT assign its own self-identifier to any other resource. The self-identifier of the reference deployment is listed in Section 8.4.

### 3.5 Issuing registry

A `did:opena2a` identifier does not itself name the registry that issued it. Two registries could return different documents for one identifier, so a verifier needs a rule for which document to trust.

The rule in this revision is metadata-based. A resolver MUST report the issuing registry's self-identifier (Section 3.4) in the resolution result's `didDocumentMetadata` under the member `issuingRegistry`, and every `assertionMethod` entry in the returned document MUST have that registry as its `controller`. A verifier MUST resolve against the registry it has pinned (Section 6.1) and MUST reject a document whose `issuingRegistry` differs from the pinned registry's self-identifier.

This revision does not define an authority segment inside the identifier. Such a segment would have to be distinguished from the `/` that scoped package identifiers already carry in the `resource-id` slot (`@modelcontextprotocol/server-filesystem`), and that distinction is not settled here.

## 4. Method operations

A registry exposes all four DID method operations (Create, Read, Update, Deactivate) through its HTTP API. This section describes each operation by role; the concrete paths served by the reference deployment are listed in Section 8.4 and may differ for another registry deployment.

### 4.1 Create

A `did:opena2a` DID is created as a side effect of registering a resource with a registry. The registry assigns the DID at registration time using the form `did:opena2a:<resource-type>:<resource-id>` and writes the DID into the registry record.

A subject that will prove possession of its identity registers at least one public key with the registry at creation time. The registry publishes those keys under `authentication` in the subject's DID Document (Section 5.1). A resource that has no key of its own (for example, a catalogued package that is not an active signer) is issued a DID Document with no `authentication` entry.

The registry SHOULD reject a registration whose resulting DID would collide with an existing registered DID. Collision detection is performed by case-sensitive comparison on the `resource-type` and `resource-id` slots after normalization per Section 3.3.

Resources are typically registered by an authenticated publisher submitting metadata through the registry's package or agent registration endpoints, or by the registry's autonomous curation pipeline ingesting from upstream registries (npm, PyPI, Hugging Face, GitHub) and assigning a `did:opena2a:` identifier at admission time.

### 4.2 Read (resolve)

A `did:opena2a` DID is resolved by issuing an HTTP `GET` request to the DID resolution endpoint of a configured registry resolver. The resolution endpoint is advertised in the registry's discovery document (Section 8.3) and in the `DIDResolver` service of the registry's own DID Document (Section 5.3).

The registry replies with a W3C DID Document (Section 5) and the following headers:

```
Content-Type:    application/did+json
Cache-Control:   public, max-age=300
```

`application/did+json` is the one media type of this method; ATP-SPEC Section 3.3 states the same value for its DID resolution operation. When the resolver reports resolution metadata (a deactivation, Section 4.4, or the issuing registry, Section 3.5) it returns a full DID resolution result (`didDocument`, `didResolutionMetadata`, `didDocumentMetadata`) per DID Core Section 7.1.

Implementation status (reference resolver, source read 2026-09-08): the reference deployment replies with `Content-Type: application/did+ld+json`, and its handler test pins that value (`opena2a-registry/internal/interfaces/http/handlers/did_handler_test.go:39-41`). Revision 0.1 of this specification stated `application/did+ld+json`. The media type in this revision follows the family's one value; the resolver change is tracked in the repository's `CHANGELOG.md`.

If the resource named by the DID is not registered, the registry MUST reply `404 Not Found` with a JSON body identifying the missing resource. If the DID does not conform to the syntax in Section 3.1, the registry MUST reply `400 Bad Request` with a JSON body identifying the syntactic defect.

Resolvers MAY cache successful resolutions in accordance with the `Cache-Control` header. Resolvers SHOULD NOT cache 4xx responses.

#### 4.2.1 Multiple registries

More than one registry deployment is the normal case for this method: any registry MAY resolve any well-formed `did:opena2a` DID it has issued, and a registry MAY mirror another registry's records under a federation agreement. The trust model does not change with the number of registries. A verifier trusts the resolved DID Document exactly as much as it trusts the registry it pinned, and it checks the issuing registry from resolution metadata (Section 3.5). The federation contract between registries is out of scope for this specification; see [agent-trust-protocol][atp].

[atp]: https://github.com/opena2a-standards/agent-trust-protocol

### 4.3 Update

A registry treats Update as three distinct operations:

1. **Resource metadata update.** A publisher updates the metadata of a resource they control through an authenticated registry endpoint. The DID itself does not change. The `updated` field of the returned DID Document reflects the time of the most recent metadata update.

2. **Subject key rotation.** The subject (or the publisher acting for it) replaces or adds a key under `authentication` through an authenticated registry endpoint. The DID does not change. A registry SHOULD keep the previous key resolvable for an overlap period so that in-flight proofs of possession verify, and MUST record the rotation in its audit trail.

3. **Registry signing key rotation.** The registry's Ed25519 signing key, which is the `assertionMethod` key for every `did:opena2a` DID it resolves, is rotated through the registry's key management operation. A rotation creates a new key version and an explicit overlap period (the reference deployment uses seven days) during which both the old and new keys are valid for verification. The registry's discovery document (Section 8.3) lists all currently valid signing keys in `publicKeys`.

Verifiers MUST consult the `publicKeys` array from the discovery document (not a single hardcoded key) when verifying a registry assertion about a `did:opena2a` DID. An assertion signature is valid if it verifies against any currently valid registry key.

### 4.4 Deactivate

A registry deactivates a `did:opena2a` DID by transitioning the underlying resource record into a non-active status (`suspended`, `revoked`, or `deprecated`).

After deactivation, resolution of the DID continues to return a DID Document, but the resolution result SHOULD report `deactivated: true` in its DID document metadata (`didDocumentMetadata`), per [DID Core Section 7.1.2][did-core], and the returned document SHOULD NOT advertise active service endpoints. `deactivated` is a property of the resolution metadata, not of the DID Document itself: a resolver that returns a bare DID Document for active DIDs returns a full DID resolution result when it needs to report a deactivation. A separate trust-proof revocation operation is used to revoke previously issued signed trust proofs for the DID; revocations are listed by the registry's revocation endpoint (Section 8.4 for the reference deployment).

#### 4.4.1 Deactivation versus credential revocation

DID deactivation and credential revocation are distinct concerns. Deactivation says: the *subject* of the DID has been retired and is no longer a valid identifier in the registry. Credential revocation (as used by ATX and other consumers) says: a *specific signed assertion about a still-valid subject* has been revoked.

A `did:opena2a` DID MAY be active while specific credentials issued for it are revoked, and a DID MAY be deactivated while previously issued credentials remain technically verifiable (their signatures still cryptographically verify against the registry's historical key versions). Verifiers SHOULD treat a credential whose subject DID is deactivated as untrusted for any new authorization decision.

## 5. DID Document structure

A `did:opena2a` DID Document is a JSON document conforming to [DID Core][did-core]. It carries the subject's own keys under `authentication` and the issuing registry's signing key under `assertionMethod`. The following document is the shape for the agent `did:opena2a:agent:agent_conformance_test_001`, the test subject of the AIP conformance suite; `registry.example` stands for the issuing registry's host:

[did-core]: https://www.w3.org/TR/did-core/

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://w3id.org/security/suites/ed25519-2020/v1"
  ],
  "id": "did:opena2a:agent:agent_conformance_test_001",
  "verificationMethod": [
    {
      "id": "did:opena2a:agent:agent_conformance_test_001#key-1",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:opena2a:agent:agent_conformance_test_001",
      "publicKeyMultibase": "z6MkiaMbhXHNA4eJVCCj8dbzKzTgYDKf6crKgHVHid1F1WCT"
    },
    {
      "id": "did:opena2a:agent:agent_conformance_test_001#registry-key",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:opena2a:registry:registry.example",
      "publicKeyMultibase": "z6Mk<base58btc of 0xed01 || registry Ed25519 public key>"
    }
  ],
  "authentication": [
    "did:opena2a:agent:agent_conformance_test_001#key-1"
  ],
  "assertionMethod": [
    "did:opena2a:agent:agent_conformance_test_001#registry-key"
  ],
  "service": [
    {
      "id": "did:opena2a:agent:agent_conformance_test_001#trust-lookup",
      "type": "TrustLookup",
      "serviceEndpoint": "https://registry.example/api/v1/trust/query?name=agent_conformance_test_001&type=agent"
    },
    {
      "id": "did:opena2a:agent:agent_conformance_test_001#trust-proof",
      "type": "TrustProof",
      "serviceEndpoint": "https://registry.example/api/v1/trust/proof?did=did%3Aopena2a%3Aagent%3Aagent_conformance_test_001"
    },
    {
      "id": "did:opena2a:agent:agent_conformance_test_001#badge",
      "type": "TrustBadge",
      "serviceEndpoint": "https://registry.example/badge/agent/agent_conformance_test_001"
    }
  ],
  "created": "2026-04-12T00:00:00Z",
  "updated": "2026-09-08T00:00:00Z"
}
```

The subject key `#key-1` above is the public key of RFC 8032 Section 7.1 Test 2 (`3d4017c3...660c`), the published test vector the AIP conformance suite binds to this agent DID (`aip-conformance/vectors/agent-bound-key.json`). It is a TEST-ONLY key whose seed is public. The registry key value is a placeholder; a real document carries the issuing registry's current signing key.

### 5.1 `verificationMethod`

Every `did:opena2a` DID Document SHALL contain at least one `verificationMethod` entry. Two kinds of entry are defined:

- **Subject keys.** One or more entries whose `controller` is the subject DID itself. Their ids use the fragment `#key-N`. A subject key is an Ed25519 key published by the subject at registration or rotation (Sections 4.1 and 4.3). The representation of a post-quantum key component is not defined in this revision.
- **Registry key.** Exactly one entry whose `controller` is the issuing registry's self-identifier (Section 3.4). Its id uses the fragment `#registry-key`. Its value is the registry's current Ed25519 signing key.

For an `Ed25519VerificationKey2020` entry, `publicKeyMultibase` is the multibase base58btc encoding (prefix `z`) of the multicodec `ed25519-pub` prefix `0xed01` followed by the 32 raw key bytes, the `z6Mk...` form. Revision 0.1 of this document described the value as a base64 encoding after `z`; that description was wrong. The reference resolver encodes as specified here (`opena2a-registry/internal/application/did_service.go:56-68`, source read 2026-09-08), and the subject key in the example above decodes with an independent multiformats implementation to the `ed25519-pub` codec and the RFC 8032 Test 2 key bytes.

During a registry key rotation overlap period (Section 4.3), the registry's discovery document SHALL advertise all currently valid registry keys. The DID Document itself advertises only the most recently rotated registry key. Verifiers handling potentially historical assertions SHOULD consult the discovery document for the full set of valid keys.

Implementation status (reference resolver, source read 2026-09-08): the reference resolver emits one `verificationMethod` entry, the registry key, and lists it under both `authentication` and `assertionMethod` (`opena2a-registry/internal/application/did_service.go:322-335`). Subject keys are not yet published by the reference resolver; the 0.2 shape is the target it is measured against.

### 5.1.1 Verification relationships

Every `did:opena2a` DID Document SHALL bind each `verificationMethod` entry to a purpose through the DID Core verification relationships [`authentication`][did-core] and [`assertionMethod`][did-core]. A `verificationMethod` entry alone declares that a key exists; the verification relationships declare what the key is *authorized to do*.

- `authentication` lists the subject keys only. A verifier that checks a proof of possession (for example AIP-SPEC Section 5.1.4 rule 2, or the ATX subject-key check) MUST use a key listed under `authentication` and MUST NOT accept the registry key for that purpose.
- `assertionMethod` lists the registry key only. A verifier that checks a registry assertion (a signed trust proof) MUST use a key listed under `assertionMethod`, together with the discovery document's `publicKeys` during rotation (Section 4.3).

Each relationship is expressed as a reference to the full id of the document's own `verificationMethod` entry rather than an embedded key. For the registry self-DID (Section 5.3) the subject and the registry are the same party, so its signing key appears under both relationships.

### 5.2 `service`

A `did:opena2a` DID Document MAY contain one or more `service` entries. The reference implementation produces three:

- **`TrustLookup`**: a `GET` endpoint returning the current trust answer for the named resource.
- **`TrustProof`**: a `GET` endpoint returning a fresh signed trust proof for the DID.
- **`TrustBadge`**: a stable URL for embedding a trust badge SVG.

Service endpoint URLs are relative to the issuing registry's base URL and therefore differ between registry deployments. A resolver MAY add or remove service endpoints over time without bumping this specification, provided the changes are backward-compatible with existing consumers.

### 5.3 The registry DID

The DID Document for a registry's self-identifier (Section 3.4) is a special case. Its `service` array advertises the registry's top-level endpoints (`TrustAPI`, `DIDResolver`, `Federation`) rather than per-resource lookups, and its single `verificationMethod` is the registry's signing key under the fragment `#signing-key`, with the registry itself as controller and listed under both `authentication` and `assertionMethod`. This DID is the trust root for every other `did:opena2a` identifier the same registry issues.

## 6. Security considerations

### 6.1 Trust root

Every registry assertion about a `did:opena2a` DID inherits its trust root from the issuing registry's signing key. Compromise of that key lets the attacker forge trust proofs for every DID the registry has issued and, because the registry publishes the subject keys, lets the attacker substitute a subject key in resolved documents. It does not let the attacker produce a proof of possession under a subject's existing key. The mitigations are the key rotation procedure described in Section 4.3, the rotation overlap window that allows verifiers to migrate without dropping in-flight verifications, and verifier-side pinning of subject keys that a verifier has already seen (a changed subject key is a rotation to confirm, not a fact to accept silently).

Verifiers MUST pin the registry they trust, MUST verify the registry's discovery document over HTTPS, and MUST check the issuing registry from resolution metadata (Section 3.5). Verifiers SHOULD NOT accept a `did:opena2a` DID resolved by an arbitrary network resolver.

### 6.2 Resolver authentication and transport

Resolution endpoints MUST be served over TLS (HTTPS). Registries SHOULD enforce TLS through the `Strict-Transport-Security` header. Resolvers SHOULD reject responses received over plain HTTP and SHOULD reject TLS connections with invalid certificates.

### 6.3 Resource squatting and impersonation

Because the `resource-id` slot is largely user-supplied (it derives from upstream identifiers such as npm package names or domain names), a `did:opena2a` DID is no harder to squat than the upstream identifier itself. Mitigations are upstream of this specification:

- A registry's curation pipeline runs classification and reputation scoring on every newly admitted resource.
- The companion HackMyAgent (HMA) and AgentPwn tooling scan registered resources for typosquatting, governance failures, and adversarial code patterns.
- The conformance suites (ATX, ATP, AIP) provide byte-stable test fixtures that distinguish a legitimate `did:opena2a:` identifier from a fabricated one for the purposes of cross-verification.

### 6.4 Key revocation

A registry signing key revocation is communicated through the discovery document by removing the revoked key from `publicKeys`. Assertions signed by a revoked key SHOULD be treated as untrusted for any new authorization decision. Verifiers SHOULD refresh their copy of the discovery document at least daily.

A subject key revocation is a rotation without a replacement (Section 4.3, item 2): the key disappears from `authentication` and proofs of possession under it SHOULD be treated as untrusted for any new authorization decision.

### 6.5 Forgeability of the DID string itself

A `did:opena2a` string is not, by itself, evidence of anything. Verification requires resolution against a pinned registry and verification of any associated signature against the resolved verification key of the right relationship (Section 5.1.1). Consumers MUST NOT treat a bare DID string in untrusted input as authoritative without performing the full resolve-and-verify procedure.

### 6.6 Availability and centralization risk

Where a registry is a single deployment operated by one party, a sustained denial of service or operational failure of that deployment renders every `did:opena2a` DID it issued temporarily unresolvable. Mitigations:

- The `Cache-Control: public, max-age=300` directive on Read responses permits five minutes of cached resolution per consumer.
- A registry's signed offline bundle of all currently cached trust proofs (Section 7.2) lets a consumer verify without a live resolver.
- Multiple registries and mirrors are the normal case (Section 4.2.1).

This specification does not claim that `did:opena2a` is a fully decentralized DID method.

### 6.7 Trust-model axis

`did:opena2a` is a *registry-mediated* DID method. The broader design axis along which a DID method anchors trust includes at least three points: self-certifying methods (the identifier is the key), ledger-anchored methods (the identifier is bound to a write on a public ledger or append-only log), and registry-mediated methods (the identifier is bound to a record in an operator-run registry that is consulted at resolution time).

Each anchor offers a different operational guarantee. Self-certifying methods minimize the resolution surface (there is nothing to resolve) and place all trust in the key holder. Ledger-anchored methods externalize trust in any one operator at the cost of depending on ledger consensus and any verifier-side log auditor. Registry-mediated methods return a richer resolution payload (trust score, signed proofs, scan history, badge endpoints) at the cost of trusting a specific registry deployment.

Implementations comparing DID methods for agent-identity use cases SHOULD pick the anchor that matches the operational guarantee they need, not the anchor that scores highest on any single axis (decentralization, resolution latency, payload richness, operator independence). A side-by-side comparison of these axes is maintained in this method's [README](https://github.com/opena2a-standards/did-method-opena2a#trust-model). Availability risk specifically for this method is covered in Section 6.6.

## 7. Privacy considerations

### 7.1 Resolution traffic

A `did:opena2a` resolution is a plain HTTPS request to a known registry. The registry observes which DID was requested, the requesting IP address, and the request timing. Consumers concerned about resolution-time privacy MAY use a registry's k-anonymous prefix lookup, which returns all proofs matching a DID prefix and lets the consumer disambiguate locally (Section 8.4 for the reference deployment's endpoint).

### 7.2 Bundle download

A registry's trust bundle endpoint returns the full set of currently cached trust proofs in a single signed payload. A consumer that downloads the bundle once per hour and queries locally exposes no per-DID resolution traffic to the registry.

### 7.3 Personally identifiable information

A `did:opena2a` DID Document SHOULD NOT contain personally identifiable information about the resource owner. A document carries the subject's public keys, the registry's signing key, and service endpoint URLs. Implementations MUST NOT include contact emails, real names, or other personally identifiable contact data in the DID Document.

### 7.4 Correlation across resources

A single publisher may control many `did:opena2a` DIDs (one per registered resource). Correlation across these DIDs is trivial because they share a `resource-id` prefix or appear under the same `publisher` resource type. This is intentional: the OpenA2A trust graph is designed to be publicly auditable. Publishers concerned about correlation MUST NOT register resources whose identifiers they do not wish to be publicly linkable. A subject key is likewise a stable correlator across every place it is presented; a subject that needs unlinkability across relying parties needs a different key per context, which this method does not manage for it.

## 8. Reference implementations

### 8.1 OpenA2A Registry

The reference implementation of the `did:opena2a` method is the OpenA2A Registry at <https://github.com/opena2a-org/opena2a-registry>. The DID-handling code is concentrated in:

- `internal/application/did_service.go`: parsing, multibase encoding, DID Document construction.
- `internal/interfaces/http/handlers/did_handler.go`: HTTP surface for Resolve, well-known, trust proof, revocation.
- `cmd/server/main.go`: route registration.

### 8.2 Conformance suites

Three conformance suites carry `did:opena2a:` identifiers in byte-stable fixtures with reference verifiers:

- **Agent Trust eXtension (ATX):** <https://github.com/opena2a-standards/atx-conformance>
- **Agent Trust Protocol (ATP):** <https://github.com/opena2a-standards/atp-conformance>
- **Agent Identity Protocol (AIP):** <https://github.com/opena2a-standards/aip-conformance>

Each suite publishes test DIDs (`did:opena2a:agent:agent_conformance_test_001`, `did:opena2a:authority:opena2a.org`, and others) in fixtures whose bytes are pinned by a `MANIFEST.sha256`. Reference verifiers exist in Go (full hybrid Ed25519 + ML-DSA-65) and Python (Ed25519; ML-DSA-65 verification is delegated to the Go verifier), and both must reproduce every fixture's pinned expected verdict. The ATX suite additionally pins RFC 8785 (JCS) canonical-bytes agreement across independent Go, Python, and TypeScript canonicalizers. The suites carry identifiers and keys, not DID Documents: no suite pins a resolved `did:opena2a` DID Document as a fixture as of this revision, and the [`examples/`](./examples/) directory of this repository is illustrative, not pinned.

### 8.3 Discovery

A registry exposes a discovery document at the well-known path `/.well-known/opena2a` on its authority host. The document advertises support for this method in its `supportedMethods` array, lists the currently valid registry signing keys in `publicKeys`, and names the DID resolution endpoint. Every registry deployment is expected to expose a comparable discovery document.

### 8.4 Reference deployment (informative)

The reference deployment operated by OpenA2A is reachable at `https://api.oa2a.org`. Its self-identifier is `did:opena2a:registry:opena2a.org`. The concrete surface, as of the source read on 2026-09-08:

- Resolution: `GET https://api.oa2a.org/api/v1/did/<did>`, replying with `Content-Type: application/did+ld+json` (Section 4.2 records the divergence from this revision's media type).
- Discovery: `GET https://api.oa2a.org/.well-known/opena2a`.
- Registry key rotation and revocation: `POST /internal/keys/rotate`, `POST /internal/keys/revoke` (operator-only).
- Trust-proof revocation: `POST /api/v1/trust/revoke`; revocation list: `GET /api/v1/trust/revocations`.
- Offline bundle: `GET /api/v1/trust/bundle`, refreshed hourly.
- k-anonymous prefix lookup: `GET /api/v1/trust/private-lookup?prefix=<10+chars>`.
- Not-found body shape: `{"error": "package not found: <type>/<id>"}`.

Example resolution against the reference deployment:

```
GET https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org
```

The DID Documents under [`examples/`](./examples/) are shaped for this deployment.

## 9. Versioning and change process

Changes to this specification are tracked in the repository's `CHANGELOG.md`. Substantive changes (changes to the ABNF, the registered resource types, the operation surface, the DID Document shape, or the security model) SHALL be accompanied by a version bump and a pull request that requires review by the editors listed in `MAINTAINERS.md` and a 7-day quiet period before merge.

Non-substantive changes (editorial, typographical, link updates) MAY be merged without a quiet period.

## 10. References

- W3C Decentralized Identifiers (DIDs) v1.0: <https://www.w3.org/TR/did-core/>
- W3C DID Extensions registry (method entry `opena2a`, w3c/did-extensions#717): <https://github.com/w3c/did-extensions>
- W3C Patent Policy: <https://www.w3.org/Consortium/Patent-Policy-20040205/>
- RFC 8032, Edwards-Curve Digital Signature Algorithm (EdDSA), Section 7.1 test vectors: <https://datatracker.ietf.org/doc/html/rfc8032#section-7.1>
- OpenA2A Agent Identity Protocol, AIP-SPEC 1.0.2-draft, Section 3.2 (method scoping): <https://github.com/opena2a-standards/agent-identity-protocol>
- OpenA2A Registry source: <https://github.com/opena2a-org/opena2a-registry>
- OpenA2A reference deployment discovery document (live): <https://api.oa2a.org/.well-known/opena2a>
- Agent Trust eXtension (ATX) conformance suite: <https://github.com/opena2a-standards/atx-conformance>
- Agent Trust Protocol (ATP) conformance suite: <https://github.com/opena2a-standards/atp-conformance>
- Agent Identity Protocol (AIP) conformance suite: <https://github.com/opena2a-standards/aip-conformance>
