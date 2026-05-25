"""Math tests."""

import pytest

@pytest.mark.parametrize(
    ("mean", "std", "cell", "result"),
    [
        (0, 1, (float("-inf"), 0, float("+inf")), 0.7979),
        (10, 2, (float("-inf"), 10, float("+inf")), 1.59576912),
        (0, 1, (float("-inf"), 1, float("+inf")), 1.16663094),
        (60, 3, (55, 58, 65), 2.30985505),
    ]
)
def test_absolute_mean_difference(mean: float, std: float, cell: tuple[float, float, float], result: float):
    from size_analysis.math import absolute_mean_difference

    assert absolute_mean_difference(mean, std, cell) == pytest.approx(result, abs=1e-4)