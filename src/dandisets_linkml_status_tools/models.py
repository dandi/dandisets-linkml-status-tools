from typing import Any

from jsonschema import ValidationError
from linkml.validator.report import ValidationResult
from pydantic import BaseModel, Json

PydanticValidationErrsType = list[dict[str, Any]]


class ValidationReport(BaseModel):
    """
    A report of validation results of a data instance against a Pydantic model and
    the JSON schema generated from the model.
    """

    dandiset_identifier: str
    dandiset_version: str  # The version of the dandiset being validated

    # Error encountered in validation against a Pydantic model
    pydantic_validation_errs: Json[PydanticValidationErrsType] = []


class DandisetValidationReport(ValidationReport):
    """
    A report of validation results of a dandiset metadata instance against the
    `dandischema.models.Dandiset` or `dandischema.models.PublishedDandiset`
    Pydantic model and the corresponding JSON schema.
    """


class AssetValidationReport(ValidationReport):
    """
    A report of validation results of an asset metadata instance against the
    `dandischema.models.Asset` or `dandischema.models.PublishedAsset`
    Pydantic model and the corresponding JSON schema.
    """

    asset_id: str | None
    asset_path: str | None


def check_source_jsonschema_validation_error(
    results: list[ValidationResult],
) -> list[ValidationResult]:
    """
    Check if the `source` field of each `ValidationResult` object in a given list is a
    `jsonschema.exceptions.ValidationError` object.

    :param results: The list of `ValidationResult` objects to be checked.

    :return: The list of `ValidationResult` objects if all `source` fields are
        `jsonschema.exceptions.ValidationError` objects.

    :raises ValueError: If the `source` field of a `ValidationResult` object is not a
        `jsonschema.exceptions.ValidationError` object.
    """
    for result in results:
        result_source = result.source
        if not isinstance(result_source, ValidationError):
            msg = (
                f"Expected `source` field of a `ValidationResult` object to be "
                f"a {ValidationError!r} object, but got {result_source!r}"
            )
            raise ValueError(msg)  # noqa: TRY004
    return results
