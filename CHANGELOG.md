# Changelog

All notable changes to the `did:opena2a` method specification will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/) for the specification version.

## [Unreleased]

### Added

- **Public reference resolver (new Section 8.6, informative).** The registry
  source stays private, and `scripts/reference_resolver.py` is a resolver
  whose source a public reader can open, written from the specification
  rather than taken from that source: DID parsing (Sections 3.1, 3.1.2 and
  3.3), the Ed25519 `publicKeyMultibase` encoding (Section 5.1), DID Document
  construction for a resource and for the registry (Sections 5 and 5.3), and
  HTTP handlers for resolution (Sections 3.5, 4.2 and 4.4) and discovery
  (Section 8.3). It reads a registry and its records from a JSON file and
  answers `GET` and `HEAD` on `/api/v1/did/<did>`; `resolve` prints one reply
  and `serve` answers HTTP on `127.0.0.1`. `serve` takes a `--port` from 0
  to 65535 and a `--host` that is an IPv4 address; it closes a connection
  when a read or a write on it waits longer than 10 seconds, so a client
  that connects and sends nothing, or stops partway through its request,
  holds a server thread for 10 seconds rather than for as long as it stays
  connected. It refuses a `--host` that is not an IPv4 address, such as an
  empty one, which the socket module reads as every interface, or a name,
  and exits 2 after one line naming the address and the reason when it
  cannot listen there; a `--host` holding a character other than visible
  ASCII, such as U+200E or a newline, appears in that line as Python's
  `ascii()` of it. python3 standard library only.
  `scripts/test_reference_resolver.py` compares its parser with the grammar
  compiled from Section 3.1 on `did:opena2a:` followed by every string of up
  to five characters over a nine-character alphabet, on each ASCII character
  in the resource-type, the resource-id and the fragment, and on each
  percent-encoded octet; it
  compares the documents it builds with the Section 5 example and
  `examples/`, and its replies with the checks of `scripts/check_vectors.py`.
  The Abstract, Sections 8.1 and 10 and the README point to it. The Status
  of this document section, Section 5.1, the README, `docs/status.md` and
  `docs/use-cases.md` now name "the reference deployment's resolver" where
  they said "the reference resolver", which meant that resolver.
- **Resolution vectors (new Section 8.5, informative).** `vectors/` holds two
  resolution vectors for the resolved-`id` check of Section 6.5: the
  `did:opena2a:registry:evil.test` substitution measured against the reference
  deployment, which a verifier rejects, and its positive control.
  `scripts/check_vectors.py` applies the issuing-registry check of Section 3.5
  and the Section 6.5 check, comparing the resolved `id` with the canonical
  form of the requested DID (Section 3.1.2), and fails when a verdict differs
  from the vector's expected verdict. `scripts/check_did_syntax.py` also reads
  `vectors/`, so a percent-encoded DID there fails locally as it fails the
  family spec-drift check `did-example-forms`.
- **README sample output.** Each of the three shell commands in the README is
  followed by what it printed, as whole lines with `...` standing for lines
  left out, and so are `python3 scripts/check_examples.py --live` and
  `python3 scripts/check_vectors.py`, which the README names in prose. The
  resolution commands pass `-s`; the two use-case commands pipe the reply
  through `jq .`, and the Resolution command passes `-i` to print the response
  headers. `scripts/capture_readme.py` re-runs these commands and writes each
  full output to `docs/captures/<name>.txt`, with a `.json` sidecar recording
  the command, its exit code, the UTC time it ran and the SHA-256 of the
  output. `scripts/test_readme.py` fails when a shell command in the README has
  no output under it, when an excerpt is not whole lines of its capture in
  their order, or when a sidecar records another command, another SHA-256 or a
  non-zero exit code.
- **`python3 scripts/check_examples.py --live` resolves the percent-encoded
  form.** A served example DID whose `resource-id` holds `/` or `@` (the `llm`
  and `mcp_server` examples) is also resolved in the percent-encoded
  serialization of Section 3.1.1, and the run exits 1 unless that request is
  answered `200` with the document the unescaped form resolves to (Sections
  3.1.2 and 4.2). Against the reference deployment it exits 0.
  `docs/examples.md` states the check.
