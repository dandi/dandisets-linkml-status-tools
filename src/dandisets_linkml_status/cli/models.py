from typing import Any

from linkml.validator.report import ValidationResult
from pydantic import BaseModel, Json


class DandisetValidationReport(BaseModel):
    """
    A report of validation results of a dandiset (metadata) against the
    `dandischema.models.Dandiset` Pydantic model and the corresponding LinkML schema.
    """

    dandiset_identifier: str
    dandiset_metadata: dict[str, Any]  # The metadata of the dandiset to be validated

    # Error encountered in validation against the Pydantic dandiset metadata model
    pydantic_validation_errs: Json[list[dict[str, Any]]] = []

    # Errors encountered in validation against the dandiset metadata model in LinkML
    linkml_validation_errs: list[ValidationResult] = []
