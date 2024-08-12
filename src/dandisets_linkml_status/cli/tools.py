from typing import Optional

from linkml.validator import Validator
from linkml.validator.plugins import ValidationPlugin, JsonschemaValidationPlugin
from pydantic2linkml.gen_linkml import translate_defs


def get_validator(
    validation_plugins: Optional[list[ValidationPlugin]] = None,
) -> Validator:
    """
    To obtain a LinkML validator instance set up with schema produced by
    the pydantic2linkml translator, for DANDI models expressed in Pydantic,
    and given validation plugins.

    :param validation_plugins: The list of given validation plugins to set up
        the validator with. If no validation plugins are given, a default of a list
        containing a `JsonschemaValidationPlugin` instance with `closed=True` is used.
    :return: The LinkML validator instance.
    """

    if validation_plugins is None:
        validation_plugins = [JsonschemaValidationPlugin(closed=True)]

    return Validator(
        translate_defs("dandischema.models"), validation_plugins=validation_plugins
    )
