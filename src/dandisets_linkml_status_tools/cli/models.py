from datetime import datetime
from typing import Annotated, Any

from dandi.dandiapi import VersionStatus
from linkml.validator.report import ValidationResult
from pydantic import BaseModel, Json, PlainSerializer, TypeAdapter
from typing_extensions import TypedDict  # Required for Python < 3.12 by Pydantic

# A `TypedDict` that has a key corresponding to each field in `ValidationResult`
# except for the `instance` field
TrimmedValidationResult = TypedDict(
    "TrimmedValidationResult",
    {
        name: info.annotation
        for name, info in ValidationResult.model_fields.items()
        if name != "instance"
    },
)


def polish_validation_results(
    errs: list[ValidationResult],
) -> list[TrimmedValidationResult]:
    """
    Polish the `ValidationResult` objects in a list to exclude their `instance` field
    and include their `source` field for serialization.

    :param errs: The list of `ValidationResult` objects to be polished.

    :return: The list of `TrimmedValidationResult` objects representing the polished
        `ValidationResult` objects.
    """
    polished_errs = []
    for err in errs:
        err_as_dict = err.model_dump()
        del err_as_dict["instance"]
        err_as_dict["source"] = err.source

        polished_errs.append(err_as_dict)
    return polished_errs


DandisetMetadataType = dict[str, Any]
PydanticValidationErrsType = list[dict[str, Any]]
LinkmlValidationErrsType = Annotated[
    list[ValidationResult], PlainSerializer(polish_validation_results)
]

dandiset_metadata_adapter = TypeAdapter(DandisetMetadataType)
pydantic_validation_errs_adapter = TypeAdapter(PydanticValidationErrsType)
linkml_validation_errs_adapter = TypeAdapter(LinkmlValidationErrsType)


class DandisetValidationReport(BaseModel):
    """
    A report of validation results of a dandiset (metadata) against the
    `dandischema.models.Dandiset` Pydantic model and the corresponding LinkML schema.
    """

    dandiset_identifier: str
    dandiset_version: str  # The version of the dandiset being validated

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
    dandiset_metadata: DandisetMetadataType

    # Error encountered in validation against the Pydantic dandiset metadata model
    pydantic_validation_errs: Json[PydanticValidationErrsType] = []

    # Errors encountered in validation against the dandiset metadata model in LinkML
    linkml_validation_errs: LinkmlValidationErrsType = []
