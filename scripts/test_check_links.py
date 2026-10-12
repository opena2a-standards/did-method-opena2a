#!/usr/bin/env python3
"""Tests for check_links.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import check_links


def targets(text: str) -> list:
    return [target for _, target in check_links.link_targets(text)]


class BareUrls(unittest.TestCase):
    def test_bare_url_in_prose_is_a_target(self):
        self.assertEqual(targets("See https://example.org/spec for details.\n"),
                         ["https://example.org/spec"])

    def test_trailing_punctuation_is_not_part_of_the_url(self):
        self.assertEqual(targets("Read https://example.org/a/b.\n"), ["https://example.org/a/b"])
        self.assertEqual(targets("(see https://example.org/x)\n"), ["https://example.org/x"])
        self.assertEqual(targets("At https://example.org/x, then\n"), ["https://example.org/x"])

    def test_balanced_parenthesis_stays_in_the_url(self):
        self.assertEqual(targets("https://example.org/wiki/Foo_(bar)\n"),
                         ["https://example.org/wiki/Foo_(bar)"])

    def test_bare_url_in_code_is_not_a_target(self):
        self.assertEqual(targets("Run `curl https://example.org/x` first.\n"), [])
        self.assertEqual(targets("```\ncurl https://example.org/x\n```\n"), [])

    def test_linked_url_is_read_once(self):
        text = ("[https://example.org/a](https://example.org/a) and <https://example.org/b>\n"
                "[ref]: https://example.org/c\n")
        self.assertEqual(targets(text),
                         ["https://example.org/a", "https://example.org/b", "https://example.org/c"])

    def test_bare_url_ends_at_whitespace_or_less_than_only(self):
        self.assertEqual(targets("https://example.org/a>b\n"), ["https://example.org/a>b"])
        self.assertEqual(targets("https://example.org/a<b\n"), ["https://example.org/a"])


class InlineLinks(unittest.TestCase):
    def test_balanced_parenthesis_stays_in_the_target(self):
        self.assertEqual(targets("[Foo](https://example.org/wiki/Foo_(bar))\n"),
                         ["https://example.org/wiki/Foo_(bar)"])
        self.assertEqual(targets("[spec](./spec_(draft).md#intro)\n"), ["./spec_(draft).md#intro"])

    def test_unbalanced_parenthesis_is_not_a_link(self):
        self.assertEqual(targets("[a](b(c)\n"), [])


class LongLines(unittest.TestCase):
    """A line built to make a backtracking pattern retry from every position."""

    LENGTH = 120_000
    SECONDS = 1.0

    def assert_linear(self, head: str, unit: str, tail: str, want: str) -> None:
        line = head + unit * (self.LENGTH // len(unit)) + tail + "\n"
        start = time.perf_counter()
        found = targets(line)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, self.SECONDS, f"{unit!r} x {self.LENGTH // len(unit)}")
        self.assertIn(want, found)

    def test_run_of_open_brackets(self):
        self.assert_linear("[a](b) ", "[", "", "b")

    def test_run_of_unclosed_inline_links(self):
        self.assert_linear("", "[a](", " [a](b)", "b")

    def test_run_of_unclosed_link_destinations(self):
        self.assert_linear("", "](", " [a](b)", "b")

    def test_run_of_unclosed_autolinks(self):
        self.assert_linear("", "<https://a", " <https://example.org/x>", "https://example.org/x")

    def test_bare_url_ending_in_closing_parentheses(self):
        self.assert_linear("https://example.org/x", ")", "", "https://example.org/x")


if __name__ == "__main__":
    unittest.main()
