#!/usr/bin/env python3
"""Check did:opena2a strings against the Section 3.1 ABNF and the Section 3.1.2 decoding step.

The grammar is read from the fenced block under the
`<!-- opena2a-definition: did-syntax -->` marker in the specification and
compiled to a regular expression, so the check follows the ABNF as written
rather than a copy of it. Three checks run:

- every `did:opena2a:` string in the README, the specification, the CHANGELOG
  and examples/ parses (templates such as `did:opena2a:<type>:<id>` and the
  bare prefix are skipped);
- the vectors below parse, or fail to parse, as listed;
- the percent-encoded vectors decode to the listed canonical form, and the
  listed invalid encodings are rejected by the decoding step.

Quoted strings in the grammar are matched case-sensitively, as Section 3.3
requires of the prefix. Exit 1 on any failure. python3 standard library only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "did-method-opena2a.md"
MARKER = "<!-- opena2a-definition: did-syntax -->"
PREFIX = "did:opena2a:"
SOURCES = [ROOT / "README.md", SPEC, ROOT / "CHANGELOG.md", *sorted((ROOT / "examples").glob("*.json"))]

# A DID in running text, JSON or code ends at whitespace, a quote, a backtick or
# a bracket. A match followed by "<" is a template, not a DID.
DID_IN_TEXT = re.compile(r"did:opena2a:[^\s`\"'<>()\[\]|,*]*")
TRIPLET = re.compile(r"%([0-9A-Fa-f]{2})")

MUST_PARSE = [
    "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem",
    "did:opena2a:mcp_server:%40modelcontextprotocol%2Fserver-filesystem",
    "did:opena2a:mcp_server:%40modelcontextprotocol%2fserver-filesystem",
    "did:opena2a:agent:agent_conformance_test_001#key-1",
]
MUST_NOT_PARSE = [
    "did:opena2a:agent:",
    "did:opena2a:Agent:agent_conformance_test_001",
    "DID:OPENA2A:agent:agent_conformance_test_001",
    "did:opena2a:mcp%5Fserver:%40modelcontextprotocol%2Fserver-filesystem",
    "did:opena2a:mcp_server:%4",
    "did:opena2a:mcp_server:%zz",
]
DECODES_TO = {
    "did:opena2a:mcp_server:%40modelcontextprotocol%2Fserver-filesystem":
        "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem",
    "did:opena2a:mcp_server:%40modelcontextprotocol%2fserver-filesystem":
        "did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem",
    "did:opena2a:agent:agent%5Fconformance%5Ftest%5F001#key-1":
        "did:opena2a:agent:agent_conformance_test_001#key-1",
    "did:opena2a:authority:opena2a.org":
        "did:opena2a:authority:opena2a.org",
}
# Each parses under the grammar, and the decoding step rejects it: the decoded
# octet is "%" (no second decoding), "#", a space, or not US-ASCII.
DOES_NOT_DECODE = [
    "did:opena2a:mcp_server:%2540modelcontextprotocol%252Fserver-filesystem",
    "did:opena2a:agent:agent_conformance_test_001%23key-1",
    "did:opena2a:skill:web%20research",
    "did:opena2a:skill:caf%C3%A9",
]

TOKEN = re.compile(r"""\s*(?:
    (?P<str>"[^"]*")
  | (?P<num>%x[0-9A-Fa-f]+(?:-[0-9A-Fa-f]+|(?:\.[0-9A-Fa-f]+)+)?)
  | (?P<rep>\d*\*\d*|\d+)
  | (?P<name>[A-Za-z][A-Za-z0-9-]*)
  | (?P<op>[/()\[\]])
)""", re.X)


def read_grammar(text: str) -> list:
    lines = text.split("\n")
    try:
        i = next(n for n, line in enumerate(lines) if MARKER in line)
        j = i + 1
        while not lines[j].startswith("```"):
            if lines[j].startswith("#"):
                raise SystemExit(f"{MARKER}: no fenced grammar before the next heading")
            j += 1
        k = j + 1
        while not lines[k].startswith("```"):
            k += 1
    except (StopIteration, IndexError):
        raise SystemExit(f"{SPEC.name}: no fenced grammar after {MARKER}")
    return lines[j + 1:k]


def strip_comment(line: str) -> str:
    out, quoted = [], False
    for ch in line:
        if ch == '"':
            quoted = not quoted
        elif ch == ";" and not quoted:
            break
        out.append(ch)
    return "".join(out).rstrip()


def parse_rules(block: list) -> dict:
    rules, name = {}, None
    for raw in block:
        line = strip_comment(raw)
        if not line.strip():
            continue
        m = re.match(r"([A-Za-z][A-Za-z0-9-]*)\s*=\s*(.*)$", line)
        if m and not m.group(2).startswith("/"):
            name = m.group(1).lower()
            if name in rules:
                raise SystemExit(f"rule defined twice: {m.group(1)}")
            rules[name] = m.group(2)
        elif name and raw[:1].isspace():
            rules[name] += " " + line.strip()
        else:
            raise SystemExit(f"cannot read grammar line: {raw!r}")
    return rules


def tokenize(text: str) -> list:
    out, pos, text = [], 0, text.rstrip()
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m or m.end() == pos:
            raise SystemExit(f"cannot read grammar at {text[pos:]!r}")
        out.append((m.lastgroup, m.group(m.lastgroup)))
        pos = m.end()
    return out


def num_val(text: str) -> str:
    body = text[2:]
    if "-" in body:
        lo, hi = body.split("-")
        return "[\\U%08x-\\U%08x]" % (int(lo, 16), int(hi, 16))
    return "".join("\\U%08x" % int(part, 16) for part in body.split("."))


class Compiler:
    """Compile a non-recursive ABNF rule set to Python regular expressions."""

    def __init__(self, rules: dict):
        self.rules, self.done, self.active = rules, {}, set()

    def rule(self, name: str) -> str:
        key = name.lower()
        if key in self.done:
            return self.done[key]
        if key not in self.rules:
            raise SystemExit(f"rule not defined: {name}")
        if key in self.active:
            raise SystemExit(f"recursive rule not supported: {name}")
        self.active.add(key)
        tokens = tokenize(self.rules[key])
        rx, pos = self.alternation(tokens, 0)
        if pos != len(tokens):
            raise SystemExit(f"{name}: unexpected {tokens[pos][1]!r}")
        self.active.discard(key)
        self.done[key] = rx
        return rx

    def alternation(self, t: list, pos: int) -> tuple:
        rx, pos = self.concatenation(t, pos)
        parts = [rx]
        while pos < len(t) and t[pos] == ("op", "/"):
            rx, pos = self.concatenation(t, pos + 1)
            parts.append(rx)
        return "(?:" + "|".join(parts) + ")", pos

    def concatenation(self, t: list, pos: int) -> tuple:
        parts = []
        while pos < len(t) and t[pos] not in (("op", "/"), ("op", ")"), ("op", "]")):
            rx, pos = self.repetition(t, pos)
            parts.append(rx)
        if not parts:
            raise SystemExit("empty alternative in grammar")
        return "".join(parts), pos

    def repetition(self, t: list, pos: int) -> tuple:
        lo, hi = 1, 1
        if t[pos][0] == "rep":
            text = t[pos][1]
            if "*" in text:
                a, b = text.split("*")
                lo, hi = (int(a) if a else 0), (int(b) if b else None)
            else:
                lo = hi = int(text)
            pos += 1
        rx, pos = self.element(t, pos)
        if (lo, hi) == (1, 1):
            return rx, pos
        return "(?:%s){%d,%s}" % (rx, lo, "" if hi is None else hi), pos

    def element(self, t: list, pos: int) -> tuple:
        if pos >= len(t):
            raise SystemExit("grammar ends inside an element")
        kind, text = t[pos]
        if kind == "name":
            return self.rule(text), pos + 1
        if kind == "str":
            return re.escape(text[1:-1]), pos + 1
        if kind == "num":
            return num_val(text), pos + 1
        if text in ("(", "["):
            close = ")" if text == "(" else "]"
            rx, pos = self.alternation(t, pos + 1)
            if pos >= len(t) or t[pos] != ("op", close):
                raise SystemExit(f"grammar: missing {close!r}")
            return (rx if close == ")" else "(?:%s)?" % rx), pos + 1
        raise SystemExit(f"grammar: unexpected {text!r}")


def canonical_form(did: str, did_rx, rid_rx) -> str | None:
    """Section 3.1.2: decode the resource-id once; None when the DID is invalid."""
    if not did_rx.fullmatch(did):
        return None
    rtype, _, tail = did[len(PREFIX):].partition(":")
    rid, hash_mark, fragment = tail.partition("#")
    decoded = TRIPLET.sub(lambda m: chr(int(m.group(1), 16)), rid)
    if "%" in decoded or not rid_rx.fullmatch(decoded):
        return None
    return f"{PREFIX}{rtype}:{decoded}{hash_mark}{fragment}"


def documented_dids() -> dict:
    found = {}
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for m in DID_IN_TEXT.finditer(text):
            did = m.group(0).rstrip(".")
            if did == PREFIX or text[m.end():m.end() + 1] == "<":
                continue
            line = text.count("\n", 0, m.start()) + 1
            found.setdefault(did, []).append(f"{path.relative_to(ROOT)}:{line}")
    return found


def main() -> int:
    compiler = Compiler(parse_rules(read_grammar(SPEC.read_text(encoding="utf-8"))))
    did_rx = re.compile(compiler.rule("opena2a-did"))
    rid_rx = re.compile(compiler.rule("resource-id"))
    failures = []
    docs = documented_dids()
    for did, where in sorted(docs.items()):
        if not did_rx.fullmatch(did):
            failures.append(f"does not parse: {did} ({', '.join(where)})")
    for did in MUST_PARSE:
        if not did_rx.fullmatch(did):
            failures.append(f"vector does not parse: {did}")
    for did in MUST_NOT_PARSE:
        if did_rx.fullmatch(did):
            failures.append(f"vector parses but must not: {did}")
    for did, want in DECODES_TO.items():
        got = canonical_form(did, did_rx, rid_rx)
        if got != want:
            failures.append(f"vector decodes to {got!r}, expected {want!r}: {did}")
    for did in DOES_NOT_DECODE:
        if not did_rx.fullmatch(did):
            failures.append(f"vector does not parse: {did}")
        elif canonical_form(did, did_rx, rid_rx) is not None:
            failures.append(f"vector decodes but must be rejected: {did}")
    for failure in failures:
        print(failure, file=sys.stderr)
    vectors = len(MUST_PARSE) + len(MUST_NOT_PARSE) + len(DECODES_TO) + len(DOES_NOT_DECODE)
    print(f"{len(docs)} distinct did:opena2a strings in {len(SOURCES)} files, "
          f"{vectors} vectors, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
