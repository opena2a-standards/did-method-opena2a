#!/usr/bin/env python3
"""Check that every link a reader can follow in the README and the spec opens.

Link targets are taken from inline links `[text](target)`, reference
definitions `[label]: target`, autolinks `<https://...>` and bare `http(s)://`
URLs in prose, which GitHub also renders as links, outside fenced code blocks
and inline code spans. The character references in an inline link or
reference definition target, such as `&amp;`, are decoded as CommonMark
decodes them: a named one only with its `;`. A bare URL ends at whitespace or
`<`, and trailing punctuation and an unbalanced `)` are not part of it, as on
GitHub. A URL in a quoted HTML attribute value, as in `<a href="...">`, runs
to the quote that closes the value, whitespace, `<` and line breaks included,
up to a blank line, and may follow whitespace written as such or as a
character reference. Its character references are decoded with html.unescape,
except that a named reference without its `;` is kept as written when `=` or
an ASCII letter or digit follows it, as a browser keeps `&sect` in
`&section=2`. Leading and trailing C0 controls and spaces are dropped and tabs
and newlines are removed, as a browser does. An inline link target may hold
parentheses in balanced pairs, one level deep. HTML comments are not excluded.
A relative target must name a file in this repository, and its `#fragment`,
when present on a Markdown file, must match a heading there. An absolute
http(s) target is requested anonymously, with each space, control or non-ASCII
character after the host percent-encoded as a browser does and the rest sent
as written, and must answer with a success status after redirects: a
repository that is private answers 404 to an anonymous reader, which is the
failure this check exists to catch. A target with a host or port that cannot
be requested, such as a host holding a space, is reported as broken.
`--offline` skips the network requests. python3 standard library only.
"""
from __future__ import annotations

import argparse
import bisect
import html
import html.entities
import http.client
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["README.md", "did-method-opena2a.md"]
USER_AGENT = "did-method-opena2a-link-check"

# An inline link destination has no whitespace and holds parentheses only in
# balanced pairs, as in CommonMark, limited here to one level of nesting;
# link text cannot hold a "[" and an autolink cannot hold a "<". CommonMark
# allows deeper nesting and matched brackets in link text: both limits are
# this script's simplifications. A destination runs past the "(" that opens a
# later inline link only when that "(" opens a balanced pair, and the later
# link is then read within its own pair. So no part of a line is read by more
# than a fixed number of failed matches, and a long line is read in linear
# time.
DEST = r"(?:[^()\s]|\([^()\s]*\))+"
INLINE = re.compile(rf"\]\(({DEST})\)")
REFDEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^>\s]+)>?")
AUTOLINK = re.compile(r"<(https?://[^<>\s]+)>")
CODE_SPAN = re.compile(r"`+[^`]*`+")
# The whole of an inline link, text included, so a URL used as link text is
# not read a second time as a bare URL.
INLINE_SPAN = re.compile(rf"\[[^\[\]]*\]\({DEST}\)")
# A character reference in an inline link or reference definition target, as
# CommonMark reads one: a name or a decimal or hexadecimal code, closed by `;`.
DESTINATION_REFERENCE = re.compile(
    r"&(?:#([0-9]{1,7})|#[xX]([0-9A-Fa-f]{1,6})|([0-9A-Za-z]+));")
# What the URL parser strips from the start of an attribute value, written as
# such or as a character reference: a C0 control or a space. `&#0;` is read as
# U+FFFD, and `&Tab;` and `&NewLine;` are the only names in the HTML table for
# one of these characters.
LEADING = (r"(?:[\x00-\x20]|&#0*(?:3[0-2]|[12][0-9]|[1-9]);?"
           r"|&#[xX]0*(?:20|1[0-9A-Fa-f]|[1-9A-Fa-f]);?|&(?:Tab|NewLine);)")
