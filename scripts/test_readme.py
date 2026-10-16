#!/usr/bin/env python3
"""Tests for the README's length and staleness rules. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import capture_readme
import check_links

REPO = SCRIPTS.parent
README = REPO / "README.md"
CAPTURES_DIR = REPO / "docs" / "captures"

# A three-part version such as 1.2.0 or a date written as 2026-07-04 in the
# README goes stale when the specification or its registration moves on; the
# specification and docs/status.md carry them. A live badge or a pinned line
# the reader copies may hold one: such a line is listed here exactly as
# written. A two-part revision such as 0.2, or a date written in words, does
# not match.
VERSION_OR_DATE = re.compile(r"v?[0-9]+\.[0-9]+\.[0-9]+|20[0-9]{2}-[0-9]{2}-[0-9]{2}")
ALLOWED_VERSION_LINES: frozenset[str] = frozenset()

MAX_PARAGRAPH_WORDS = 60
# A heading, a list item or a link reference definition starts a block of its own.
BLOCK_START = re.compile(r"^ {0,3}(#{1,6} |[-*+] |[0-9]+[.)] |\[[^\]]+\]:)")


def blocks(text: str) -> list[tuple[int, str]]:
    """Return (first line number, text) for each block of prose outside code blocks.

    Code blocks are read as scripts/check_links.py reads them: a fence closes
    only at a run of the character that opened it at least as long as the
    opening run, and a line indented four or more columns that does not
    continue a paragraph is indented code. A block is a run of non-blank
    lines; a heading, a list item and a link reference definition each start
    a new one."""
    lines = text.splitlines()
    fenced, indented = check_links.code_blocks(lines)
    found: list[tuple[int, list[str]]] = []
    current: tuple[int, list[str]] | None = None
    for number, line in enumerate(lines, start=1):
        if number in fenced or number in indented or not line.strip():
            current = None
            continue
        if current is None or BLOCK_START.match(line):
            current = (number, [])
            found.append(current)
        current[1].append(line)
    return [(number, " ".join(lines)) for number, lines in found]


# Sample output: a label naming the command, then a fenced excerpt of the
# capture scripts/capture_readme.py wrote for it. The excerpt is whole lines of
# the capture in their order; a line holding only the elision mark stands for
# one or more lines left out between two kept ones.
LABEL = re.compile(r"^What `(?P<command>[^`]+)` prints(?P<trimmed>, trimmed)? "
                   r"\(\[full output\]\(\./docs/captures/(?P<name>[a-z0-9-]+)\.txt\)\):$")
ELISION = "..."


def fences(lines: list[str]) -> list[tuple[int, int, str, list[str]]]:
    """Return (opening index, closing index, info string, body lines) for each fenced block.

    Fences are read from the start of the line with the patterns of
    scripts/check_links.py, and a block closes only at a run of the character
    that opened it at least as long as the opening run."""
    found = []
    opening = run = None
    for index, line in enumerate(lines):
        if opening is None:
            m = check_links.OPENING_FENCE.match(line)
            if m:
                opening, run = index, m.group(1) or m.group(2)
            continue
        m = check_links.CLOSING_FENCE.match(line)
        if m and m.group(1)[0] == run[0] and len(m.group(1)) >= len(run):
            info = lines[opening].lstrip(" ")[len(run):].strip()
            found.append((opening, index, info, lines[opening + 1:index]))
            opening = None
    return found


def next_filled(lines: list[str], index: int) -> int | None:
    """Return the index of the first non-blank line after `index`, or None."""
    for later in range(index + 1, len(lines)):
        if lines[later].strip():
            return later
    return None


def outputs(lines: list[str]) -> list[tuple[int, re.Match, list[str] | None]]:
    """Return (line number, label match, excerpt lines or None) for each sample-output label.

    The excerpt is the body of the fenced block that is the next non-blank
    line after the label; None when no fenced block follows it."""
    opened = {opening: body for opening, _, _, body in fences(lines)}
    found = []
    for index, line in enumerate(lines):
        label = LABEL.match(line)
        if label:
            found.append((index + 1, label, opened.get(next_filled(lines, index))))
    return found


def cut_from(excerpt: list[str], capture: list[str]) -> str | None:
    """Return why `excerpt` is not whole lines of `capture` in their order, or None when it is."""
    if not excerpt:
        return "the excerpt is empty"
    if excerpt[0] == ELISION or excerpt[-1] == ELISION:
        return "an elision line opens or closes the excerpt"
    runs: list[list[str]] = [[]]
    for line in excerpt:
        if line == ELISION:
            runs.append([])
        else:
            runs[-1].append(line)
    if any(not run for run in runs):
        return "two elision lines are adjacent"
    start = 0
    for run in runs:
        at = next((i for i in range(start, len(capture) - len(run) + 1)
                   if capture[i:i + len(run)] == run), None)
        if at is None:
            return f"{run[0]!r} and the {len(run) - 1} line(s) after it are not in the capture at this point"
        # An elision line stands for at least one line left out.
        start = at + len(run) + 1
    return None


def capture_lines(name: str) -> list[str]:
    return (CAPTURES_DIR / f"{name}.txt").read_bytes().decode("utf-8").splitlines()


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

    def test_a_fence_closes_only_at_its_own_character_and_length(self):
        long = " ".join(["w"] * 61)
        self.assertEqual(blocks(f"```\n~~~\n```\n{long}\n"), [(4, long)])
        self.assertEqual(blocks(f"~~~\n```\n~~~\n{long}\n"), [(4, long)])
        self.assertEqual(blocks(f"````\n```\n````\n{long}\n"), [(4, long)])
        self.assertEqual(blocks("```\none\n``` x\n~~~\n```\ntwo\n"), [(6, "two")])

    def test_indented_code_is_not_prose(self):
        long = " ".join(["w"] * 61)
        self.assertEqual(blocks(f"text\n\n    {long}\n"), [(1, "text")])
        self.assertEqual(blocks(f"# Title\n    {long}\nafter\n"), [(1, "# Title"), (3, "after")])
        self.assertEqual(blocks(f"- item\n\n      {long}\n"), [(1, "- item")])

    def test_an_indented_line_in_a_paragraph_or_at_a_list_item_content_is_prose(self):
        def words(text):
            return [(n, body.split()) for n, body in blocks(text)]
        self.assertEqual(words("one\n    two\n"), [(1, ["one", "two"])])
        self.assertEqual(words("-   one\n\n    two\n"), [(1, ["-", "one"]), (3, ["two"])])


class ShowsWhatEachCommandPrints(unittest.TestCase):
    def setUp(self):
        self.lines = README.read_text(encoding="utf-8").splitlines()
        self.outputs = outputs(self.lines)

    def test_every_shell_block_is_followed_by_what_it_prints(self):
        bare = []
        for opening, closing, info, body in fences(self.lines):
            if info != "sh":
                continue
            after = next_filled(self.lines, closing)
            label = LABEL.match(self.lines[after]) if after is not None else None
            if label is None or [label["command"]] != body:
                bare.append(f"README.md:{opening + 2}: {' '.join(body)[:60]}")
        self.assertEqual(bare, [])

    def test_each_excerpt_is_cut_from_its_capture_without_changing_a_line(self):
        wrong = []
        for number, label, excerpt in self.outputs:
            path = CAPTURES_DIR / f"{label['name']}.txt"
            if excerpt is None:
                wrong.append(f"README.md:{number}: no fenced block follows the label")
            elif not path.is_file():
                wrong.append(f"README.md:{number}: docs/captures/{label['name']}.txt is missing")
            elif (reason := cut_from(excerpt, capture_lines(label["name"]))) is not None:
                wrong.append(f"README.md:{number}: {reason}")
            elif bool(label["trimmed"]) != (excerpt != capture_lines(label["name"])):
                wrong.append(f"README.md:{number}: the label says 'trimmed' only when lines are left out")
        self.assertEqual(wrong, [])

    def test_each_capture_records_the_command_the_readme_shows(self):
        wrong = []
        for number, label, _ in self.outputs:
            name, command = label["name"], label["command"]
            sidecar_path = CAPTURES_DIR / f"{name}.json"
            if capture_readme.CAPTURES.get(name) != command:
                wrong.append(f"README.md:{number}: capture_readme.py runs another command for {name}")
            if not sidecar_path.is_file() or not (CAPTURES_DIR / f"{name}.txt").is_file():
                wrong.append(f"README.md:{number}: docs/captures/{name}.txt or .json is missing")
                continue
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            if sidecar.get("command") != command:
                wrong.append(f"docs/captures/{name}.json: records another command")
            if sidecar.get("exitCode") != 0:
                wrong.append(f"docs/captures/{name}.json: the command exited {sidecar.get('exitCode')}")
            if sidecar.get("sha256") != hashlib.sha256((CAPTURES_DIR / f"{name}.txt").read_bytes()).hexdigest():
                wrong.append(f"docs/captures/{name}.json: sha256 differs from {name}.txt")
        self.assertEqual(wrong, [])

    def test_every_capture_is_shown_in_the_readme(self):
        shown = sorted(label["name"] for _, label, _ in self.outputs)
        self.assertEqual(shown, sorted(set(shown)), "a capture is shown twice")
        self.assertEqual(shown, sorted(capture_readme.CAPTURES))
        self.assertEqual(sorted(p.stem for p in CAPTURES_DIR.glob("*.txt")), shown)
        self.assertEqual(sorted(p.stem for p in CAPTURES_DIR.glob("*.json")), shown)


class Fences(unittest.TestCase):
    def test_a_fence_closes_only_at_its_own_character_and_length(self):
        lines = ["````sh", "```", "````", "~~~", "```", "~~~~", "~~~ x", "~~~"]
        self.assertEqual(fences(lines), [(0, 2, "sh", ["```"]), (3, 5, "", ["```"]), (6, 7, "x", [])])

    def test_a_fence_with_text_after_it_does_not_close_a_block(self):
        self.assertEqual(fences(["```", "``` x", "```"]), [(0, 2, "", ["``` x"])])


class CutFrom(unittest.TestCase):
    CAPTURE = ["{", '  "id": "did:opena2a:registry:opena2a.org",', '  "type": "TrustAPI"', "  ],", "}"]

    def test_whole_lines_in_order_with_elisions_are_a_cut(self):
        self.assertIsNone(cut_from(self.CAPTURE, self.CAPTURE))
        self.assertIsNone(cut_from(self.CAPTURE[1:3], self.CAPTURE))
        self.assertIsNone(cut_from(["{", ELISION, '  "type": "TrustAPI"', ELISION, "}"], self.CAPTURE))

    def test_a_changed_token_is_not_a_cut(self):
        self.assertIsNotNone(cut_from(["{", ELISION, '  "type": "TrustApi"', ELISION, "}"], self.CAPTURE))

    def test_lines_out_of_order_are_not_a_cut(self):
        self.assertIsNotNone(cut_from(['  "type": "TrustAPI"', ELISION, '  "id": "did:opena2a:registry:opena2a.org",'],
                                      self.CAPTURE))

    def test_an_elision_at_either_end_or_standing_for_no_line_is_not_a_cut(self):
        self.assertIsNotNone(cut_from([ELISION, "}"], self.CAPTURE))
        self.assertIsNotNone(cut_from(["{", ELISION], self.CAPTURE))
        self.assertIsNotNone(cut_from(["{", ELISION, ELISION, "}"], self.CAPTURE))
        self.assertIsNotNone(cut_from(["{", ELISION, '  "id": "did:opena2a:registry:opena2a.org",'], self.CAPTURE))
        self.assertIsNotNone(cut_from([], self.CAPTURE))


if __name__ == "__main__":
    unittest.main()
