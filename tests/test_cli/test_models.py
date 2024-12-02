import pytest

from dandisets_linkml_status_tools.models import JsonschemaValidationErrorType


@pytest.mark.parametrize(
    ("op1", "op2", "expected_result"),
    [
        (JsonschemaValidationErrorType("integer", [1, 2]), "hello", False),
        (
            JsonschemaValidationErrorType("integer", 1),
            JsonschemaValidationErrorType("string", 1),
            False,
        ),
        (
            JsonschemaValidationErrorType("integer", 1),
            JsonschemaValidationErrorType("integer", "1"),
            False,
        ),
        (
            JsonschemaValidationErrorType("integer", 1),
            JsonschemaValidationErrorType("integer", 2),
            False,
        ),
        (
            JsonschemaValidationErrorType("integer", 42),
            JsonschemaValidationErrorType("integer", 42),
            True,
        ),
        (
            JsonschemaValidationErrorType("integer", [1, 2, 3]),
            JsonschemaValidationErrorType("integer", [1, 2, 3]),
            True,
        ),
    ],
)
def test_jsonschema_validation_error_type_equality(op1, op2, expected_result):
    """
    Test the equal operator of the `JsonschemaValidationErrorType` class
    """
    assert (op1 == op2) == expected_result
