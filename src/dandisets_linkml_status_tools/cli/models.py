from datetime import datetime
from typing import Annotated, Any

from dandi.dandiapi import VersionStatus
from linkml.validator.report import ValidationResult
from pydantic import AfterValidator, BaseModel, Json, PlainSerializer, TypeAdapter

from dandisets_linkml_status_tools.models import (
    check_source_jsonschema_validation_error,
    polish_validation_results,
)

DandisetMetadataType = dict[str, Any]
PydanticValidationErrsType = list[dict[str, Any]]
LinkmlValidationErrsType = Annotated[
    list[ValidationResult],
    AfterValidator(check_source_jsonschema_validation_error),
    PlainSerializer(polish_validation_results),
]

dandiset_metadata_adapter = TypeAdapter(DandisetMetadataType)
pydantic_validation_errs_adapter = TypeAdapter(PydanticValidationErrsType)
linkml_validation_errs_adapter = TypeAdapter(LinkmlValidationErrsType)


class DandisetLinkmlTranslationReport(BaseModel):
    """
    A report of validation results of a dandiset (metadata) against the
    `dandischema.models.Dandiset` or `dandischema.models.PublishedDandiset` Pydantic
    model and the corresponding LinkML schema.
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
