#!/usr/bin/env python3
"""Tests for check_examples.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import contextlib
import io
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


if __name__ == "__main__":
    unittest.main()
