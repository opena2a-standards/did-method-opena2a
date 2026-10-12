#!/usr/bin/env python3
"""Tests for gen_registries.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import gen_registries


def help_text() -> str:
    env = dict(os.environ, NO_COLOR="1", PYTHON_COLORS="0")
    env.pop("FORCE_COLOR", None)
    run = subprocess.run(
        [sys.executable, str(SCRIPTS / "gen_registries.py"), "--help"],
        capture_output=True, text=True, check=True, env=env,
    )
    return run.stdout


def written_files() -> list:
    """Run the generator against a scratch root and list what it wrote."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with mock.patch.multiple(gen_registries, ROOT=root, REGISTRIES=root / "registries"):
            with mock.patch.object(sys, "argv", ["gen_registries.py"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    status = gen_registries.main()
        if status != 0:
            raise AssertionError(f"generator exited {status}")
        return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


class HelpNamesTheGeneratedFiles(unittest.TestCase):
    def test_help_names_every_file_the_generator_writes(self):
        files = written_files()
        self.assertTrue(files, "the generator wrote nothing")
        text = help_text()
        for name in files:
            self.assertIn(name, text)

    def test_help_does_not_name_the_file_after_the_marker_id(self):
        self.assertNotIn("registries/<id>.json", help_text())


if __name__ == "__main__":
    unittest.main()
