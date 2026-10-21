#!/usr/bin/env python3
"""Tests for reference_resolver.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import base64
import contextlib
import io
import itertools
import json
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import check_did_syntax
import check_vectors
import reference_resolver as rr

REPO = SCRIPTS.parent
EXAMPLES = REPO / "examples"

AGENT = "did:opena2a:agent:agent_conformance_test_001"
MCP = "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem"
# The Section 3.1.1 serialization of MCP, and the same string percent-encoded
# once more, as a client writes it into a URL path.
MCP_ENCODED = "did:opena2a:mcp_server:%40modelcontextprotocol%2Fserver-filesystem"
MCP_ENCODED_IN_URL = "did:opena2a:mcp_server:%2540modelcontextprotocol%252Fserver-filesystem"
DEPRECATED = "did:opena2a:agent:a2a-spec"
REGISTRY = "did:opena2a:registry:registry.example"


def example(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


# The subject key of examples/conformance/agent.json: the RFC 8032 Section 7.1
# Test 2 public key, a TEST-ONLY key whose seed is public (spec Section 5).
SUBJECT_KEY = example("conformance/agent.json")["verificationMethod"][0]["publicKeyMultibase"]
# Stand-in registry keys, the current one and an older one still valid:
# 32 bytes counting up from 0, and from 32.
REGISTRY_KEY = rr.ed25519_multibase(bytes(range(32)))
OLDER_REGISTRY_KEY = rr.ed25519_multibase(bytes(range(32, 64)))


def records(**members) -> dict:
    data = {
        "authority": "registry.example",
        "baseUrl": "https://registry.example",
        "signingKeys": [REGISTRY_KEY, OLDER_REGISTRY_KEY],
        "created": "2026-02-15T00:00:00Z",
        "updated": "2026-09-08T00:00:00Z",
        "resources": [
            {"did": AGENT, "subjectKeys": [SUBJECT_KEY], "status": "active",
             "created": "2026-04-12T00:00:00Z", "updated": "2026-09-08T00:00:00Z"},
            {"did": MCP, "created": "2026-02-20T00:00:00Z", "updated": "2026-09-08T00:00:00Z"},
            {"did": DEPRECATED, "status": "deprecated",
             "created": "2026-03-01T00:00:00Z", "updated": "2026-09-08T00:00:00Z"},
        ],
    }
    data.update(members)
    return data


def registry(**members) -> rr.Registry:
    return rr.Registry.from_json(records(**members))


def get(reg: rr.Registry, target: str, method: str = "GET") -> tuple:
    status, headers, body = reg.respond(method, target)
    return status, dict(headers), json.loads(body)


def section_5_example() -> dict:
    """The DID Document under Section 5 of the specification."""
    lines = check_did_syntax.SPEC.read_text(encoding="utf-8").splitlines()
    start = lines.index("## 5. DID Document structure")
    opening = lines.index("```json", start)
    return json.loads("\n".join(lines[opening + 1:lines.index("```", opening + 1)]))


def with_registry_key(doc: dict, controller: str) -> dict:
    """`doc` with each key `controller` controls set to REGISTRY_KEY, for the placeholder the examples carry."""
    for method in doc["verificationMethod"]:
        if method["controller"] == controller:
            method["publicKeyMultibase"] = REGISTRY_KEY
    return doc


class ParsesAsTheGrammarCompiledFromTheSpec(unittest.TestCase):
    """parse_did() accepts exactly what the Section 3.1 ABNF and the Section 3.1.2 step accept.

    check_did_syntax.py compiles the ABNF from the specification, so these
    tests fail when the parser and the grammar as written disagree on a
    string, or on its canonical form.
    """

    @classmethod
    def setUpClass(cls):
        cls.did_rx, cls.rid_rx = check_vectors.grammar()

    def disagreements(self, texts) -> list:
        found = []
        for text in texts:
            spec = check_did_syntax.canonical_form(text, self.did_rx, self.rid_rx)
            try:
                got = rr.parse_did(text).canonical
            except rr.DidSyntaxError:
                got = None
            if got != spec:
                found.append((text, spec, got))
        return found

    def test_the_vectors_of_check_did_syntax(self):
        texts = (check_did_syntax.MUST_PARSE + check_did_syntax.MUST_NOT_PARSE
                 + list(check_did_syntax.DECODES_TO) + check_did_syntax.DOES_NOT_DECODE
                 + ["", "did:opena2a", "did:opena2a:", " did:opena2a:a:x", "did:opena2a:a:x ", "did:OpenA2A:a:x",
                    "did:opena2a:a:%2g", "did:opena2a:a:%g2", "did:opena2a:a:%%41", "did:opena2a:a:x#y#z"])
        self.assertEqual(self.disagreements(texts), [])

    def test_every_did_in_the_repository(self):
        texts = list(check_did_syntax.documented_dids(check_did_syntax.sources()))
        self.assertTrue(texts)
        self.assertEqual(self.disagreements(texts), [])

    def test_each_character_in_each_part(self):
        # Four non-ASCII characters, written as escapes so the source holds none.
        chars = [chr(c) for c in range(128)] + ["\N{LATIN SMALL LETTER E WITH ACUTE}", "\N{NO-BREAK SPACE}",
                                                "\N{ARABIC-INDIC DIGIT ZERO}", "\N{FULLWIDTH LATIN SMALL LETTER A}"]
        texts = []
        for c in chars:
            texts += [f"did:opena2a:{c}:x", f"did:opena2a:a{c}:x", f"did:opena2a:a:{c}",
                      f"did:opena2a:a:x{c}y", f"did:opena2a:a:x#{c}", f"did:opena2a:a:x#y{c}"]
        self.assertEqual(self.disagreements(texts), [])

    def test_each_octet_percent_encoded(self):
        texts = []
        for octet in range(256):
            texts += [f"did:opena2a:a:%{octet:02X}", f"did:opena2a:a:x%{octet:02x}y"]
        self.assertEqual(self.disagreements(texts), [])

    def test_every_string_of_up_to_five_characters_over_one_of_each_kind(self):
        # A lowercase letter, an uppercase hex letter, a digit, "_", "@", the
        # three delimiters and a character no part admits.
        alphabet = ["a", "F", "2", "_", "@", ":", "%", "#", " "]
        texts = ["did:opena2a:" + "".join(chars) for n in range(6) for chars in itertools.product(alphabet, repeat=n)]
        self.assertEqual(len(texts), sum(9 ** n for n in range(6)))
        self.assertEqual(self.disagreements(texts), [])


class NamesTheDefect(unittest.TestCase):
    def assert_defect(self, text: str, part: str) -> None:
        with self.assertRaises(rr.DidSyntaxError) as raised:
            rr.parse_did(text)
        self.assertIn(part, str(raised.exception))

    def test_each_kind_of_defect(self):
        self.assert_defect("did:OPENA2A:agent:x", "does not begin with did:opena2a:")
        self.assert_defect("did:opena2a:agent", "no ':'")
        self.assert_defect("did:opena2a:agent9:x", "resource-type 'agent9'")
        self.assert_defect("did:opena2a:Agent:x", "resource-type 'Agent'")
        self.assert_defect("did:opena2a:agent:", "resource-id is empty")
        self.assert_defect("did:opena2a:agent:x#", "fragment")
        self.assert_defect("did:opena2a:agent:x%2", "two hexadecimal digits")
        self.assert_defect("did:opena2a:agent:x%25", "%25 in the resource-id decodes")
        self.assert_defect("did:opena2a:agent:a b", "' ' at offset 1")

    def test_the_resource_id_keeps_its_case(self):
        did = rr.parse_did("did:opena2a:mcp_server:%40Scope%2fServer")
        self.assertEqual((did.resource_type, did.resource_id, did.fragment), ("mcp_server", "@Scope/Server", None))
        self.assertEqual(rr.parse_did(AGENT + "#key-1").fragment, "key-1")


class Multibase(unittest.TestCase):
    def test_base58btc_known_answers(self):
        # Leading zero bytes are "1"; 57 is the last character; 58 is "21".
        cases = {b"": "", b"\0": "1", b"\0\x01": "12", bytes([57]): "z", bytes([58]): "21", b"\0\0\xff": "115Q"}
        for data, text in cases.items():
            self.assertEqual(rr.base58btc_encode(data), text)
            self.assertEqual(rr.base58btc_decode(text), data)

    def test_the_conformance_subject_key_is_the_rfc_8032_test_2_key(self):
        # Spec Section 5 abbreviates the key as 3d4017c3...660c.
        key = rr.ed25519_key(SUBJECT_KEY)
        self.assertEqual((len(key), key.hex()[:8], key.hex()[-4:]), (32, "3d4017c3", "660c"))
        self.assertEqual(rr.ed25519_multibase(key), SUBJECT_KEY)
        self.assertTrue(SUBJECT_KEY.startswith("z6Mk"))

    def test_round_trip(self):
        for key in (bytes(32), bytes(range(32)), b"\xff" * 32):
            value = rr.ed25519_multibase(key)
            self.assertTrue(value.startswith("z6Mk"), value)
            self.assertEqual(rr.ed25519_key(value), key)

    def test_rejects_what_is_not_an_ed25519_multibase_key(self):
        wrong = [
            "f" + (rr.ED25519_PUB + bytes(32)).hex(),                   # base16, not base58btc
            "z" + rr.base58btc_encode(b"\xec\x01" + bytes(32)),         # x25519-pub, not ed25519-pub
            "z" + rr.base58btc_encode(rr.ED25519_PUB + bytes(31)),      # 31 key bytes
            "z",
            "z6Mk-FAKE-key",
            "z6MkO0Il",                                                 # characters base58btc leaves out
            None,
        ]
        for value in wrong:
            with self.subTest(value=value), self.assertRaises(ValueError):
                rr.ed25519_key(value)
        with self.assertRaises(ValueError):
            rr.ed25519_multibase(bytes(31))


class BuildsDocuments(unittest.TestCase):
    def test_the_section_5_example(self):
        reg = registry()
        want = with_registry_key(section_5_example(), REGISTRY)
        self.assertEqual(reg.document(reg.records[AGENT]), want)

    def test_the_documents_under_examples(self):
        base = example("registry.json")
        reg = rr.Registry.from_json({"authority": "opena2a.org", "baseUrl": "https://api.oa2a.org",
                                     "signingKeys": [REGISTRY_KEY], "created": base["created"],
                                     "updated": base["updated"]})
        paths = sorted(EXAMPLES.glob("*.json")) + sorted((EXAMPLES / "conformance").glob("*.json"))
        self.assertEqual(len(paths), 8)
        for path in paths:
            want = with_registry_key(json.loads(path.read_text(encoding="utf-8")), reg.did)
            if want["id"] == reg.did:
                got = reg.registry_document()
            else:
                keys = [vm["publicKeyMultibase"] for vm in want["verificationMethod"]
                        if vm["id"] in want.get("authentication", [])]
                reg.add(rr.Record.from_json({"did": want["id"], "subjectKeys": keys,
                                             "created": want["created"], "updated": want["updated"]}))
                got = reg.document(reg.records[want["id"]])
            if path == EXAMPLES / "agent.json":
                # The reference deployment catalogues agents under the alias
                # a2a_agent and writes it into two URLs (docs/examples.md); the
                # resolver writes the resource type, as the Section 5 example does.
                for service in want["service"]:
                    url = service["serviceEndpoint"]
                    service["serviceEndpoint"] = url.replace("type=a2a_agent", "type=agent").replace(
                        "/badge/a2a_agent/", "/badge/agent/")
                    self.assertEqual(url != service["serviceEndpoint"], service["type"] != "TrustProof")
            with self.subTest(path=path.relative_to(REPO).as_posix()):
                self.assertEqual(got, want)

    def test_a_resource_without_keys_of_its_own(self):
        reg = registry()
        doc = reg.document(reg.records[MCP])
        self.assertNotIn("authentication", doc)
        self.assertEqual([vm["id"] for vm in doc["verificationMethod"]], [MCP + "#registry-key"])
        self.assertEqual(doc["assertionMethod"], [MCP + "#registry-key"])

    def test_subject_keys_are_numbered_and_only_they_authenticate(self):
        second = rr.ed25519_multibase(b"\x01" * 32)
        reg = registry(resources=[{"did": AGENT, "subjectKeys": [SUBJECT_KEY, second],
                                   "created": "2026-04-12T00:00:00Z", "updated": "2026-09-08T00:00:00Z"}])
        doc = reg.document(reg.records[AGENT])
        self.assertEqual([(vm["id"], vm["controller"], vm["publicKeyMultibase"]) for vm in doc["verificationMethod"]],
                         [(AGENT + "#key-1", AGENT, SUBJECT_KEY), (AGENT + "#key-2", AGENT, second),
                          (AGENT + "#registry-key", REGISTRY, REGISTRY_KEY)])
        self.assertEqual(doc["authentication"], [AGENT + "#key-1", AGENT + "#key-2"])
        self.assertEqual(doc["assertionMethod"], [AGENT + "#registry-key"])

    def test_documents_carry_the_current_registry_key(self):
        reg = registry()
        for doc in (reg.registry_document(), reg.document(reg.records[AGENT])):
            registry_keys = [vm["publicKeyMultibase"] for vm in doc["verificationMethod"]
                             if vm["controller"] == REGISTRY]
            self.assertEqual(registry_keys, [REGISTRY_KEY])


class Resolves(unittest.TestCase):
    def setUp(self):
        self.reg = registry()
        self.did_rx, self.rid_rx = check_vectors.grammar()

    def accepted(self, requested: str, result: dict) -> bool:
        verdict = check_vectors.verify(requested, result, self.did_rx, self.rid_rx, pinned=REGISTRY)
        return verdict == ("accept", None)

    def test_a_registered_did_with_the_section_4_2_reply(self):
        status, headers, body = get(self.reg, rr.RESOLVE_PATH + AGENT)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/did+ld+json")
        self.assertEqual(headers["Cache-Control"], "public, max-age=300")
        self.assertEqual(body["didDocument"], self.reg.document(self.reg.records[AGENT]))
        self.assertEqual(body["didResolutionMetadata"], {"contentType": "application/did+ld+json"})
        self.assertEqual(body["didDocumentMetadata"], {"issuingRegistry": REGISTRY})

    def test_every_reply_passes_the_verifier_checks(self):
        for did in [REGISTRY, *self.reg.records]:
            status, _, body = get(self.reg, rr.RESOLVE_PATH + did)
            with self.subTest(did=did):
                self.assertEqual(status, 200)
                self.assertTrue(self.accepted(did, body))

    def test_a_percent_encoded_did_resolves_to_its_canonical_form(self):
        # MCP_ENCODED_IN_URL reaches the resolver as MCP_ENCODED after the
        # transport's URL decoding; MCP_ENCODED reaches it as MCP.
        for target, requested in ((MCP_ENCODED_IN_URL, MCP_ENCODED), (MCP_ENCODED, MCP)):
            status, _, body = get(self.reg, rr.RESOLVE_PATH + target)
            with self.subTest(target=target):
                self.assertEqual(status, 200)
                self.assertEqual(body["didDocument"]["id"], MCP)
                self.assertTrue(self.accepted(requested, body))

    def test_a_did_with_no_record_is_404_naming_it(self):
        for did in ("did:opena2a:agent:not_registered", "did:opena2a:registry:evil.test", "did:opena2a:widget:x"):
            status, headers, body = get(self.reg, rr.RESOLVE_PATH + did)
            with self.subTest(did=did):
                self.assertEqual(status, 404)
                self.assertEqual(headers["Content-Type"], "application/json")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(body["did"], did)
                self.assertIn(did, body["message"])

    def test_an_invalid_did_or_a_fragment_is_400(self):
        # The Section 3.2 alias a2a_agent holds a digit, which no resource-type admits.
        for target in ("did:opena2a:agent9:x", "did:opena2a:a2a_agent:agent_conformance_test_001",
                       "did:OPENA2A:agent:x", "did:opena2a:agent:x%2525", AGENT + "%23key-1", AGENT + "#key-1", ""):
            status, headers, body = get(self.reg, rr.RESOLVE_PATH + target)
            with self.subTest(target=target):
                self.assertEqual(status, 400)
                self.assertEqual(headers["Content-Type"], "application/json")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(body["error"], "invalidDid")
                self.assertEqual(body["did"], urllib.parse.unquote(target))
                self.assertTrue(body["message"])
        _, _, body = get(self.reg, rr.RESOLVE_PATH + "did:opena2a:agent9:x")
        self.assertIn("resource-type 'agent9'", body["message"])

    def test_a_deactivated_record(self):
        for status_name in ("suspended", "revoked", "deprecated"):
            reg = registry(resources=[{"did": DEPRECATED, "status": status_name,
                                       "created": "2026-03-01T00:00:00Z", "updated": "2026-09-08T00:00:00Z"}])
            status, _, body = get(reg, rr.RESOLVE_PATH + DEPRECATED)
            with self.subTest(status=status_name):
                self.assertEqual(status, 200)
                self.assertEqual(body["didDocumentMetadata"], {"issuingRegistry": REGISTRY, "deactivated": True})
                self.assertNotIn("service", body["didDocument"])
                self.assertTrue(self.accepted(DEPRECATED, body))
        status, _, body = get(self.reg, rr.RESOLVE_PATH + MCP)
        self.assertEqual(body["didDocumentMetadata"], {"issuingRegistry": REGISTRY})
        self.assertEqual([s["type"] for s in body["didDocument"]["service"]],
                         ["TrustLookup", "TrustProof", "TrustBadge"])

    def test_head_gets_the_status_and_headers_of_get(self):
        target = rr.RESOLVE_PATH + AGENT
        self.assertEqual(self.reg.respond("HEAD", target), self.reg.respond("GET", target))

    def test_other_methods_and_paths(self):
        status, headers, _ = get(self.reg, rr.RESOLVE_PATH + AGENT, method="POST")
        self.assertEqual((status, headers["Allow"]), (405, "GET, HEAD"))
        status, _, _ = get(self.reg, "/api/v1/registry/packages")
        self.assertEqual(status, 404)

    def test_the_query_is_not_part_of_the_did(self):
        status, _, body = get(self.reg, rr.RESOLVE_PATH + AGENT + "?x=1")
        self.assertEqual((status, body["didDocument"]["id"]), (200, AGENT))

    def test_the_discovery_document_lists_every_signing_key(self):
        status, headers, body = get(self.reg, rr.DISCOVERY_PATH)
        self.assertEqual((status, headers["Content-Type"]), (200, "application/json"))
        self.assertEqual(body["registryDid"], REGISTRY)
        self.assertEqual(body["supportedMethods"], ["did:opena2a"])
        self.assertEqual(body["endpoints"], {"didResolve": "/api/v1/did/{did}"})
        self.assertEqual([(k["algorithm"], base64.b64decode(k["publicKey"]), k["publicKeyMultibase"])
                          for k in body["publicKeys"]],
                         [("Ed25519", bytes(range(32)), REGISTRY_KEY),
                          ("Ed25519", bytes(range(32, 64)), OLDER_REGISTRY_KEY)])

    def test_the_resolution_vectors(self):
        # Against the vectors' pinned registry: the resolver answers the
        # accepted request, and answers 404 where a verifier would have to
        # reject the document it was given.
        reg = registry(authority="opena2a.org", baseUrl="https://api.oa2a.org", resources=[])
        paths = sorted(check_vectors.VECTORS.glob("*.json"))
        self.assertEqual(len(paths), 2)
        for path in paths:
            vector = json.loads(path.read_text(encoding="utf-8"))
            status, body = reg.resolve(vector["requestedDid"])
            with self.subTest(vector=path.name):
                if vector["expected"]["verdict"] == "accept":
                    self.assertEqual(status, 200)
                    self.assertEqual(check_vectors.verify(vector["requestedDid"], body, self.did_rx, self.rid_rx),
                                     ("accept", None))
                else:
                    self.assertEqual(status, 404)


class LoadsRecords(unittest.TestCase):
    RESOURCE = {"did": AGENT, "created": "2026-04-12T00:00:00Z", "updated": "2026-09-08T00:00:00Z"}

    def assert_refused(self, data: dict, part: str) -> None:
        with self.assertRaises(ValueError) as raised:
            rr.Registry.from_json(data)
        self.assertIn(part, str(raised.exception))

    def test_the_section_4_1_rules(self):
        self.assert_refused(records(resources=[self.RESOURCE, dict(self.RESOURCE)]), "registered twice")
        self.assert_refused(records(resources=[dict(self.RESOURCE, did=MCP_ENCODED)]), "canonical form")
        self.assert_refused(records(resources=[dict(self.RESOURCE, did=AGENT + "#key-1")]), "canonical form")
        self.assert_refused(records(resources=[dict(self.RESOURCE, did=REGISTRY)]), "self-identifier")
        self.assert_refused(records(resources=[dict(self.RESOURCE, did="did:opena2a:Agent:x")]), "resources[0].did")

    def test_keys_times_and_addresses(self):
        self.assert_refused(records(signingKeys=[]), "signingKeys")
        self.assert_refused(records(signingKeys=["z6Mk-FAKE-registry-key"]), "signingKeys[0]")
        self.assert_refused(records(signingKeys=[REGISTRY_KEY, REGISTRY_KEY]), "twice")
        self.assert_refused(records(resources=[dict(self.RESOURCE, subjectKeys=["not-a-real-key"])]), "subjectKeys[0]")
        self.assert_refused(records(created="2026-02-15"), "created")
        self.assert_refused(records(created="2026-13-15T00:00:00Z"), "created")
        self.assert_refused(records(baseUrl="http://registry.example"), "https")
        self.assert_refused(records(baseUrl="https://registry.example/?x=1"), "https")
        self.assert_refused(records(authority="Registry.Example"), "authority")
        self.assert_refused(records(authority="registry.example/x"), "authority")
        self.assert_refused(records(extra=1), "unknown member 'extra'")
        self.assert_refused([], "not a JSON object")

    def test_resources_subject_keys_and_status_are_optional(self):
        data = records()
        del data["resources"]
        self.assertEqual(rr.Registry.from_json(data).records, {})
        record = registry().records[MCP]
        self.assertEqual((record.subject_keys, record.status, record.deactivated), ((), "active", False))

    def test_a_trailing_slash_on_the_base_url(self):
        reg = registry(baseUrl="https://registry.example/")
        self.assertEqual(reg.registry_document()["service"][1]["serviceEndpoint"],
                         "https://registry.example/api/v1/did/")


class ServesHttp(unittest.TestCase):
    """The handler on a loopback socket, requested with urllib."""

    def setUp(self):
        self.server = rr.ThreadingHTTPServer(("127.0.0.1", 0), rr.handler_for(registry(), log=False))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        # No proxy, from the environment or the system settings.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=10)

    def request(self, path: str, method: str = "GET") -> tuple:
        req = urllib.request.Request(self.base + path, method=method)
        try:
            with self.opener.open(req, timeout=10) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as err:
            with err:
                return err.code, err.headers, err.read()

    def test_get_head_and_errors(self):
        status, headers, body = self.request(rr.RESOLVE_PATH + MCP)
        self.assertEqual((status, headers["Content-Type"]), (200, "application/did+ld+json"))
        self.assertEqual(json.loads(body)["didDocument"]["id"], MCP)

        status, head_headers, head_body = self.request(rr.RESOLVE_PATH + MCP, method="HEAD")
        self.assertEqual((status, head_body), (200, b""))
        self.assertEqual(head_headers["Content-Length"], str(len(body)))

        status, _, body = self.request(rr.RESOLVE_PATH + MCP_ENCODED)
        self.assertEqual((status, json.loads(body)["didDocument"]["id"]), (200, MCP))

        status, _, body = self.request(rr.RESOLVE_PATH + "did:opena2a:registry:evil.test")
        self.assertEqual((status, json.loads(body)["error"]), (404, "notFound"))

        status, headers, _ = self.request(rr.RESOLVE_PATH + AGENT, method="POST")
        self.assertEqual((status, headers["Allow"]), (405, "GET, HEAD"))

        status, _, body = self.request(rr.DISCOVERY_PATH)
        self.assertEqual((status, json.loads(body)["registryDid"]), (200, REGISTRY))


class ClosesIdleConnections(unittest.TestCase):
    """serve's handler has a timeout, and a read that waits longer than it closes the connection."""

    def test_serve_gives_its_handler_the_timeout(self):
        handlers = []

        def refuse(address, handler):
            handlers.append(handler)
            raise OSError("this test does not listen")

        with mock.patch.object(rr, "ThreadingHTTPServer", refuse), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(rr.serve(registry(), "127.0.0.1", 0), 2)
        self.assertEqual([handler.timeout for handler in handlers], [rr.TIMEOUT_SECONDS])
        self.assertGreater(rr.TIMEOUT_SECONDS, 0)
        # The module docstring, which --help prints, states the value.
        self.assertIn(f"waits longer than {rr.TIMEOUT_SECONDS} seconds", " ".join(rr.__doc__.split()))

    def test_a_connection_that_sends_nothing_or_stops_partway_is_closed(self):
        # Half a second, so the test does not wait the TIMEOUT_SECONDS that serve() gives a read.
        server = rr.ThreadingHTTPServer(("127.0.0.1", 0), rr.handler_for(registry(), log=False, timeout=0.5))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        request = f"GET {rr.RESOLVE_PATH}{AGENT} HTTP/1.0\r\nHost: 127.0.0.1\r\n".encode("ascii")
        # Nothing, part of the request line, and the request line and a header without the blank line that ends them.
        for sent in (b"", request[:12], request):
            with self.subTest(sent=sent), socket.create_connection(("127.0.0.1", server.server_port),
                                                                    timeout=10) as conn:
                conn.sendall(sent)
                try:
                    reply = conn.recv(1024)
                except socket.timeout:
                    self.fail("the server kept the connection open for 10 seconds")
                self.assertEqual(reply, b"")


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "records.json"
        self.path.write_text(json.dumps(records()), encoding="utf-8")

    def tearDown(self):
        self.dir.cleanup()

    def run_main(self, *argv: str) -> tuple:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rr.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_resolve_prints_the_reply_and_exits_0_for_200(self):
        code, out, _ = self.run_main("--records", str(self.path), "resolve", AGENT)
        head, _, body = out.partition("\n\n")
        self.assertEqual(code, 0)
        self.assertEqual(head.splitlines()[0], "200 OK")
        self.assertIn("Content-Type: application/did+ld+json", head.splitlines())
        self.assertEqual(json.loads(body)["didDocument"]["id"], AGENT)

    def test_resolve_takes_the_did_string_as_written(self):
        # A DID string, not a URL path: one decoding, the Section 3.1.2 step.
        code, out, _ = self.run_main("--records", str(self.path), "resolve", MCP_ENCODED)
        self.assertEqual((code, json.loads(out.partition("\n\n")[2])["didDocument"]["id"]), (0, MCP))
        code, out, _ = self.run_main("--records", str(self.path), "resolve", MCP_ENCODED_IN_URL)
        self.assertEqual((code, out.splitlines()[0]), (1, "400 Bad Request"))

    def test_resolve_exits_1_otherwise(self):
        code, out, _ = self.run_main("--records", str(self.path), "resolve", "did:opena2a:agent:not_registered")
        self.assertEqual((code, out.splitlines()[0]), (1, "404 Not Found"))

    def test_a_records_file_that_does_not_load_exits_2(self):
        self.path.write_text(json.dumps(records(baseUrl="http://registry.example")), encoding="utf-8")
        code, out, err = self.run_main("--records", str(self.path), "resolve", AGENT)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("baseUrl", err)
        code, _, err = self.run_main("--records", str(self.path) + ".missing", "resolve", AGENT)
        self.assertEqual(code, 2)

    def test_serve_reports_an_address_it_cannot_listen_on_in_one_line(self):
        with socket.socket() as holder:
            holder.bind(("127.0.0.1", 0))
            holder.listen()
            port = holder.getsockname()[1]
            code, out, err = self.run_main("--records", str(self.path), "serve", "--port", str(port))
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertTrue(err.startswith(f"cannot listen on 127.0.0.1:{port}: "), err)

    def test_serve_refuses_a_host_that_is_not_an_ipv4_address(self):
        # The socket module reads an empty host as every interface, so a script whose host variable is unset
        # would listen beyond loopback. It reads "0" as every interface too, and so "0" followed by a zero-width
        # space or written as a fullwidth digit, which the IDNA codec turns into "0"; it looks up a name and reads
        # 127.1 and 0x7f.0.0.1 as 127.0.0.1. ThreadingHTTPServer is replaced, so a host serve() let through would
        # not be listened on.
        hosts = ("", " ", "0", "0\N{ZERO WIDTH SPACE}", "\N{FULLWIDTH DIGIT ZERO}", "localhost", "::1", "127.1",
                 "0x7f.0.0.1", "127.0.0.01", "256.0.0.1", "<broadcast>", " 127.0.0.1", "127.0.0.1 ", "127.0.0.1\n",
                 "127.0.0.1\N{LEFT-TO-RIGHT MARK}")
        for host in hosts:
            with mock.patch.object(rr, "ThreadingHTTPServer") as server:
                code, out, err = self.run_main("--records", str(self.path), "serve", "--host", host)
            self.assertEqual((code, out), (2, ""), ascii(host))
            server.assert_not_called()
            # The line names the host, which the other serve tests check, then the port and the reason.
            self.assertTrue(err.startswith("cannot listen on "), ascii(err))
            self.assertTrue(err.endswith(":8080: not an IPv4 address such as 127.0.0.1\n"), ascii(err))

    def test_serve_takes_an_ipv4_address_for_host(self):
        # ThreadingHTTPServer is replaced by one that records the address and refuses it, so nothing listens.
        addresses = []

        def refuse(address, handler):
            addresses.append(address)
            raise OSError("this test does not listen")

        for argv, host in ((["serve"], "127.0.0.1"), (["serve", "--host", "192.0.2.1"], "192.0.2.1"),
                           (["serve", "--host", "0.0.0.0"], "0.0.0.0")):
            with mock.patch.object(rr, "ThreadingHTTPServer", refuse):
                code, out, err = self.run_main("--records", str(self.path), *argv)
            self.assertEqual((code, out, err), (2, "", f"cannot listen on {host}:8080: this test does not listen\n"))
        self.assertEqual(addresses, [("127.0.0.1", 8080), ("192.0.2.1", 8080), ("0.0.0.0", 8080)])

    def test_serve_reports_a_host_it_cannot_encode_in_one_line(self):
        # Hosts the IDNA codec refuses, for which the socket module would raise TypeError, not OSError: an
        # invisible mark copied with the address, the byte 0xFF as the command line decodes it, an empty label.
        # serve refuses each as not an IPv4 address before the socket module reads it; the held port keeps serve
        # from answering should one of them get through.
        hosts = ("127.0.0.1\N{LEFT-TO-RIGHT MARK}", "\N{RIGHT-TO-LEFT OVERRIDE}127.0.0.1",
                 "127.0.0.1\N{REPLACEMENT CHARACTER}", "127.0.0.1\udcff", "\N{LATIN SMALL LETTER A WITH DIAERESIS}..b")
        with socket.socket() as holder:
            holder.bind(("127.0.0.1", 0))
            holder.listen()
            port = str(holder.getsockname()[1])
            for host in hosts:
                code, out, err = self.run_main("--records", str(self.path), "serve", "--host", host, "--port", port)
                self.assertEqual((code, out), (2, ""), ascii(host))
                self.assertEqual(len(err.splitlines()), 1, ascii(err))
                self.assertTrue(err.startswith(f"cannot listen on {ascii(host)}:{port}: "), ascii(err))

    def test_serve_shows_a_host_with_an_invisible_character_escaped_on_one_line(self):
        # A newline, a tab or a trailing space in --host fails to resolve; the report escapes it rather than
        # printing it, so the line does not break and the character is visible.
        hosts = ("127.0.0.1\n", "127.0.0.1\r\n:x", "127.0.0.1\t", "127.0.0.1 ", "\x00127.0.0.1")
        with socket.socket() as holder:
            holder.bind(("127.0.0.1", 0))
            holder.listen()
            port = str(holder.getsockname()[1])
            for host in hosts:
                code, out, err = self.run_main("--records", str(self.path), "serve", "--host", host, "--port", port)
                self.assertEqual((code, out), (2, ""), ascii(host))
                self.assertEqual(len(err.splitlines()), 1, ascii(err))
                self.assertTrue(err.isascii(), ascii(err))
                self.assertTrue(err.startswith(f"cannot listen on {ascii(host)}:{port}: "), ascii(err))
        self.assertEqual(rr.shown_host("127.0.0.1"), "127.0.0.1")
        self.assertEqual(rr.shown_host("::1"), "::1")
        self.assertEqual(rr.shown_host("127.0.0.1\N{LEFT-TO-RIGHT MARK}"), "'127.0.0.1\\u200e'")
        self.assertEqual(rr.shown_host(""), "''")

    def test_serve_refuses_a_port_outside_0_to_65535(self):
        for port in ("65536", "-1", "x"):
            err = io.StringIO()
            with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(err):
                rr.main(["--records", str(self.path), "serve", "--port", port])
            self.assertEqual(caught.exception.code, 2, port)
            self.assertIn("argument --port", err.getvalue())
        # Called directly, serve() reports the port it cannot bind the same way.
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = rr.serve(registry(), "127.0.0.1", 65536)
        self.assertEqual(code, 2)
        self.assertEqual(len(err.getvalue().splitlines()), 1, err.getvalue())
        self.assertTrue(err.getvalue().startswith("cannot listen on 127.0.0.1:65536: "), err.getvalue())


if __name__ == "__main__":
    unittest.main()
