# For tool definitions related to JSON Schema

from typing import Any

from jsonschema.protocols import Validator as JsonschemaValidator
from jsonschema.validators import validator_for

from dandisets_linkml_status_tools.models import JsonschemaValidationErrorModel


def jsonschema_validator(
    schema: dict[str, Any], *, check_format: bool
) -> JsonschemaValidator:
    """
    Create a JSON schema validator appropriate for validating instances against a given
    schema

    :param schema: The JSON schema to validate against
    :param check_format: Indicates whether to check the format against format
        specifications in the schema
    :return: The JSON schema validator
    """
    # Retrieve appropriate validator class for validating the given schema
    validator_cls = validator_for(schema)

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