# A URL outside the link forms above. One in a quoted HTML attribute value
# (href="...", src='...') runs to the quote that closes the value, so the rest
# of the tag is not read into it; any other is a bare URL. A value stops at the
# first quote of its own kind, and every value that opens holds a quote of that
# kind, so only the last value of each kind can fail to close and be read to
# the end of its block of lines.
URL = re.compile(rf"""=\s*(["'])({LEADING}*https?://(?:(?!\1).)*)\1|https?://[^\s<]+""",
                 re.DOTALL)
BARE_TRAILING = ".,:;!?\"'*_~"
# What the WHATWG URL parser strips from both ends of a URL, and removes from
# within it.
C0_OR_SPACE = "".join(map(chr, range(0x21)))
TAB_OR_NEWLINE = re.compile("[\t\n\r]")
# A named character reference: `&` and the letters and digits after it. The
# longest name in the HTML table of named references bounds the search.
NAMED_REFERENCE = re.compile(r"&([0-9A-Za-z]+)")
LONGEST_NAME = max(map(len, html.entities.html5))
# A decimal character reference. html.unescape cannot convert more than 4,300
# digits, and any code of more than 7 digits after its leading zeros is above
# U+10FFFF, which html.unescape and a browser both read as U+FFFD.
DECIMAL_REFERENCE = re.compile(r"&#([0-9]+)")
# The scheme and host of an http(s) URL, up to the first `/`, `?` or `#`.
ORIGIN = re.compile(r"https?://[^/?#]*")
# Characters http.client will not send, and a browser percent-encodes after
# the host: whitespace, controls and anything outside ASCII.
UNSENDABLE = re.compile(r"[^\x21-\x7e]+")


def bare_url(text: str) -> str:
    """Drop the trailing characters GitHub leaves out of a bare URL link."""
    end = len(text)
    unbalanced = text.count(")") - text.count("(")
    while end:
        if text[end - 1] in BARE_TRAILING:
            end -= 1
        elif text[end - 1] == ")" and unbalanced > 0:
            end -= 1
            unbalanced -= 1
        else:
            break
    return text[:end]


def unescape_destination(target: str) -> str:
    """Decode the character references in an inline link or reference
    definition target as CommonMark does: a named one only with its `;` and a
    name in the HTML table, a numeric one to its character, or to U+FFFD for
    zero, a surrogate or a code above U+10FFFF."""
    def decoded(m: re.Match) -> str:
        if m.group(3) is not None:
            return html.entities.html5.get(m.group(3) + ";", m.group())
        code = int(m.group(1)) if m.group(1) else int(m.group(2), 16)
        if code == 0 or 0xD800 <= code <= 0xDFFF or code > 0x10FFFF:
            return "�"
        return chr(code)

    return DESTINATION_REFERENCE.sub(decoded, target)


def unescape_attribute(value: str) -> str:
    """Decode the character references in an attribute value with
    html.unescape, but keep a named reference that has no `;`, such as
    `&sect`, as written when `=` or an ASCII letter or digit follows it, as
    the HTML tokenizer keeps it in an attribute value."""
    def bounded(m: re.Match) -> str:
        # Eight digits are enough to read any longer code as U+FFFD.
        return "&#" + (m.group(1).lstrip("0") or "0")[:8]

    def written(m: re.Match) -> str:
        name, after = m.group(1), m.string[m.end():m.end() + 1]
        if after == ";" and name + ";" in html.entities.html5:
            return m.group()
        # The tokenizer reads the longest name in the table.
        for end in range(min(len(name), LONGEST_NAME), 1, -1):
            if name[:end] in html.entities.html5:
                if end < len(name) or after == "=":
                    # html.unescape turns this back into the text as written.
                    return "&amp;" + name
                break
        return m.group()

    return html.unescape(NAMED_REFERENCE.sub(written, DECIMAL_REFERENCE.sub(bounded, value)))


def attribute_url(value: str) -> str:
    """The URL in a quoted HTML attribute value: references decoded, the ends
    stripped and tabs and newlines removed, as the module docstring says."""
    return TAB_OR_NEWLINE.sub("", unescape_attribute(value).strip(C0_OR_SPACE))


