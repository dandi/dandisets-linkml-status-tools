from typing import Any

from linkml.validator.report import ValidationResult
from pydantic import BaseModel, Json, TypeAdapter

DANDISET_METADATA_TYPE = dict[str, Any]
PYDANTIC_VALIDATION_ERRS_TYPE = list[dict[str, Any]]
LINKML_VALIDATION_ERRS_TYPE = list[ValidationResult]

DANDISET_METADATA_ADAPTER = TypeAdapter(DANDISET_METADATA_TYPE)
PYDANTIC_VALIDATION_ERRS_ADAPTER = TypeAdapter(PYDANTIC_VALIDATION_ERRS_TYPE)
LINKML_VALIDATION_ERRS_ADAPTER = TypeAdapter(LINKML_VALIDATION_ERRS_TYPE)


class DandisetValidationReport(BaseModel):
    """
    A report of validation results of a dandiset (metadata) against the
    `dandischema.models.Dandiset` Pydantic model and the corresponding LinkML schema.
    """

    dandiset_identifier: str
    dandiset_version: str  # The version of the dandiset being validated

    # The metadata of the dandiset to be validated
    dandiset_metadata: DANDISET_METADATA_TYPE

    # Error encountered in validation against the Pydantic dandiset metadata model
    pydantic_validation_errs: Json[PYDANTIC_VALIDATION_ERRS_TYPE] = []

    # Errors encountered in validation against the dandiset metadata model in LinkML
    linkml_validation_errs: LINKML_VALIDATION_ERRS_TYPE = []
