# Status

- **Version:** 0.3 (draft)
- **Status:** Registered in the W3C DID Extensions registry (did-extensions #717, merged 2026-07-04)
- **License:** Apache License, Version 2.0 (see [`LICENSE`](../LICENSE))

Revision 0.2 changes the DID Document shape (subject keys under `authentication`, registry key under `assertionMethod`), corrects the `publicKeyMultibase` description to base58btc with the multicodec prefix, adds the issuing-registry rule, and keeps the resolution media type at `application/did+ld+json` (the served document is JSON-LD). The reference resolver still emits the 0.1 document shape; the spec's implementation status notes and [`CHANGELOG.md`](../CHANGELOG.md) record what is open.

Revision 0.3 requires a resolved DID Document's `id` to equal the requested DID in its canonical form (Section 3.1.2), and a `404` for a DID the registry has not registered rather than another document (Sections 4.2, 6.1 and 6.5). The reference deployment still answers every `did:opena2a:registry:<authority>` DID with its own registry DID Document (measured 2026-10-11).

## Resolution

The registry replies with a DID Document, `Content-Type: application/did+ld+json`, and a 5-minute cache header (spec Section 4.2; the reference deployment replies with that media type as of 2026-09-08).
