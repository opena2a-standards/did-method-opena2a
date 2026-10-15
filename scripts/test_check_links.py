#!/usr/bin/env python3
"""Tests for check_links.py. python3 standard library only.

Run from the repository root: python3 -m unittest discover -s scripts
"""
from __future__ import annotations

import socket
import sys
import tempfile
import threading
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

    def test_value_outside_a_start_tag_is_not_read_across_lines(self):
        # Each later quote is followed by whitespace or `>`, as in a tag.
        for text in ("x='https://example.org/a\nthe users' guide\n",
                     'x="https://example.org/a\na 12" ruler\n',
                     'x="https://example.org/a\nthe ">" sign\n',
                     '<b>x="https://example.org/a\nthe ">" sign</b>\n',
                     '<a="https://example.org/a\nb">t</a>\n',
                     '<1 x="https://example.org/a\nb">t</a>\n',
                     '<a < href="https://example.org/a\nb">t</a>\n',
                     '<a x > href="https://example.org/a\nb">t</a>\n'):
            self.assertEqual(check_links.link_targets(text), [(1, "https://example.org/a")],
                             text)

    def test_tag_that_no_greater_than_closes_is_not_a_start_tag(self):
        for text in ("If a <b then x='https://example.org/a\nthe users' guide\n",
                     '<a href="https://example.org/a\nb" title="t"\n',
                     '<a href="https://example.org/a\nb" <b>\n'):
            self.assertEqual(check_links.link_targets(text), [(1, "https://example.org/a")],
                             text)

    def test_earlier_quoted_value_that_holds_a_less_than_or_greater_than_stays_in_the_tag(self):
        # The HTML tokenizer keeps a `<` or `>` in a quoted value.
        for text in ('<a title=">" href="https://example.org/a\nb">t</a>\n',
                     "<a title='<' href=\"https://example.org/a\nb\">t</a>\n",
                     '<a title = "a > b" href="https://example.org/a\nb">t</a>\n'):
            self.assertEqual(check_links.link_targets(text), [(1, "https://example.org/ab")],
                             text)

    def test_less_than_or_greater_than_in_a_code_span_or_link_form_ends_the_attribute_part(self):
        self.assertEqual(check_links.link_targets('<a `>` href="https://example.org/a\nb">t</a>\n'),
                         [(1, "https://example.org/a")])
        self.assertEqual(check_links.link_targets('<a `<` href="https://example.org/a\nb">t</a>\n'),
                         [(1, "https://example.org/a")])
        self.assertEqual(check_links.link_targets('<a <https://example.org/x> '
                                                  'href="https://example.org/a\nb">t</a>\n'),
                         [(1, "https://example.org/x"), (1, "https://example.org/a")])
        self.assertEqual(check_links.link_targets('<a [>](y) href="https://example.org/a\nb">t</a>\n'),
                         [(1, "y"), (1, "https://example.org/a")])

    def test_value_whose_line_break_comes_before_its_url_is_read_as_one_only_in_a_start_tag(self):
        self.assertEqual(check_links.link_targets('x="\nhttps://example.org/a b" c\n'),
                         [(2, "https://example.org/a")])
        self.assertEqual(check_links.link_targets("x='  \n  https://example.org/a b' c\n"),
                         [(2, "https://example.org/a")])
        self.assertEqual(check_links.link_targets('<a href="\nhttps://example.org/a\nb">t</a>\n'),
                         [(2, "https://example.org/ab")])
        self.assertEqual(check_links.link_targets('<a href="\n  https://example.org/a">t</a>\n'),
                         [(2, "https://example.org/a")])

    def test_url_in_a_value_is_reported_at_the_line_of_its_scheme(self):
        self.assertEqual(check_links.link_targets('<a href=\n"https://example.org/a">t</a>\n'),
                         [(2, "https://example.org/a")])
        self.assertEqual(check_links.link_targets('<a href="&#10;https://example.org/a">t</a>\n'),
                         [(1, "https://example.org/a")])

    def test_value_outside_a_start_tag_with_no_bare_url_at_its_scheme_is_not_a_target(self):
        # Whitespace or `<` follows the scheme, and the block holds no other URL.
        for text in ('x="https://\nb" c\n',
                     'x="https:// foo\nbar" baz\n',
                     "x='http://\nb'>\n",
                     'Set href="https://<your-host>/callback\nto your host name" first.\n'):
            self.assertEqual(check_links.link_targets(text), [], text)

    def test_text_after_the_opening_quote_of_such_a_value_is_read_as_any_other(self):
        # The second value is outside a start tag too, so its URL is a bare URL.
        self.assertEqual(check_links.link_targets('x="https://\ny=\'https://example.org/a\n'
                                                  'the users\' guide" z\n'),
                         [(2, "https://example.org/a")])
        # The second value is in a start tag, so it is read across lines.
        self.assertEqual(check_links.link_targets('x="https://\n<a href=\'https://example.org/a\n'
                                                  'b\'>t</a>" z\n'),
                         [(2, "https://example.org/ab")])
        self.assertEqual(check_links.link_targets('x="https://\nb" c https://example.org/d\n'),
                         [(2, "https://example.org/d")])

    def test_value_in_a_start_tag_that_opens_on_an_earlier_line_is_read_across_lines(self):
        self.assertEqual(check_links.link_targets('<a\n  href="https://example.org/a\nb">t</a>\n'),
                         [(2, "https://example.org/ab")])
        self.assertEqual(targets('<a title="t" href="https://example.org/a\nb">t</a>\n'),
                         ["https://example.org/ab"])
        self.assertEqual(targets('<img/src="https://example.org/a\nb">\n'),
                         ["https://example.org/ab"])

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


