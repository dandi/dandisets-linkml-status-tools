from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, NamedTuple, TypeAlias

from dandi.dandiapi import VersionStatus
from jsonschema import ValidationError
from linkml.validator.report import ValidationResult
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    Json,
    PlainSerializer,
    TypeAdapter,
)
from pydantic2linkml.cli.tools import LogLevel
from typing_extensions import TypedDict  # Required for Python < 3.12 by Pydantic

# Dandi metadata instances are always objects in JSON
DandiMetadata: TypeAlias = dict[str, Any]

PydanticValidationErrsType: TypeAlias = list[dict[str, Any]]


class Config(TypedDict):
    """
    A dict for storing configuration settings for this app
    """

    output_dir_path: Path
    log_level: LogLevel


class JsonValidationErrorView(BaseModel):
    """
    A Pydantic model to represent a `jsonschema.exceptions.ValidationError` object,
    by including selective fields or properties of the original object,
    for serialization
    """

    message: str
    absolute_path: Sequence[str | int]
    absolute_schema_path: Sequence[str | int]
    validator: str
    validator_value: Any


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
        result_as_dict["source"] = JsonValidationErrorView(
            message=result_source.message,
            absolute_path=result_source.absolute_path,
            absolute_schema_path=result_source.absolute_schema_path,
            validator=result_source.validator,
            validator_value=result_source.validator_value,
        )

        polished_results.append(result_as_dict)
    return polished_results


LinkmlValidationErrsType: TypeAlias = Annotated[
    list[ValidationResult],
    AfterValidator(check_source_jsonschema_validation_error),
    PlainSerializer(polish_validation_results),
]


class DandiBaseReport(BaseModel):
    """
    A base class for any report related to a DANDI dataset
    """

    dandiset_identifier: str
    dandiset_version: str  # The version of the dandiset being validated


class ValidationReport(DandiBaseReport):
    """
    A report of validation results of a data instance against a Pydantic model and
    the JSON schema generated from the model.
    """

    # Error encountered in validation against a Pydantic model
    pydantic_validation_errs: Annotated[
        PydanticValidationErrsType, Field(default_factory=list)
    ]


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


class JsonschemaValidationErrorType(NamedTuple):
    """
    A named tuple for representing types of `jsonschema.exceptions.ValidationError`
    objects.

    The type of a `jsonschema.exceptions.ValidationError` is decided by the value of its
    `validator` field and the value of its `validator_value` field. The values
    of these fields are bundled in an instance of this named tuple to represent a type
    of `jsonschema.exceptions.ValidationError` objects.
    """

    validator: str
    validator_value: Any

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, JsonschemaValidationErrorType)
            and self.validator == other.validator
            and type(self.validator_value) is type(other.validator_value)  # noqa E721
            and self.validator_value == other.validator_value
        )


class DandisetLinkmlTranslationReport(DandiBaseReport):
    """
    A report of validation results of a dandiset (metadata) against the
    `dandischema.models.Dandiset` or `dandischema.models.PublishedDandiset` Pydantic
    model and the corresponding LinkML schema.
    """

    @property
    def dandiset_schema_version(self) -> str:
        """
        The schema version of the dandiset metadata being validated as specified in the
        metadata itself

        :return: The schema version of the dandiset metadata being validated. An empty
            indicates that no valid schema version is found in the metadata.
        """
        version = self.dandiset_metadata.get("schemaVersion", "")

        # Since there is no guarantee that the dandiset metadata is valid,
        # there is no guarantee the obtained version is a valid string.
        # If the fetched version is not a string, return an empty string to indicate,
        # there is no valid version.
        if not isinstance(version, str):
            version = ""

        return version

    # Dandiset version status as provided by the DANDI API
    dandiset_version_status: VersionStatus

    # Dandiset version modified datetime as provided by the DANDI API
    dandiset_version_modified: datetime

    # The metadata of the dandiset to be validated
    dandiset_metadata: DandiMetadata

    # Error encountered in validation against the Pydantic dandiset metadata model
    pydantic_validation_errs: Annotated[
        PydanticValidationErrsType, Field(default_factory=list)
    ]

    # Errors encountered in validation against the dandiset metadata model in LinkML
    linkml_validation_errs: Annotated[
        LinkmlValidationErrsType, Field(default_factory=list)
    ]


DandisetValidationReportsType: TypeAlias = defaultdict[
    str, Annotated[dict[str, DandisetValidationReport], Field(default_factory=dict)]
]
AssetValidationReportsType: TypeAlias = defaultdict[
    str, Annotated[dict[str, list[AssetValidationReport]], Field(default_factory=dict)]
]
ValidationReportsType: TypeAlias = (
    DandisetValidationReportsType | AssetValidationReportsType
)

# Type adapters for various types (this section should be at the end of this file)
DANDI_METADATA_ADAPTER = TypeAdapter(DandiMetadata)
PYDANTIC_VALIDATION_ERRS_ADAPTER = TypeAdapter(PydanticValidationErrsType)
LINKML_VALIDATION_ERRS_ADAPTER = TypeAdapter(LinkmlValidationErrsType)
DANDI_METADATA_LIST_ADAPTER = TypeAdapter(list[DandiMetadata])
DANDISET_VALIDATION_REPORTS_ADAPTER = TypeAdapter(DandisetValidationReportsType)
ASSET_VALIDATION_REPORTS_ADAPTER = TypeAdapter(AssetValidationReportsType)