- **`python3 scripts/check_examples.py --live` compares keys.** Each resolved
  document's verification method ids, types and controllers, a JSON Web Key's
  `kty` and `alg`, its `authentication` and `assertionMethod` lists and its
  `@context` must match the layout the Implementation status notes of
  Sections 5.1 and 5.3 record for the reference deployment, and each Ed25519
  key the registry controls must carry the value of the registry document's
  `#signing-key`; the run exits 1 otherwise. Before, `--live` compared `id`
  and `service` only, and exited 0 against a registry document carrying one
  key or a resource document whose `#registry-key` was another key. Against
  the reference deployment it exits 0. `docs/examples.md` states that the
  resolved registry document carries three verification methods where its
  example carries one.
- **`python3 scripts/check_examples.py --live` compares the not-found body.**
  `did:opena2a:agent:agent_conformance_test_001` must answer `404` with the
  body Section 8.4 records,
  `{"error":"resource not found: agent/agent_conformance_test_001"}`; the run
  exits 1 otherwise. Against the reference deployment it exits 0.

### Changed

- **README shortened.** The README keeps the specification link, the use
  cases with their limits, resolution, examples and conformance, and links
  the rest. Its reference text moved, as written: the Trust model section to
  `docs/trust-model.md`, the Status section to `docs/status.md`, the
  Contributing section to `CONTRIBUTING.md`, the full use cases with each
  conformance suite's fixture count to `docs/use-cases.md`, and the full
  notes on each example to `docs/examples.md`. The References list joined a
  new Documentation list. Section 6.7 links `docs/trust-model.md` for the
  side-by-side comparison of trust anchors. The README header states the
  registration and the method's scope without the merge date or the AIP
  revision, which the specification's Status of this document section
  carries, and the sentence on what a resolved DID Document carries opens the
  Resolution section. `scripts/test_readme.py` fails when a README line holds
  a three-part version such as 1.2.0 or a date written as 2026-07-04, or a
  README paragraph runs over 60 words.
- **README shorter.** The Use cases section left the README; its text is in
  `docs/use-cases.md`, and its two resolution commands with their sample
  output joined the Resolution section, followed by one sentence on where the
  reference resolver stops. The Conformance section's suite list and signature
  coverage moved, as written, to the new `docs/conformance.md`. The notes on
  each example stay in `docs/examples.md`, and the sentence on the reply's
  media type and cache header in `docs/status.md`. The Documentation list
  holds 9 entries.

### Fixed