class CodeFences(unittest.TestCase):
    def test_fence_indented_up_to_three_spaces_hides_its_lines(self):
        for indent in ("", " ", "  ", "   "):
            for fence in ("```", "~~~"):
                text = f"{indent}{fence}\nhttps://example.org/a\n{indent}{fence}\n"
                self.assertEqual(targets(text), [], text)

    def test_line_indented_four_spaces_or_a_tab_is_not_a_fence(self):
        # CommonMark reads it as an indented code block, which renders the
        # fence as text, so the URL on the next line is a link.
        for indent in ("    ", "     ", "\t", "  \t"):
            for fence in ("```", "~~~"):
                text = f"{indent}{fence}\nhttps://example.org/a\n"
                self.assertEqual(check_links.link_targets(text),
                                 [(2, "https://example.org/a")], text)

    def test_lines_after_an_indented_fence_line_are_read(self):
        text = "    ```\n\nSee https://example.org/a.\n\n[b](https://example.org/b)\n"
        self.assertEqual(targets(text), ["https://example.org/a", "https://example.org/b"])

    def test_indented_fence_line_does_not_close_a_fence(self):
        text = "```\n    ```\nhttps://example.org/a\n```\nhttps://example.org/b\n"
        self.assertEqual(targets(text), ["https://example.org/b"])

    def test_heading_after_an_indented_fence_line_has_an_anchor(self):
        self.assertEqual(check_links.heading_anchors("    ```\n# Title\n"), {"title"})
        self.assertEqual(check_links.heading_anchors("```\n    ```\n# Code\n```\n# Title\n"),
                         {"title"})

    def test_fence_indentation_in_a_list_item_is_counted_from_the_item_content(self):
        # Each fence is indented four or more spaces, or a tab, from the start
        # of the line and at most three from the content of its list item, so
        # each of these holds a fenced code block, as in CommonMark.
        for text in (
            "- step\n\n    ```\n    https://example.org/x\n    ```\n",
            "1. step\n\n    ```\n    https://example.org/x\n    ```\n",
            "- a\n  - b\n\n      ```\n      https://example.org/x\n      ```\n",
            "- step\n\n\t```\n\thttps://example.org/x\n\t```\n",
            "- step\n\n  \t~~~\n  \thttps://example.org/x\n  \t~~~\n",
        ):
            self.assertEqual(check_links.link_targets(text), [], text)

    def test_fence_indented_four_spaces_from_the_item_content_is_not_a_fence(self):
        for text in (
            "- step\n\n      ```\n      https://example.org/x\n",
            "- step\n\n\t\t```\n\t\thttps://example.org/x\n",
        ):
            self.assertEqual(check_links.link_targets(text),
                             [(4, "https://example.org/x")], text)

    def test_closing_fence_in_a_list_item_is_counted_from_the_item_content(self):
        # The closing fence is indented four spaces from the start of the line
        # and one, or three, from the item's content.
        for text, line in (
            ("1. a\n\n   ```\n   code\n    ```\n\nSee https://example.org/after\n", 7),
            ("1. a\n\n   ```\n   code\n    ```\n\n   See https://example.org/after\n", 7),
            ("- a\n  ```\n  code\n     ```\n  See https://example.org/after\n", 5),
        ):
            self.assertEqual(check_links.link_targets(text),
                             [(line, "https://example.org/after")], text)
        self.assertEqual(
            check_links.heading_anchors("1. a\n\n   ```\n   code\n    ```\n\n## After\n"),
            {"after"})
        # Four spaces from the item's content: a line of the block.
        text = ("1. a\n\n   ```\n       ```\n   https://example.org/x\n   ```\n\n"
                "See https://example.org/after\n")
        self.assertEqual(check_links.link_targets(text), [(8, "https://example.org/after")])

    def test_fenced_block_ends_where_its_list_item_ends(self):
        for text, line in (
            ("- a\n  ```\n  code\nSee https://example.org/after\n", 4),
            ("- a\n  - b\n    ```\n    code\n  https://example.org/after\n", 5),
            ("- a\n  ```\n\n  code\n\nSee https://example.org/after\n", 6),
        ):
            self.assertEqual(check_links.link_targets(text),
                             [(line, "https://example.org/after")], text)
        self.assertEqual(check_links.heading_anchors("- a\n  ```\n  code\n# After\n"), {"after"})
        # A blank line, and a line indented to the item's content, are in it.
        text = "- a\n  ```\n\n  https://example.org/x\n\n  ```\n"
        self.assertEqual(check_links.link_targets(text), [])
        # The lines below the item are read, each of them.
        text = "- a\n  ```\n  code\nSee https://example.org/after\nand https://example.org/more\n"
        self.assertEqual(check_links.link_targets(text),
                         [(4, "https://example.org/after"), (5, "https://example.org/more")])
        # The line that ends the block continues no paragraph of the item, so
        # the item ends too and the fence below it is indented four spaces.
        text = "10. a\n    ```\n    code\nb\n\n    ```\n    https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(7, "https://example.org/x")])

    def test_line_indented_to_an_outer_item_ends_the_inner_item_only(self):
        # `c` is in `- a` and ends `- b`. The first fence is indented three
        # spaces from the content of `- a`; the second five, and it would be
        # three from the content of `- b`.
        text = "- a\n  - b\n\n  c\n\n     ```\n     https://example.org/x\n     ```\n"
        self.assertEqual(check_links.link_targets(text), [])
        text = "- a\n  - b\n\n  c\n\n       ```\n       https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(7, "https://example.org/x")])

    def test_fence_line_is_not_read(self):
        # Neither the line that opens a block nor the one that closes it,
        # at the start of a line and in a list item.
        for text in (
            "```sh https://example.org/x\ncode\n``` https://example.org/y\n",
            "- a\n\n    ```sh https://example.org/x\n    code\n    ``` https://example.org/y\n",
        ):
            self.assertEqual(check_links.link_targets(text), [], text)

    def test_fence_on_the_line_of_a_list_marker(self):
        for text in (
            "- ```\n  https://example.org/x\n  ```\n\nSee https://example.org/after\n",
            "1. - ~~~\n     https://example.org/x\n     ~~~\n\nSee https://example.org/after\n",
        ):
            self.assertEqual(check_links.link_targets(text),
                             [(5, "https://example.org/after")], text)

    def test_each_list_marker_opens_an_item(self):
        # The fence is indented three spaces from the item's content.
        for marker in ("-", "+", "*", "1.", "1)", "0.", "7)", "123456789."):
            pad = " " * (len(marker) + 4)
            text = f"{marker} a\n\n{pad}```\n{pad}https://example.org/x\n{pad}```\n"
            self.assertEqual(check_links.link_targets(text), [], text)

    def test_line_without_a_list_marker_opens_no_item(self):
        # No space after the marker, ten digits, another delimiter, a letter,
        # a marker indented four spaces. The fence is indented four or more
        # spaces, and would be at the content of an item the line opened.
        for first, indent in (("-a", 4), ("1.a", 4), ("1234567890. a", 13), ("1: a", 4),
                              ("a. b", 4), ("    - a", 6)):
            pad = " " * indent
            text = f"{first}\n\n{pad}```\n{pad}https://example.org/x\n"
            self.assertEqual(check_links.link_targets(text),
                             [(4, "https://example.org/x")], text)

    def test_item_content_starts_after_the_spaces_that_follow_the_marker(self):
        hidden = (
            # Four spaces after the marker: content at column 5.
            "-    a\n\n        ```\n        https://example.org/x\n        ```\n",
            # Five: content one column after the marker, as for indented code.
            "-     a\n\n     ```\n     https://example.org/x\n     ```\n",
            # A marker indented three spaces, and a tab after a marker.
            "   - a\n\n        ```\n        https://example.org/x\n        ```\n",
            "-\ta\n\n\t```\n\thttps://example.org/x\n\t```\n",
        )
        for text in hidden:
            self.assertEqual(check_links.link_targets(text), [], text)
        read = (
            "-    a\n\n         ```\n         https://example.org/x\n",
            "-    a\n\n    ```\n    https://example.org/x\n",
            "-     a\n\n      ```\n      https://example.org/x\n",
        )
        for text in read:
            self.assertEqual(check_links.link_targets(text),
                             [(4, "https://example.org/x")], text)

    def test_item_with_nothing_after_its_marker(self):
        # Its content starts one column after the marker.
        for text in (
            "1.\n    ```\n    https://example.org/x\n    ```\n",
            "1.\n   a\n\n    ```\n    https://example.org/x\n    ```\n",
        ):
            self.assertEqual(check_links.link_targets(text), [], text)
        # A blank line right below the marker ends the item, and so does a
        # line indented less than its content: it has no paragraph to continue.
        text = "1.\n\n    ```\n    https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(4, "https://example.org/x")])
        text = "1.\nb\n\n    ```\n    https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(5, "https://example.org/x")])
        # One item in another: the blank line ends the inner one only.
        text = "* *\n\n     ```\n     https://example.org/x\n     ```\n"
        self.assertEqual(check_links.link_targets(text), [])

    def test_paragraph_line_without_indentation_continues_a_list_item(self):
        # CommonMark's lazy continuation line: the item is still open below it.
        for second in ("b", "#b", "####### b", "===", "1234567890. b"):
            text = f"10. a\n{second}\n\n    ```\n    https://example.org/x\n    ```\n"
            self.assertEqual(check_links.link_targets(text), [], text)
        # A line indented four spaces from the list is one whatever it holds.
        text = ("- a\n - b\n  - c\n   - d\n    - e\n\n         ```\n"
                "         https://example.org/x\n")
        self.assertEqual(check_links.link_targets(text), [(8, "https://example.org/x")])
        text = ("- a\n - b\n  - c\n   - d\n    - e\n\n        ```\n"
                "        https://example.org/x\n        ```\n")
        self.assertEqual(check_links.link_targets(text), [])

    def test_line_that_does_not_continue_a_paragraph_ends_a_list_item(self):
        # After a blank line, or a line that opens a block: a heading, a
        # thematic break, a fence or another list item.
        for second in ("\nb", "# b", "###### b", "#", "***", "---", "___", "_ _ _"):
            text = f"10. a\n{second}\n\n    ```\n    https://example.org/x\n"
            self.assertEqual(targets(text), ["https://example.org/x"], text)
        text = "10. a\n```\ncode\n```\n\n    ```\n    https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(7, "https://example.org/x")])
        # The fence is indented two spaces from the content of `10. a` and
        # four from the content of `- b`.
        text = "10. a\n- b\n\n      ```\n      https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(5, "https://example.org/x")])
        # After indented code, here the `a` five spaces after its marker, no
        # paragraph is open to continue.
        text = "Steps:\n-     a\nb\n\n     ```\n     https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(6, "https://example.org/x")])
        # Indented code below a blank line, indented less than the item's
        # content, ends the item: the fence is not at the content of `-    a`.
        text = "-    a\n\n    b\n     ```\n     https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(5, "https://example.org/x")])

    def test_list_marker_right_below_a_paragraph_line(self):
        # A bullet with text after it, and number 1, open an item there.
        for second in ("-   a", "1.  a", "01. a", "1)  a"):
            text = f"Steps:\n{second}\n\n    ```\n    https://example.org/x\n    ```\n"
            self.assertEqual(check_links.link_targets(text), [], text)
        # Another number, and a marker with nothing after it, do not: the
        # line is more of the paragraph.
        for second in ("2.  a", "10. a", "0.  a"):
            text = f"Steps:\n{second}\n\n    ```\n    https://example.org/x\n"
            self.assertEqual(check_links.link_targets(text),
                             [(5, "https://example.org/x")], text)
        for second in ("*", "+", "1.", "1)"):
            text = f"Steps:\n{second}\n     ```\n     https://example.org/x\n"
            self.assertEqual(check_links.link_targets(text),
                             [(4, "https://example.org/x")], text)
        # The paragraph of a list item counts as one for the item's own lines.
        text = "- Steps:\n  2.  a\n\n      ```\n      https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(5, "https://example.org/x")])
        # What follows a marker on its line is not below the paragraph: the
        # fence is indented three spaces from the content of `2. a`.
        text = "Steps:\n- 2. a\n\n        ```\n        https://example.org/x\n        ```\n"
        self.assertEqual(check_links.link_targets(text), [])
        # Below a blank line, a heading or a setext underline, and where the
        # paragraph is in an item the line is not in, any number opens one.
        for before in ("Steps:\n\n", "# Steps\n", "Steps\n===\n", "Steps\n=\n", "Steps\n--\n",
                       "Steps\n---\n", "- a\n"):
            text = f"{before}2.  a\n\n       ```\n       https://example.org/x\n       ```\n"
            self.assertEqual(check_links.link_targets(text), [], text)
        # `=== x` is not a setext underline, so the paragraph goes on.
        text = "Steps\n=== x\n2.  a\n\n    ```\n    https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(6, "https://example.org/x")])

    def test_thematic_break_is_not_a_list_item(self):
        for rule in ("- - -", "* * *", "-  - -", "* * * *"):
            text = f"{rule}\n\n    ```\n    https://example.org/x\n"
            self.assertEqual(check_links.link_targets(text),
                             [(4, "https://example.org/x")], text)
        # One in a list item: the fence is indented five spaces from the
        # content of `-`, and would be one from the content of a third `*`.
        text = "- * * *\n\n       ```\n       https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(4, "https://example.org/x")])
        # Markers followed by text are items, one in the other.
        text = "- - a\n\n      ```\n      https://example.org/x\n      ```\n"
        self.assertEqual(check_links.link_targets(text), [])

    def test_spaces_and_tabs_that_end_a_line_are_not_part_of_it(self):
        # An item with nothing after its marker, which the blank line ends,
        # and a thematic break.
        for first in ("1. ", "1.\t", "-   ", "- - - ", "* * *\t"):
            text = f"{first}\n\n    ```\n    https://example.org/x\n"
            self.assertEqual(check_links.link_targets(text),
                             [(4, "https://example.org/x")], text)
        # A setext underline, below which any number opens an item.
        text = "Steps\n===  \n2.  a\n\n    ```\n    https://example.org/x\n    ```\n"
        self.assertEqual(check_links.link_targets(text), [])

    def test_block_quote_line_ends_the_paragraph_of_a_list_item(self):
        # It is no lazy continuation line, so the item ends there and the
        # fence below is indented four spaces.
        text = "10. a\n> b\n\n    ```\n    https://example.org/x\n    ```\n"
        self.assertEqual(check_links.link_targets(text), [(5, "https://example.org/x")])

    def test_html_block_is_read_as_paragraph_text(self):
        # CommonMark ends the list item at the `<div>` line, which opens an
        # HTML block; HTML blocks are not followed here, this script's
        # simplification, so the line continues the item's paragraph and the
        # item still holds the fence.
        text = "10. a\n<div>\n\n    ```\n    https://example.org/x\n    ```\n"
        self.assertEqual(check_links.link_targets(text), [])


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


