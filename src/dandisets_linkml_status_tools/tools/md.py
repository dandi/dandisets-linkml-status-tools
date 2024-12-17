# This file contains helpers for generating Markdown files
from collections.abc import Iterable

from dandisets_linkml_status_tools.models import PydanticValidationErrsType


def gen_row(cell_str_values: Iterable[str]) -> str:
    """
    Construct a row of a Markdown table with given cell string values
    :param cell_str_values: The given iterable of cell string values
    :return: The constructed row of a Markdown table

    Note: The given iterable of cell string values are `str` values
    """
    return f'|{"|".join(cell_str_values)}|\n'


def gen_header_and_alignment_rows(headers: Iterable[str]) -> str:
    """
    Generate a header row and an alignment row for a Markdown table

    :return: The string containing the header row followed by the alignment row
    """

    header_row = gen_row(f" {h} " for h in headers)
    alignment_row = gen_row("-" * (len(h) + 2) for h in headers)
    return header_row + alignment_row


def gen_pydantic_validation_errs_cell(
    errs: PydanticValidationErrsType, errs_file: str
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
