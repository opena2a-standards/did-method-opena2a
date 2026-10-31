#!/usr/bin/env python3
"""Check the conformance-suite fixture counts the documents state against each suite, at the commit they name.

docs/use-cases.md states in which fixtures of atx-conformance, atp-conformance
and aip-conformance `did:opena2a` identifiers appear, how many fixtures that
is, and the commit of each suite the counts were read at. Those are
measurements taken in other repositories, so they are checked here rather than
maintained by hand: the page stated 25 atx-conformance fixtures while the suite
shipped 41, and 4 of 7 aip-conformance fixtures while it shipped 14 of 17, and
nothing caught it. This check reads each suite at the commit the sentence
names and fails when a stated count differs.

It reads README.md and the Markdown files under docs/, outside fenced code
blocks. A count belongs to the conformance suite named before it in the same
paragraph, and is read at the commit named in that suite's part of the
paragraph, as in

    [atx-conformance](...) (all 41 fixtures at commit `2328506`)

A fixture is a .json file directly under the suite's fixtures/; it carries an
identifier when its text holds a `did:opena2a:` DID, and its class is its
fixtureType. The counts say where identifiers appear, so the phrasings read are

  "all 41 fixtures"                         41 fixtures, every one carrying an identifier
  "the 14 challenge-response fixtures of its 17"
                                            17 fixtures, 14 of them challengeResponse,
                                            each of those carrying an identifier
  "the 3 trust-score fixtures carry none"   3 trustScoreComposition fixtures, none
                                            carrying an identifier
  "41 fixtures", "41 byte-pinned fixtures"  41 fixtures
  "14 challenge-response fixtures"          14 challengeResponse fixtures

A section number, as in "the Section 6.5 fixtures", is not a count.

It fails when a stated count differs from the suite at the named commit; when
a count names no commit, two commits, or no suite before it; when the named
commit is not in the history of the suite checkout's HEAD or ships no
fixtures; when no checkout of a suite whose count is stated was given; and
when docs/use-cases.md states no count for one of the three suites, so it
never passes vacuously. When a suite's HEAD ships a different number of
fixtures than the named commit, it says so and passes: the sentence is true
at the commit it names.

This repository does not contain the fixtures, so the caller supplies each
suite as a git clone with its history, because the check reads commits rather
than working trees:

    python3 scripts/check_conformance_counts.py --suite atx-conformance=<path> \\
        --suite atp-conformance=<path> --suite aip-conformance=<path> [--root <tree>]
    python3 scripts/check_conformance_counts.py --family-dir <dir> [--root <tree>]

--family-dir names a directory holding the clones under the suites' names;
--suite overrides it for one suite. --root names the tree whose documents are
read (default: this repository); scripts/test_check_conformance_counts.py uses
it on scratch trees. Modelled on the conformance-count check of
opena2a-standards/atx-spec. python3 standard library and git only. Exit code
0 = every stated count matches.
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SUITES = ("atx-conformance", "atp-conformance", "aip-conformance")
# The document that must state a count for every suite, so the check never passes vacuously.
REQUIRED = "docs/use-cases.md"

# The fixtureType each class word stands for.
CLASSES = {
    "challenge-response": "challengeResponse",
    "trust-score": "trustScoreComposition",
}
CARRYING = " with a did:opena2a identifier"
KINDS = tuple(
    kind + suffix
    for kind in ("fixtures",) + tuple(f"{word} fixtures" for word in CLASSES)
    for suffix in ("", CARRYING)
)
DID_RE = re.compile(rb"did:opena2a:[A-Za-z0-9]")

# A word that may sit between the count and "fixtures" and still describe the
# whole suite.
WHOLE_SUITE_QUALIFIERS = ("byte-pinned", "pinned", "shipped", "conformance")

# A number that is not the end of a section number such as 6.5.
NUMBER = r"(?<![\w.])(\d+)"
CLASS = r"(" + "|".join(map(re.escape, CLASSES)) + r")"
WHOLE = r"(?:(?:" + "|".join(map(re.escape, WHOLE_SUITE_QUALIFIERS)) + r")\s+)?fixtures\b"

# Each phrasing and the counts it states, as (kind, group holding the value or
# a fixed value). A match that overlaps an earlier phrasing's is not read again.
PHRASES = [
    (re.compile(r"\bthe\s+" + NUMBER + r"\s+" + CLASS + r"\s+fixtures\s+of\s+its\s+" + NUMBER + r"\b"),
     lambda m: [(f"{m[2]} fixtures", int(m[1]), m.start(1)),
                (f"{m[2]} fixtures{CARRYING}", int(m[1]), m.start(1)),
                ("fixtures", int(m[3]), m.start(3))]),
    (re.compile(r"\bthe\s+" + NUMBER + r"\s+" + CLASS + r"\s+fixtures\s+carry\s+none\b"),
     lambda m: [(f"{m[2]} fixtures", int(m[1]), m.start(1)),
                (f"{m[2]} fixtures{CARRYING}", 0, m.start(1))]),
    (re.compile(r"\ball\s+" + NUMBER + r"\s+" + WHOLE),
     lambda m: [("fixtures", int(m[1]), m.start(1)),
                (f"fixtures{CARRYING}", int(m[1]), m.start(1))]),
    (re.compile(NUMBER + r"\s+" + CLASS + r"\s+(?:transcripts|compositions|fixtures)\b"),
     lambda m: [(f"{m[2]} fixtures", int(m[1]), m.start(1))]),
    (re.compile(NUMBER + r"\s+" + WHOLE),
     lambda m: [("fixtures", int(m[1]), m.start(1))]),
]
# The conformance suites of the family. Naming one starts that suite's part of
# a paragraph; the name inside a link target or a path does not.
SUITE_NAME_RE = re.compile(r"(?<![\w/.-])((?:aap|aip|atp|atx)-conformance)(?![\w-])")
COMMIT_RE = re.compile(r"\bcommit\s+`?([0-9a-f]{7,40})\b`?")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)\s]*\)")
FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
FENCE_CLOSE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*$")
# A line that starts a block of its own: a heading, a list item, a block quote or a table row.
BLOCK_START_RE = re.compile(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\|)")


@dataclass
class Part:
    """One suite's part of a paragraph: from where the suite is named to where the next one is."""

    suite: str | None
    commits: list[tuple[str, int]] = field(default_factory=list)  # (commit, line)
    counts: list[tuple[str, int, int]] = field(default_factory=list)  # (kind, value, line)


