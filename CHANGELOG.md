# Changelog

All notable changes to the `did:opena2a` method specification will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/) for the specification version.

## [Unreleased]

## [0.2.0] - 2026-09-08

Pairing: this revision is the `did:opena2a` method cited by AIP-SPEC 1.1.0-draft
Section 3.2 and by `draft-fane-opena2a-aip-03` (the Internet-Draft that carries
the AIP method scoping). 0.1.0 was cited by AIP-SPEC 1.0.0-draft and 1.0.1-draft
and by `draft-fane-opena2a-aip-00` through `-02`.

Change process: this revision changes the DID Document shape, so Section 9
applies. The 7-day quiet period starts when the pull request for this revision
opens.

### Changed

- **DID Document shape (Section 5).** The subject's own keys are published under
  `authentication` with the subject as controller (`#key-N`); the issuing
  registry's Ed25519 signing key is published under `assertionMethod` with the
  registry as controller (`#registry-key`). 0.1 listed a single registry key
  under both relationships, so a proof of possession could never be checked
  through resolution. Section 5.1.1 now says which relationship a verifier uses
  for which purpose, and Sections 4.1 and 4.3 add subject key publication and
  subject key rotation. The registry self-DID (Section 5.3) keeps its one key
  under both relationships. Implementation status: the reference resolver still
  emits the 0.1 shape (`opena2a-registry/internal/application/did_service.go:322-335`,
  source read 2026-09-08); the resolver change is open.
