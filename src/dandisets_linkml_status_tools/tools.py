from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from .models import ValidationReport


def iter_direct_subdirs(path: Path) -> Iterable[Path]:
    """
    Get an iterable of the direct subdirectories of a given path.

    :param path: The given path
    :return: The iterable of the direct subdirectories of the given path
    :raises: ValueError if the given path is not a directory
    """
    if not path.is_dir():
        raise ValueError(f"The given path is not a directory: {path}")
    return (p for p in path.iterdir() if p.is_dir())


def pydantic_validate(data: dict[str, Any] | str, model: type[BaseModel]) -> str:
    """
    Validate the given data against a Pydantic model

    :param data: The data, as a dict or JSON string, to be validated
    :param model: The Pydantic model to validate the data against
    :return: A JSON string that specifies an array of errors encountered in
        the validation (The JSON string returned in a case of any validation failure
        is one returned by the Pydantic `ValidationError.json()` method. In the case
        of no validation error, the empty array JSON expression, `"[]"`, is returned.)
    """
    if isinstance(data, str):
        validate_method = model.model_validate_json
    else:
        validate_method = model.model_validate

    try:
        validate_method(data)
    except ValidationError as e:
        return e.json()

    return "[]"


def write_reports(
    file_path: Path, reports: list[ValidationReport], type_adapter: TypeAdapter
) -> None:
    """
    Write a given list of validation reports to a specified file

    :param file_path: The path specifying the file to write the reports to
    :param reports: The list of validation reports to write
    :param type_adapter: The type adapter to use for serializing the list of reports
    """
    file_path.write_bytes(type_adapter.dump_json(reports, indent=2))
