#!/usr/bin/env python3
"""Tests for check_vectors.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import check_vectors

CANONICAL = "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem"
# The Section 3.1.1 serialization of CANONICAL. Percent-encoded DIDs stay out
# of vectors/, which the family did-example-forms check reads.
ENCODED = "did:opena2a:mcp_server:%40modelcontextprotocol%2Fserver-filesystem"
ACCEPT = {"verdict": "accept"}
REJECT = {"verdict": "reject", "reason": "resolved-id-mismatch"}


def result(doc_id: str, issuing: str = check_vectors.PINNED_REGISTRY) -> dict:
    return {
        "didDocument": {"id": doc_id},
        "didResolutionMetadata": {"contentType": "application/did+ld+json"},
        "didDocumentMetadata": {"issuingRegistry": issuing},
    }


def vector(doc_id: str, expected: dict) -> dict:
    """A vector for a request for CANONICAL answered with the document `doc_id`."""
    return {"requestedDid": CANONICAL, "resolutionResult": result(doc_id), "expected": expected}


class VerifyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rx = check_vectors.grammar()

    def verify(self, requested: str, res) -> tuple:
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

    def test_absent_or_null_document_is_a_resolved_id_mismatch(self):
        for res in ({"didDocumentMetadata": result(CANONICAL)["didDocumentMetadata"]},
                    {**result(CANONICAL), "didDocument": None}):
            with self.subTest(res=res):
                self.assertEqual(self.verify(CANONICAL, res), ("reject", "resolved-id-mismatch"))

    def test_absent_or_null_metadata_is_an_issuing_registry_mismatch(self):
        for res in ({"didDocument": {"id": CANONICAL}},
                    {**result(CANONICAL), "didDocumentMetadata": None}):
            with self.subTest(res=res):
                self.assertEqual(self.verify(CANONICAL, res), ("reject", "issuing-registry-mismatch"))

    def test_result_that_is_not_an_object_is_malformed(self):
        for res in ([], "text", None, 7):
            with self.subTest(res=res), self.assertRaisesRegex(ValueError, "resolutionResult is not an object"):
                self.verify(CANONICAL, res)

    def test_member_that_is_not_an_object_is_malformed(self):
        for name in ("didDocument", "didDocumentMetadata"):
            for value in ([], [CANONICAL], "text", 7, False):
                with self.subTest(name=name, value=value), \
                        self.assertRaisesRegex(ValueError, f"{name} is not an object"):
                    self.verify(CANONICAL, {**result(CANONICAL), name: value})

    def test_repository_vectors_pass(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check_vectors.main([]), 0)


class ScratchVectors(unittest.TestCase):
    """Run main() against a scratch root holding a copy of the repository's vectors."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.vectors = self.root / "vectors"
        shutil.copytree(check_vectors.VECTORS, self.vectors)
        patcher = mock.patch.multiple(check_vectors, ROOT=self.root, VECTORS=self.vectors)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, name: str, content: dict) -> None:
        (self.vectors / name).write_text(json.dumps(content), encoding="utf-8")

    def remove_expecting(self, expected: dict) -> None:
        for path in sorted(self.vectors.glob("*.json")):
            if json.loads(path.read_text(encoding="utf-8"))["expected"] == expected:
                path.unlink()

    def run_main(self) -> tuple:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = check_vectors.main([])
        return status, out.getvalue(), err.getvalue()

    def assert_summary(self, out: str, failures: int) -> None:
        count = len(list(self.vectors.glob("*.json")))
        self.assertTrue(out.endswith(f"{count} vectors, {failures} failures\n"), out)

    def test_copied_vectors_pass(self):
        status, out, err = self.run_main()
        self.assertEqual((status, err), (0, ""))
        self.assert_summary(out, 0)

    # The two tests below add a vector to the copied set, so the set still
    # covers both required verdicts and the comparison of the verifier's
    # verdict with `expected` is the only check that can fail.

    def test_expected_reject_for_an_accepted_resolution_fails(self):
        self.write("flipped.json", vector(CANONICAL, REJECT))
        status, out, err = self.run_main()
        self.assertEqual(status, 1)
        self.assertIn("vectors/flipped.json: verifier says accept, "
                      "vector expects reject resolved-id-mismatch", err)
        self.assert_summary(out, 1)

    def test_expected_accept_for_a_substituted_document_fails(self):
        self.write("flipped.json", vector(check_vectors.PINNED_REGISTRY, ACCEPT))
        status, out, err = self.run_main()
        self.assertEqual(status, 1)
        self.assertIn("vectors/flipped.json: verifier says reject resolved-id-mismatch, "
                      "vector expects accept", err)
        self.assert_summary(out, 1)

    def test_set_without_a_negative_vector_fails(self):
        self.remove_expecting(REJECT)
        status, out, err = self.run_main()
        self.assertEqual(status, 1)
        self.assertIn("no vector expects reject resolved-id-mismatch", err)
        self.assert_summary(out, 1)

    def test_set_without_a_positive_vector_fails(self):
        self.remove_expecting(ACCEPT)
        status, out, err = self.run_main()
        self.assertEqual(status, 1)
        self.assertIn("no vector expects accept", err)
        self.assert_summary(out, 1)

    def test_empty_directory_fails(self):
        for path in self.vectors.glob("*.json"):
            path.unlink()
        status, _, err = self.run_main()
        self.assertEqual((status, err), (1, "no vectors under vectors/\n"))

    def test_unknown_expected_verdict_is_malformed(self):
        self.write("extra.json", vector(CANONICAL, {"verdict": "reject", "reason": "other"}))
        status, out, err = self.run_main()
        self.assertEqual(status, 1)
        self.assertIn("vectors/extra.json: malformed vector: unknown expected verdict", err)
        self.assert_summary(out, 1)

    def test_resolution_result_that_is_not_an_object_is_malformed(self):
        shapes = (
            ("resolutionResult", []),
            ("resolutionResult", None),
            ("resolutionResult", "text"),
            ("didDocument", [CANONICAL]),
            ("didDocument", "text"),
            ("didDocumentMetadata", [CANONICAL]),
        )
        for name, value in shapes:
            with self.subTest(name=name, value=value):
                extra = vector(CANONICAL, ACCEPT)
                if name == "resolutionResult":
                    extra[name] = value
                else:
                    extra["resolutionResult"][name] = value
                self.write("extra.json", extra)
                status, out, err = self.run_main()
                self.assertEqual(status, 1)
                self.assertIn(f"vectors/extra.json: malformed vector: {name} is not an object", err)
                self.assert_summary(out, 1)


