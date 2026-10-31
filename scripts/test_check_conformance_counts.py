#!/usr/bin/env python3
"""Tests for check_conformance_counts.py. python3 standard library and git only.

Each phrasing the check reads is built here in a scratch tree and checked
against scratch atx-conformance, atp-conformance and aip-conformance suites:
git repositories whose commits ship fixtures of a known number, fixtureType
and identifier content. A stated count that differs from a suite at the commit
it names is asserted to exit 1 naming the file, the line and the kind of
count. The delivered docs/use-cases.md is asserted to state each suite's
counts at one named commit, and the delivered README.md and docs/ pass against
suites of the shape they state.

Set ATX_CONFORMANCE_SUITE, ATP_CONFORMANCE_SUITE and AIP_CONFORMANCE_SUITE to
git clones of the three suites to also check the delivered documents against
the real suites; that test is skipped otherwise.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent
CHECK = SCRIPTS / "check_conformance_counts.py"
sys.path.insert(0, str(SCRIPTS))

import check_conformance_counts as counts

AGENT = "did:opena2a:agent:a2a-server"
LINKS = {name: f"[{name}](https://github.com/opena2a-standards/{name})" for name in counts.SUITES}
WITH_ID = " with a did:opena2a identifier"


def sentence(atx: int = 41, atp: int = 14, challenge_response: int = 14, total: int = 17,
             trust_score: int = 3, commits: dict[str, str] | None = None) -> str:
    """docs/use-cases.md with the sentence on line 3; a suite missing from commits names none, as before."""
    commits = commits or {}

    def at(name: str) -> str:
        return f" at commit `{commits[name]}`" if name in commits else ""

    return (
        "# Use cases\n\n"
        "What you can check yourself: `did:opena2a` identifiers appear in byte-pinned fixtures of "
        f"{LINKS['atx-conformance']} (all {atx} fixtures{at('atx-conformance')}), "
        f"{LINKS['atp-conformance']} (all {atp} fixtures{at('atp-conformance')}) and "
        f"{LINKS['aip-conformance']} (the {challenge_response} challenge-response fixtures of its "
        f"{total}{at('aip-conformance')}; the {trust_score} trust-score fixtures carry none), "
        "each with Go and Python reference verifiers.\n"
    )


class CountsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="did-method-conformance-counts-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # Only what git needs, no user or system git configuration, and no
        # repository found above the scratch directory.
        self.env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.tmp),
            "GIT_CEILING_DIRECTORIES": os.path.realpath(self.tmp),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "fixture author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "fixture author",
            "GIT_COMMITTER_EMAIL": "author@example.invalid",
        }
        self.family = self.tmp / "family"
        for name in counts.SUITES:
            (self.family / name).mkdir(parents=True)
            self.git(name, "init", "-q")
        self.trees = 0

    def git(self, name: str, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.family / name), *args],
            env=self.env, capture_output=True, text=True, check=True,
        )
        return proc.stdout.strip()

    def commit(self, name: str, *, plain: int = 0, plain_bare: int = 0, challenge_response: int = 0,
               challenge_response_bare: int = 0, trust_score: int = 0, trust_score_carrying: int = 0,
               extra: dict[str, str] | None = None) -> str:
        """Commit a fixtures/ tree of this shape to one scratch suite; return its short id.

        plain and challenge_response fixtures carry an identifier and trust_score
        fixtures carry none; the _bare and _carrying counts add the opposite case.
        """
        fixtures = self.family / name / "fixtures"
        shutil.rmtree(fixtures, ignore_errors=True)
        fixtures.mkdir()
        shapes = [("plain", None, True, plain), ("plain-bare", None, False, plain_bare),
                  ("challenge-response", "challengeResponse", True, challenge_response),
                  ("challenge-response-bare", "challengeResponse", False, challenge_response_bare),
                  ("trust-score", "trustScoreComposition", False, trust_score),
                  ("trust-score-carrying", "trustScoreComposition", True, trust_score_carrying)]
        for prefix, fixture_type, carrying, number in shapes:
            for index in range(number):
                body: dict[str, object] = {"name": f"{prefix}-{index}"}
                if fixture_type:
                    body["fixtureType"] = fixture_type
                if carrying:
                    body["subject"] = AGENT
                (fixtures / f"{prefix}-{index}.json").write_text(json.dumps(body) + "\n")
        for path, text in (extra or {}).items():
            target = self.family / name / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        self.git(name, "add", "--all")
        self.trees += 1
        self.git(name, "commit", "-q", "--allow-empty", "-m", f"tree {self.trees}")
        return self.git(name, "rev-parse", "--short=7", "HEAD")

    def commit_all(self, atx: int = 41, atp: int = 14, challenge_response: int = 14,
                   trust_score: int = 3) -> dict[str, str]:
        """One commit per suite in the shape the sentence states; return each suite's short id."""
        return {
            "atx-conformance": self.commit("atx-conformance", plain=atx),
            "atp-conformance": self.commit("atp-conformance", plain=atp),
            "aip-conformance": self.commit("aip-conformance", challenge_response=challenge_response,
                                           trust_score=trust_score),
        }

    def tree(self, use_cases: str | None, files: dict[str, str] | None = None) -> Path:
        """A scratch tree holding docs/use-cases.md (unless None) and any other files given."""
        root = self.tmp / f"tree-{len(list(self.tmp.glob('tree-*')))}"
        (root / "docs").mkdir(parents=True)
        if use_cases is not None:
            (root / "docs" / "use-cases.md").write_text(use_cases)
        for path, text in (files or {}).items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        return root

    def run_check(self, root: Path, *suite_args: str) -> tuple[int, str]:
        args = list(suite_args) or ["--family-dir", str(self.family)]
        proc = subprocess.run(
            [sys.executable, "-B", str(CHECK), "--root", str(root), *args],
            env=self.env, capture_output=True, text=True,
        )
        return proc.returncode, proc.stdout + proc.stderr

    def assertFails(self, root: Path, *reported: str, args: tuple[str, ...] = ()) -> None:
        code, out = self.run_check(root, *args)
        self.assertEqual(code, 1, out)
        for text in reported:
            self.assertIn(text, out)

    def assertPasses(self, root: Path, *reported: str, args: tuple[str, ...] = ()) -> str:
        code, out = self.run_check(root, *args)
        self.assertEqual(code, 0, out)
        for text in reported:
            self.assertIn(text, out)
        return out


