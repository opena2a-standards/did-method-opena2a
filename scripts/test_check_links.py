#!/usr/bin/env python3
"""Tests for check_links.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import check_links


def targets(text: str) -> list:
    return [target for _, target in check_links.link_targets(text)]


class BareUrls(unittest.TestCase):
    def test_bare_url_in_prose_is_a_target(self):
        self.assertEqual(targets("See https://example.org/spec for details.\n"),
                         ["https://example.org/spec"])

    def test_trailing_punctuation_is_not_part_of_the_url(self):
        self.assertEqual(targets("Read https://example.org/a/b.\n"), ["https://example.org/a/b"])
        self.assertEqual(targets("(see https://example.org/x)\n"), ["https://example.org/x"])
        self.assertEqual(targets("At https://example.org/x, then\n"), ["https://example.org/x"])

    def test_balanced_parenthesis_stays_in_the_url(self):
        self.assertEqual(targets("https://example.org/wiki/Foo_(bar)\n"),
                         ["https://example.org/wiki/Foo_(bar)"])

    def test_bare_url_in_code_is_not_a_target(self):
        self.assertEqual(targets("Run `curl https://example.org/x` first.\n"), [])
        self.assertEqual(targets("```\ncurl https://example.org/x\n```\n"), [])

    def test_linked_url_is_read_once(self):
        text = ("[https://example.org/a](https://example.org/a) and <https://example.org/b>\n"
                "[ref]: https://example.org/c\n")
        self.assertEqual(targets(text),
                         ["https://example.org/a", "https://example.org/b", "https://example.org/c"])

    def test_bare_url_ends_at_whitespace_or_less_than_only(self):
        self.assertEqual(targets("https://example.org/a>b\n"), ["https://example.org/a>b"])
        self.assertEqual(targets("https://example.org/a<b\n"), ["https://example.org/a"])

    def test_quotation_mark_inside_a_bare_url_does_not_end_it(self):
        self.assertEqual(targets('https://example.org/a"b c\n'), ['https://example.org/a"b'])
        self.assertEqual(targets('https://example.org/?q="a"&r=1 next\n'),
                         ['https://example.org/?q="a"&r=1'])
        self.assertEqual(targets('See "https://example.org/x".\n'), ["https://example.org/x"])


class HtmlAttributes(unittest.TestCase):
    def test_url_in_a_quoted_attribute_ends_at_the_closing_quote(self):
        self.assertEqual(targets('<a href="https://example.org/x">text</a>\n'),
                         ["https://example.org/x"])
        self.assertEqual(targets('<p><img src="https://example.org/logo.png"></p>\n'),
                         ["https://example.org/logo.png"])
        self.assertEqual(targets("<a href='https://example.org/x'>text</a>\n"),
                         ["https://example.org/x"])
        self.assertEqual(targets('<a href = "https://example.org/x" title="t">text</a>\n'),
                         ["https://example.org/x"])

    def test_attribute_value_is_read_as_written(self):
        self.assertEqual(targets('<a href="https://example.org/it\'s.">text</a>\n'),
                         ["https://example.org/it's."])

    def test_value_runs_past_whitespace_and_less_than_to_the_closing_quote(self):
        self.assertEqual(targets('<a href="https://example.org/a b">t</a>\n'),
                         ["https://example.org/a b"])
        self.assertEqual(targets('<a href="https://example.org/?q=<x>">t</a>\n'),
                         ["https://example.org/?q=<x>"])

    def test_character_references_in_the_value_are_decoded(self):
        self.assertEqual(targets('<a href="https://example.org/?a=1&amp;b=2">t</a>\n'),
                         ["https://example.org/?a=1&b=2"])
        self.assertEqual(targets("<a href='https://example.org/it&#39;s'>t</a>\n"),
                         ["https://example.org/it's"])

    def test_named_reference_without_a_semicolon_is_kept_before_equals_letter_or_digit(self):
        # As a browser keeps it in an attribute value.
        for url in ("https://example.org/?q=x&section=2", "https://example.org/?q=x&para1=2",
                    "https://example.org/?q=x&copy=2", "https://example.org/?a=1&notify",
                    "https://example.org/?id=1&REGION=eu", "https://example.org/?a=1&lt=5"):
            self.assertEqual(targets(f'<a href="{url}">t</a>\n'), [url])

    def test_named_reference_is_decoded_with_its_semicolon_or_before_another_character(self):
        self.assertEqual(targets('<a href="https://example.org/a&copy/b">t</a>\n'),
                         ["https://example.org/a©/b"])
        self.assertEqual(targets('<a href="https://example.org/a&notin;b">t</a>\n'),
                         ["https://example.org/a∉b"])

    def test_whitespace_is_dropped_from_the_value_as_a_browser_does(self):
        self.assertEqual(targets('<a href="https://example.org/x ">t</a>\n'),
                         ["https://example.org/x"])
        self.assertEqual(targets('<a href="https://example.org/a&#9;b&#10;c">t</a>\n'),
                         ["https://example.org/abc"])

    def test_whitespace_between_the_equals_sign_and_the_quote(self):
        # No space after the closing quote, so a bare URL would run into the tag.
        self.assertEqual(targets('<a href = "https://example.org/x">text</a>\n'),
                         ["https://example.org/x"])
        self.assertEqual(targets('<a href=\t "https://example.org/x">text</a>\n'),
                         ["https://example.org/x"])

    def test_http_url_in_an_attribute(self):
        self.assertEqual(targets('<a href="http://example.org/x">text</a>\n'),
                         ["http://example.org/x"])

    def test_quoted_url_that_is_not_an_attribute_value_is_a_bare_url(self):
        self.assertEqual(targets('Say "https://example.org/a b" here.\n'),
                         ["https://example.org/a"])

    def test_value_with_no_closing_quote_is_read_as_a_bare_url(self):
        # The value holds a quote of the other kind and a space.
        self.assertEqual(targets('<a href="https://example.org/it\'s b\n'),
                         ["https://example.org/it's"])

    def test_value_of_the_scheme_alone_runs_to_the_closing_quote(self):
        self.assertEqual(targets('<a href="https://">text</a>\n'), ["https://"])

    def test_value_that_does_not_open_with_http_or_https_and_two_slashes_is_not_a_target(self):
        self.assertEqual(targets('<a href="https:/example.org/x">text</a>\n'), [])

    def test_attribute_on_a_continuation_line_of_its_tag(self):
        self.assertEqual(targets('<a\n  href="https://example.org/x">text</a>\n'),
                         ["https://example.org/x"])

    def test_url_between_the_tags_is_still_a_bare_url(self):
        self.assertEqual(targets('<a href="https://example.org/x">https://example.org/y</a>.\n'),
                         ["https://example.org/x", "https://example.org/y"])


class InlineLinks(unittest.TestCase):
    def test_balanced_parenthesis_stays_in_the_target(self):
        self.assertEqual(targets("[Foo](https://example.org/wiki/Foo_(bar))\n"),
                         ["https://example.org/wiki/Foo_(bar)"])
        self.assertEqual(targets("[spec](./spec_(draft).md#intro)\n"), ["./spec_(draft).md#intro"])

    def test_unbalanced_parenthesis_is_not_a_link(self):
        self.assertEqual(targets("[a](b(c)\n"), [])

    def test_parentheses_nested_two_levels_deep_are_not_a_link(self):
        # CommonMark reads this as a link to a((b)); the one-level limit is
        # this script's simplification.
        self.assertEqual(targets("[x](a((b)))\n"), [])

    def test_target_can_hold_a_later_link_that_closes(self):
        self.assertEqual(targets("[a](x[b](y))\n"), ["x[b](y)"])
        self.assertEqual(targets("[a](x[b](y)\n"), ["y"])


class RequestUrls(unittest.TestCase):
    def test_url_of_printable_ascii_is_requested_as_written(self):
        url = "https://example.org/a/b?q=<x>&r=%20#top"
        self.assertEqual(check_links.request_url(url), url)

    def test_space_control_and_non_ascii_after_the_host_are_percent_encoded(self):
        self.assertEqual(check_links.request_url("https://example.org/a b?q=\x01é#c d"),
                         "https://example.org/a%20b?q=%01%C3%A9#c%20d")


class LongLines(unittest.TestCase):
    """A line built to make a backtracking pattern retry from every position."""

    LENGTH = 120_000
    SECONDS = 1.0

    def assert_linear(self, head: str, unit: str, tail: str, want: str) -> None:
        line = head + unit * (self.LENGTH // len(unit)) + tail + "\n"
        start = time.perf_counter()
        found = targets(line)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, self.SECONDS, f"{unit!r} x {self.LENGTH // len(unit)}")
        self.assertIn(want, found)

    def test_run_of_open_brackets(self):
        self.assert_linear("[a](b) ", "[", "", "b")

    def test_run_of_unclosed_inline_links(self):
        self.assert_linear("", "[a](", " [a](b)", "b")

    def test_run_of_unclosed_link_destinations(self):
        self.assert_linear("", "](", " [a](b)", "b")

    def test_run_of_unclosed_autolinks(self):
        self.assert_linear("", "<https://a", " <https://example.org/x>", "https://example.org/x")

    def test_bare_url_ending_in_closing_parentheses(self):
        self.assert_linear("https://example.org/x", ")", "", "https://example.org/x")

    def test_unclosed_target_followed_by_a_run_of_closed_links(self):
        self.assert_linear("[a](x", "[b](y)", " [a](b)", "y")

    def test_run_of_unclosed_attribute_values(self):
        self.assert_linear("", "='https://a<", ' <a href="https://example.org/x">',
                           "https://example.org/x")


if __name__ == "__main__":
    unittest.main()
