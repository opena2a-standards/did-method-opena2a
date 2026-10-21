#!/usr/bin/env python3
"""Tests for check_examples.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import contextlib
import io
import json
import socket
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import check_examples


def run_live(side_effect) -> tuple:
    """Run `check_examples.py --live` with every request raising, or answered by, `side_effect`."""
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["check_examples.py", "--live"]), \
            mock.patch("urllib.request.urlopen", side_effect=side_effect), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = check_examples.main()
    return status, out.getvalue(), err.getvalue()


class Response(io.BytesIO):
    """A 200 response whose body is the given bytes."""

    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def answer(body: bytes):
    return lambda *args, **kwargs: Response(body)


class LiveNetworkErrors(unittest.TestCase):
    def assert_reported(self, error: BaseException, reason: str) -> None:
        status, out, err = run_live(error)
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertIn("examples/agent.json: did:opena2a:", err)
        self.assertIn(f"request failed: {reason}", err)
        self.assertNotIn("answered", err)

    def test_refused_connection_is_reported_not_raised(self):
        self.assert_reported(urllib.error.URLError(ConnectionRefusedError(61, "Connection refused")),
                             "[Errno 61] Connection refused")

    def test_dns_failure_is_reported_not_raised(self):
        self.assert_reported(urllib.error.URLError(socket.gaierror(8, "nodename nor servname provided")),
                             "[Errno 8] nodename nor servname provided")

    def test_timeout_is_reported_not_raised(self):
        self.assert_reported(TimeoutError("timed out"), "timed out")

    def test_http_error_is_still_reported_as_a_status(self):
        error = urllib.error.HTTPError("https://api.oa2a.org/", 404, "Not Found", None, io.BytesIO(b""))
        status, _, err = run_live(error)
        self.assertEqual(status, 1)
        self.assertIn("answered 404, expected 200", err)
        self.assertNotIn("request failed", err)
        self.assertNotIn("examples/conformance/", err)


class LiveBodyNotJson(unittest.TestCase):
    def assert_reported(self, body: bytes) -> None:
        status, out, err = run_live(answer(body))
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertIn("examples/agent.json: did:opena2a:agent:", err)
        self.assertIn("answered 200 with a body that is not a JSON object", err)
        # A conformance DID that answers 200 is reported as served, whatever the body.
        self.assertIn("examples/conformance/agent.json: did:opena2a:agent:agent_conformance_test_001 "
                      "answered 200; it is served", err)

    def test_html_body_is_reported_not_raised(self):
        self.assert_reported(b"<html>")

    def test_body_that_is_not_utf8_is_reported_not_raised(self):
        self.assert_reported(b"\x80<html>")

    def test_json_array_body_is_reported_not_raised(self):
        self.assert_reported(b"[]")


REGISTRY = check_examples.REGISTRY_DID
ED25519 = "Ed25519VerificationKey2020"
SIGNING = "z6Mk-FAKE-registry-signing-key"


def deployment() -> dict:
    """DID -> the document a deployment with the layout spec Sections 5.1 and 5.3 record returns.

    Each served example keeps its id and service; its keys take the deployment's
    layout. Key values are fake; the conformance DIDs are left out, so they answer 404.
    """
    served = {}
    for path in sorted(check_examples.EXAMPLES.glob("*.json")):
        example = json.loads(path.read_text(encoding="utf-8"))
        did = example["id"]
        if did == REGISTRY:
            doc = {
                "@context": check_examples.CONTEXT + ["https://w3id.org/security/jwk/v1"],
                "id": did,
                "verificationMethod": [
                    {"id": f"{did}#signing-key", "type": ED25519, "controller": did, "publicKeyMultibase": SIGNING},
                    {"id": f"{did}#key-v1", "type": ED25519, "controller": did, "publicKeyMultibase": SIGNING},
                    {"id": f"{did}#pqc-v1", "type": "JsonWebKey", "controller": did,
                     "publicKeyJwk": {"kty": "AKP", "alg": "ML-DSA-65", "pub": "FAKE-ML-DSA-65"}},
                ],
                "authentication": [f"{did}#signing-key"],
                "assertionMethod": [f"{did}#signing-key", f"{did}#key-v1", f"{did}#pqc-v1"],
            }
        else:
            key = f"{did}#registry-key"
            doc = {
                "@context": check_examples.CONTEXT,
                "id": did,
                "verificationMethod": [
                    {"id": key, "type": ED25519, "controller": REGISTRY, "publicKeyMultibase": SIGNING},
                ],
                "authentication": [key],
                "assertionMethod": [key],
            }
        doc["service"] = example["service"]
        served[did] = doc
    return served


def not_found(did: str) -> bytes:
    """The body of the deployment's 404 reply to `did`, as spec Section 8.4 records it."""
    _, _, rtype, rid = did.split(":", 3)
    return json.dumps({"error": f"resource not found: {rtype}/{rid}"}).encode("utf-8")