class DeliveredTest(CountsTest):
    def stated(self) -> dict[str, counts.Part]:
        text = (REPO / "docs" / "use-cases.md").read_text(encoding="utf-8")
        stated: dict[str, counts.Part] = {}
        for part in counts.parts(text):
            if part.suite in counts.SUITES and part.counts:
                self.assertNotIn(part.suite, stated, f"docs/use-cases.md states {part.suite} counts once")
                self.assertTrue(part.commits, f"the {part.suite} counts name no commit")
                stated[part.suite] = part
        self.assertEqual(sorted(stated), sorted(counts.SUITES))
        return stated

    def values(self, part: counts.Part) -> dict[str, int]:
        return {kind: value for kind, value, _ in part.counts}

    def delivered_tree(self, commits: dict[str, str]) -> Path:
        """README.md and docs/ as delivered, with each named suite commit replaced by a scratch one."""
        stated = self.stated()
        files = {}
        for path in [REPO / "README.md", *sorted((REPO / "docs").rglob("*.md"))]:
            text = path.read_text(encoding="utf-8")
            for name, part in stated.items():
                text = text.replace(f"`{part.commits[0][0]}`", f"`{commits[name]}`")
            files[path.relative_to(REPO).as_posix()] = text
        return self.tree(None, files)

    def scratch_like_delivered(self, challenge_response_extra: int = 0) -> dict[str, str]:
        stated = self.stated()
        atx = self.values(stated["atx-conformance"])
        atp = self.values(stated["atp-conformance"])
        aip = self.values(stated["aip-conformance"])
        return {
            "atx-conformance": self.commit("atx-conformance", plain=atx["fixtures"]),
            "atp-conformance": self.commit("atp-conformance", plain=atp["fixtures"]),
            "aip-conformance": self.commit(
                "aip-conformance",
                challenge_response=aip["challenge-response fixtures"] + challenge_response_extra,
                trust_score=aip["trust-score fixtures"]),
        }

    def test_the_delivered_page_states_each_suite_at_one_named_commit_and_the_counts_agree(self):
        stated = self.stated()
        for name, part in stated.items():
            self.assertEqual(len({commit for commit, _ in part.commits}), 1, (name, part.commits))
        for name in ("atx-conformance", "atp-conformance"):
            values = self.values(stated[name])
            self.assertEqual(values["fixtures"], values["fixtures" + WITH_ID], name)
        aip = self.values(stated["aip-conformance"])
        self.assertEqual(aip["fixtures"], aip["challenge-response fixtures"] + aip["trust-score fixtures"])
        self.assertEqual(aip["challenge-response fixtures"], aip["challenge-response fixtures" + WITH_ID])
        self.assertEqual(aip["trust-score fixtures" + WITH_ID], 0)

    def test_the_delivered_documents_pass_against_suites_of_the_shape_they_state(self):
        self.assertPasses(self.delivered_tree(self.scratch_like_delivered()), "9 stated value(s) checked")

    def test_the_delivered_documents_fail_against_a_suite_that_differs_at_the_named_commit(self):
        part = self.stated()["aip-conformance"]
        values = self.values(part)
        line = next(line for kind, _, line in part.counts if kind == "fixtures")
        commits = self.scratch_like_delivered(challenge_response_extra=2)
        self.assertFails(
            self.delivered_tree(commits),
            f"docs/use-cases.md:{line} states {values['fixtures']} (fixtures) for aip-conformance "
            f"at {commits['aip-conformance']}, which has {values['fixtures'] + 2}",
        )

    @unittest.skipUnless(
        all(os.environ.get(f"{name.split('-')[0].upper()}_CONFORMANCE_SUITE") for name in counts.SUITES),
        "ATX_CONFORMANCE_SUITE, ATP_CONFORMANCE_SUITE and AIP_CONFORMANCE_SUITE not all set",
    )
    def test_the_delivered_documents_state_the_real_suite_counts(self):
        args = []
        for name in counts.SUITES:
            args += ["--suite", f"{name}={os.environ[name.split('-')[0].upper() + '_CONFORMANCE_SUITE']}"]
        self.assertPasses(REPO, "9 stated value(s) checked", args=tuple(args))


