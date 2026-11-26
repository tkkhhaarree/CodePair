"""Small metric helpers for the evals. Each returns None when there is nothing to measure
(e.g. recall with 0 planted bugs), so reports can show "n/a" instead of crashing on 0/0.
"""

import math


def recall(caught: int, total: int) -> float | None:
    """Share of planted bugs that were caught, e.g. recall(3, 4) == 0.75. None if total is 0."""
    # TODO: return None when total is 0, otherwise caught / total.
    if total == 0:
        return None
    return caught/total


def precision(real: int, total: int) -> float | None:
    """Share of comments that point at a real problem. None if there were no comments."""
    # TODO: same idea as recall.
    if total == 0:
        return None
    return real/total


def mean(values: list[float]) -> float | None:
    """Average of the values. None for an empty list."""
    # TODO: None if the list is empty, otherwise sum(...) / len(...).
    if len(values) == 0:
        return None
    return sum(values) / len(values)


def p95(values: list[float]) -> float | None:
    """95th percentile, nearest-rank method. None for an empty list.

    1. sort the values (don't change the caller's list: sorted() returns a new one)
    2. rank = math.ceil(0.95 * number_of_values)
    3. return the value at that rank, counting from 1 -> index rank - 1
    """
    # TODO
    if len(values) == 0:
        return None
    sorted_values = sorted(values)
    rank = math.ceil(0.95 * len(sorted_values))
    return sorted_values[rank-1]