def request_url(url: str) -> str:
    """The URL as written, with each space, control and non-ASCII character
    after the host percent-encoded, as a browser encodes it, so that
    http.client sends it. Other characters a browser also encodes, such as
    `"`, `<`, `>` and a backquote, are sent as written."""
    origin = ORIGIN.match(url)
    start = origin.end() if origin else 0
    return url[:start] + UNSENDABLE.sub(lambda m: urllib.parse.quote(m.group()), url[start:])


def prose_urls(block: list) -> list:
    """Return (line number, target) for every URL in a block of prose, given
    as (line number, prose) pairs. A quoted attribute value may continue onto
    the following lines of the block."""
    text = "\n".join(prose for _, prose in block)
    starts = [0]
    for _, prose in block[:-1]:
        starts.append(starts[-1] + len(prose) + 1)
    found = []
    for m in URL.finditer(text):
        n = block[bisect.bisect_right(starts, m.start()) - 1][0]
        found.append((n, attribute_url(m.group(2)) if m.group(1) else bare_url(m.group(0))))
    return found


def link_targets(text: str) -> list:
    """Return (line number, target) for every followable link in the text."""
    found = []
    block = []
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        fence = line.lstrip().startswith(("```", "~~~"))
        if fence or in_fence or not line.strip(" \t"):
            # A fence, a line inside one or a blank line ends a block of prose.
            found += prose_urls(block)
            block = []
            if fence:
                in_fence = not in_fence
            continue
        line = CODE_SPAN.sub("", line)
        for pattern in (INLINE, REFDEF):
            for m in pattern.finditer(line):
                found.append((n, unescape_destination(m.group(1))))
        for m in AUTOLINK.finditer(line):
            found.append((n, m.group(1)))
        prose = line
        for pattern in (INLINE_SPAN, REFDEF, AUTOLINK):
            prose = pattern.sub(" ", prose)
        block.append((n, prose))
    found += prose_urls(block)
    # A stable sort keeps the link forms of a line before its URLs in prose.
    return sorted(found, key=lambda target: target[0])


def heading_anchors(text: str) -> set:
    """GitHub-style anchors for the headings of a Markdown file."""
    anchors = set()
    seen = {}
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        m = None if in_fence else re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        slug = re.sub(r"[^\w\- ]", "", m.group(1).lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def check_relative(doc: Path, target: str) -> str | None:
    path, _, fragment = target.partition("#")
    file = doc if not path else (doc.parent / path).resolve()
    if not file.exists():
        return "no such file in this repository"
    if fragment and file.suffix == ".md":
        if fragment.lower() not in heading_anchors(file.read_text(encoding="utf-8")):
            return f"no heading with anchor #{fragment} in {file.name}"
    return None


def check_remote(url: str) -> str | None:
    request = urllib.request.Request(request_url(url), headers={"User-Agent": USER_AGENT})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if 200 <= response.status < 300:
                    return None
                return f"HTTP {response.status}"
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 1:
                return f"HTTP {e.code} for an anonymous request"
        except http.client.InvalidURL as e:
            # A host or port http.client cannot use, such as a host with a space.
            return f"invalid URL: {e}"
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 1:
                return f"request failed: {getattr(e, 'reason', e)}"
        time.sleep(2)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true", help="skip absolute http(s) links")
    args = ap.parse_args()

    failures = []
    remote = {}
    for name in DOCS:
        doc = ROOT / name
        for n, target in link_targets(doc.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://")):
                remote.setdefault(target, []).append(f"{name}:{n}")
            elif not target.startswith("mailto:"):
                problem = check_relative(doc, target)
                if problem:
                    failures.append(f"{name}:{n}: {target}: {problem}")

    if not args.offline:
        for url, where in sorted(remote.items()):
            problem = check_remote(url)
            if problem:
                failures.append(f"{', '.join(where)}: {url}: {problem}")

    for failure in failures:
        print(failure, file=sys.stderr)
    checked = "relative links only" if args.offline else f"{len(remote)} distinct URLs"
    print(f"check_links: {len(failures)} broken ({checked}, files: {', '.join(DOCS)})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