class PhrasingTest(CountsTest):
    def test_counts_equal_to_the_suites_at_the_named_commits_pass(self):
        commits = self.commit_all()
        self.assertPasses(self.tree(sentence(commits=commits)), "9 stated value(s) checked across 3 suites")

    def test_the_suites_may_be_given_one_by_one(self):
        commits = self.commit_all()
        args = []
        for name in counts.SUITES:
            args += ["--suite", f"{name}={self.family / name}"]
        self.assertPasses(self.tree(sentence(commits=commits)), "9 stated value(s) checked", args=tuple(args))

    def test_the_sentence_as_it_read_before_fails_for_each_suite(self):
        # all 25 atx-conformance fixtures, all 14 atp-conformance fixtures, 4 of 7 aip-conformance; no commit named.
        commits = self.commit_all()
        self.assertFails(
            self.tree(sentence(25, 14, 4, 7, 3)),
            f"docs/use-cases.md:3 states 25 (fixtures) for atx-conformance and names no commit; "
            f"at HEAD {commits['atx-conformance']} the suite has 41",
            "docs/use-cases.md:3 states 14 (fixtures) for atp-conformance and names no commit",
            f"docs/use-cases.md:3 states 4 (challenge-response fixtures) for aip-conformance and names "
            f"no commit; at HEAD {commits['aip-conformance']} the suite has 14",
            "docs/use-cases.md:3 states 7 (fixtures) for aip-conformance and names no commit",
        )

    def test_a_suite_whose_count_names_no_commit_fails_alone(self):
        commits = self.commit_all()
        del commits["atp-conformance"]
        code, out = self.run_check(self.tree(sentence(commits=commits)))
        self.assertEqual(code, 1, out)
        self.assertIn("states 14 (fixtures) for atp-conformance and names no commit", out)
        self.assertNotIn("for atx-conformance", out)
        self.assertNotIn("for aip-conformance", out)

    def test_a_stale_all_count_fails_on_the_total_and_on_the_fixtures_carrying_an_identifier(self):
        commits = self.commit_all()
        at = commits["atx-conformance"]
        self.assertFails(
            self.tree(sentence(40, commits=commits)),
            f"docs/use-cases.md:3 states 40 (fixtures) for atx-conformance at {at}, which has 41",
            f"docs/use-cases.md:3 states 40 (fixtures{WITH_ID}) for atx-conformance at {at}, which has 41",
        )

    def test_all_fails_when_a_fixture_carries_no_identifier(self):
        commits = self.commit_all()
        commits["atx-conformance"] = self.commit("atx-conformance", plain=40, plain_bare=1)
        self.assertFails(
            self.tree(sentence(commits=commits)),
            f"states 41 (fixtures{WITH_ID}) for atx-conformance at {commits['atx-conformance']}, which has 40",
        )

    def test_carry_none_fails_when_a_trust_score_fixture_carries_an_identifier(self):
        commits = self.commit_all()
        commits["aip-conformance"] = self.commit("aip-conformance", challenge_response=14, trust_score=2,
                                                 trust_score_carrying=1)
        self.assertFails(
            self.tree(sentence(commits=commits)),
            f"states 0 (trust-score fixtures{WITH_ID}) for aip-conformance at {commits['aip-conformance']}, "
            "which has 1",
        )

    def test_of_its_fails_on_a_stale_total_or_class_count(self):
        commits = self.commit_all()
        at = commits["aip-conformance"]
        self.assertFails(self.tree(sentence(total=16, commits=commits)),
                         f"states 16 (fixtures) for aip-conformance at {at}, which has 17")
        self.assertFails(self.tree(sentence(challenge_response=13, commits=commits)),
                         f"states 13 (challenge-response fixtures) for aip-conformance at {at}, which has 14")

    def test_of_its_fails_when_a_challenge_response_fixture_carries_no_identifier(self):
        commits = self.commit_all()
        commits["aip-conformance"] = self.commit("aip-conformance", challenge_response=13,
                                                 challenge_response_bare=1, trust_score=3)
        self.assertFails(
            self.tree(sentence(commits=commits)),
            f"states 14 (challenge-response fixtures{WITH_ID}) for aip-conformance at "
            f"{commits['aip-conformance']}, which has 13",
        )

    def test_a_count_read_at_an_older_commit_passes_and_says_the_suite_has_moved(self):
        older = self.commit("atx-conformance", plain=25)
        commits = self.commit_all()
        commits["atx-conformance"] = older
        out = self.assertPasses(self.tree(sentence(25, commits=commits)), "9 stated value(s) checked")
        head = self.git("atx-conformance", "rev-parse", "--short=7", "HEAD")
        self.assertIn(f"at HEAD {head} the suite ships 41", out)

    def test_a_commit_the_suite_does_not_have_fails(self):
        commits = self.commit_all()
        commits["atp-conformance"] = "0000000"
        self.assertFails(self.tree(sentence(commits=commits)),
                         "names atp-conformance commit 0000000, which the suite checkout at",
                         "does not resolve to one commit")

    def test_a_commit_outside_the_history_of_the_suite_head_fails(self):
        commits = self.commit_all()
        branch = self.git("atx-conformance", "rev-parse", "--abbrev-ref", "HEAD")
        self.git("atx-conformance", "checkout", "-q", "-b", "side")
        commits["atx-conformance"] = self.commit("atx-conformance", plain=42)
        self.git("atx-conformance", "checkout", "-q", branch)
        self.assertFails(self.tree(sentence(42, commits=commits)),
                         f"names atx-conformance commit {commits['atx-conformance']}, which is not in the "
                         "history of the suite checkout's HEAD")

    def test_two_commits_in_one_suite_part_fail(self):
        commits = self.commit_all()
        second = self.commit("aip-conformance", challenge_response=14, trust_score=3)
        text = sentence(commits=commits).replace("trust-score fixtures carry none",
                                                 f"trust-score fixtures carry none at commit `{second}`")
        self.assertFails(self.tree(text), "docs/use-cases.md:3 names 2 aip-conformance commits")

    def test_a_section_number_is_not_a_count(self):
        commits = self.commit_all()
        text = sentence(commits=commits) + (
            "\nThe Section 6.5 fixtures of atx-conformance and the Section 5.1 challenge-response "
            "fixtures of aip-conformance are read by the same verifiers.\n"
        )
        self.assertPasses(self.tree(text), "9 stated value(s) checked")

    def test_fenced_code_is_not_read(self):
        commits = self.commit_all()
        text = sentence(commits=commits) + (
            "\n```\natx-conformance\nsummary: 2 pass, 0 fail (2 fixtures)\n```\n"
        )
        self.assertPasses(self.tree(text), "9 stated value(s) checked")

    def test_a_line_opening_with_an_inline_code_span_is_not_a_fence(self):
        commits = self.commit_all()
        text = sentence(40, commits=commits).replace("# Use cases\n", "# Use cases\n\n```code``` comes first here.\n")
        self.assertFails(self.tree(text), "states 40 (fixtures) for atx-conformance")

    def test_a_count_before_any_suite_is_named_fails(self):
        commits = self.commit_all()
        text = sentence(commits=commits) + "\nThe suites ship 72 fixtures.\n"
        self.assertFails(self.tree(text),
                         "docs/use-cases.md:5 states 72 (fixtures) before naming a conformance suite")

    def test_a_count_for_a_suite_this_check_does_not_read_fails(self):
        commits = self.commit_all()
        text = sentence(commits=commits) + (
            "\n[aap-conformance](https://github.com/opena2a-standards/aap-conformance) ships 9 fixtures.\n"
        )
        self.assertFails(self.tree(text),
                         "docs/use-cases.md:5 states 9 (fixtures) for aap-conformance, which this check does not read")

    def test_a_count_wrapped_onto_the_next_line_is_read_and_reported_there(self):
        commits = self.commit_all()
        text = sentence(commits=commits).replace(" (all 14 fixtures", "\n(all 13 fixtures")
        self.assertFails(self.tree(text),
                         f"docs/use-cases.md:4 states 13 (fixtures) for atp-conformance at "
                         f"{commits['atp-conformance']}, which has 14")

    def test_a_count_in_the_readme_or_another_page_is_read(self):
        commits = self.commit_all()
        stale = (f"# Title\n\n{LINKS['atx-conformance']} at commit `{commits['atx-conformance']}` "
                 "ships 40 fixtures.\n")
        self.assertFails(self.tree(sentence(commits=commits), {"README.md": stale}),
                         f"README.md:3 states 40 (fixtures) for atx-conformance at {commits['atx-conformance']}")
        self.assertFails(self.tree(sentence(commits=commits), {"docs/notes/suites.md": stale}),
                         "docs/notes/suites.md:3 states 40 (fixtures) for atx-conformance")

    def test_a_page_that_states_no_count_for_a_suite_fails_instead_of_passing_vacuously(self):
        commits = self.commit_all()
        text = sentence(commits=commits).replace(f" (all 14 fixtures at commit `{commits['atp-conformance']}`)", "")
        self.assertFails(self.tree(text), "docs/use-cases.md states no atp-conformance count")

    def test_a_missing_use_cases_page_fails(self):
        self.commit_all()
        self.assertFails(self.tree(None), "docs/use-cases.md is missing")

    def test_a_suite_with_no_checkout_given_fails(self):
        commits = self.commit_all()
        args = ("--suite", f"atx-conformance={self.family / 'atx-conformance'}",
                "--suite", f"aip-conformance={self.family / 'aip-conformance'}")
        self.assertFails(self.tree(sentence(commits=commits)),
                         "no checkout of atp-conformance was given", args=args)

    def test_a_suite_argument_that_is_not_name_equals_path_is_refused(self):
        self.commit_all()
        code, out = self.run_check(self.tree(sentence()), "--suite", "atx-conformance")
        self.assertEqual(code, 2, out)
        self.assertIn("--suite takes NAME=PATH", out)

    def test_a_suite_path_that_is_not_a_git_checkout_fails(self):
        commits = self.commit_all()
        plain = self.tmp / "plain"
        (plain / "fixtures").mkdir(parents=True)
        args = ("--family-dir", str(self.family), "--suite", f"atp-conformance={plain}")
        self.assertFails(self.tree(sentence(commits=commits)), "(atp-conformance) is not a git checkout", args=args)

    def test_a_commit_that_ships_no_fixtures_fails_instead_of_passing_vacuously(self):
        commits = self.commit_all()
        commits["atp-conformance"] = self.commit("atp-conformance")
        self.assertFails(self.tree(sentence(atp=0, commits=commits)),
                         f"names atp-conformance commit {commits['atp-conformance']}, which ships no fixtures")

    def test_only_json_files_directly_under_fixtures_are_counted(self):
        commits = self.commit_all()
        commits["atx-conformance"] = self.commit(
            "atx-conformance", plain=41,
            extra={"fixtures/load-errors/truncated.json": "{\n", "fixtures/NOTES.md": f"{AGENT}\n"})
        self.assertPasses(self.tree(sentence(commits=commits)), "9 stated value(s) checked")


if __name__ == "__main__":
    unittest.main()