- **Discovery request on the authority host (Section 8.4).** The Discovery
  bullet now gives `GET https://opena2a.org/.well-known/opena2a`, on the host
  the self-identifier `did:opena2a:registry:opena2a.org` names (Sections 3.4
  and 8.3). Measured 2026-10-21 (UTC), it answers `307` with `Location:
  https://api.oa2a.org/.well-known/opena2a`, which serves the discovery
  document with `"did:opena2a"` in `supportedMethods`. (#22)

- **Registry DIDs other than the self-identifier, re-measured (Sections 4.2
  and 8.4).** On 2026-10-21 (UTC) the reference deployment answered
  `did:opena2a:registry:evil.test`, `did:opena2a:registry:example.com` and
  `did:opena2a:registry:api.oa2a.org` with `404` and a body naming the
  requested resource, such as
  `{"error":"resource not found: registry/evil.test"}`; on 2026-10-11 it
  answered them with `200` and its own registry DID Document. The
  implementation status note of Section 4.2, the Status of this document
  paragraph, the README, `docs/status.md` and `docs/use-cases.md` said the
  deployment answers every `did:opena2a:registry:<authority>` DID with that
  document. All but the README now give the 2026-10-21 measurement, and the
  Section 4.2 note keeps the 2026-10-11 substitution that the negative
  resolution vector records; the README drops the claim from where the
  reference resolver stops. Section 4.2 and Section 8.4 give the body for the
  unregistered `agent` DID `did:opena2a:agent:agent_conformance_test_001`,
  `{"error":"resource not found: agent/agent_conformance_test_001"}`, in
  place of `{"error":"package not found: registry package not found"}`.
  `python3 scripts/check_examples.py --live` also resolves the six registry
  DIDs the Section 4.2 note lists and exits 1 when one answers other than
  `404`.
- **`scripts/test_readme.py` reads code blocks as `scripts/check_links.py`
  does.** The word-limit test flipped its fenced-code state at any line that
  starts with three backticks or three tildes, so after a backtick fence
  holding a `~~~` line, or a four-backtick fence holding a three-backtick
  line, the prose below the block was read as code, and a 61-word paragraph
  there passed the 60-word limit. An indented code block was read as prose,
  so 61 words of indented code failed it. A fence now closes only at a run of
  the character that opened it at least as long as the opening run, and a
  line indented four or more columns that does not continue a paragraph is
  skipped as indented code. The sample-output checks close a fence by the
  same rule. `scripts/check_links.py` gains `code_blocks`, which also returns
  the lines of indented code blocks; the link targets it reads in the README
  and the specification are unchanged.
- **ATX fixture count in `docs/use-cases.md`.** The use cases gave
  `atx-conformance` as 23 fixtures; its `MANIFEST.sha256` on `main` lists 25,
  and each of the 25 carries a `did:opena2a` identifier.
- **`examples/registry.json` lists the Federation endpoint the deployment
  serves.** The reference deployment's registry DID Document lists the
  `Federation` service at `https://api.oa2a.org/api/v1/federation/proposals`;
  the example listed `https://api.oa2a.org/api/v1/federation/sync`, so
  `python3 scripts/check_examples.py --live` exited 1 with
  `examples/registry.json: service endpoints differ from the live document`.
  The example now carries the served URL, and the run exits 0.
- **`scripts/check_did_syntax.py` reads every Markdown and JSON file.** It read
  the README, the specification, the CHANGELOG and `examples/*.json` (9 files),
  while the family spec-drift check `did-example-forms` reads every Markdown and
  JSON file in the repository, so a `did:opena2a` string in
  `examples/conformance/`, `registries/` or `MAINTAINERS.md` could turn that
  check red unnoticed. It now reads every `.md` and `.json` file outside hidden
  directories (13 files). `CONTRIBUTING.md` and Section 3.1.2 now also say
  that it fails when a percent-encoded `did:opena2a` string is spelled out
  anywhere other than Section 3.1.1.
- **`scripts/check_examples.py --live` on a network error.** A DNS failure,
  refused connection or timeout is reported as a problem for each DID, with
  exit 1, instead of ending the run with a traceback.
- **`scripts/check_links.py` checks bare URLs.** A bare `https://` URL in prose,
  which GitHub renders as a link, is now followed like the other link forms.
- **`scripts/check_links.py` reads a long line in linear time.** A long run of
  `[`, `[a](`, `](` or `<https://` with no closing bracket made a link pattern
  retry from every position: a line of 40,000 `[` took 0.52 s and a line of
  40,000 `[a](` took 49 s, fourfold per doubling. Link text no longer holds a
  `[`, an autolink no longer holds a `<`, and an inline link target holds
  parentheses only in balanced pairs, as in CommonMark, limited here to one
  level of nesting. The one-level limit and link text without a `[` are this
  script's simplifications: CommonMark allows deeper nesting and matched
  brackets in link text. The targets read from the README and the spec are
  unchanged.
- **`scripts/check_links.py` ends a bare URL at whitespace or `<` only**, as
  GitHub and its docstring do; a `>` no longer ends it.
- **`scripts/check_links.py` ends a URL in an HTML attribute at the closing
  quote.** Once a `>` no longer ended a bare URL, the rest of an HTML tag was
  read into a URL held in an attribute:
  `<a href="https://example.org/x">text</a>` gave the target
  `https://example.org/x">text`. A URL that opens a quoted attribute value now
  runs to the quote that closes the value, whitespace and `<` included. Its
  character references are decoded with `html.unescape`, so
  `<a href="https://example.org/?a=1&amp;b=2">` gives
  `https://example.org/?a=1&b=2`, except that a named reference without its
  `;` is kept as written when `=` or an ASCII letter or digit follows it, as a
  browser keeps it in an attribute value: `?q=x&section=2` stays as written
  and is not read as `?q=x§ion=2`. Leading and trailing whitespace is dropped
  and tabs and newlines are removed, as a browser does. A space, control or
  non-ASCII character after the host is percent-encoded in the request, as a
  browser does; a control or non-ASCII character in a bare URL ended the run
  with a traceback before. The README and the spec hold no such tag, so the
  targets read from them are unchanged.
- **`scripts/check_links.py` reads more attribute and link targets as a reader
  follows them.** An attribute value that opens with whitespace, as in
  `<a href=" https://example.org/x">text</a>` or with `&#32;` before the
  scheme, gave the target `https://example.org/x">text`; the whitespace is now
  dropped, as the module docstring said. A value that continues onto the next
  line was cut at the line break; it now runs to its closing quote, up to a
  blank line, with the line break removed, when the value is in a start tag
  and that quote is followed by whitespace, `/>` or `>`. A start tag is a
  `<`, a tag name and whitespace or `/`, then an attribute part that a `>`
  closes, with no other `<` or `>` in it outside a quoted attribute value; one
  in a code span, autolink or inline link counts. So
  `<a title=">" href="https://example.org/a` followed by `b">` on the next
  line gives `https://example.org/ab`, as a browser reads it. Otherwise the
  value's URL is read as a bare URL, at the line its scheme is on, as before,
  so an unclosed `x="https://example.org/a` in prose, or one after a `<` and
  a word that no `>` closes, does not take the opening quote of `"hi"`, or
  the quote in `a 12" ruler`, on the next line as its own, and `x="` followed
  by `https://example.org/a b" c` on the next line gives
  `https://example.org/a` at that line. The line
  break at the end of the last line before a blank line, a fenced code block
  or the end of the file does not count as that whitespace, so a quote that
  ends that line does not close a value whose URL starts on an earlier line.
  The character references in an inline link or reference definition target
  are decoded as CommonMark decodes them, so
  `[a](https://example.org/?a=1&amp;b=2)` gives
  `https://example.org/?a=1&b=2`. A URL that is percent-encoded for the request
  keeps an empty query or fragment, so `https://example.org/a b?` is requested
  as `https://example.org/a%20b?`. A decimal character reference of more than
  4,300 digits in an attribute value, and a target with a space in its host,
  ended the run with a traceback; the first is now read by its value, as a
  browser reads it, which is U+FFFD above U+10FFFF, and the second is reported
  as a broken link. The README and the spec hold no such target, so the
  targets read from them are unchanged.
- **`scripts/check_links.py` reads a code fence only when it is indented by at
  most three spaces.** A `` ``` `` or `~~~` line indented by four or more
  spaces, or by a tab, was read as a code fence, so the lines below it were
  skipped up to the next such line: a `https://example.org/a` on the line
  after it, which GitHub renders as a link, was not checked. A fence now holds
  at most three spaces of indentation, so a line indented further neither
  opens nor closes one, and the headings below it get their anchors. The
  README and the spec hold no such line, so the targets read from them are
  unchanged.
- **`scripts/check_links.py` closes a fenced code block at a matching fence
  and reads one in a block quote.** A fence was any line that started with
  three backticks or tildes after at most three spaces, and the next such line
  closed it. A closing fence is now a run of the same character at least as
  long, with only spaces or tabs after it, so `~~~` no longer closes a block
  that `~~~~` opened. A run of backticks with a backtick after it on its line
  opens no block, so a line holding the code span `` ``` a ``` `` no longer
  hides the lines after it. A fence after block quote markers opens a block,
  with its three spaces of indentation counted from after those markers, and
  the block also closes where the block quote ends: a URL in such a block was
  followed. Headings in a fenced code block are read by the same rule. A code
  span now ends a bare URL before it, as on GitHub. The targets and headings
  read from the README and the spec are unchanged.
- **`scripts/check_links.py` counts a fence's indentation from the content of
  its list item.** Counted from the start of the line, a closing fence
  indented four spaces under `1. a` was not read as one, so the block stayed
  open and every line below it was skipped: a link there was not checked, and
  a link to a heading there was reported as `no heading with anchor`. A block
  fenced at four or more spaces in a list item, as under `- step`, and a block
  fenced after a list item marker on its line were read as prose, so a URL in
  them was checked as a link. A fence's zero to three spaces of indentation
  are now counted from the content of the list item it is in, as in
  CommonMark, and a fenced code block that is still open where its list item
  ends is closed there. A list item ends at the first line that is not blank,
  is indented less than the item's content and does not continue the item's
  paragraph, and an item with nothing after its marker also ends at a blank
  line right below the marker. Block quotes and list items are read inside each other as
  CommonMark reads them, and a line that continues a paragraph keeps open each
  block quote and list item that paragraph is in. HTML blocks are not
  followed, which is this script's simplification: a line that starts with `<`
  is read as a line of a paragraph. A line indented to the content of 100,000
  nested list items took 2.65 s to read, fourfold per doubling, because the
  run of spaces was scanned again for each item; it is now scanned once, and
  the line is read in 0.08 s. The README and the spec hold no fence in a
  list item, and the targets and anchors read from them are unchanged.
- **`scripts/check_links.py` reads a `===` line below link reference
  definitions as a line of their paragraph.** A line of `=` or `-` right below
  a paragraph line was read as a setext heading underline even when that
  paragraph held only link reference definitions, where CommonMark reads no
  heading and a `===` line continues the paragraph. Below `[a]: /u` and
  `===`, a `` 2. ``` `` line was then read as a list item that opens a fenced
  code block, and `https://example.org/x` on the line below it was not
  checked; CommonMark reads both lines as more of the paragraph, as `2.` cannot
  interrupt one. Below a paragraph of definitions, each on a line of its own,
  a line of `=`, such as `===`, and the line `--` now continue the paragraph,
  and a `---` line is still read as a thematic break. A definition written
  across lines is not read as one there, which is this script's
  simplification. The targets, anchors and fenced code block lines read from
  the README and the spec are unchanged.
- **`scripts/check_links.py` reports a relative target outside the
  repository.** A target such as `../outside.md` passed when a file of that
  name was there, next to the clone; a target whose resolved path is outside
  the repository is now reported, as the module docstring said.
- **`scripts/check_links.py` on a connection closed before a reply or a reply
  that is not HTTP.** urllib does not wrap the `http.client.RemoteDisconnected`
  and `http.client.BadStatusLine` it raises while reading a response, so either
  ended the run with a traceback, before any link was reported. The request is
  now retried once, as a failed request is, and the URL is then reported as
  broken, as in `request failed: BadStatusLine: garbage`, with the other links'
  results and exit 1.
- **`scripts/check_links.py` escapes control characters in a reported error
  and cuts it at 200 characters.** A reply whose status line is not HTTP was
  reported with that line as the server sent it, so an escape sequence in it,
  such as ESC `[31m`, reached the terminal or CI log, and a status line of
  65,000 characters was copied in full. In the error text of a request that
  failed or of a URL that cannot be requested, each run of whitespace is one
  space, each other control or format character is written as its Python
  escape, as in `request failed: BadStatusLine: \x1b[31mred`, and a text
  longer than 200 characters is cut to 200 or fewer and ends in `...`.
- **`scripts/check_links.py` skips indented code blocks and reads a code span
  across the lines of its paragraph.** A URL in an indented code block, as on
  a line of four spaces and `curl https://example.org/x`, was checked as a
  link, though CommonMark renders that line as code; the lines of indented
  code blocks, which `code_blocks` returned, are now skipped as the lines of
  fenced ones are. A code span was read one line at a time, so a span opened
  on one line and closed on the next, after `https://example.org/x`, gave the
  target `https://example.org/x` with the closing backtick at its end. A code
  span is now read as CommonMark reads one: a run of backticks opens one that
  the next run of as many backticks in the same paragraph closes, across its
  lines, in a block quote or a list item too. A run with no such run after it
  is text, and a backtick escaped with a backslash opens none; before, a run
  of any length closed a span, and an escaped backtick opened one. The
  targets read from the README and the spec are unchanged.
- **`scripts/check_examples.py --live` on a body that is not JSON.** A `200`
  answer whose body is not a JSON object, such as an HTML error page, is
  reported as a problem for that DID, with exit 1, instead of ending the run
  with a traceback.
- **`scripts/check_did_syntax.py --help` prints usage.** The script ran the
  check whatever arguments it was given; `--help` now prints the usage, and an
  unknown argument exits 2 without running the check.
- **`scripts/check_vectors.py --help` prints usage.** The script read no
  arguments, so `--help` ran the check and an unknown argument was accepted;
  `--help` now prints the usage, and an unknown argument exits 2 without
  running the check.
- **`scripts/check_vectors.py` on a vector whose `resolutionResult`,
  `didDocument` or `didDocumentMetadata` is not an object.** A
  `resolutionResult` that is not a JSON object, and a `didDocument` or
  `didDocumentMetadata` that is present and neither an object nor `null`, is
  reported as a malformed vector, with exit 1. Before, in a vector whose
  requested DID and expected verdict were well formed: a `resolutionResult`
  that was not an object ended the run with a traceback; a `didDocument` or
  `didDocumentMetadata` that was an empty array or string, zero or `false`
  read as empty and gave a reject verdict, so a vector that expected that
  reject passed, where it now fails as malformed; and any other value of
  either member that was neither an object nor `null` ended the run with a
  traceback, unless it was a `didDocument` and the issuing-registry check had
  already rejected the vector. A `didDocument` or `didDocumentMetadata` that
  is absent or `null` still reads as empty.
- **`scripts/check_vectors.py` runs under `python3 -P` and
  `PYTHONSAFEPATH=1`.** It imports `scripts/check_did_syntax.py` and relied on
  Python putting the script directory on `sys.path`, so it stopped with
  `ModuleNotFoundError` when Python was told to leave that directory out. It
  now adds the directory itself.
- **CHANGELOG 0.3.0.** The percent-encoding and `scripts/check_did_syntax.py`
  entries moved from [Unreleased] to 0.3.0, the revision whose header and
  Section 3.1 carry the ABNF change, and the spec's status section names the
  change. The 0.3.0 change-process paragraph said the quiet period would start
  when the pull request opened; it now records when the revision's pull
  requests opened and merged.
- **Section 4.4** cites DID Core Section 7.1.3 (DID Document Metadata) for
  `deactivated`; it cited 7.1.2, which is DID Resolution Metadata.
- **Section 3.2** no longer says a registry MAY reply `404` for a resource it
  has no record of; it points to the Section 4.2 rule, under which `404` is the
  one conforming reply.
- **Section 8.4** records the not-found body the reference deployment returns,
  `{"error":"resource not found: <type>/<id>"}` with the requested resource
  type and id (measured 2026-10-21 UTC), in place of the
  `package not found: <type>/<id>` shape revision 0.3 recorded. The body
  identifies the missing resource, as Section 4.2 requires, and the Section
  4.2 implementation status note no longer says it does not. On 2026-10-12
  the deployment answered an unregistered `agent` DID with
  `{"error":"package not found: registry package not found"}`.
- **Requests that name `a2a_agent` (Sections 3.1.2, 3.2, 4.2 and 6.5).**
  Section 3.2 says resolvers SHOULD treat the alias as `agent`, but the alias
  holds a digit, which the Section 3.1 `resource-type` rule does not admit,
  and no section said which `id` a request naming it is answered with.
  Section 3.2 now says that treating it as `agent` means reading the request
  as the `agent` DID with the same `resource-id` before it is parsed and
  decoded: the registry answers with the canonical form of that DID as `id`,
  and the resolved-`id` checks of Sections 4.2 and 6.5 compare the returned
  `id` with it. A resolver that does not treat the alias as `agent` answers
  `400`. `scripts/check_vectors.py` reads such a request the same way;
  before, it stopped on one with `requested DID does not parse or decode`.
  Implementation status (measured 2026-10-21 UTC for three registered
  agents): the reference deployment answers a request naming the alias with
  a document whose `id` keeps the alias.
- **Section 5.1** says revision 0.2 corrected the `publicKeyMultibase`
  description; "this revision" read as a 0.3 change.
- **Status paragraph and Section 10** cite AIP-SPEC 1.2.0-draft Section 3.2 and
  `draft-fane-opena2a-aip-04`; the Section 3.2 text is unchanged from
  1.1.0-draft.
- **README.** The "resolve the reference registry's own DID" use case says that
  every `did:opena2a:registry:<authority>` DID currently resolves to that same
  document, and that a verifier rejects that answer with the Section 6.5 check.
- **Section 4.2 implementation status note, re-measured 2026-10-21.** The
  reference deployment resolves the percent-encoded serialization of Section
  3.1.1 to the same DID Document as the unescaped form: both requests are
  answered `200`, the two response bodies are the same bytes, and the `id` is
  the canonical form. The note said the encoded form was answered `404`, as
  measured on 2026-10-11. It now also records that the encoded form written
  with a lowercase hexadecimal digit is answered with the same bytes, and that
  the encoded form written with `%25` in place of each `%`, a `resource-id`
  that does not decode under Section 3.1.2, is answered `400`. Section 8.6
  now matches: the public reference resolver's resolution of the
  percent-encoded form to the same DID Document is no longer listed among the
  rules the reference deployment does not yet follow, and stands with the
  behaviour the Section 4.2 notes record the deployment showing.
- **The commit that added the README use cases (`fe26e40`, #9) describes a
  removal its diff does not contain.** Its message says it removed the word
  "signed" from "returns a signed DID Document", but its diff adds 32 lines to
  `README.md` and removes none, and no version of `README.md` on `main` has
  carried that phrase. (#10)
- **Agents catalogued under `a2a_agent` (Section 3.2).** Section 3.2 now
  records, as measured on 2026-10-21 (UTC), that the reference deployment
  catalogues agents under the deprecated alias `a2a_agent`: its package
  listing reports `1194` records of that type and `0` of type `agent`. The
  resolved `agent` DID Documents of the agents `a2a-server`, `a2a-settlement`
  and `a2a-spec` use the alias in two service URLs: `type=a2a_agent` in the
  `TrustLookup` endpoint and `/badge/a2a_agent/` in the `TrustBadge`
  endpoint. (#25)

## [0.3.0] - 2026-10-11

Change process: this revision changes the ABNF (Sections 3.1 and 3.1.2) and the
security model (Sections 4.2, 6.1 and 6.5), so Section 9 applies: a version
bump, review by the editors and a 7-day quiet period before merge. The security
model change merged in pull request #30 and the ABNF change in pull request #32;
each opened and merged on 2026-10-12 (UTC), so neither had the quiet period.
The revision remains a draft.

### Security

- **Resolved `id` must be the requested DID (Sections 4.2, 6.1, 6.5).** A
  registry replies with a document whose `id` equals the requested DID, or with
  `404`; it never answers an unregistered DID with another document, its own
  registry DID Document included. A verifier rejects a resolution whose `id`
  differs from the DID it requested; the issuing-registry check does not catch
  that substitution. Section 9 applies: this entry changes the security model,
  so the revision that carries it is a version bump with the 7-day quiet period.
  Implementation status (measured 2026-10-11): the reference deployment answers
  every `did:opena2a:registry:<authority>` DID, `registry:evil.test` included,
  with `200` and its own registry DID Document; an unregistered `agent` DID
  returns `404` with a body that does not identify the missing resource; the
  resolver change is open.

### Changed

- **Percent-encoded `resource-id` (Sections 3.1 and 3.1.2).** The `resource-id`
  production admits `pct-encoded` triplets, so the strict DID Core
  serialization that Section 3.1.1 calls equivalent
  (`did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem` with the
  `resource-id` encoded as `%40modelcontextprotocol%2Fserver-filesystem`) now
  parses; it was the only DID string in the README, specification, CHANGELOG
  and examples that did not. New Section 3.1.2 defines the decoding step: the
  `resource-id` is decoded exactly once, a triplet that decodes to a character
  outside `unreserved` and `:` makes the DID invalid, a resolver decodes before
  lookup, and identifiers are compared and collisions checked in the decoded
  canonical form. Sections 3.1.1, 3.3, 4.1 and 4.2 refer to the step.
  Sections 4.2, 6.1 and 6.5 compare the returned `id` with the canonical form
  of the requested DID, so the canonical `id` that a percent-encoded request
  resolves to passes the verifier check; a request in canonical form, the form
  every signed artifact carries, compares byte for byte as before. The encoded
  serialization is spelled out only in Section 3.1.1, which the family
  spec-drift check `did-example-forms` excludes; Section 4.2 and this entry
  refer to it. Implementation status: the reference resolver returns `404` for
  the encoded form as of 2026-10-11 (Section 4.2); the resolver change is
  open.

### Added

- `scripts/check_did_syntax.py` compiles the Section 3.1 ABNF from the
  specification, checks every `did:opena2a` string in the README,
  specification, CHANGELOG and examples against it, checks that a
  percent-encoded `did:opena2a` string is spelled out only in Section 3.1.1 of
  the specification, and checks the Section 3.1.2 decoding step against
  encoded and invalid vectors. python3 standard library only.

### Fixed

- **Section 2 (editorial).** The prefix sentence now says the prefix is
  lowercase and points to Section 3.3, which holds the one rule: the prefix is
  case-sensitive lowercase. It previously said the prefix "is normalized to
  lowercase", which contradicted Section 3.3 and the reference resolver, which
  rejects `did:OPENA2A:...` with `400` rather than lowercasing it.
- **Section 4.2 implementation note.** The cited command is now a `GET` that
  prints only the response headers; the reference resolver answers `HEAD` with
  `405`, so the previous `curl -sI` command did not show the media type.
- **Section 5.3 implementation note.** Records how the reference deployment's
  registry DID Document differs from the section and from
  `examples/registry.json`: three verification methods (two Ed25519 entries for
  one key and an ML-DSA-65 `JsonWebKey`), all three under `assertionMethod`, the
  JWK context, and `created` and `updated` set to the request time.
- **Section 3.2 implementation note.** Records that the reference resolver
  answers a DID with a well-formed but unregistered `resource-type` (`widget`)
  with `400` instead of the `404` that Sections 3.2 and 4.2 call for. It also
  records that `400` is correct for a `resource-type` outside the ABNF
  (`agent9`, which contains a digit). The resolver change in `opena2a-registry`
  is open.
- **Section 4.4 implementation note.** Records that the reference resolver does
  not yet report deactivation: a `suspended` or `deprecated` resource resolves
  as an active one, with the bare DID Document, no `didDocumentMetadata` and
  all three services, and the trust proof for the deprecated record carries the
  verdict `listed`. Of the first 100 `a2a_agent` records, 1 is `suspended` and
  9 are `deprecated`. The resolver change in `opena2a-registry` is open.
- **README.** The closing paragraph of the use cases is headed "What you can
  check yourself" and counts only the AIP fixtures that carry a `did:opena2a`
  identifier (4 of 7).
- **Examples match the reference deployment.** `examples/` holds one DID
  Document per resource type the deployment serves (`agent`, `mcp_server`,
  `ai_tool`, `llm`, `skill`) plus the registry self-DID. Each one names a DID
  that resolves and carries the `service` endpoints the deployment returns.
  `ai_tool.json`, `llm.json` and `skill.json` are new. `agent.json` now names
  a catalogued agent. The `mcp_server.json` badge path leaves `@` unescaped,
  as the live document does. `registry.json` uses the `z6Mk...` placeholder in
  place of the 0.1 base64 placeholder. The AIP conformance agent, with its
  subject key, and `authority:opena2a.org` both answer `404` at the
  deployment, so they moved to `examples/conformance/`. The new
  `scripts/check_examples.py` checks the file set, the 0.2 shape and the URL
  encoding, and `--live` resolves each DID.
- **Sections 6.6, 7.1 and 7.2: offline bundle and prefix lookup.** The bundle
  and the k-anonymous lookup cover only the DIDs whose proofs the registry
  holds, so the text no longer says that the bundle lets a consumer verify any
  DID offline, that the lookup returns all proofs under a prefix, or that an
  hourly download hides all per-DID traffic. Section 7.2 names the two
  properties these depend on (coverage of the registry's active resources and
  a signature over the whole bundle) and states that a bundle built from
  on-request proofs discloses recent lookups. Section 8.4 records the reference
  deployment's measured bundle and lookup.
- **Registry generator help.** `scripts/gen_registries.py --help` described the
  output as `registries/<id>.json`, but the file name comes from the table's
  entry in the script, not from the marker id. The help now says
  `registries/<file>.json` and lists each generated file beside its marker id
  (`registries/resource-types.json` for `did-resource-types`).
- **README and spec Section 8.2 verifier coverage.** One sentence described
  every suite's verifiers as Go with full hybrid Ed25519 + ML-DSA-65 and
  Python with Ed25519 only, ML-DSA-65 delegated to Go; the 0.2.0 entry below
  repeats it. That holds for ATP only. Both now state the coverage per suite:
  ATX verifies ML-DSA-65 in both Go and Python, ATP verifies it in Go and
  records it as present in Python, and AIP verifies Ed25519 only in both
  because no AIP fixture carries an ML-DSA-65 signature.
- **Reference implementation links (README, Abstract, Sections 8.1 and 10).**
  The README and the spec no longer link to `opena2a-org/opena2a-registry`,
  which answers `404` to an anonymous reader. Section 8.1 states that the
  registry source is private, that the citations into it can be checked only
  with access, and that a public reader checks the reference deployment
  (Section 8.4) and the conformance suites (Section 8.2). The README's registry
  link points to spec Section 8 and its references list the live discovery
  document. `scripts/check_links.py` checks every link in the README and the
  spec: relative targets and heading anchors offline, absolute targets with an
  anonymous request.

## [0.2.0] - 2026-09-08

Pairing: this revision is the `did:opena2a` method cited by AIP-SPEC 1.1.0-draft
Section 3.2 and by `draft-fane-opena2a-aip-03` (the Internet-Draft that carries
the AIP method scoping). 0.1.0 was cited by AIP-SPEC 1.0.0-draft and 1.0.1-draft
and by `draft-fane-opena2a-aip-00` through `-02`.

Change process: this revision changes the DID Document shape, so Section 9
applies. The 7-day quiet period started on 2026-09-09, the day the pull request
for this revision opened; the earliest merge date is 2026-09-16.

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
  (`did_service.go:56-68`; private source; a live `publicKeyMultibase` begins
  `z6Mk`). The Section 5 example carries a real subject key
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
- The resolver changes (the 0.2 document shape and `issuingRegistry` metadata) in `opena2a-registry`.

## [0.1.0] - 2026-05-28

### Added

- Initial draft specification of the `did:opena2a` DID method.
- ABNF syntax for `did:opena2a:<resource-type>:<resource-id>[#fragment]`.
- Non-normative enumeration of currently-recognized resource types: `registry`, `authority`, `publisher`, `agent`, `mcp_server`, `ai_tool`, `llm`, `skill`.
- Documentation of all four method operations (Create, Read, Update, Deactivate) as backed by the OpenA2A Registry HTTP API.
- Security and privacy considerations, including honest discussion of the registry-mediated trust model and centralization risk.
- Reference implementation links to `opena2a-org/opena2a-registry` and the three conformance suites (ATX, ATP, AIP).
- DID Document examples for each registered resource type.
