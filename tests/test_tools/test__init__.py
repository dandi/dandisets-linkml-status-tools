from collections import Counter

import pytest
from jsonschema import ValidationError
from linkml.validator.report import Severity, ValidationResult

from dandisets_linkml_status_tools.models import JsonschemaValidationErrorType
from dandisets_linkml_status_tools.tools import (
    count_pydantic_validation_errs,
    get_linkml_err_counts,
)


@pytest.mark.parametrize(
    ("errs", "compress", "expected"),
    [
        # ──────────────────────────
        # Empty input
        # ──────────────────────────
        ([], False, Counter()),
        ([], True, Counter()),
        # ──────────────────────────
        # Single error
        # ──────────────────────────
        (
            [{"type": "value_error", "msg": "Invalid value", "loc": ["field_a"]}],
            False,
            Counter({("value_error", "Invalid value", ("field_a",)): 1}),
        ),
        (
            [{"type": "value_error", "msg": "Invalid value", "loc": ["field_a"]}],
            True,
            # Same as above, because there's no integer index to compress
            Counter({("value_error", "Invalid value", ("field_a",)): 1}),
        ),
        # ──────────────────────────
        # Multiple distinct errors
        # ──────────────────────────
        (
            [
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a", 0]},
                {"type": "type_error", "msg": "Wrong type", "loc": ["field_b", 2]},
                {"type": "missing_field", "msg": "Field required", "loc": ["field_c"]},
            ],
            False,
            Counter(
                {
                    ("value_error", "Invalid value", ("field_a", 0)): 1,
                    ("type_error", "Wrong type", ("field_b", 2)): 1,
                    ("missing_field", "Field required", ("field_c",)): 1,
                }
            ),
        ),
        (
            [
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a", 0]},
                {"type": "type_error", "msg": "Wrong type", "loc": ["field_b", 2]},
                {"type": "missing_field", "msg": "Field required", "loc": ["field_c"]},
            ],
            True,
            # Integer indices in loc become "[*]"
            Counter(
                {
                    ("value_error", "Invalid value", ("field_a", "[*]")): 1,
                    ("type_error", "Wrong type", ("field_b", "[*]")): 1,
                    ("missing_field", "Field required", ("field_c",)): 1,
                }
            ),
        ),
        # ──────────────────────────
        # Repeated identical errors
        # ──────────────────────────
        (
            [
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a"]},
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a"]},
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a"]},
            ],
            False,
            Counter({("value_error", "Invalid value", ("field_a",)): 3}),
        ),
        (
            [
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a"]},
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a"]},
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a"]},
            ],
            True,
            # Same as above, because there's no integer index to compress
            Counter({("value_error", "Invalid value", ("field_a",)): 3}),
        ),
        # ──────────────────────────
        # Multiple integer indices
        # ──────────────────────────
        (
            [
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a", 0]},
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a", 1]},
                {
                    "type": "type_error",
                    "msg": "Wrong type",
                    "loc": ["field_b", 2, "subfield"],
                },
            ],
            False,
            Counter(
                {
                    ("value_error", "Invalid value", ("field_a", 0)): 1,
                    ("value_error", "Invalid value", ("field_a", 1)): 1,
                    ("type_error", "Wrong type", ("field_b", 2, "subfield")): 1,
                }
            ),
        ),
        (
            [
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a", 0]},
                {"type": "value_error", "msg": "Invalid value", "loc": ["field_a", 1]},
                {
                    "type": "type_error",
                    "msg": "Wrong type",
                    "loc": ["field_b", 2, "subfield"],
                },
            ],
            True,
            # Index locations are replaced by "[*]"
            Counter(
                {
                    ("value_error", "Invalid value", ("field_a", "[*]")): 2,
                    ("type_error", "Wrong type", ("field_b", "[*]", "subfield")): 1,
                }
            ),
        ),
    ],
)
def test_count_pydantic_validation_errs(errs, compress, expected):
    """
    Test the count_pydantic_validation_errs function with 'loc' as a list rather than
    a tuple, under multiple scenarios of input errors and compression settings.
    """
    result = count_pydantic_validation_errs(errs, compress=compress)
    assert result == expected


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
