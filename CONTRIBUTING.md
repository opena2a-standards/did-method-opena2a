# Contributing

Editorial corrections, clarifications, and link fixes are welcome via pull request. Substantive changes (changes to the ABNF, the operation surface, the DID Document shape, or the security model) require a version bump, editor review, and a 7-day quiet period per Section 9 of the spec.

`python3 scripts/check_did_syntax.py` checks every `did:opena2a` string in the repository's Markdown and JSON files against the Section 3.1 grammar and the Section 3.1.2 decoding step; run it after changing either, or after adding an example DID. It also fails when a percent-encoded `did:opena2a` string is spelled out anywhere other than Section 3.1.1 of the spec, the one place the family spec-drift check `did-example-forms` excludes; elsewhere, refer to that section instead of writing the encoded form.

This specification is licensed under [Apache-2.0](./LICENSE). By contributing, you agree your contributions are likewise licensed under Apache-2.0. The W3C registry entry that cites this specification is governed separately by the [W3C Patent Policy][w3c-pp] and [Document License][w3c-dl].

[w3c-pp]: https://www.w3.org/Consortium/Patent-Policy-20040205/
[w3c-dl]: https://www.w3.org/Consortium/Legal/copyright-documents
