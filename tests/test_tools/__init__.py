import pytest
from jsonschema.exceptions import ValidationError
from linkml.validator.report import Severity, ValidationResult

from dandisets_linkml_status_tools.models import JsonschemaValidationErrorType
from dandisets_linkml_status_tools.tools import get_linkml_err_counts


@pytest.mark.parametrize(
    ("error_types", "expected_counts"),
    [
        ([], []),
        (
            [
                JsonschemaValidationErrorType("integer", 1),
                JsonschemaValidationErrorType("integer", 2),
                JsonschemaValidationErrorType("string", "hello"),
            ],
            [
                (JsonschemaValidationErrorType("integer", 1), 1),
                (JsonschemaValidationErrorType("integer", 2), 1),
                (JsonschemaValidationErrorType("string", "hello"), 1),
            ],
        ),
        (
            [
                JsonschemaValidationErrorType("integer", 1),
                JsonschemaValidationErrorType("integer", 1),
                JsonschemaValidationErrorType("integer", 1),
            ],
            [(JsonschemaValidationErrorType("integer", 1), 3)],
        ),
        (
            [
                JsonschemaValidationErrorType("integer", 1),
                JsonschemaValidationErrorType("string", "hello"),
                JsonschemaValidationErrorType("string", "hello"),
                JsonschemaValidationErrorType("integer", 2),
                JsonschemaValidationErrorType("integer", 1),
                JsonschemaValidationErrorType("array", [1, 2, 3]),
                JsonschemaValidationErrorType("array", (1, 2, 3)),
            ],
            [
                (JsonschemaValidationErrorType("array", [1, 2, 3]), 1),
                (JsonschemaValidationErrorType("array", (1, 2, 3)), 1),
                (JsonschemaValidationErrorType("integer", 1), 2),
                (JsonschemaValidationErrorType("integer", 2), 1),
                (JsonschemaValidationErrorType("string", "hello"), 2),
            ],
        ),
    ],
)
def test_get_linkml_err_counts(
    error_types: list[JsonschemaValidationErrorType],
    expected_counts: list[tuple[JsonschemaValidationErrorType, int]],
):
    """
    Test the `get_linkml_err_counts` function

    :param error_types: A list of JSON schema validation error types
    :param expected_counts: A list of tuples of JSON schema validation error types
        and their expected counts
    """
    errs = []
    for t in error_types:
        jsonschema_validation_error = ValidationError(
            message="An artificial error",
            validator=t.validator,
            validator_value=t.validator_value,
        )
        validation_result = ValidationResult(
            type="jsonschema",
            severity=Severity.ERROR,
            message="What need to be fixed",
            source=jsonschema_validation_error,
        )
        errs.append(validation_result)

    counts = get_linkml_err_counts(errs)
    assert counts == expected_counts