def paragraphs(text: str):
    """Yield (line numbers, lines) per paragraph outside fenced code blocks, each link reduced to its text."""
    fence = None
    numbers: list[int] = []
    lines: list[str] = []
    for number, raw in enumerate(text.split("\n"), 1):
        if fence is not None:
            close = FENCE_CLOSE_RE.match(raw)
            if close and close.group(1)[0] == fence[0] and len(close.group(1)) >= len(fence):
                fence = None
            continue
        opening = FENCE_OPEN_RE.match(raw)
        if opening and opening.group(1)[0] == "`" and "`" in raw[opening.end():]:
            opening = None  # a run of backticks with a backtick after it on its line opens no fence
        if opening or not raw.strip() or (lines and BLOCK_START_RE.match(raw)):
            if lines:
                yield numbers, lines
            numbers, lines = [], []
            if opening:
                fence = opening.group(1)
                continue
            if not raw.strip():
                continue
        numbers.append(number)
        lines.append(LINK_RE.sub(r"\1", raw))
    if lines:
        yield numbers, lines


def counts_in(segment: str) -> list[tuple[str, int, int]]:
    """Every count stated in one suite's part of a paragraph, as (kind, value, offset)."""
    taken: list[tuple[int, int]] = []
    found = []
    for regex, read in PHRASES:
        for m in regex.finditer(segment):
            if any(m.start() < end and start < m.end() for start, end in taken):
                continue
            taken.append((m.start(), m.end()))
            found += read(m)
    return sorted(found, key=lambda item: item[2])


def parts(text: str) -> list[Part]:
    """Each part of each paragraph of text that states a count or names a commit."""
    result = []
    for numbers, lines in paragraphs(text):
        joined = "\n".join(lines)
        starts = [0]
        for line in lines[:-1]:
            starts.append(starts[-1] + len(line) + 1)

        def line_of(offset: int) -> int:
            return numbers[bisect.bisect_right(starts, offset) - 1]

        names = list(SUITE_NAME_RE.finditer(joined))
        bounds = [(None, 0)] + [(m.group(1), m.start()) for m in names]
        for index, (suite, begin) in enumerate(bounds):
            end = bounds[index + 1][1] if index + 1 < len(bounds) else len(joined)
            segment = joined[begin:end]
            part = Part(suite)
            part.commits = [(m.group(1), line_of(begin + m.start())) for m in COMMIT_RE.finditer(segment)]
            part.counts = [(kind, value, line_of(begin + offset)) for kind, value, offset in counts_in(segment)]
            if part.counts or part.commits:
                result.append(part)
    return result


class SuiteError(Exception):
    pass


