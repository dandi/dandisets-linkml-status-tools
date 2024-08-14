from typing import Any, Optional

from dandischema.models import Dandiset
from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin, ValidationPlugin
from linkml.validator.report import ValidationResult
from pydantic import ValidationError
from pydantic2linkml.gen_linkml import translate_defs


def get_linkml_validator(
    validation_plugins: Optional[list[ValidationPlugin]] = None,
) -> Validator:
    """
    To obtain a LinkML validator instance set up with schema produced by
    the pydantic2linkml translator, for DANDI models expressed in Pydantic,
    and given validation plugins.

    :param validation_plugins: The list of given validation plugins to set up
        the validator with. If no validation plugins are given, the default of a list
        containing a `JsonschemaValidationPlugin` instance with `closed=True` is used.
    :return: The LinkML validator instance.
    """

    if validation_plugins is None:
        validation_plugins = [JsonschemaValidationPlugin(closed=True)]

    return Validator(
        translate_defs("dandischema.models"), validation_plugins=validation_plugins
    )


def pydantic_validate(dandiset_metadata: dict[str, Any]) -> Optional[str]:
    """
    Validate the given dandiset metadata against the Pydantic dandiset metadata model

    :param dandiset_metadata: The dandiset metadata to validate.
    :return: A JSON string that is an array of errors encountered in the validation if
        it fails, else `None`. (The JSON string returned in a case of failure is
        one returned by the Pydantic `ValidationError.json()` method.)
    """
    try:
        Dandiset.model_validate(dandiset_metadata)
    except ValidationError as e:
        return e.json()

    return None


def linkml_validate(
    dandiset_metadata: dict[str, Any]
) -> Optional[list[ValidationResult]]:
    """
    Validate the given dandiset metadata against the dandiset metadata model in LinkML

    :param dandiset_metadata: The dandiset metadata to validate
    :return: A list of validation errors encountered in the validation if it fails,
        else `None`
    """
    validator = get_linkml_validator()
    validation_report = validator.validate(dandiset_metadata, target_class="Dandiset")
    return validation_report.results if validation_report.results else None
