from typing import Any

from pydantic import TypeAdapter

from dandisets_linkml_status_tools.models import (
    DandisetMetadataType, LinkmlValidationErrsType,
)

PydanticValidationErrsType = list[dict[str, Any]]

dandiset_metadata_adapter = TypeAdapter(DandisetMetadataType)
pydantic_validation_errs_adapter = TypeAdapter(PydanticValidationErrsType)
linkml_validation_errs_adapter = TypeAdapter(LinkmlValidationErrsType)
