# For tool definitions related to JSON Schema

from typing import Any

from jsonschema.protocols import Validator as JsonschemaValidator
from jsonschema.validators import validator_for

from dandisets_linkml_status_tools.models import JsonschemaValidationErrorModel


# todo: this function is available through the dandischema package if
#  https://github.com/dandi/dandi-schema/pull/278 is accepted
def jsonschema_validator(
    schema: dict[str, Any],
    *,
    check_format: bool,
    default_cls: type[JsonschemaValidator] | None = None,
) -> JsonschemaValidator:
    """
    Create a JSON schema validator appropriate for validating instances against a given
    schema

    :param schema: The JSON schema to validate against
    :param check_format: Indicates whether to check the format against format
        specifications in the schema
    :param default_cls: The default JSON schema validator class to use to create the
        validator should the appropriate validator class cannot be determined based on
        the schema (by assessing the `$schema` property). If `None`, the class
        representing the latest JSON schema draft supported by the `jsonschema` package.
    :return: The JSON schema validator
    :raises jsonschema.exceptions.SchemaError: If the JSON schema is invalid
    """
    # Retrieve appropriate validator class for validating the given schema
    validator_cls: type[JsonschemaValidator] = (
        validator_for(schema, default_cls)
        if default_cls is not None
        else validator_for(schema)
    )

    # Ensure the schema is valid
    validator_cls.check_schema(schema)

    if check_format:
        # Return a validator with format checking enabled
        return validator_cls(schema, format_checker=validator_cls.FORMAT_CHECKER)

    # Return a validator with format checking disabled
    return validator_cls(schema)


def err_lst(
    validator: JsonschemaValidator, instance: Any
) -> list[JsonschemaValidationErrorModel]:
    """
    Validate an instance with a given JSON schema validator

    :param validator: The JSON schema validator
    :param instance: The instance to validate
    :return: A list of validation errors
    """

    # Get the representations of errors in the validation in
    # `JsonschemaValidationErrorModel` objects
    # noinspection PyTypeChecker
    errs = [
        JsonschemaValidationErrorModel(
            message=e.message,
            absolute_schema_path=e.absolute_schema_path,
            absolute_path=e.absolute_path,
        )
        for e in validator.iter_errors(instance)
    ]

    # Sort the errors by their absolute schema path
    errs.sort(key=lambda err: err.absolute_schema_path)

    return errs
