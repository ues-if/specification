import math
import pytest

from ues.spec.lens import SHAPE_CATALOGUE
from ues.spec.contour import _bbox, _effective_diameter


@pytest.mark.parametrize("name,contour", SHAPE_CATALOGUE.items())
def test_ed_equals_one(name, contour):
    """Every normalised shape must have ED = 1 (dec = 0)."""
    x_min, x_max, y_min, y_max = _bbox(contour.points)
    ed = _effective_diameter(x_min, x_max, y_min, y_max, dec=0.0)
    assert math.isclose(ed, 1.0, abs_tol=1e-9), (
        f"Shape '{name}': ED = {ed!r}, expected 1.0"
    )


@pytest.mark.parametrize("name,contour", SHAPE_CATALOGUE.items())
def test_dec_x_equals_zero(name, contour):
    """Every normalised shape must be horizontally centred on the origin (dec_x = 0)."""
    x_min, x_max, _, _ = _bbox(contour.points)
    dec_x = (x_min + x_max) / 2
    assert math.isclose(dec_x, 0.0, abs_tol=1e-9), (
        f"Shape '{name}': dec_x = {dec_x!r}, expected 0.0"
    )
