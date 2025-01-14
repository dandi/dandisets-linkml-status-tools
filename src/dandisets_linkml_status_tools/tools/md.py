# This file contains helpers for generating Markdown files

from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from dandisets_linkml_status_tools.models import PydanticValidationErrsType
from dandisets_linkml_status_tools.tools.typing import Stringable


def gen_row(cell_values: Iterable[Stringable]) -> str:
    """
    Construct a row of a Markdown table with given stringable cell values

    :param cell_values: The given iterable of stringable cell values
    :return: The constructed row of a Markdown table

    Note: The given iterable of cell string values are `str` values
    """
    return f'|{"|".join(str(v) for v in cell_values)}|\n'


def gen_header_and_alignment_rows(headers: Iterable[str]) -> str:
    """
    Generate a header row and an alignment row for a Markdown table

    :return: The string containing the header row followed by the alignment row
    """

    header_row = gen_row(f" {h} " for h in headers)
    alignment_row = gen_row("-" * (len(h) + 2) for h in headers)
    return header_row + alignment_row


def gen_pydantic_validation_errs_cell(
    errs: PydanticValidationErrsType, errs_file: str | Path
) -> str:
    """
    Generate the content of a cell representing Pydantic validation errors in a table
    in a Markdown file

    :param errs: The collection of Pydantic validation errors to be represented
    :param errs_file: The relative path, from the Markdown file, to the file containing
        the Pydantic validation errors
    :return: The content of the cell
    """
    from dandisets_linkml_status_tools.tools import get_pydantic_err_counts

    return (
        f"[{len(errs)} "
        f"({', '.join(f'{v} {k}' for k, v in get_pydantic_err_counts(errs).items())})]"
        f"({errs_file})"
        if errs
        else "0"
    )


def gen_diff_cell(diff: dict | list, diff_file: str | Path) -> str:
    """
    Generate the content of a cell representing a diff in a table in a Markdown file

    :param diff: The diff to be represented
    :param diff_file: The relative path, from the Markdown file, to the file containing
        the diff
    :return: The content of the cell
    """
    return f"[**DIFFERENT**]({diff_file})" if diff else "same"


def validation_err_count_table(c: dict[tuple, int]) -> str:
    """
    Generate a table of validation error counts from a `dict` object which has tuples
    as keys that represent the types of validation errors and values as integers that
    represent the counts of the errors of the corresponding types

    :param c: The `dict` object
    :return: The string presenting the table in Markdown format
    """
    return (
        # The header row and the alignment row
        gen_header_and_alignment_rows(["Error category", "Count"])
        +
        # The content rows
        "".join([gen_row((escape(str(k)), v)) for k, v in sorted(c.items())])
    )


# The set of special Markdown characters that need to be escaped
# This set doesn't include (<, >, |) because they are HTML-sensitive characters
BASE_SPECIAL_CHARS = set(r"\`*_{}[]()#+-.!")


def escape(text: str) -> str:
    r"""
    Escape the given text for Markdown.

    The function escapes special Markdown characters (\`*_{}[]()#+-.!) and
    HTML-sensitive characters (<, >, |) by adding the necessary escape sequences.

    :param text: The input text to be escaped.
    :return: The escaped text.
    """

    escaped_substrs = []
    for c in text:
        if c in BASE_SPECIAL_CHARS:
            escaped = f"\\{c}"
        elif c == "<":
            escaped = "&lt;"
        elif c == ">":
            escaped = "&gt;"
        elif c == "|":
            escaped = "&#124;"
        else:
            escaped = c
        escaped_substrs.append(escaped)

    return "".join(escaped_substrs)


def validation_err_diff_table(
    diff: dict[tuple, tuple[Counter[tuple], Counter[tuple]]]
) -> str:
    """
    Generate a table displaying the differences in two sets of validation errors by
    categories

    :param diff: The differences represented in a dictionary where the keys are tuples
        representing the categories and the values are tuples consisting of a `Counter`
        representing the validation errors removed and a `Counter` representing the
        validation errors gained from the first set of validation errors to the second
        set of validation errors in the corresponding categories
    :return: The string presenting the table in Markdown format
    """
    return (
        # The header row and the alignment row
        gen_header_and_alignment_rows(["Error category", "Removed", "Gained"])
        +
        # The content rows
        "".join(
            gen_row(
                (
                    escape(str(cat)),
                    removed.total(),
                    gained.total(),
                )
            )
            for cat, (removed, gained) in sorted(diff.items())
        )
    )