class FencedCodeBlocks(unittest.TestCase):
    def test_closing_fence_is_a_run_of_the_same_character_at_least_as_long(self):
        self.assertEqual(targets("~~~~\nhttps://example.org/a\n~~~\nhttps://example.org/b\n"), [])
        self.assertEqual(targets("```\nhttps://example.org/a\n~~~\nhttps://example.org/b\n"), [])
        self.assertEqual(check_links.link_targets("~~~\nhttps://example.org/a\n~~~~\n"
                                                  "https://example.org/b\n"),
                         [(4, "https://example.org/b")])

    def test_closing_fence_has_only_spaces_or_tabs_after_it(self):
        self.assertEqual(targets("```\nhttps://example.org/a\n``` x\nhttps://example.org/b\n"), [])
        self.assertEqual(check_links.link_targets("```\nhttps://example.org/a\n``` \t\n"
                                                  "https://example.org/b\n"),
                         [(4, "https://example.org/b")])

    def test_run_of_backticks_with_a_backtick_after_it_opens_no_fence(self):
        self.assertEqual(check_links.link_targets("``` a ```\nhttps://example.org/a\n"),
                         [(2, "https://example.org/a")])
        self.assertEqual(targets("~~~ a ~~~\nhttps://example.org/a\n"), [])

    def test_fenced_block_in_a_block_quote(self):
        self.assertEqual(check_links.link_targets("> ```\n> https://example.org/a\n> ```\n"
                                                  "https://example.org/b\n"),
                         [(4, "https://example.org/b")])
        self.assertEqual(targets("> > ~~~\n> > https://example.org/a\n> > ~~~\n"), [])
        self.assertEqual(check_links.link_targets(">```\n>https://example.org/a\n>```\n"
                                                  ">https://example.org/b\n"),
                         [(4, "https://example.org/b")])
        # The block quote of the fence is the one its line is in, not a
        # deeper one that ended above it.
        self.assertEqual(check_links.link_targets("> > a\n> ```\n> https://example.org/a\n"
                                                  "> ```\n> https://example.org/b\n"),
                         [(5, "https://example.org/b")])

    def test_fenced_block_closes_where_its_block_quote_ends(self):
        self.assertEqual(check_links.link_targets("> ```\n> https://example.org/a\n"
                                                  "https://example.org/b\n"),
                         [(3, "https://example.org/b")])
        self.assertEqual(check_links.link_targets("> ```\n> https://example.org/a\n\n"
                                                  "https://example.org/b\n"),
                         [(4, "https://example.org/b")])
        self.assertEqual(check_links.link_targets("> > ```\n> https://example.org/a\n"),
                         [(2, "https://example.org/a")])

    def test_line_in_a_fenced_block_holds_the_block_quote_markers_of_its_fence(self):
        # A `>` beyond those markers is part of the code.
        self.assertEqual(check_links.link_targets("> ```\n> > https://example.org/a\n> ```\n"
                                                  "https://example.org/b\n"),
                         [(4, "https://example.org/b")])
        self.assertEqual(check_links.link_targets("```\n> ```\nhttps://example.org/a\n```\n"
                                                  "https://example.org/b\n"),
                         [(5, "https://example.org/b")])

    def test_closing_fence_is_indented_as_its_opening_fence_can_be(self):
        for indent in ("", " ", "  ", "   "):
            for fence in ("```", "~~~"):
                text = (f"{indent}{fence}\nhttps://example.org/a\n{indent}{fence}\n"
                        "https://example.org/b\n")
                self.assertEqual(check_links.link_targets(text), [(4, "https://example.org/b")],
                                 text)
        self.assertEqual(check_links.link_targets("```\nhttps://example.org/a\n   ```\n"
                                                  "https://example.org/b\n"),
                         [(4, "https://example.org/b")])
        self.assertEqual(check_links.link_targets("> ```\n> https://example.org/a\n>    ```\n"
                                                  "> https://example.org/b\n"),
                         [(4, "https://example.org/b")])
        self.assertEqual(targets("> ```\n> https://example.org/a\n>     ```\n"
                                 "> https://example.org/b\n"), [])

    def test_fence_in_a_block_quote_is_indented_from_its_marker(self):
        self.assertEqual(targets(">    ```\n> https://example.org/a\n"), [])
        self.assertEqual(check_links.link_targets(">     ```\n> https://example.org/a\n"),
                         [(2, "https://example.org/a")])
        # A tab runs to the next multiple of four columns: three after `>`,
        # one of which is the space of the marker.
        self.assertEqual(targets(">\t```\n> https://example.org/a\n"), [])
        self.assertEqual(check_links.link_targets(">\t\t```\n> https://example.org/a\n"),
                         [(2, "https://example.org/a")])

    def test_block_quote_marker_holds_at_most_three_spaces_of_indentation(self):
        self.assertEqual(targets("   > ```\n   > https://example.org/a\n"), [])
        self.assertEqual(check_links.link_targets("    > ```\n    > https://example.org/a\n"),
                         [(2, "https://example.org/a")])

    def test_list_item_in_a_block_quote(self):
        # The fence's indentation is counted from the content of the item,
        # which starts after the block quote marker.
        for text in ("> - ```\n>   https://example.org/x\n>   ```\n",
                     "> 1. a\n>\n>       ```\n>       https://example.org/x\n>       ```\n"):
            self.assertEqual(check_links.link_targets(text), [], text)
        # The block closes where the item ends, inside the block quote.
        self.assertEqual(check_links.link_targets("> - a\n>   ```\n>   code\n"
                                                  "> https://example.org/after\n"),
                         [(4, "https://example.org/after")])

    def test_block_quote_in_a_list_item(self):
        # The block quote marker is counted from the content of the item.
        for text in ("- a\n\n  > ```\n  > https://example.org/x\n  > ```\n",
                     "1.   a\n\n     > ```\n     > https://example.org/x\n"):
            self.assertEqual(check_links.link_targets(text), [], text)
        # Four spaces from there, the line is indented code, read as prose.
        self.assertEqual(check_links.link_targets("1. a\n\n       > ```\n"
                                                  "       > https://example.org/x\n"),
                         [(4, "https://example.org/x")])
        # The block closes where the block quote ends, inside the item.
        self.assertEqual(check_links.link_targets("- > ```\n  > code\n"
                                                  "  https://example.org/after\n"),
                         [(3, "https://example.org/after")])

    def test_lazy_continuation_line_keeps_its_block_quote_and_list_item_open(self):
        # `b` continues the paragraph of the item in the block quote, so the
        # fence below it is at the item's content.
        text = "> 1.  a\nb\n>     ```\n>     https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [])
        # A blank line ends the block quote, and the same fence is then
        # indented four spaces from the marker of a new one.
        text = "> 1.  a\n\n>     ```\n>     https://example.org/x\n"
        self.assertEqual(check_links.link_targets(text), [(4, "https://example.org/x")])

    def test_code_span_ends_a_bare_url(self):
        self.assertEqual(targets("https://example.org/a`b`c\n"), ["https://example.org/a"])

    def test_heading_anchors_use_the_same_fence_rule(self):
        self.assertEqual(check_links.heading_anchors("~~~~\n~~~\n# A\n~~~~\n# B\n"), {"b"})
        self.assertEqual(check_links.heading_anchors("``` a ```\n# B\n"), {"b"})
        self.assertEqual(check_links.heading_anchors("> ```\n# B\n```\n# C\n"), {"b"})