def serve(documents: dict, bodies: dict | None = None):
    """Answer each resolution request with its DID's document, or 404 for a DID not in `documents`.

    A 404 reply carries the body `bodies` gives for its DID, or the one spec Section 8.4 records.
    """
    def respond(request, *args, **kwargs):
        did = request.full_url.split("/api/v1/did/", 1)[1]
        if did not in documents:
            body = (bodies or {}).get(did, not_found(did))
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, io.BytesIO(body))
        return Response(json.dumps(documents[did]).encode("utf-8"))
    return respond


class LiveKeys(unittest.TestCase):
    MCP = "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem"

    def run_against(self, documents: dict) -> tuple:
        return run_live(serve(documents))

    def assert_only_problem(self, documents: dict, *expected: str) -> None:
        status, out, err = self.run_against(documents)
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertEqual(err.splitlines(), list(expected))

    def test_the_recorded_deployment_layout_passes(self):
        status, out, err = self.run_against(deployment())
        self.assertEqual(err, "")
        self.assertEqual(status, 0)
        self.assertEqual(out, "examples match: 6 served, 2 conformance, resolved against the reference deployment\n")

    def test_a_registry_document_with_one_key_is_reported(self):
        documents = deployment()
        registry = documents[REGISTRY]
        registry["@context"] = check_examples.CONTEXT
        registry["verificationMethod"] = registry["verificationMethod"][:1]
        registry["assertionMethod"] = [f"{REGISTRY}#signing-key"]
        status, _, err = self.run_against(documents)
        self.assertEqual(status, 1)
        self.assertIn("examples/registry.json: live verificationMethod "
                      f"[#signing-key {ED25519} {REGISTRY}] differs from the layout spec Section 5.3 records "
                      f"for the deployment, [#signing-key {ED25519} {REGISTRY}, #key-v1 {ED25519} {REGISTRY}, "
                      f"#pqc-v1 JsonWebKey {REGISTRY} AKP ML-DSA-65]", err)
        self.assertIn("examples/registry.json: live assertionMethod [#signing-key] differs from the layout "
                      "spec Section 5.3 records for the deployment, [#signing-key, #key-v1, #pqc-v1]", err)
        self.assertIn("examples/registry.json: live @context", err)
        self.assertEqual(len(err.splitlines()), 3)

    def test_a_registry_key_under_authentication_twice_is_reported(self):
        documents = deployment()
        documents[REGISTRY]["authentication"] = list(documents[REGISTRY]["assertionMethod"])
        self.assert_only_problem(
            documents,
            "examples/registry.json: live authentication [#signing-key, #key-v1, #pqc-v1] differs from the "
            "layout spec Section 5.3 records for the deployment, [#signing-key]")

    def test_a_pqc_key_with_another_algorithm_is_reported(self):
        documents = deployment()
        documents[REGISTRY]["verificationMethod"][2]["publicKeyJwk"]["alg"] = "ML-DSA-44"
        status, _, err = self.run_against(documents)
        self.assertEqual(status, 1)
        self.assertIn(f"examples/registry.json: live verificationMethod [#signing-key {ED25519} {REGISTRY}, "
                      f"#key-v1 {ED25519} {REGISTRY}, #pqc-v1 JsonWebKey {REGISTRY} AKP ML-DSA-44] differs", err)

    def test_a_resource_document_in_the_target_shape_is_reported(self):
        # A resolver that publishes a subject key (the Section 5 shape) makes the
        # Section 5.1 note stale.
        documents = deployment()
        doc = documents[self.MCP]
        doc["verificationMethod"].insert(0, {"id": f"{self.MCP}#key-1", "type": ED25519, "controller": self.MCP,
                                             "publicKeyMultibase": "z6Mk-FAKE-subject-key"})
        doc["authentication"] = [f"{self.MCP}#key-1"]
        self.assert_only_problem(
            documents,
            f"examples/mcp_server.json: live verificationMethod [#key-1 {ED25519} {self.MCP}, #registry-key "
            f"{ED25519} {REGISTRY}] differs from the layout spec Section 5.1 records for the deployment, "
            f"[#registry-key {ED25519} {REGISTRY}]",
            "examples/mcp_server.json: live authentication [#key-1] differs from the layout spec "
            "Section 5.1 records for the deployment, [#registry-key]")

    def test_a_resource_registry_key_that_is_not_the_signing_key_is_reported(self):
        documents = deployment()
        documents[self.MCP]["verificationMethod"][0]["publicKeyMultibase"] = "z6Mk-FAKE-other-key"
        self.assert_only_problem(
            documents,
            f"examples/mcp_server.json: {self.MCP}#registry-key does not carry the key "
            f"{REGISTRY}#signing-key carries (spec Section 5.1)")

    def test_a_key_v1_that_is_not_the_signing_key_is_reported(self):
        documents = deployment()
        documents[REGISTRY]["verificationMethod"][1]["publicKeyMultibase"] = "z6Mk-FAKE-other-key"
        self.assert_only_problem(
            documents,
            f"examples/registry.json: {REGISTRY}#key-v1 does not carry the key "
            f"{REGISTRY}#signing-key carries (spec Section 5.3)")

    def test_a_verification_method_that_is_not_a_list_is_reported_not_raised(self):
        documents = deployment()
        documents[self.MCP]["verificationMethod"] = documents[self.MCP]["verificationMethod"][0]
        status, _, err = self.run_against(documents)
        self.assertEqual(status, 1)
        self.assertIn("examples/mcp_server.json: live verificationMethod {'id': ", err)
        self.assertEqual(len(err.splitlines()), 1)

    def test_service_and_keys_are_both_reported(self):
        documents = deployment()
        documents[self.MCP]["service"] = documents[self.MCP]["service"][:1]
        documents[self.MCP]["assertionMethod"] = []
        self.assert_only_problem(
            documents,
            "examples/mcp_server.json: service endpoints differ from the live document",
            "examples/mcp_server.json: live assertionMethod [] differs from the layout spec Section 5.1 "
            "records for the deployment, [#registry-key]")


