# The `did:opena2a` DID Method Specification

**Version:** 0.1 (draft)
**Status:** Registered in the W3C DID Extensions registry (did-extensions #717, merged 2026-07-04)
**License:** Apache License, Version 2.0
**Editor:** Abdel Sy Fane (OpenA2A, <abdelsyfane@gmail.com>)
**Repository:** <https://github.com/opena2a-standards/did-method-opena2a>

---

## Abstract

This specification defines the `did:opena2a` Decentralized Identifier method. A `did:opena2a` identifier names a resource (an agent, an MCP server, an authority, a publisher, an AI tool, an LLM, a skill, or the registry itself) that is registered in an OpenA2A Registry. Resolution returns a W3C DID Document whose `verificationMethod` is the OpenA2A Registry's Ed25519 signing key and whose `service` endpoints expose trust lookup, signed trust proofs, and trust badges for the named resource.

The method is implemented in production by the OpenA2A Registry (`opena2a-org/opena2a-registry`) and exercised by three independent conformance suites that publish byte-stable test vectors:

- Agent Trust eXtension (ATX)
- Agent Trust Protocol (ATP)
- Agent Identity Protocol (AIP)

This document specifies the method's syntax, operations, resolution behaviour, and security and privacy considerations. It is intended to support submission to the [W3C DID Method Registry][did-spec-registries].

[did-spec-registries]: https://github.com/w3c/did-spec-registries

## Status of This Document

This is the initial draft of the `did:opena2a` method specification, prepared to accompany a registration entry in the W3C DID method registry. The registration entry is published in the W3C DID Extensions registry ([w3c/did-extensions#717](https://github.com/w3c/did-extensions/pull/717), merged 2026-07-04). The method itself has been in production use since OpenA2A Registry migration 102 (Ed25519 trust proofs) and is currently advertised by the registry's `/.well-known/opena2a` discovery document under `supportedMethods: ["did:opena2a"]`.

Substantive changes to this document are tracked in the repository's `CHANGELOG.md`.

## Table of Contents

1. [Introduction](#1-introduction)
2. [Method Name](#2-method-name)
3. [Method-Specific Identifier](#3-method-specific-identifier)
4. [Method Operations](#4-method-operations)
5. [DID Document Structure](#5-did-document-structure)
6. [Security Considerations](#6-security-considerations)
7. [Privacy Considerations](#7-privacy-considerations)
8. [Reference Implementations](#8-reference-implementations)
9. [Versioning and Change Process](#9-versioning-and-change-process)
10. [References](#10-references)

## 1. Introduction

OpenA2A is an open ecosystem for agent-to-agent trust. Its core component, the OpenA2A Registry, catalogues software resources that participate in agent-to-agent and human-to-agent interactions: MCP servers, AI tools, LLMs, skills, autonomous agents, the publishers and authorities that vouch for them, and the registry itself. Each catalogued resource is assigned a DID of the form `did:opena2a:<type>:<id>`.

A `did:opena2a` DID is bound to a specific resource type and a specific identifier within that type. Resolving the DID returns a W3C DID Document whose verification material is the Registry's Ed25519 signing key. Verifying any signature attributed to a `did:opena2a` subject is therefore an act of verifying a signature attributed to the OpenA2A Registry that issued the DID. The trust model is explicit: a verifier trusts a `did:opena2a` DID exactly as much as it trusts the Registry resolver it was configured with.

This trust model is acknowledged honestly throughout this specification. The `did:opena2a` method is not a fully decentralized identifier method in the sense of `did:peer` or `did:key`. It is a registry-mediated method that derives its utility from the auditable, public nature of the OpenA2A Registry and the byte-stable interoperability surface defined by the three OpenA2A conformance suites.

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

## 2. Method Name

The method name that shall identify this DID method is: `opena2a`.

A DID that uses this method MUST begin with the following literal prefix: `did:opena2a:`. The prefix is normalized to lowercase. All bytes are US-ASCII.

## 3. Method-Specific Identifier

### 3.1 Syntax (ABNF)

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

The `resource-type` is intentionally an open ABNF rule. New resource types are expected to be added to the OpenA2A Registry over time without requiring revisions to this specification.

### 3.2 Resource type registry

This section is the **shared resource-type registry** for the OpenA2A
specification family: ATX (core.md §2/§14), ATP-SPEC (§3.1), and AIP-SPEC
example identifiers all defer to this table for the set of registered
`resource-type` values. Additions are made by pull request against this
repository (the same change policy the ATX §14 registry table records) and
are mirrored into the consuming specifications.

Registration governs *issuance*, not *resolution*: implementations MUST NOT
reject a DID solely because the `resource-type` slot contains an unregistered
value that otherwise conforms to the ABNF in §3.1. Implementations MAY return
a 404 Not Found if the Registry has no record of the named resource.

| Resource type    | Description                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------------- |
| `registry`       | An OpenA2A Registry instance itself. There is one canonical registry: `did:opena2a:registry:opena2a.org`. |
| `authority`      | A naming authority (typically a domain) recognized as a root or delegated trust anchor.       |
| `publisher`      | A vetted publisher of one or more catalogued resources.                                       |
| `agent`          | An autonomous agent (A2A or otherwise) registered with the Registry.                          |
| `mcp_server`     | A Model Context Protocol server.                                                              |
| `ai_tool`        | A generic AI tool catalogued in the Registry.                                                 |
| `llm`            | A large language model catalogued in the Registry.                                            |
| `skill`          | A reusable agent skill.                                                                       |

**Deprecated aliases.** `a2a_agent` is a legacy alias of `agent` that appears
in older fixtures and examples. It is not a registered type: resolvers SHOULD
treat it as `agent` when encountered, and issuers MUST NOT mint new
identifiers with it.

### 3.3 Identifier normalization

Implementations MUST treat the literal prefix `did:opena2a:` and the `resource-type` slot as case-sensitive lowercase. The `resource-id` slot is case-preserving and MUST NOT be lowercased by the resolver, since some resource identifiers (notably scoped npm package names such as `@modelcontextprotocol/server-filesystem`) are case-significant in their upstream ecosystems.

### 3.4 Reserved identifier

The identifier `did:opena2a:registry:opena2a.org` is reserved for the canonical OpenA2A Registry and SHALL NOT be assigned to any other resource.

## 4. Method Operations

The OpenA2A Registry exposes all four DID method operations (Create, Read, Update, Deactivate) as HTTP API endpoints. The exact URL paths below are the ones served by the reference implementation in `opena2a-org/opena2a-registry` and may differ for a federated registry deployment.

### 4.1 Create

A `did:opena2a` DID is created as a side effect of registering a resource with the OpenA2A Registry. The Registry assigns the DID at registration time using the form `did:opena2a:<resource-type>:<resource-id>` and writes the DID into the registry record.

The Registry SHOULD reject a registration whose resulting DID would collide with an existing registered DID. Collision detection is performed by case-sensitive comparison on the `resource-type` and `resource-id` slots after normalization per §3.3.

Resources are typically registered by an authenticated publisher submitting metadata through the Registry's package or agent registration endpoints, or by the Registry's autonomous curation pipeline ingesting from upstream registries (npm, PyPI, Hugging Face, GitHub) and assigning a `did:opena2a:` identifier at admission time.

### 4.2 Read (Resolve)

A `did:opena2a` DID is resolved by issuing an HTTP `GET` request to the path `/api/v1/did/<did>` on a configured OpenA2A Registry resolver. The reference implementation is:

```
GET https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org
```

The Registry replies with a W3C DID Document (see §5) and the following headers:

```
Content-Type:    application/did+ld+json
Cache-Control:   public, max-age=300
```

If the resource named by the DID is not registered, the Registry MUST reply `404 Not Found` with a JSON body of the form `{"error": "package not found: <type>/<id>"}`. If the DID does not conform to the syntax in §3.1, the Registry MUST reply `400 Bad Request` with a JSON body identifying the syntactic defect.

Resolvers MAY cache successful resolutions in accordance with the `Cache-Control` header. Resolvers SHOULD NOT cache 4xx responses.

#### 4.2.1 Federation

The `did:opena2a` method permits federation: more than one OpenA2A Registry deployment MAY exist, and each deployment MAY resolve any well-formed `did:opena2a` DID. The trust model under federation is the same as the single-registry case: a verifier trusts the resolved DID Document exactly as much as it trusts the Registry resolver it was configured with. Federation between registries is out of scope for this specification; see [agent-trust-protocol][atp] for the in-progress federation contract.

[atp]: https://github.com/opena2a-standards/agent-trust-protocol

### 4.3 Update

The OpenA2A Registry treats Update as two distinct operations:

1. **Resource metadata update.** A publisher updates the metadata of a resource they control through an authenticated Registry endpoint. The DID itself does not change. The `updated` field of the returned DID Document reflects the time of the most recent metadata update.

2. **Signing key rotation.** The Registry's Ed25519 signing key — which is the controller key for every `did:opena2a` DID it resolves — is rotated through the internal endpoint `POST /internal/keys/rotate`. A rotation creates a new key version and an explicit overlap period (default seven days) during which both the old and new keys are valid for verification. The Registry's `/.well-known/opena2a` discovery document lists all currently-valid signing keys in `publicKeys`.

Verifiers MUST consult the `publicKeys` array from `/.well-known/opena2a` (not a single hardcoded key) when verifying signatures against a `did:opena2a` DID. A signature is valid if it verifies against any currently-valid key.

### 4.4 Deactivate

The OpenA2A Registry deactivates a `did:opena2a` DID by transitioning the underlying resource record into a non-active status (`suspended`, `revoked`, or `deprecated`).

After deactivation, resolution of the DID continues to return a DID Document, but the document SHOULD include a `deactivated: true` property at the document root and SHOULD NOT advertise active service endpoints. A separate trust-proof revocation endpoint (`POST /api/v1/trust/revoke`) is used to revoke previously-issued signed trust proofs for the DID; revocations are listed at `GET /api/v1/trust/revocations`.

#### 4.4.1 Deactivation vs. credential revocation

DID Deactivation and credential revocation are distinct concerns. Deactivation says: the *subject* of the DID has been retired and is no longer a valid identifier in the Registry. Credential revocation (as used by ATX and other consumers) says: a *specific signed assertion about a still-valid subject* has been revoked.

A `did:opena2a` DID MAY be active while specific credentials issued for it are revoked, and a DID MAY be deactivated while previously-issued credentials remain technically verifiable (their signatures still cryptographically verify against the Registry's historical key versions). Verifiers SHOULD treat a credential whose subject DID is deactivated as untrusted for any new authorization decision.

## 5. DID Document Structure

A `did:opena2a` DID Document is a JSON-LD document conforming to [DID Core][did-core]. The reference implementation produces documents of the following shape (excerpted from `opena2a-registry/internal/application/did_service.go`):

[did-core]: https://www.w3.org/TR/did-core/

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://w3id.org/security/suites/ed25519-2020/v1"
  ],
  "id": "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem",
  "verificationMethod": [
    {
      "id": "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem#registry-key",
      "type": "Ed25519VerificationKey2020",
      "controller": "did:opena2a:registry:opena2a.org",
      "publicKeyMultibase": "z<base64-encoded Ed25519 public key>"
    }
  ],
  "service": [
    {
      "id": "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem#trust-lookup",
      "type": "TrustLookup",
      "serviceEndpoint": "https://api.oa2a.org/api/v1/trust/query?name=%40modelcontextprotocol%2Fserver-filesystem&type=mcp_server"
    },
    {
      "id": "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem#trust-proof",
      "type": "TrustProof",
      "serviceEndpoint": "https://api.oa2a.org/api/v1/trust/proof?did=did%3Aopena2a%3Amcp_server%3A%40modelcontextprotocol%2Fserver-filesystem"
    },
    {
      "id": "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem#badge",
      "type": "TrustBadge",
      "serviceEndpoint": "https://api.oa2a.org/badge/mcp_server/%40modelcontextprotocol%2Fserver-filesystem"
    }
  ],
  "created": "2026-02-15T19:24:01Z",
  "updated": "2026-05-14T08:11:33Z"
}
```

### 5.1 `verificationMethod`

Every `did:opena2a` DID Document SHALL contain at least one `verificationMethod` entry. The reference implementation uses a single `Ed25519VerificationKey2020` entry whose `controller` is the Registry DID (`did:opena2a:registry:opena2a.org`) and whose `publicKeyMultibase` value is the Registry's current Ed25519 signing key encoded with the multibase `z` prefix.

During a key-rotation overlap period (§4.3), the Registry's `/.well-known/opena2a` discovery document SHALL advertise all currently-valid keys. The DID Document itself currently advertises only the most recently-rotated key. Verifiers handling potentially historical signatures SHOULD consult `/.well-known/opena2a` for the full set of valid keys.

### 5.2 `service`

A `did:opena2a` DID Document MAY contain one or more `service` entries. The reference implementation produces three:

- **`TrustLookup`** — a `GET` endpoint returning the current trust answer for the named resource.
- **`TrustProof`** — a `GET` endpoint returning a fresh signed trust proof for the DID.
- **`TrustBadge`** — a stable URL for embedding a trust badge SVG.

A resolver MAY add or remove service endpoints over time without bumping this specification, provided the changes are backward-compatible with existing consumers.

### 5.3 The registry DID

The DID Document for `did:opena2a:registry:opena2a.org` is a special case. Its `service` array advertises the Registry's top-level endpoints (`TrustAPI`, `DIDResolver`, `Federation`) rather than per-resource lookups, and its `verificationMethod` is the Registry's signing key under the controller `did:opena2a:registry:opena2a.org` (i.e., self-controlled). This DID is the trust root for every other `did:opena2a` identifier resolved by the same Registry.

## 6. Security Considerations

### 6.1 Trust root

Every `did:opena2a` DID resolved by a given Registry inherits its trust root from that Registry's signing key. Compromise of the signing key compromises every DID the Registry has issued. The mitigation is the key-rotation procedure described in §4.3 and the rotation-overlap window that allows verifiers to migrate without dropping in-flight verifications.

Verifiers MUST pin the Registry resolver they trust and MUST verify the Registry's discovery document over HTTPS. Verifiers SHOULD NOT accept a `did:opena2a` DID resolved by an arbitrary network resolver.

### 6.2 Resolver authentication and transport

Resolution endpoints MUST be served over TLS (HTTPS). The reference Registry is configured to enforce TLS via the `Strict-Transport-Security` header. Resolvers SHOULD reject responses received over plain HTTP and SHOULD reject TLS connections with invalid certificates.

### 6.3 Resource squatting and impersonation

Because the `resource-id` slot is largely user-supplied (it derives from upstream identifiers such as npm package names or domain names), a `did:opena2a` DID is no harder to squat than the upstream identifier itself. Mitigations are upstream of this specification:

- The OpenA2A Registry's curation pipeline runs heuristic classification and reputation scoring on every newly-admitted resource.
- The companion HackMyAgent (HMA) and AgentPwn tooling scan registered resources for typosquatting, governance failures, and adversarial code patterns.
- The three conformance suites (ATX, ATP, AIP) provide byte-stable test fixtures that distinguish a legitimate `did:opena2a:` identifier from a fabricated one for the purposes of cross-verification.

### 6.4 Key revocation

A signing-key revocation (`POST /internal/keys/revoke`) is communicated via the discovery document by removing the revoked key from `publicKeys`. Signatures issued by a revoked key SHOULD be treated as untrusted for any new authorization decision. Verifiers SHOULD refresh their copy of `/.well-known/opena2a` at least daily.

### 6.5 Forgeability of the DID string itself

A `did:opena2a` string is not, by itself, evidence of anything. Verification requires resolution against a trusted Registry and verification of any associated signature against the resolved verification key. Consumers MUST NOT treat a bare DID string in untrusted input as authoritative without performing the full resolve-and-verify procedure.

### 6.6 Centralization risk

Because the reference Registry is a single Azure Container Apps deployment, a sustained denial-of-service or operational failure of that deployment renders every `did:opena2a` DID temporarily unresolvable. Mitigations:

- The `Cache-Control: public, max-age=300` directive on `Read` responses permits five minutes of cached resolution per consumer.
- The `GET /api/v1/trust/bundle` endpoint offers a signed offline bundle of all currently-cached trust proofs, refreshed hourly.
- Federation (§4.2.1) is an in-progress contract that permits additional Registry deployments to resolve the same method.

This specification does not claim that `did:opena2a` is a fully decentralized DID method.

### 6.7 Trust-model axis

`did:opena2a` is a *registry-mediated* DID method. The broader design axis along which a DID method anchors trust includes at least three points: self-certifying methods (the identifier is the key), ledger-anchored methods (the identifier is bound to a write on a public ledger or append-only log), and registry-mediated methods (the identifier is bound to a record in an operator-run registry that is consulted at resolution time).

Each anchor offers a different operational guarantee. Self-certifying methods minimize the resolution surface (there is nothing to resolve) and place all trust in the key holder. Ledger-anchored methods externalize trust in any one operator at the cost of depending on ledger consensus and any verifier-side log auditor. Registry-mediated methods return a richer resolution payload (trust score, signed proofs, scan history, badge endpoints) at the cost of trusting a specific Registry deployment.

Implementations comparing DID methods for agent-identity use cases SHOULD pick the anchor that matches the operational guarantee they need, not the anchor that scores highest on any single axis (decentralization, resolution latency, payload richness, operator independence). A side-by-side comparison of these axes is maintained in this method's [README](https://github.com/opena2a-standards/did-method-opena2a#trust-model). Centralization risk specifically for this method is covered in §6.6.

## 7. Privacy Considerations

### 7.1 Resolution traffic

A `did:opena2a` resolution is a plain HTTPS request to a known Registry. The Registry observes which DID was requested, the requesting IP address, and the request timing. Consumers concerned about resolution-time privacy MAY use the k-anonymous `GET /api/v1/trust/private-lookup?prefix=<10+chars>` endpoint, which returns all proofs matching a DID prefix and lets the consumer disambiguate locally.

### 7.2 Bundle download

The `GET /api/v1/trust/bundle` endpoint returns the full set of currently-cached trust proofs in a single signed payload. A consumer that downloads the bundle once per hour and queries locally exposes no per-DID resolution traffic to the Registry.

### 7.3 Personally identifiable information

A `did:opena2a` DID Document SHOULD NOT contain personally identifiable information about the resource owner. The reference implementation produces only the Registry's signing key and service endpoint URLs. Implementations MUST NOT include contact emails, real names, or other personally identifiable contact data in the DID Document.

### 7.4 Correlation across resources

A single publisher may control many `did:opena2a` DIDs (one per registered resource). Correlation across these DIDs is trivial because they share a `resource-id` prefix or appear under the same `publisher` resource type. This is intentional: the OpenA2A trust graph is designed to be publicly auditable. Publishers concerned about correlation MUST NOT register resources whose identifiers they do not wish to be publicly linkable.

## 8. Reference Implementations

### 8.1 OpenA2A Registry

The canonical reference implementation of the `did:opena2a` method is the OpenA2A Registry at <https://github.com/opena2a-org/opena2a-registry>. The DID-handling code is concentrated in:

- `internal/application/did_service.go` — parsing, DID Document construction.
- `internal/interfaces/http/handlers/did_handler.go` — HTTP surface for Resolve, well-known, trust proof, revocation.
- `cmd/server/main.go` (route registration) — `GET /api/v1/did/*`, `GET /.well-known/opena2a`, `POST /internal/keys/rotate`, `POST /internal/keys/revoke`.

### 8.2 Conformance suites

Three independent conformance suites exercise `did:opena2a:` identifiers with byte-stable fixtures and reference verifiers:

- **Agent Trust eXtension (ATX):** <https://github.com/opena2a-standards/atx-conformance>
- **Agent Trust Protocol (ATP):** <https://github.com/opena2a-standards/atp-conformance>
- **Agent Identity Protocol (AIP):** <https://github.com/opena2a-standards/aip-conformance>

Each suite publishes test DIDs (`did:opena2a:agent:agent_conformance_test_001`, `did:opena2a:authority:opena2a.org`, etc.) in fixtures whose bytes are pinned by a `MANIFEST.sha256`. Reference verifiers exist in Go (full hybrid Ed25519 + ML-DSA-65) and Python (Ed25519; ML-DSA-65 verification is delegated to the Go verifier), and both must reproduce every fixture's pinned expected verdict. The ATX suite additionally pins RFC 8785 (JCS) canonical-bytes agreement across independent Go, Python, and TypeScript canonicalizers.

### 8.3 Discovery

The reference Registry exposes a discovery document at <https://api.oa2a.org/.well-known/opena2a> that advertises support for this method in its `supportedMethods` array. Federated Registries are encouraged to expose a comparable discovery document.

## 9. Versioning and Change Process

Changes to this specification are tracked in the repository's `CHANGELOG.md`. Substantive changes (changes to the ABNF, the registered resource types, the operation surface, the DID Document shape, or the security model) SHALL be accompanied by a version bump and a pull request that requires review by the editors listed in `MAINTAINERS.md` and a 7-day quiet period before merge.

Non-substantive changes (editorial, typographical, link updates) MAY be merged without a quiet period.

## 10. References

- W3C Decentralized Identifiers (DIDs) v1.0: <https://www.w3.org/TR/did-core/>
- W3C DID Method Registry: <https://github.com/w3c/did-spec-registries>
- W3C Patent Policy: <https://www.w3.org/Consortium/Patent-Policy-20040205/>
- OpenA2A Registry source: <https://github.com/opena2a-org/opena2a-registry>
- OpenA2A discovery document (live): <https://api.oa2a.org/.well-known/opena2a>
- Agent Trust eXtension (ATX) conformance suite: <https://github.com/opena2a-standards/atx-conformance>
- Agent Trust Protocol (ATP) conformance suite: <https://github.com/opena2a-standards/atp-conformance>
- Agent Identity Protocol (AIP) conformance suite: <https://github.com/opena2a-standards/aip-conformance>
