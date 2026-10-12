#!/usr/bin/env python3
"""Tests for check_links.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest import mock

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

    def test_url_is_given_the_line_it_is_on_within_its_paragraph(self):
        text = 'Text\n<a href="https://example.org/a">t</a>\nhttps://example.org/b\n'
        self.assertEqual(check_links.link_targets(text),
                         [(2, "https://example.org/a"), (3, "https://example.org/b")])

    def test_targets_are_in_line_order_with_link_forms_before_prose_urls_on_a_line(self):
        self.assertEqual(check_links.link_targets("https://example.org/a\n"
                                                  "[t](https://example.org/b)\n"),
                         [(1, "https://example.org/a"), (2, "https://example.org/b")])
        text = "https://example.org/a [t](https://example.org/b)\n"
        self.assertEqual(check_links.link_targets(text),
                         [(1, "https://example.org/b"), (1, "https://example.org/a")])

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

    def test_name_that_is_not_in_the_table_with_its_semicolon_is_read_by_its_longest_prefix(self):
        # `&not` is in the table and a letter follows it, so it stays as written.
        url = "https://example.org/a&notit;"
        self.assertEqual(targets(f'<a href="{url}">t</a>\n'), [url])

    def test_name_that_is_in_the_table_only_with_a_semicolon_is_kept_without_it(self):
        url = "https://example.org/a&notin"
        self.assertEqual(targets(f'<a href="{url}">t</a>\n'), [url])

    def test_named_reference_of_five_or_six_characters_is_kept_before_equals(self):
        for url in ("https://example.org/?x=1&times=3", "https://example.org/?x=1&middot=3"):
            self.assertEqual(targets(f'<a href="{url}">t</a>\n'), [url])

    def test_two_character_named_reference_is_kept_before_a_letter(self):
        url = "https://example.org/?x=1&ltx=3"
        self.assertEqual(targets(f'<a href="{url}">t</a>\n'), [url])

    def test_decimal_reference_of_more_than_4300_digits_is_read_by_its_value(self):
        self.assertEqual(targets('<a href="https://example.org/&#' + "1" * 5000 + ';">t</a>\n'),
                         ["https://example.org/�"])
        self.assertEqual(targets('<a href="https://example.org/&#' + "0" * 5000 + '65;">t</a>\n'),
                         ["https://example.org/A"])

    def test_whitespace_is_dropped_from_the_value_as_a_browser_does(self):
        self.assertEqual(targets('<a href="https://example.org/x ">t</a>\n'),
                         ["https://example.org/x"])
        self.assertEqual(targets('<a href="https://example.org/a&#9;b&#10;c">t</a>\n'),
                         ["https://example.org/abc"])

    def test_only_c0_controls_and_space_are_stripped_from_the_value(self):
        self.assertEqual(check_links.attribute_url("https://example.org/x "),
                         "https://example.org/x ")
        self.assertEqual(targets('<a href="https://example.org/x&nbsp;">t</a>\n'),
                         ["https://example.org/x "])

    def test_whitespace_before_the_scheme_is_dropped(self):
        for value in (" https://example.org/x", "\t https://example.org/x",
                      "&#32;https://example.org/x", "&#x20;https://example.org/x",
                      "&#0032https://example.org/x", "&Tab;&NewLine;https://example.org/x"):
            self.assertEqual(targets(f'<a href="{value}">text</a>\n'), ["https://example.org/x"])

    def test_value_continues_onto_the_next_line_without_the_line_break(self):
        self.assertEqual(check_links.link_targets('<a href="https://example.org/a\nb">t</a>\n'),
                         [(1, "https://example.org/ab")])
        self.assertEqual(targets('Text\n<a href="https://example.org/a\nb\nc">t</a> and\n'
                                 'https://example.org/d\n'),
                         ["https://example.org/abc", "https://example.org/d"])

    def test_value_on_later_lines_closes_only_where_a_tag_can_go_on(self):
        self.assertEqual(targets('<a href="https://example.org/a\nb" title="t">t</a>\n'),
                         ["https://example.org/ab"])
        self.assertEqual(targets('<img src="https://example.org/a\nb"/>\n'),
                         ["https://example.org/ab"])
        self.assertEqual(targets('<a href="https://example.org/a\nb"\n>t</a>\n'),
                         ["https://example.org/ab"])

    def test_unclosed_value_does_not_take_a_quote_in_the_prose_below_it(self):
        self.assertEqual(check_links.link_targets('x="https://example.org/a\n'
                                                  'say "hi" https://example.org/b\n'),
                         [(1, "https://example.org/a"), (2, "https://example.org/b")])
        self.assertEqual(targets("x='https://example.org/a\nit's here\n"),
                         ["https://example.org/a"])
        self.assertEqual(targets('x="https://example.org/a\nend"\n'), ["https://example.org/a"])

    def test_value_does_not_continue_past_a_blank_line(self):
        self.assertEqual(targets('<a href="https://example.org/a\n\nb">t</a>\n'),
                         ["https://example.org/a"])

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

    def test_character_references_in_the_target_are_decoded_as_in_commonmark(self):
        self.assertEqual(targets("[a](https://example.org/?a=1&amp;b=2)\n"),
                         ["https://example.org/?a=1&b=2"])
        self.assertEqual(targets("[a]: https://example.org/f&ouml;&#246;&#xF6;\n"),
                         ["https://example.org/fööö"])
        self.assertEqual(targets("[a](https://example.org/&#0;&#xD800;)\n"),
                         ["https://example.org/��"])

    def test_reference_without_a_semicolon_or_with_an_unknown_name_is_kept(self):
        for url in ("https://example.org/?a=1&copy=2", "https://example.org/?a=1&bogus;",
                    "https://example.org/&#12345678;"):
            self.assertEqual(targets(f"[a]({url})\n"), [url])


class RequestUrls(unittest.TestCase):
    def test_url_of_printable_ascii_is_requested_as_written(self):
        url = "https://example.org/a/b?q=<x>&r=%20#top"
        self.assertEqual(check_links.request_url(url), url)

    def test_quotation_mark_and_backquote_are_requested_as_written(self):
        url = 'https://example.org/a"b`c?q="x"#`'
        self.assertEqual(check_links.request_url(url), url)

    def test_space_control_and_non_ascii_after_the_host_are_percent_encoded(self):
        self.assertEqual(check_links.request_url("https://example.org/a b?q=\x01é#c d"),
                         "https://example.org/a%20b?q=%01%C3%A9#c%20d")
        self.assertEqual(check_links.request_url("https://example.org/x "),
                         "https://example.org/x%C2%A0")

    def test_host_is_not_percent_encoded(self):
        self.assertEqual(check_links.request_url("https://exämple.org/ä"),
                         "https://exämple.org/%C3%A4")
        self.assertEqual(check_links.request_url("http://exämple.org"), "http://exämple.org")

    def test_empty_query_and_fragment_are_kept(self):
        self.assertEqual(check_links.request_url("https://example.org/a b?"),
                         "https://example.org/a%20b?")
        self.assertEqual(check_links.request_url("https://example.org/a b?#"),
                         "https://example.org/a%20b?#")


class RemoteChecks(unittest.TestCase):
    def test_encoded_url_is_requested(self):
        requested = []

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def urlopen(request, timeout):
            requested.append(request.full_url)
            return Response()

        with mock.patch.object(check_links.urllib.request, "urlopen", urlopen):
            self.assertIsNone(check_links.check_remote("https://example.org/é"))
        self.assertEqual(requested, ["https://example.org/%C3%A9"])

    def test_host_with_a_space_is_reported_as_broken(self):
        # http.client refuses the host before any connection is made.
        problem = check_links.check_remote("https://exa mple.org/a b")
        self.assertIsNotNone(problem)
        self.assertTrue(problem.startswith("invalid URL"), problem)


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

    def test_run_of_lines_each_holding_an_unclosed_attribute_value(self):
        self.assert_linear("", 'x="https://a\n', ' <a href="https://example.org/x">',
                           "https://example.org/x")

    def test_run_of_letters_after_an_ampersand_in_an_attribute_value(self):
        self.assert_linear('<a href="https://example.org/&', "a", '">t</a>',
                           "https://example.org/&" + "a" * self.LENGTH)

    def test_run_of_whitespace_references_before_the_scheme(self):
        self.assert_linear('<a href="', "&#32;", 'https://example.org/x">t</a>',
                           "https://example.org/x")


if __name__ == "__main__":
    unittest.main()
