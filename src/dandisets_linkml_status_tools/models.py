from typing import Any

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
