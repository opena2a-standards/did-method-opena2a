# Trust model

`did:opena2a` is a **registry-mediated** DID method. Resolution is performed by HTTP against an OpenA2A Registry; a registry's assertions about a DID are signed with the registry's Ed25519 key, proofs of possession are checked against the subject's own published key, and the trust a verifier places in a `did:opena2a` DID is exactly the trust the verifier places in the registry it has pinned.

This is one design point on a broader axis that implementers comparing agent-identity options should be aware of:

| Anchor                                 | Resolution surface                          | Trust assumption                                              | Key rotation                                                |
| -------------------------------------- | ------------------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------- |
| Self-certifying (e.g. `did:key`, `did:peer`) | None; the identifier IS the key             | The key holder                                                | Identifier changes when key changes                          |
| Ledger-anchored (e.g. distributed ledgers, append-only logs) | Public ledger or log read                    | The ledger's consensus and any verifier-side log auditor       | Per-method (revocation registries, rotation operations)      |
| **Registry-mediated (`did:opena2a`)**  | **HTTP `GET` against an OpenA2A Registry**  | **The pinned registry (one or several)**                      | **Registry-side rotation with an overlap window; subject keys rotate through the registry** |

Each anchor solves a different operational problem. Self-certifying methods give you portable identifiers with no resolution dependency. Ledger-anchored methods give you a write surface that is independent of any one operator. Registry-mediated methods give you a resolution surface that returns more than a key (trust score, signed proofs, scan history, badge endpoints) at the cost of trusting a specific operator.

The choice is deliberate. `did:opena2a` exists because the OpenA2A Registry was already the place where agent reputation, attestation, and supply-chain context lived, and a DID method gave verifiers a single, byte-stable way to ask a registry "what do you know about this resource?" If you do not need a registry's resolution payload, you do not need this method.

For the security-considerations view of the same axis (availability risk, key rotation, transport authentication), see Sections 6.6 and 6.7 of [`did-method-opena2a.md`](../did-method-opena2a.md).