class LiveNotFoundBody(unittest.TestCase):
    DID = check_examples.NOT_FOUND_DID
    RECORDED = '{"error":"resource not found: agent/agent_conformance_test_001"}'

    def assert_only_problem(self, bodies: dict, expected: str) -> None:
        status, out, err = run_live(serve(deployment(), bodies))
        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertEqual(err.splitlines(), [expected])

    def test_another_body_is_reported(self):
        # The body the deployment returned on 2026-10-12, which did not name the resource.
        self.assert_only_problem(
            {self.DID: b'{"error":"package not found: registry package not found"}'},
            f'spec Section 8.4: {self.DID} answered 404 with '
            f'{{"error":"package not found: registry package not found"}}, where the section records {self.RECORDED}')

    def test_a_body_that_is_not_json_is_reported(self):
        self.assert_only_problem(
            {self.DID: b"<html>"},
            f"spec Section 8.4: {self.DID} answered 404 with a body that is not a JSON object, "
            f"where the section records {self.RECORDED}")

    def test_a_served_did_is_reported(self):
        documents = deployment()
        documents[self.DID] = {"id": self.DID}
        status, _, err = run_live(serve(documents))
        self.assertEqual(status, 1)
        self.assertIn(f"spec Section 8.4: {self.DID} answered 200, where the section records 404 with "
                      f"{self.RECORDED}", err)


