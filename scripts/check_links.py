#!/usr/bin/env python3
"""Check that every link a reader can follow in the README and the spec opens.

Link targets are taken from inline links `[text](target)`, reference
definitions `[label]: target`, autolinks `<https://...>` and bare `http(s)://`
URLs in prose, which GitHub also renders as links, outside fenced code blocks
and inline code spans. A fenced code block opens at a run of three or more
backticks or tildes, and a run of backticks with a backtick after it on its
line opens none. Block quotes and list items are read as CommonMark reads
them, and a fence holds at most three spaces of indentation, counted from
where the text of the block quote or list item it is in starts: after each
`>` and the space after it when there is one, and at the content of a list
item, so under `- step` a fence indented by two to five spaces is one. A ```
or ~~~ line indented by four or more columns from there is not a fence. A tab
runs to the next multiple of four columns, counted from the start of the
line, so under `- step` a tab, or two spaces and a tab, is two columns of
indentation, and two tabs are six. A block quote holds
the lines that start with its `>`, and a list item the blank lines and the
lines indented to its content, except that a blank line right below a marker
with nothing after it ends that item. A line that is not blank and opens no
heading, thematic break, fence, block quote or list item continues a
paragraph open above it, so it is held by each block quote and list item that
paragraph is in. Right below a paragraph line, a list marker that is in the
same block quotes and list items as that paragraph opens an item only with
text after it, and a numbered one only as number 1; any other marker there
opens one, such as a `2.` that starts the line below `- a`, which is not
indented to that item's content, or the `2.` in `- 2. a`, which is in the
item that `-` opens. Right below a paragraph line, a line of
`=` or `-` underlines a heading, except below a paragraph that holds only link
reference definitions: that line is then read as any other, so `===`
continues the paragraph. A definition is read as one there only when it is on
a line of its own, which is this script's simplification: CommonMark also
reads one written across lines. A fenced code block closes at a run of the
same character at least as long, indented in the same way,
with only spaces or tabs after it, at a line that leaves a block quote or list
item the fence is in, or at the end of the file. HTML blocks are not followed,
which is this script's simplification: a line that starts with `<` is read as
a line of a paragraph. A code span ends a bare URL before it. The character
references in an inline link or reference definition target, such as `&amp;`,
are decoded as CommonMark decodes them: a named one only with its `;`. A bare
URL ends at whitespace or
`<`, and trailing punctuation and an unbalanced `)` are not part of it, as on
GitHub. A URL in a quoted HTML attribute value, as in `<a href="...">`, runs
to the quote that closes the value, whitespace, `<` and line breaks included,
up to a blank line, and may follow whitespace written as such or as a
character reference. A value that holds a line break, before its URL or in
it, is read as one only when it is in a start tag and its closing quote is
followed by whitespace, `/>` or `>`; otherwise its URL is read as a bare URL,
so an unclosed `x="https://...` in prose is not read into the line below. A
start tag is a `<`, a tag name and whitespace or `/`, then an attribute part
that a `>` closes, holding no other `<` or `>` outside its quoted attribute
values; a `<` or `>` in a code span, autolink or inline link counts. The line
break at the end of the last line before a blank line, a fenced code block or
the end of the file does not count as that whitespace, so a quote that ends
that line does not close a value whose URL starts on an earlier line. A
value's character references are decoded with html.unescape, except that a
named reference without its `;` is kept as written when `=` or an ASCII letter or
digit follows it, as a browser keeps `&sect` in `&section=2`. Leading and
trailing C0 controls and spaces are dropped and tabs and newlines are
removed, as a browser does. A URL in prose is reported at the line its
scheme is on. An inline
link target may hold parentheses in balanced pairs, one level deep. HTML
comments are not excluded. A relative target must name a file in this
repository, a path that leaves it is reported even when a file is there, and
its `#fragment`, when present on a Markdown file, must match a
heading there. An absolute http(s) target is requested anonymously, with each
space, control or non-ASCII character after the host percent-encoded as a
browser does and the rest sent as written, and must answer with a success
status after redirects: a repository that is private answers 404 to an
anonymous reader, which is the failure this check exists to catch. A target
with a host or port that cannot be requested, such as a host holding a space,
is reported as broken. `--offline` skips the network requests. python3
standard library only.
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
LEADING_CHARACTER = (r"&#0*(?:3[0-2]|[12][0-9]|[1-9]);?"
                     r"|&#[xX]0*(?:20|1[0-9A-Fa-f]|[1-9A-Fa-f]);?|&(?:Tab|NewLine);")
LEADING = rf"(?:[\x00-\x20]|{LEADING_CHARACTER})"
# The same, without a line break as written.
LEADING_ON_LINE = rf"(?:[\x00-\x09\x0b-\x20]|{LEADING_CHARACTER})"
# A URL outside the link forms above. One in a quoted HTML attribute value
# (href="...", src='...') runs to the quote that closes the value, so the rest
# of the tag is not read into it; any other is a bare URL. Group 2 is the URL
# of a value on one line. Group 3 is the URL of a value that holds a line
# break, before its scheme or after it: it is read only when its closing quote
# is followed by whitespace, `/>` or `>`, as in a tag, and prose_urls keeps it
# only when its `=` is in the attribute part of a start tag (START_TAG), so an
# unclosed value in prose does not take a later quote, such as the one in "the
# users' guide" or the opening quote of "hi", as its own. A block ends at a
# blank line, a fenced code block or the end of the file, and its lines are
# joined without a line break after the last, so a quote that ends its last
# line does not close a value whose URL starts on an earlier line. A value is
# read only to the first quote of its own kind, and the quote that opens the
# next value of that kind is one, so only the last value of each kind can be
# read to the end of its block of lines.
URL = re.compile(rf"""=\s*(["'])(?:{LEADING_ON_LINE}*(https?://(?:(?!\1)[^\n])*)(?=\1)"""
                 rf"""|{LEADING}*(https?://(?:(?!\1).)*)(?=\1(?:\s|/?>)))\1"""
                 rf"""|https?://[^\s<]+""", re.DOTALL)
# A start tag: `<`, an ASCII letter and the rest of the tag name, whitespace
# or `/`, then the part that can hold an attribute, group 1, up to the next `<`
# or `>` that is not in a quoted attribute value, and group 2, the `>` that
# closes the tag when that is the character the part ends at. A tag name here
# holds no `<`, so a run of `<` is read in linear time. A quoted value is read
# to the first quote of its kind and its `=` is read once, so no character of
# the part is read twice unless a value has no closing quote, and only the
# last value of each kind in the text can have none.
START_TAG = re.compile(r"""<[A-Za-z][^\s/<>]*[\s/]((?:[^<>=]|=\s*(?:"[^"]*"|'[^']*')?)*)(>?)""")
# A fence of a fenced code block, read where the text of the block quote or
# list item that holds it starts, or from the start of its line outside one,
# on a line whose tabs are expanded: at most three spaces, then a run of
# backticks with no backtick after it on the line, or a run of tildes. A
# closing fence has only spaces after it. A ``` or ~~~ line indented four or
# more columns from there is not a fence, and the lines below it are read as
# usual.
OPENING_FENCE = re.compile(r" {0,3}(?:(`{3,})[^`]*|(~{3,}).*)$")
CLOSING_FENCE = re.compile(r" {0,3}(`{3,}|~{3,}) *$")
# A block quote marker, as CommonMark reads one where a line or the text of a
# block quote or list item starts.
QUOTE_MARKER = re.compile(r" {0,3}> ?")
# A list item marker: a bullet, or one to nine digits, group 1, and a `.` or
# `)`, followed by a space or the end of the line.
MARKER = re.compile(r"(?:[-+*]|([0-9]{1,9})[.)])(?= |$)")
# The start of an ATX heading and the underline of a setext heading. With a
# fence, a block quote marker, a list marker and a thematic break, these are
# the lines that end a paragraph: any other line that is not blank continues
# one.
ATX = re.compile(r"#{1,6}(?= |$)")
SETEXT = re.compile(r"(?:=+|-+)$")
# A link reference definition on a line of its own, read where its text
# starts: a label, group 1, that holds a `[` or `]` only escaped and is not
# all spaces; `:`; a destination, group 2, in `<` and `>` or without spaces or
# controls; and a title, after a space, in quotes or parentheses.
DEFINITION = re.compile(r"""\[(?! *\])((?:\\.|[^\\\[\]])+)\]: *"""
                        r"""(<(?:\\.|[^\\<>])*>|[^<\x00-\x20\x7f][^\x00-\x20\x7f]*)"""
                        r"""(?: +(?:"(?:\\.|[^\\"])*"|'(?:\\.|[^\\'])*'|\((?:\\.|[^\\()])*\)))? *""")
ESCAPE = re.compile(r"\\.")
SPACES = re.compile(r" *")
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


def blank(m: re.Match) -> str:
    """Spaces in place of a span, so the rest of its line keeps its place."""
    return " " * len(m.group())


def is_definition(line: str, start: int) -> bool:
    """Whether the line, from `start`, is one whole link reference definition,
    as CommonMark reads one: a label of at most 999 characters, and a
    destination outside `<` and `>` whose unescaped parentheses are in
    balanced pairs."""
    m = DEFINITION.fullmatch(line, start)
    if not m or len(m.group(1)) > 999:
        return False
    depth = 0
    if not m.group(2).startswith("<"):
        for c in ESCAPE.sub("", m.group(2)):
            depth += (c == "(") - (c == ")")
            if depth < 0:
                return False
    return depth == 0


def code_block_lines(lines: list) -> set:
    """The numbers of the lines that open, hold or close a fenced code block,
    read as the module docstring says: block quotes and list items are
    followed as CommonMark reads them, a fence's indentation is counted from
    where the text of the one it is in starts, and a block that is still open
    where its block quote or list item ends is closed there."""
    code = set()
    # The block quotes and list items open after the last line read, outermost
    # first: None for a block quote, and for a list item how many columns its
    # content starts after where the text of the one it is in starts.
    containers = []
    # Where the block quotes are in `containers`. A blank line stays in a list
    # item and leaves a block quote, so it ends the first block quote it
    # reaches and every container in it.
    quotes = []
    # The block the last line read is in, in the innermost container: a
    # paragraph, a fenced code block given as the character and length of
    # its fence, or None for any other.
    leaf = None
    # The paragraph holds only link reference definitions, each on a line of
    # its own: CommonMark reads no setext heading there.
    definitions = False
    empty = False  # The innermost item is a marker with nothing after it.

    def close(held: int) -> None:
        """End the containers after the first `held`."""
        del containers[held:]
        del quotes[bisect.bisect_left(quotes, held):]

    for n, line in enumerate(lines, 1):
        # A tab reaches the next column that is a multiple of four.
        line = line.expandtabs(4).rstrip(" ")
        was_empty, empty = empty, False
        # The containers the line stays in, and `pos`, where its text starts
        # in the last of them.
        pos = held = 0
        # Where the run of spaces last scanned ends. `pos` only moves on, so
        # while it is inside that run the run is not scanned again.
        run_end = -1
        while held < len(containers):
            width = containers[held]
            if width is None:
                m = QUOTE_MARKER.match(line, pos)
                if not m:
                    break
                pos = m.end()
            elif pos == len(line):
                # A blank line, which stays in each list item up to the next
                # block quote, but not in one with nothing after its marker.
                i = bisect.bisect_left(quotes, held)
                held = (quotes[i] if i < len(quotes)
                        else len(containers) - (1 if was_empty else 0))
                break
            else:
                if run_end < pos:
                    run_end = SPACES.match(line, pos).end()
                if run_end - pos < width:
                    break
                pos += width
            held += 1
        if isinstance(leaf, tuple) and held == len(containers):
            # A line of the block, or the fence that closes it.
            code.add(n)
            m = CLOSING_FENCE.match(line, pos)
            if m and m.group(1)[0] == leaf[0] and len(m.group(1)) >= leaf[1]:
                leaf = None
            continue
        if pos == len(line):
            # A blank line ends a paragraph, and the containers it leaves.
            close(held)
            leaf = None
            continue
        # A line that opens no block continues a paragraph open above it: one
        # in the innermost container the line stays in (`below`), or, as a
        # lazy continuation line, one in a container it leaves, which then
        # stays open. A setext underline and a list marker are read against
        # `below`.
        paragraph = leaf == "paragraph"
        below = paragraph and held == len(containers)
        # A thematic break is three or more of one of these characters and
        # nothing else but spaces, so one can start only in the run of them
        # that ends the line: found once, for a line read in linear time.
        last = line[-1]
        tail = len(line.rstrip(last + " ")) if last in "*-_" else len(line)
        while True:
            start = SPACES.match(line, pos).end()
            if start - pos >= 4:
                # Indented code, which cannot interrupt a paragraph, or more
                # of one: no block opens.
                if not paragraph:
                    close(held)
                    leaf = None
                else:
                    definitions = definitions and is_definition(line, start)
                break
            if line[start] == ">":
                close(held)
                quotes.append(held)
                containers.append(None)
                held += 1
                pos = start + 1 + (line[start + 1:start + 2] == " ")
                leaf = None
                paragraph = below = False
                if pos >= len(line):
                    break
                # What follows the marker is read as a line of the new block
                # quote.
                continue
            m = OPENING_FENCE.match(line, start)
            if m:
                close(held)
                run = m.group(1) or m.group(2)
                leaf = (run[0], len(run))
                code.add(n)
                break
            # Below definitions alone, a setext underline is read as any
            # other line.
            if (ATX.match(line, start) or below and not definitions and SETEXT.match(line, start)
                    or start >= tail and line.count(last, start) >= 3):
                close(held)
                leaf = None
                break
            m = MARKER.match(line, start)
            # Right below a paragraph line in the same containers (`below`), a
            # marker opens an item only with text after it, and a numbered one
            # only as number 1.
            if m and not (below and (m.end() == len(line) or int(m.group(1) or 1) != 1)):
                close(held)
                empty = m.end() == len(line)
                # The content starts after one to four spaces; after five or
                # more, and in an item with nothing in it, one column on.
                spaces = SPACES.match(line, m.end()).end() - m.end()
                width = m.end() - pos + (spaces if 1 <= spaces <= 4 else 1)
                containers.append(width)
                held += 1
                pos += width
                leaf = None
                paragraph = below = False
                if empty:
                    break
                # What follows the marker is read as a line of the new item.
                continue
            # Text: more of a paragraph when one is open above the line.
            if not paragraph:
                close(held)
                leaf = "paragraph"
                definitions = True
            definitions = definitions and is_definition(line, start)
            break
    return code


def prose_urls(block: list) -> list:
    """Return (line number, target) for every URL in a block of prose, given
    as (line number, line, prose) triples, where the prose is the line with
    its code spans and link forms blanked out. A quoted attribute value in a
    start tag may continue onto the following lines of the block."""
    text = "\n".join(prose for _, _, prose in block)
    starts = [0]
    for _, _, prose in block[:-1]:
        starts.append(starts[-1] + len(prose) + 1)
    tags = None
    found = []
    m = URL.search(text)
    while m:
        if m.group(3) is not None:
            if tags is None:
                # The prose with the `<` and `>` of its code spans and link
                # forms put back, which end an attribute part too.
                marks = "\n".join("".join(c if c in "<>" else p for c, p in zip(line, prose))
                                  for _, line, prose in block)
                tags = [t.span(1) for t in START_TAG.finditer(marks) if t.group(2)]
            # The last attribute part that starts at or before the `=`.
            i = bisect.bisect_right(tags, (m.start(), len(text))) - 1
            if i < 0 or tags[i][1] <= m.start():
                # Outside a start tag the quote opens no value, and the search
                # goes on at the scheme, where the first URL it can find is
                # the bare URL at the scheme. When whitespace or `<` follows
                # the scheme no bare URL starts there, and it finds a later
                # URL, which may be another value outside a start tag, or
                # none: the loop tests what it found.
                m = URL.search(text, m.start(3))
                continue
        if m.group(1) is None:
            start, target = m.start(), bare_url(m.group())
        else:
            group = 2 if m.group(2) is not None else 3
            start, target = m.start(group), attribute_url(m.group(group))
        found.append((block[bisect.bisect_right(starts, start) - 1][0], target))
        m = URL.search(text, m.end())
    return found


def link_targets(text: str) -> list:
    """Return (line number, target) for every followable link in the text."""
    found = []
    block = []
    lines = text.splitlines()
    code = code_block_lines(lines)
    for n, line in enumerate(lines, 1):
        if n in code or not line.strip(" \t"):
            # A line of a fenced code block or a blank line ends a block of
            # prose.
            found += prose_urls(block)
            block = []
            continue
        unspanned = CODE_SPAN.sub(blank, line)
        for pattern in (INLINE, REFDEF):
            for m in pattern.finditer(unspanned):
                found.append((n, unescape_destination(m.group(1))))
        for m in AUTOLINK.finditer(unspanned):
            found.append((n, m.group(1)))
        prose = unspanned
        for pattern in (INLINE_SPAN, REFDEF, AUTOLINK):
            prose = pattern.sub(blank, prose)
        block.append((n, line, prose))
    found += prose_urls(block)
    # A stable sort keeps the link forms of a line before its URLs in prose.
    return sorted(found, key=lambda target: target[0])


def heading_anchors(text: str) -> set:
    """GitHub-style anchors for the headings of a Markdown file."""
    anchors = set()
    seen = {}
    lines = text.splitlines()
    code = code_block_lines(lines)
    for n, line in enumerate(lines, 1):
        m = None if n in code else re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
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
    if file != ROOT and ROOT not in file.parents:
        return "outside this repository"
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
        except (http.client.HTTPException, ConnectionError) as e:
            # Raised while the response is read, which urllib does not wrap in
            # URLError: a connection closed before a reply, or a reply whose
            # status line is not HTTP. That line is in the message with its
            # line break, so whitespace is collapsed to keep the report on
            # one line.
            if attempt == 1:
                return f"request failed: {type(e).__name__}: {' '.join(str(e).split())}"
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
