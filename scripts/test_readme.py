#!/usr/bin/env python3
"""Tests for the README's length and staleness rules. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"

# A three-part version such as 1.2.0 or a date written as 2026-07-04 in the
# README goes stale when the specification or its registration moves on; the
# specification and docs/status.md carry them. A live badge or a pinned line
# the reader copies may hold one: such a line is listed here exactly as
# written. A two-part revision such as 0.2, or a date written in words, does
# not match.
VERSION_OR_DATE = re.compile(r"v?[0-9]+\.[0-9]+\.[0-9]+|20[0-9]{2}-[0-9]{2}-[0-9]{2}")
ALLOWED_VERSION_LINES: frozenset[str] = frozenset()

MAX_PARAGRAPH_WORDS = 60
FENCE = re.compile(r"^ {0,3}(```|~~~)")
# A heading, a list item or a link reference definition starts a block of its own.
BLOCK_START = re.compile(r"^ {0,3}(#{1,6} |[-*+] |[0-9]+[.)] |\[[^\]]+\]:)")


def blocks(text: str) -> list[tuple[int, str]]:
    """Return (first line number, text) for each block of prose outside fenced code.

    A block is a run of non-blank lines; a heading, a list item and a link
    reference definition each start a new one."""
    found: list[tuple[int, list[str]]] = []
    in_fence = False
    current: tuple[int, list[str]] | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            current = None
            continue
        if in_fence or not line.strip():
            current = None
            continue
        if current is None or BLOCK_START.match(line):
            current = (number, [])
            found.append(current)
        current[1].append(line)
    return [(number, " ".join(lines)) for number, lines in found]


class StatesNoVersionOrDate(unittest.TestCase):
    def test_no_readme_line_holds_a_version_or_a_date(self):
        lines = README.read_text(encoding="utf-8").splitlines()
        stale = [f"README.md:{n}: {line[:80]}"
                 for n, line in enumerate(lines, start=1)
                 if VERSION_OR_DATE.search(line) and line not in ALLOWED_VERSION_LINES]
        self.assertEqual(stale, [])

    def test_the_check_matches_a_version_and_a_date(self):
        self.assertTrue(VERSION_OR_DATE.search("see AIP-SPEC 1.2.0-draft Section 3.2"))
        self.assertTrue(VERSION_OR_DATE.search("(merged 2026-07-04)"))
        self.assertIsNone(VERSION_OR_DATE.search("spec Section 4.2"))


class KeepsParagraphsShort(unittest.TestCase):
    def test_no_readme_paragraph_is_over_the_word_limit(self):
        long = [f"README.md:{n}: {len(body.split())} words"
                for n, body in blocks(README.read_text(encoding="utf-8"))
                if len(body.split()) > MAX_PARAGRAPH_WORDS]
        self.assertEqual(long, [])

    def test_blocks_split_on_blank_lines_headings_and_list_items(self):
        text = "# Title\n\none two\nthree\n\n- item one\n- item two\n\n```\nfour five\n```\n"
        self.assertEqual(blocks(text), [(1, "# Title"), (3, "one two three"),
                                        (6, "- item one"), (7, "- item two")])


if __name__ == "__main__":
    unittest.main()