class Suite:
    """A git clone of a suite, read at commits rather than at its working tree."""

    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path
        if self._git("rev-parse", "--git-dir").returncode != 0:
            raise SuiteError(
                f"{path} ({name}) is not a git checkout; the check reads the suite at the commit "
                f"a sentence names, so it needs a clone with history"
            )
        self.head = self.resolve("HEAD")
        if self.head is None:
            raise SuiteError(f"{path} ({name}) has no HEAD commit")
        self._facts: dict[str, dict[str, int]] = {}

    def _git(self, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.path), *args], input=stdin, capture_output=True, check=False
        )

    def resolve(self, name: str) -> str | None:
        """The full id of the commit name resolves to, or None when it resolves to none or to more than one."""
        proc = self._git("rev-parse", "--verify", "--quiet", f"{name}^{{commit}}")
        return proc.stdout.decode().strip() if proc.returncode == 0 else None

    def in_head_history(self, commit: str) -> bool:
        proc = self._git("merge-base", "--is-ancestor", commit, self.head)
        if proc.returncode not in (0, 1):
            raise SuiteError(f"git merge-base failed in {self.path}: {proc.stderr.decode().strip()}")
        return proc.returncode == 0

    def facts(self, commit: str) -> dict[str, int]:
        """The counts at commit: every .json file directly under fixtures/, by class and by whether it carries an identifier."""
        if commit in self._facts:
            return self._facts[commit]
        listing = self._git("ls-tree", "-z", "--full-tree", commit, "--", "fixtures/")
        if listing.returncode != 0:
            raise SuiteError(f"git ls-tree failed in {self.path}: {listing.stderr.decode().strip()}")
        objects = []
        for record in listing.stdout.split(b"\0"):
            meta, _, raw_path = record.partition(b"\t")
            if not meta:
                continue
            _mode, object_type, object_id = meta.split()
            path = raw_path.decode("utf-8", "surrogateescape")
            name = path[len("fixtures/"):]
            if (object_type == b"blob" and path.startswith("fixtures/") and "/" not in name
                    and name.endswith(".json")):
                objects.append(object_id.decode())
        facts = dict.fromkeys(KINDS, 0)
        for data in self._blobs(objects):
            try:
                fixture_type = json.loads(data).get("fixtureType")
            except (ValueError, AttributeError):
                fixture_type = None
            kinds = ["fixtures"] + [f"{word} fixtures" for word, value in CLASSES.items() if fixture_type == value]
            carrying = DID_RE.search(data) is not None
            for kind in kinds:
                facts[kind] += 1
                if carrying:
                    facts[kind + CARRYING] += 1
        self._facts[commit] = facts
        return facts

    def _blobs(self, objects: list[str]) -> list[bytes]:
        if not objects:
            return []
        proc = self._git("cat-file", "--batch", stdin="".join(f"{o}\n" for o in objects).encode())
        if proc.returncode != 0:
            raise SuiteError(f"git cat-file failed in {self.path}: {proc.stderr.decode().strip()}")
        out, position, blobs = proc.stdout, 0, []
        for _ in objects:
            header_end = out.index(b"\n", position)
            header = out[position:header_end].split()
            if len(header) != 3 or header[1] != b"blob":
                raise SuiteError(f"git cat-file did not return a blob in {self.path}: {header!r}")
            start = header_end + 1
            blobs.append(out[start:start + int(header[2])])
            position = start + int(header[2]) + 1
        return blobs


def claim_files(root: Path) -> list[Path]:
    files = [root / "README.md"] if (root / "README.md").is_file() else []
    docs = root / "docs"
    if docs.is_dir():
        files += sorted(path for path in docs.rglob("*.md") if path.is_file())
    return files


def hint(suites: dict[str, Suite]) -> str:
    """Each suite's counts as its HEAD would state them."""
    said = []
    for name, suite in suites.items():
        facts = suite.facts(suite.head)
        classes = ", ".join(
            f"{facts[f'{word} fixtures']} {word}" for word in CLASSES if facts[f"{word} fixtures"]
        )
        said.append(
            f"{name} at {suite.head[:7]}: {facts['fixtures']} fixtures"
            + (f" ({classes})" if classes else "")
            + f", {facts['fixtures' + CARRYING]} carrying an identifier"
        )
    return ("At HEAD, " + "; ".join(said) + ".") if said else ""


