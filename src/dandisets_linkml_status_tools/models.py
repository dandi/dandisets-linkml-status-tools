from typing import Any

from dandisets_linkml_status_tools.cli.models import JsonValidationErrorView
from typing_extensions import TypedDict  # Required for Python < 3.12 by Pydantic

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


# Build a `TypedDict` for representing a polished version of `ValidationResult`
field_annotations = {
    name: info.annotation
    for name, info in ValidationResult.model_fields.items()
    if name not in {"instance", "source"}
}
field_annotations["source"] = JsonValidationErrorView
PolishedValidationResult = TypedDict(
    "PolishedValidationResult",
    field_annotations,
)


def polish_validation_results(
    results: list[ValidationResult],
) -> list[PolishedValidationResult]:
    """
    Polish the `ValidationResult` objects in a list to exclude their `instance` field
    and include their `source` field for serialization.

    Note: This function is intended to be used to handle `ValidationResult` objects
    produced by `linkml.validator.plugins.JsonschemaValidationPlugin`. The `source`
    field of these `ValidationResult` objects is expected to be a
    `jsonschema.exceptions.ValidationError` object.

    :param results: The list of `ValidationResult` objects to be polished.

    :return: The list of `PolishedValidationResult` objects representing the polished
        `ValidationResult` objects.

    :raises ValueError: If the `source` field of a `ValidationResult` object is not a
        `jsonschema.exceptions.ValidationError` object.
    """
    polished_results = []
    for result in results:
        result_as_dict = result.model_dump()

        # Remove the `instance` field
        del result_as_dict["instance"]

        # Include the `source` field as a `JsonValidationErrorView` object
        result_source = result.source
        # noinspection PyTypeChecker
        result_as_dict["source"] = JsonValidationErrorView(
            message=result_source.message,
            absolute_path=result_source.absolute_path,
            absolute_schema_path=result_source.absolute_schema_path,
            validator=result_source.validator,
            validator_value=result_source.validator_value,
        )

        polished_results.append(result_as_dict)
    return polished_results
