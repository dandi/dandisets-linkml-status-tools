from collections import Counter

import pytest

from dandisets_linkml_status_tools.tools import count_pydantic_validation_errs


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
