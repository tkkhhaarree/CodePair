from evals.metrics import mean, p95, precision, recall


def test_recall():
    assert recall(3, 4) == 0.75
    assert recall(0, 5) == 0.0
    assert recall(0, 0) is None


def test_precision():
    assert precision(2, 3) == 2 / 3
    assert precision(0, 0) is None


def test_mean():
    assert mean([1, 2, 3, 6]) == 3
    assert mean([]) is None


def test_p95():
    assert p95(list(range(1, 21))) == 19  # 1..20 -> ceil(19.0) = 19th value
    assert p95(list(range(1, 101))) == 95  # 1..100 -> 95th value
    assert p95([7]) == 7
    assert p95([]) is None


def test_p95_does_not_need_sorted_input_or_change_it():
    values = [30, 5, 12, 7]
    assert p95(values) == 30  # 4 values -> ceil(3.8) = 4th = the largest
    assert values == [30, 5, 12, 7]  # caller's list unchanged