def check(root: Path, paths: dict[str, Path]) -> tuple[list[str], list[str], int, str]:
    """Return (failures, notes, number of stated values checked, a hint for the fix)."""
    failures: list[str] = []
    notes: list[str] = []
    checked = 0
    suites: dict[str, Suite] = {}
    broken: set[str] = set()

    def suite_for(name: str) -> Suite | None:
        if name in suites:
            return suites[name]
        if name in broken:
            return None
        broken.add(name)
        if name not in paths:
            failures.append(
                f"no checkout of {name} was given; pass --suite {name}=<path> or --family-dir <dir>"
            )
            return None
        try:
            suites[name] = Suite(name, paths[name])
        except SuiteError as error:
            failures.append(str(error))
            return None
        broken.discard(name)
        return suites[name]

    if not (root / REQUIRED).is_file():
        failures.append(f"{REQUIRED} is missing")
    required_stated: set[str] = set()
    for path in claim_files(root):
        rel = path.relative_to(root).as_posix()
        for part in parts(path.read_text(encoding="utf-8")):
            if not part.counts:
                continue
            if part.suite is None:
                for kind, value, line in part.counts:
                    failures.append(
                        f"{rel}:{line} states {value} ({kind}) before naming a conformance suite; "
                        f"name the suite and the commit the count was read at first"
                    )
                continue
            if part.suite not in SUITES:
                for kind, value, line in part.counts:
                    failures.append(
                        f"{rel}:{line} states {value} ({kind}) for {part.suite}, which this check "
                        f"does not read"
                    )
                continue
            if rel == REQUIRED:
                required_stated.add(part.suite)
            suite = suite_for(part.suite)
            if suite is None:
                continue
            head = suite.head[:7]
            commits = sorted({commit for commit, _ in part.commits})
            if not commits:
                at_head = suite.facts(suite.head)
                for kind, value, line in part.counts:
                    failures.append(
                        f"{rel}:{line} states {value} ({kind}) for {suite.name} and names no commit; "
                        f"at HEAD {head} the suite has {at_head[kind]}"
                    )
                continue
            line = part.commits[0][1]
            if len(commits) > 1:
                failures.append(
                    f"{rel}:{line} names {len(commits)} {suite.name} commits ({', '.join(commits)}); "
                    f"a count is read at one"
                )
                continue
            named = commits[0]
            commit = suite.resolve(named)
            if commit is None:
                failures.append(
                    f"{rel}:{line} names {suite.name} commit {named}, which the suite checkout at "
                    f"{suite.path} does not resolve to one commit; a shallow clone holds only its "
                    f"head, so fetch the suite's history"
                )
                continue
            if not suite.in_head_history(commit):
                failures.append(
                    f"{rel}:{line} names {suite.name} commit {named}, which is not in the history of "
                    f"the suite checkout's HEAD ({head})"
                )
                continue
            facts = suite.facts(commit)
            if facts["fixtures"] == 0:
                failures.append(
                    f"{rel}:{line} names {suite.name} commit {named}, which ships no fixtures; "
                    f"refusing to pass vacuously"
                )
                continue
            for kind, value, count_line in part.counts:
                checked += 1
                if value != facts[kind]:
                    failures.append(
                        f"{rel}:{count_line} states {value} ({kind}) for {suite.name} at {named}, "
                        f"which has {facts[kind]}"
                    )
            moved = suite.facts(suite.head)["fixtures"]
            if commit != suite.head and moved != facts["fixtures"]:
                notes.append(
                    f"note: {rel}:{line} states the {suite.name} count at {named} "
                    f"({facts['fixtures']} fixtures); at HEAD {head} the suite ships {moved}. The "
                    f"sentence holds at the commit it names."
                )
    if (root / REQUIRED).is_file():
        for name in SUITES:
            if name not in required_stated:
                failures.append(
                    f"{REQUIRED} states no {name} count; the check would pass vacuously, so this "
                    f"is a failure"
                )
    return failures, notes, checked, hint(suites)


def suite_paths(family_dir: str | None, given: list[str]) -> dict[str, Path]:
    paths = {name: Path(family_dir) / name for name in SUITES} if family_dir else {}
    for value in given:
        name, sep, path = value.partition("=")
        if not sep or name not in SUITES or not path:
            raise argparse.ArgumentTypeError(
                f"--suite takes NAME=PATH with NAME one of {', '.join(SUITES)}, not {value!r}"
            )
        paths[name] = Path(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--suite", action="append", default=[], metavar="NAME=PATH",
                    help="a git clone of opena2a-standards/NAME; repeat once per suite")
    ap.add_argument("--family-dir", help="a directory holding the suites' clones under their names")
    ap.add_argument("--root", default=str(ROOT), help="tree to check (default: this repository)")
    args = ap.parse_args(argv)
    try:
        paths = suite_paths(args.family_dir, args.suite)
    except argparse.ArgumentTypeError as error:
        ap.error(str(error))
    root = Path(args.root).resolve()

    try:
        failures, notes, checked, fix = check(root, paths)
    except SuiteError as error:
        failures, notes, checked, fix = [str(error)], [], 0, ""
    for note in notes:
        print(note)
    if failures:
        print("conformance counts do not match the suites:\n", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            f"\nState each count with the commit of its suite it was read at "
            f"(\"at commit `<sha>`\") and the suite's counts at that commit. {fix}".rstrip(),
            file=sys.stderr,
        )
        return 1
    print(
        f"conformance counts match: {checked} stated value(s) checked across "
        f"{len(SUITES)} suites, each at the commit its sentence names"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
