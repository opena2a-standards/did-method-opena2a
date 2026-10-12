#!/usr/bin/env python3
"""Apply the Section 3.5 and Section 6.5 resolution checks to every vector under vectors/.

Each vector pairs a requested DID with the DID resolution result a resolver
returned for it and the verdict a verifier reaches (Section 8.5). This script
is a reference for two checks, in the order a verifier applies them: the
`issuingRegistry` in `didDocumentMetadata` is the pinned registry (Section
3.5), and the resolved `id` equals the canonical form of the requested DID
(Sections 3.1.2 and 6.5), compared as exact strings. The canonical form comes
from check_did_syntax.py, which compiles the Section 3.1 ABNF from the
specification. It fails when a verdict differs from the vector's `expected`
member, or when the set no longer covers an accepted resolution and a
resolved-id rejection. python3 standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# check_did_syntax.py sits beside this script. Python leaves the script
# directory off sys.path under -P, -I and PYTHONSAFEPATH=1, so add it here.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_did_syntax import SPEC, Compiler, canonical_form, parse_rules, read_grammar

ROOT = Path(__file__).resolve().parent.parent
VECTORS = ROOT / "vectors"
# Section 8.4: the self-identifier of the reference deployment, the registry
# every vector is checked against.
PINNED_REGISTRY = "did:opena2a:registry:opena2a.org"
REASONS = ("issuing-registry-mismatch", "resolved-id-mismatch")
REQUIRED = (("accept", None), ("reject", "resolved-id-mismatch"))


def grammar() -> tuple:
    compiler = Compiler(parse_rules(read_grammar(SPEC.read_text(encoding="utf-8"))))
    return re.compile(compiler.rule("opena2a-did")), re.compile(compiler.rule("resource-id"))


def member(result: dict, name: str) -> dict:
    """An object-valued member of a resolution result; absent or null reads as empty."""
    value = result.get(name)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} is not an object")
    return value


def verify(requested: str, result: dict, did_rx, rid_rx, pinned: str = PINNED_REGISTRY) -> tuple:
    """Return (verdict, reason) for one resolution under Sections 3.5 and 6.5."""
    canonical = canonical_form(requested, did_rx, rid_rx)
    if canonical is None:
        raise ValueError(f"requested DID does not parse or decode (Section 3.1.2): {requested!r}")
    if not isinstance(result, dict):
        raise ValueError("resolutionResult is not an object")
    document = member(result, "didDocument")
    metadata = member(result, "didDocumentMetadata")
    if metadata.get("issuingRegistry") != pinned:
        return "reject", "issuing-registry-mismatch"
    if document.get("id") != canonical:
        return "reject", "resolved-id-mismatch"
    return "accept", None


def label(verdict: str, reason) -> str:
    return f"{verdict} {reason}" if reason else verdict


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    paths = sorted(VECTORS.glob("*.json"))
    if not paths:
        print(f"no vectors under {VECTORS.relative_to(ROOT)}/", file=sys.stderr)
        return 1
    did_rx, rid_rx = grammar()
    failures = []
    covered = set()
    for path in paths:
        name = path.relative_to(ROOT).as_posix()
        try:
            vector = json.loads(path.read_text(encoding="utf-8"))
            want = (vector["expected"]["verdict"], vector["expected"].get("reason"))
            if want != ("accept", None) and not (want[0] == "reject" and want[1] in REASONS):
                raise ValueError(f"unknown expected verdict {label(*want)!r}")
            got = verify(vector["requestedDid"], vector["resolutionResult"], did_rx, rid_rx)
        except (KeyError, TypeError, ValueError) as exc:
            failures.append(f"{name}: malformed vector: {exc}")
            print(f"FAIL  {name}: malformed vector")
            continue
        covered.add(want)
        if got == want:
            print(f"ok    {name}: {label(*got)}")
        else:
            failures.append(f"{name}: verifier says {label(*got)}, vector expects {label(*want)}")
            print(f"FAIL  {name}: {label(*got)}")
    for want in REQUIRED:
        if want not in covered:
            failures.append(f"no vector expects {label(*want)}")
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    print(f"{len(paths)} vectors, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
