from typing import Annotated, Any

from linkml.validator.report import ValidationResult
from pydantic import AfterValidator, PlainSerializer, TypeAdapter

from dandisets_linkml_status_tools.models import (
    check_source_jsonschema_validation_error,
    polish_validation_results,
    DandisetMetadataType,
)

PydanticValidationErrsType = list[dict[str, Any]]
LinkmlValidationErrsType = Annotated[
    list[ValidationResult],
    AfterValidator(check_source_jsonschema_validation_error),
    PlainSerializer(polish_validation_results),
]

dandiset_metadata_adapter = TypeAdapter(DandisetMetadataType)
pydantic_validation_errs_adapter = TypeAdapter(PydanticValidationErrsType)
linkml_validation_errs_adapter = TypeAdapter(LinkmlValidationErrsType)
