
from statistics import NormalDist


def absolute_mean_difference(mean: float, std: float, cell: tuple[float, float, float]):
    """
    """
    assert cell[0] < cell[1] < cell[2], f"Cell {cell} must be ordered (lower, mean, upper)"

    lower, center, upper = cell

    normal = NormalDist(0, 1)
    phi = normal.pdf
    psi = normal.cdf
    # m1 = std * phi((cell[0] - mean) / std) + phi((cell[2] - mean) / std) - 2 * phi((cell[1] - mean) / std)
    m1 = std * (
        2 * phi((center - mean) / std)
        - phi((lower - mean) / std)
        - phi((upper - mean) / std)
    )
    m2 = (center - mean) * (psi((center - mean) / std) - psi((lower - mean) / std))
    m3 = (mean - center) * (psi((upper - mean) / std) - psi((center - mean) / std))

    return m1 + m2 + m3