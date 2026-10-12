#!/usr/bin/env python3
"""Tests for check_vectors.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import check_vectors

CANONICAL = "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem"
# The Section 3.1.1 serialization of CANONICAL. Percent-encoded DIDs stay out
# of vectors/, which the family did-example-forms check reads.
ENCODED = "did:opena2a:mcp_server:%40modelcontextprotocol%2Fserver-filesystem"


def result(doc_id: str, issuing: str = check_vectors.PINNED_REGISTRY) -> dict:
    return {
        "didDocument": {"id": doc_id},
        "didResolutionMetadata": {"contentType": "application/did+ld+json"},
        "didDocumentMetadata": {"issuingRegistry": issuing},
    }


class VerifyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rx = check_vectors.grammar()

    def verify(self, requested: str, res: dict) -> tuple:
        return check_vectors.verify(requested, res, *self.rx)

    def test_canonical_request_compares_as_is(self):
        self.assertEqual(self.verify(CANONICAL, result(CANONICAL)), ("accept", None))

    def test_percent_encoded_request_answered_with_canonical_id_is_accepted(self):
        # Sections 3.1.2, 4.2 and 6.5: the returned id is the canonical form.
        self.assertEqual(self.verify(ENCODED, result(CANONICAL)), ("accept", None))

    def test_percent_encoded_request_answered_with_requested_string_is_rejected(self):
        self.assertEqual(self.verify(ENCODED, result(ENCODED)), ("reject", "resolved-id-mismatch"))

    def test_other_issuing_registry_is_rejected(self):
        res = result(CANONICAL, issuing="did:opena2a:registry:evil.test")
        self.assertEqual(self.verify(CANONICAL, res), ("reject", "issuing-registry-mismatch"))

    def test_request_that_does_not_decode_is_malformed(self):
        with self.assertRaises(ValueError):
            self.verify("did:opena2a:skill:web%20research", result(CANONICAL))

    def test_repository_vectors_pass(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check_vectors.main(), 0)


if __name__ == "__main__":
    unittest.main()
