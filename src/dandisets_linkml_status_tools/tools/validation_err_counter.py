from collections import Counter, defaultdict
from collections.abc import Callable, Iterable


class ValidationErrCounter:

    def __init__(self, err_categorizer: Callable[[tuple], tuple]):
        """
        Initialize the validation error counter

        :param err_categorizer: A function that categorizes validation errors,
            represented by tuples, into categories, also represented by tuples
        """
        self._err_categorizer = err_categorizer

        # A dictionary with keys being the categories of the errors and values being
        # `Counter` objects with keys being individual errors counted in the
        # corresponding category.
        self._err_ctrs_by_cat: dict[tuple, Counter[tuple]] = defaultdict(Counter)

    def count(self, errs: Iterable[tuple]) -> None:
        """
        Count the validation errors

        :param errs: An iterable of tuples representing validation errors
        """
        for err in errs:
            cat = self._err_categorizer(err)

            # Count the error in the corresponding category
            self._err_ctrs_by_cat[cat].update([err])

    @property
    def counts_by_cat(self) -> dict[tuple, int]:
        """
        Get the counts of validation errors keyed by their categories

        :return: A dictionary with keys being tuples representing categories of the
            errors and values being the counts of the errors in the corresponding
            categories
        """
        return {cat: ctr.total() for cat, ctr in self._err_ctrs_by_cat.items()}

    def cats(self) -> set[tuple]:
        """
        Get the categories of the validation errors

        :return: The set of all categories of the validation errors represented
            by tuples
        """
        return set(self._err_ctrs_by_cat.keys())

    def __getitem__(self, cat: tuple) -> Counter[tuple]:
        """
        Get the `Counter` corresponding to a category of the validation errors

        :param cat: The category of the validation errors
        :return: The `Counter` object
        """
        return self._err_ctrs_by_cat[cat].copy()

    def items(self) -> list[tuple[tuple, Counter[tuple]]]:
        """
        Get the items of the counter

        :return: A list of tuples, each consisting of a tuple representing a category of
            validation errors and a `Counter` object representing the counts of the
            errors in the that category
        """

        return [(cat, ctr.copy()) for cat, ctr in self._err_ctrs_by_cat.items()]


def validation_err_diff(
    c1: ValidationErrCounter, c2: ValidationErrCounter
) -> dict[tuple, tuple[Counter[tuple], Counter[tuple]]]:
    """
    Get the diff between two `ValidationErrCounter` objects

    :param c1: The first `ValidationErrCounter` object
    :param c2: The second `ValidationErrCounter` object
    :return: A dictionary presenting the diff between the two objects. The keys are the
        keys in `c1` or `c2` that represent a category of validation errors in which
        there is a difference `c1` and `c2`. The values are a tuple consisting of a
        `Counter` object representing the validation errors removed from `c1` when
        compared to `c2` in the corresponding error category and a `Counter` object
        representing the validation errors gained in `c2` when compared to `c1` in the
        corresponding error category
    """
    cats = c1.cats().union(c2.cats())

    diff: dict[tuple, tuple[Counter[tuple], Counter[tuple]]] = {}
    for cat in cats:
        removed = c1[cat] - c2[cat]
        gained = c2[cat] - c1[cat]

        if removed or gained:
            diff[cat] = (removed, gained)

    return diff