class CommandLine(unittest.TestCase):
    def run_main(self, argv: list) -> tuple:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as exit_:
            check_vectors.main(argv)
        return exit_.exception.code, out.getvalue(), err.getvalue()

    def test_help_prints_usage_instead_of_running_the_check(self):
        code, out, err = self.run_main(["--help"])
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("usage: "))
        self.assertIn("resolution checks to every vector under vectors/.", out)
        self.assertNotIn(" failures", out)

    def test_unknown_argument_is_refused_without_running_the_check(self):
        code, out, err = self.run_main(["--bogus"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("unrecognized arguments: --bogus", err)


class ScriptDirectoryOffThePath(unittest.TestCase):
    """The script imports check_did_syntax.py when Python leaves its directory off sys.path."""

    def run_script(self, *options: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, *options, str(SCRIPTS / "check_vectors.py")],
            capture_output=True, text=True, cwd=tempfile.gettempdir(), env={**os.environ, **env},
        )

    def assert_passes(self, run: subprocess.CompletedProcess) -> None:
        self.assertEqual((run.returncode, run.stderr), (0, ""))
        self.assertTrue(run.stdout.endswith(" vectors, 0 failures\n"), run.stdout)

    def test_isolated_mode(self):
        self.assert_passes(self.run_script("-I"))

    @unittest.skipUnless(sys.version_info >= (3, 11), "-P and PYTHONSAFEPATH need Python 3.11")
    def test_safe_path_option(self):
        self.assert_passes(self.run_script("-P"))

    @unittest.skipUnless(sys.version_info >= (3, 11), "-P and PYTHONSAFEPATH need Python 3.11")
    def test_safe_path_environment_variable(self):
        self.assert_passes(self.run_script(PYTHONSAFEPATH="1"))


if __name__ == "__main__":
    unittest.main()
