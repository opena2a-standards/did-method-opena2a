#!/usr/bin/env python3
"""Check that every link a reader can follow in the README and the spec opens.

Link targets are taken from inline links `[text](target)`, reference
definitions `[label]: target`, autolinks `<https://...>` and bare `http(s)://`
URLs in prose, which GitHub also renders as links, outside fenced code blocks
and inline code spans. A bare URL ends at whitespace or `<`, and trailing
punctuation and an unbalanced `)` are not part of it, as on GitHub. A URL that
opens a quoted HTML attribute value, as in `<a href="...">`, ends at the quote
that closes the value. An inline link target may hold parentheses in balanced
pairs, one level deep. HTML comments are not excluded. A relative target must
name a file in this repository, and its `#fragment`, when present on a
Markdown file, must match a heading there. An absolute http(s) target is
requested anonymously and must answer with a success status after redirects:
a repository that is private answers 404 to an anonymous reader, which is the
failure this check exists to catch. `--offline` skips the network requests.
python3 standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.error
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
# A URL outside the link forms above. One that opens a quoted HTML attribute
# value (href="...", src='...') ends at the quote that closes the value, so
# the rest of the tag is not read into it; any other is a bare URL.
URL = re.compile(r"""=\s*(["'])(https?://(?:(?!\1)[^\s<])*)\1|https?://[^\s<]+""")
BARE_TRAILING = ".,:;!?\"'*_~"


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


def link_targets(text: str) -> list:
    """Return (line number, target) for every followable link in the text."""
    found = []
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = CODE_SPAN.sub("", line)
        for pattern in (INLINE, REFDEF, AUTOLINK):
            for m in pattern.finditer(line):
                found.append((n, m.group(1)))
        prose = line
        for pattern in (INLINE_SPAN, REFDEF, AUTOLINK):
            prose = pattern.sub(" ", prose)
        for m in URL.finditer(prose):
            found.append((n, m.group(2) if m.group(1) else bare_url(m.group(0))))
    return found


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
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if 200 <= response.status < 300:
                    return None
                return f"HTTP {response.status}"
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 1:
                return f"HTTP {e.code} for an anonymous request"
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