- **`publicKeyMultibase` description corrected (Section 5.1).** The value is
  base58btc (multibase prefix `z`) of the multicodec `ed25519-pub` prefix
  `0xed01` followed by the raw key, the `z6Mk...` form. 0.1 described it as a
  base64 encoding after `z`; that was a text error, not a resolver defect: the
  reference resolver already encodes as now specified
  (`did_service.go:56-68`). The Section 5 example carries a real subject key
  (RFC 8032 Section 7.1 Test 2, the AIP conformance suite's bound agent key)
  that an independent multiformats implementation decodes to the
  `ed25519-pub` codec and the published key bytes.
- **Issuing registry (new Section 3.5).** A resolver reports the issuing
  registry's self-identifier in `didDocumentMetadata.issuingRegistry`, every
  `assertionMethod` entry has that registry as controller, and a verifier
  rejects a document whose issuing registry differs from the registry it
  pinned. This method does not define an authority segment: the identifier
  names the resource and the issuing registry is provenance reported in
  metadata, so provenance can change without renaming the subject; a segment
  would also collide with the `/` that scoped package identifiers already
  carry in `resource-id`.
- **Media type (Section 4.2).** Unchanged from 0.1: `application/did+ld+json`,
  the JSON-LD document type, which the reference resolver emits and its
  handler test pins (`did_handler_test.go:39-41`). Section 4.2 now states why
  (the served document carries `@context`).
- **Roles, not brands, in normative text (Sections 3.2, 3.4, 4, 6, 7, 8).**
  "One canonical registry" became "the registry that issued the DID"; a registry
  names itself `did:opena2a:registry:<authority>`; concrete `api.oa2a.org`
  paths, the not-found body shape, the internal key rotation and revocation
  endpoints, the bundle, revocation and k-anonymous lookup paths, and the
  hosting platform name moved out of the normative sections into the new
  informative Section 8.4 "Reference deployment". Multiple registries are
  described as the normal case (Section 4.2.1, formerly "Federation").
- **Trust root (Section 6.1)** restated for the two-key model: compromise of
  the registry key forges assertions and can substitute a published subject
  key, but cannot produce a proof of possession under an existing subject key;
  verifiers pin subject keys they have seen. Section 6.4 adds subject key
  revocation; Section 7.4 notes that a subject key is a stable correlator.
- **Status paragraph** reflects the merged W3C registration and states the
  scope split with the Agent Identity Protocol: `did:opena2a` is the
  ecosystem-scoped method used at the ATP and ATX layer; an AIP identity
  provider issues and resolves its own provider-scoped identifiers (a
  `did:web` profile) and does not serve `did:opena2a`.
- **Section 8.2** no longer says the conformance suites exercise the
  `examples/` documents: no suite pins a resolved DID Document as a fixture
  (measured across `atx-conformance`, `atp-conformance`, `aip-conformance` on
  2026-09-08). The examples are illustrative and were regenerated in the 0.2
  shape; `examples/agent.json` carries the RFC 8032 Test 2 subject key.
- Headings in sentence case; em dashes removed from running text.
- Section 3.2 upgraded from "currently registered resource types" (labelled
  non-normative) to the **shared resource-type registry** for the OpenA2A
  spec family: ATX Sections 2 and 14, ATP-SPEC Section 3.1, and AIP examples
  defer here; additions by PR against this repository, mirrored into consumers.
  The registration-governs-issuance / resolvers-must-not-reject rule is
  retained.
- `a2a_agent` moved from an in-table synonym note to an explicit
  **Deprecated aliases** rule: resolvers SHOULD treat it as `agent`; issuers
  MUST NOT mint new identifiers with it. This is the family's one existing
  deprecation precedent and is unchanged in 0.2. Companion cleanups: atx-spec#7
  (prefix set in Sections 2 and 14, `registry` added there) and
  agent-trust-protocol#6 (example tokens).

### Added

- One home per shared definition, marked for the family drift gate: Sections
  3.1 and 3.1.1 are the home of the `did:opena2a` string form, stating that
  signed artifacts carry exactly one form (the unescaped form) and that
  verifiers compare after the Section 3.3 normalization and never normalize
  before signature verification; Section 3.2's table is the shared
  resource-type registry, from which `registries/resource-types.json` is
  generated by `scripts/gen_registries.py` and checked in CI (`registries`
  workflow).
- README: "Trust model" section comparing self-certifying, ledger-anchored,
  and registry-mediated DID methods so implementers can choose deliberately.
- Spec Section 6.7 Trust-model axis: short cross-reference to the README
  comparison; classifies `did:opena2a` as registry-mediated alongside
  Section 6.6.
- Section 10: references to the W3C DID Extensions registry entry, RFC 8032
  Section 7.1, and AIP-SPEC Section 3.2.

### Fixed

- README and spec Section 8.2 overstated the reference-verifier coverage
  ("Go, Rust, TypeScript, and Python ... byte-identical across all four").
  Corrected to the actual set: Go (full hybrid Ed25519 + ML-DSA-65) and Python
  (Ed25519, ML-DSA-65 delegated to Go), with fixture bytes pinned by each
  suite's `MANIFEST.sha256` and JCS canonical-bytes agreement pinned across
  Go/Python/TypeScript in `atx-conformance/jcs-vectors/`.
- README and spec Section 8.2 mis-expanded ATX as "Agent Trust
  Cross-Verification"; the correct expansion is "Agent Trust eXtension".
- README status said "Provisional, pending W3C DID Method Registry review"
  while the spec said registered; both now say registered (merged 2026-07-04).

### Not in this revision

- A third-party parse fixture for `publicKeyMultibase` and the DID string
  form fixture pair are specified (Sections 3.1.1 and 5.1) but no fixture is
  added to a conformance suite by this revision.
- The representation of a post-quantum subject key component.
- The resolver changes (0.2 shape, media type) in `opena2a-registry`.

## [0.1.0] - 2026-05-28

### Added

- Initial draft specification of the `did:opena2a` DID method.
- ABNF syntax for `did:opena2a:<resource-type>:<resource-id>[#fragment]`.
- Non-normative enumeration of currently-recognized resource types: `registry`, `authority`, `publisher`, `agent`, `mcp_server`, `ai_tool`, `llm`, `skill`.
- Documentation of all four method operations (Create, Read, Update, Deactivate) as backed by the OpenA2A Registry HTTP API.
- Security and privacy considerations, including honest discussion of the registry-mediated trust model and centralization risk.
- Reference implementation links to `opena2a-org/opena2a-registry` and the three conformance suites (ATX, ATP, AIP).
- DID Document examples for each registered resource type.
