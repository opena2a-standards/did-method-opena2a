#!/usr/bin/env python3
"""Tests for check_did_syntax.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import check_did_syntax

REPO = SCRIPTS.parent
SPEC_NAME = "did-method-opena2a.md"


class ReadsTheFamilyCheckFiles(unittest.TestCase):
    def test_reads_markdown_and_json_files_outside_the_original_four_sources(self):
        names = {p.relative_to(REPO).as_posix() for p in check_did_syntax.sources()}
        for name in ("MAINTAINERS.md", "registries/resource-types.json",
                     "examples/conformance/agent.json", "examples/agent.json",
                     "README.md", "CHANGELOG.md", SPEC_NAME):
            self.assertIn(name, names)


class PercentEncodedRuleDocumentation(unittest.TestCase):
    """The unreleased CHANGELOG entry names the places that state the
    percent-encoded rule, and each place it names states it."""

    RULE = ("fails when a percent-encoded `did:opena2a` string is spelled out "
            "anywhere other than Section 3.1.1")

    @staticmethod
    def flat(text: str) -> str:
        return " ".join(text.split())

    def test_each_place_the_changelog_names_states_the_rule(self):
        changelog = self.flat((REPO / "CHANGELOG.md").read_text(encoding="utf-8").split("\n## [", 2)[1])
        subjects = [s.split(" now also say", 1)[0] for s in changelog.split(". ")
                    if "now also say that it " + self.RULE in s]
        self.assertEqual(len(subjects), 1, subjects)
        subject = subjects[0]
        names = re.findall(r"`([^`]+\.md)`", subject)
        if re.search(r"\bREADME\b", subject):
            names.append("README.md")
        self.assertTrue(names, subject)
        for name in names:
            text = self.flat((REPO / name).read_text(encoding="utf-8"))
            self.assertTrue(self.RULE in text, f"{name} does not state the rule")
        if "Section 3.1.2" in subject:
            spec = (REPO / SPEC_NAME).read_text(encoding="utf-8")
            section = spec.split("\n### 3.1.2 ", 1)[1].split("\n#", 1)[0]
            self.assertTrue(self.RULE in self.flat(section), "Section 3.1.2 does not state the rule")


class ScratchRepository(unittest.TestCase):
    """Run main() against a scratch root holding a copy of the specification."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copy(REPO / SPEC_NAME, self.root / SPEC_NAME)
        patcher = mock.patch.multiple(check_did_syntax, ROOT=self.root, SPEC=self.root / SPEC_NAME)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run_main(self) -> tuple:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = check_did_syntax.main([])
        return status, out.getvalue(), err.getvalue()

    def test_specification_alone_passes(self):
        status, out, err = self.run_main()
        self.assertEqual((status, err), (0, ""))
        self.assertIn(" in 1 files,", out)

    def test_non_parsing_did_in_a_registries_json_file_fails(self):
        self.write("registries/extra.json", '{"id": "did:opena2a:Agent:example"}\n')
        status, _, err = self.run_main()
        self.assertEqual(status, 1)
        self.assertIn("does not parse: did:opena2a:Agent:example (registries/extra.json:1)", err)

    def test_non_parsing_did_in_nested_markdown_fails(self):
        self.write("examples/conformance/notes.md", "See did:opena2a:agent: for the shape.\n")
        status, _, err = self.run_main()
        self.assertEqual(status, 1)
        self.assertIn("examples/conformance/notes.md:1", err)

    def test_percent_encoded_did_outside_section_3_1_1_fails(self):
        self.write("MAINTAINERS.md", "did:opena2a:skill:web%2Dresearch\n")
        status, _, err = self.run_main()
        self.assertEqual(status, 1)
        self.assertIn("percent-encoded form outside Section 3.1.1", err)
        self.assertIn("MAINTAINERS.md:1", err)

    def test_hidden_directories_are_not_read(self):
        self.write(".github/notes.md", "did:opena2a:Agent:example\n")
        status, _, err = self.run_main()
        self.assertEqual((status, err), (0, ""))


class CommandLine(unittest.TestCase):
    def run_main(self, argv: list) -> tuple:
        # Python 3.14 argparse colours its output when FORCE_COLOR is set.
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"PYTHON_COLORS": "0"}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                self.assertRaises(SystemExit) as exit_:
            check_did_syntax.main(argv)
        return exit_.exception.code, out.getvalue(), err.getvalue()

    def test_help_prints_usage_instead_of_running_the_check(self):
        code, out, err = self.run_main(["--help"])
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("usage: "))
        self.assertIn("- the vectors below parse, or fail to parse, as listed;", out)
        self.assertNotIn("distinct did:opena2a strings", out)

    def test_unknown_argument_is_refused_without_running_the_check(self):
        code, out, err = self.run_main(["--bogus"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("unrecognized arguments: --bogus", err)


if __name__ == "__main__":
    unittest.main()