class NotFoundBodyDocumentation(unittest.TestCase):
    """Spec Section 8.4 records the reply `--live` compares, for the DID it compares."""

    def test_section_8_4_records_the_body_the_live_check_compares(self):
        spec = (check_examples.ROOT / "did-method-opena2a.md").read_text(encoding="utf-8")
        section = spec.split("\n### 8.4 ", 1)[1].split("\n### ", 1)[0]
        did = check_examples.NOT_FOUND_DID
        for rtype, rid in (("<type>", "<id>"), did.split(":", 3)[2:]):
            body = json.dumps(check_examples.not_found_body(rtype, rid), separators=(",", ":"))
            self.assertIn(f"`{body}`", section)
        self.assertIn(f"`curl -s https://api.oa2a.org/api/v1/did/{did}`", section)


# The registry DIDs the spec Section 4.2 implementation status note records the
# deployment answering with 404; none of them is its self-identifier.
NOTED_REGISTRIES = (
    "did:opena2a:registry:evil.test",
    "did:opena2a:registry:example.com",
    "did:opena2a:registry:api.oa2a.org",
    "did:opena2a:registry:OPENA2A.ORG",
    "did:opena2a:registry:OpenA2A.org",
    "did:opena2a:registry:opena2a.org.",
)


def requested_did(request) -> str:
    return request.full_url.split("/api/v1/did/", 1)[1]


class LiveUnregisteredRegistries(unittest.TestCase):
    def test_each_noted_registry_did_is_resolved(self):
        requested = []
        respond = serve(deployment())

        def record(request, *args, **kwargs):
            requested.append(requested_did(request))
            return respond(request, *args, **kwargs)

        status, _, err = run_live(record)
        self.assertEqual((status, err), (0, ""))
        self.assertEqual([did for did in requested if did in NOTED_REGISTRIES], list(NOTED_REGISTRIES))

    def test_one_answered_with_the_registry_document_is_reported(self):
        # The substitution the deployment served for registry:evil.test on 2026-10-11.
        for did in NOTED_REGISTRIES:
            with self.subTest(did=did):
                documents = deployment()
                documents[did] = documents[REGISTRY]
                status, out, err = run_live(serve(documents))
                self.assertEqual(status, 1)
                self.assertEqual(out, "")
                self.assertEqual(err.splitlines(), [
                    f"did-method-opena2a.md: {did} answered 200 with the document of {REGISTRY}, "
                    "expected 404 (Section 4.2)"])

    def test_one_answered_200_with_a_body_that_is_not_a_document_is_reported(self):
        respond = serve(deployment())

        def answer_evil_test(request, *args, **kwargs):
            if requested_did(request) == NOTED_REGISTRIES[0]:
                return Response(b"<html>")
            return respond(request, *args, **kwargs)

        status, _, err = run_live(answer_evil_test)
        self.assertEqual(status, 1)
        self.assertEqual(err.splitlines(), [
            f"did-method-opena2a.md: {NOTED_REGISTRIES[0]} answered 200, expected 404 (Section 4.2)"])

    def test_one_answered_with_another_error_status_is_reported(self):
        respond = serve(deployment())

        def fail_example_com(request, *args, **kwargs):
            if requested_did(request) == NOTED_REGISTRIES[1]:
                raise urllib.error.HTTPError(request.full_url, 500, "Internal Server Error", None, io.BytesIO(b""))
            return respond(request, *args, **kwargs)

        status, _, err = run_live(fail_example_com)
        self.assertEqual(status, 1)
        self.assertEqual(err.splitlines(), [
            f"did-method-opena2a.md: {NOTED_REGISTRIES[1]} answered 500, expected 404 (Section 4.2)"])

    def test_a_network_error_is_reported_not_raised(self):
        respond = serve(deployment())

        def time_out_registries(request, *args, **kwargs):
            if requested_did(request) in NOTED_REGISTRIES:
                raise TimeoutError("timed out")
            return respond(request, *args, **kwargs)

        status, _, err = run_live(time_out_registries)
        self.assertEqual(status, 1)
        self.assertEqual(err.splitlines(), [f"did-method-opena2a.md: {did}: request failed: timed out"
                                            for did in NOTED_REGISTRIES])


if __name__ == "__main__":
    unittest.main()
