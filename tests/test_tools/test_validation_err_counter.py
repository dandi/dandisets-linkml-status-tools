from collections import Counter

import pytest

from dandisets_linkml_status_tools.tools.validation_err_counter import (
    ValidationErrCounter,
)


def simple_categorizer(err: tuple) -> tuple:
    """
    A simple categorizer function that:
      - Uses the first element of the error tuple to categorize errors by type
      - Returns a tuple representing the category. For example, ('TypeError',)
    """
    # In practice, you might analyze multiple elements of `err`
    return (err[0],)


@pytest.fixture
def err_counter():
    """
    Returns a ValidationErrCounter instance using our simple_categorizer above.
    """
    return ValidationErrCounter(err_categorizer=simple_categorizer)


def test_init(err_counter):
    """
    Test that the ValidationErrCounter is initialized properly.
    """
    assert isinstance(err_counter._err_ctrs_by_cat, dict)
    assert len(err_counter._err_ctrs_by_cat) == 0


def test_count_single(err_counter):
    """
    Test counting a single error.
    """
    errors = [("ValueError", "Some message")]
    err_counter.count(errors)

    err_ctrs_by_cat = err_counter._err_ctrs_by_cat

    assert set(err_ctrs_by_cat.keys()) == {("ValueError",)}
    assert err_ctrs_by_cat[("ValueError",)] == {("ValueError", "Some message"): 1}


def test_count_multiple_same_category(err_counter):
    """
    Test counting multiple errors that fall into the same category.
    """
    errors = [
        ("TypeError", "Message 1"),
        ("TypeError", "Message 2"),
        ("TypeError", "Message 1"),  # repeated error
    ]
    err_counter.count(errors)

    err_ctrs_by_cat = err_counter._err_ctrs_by_cat

    assert set(err_ctrs_by_cat.keys()) == {("TypeError",)}

    # "Message 1" appears twice, "Message 2" appears once
    assert err_ctrs_by_cat[("TypeError",)] == {
        ("TypeError", "Message 1"): 2,
        ("TypeError", "Message 2"): 1,
    }


def test_count_multiple_different_categories(err_counter):
    """
    Test counting multiple errors that fall into different categories.
    """
    errors = [
        ("TypeError", "Message A"),
        ("ValueError", "Message B"),
        ("ValueError", "Message B"),
        ("KeyError", "Message C"),
    ]
    err_counter.count(errors)

    err_ctrs_by_cat = err_counter._err_ctrs_by_cat

    assert set(err_ctrs_by_cat.keys()) == {
        ("TypeError",),
        ("ValueError",),
        ("KeyError",),
    }

    assert err_ctrs_by_cat[("TypeError",)] == {("TypeError", "Message A"): 1}
    assert err_ctrs_by_cat[("ValueError",)] == {("ValueError", "Message B"): 2}
    assert err_ctrs_by_cat[("KeyError",)] == {("KeyError", "Message C"): 1}


def test_counts_by_cat(err_counter):
    """
    Test the counts_by_cat property, which returns the sum of errors in each category.
    """
    errors = [
        ("TypeError", "Message A"),
        ("TypeError", "Message B"),
        ("KeyError", "Message C"),
        ("KeyError", "Message C"),
        ("KeyError", "Message C"),
    ]
    err_counter.count(errors)

    counts = err_counter.counts_by_cat
    # There are 2 'TypeError' errors and 3 'KeyError' error
    assert counts[("TypeError",)] == 2
    assert counts[("KeyError",)] == 3


def test_cats(err_counter):
    """
    Test the cats method, which returns the set of error categories.
    """
    errors = [
        ("TypeError", "Message 1"),
        ("ValueError", "Message 2"),
    ]
    err_counter.count(errors)
    categories = err_counter.cats()

    # Should contain exactly ("TypeError",) and ("ValueError",)
    assert categories == {("TypeError",), ("ValueError",)}


def test_getitem(err_counter):
    """
    Test the __getitem__ method, which returns a copy of the Counter for a given category.
    """
    errors = [("ValueError", "Some message")]
    err_counter.count(errors)

    value_error_counter = err_counter[("ValueError",)]

    assert isinstance(value_error_counter, Counter)
    # value_error_counter should be a copy of the original Counter
    assert value_error_counter is not err_counter._err_ctrs_by_cat[("ValueError",)]
    assert value_error_counter == {("ValueError", "Some message"): 1}


def test_items(err_counter):
    """
    Test the items method, which returns list of (category, Counter) pairs.
    """
    errors = [
        ("TypeError", "Message 1"),
        ("ValueError", "Message 2"),
    ]
    err_counter.count(errors)

    items = err_counter.items()
    # We expect two pairs: ((TypeError,), Counter) and ((ValueError,), Counter)
    assert len(items) == 2

    # Sort so we can reliably test
    items_sorted = sorted(items, key=lambda x: x[0])
    assert items_sorted[0][0] == ("TypeError",)
    assert items_sorted[1][0] == ("ValueError",)

    # Check that the counters inside match
    assert items_sorted[0][1] == {("TypeError", "Message 1"): 1}
    assert items_sorted[1][1] == {("ValueError", "Message 2"): 1}

    # Test the Counter in each pair is a copy
    for _, counter in items:
        for counter_original in err_counter._err_ctrs_by_cat.values():
            assert counter is not counter_original