class RelativeTargets(unittest.TestCase):
    def test_target_outside_the_repository_is_reported_even_when_its_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / "repo"
            root.mkdir()
            doc = root / "README.md"
            doc.write_text("# Top\n", encoding="utf-8")
            (root / "inside.md").write_text("# In\n", encoding="utf-8")
            outside = root.parent / "outside.md"
            outside.write_text("# Out\n", encoding="utf-8")
            with mock.patch.object(check_links, "ROOT", root):
                for target in ("../outside.md", "../missing.md", str(outside),
                               "../repo/../outside.md"):
                    self.assertIsNotNone(check_links.check_relative(doc, target), target)
                for target in ("inside.md", "inside.md#in", "./", "#top", "../repo/inside.md"):
                    self.assertIsNone(check_links.check_relative(doc, target), target)


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

    def serve(self, reply: bytes) -> tuple:
        """A local server that reads two requests, sends reply to each and
        closes the connection; returns its URL and the requests it read."""
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen()
        server.settimeout(10)
        requests = []

        def answer():
            for _ in range(2):
                try:
                    conn, _ = server.accept()
                except OSError:
                    return
                with conn:
                    requests.append(conn.recv(65536))
                    if reply:
                        conn.sendall(reply)

        thread = threading.Thread(target=answer, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(server.close)
        return f"http://127.0.0.1:{server.getsockname()[1]}/x", requests

    def test_connection_closed_without_a_reply_is_reported_as_broken(self):
        url, requests = self.serve(b"")
        with mock.patch.object(check_links.time, "sleep"):
            problem = check_links.check_remote(url)
        self.assertEqual(
            problem,
            "request failed: RemoteDisconnected: "
            "Remote end closed connection without response",
        )
        # Retried once, as a failed request is.
        self.assertEqual(len(requests), 2)

    def test_reply_that_is_not_http_is_reported_as_broken(self):
        url, requests = self.serve(b"garbage\r\n")
        with mock.patch.object(check_links.time, "sleep"):
            problem = check_links.check_remote(url)
        # The status line's line break is not in the one-line report.
        self.assertEqual(problem, "request failed: BadStatusLine: garbage")
        self.assertEqual(len(requests), 2)


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

    def test_run_of_lines_each_holding_a_value_read_across_lines_in_prose(self):
        self.assert_linear("", 'x="https://a\n" ', ' <a href="https://example.org/x">',
                           "https://example.org/x")

    def test_run_of_lines_each_holding_a_value_read_across_lines_in_a_tag(self):
        self.assert_linear("<a ", 'x="https://a\n" ', ">", "https://a")

    def test_run_of_unclosed_tags_before_a_value_read_across_lines(self):
        self.assert_linear("", "<a", ' x="https://a\nb">', "https://ab")

    def test_run_of_unclosed_tags_after_a_value_read_across_lines_in_prose(self):
        # Nothing after the run ends a tag name that could hold a `<`.
        self.assert_linear('x="https://a\nb" ', "<a", "", "https://a")

    def test_run_of_tags_holding_quoted_values_after_a_value_read_across_lines_in_prose(self):
        self.assert_linear('x="https://a\nb" ', '<a x="', "", "https://a")
        self.assert_linear('x="https://a\nb" ', "<a x='>", "", "https://a")

    def test_run_of_block_quote_markers(self):
        self.assert_linear("", ">", " https://example.org/x", "https://example.org/x")

    def test_run_of_lines_after_a_run_of_block_quote_markers(self):
        self.assert_linear(">" * (self.LENGTH // 4) + " a\n", ">\n", "https://example.org/x",
                           "https://example.org/x")
        self.assert_linear(">" * (self.LENGTH // 4) + " ```\n", "\n", "https://example.org/x",
                           "https://example.org/x")

    def test_run_of_letters_after_an_ampersand_in_an_attribute_value(self):
        self.assert_linear('<a href="https://example.org/&', "a", '">t</a>',
                           "https://example.org/&" + "a" * self.LENGTH)

    def test_run_of_whitespace_references_before_the_scheme(self):
        self.assert_linear('<a href="', "&#32;", 'https://example.org/x">t</a>',
                           "https://example.org/x")

    def test_run_of_list_markers_on_one_line(self):
        self.assert_linear("", "+ ", "[a](b)", "b")
        self.assert_linear("", "1. ", "[a](b)", "b")

    def test_run_of_list_markers_that_is_not_a_thematic_break(self):
        self.assert_linear("", "* ", "[a](b)", "b")
        self.assert_linear("", "* ", "+ * * [a](b) * *", "b")

    def test_run_of_list_items(self):
        self.assert_linear("", "- a\n", "[a](b)", "b")
        self.assert_linear("", "- a\nb\n", "[a](b)", "b")

    def test_run_of_lines_after_a_run_of_list_and_block_quote_markers(self):
        # A blank line stays in every list item, up to a block quote.
        self.assert_linear("- " * (self.LENGTH // 4) + "a\n", "\n", "[a](b)", "b")
        self.assert_linear("> - " * (self.LENGTH // 8) + "a\n", ">\n", "[a](b)", "b")
        self.assert_linear("- > " * (self.LENGTH // 8) + "a\n", "  >\n", "[a](b)", "b")


if __name__ == "__main__":
    unittest.main()
