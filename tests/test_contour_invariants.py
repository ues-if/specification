import math
import pytest

from ues.spec.lens import SHAPE_CATALOGUE, SIZE_CATALOGUE, SizeCode, PROGRESSIVE_LENS_MIN_DROP, LENS_SPECS
from ues.spec.contour import _bbox, _effective_diameter


@pytest.mark.parametrize("name,contour", SHAPE_CATALOGUE.items())
def test_boxing_width_equals_one(name, contour):
    """Every normalised unit shape must have boxing width A = 1 (dec = 0).

    A is the horizontal extent of the bounding box (the 'lens size' on the temple
    per ISO 8624 §5).  The unit shape is normalised by A, not by ED.
    """
    x_min, x_max, _, _ = _bbox(contour.points)
    a = x_max - x_min
    assert math.isclose(a, 1.0, abs_tol=1e-9), (
        f"Shape '{name}': A = {a!r}, expected 1.0"
    )


@pytest.mark.parametrize("name,contour", SHAPE_CATALOGUE.items())
def test_dec_x_equals_zero(name, contour):
    """Every normalised shape must be horizontally centred on the origin (dec_x = 0)."""
    x_min, x_max, _, _ = _bbox(contour.points)
    dec_x = (x_min + x_max) / 2
    assert math.isclose(dec_x, 0.0, abs_tol=1e-9), (
        f"Shape '{name}': dec_x = {dec_x!r}, expected 0.0"
    )


@pytest.mark.parametrize("product_code,lens_spec", LENS_SPECS.items())
def test_progressive_lens_min_drop(product_code, lens_spec):
    """Every admitted (shape, size) product must provide sufficient vertical clearance
    for progressive prescription lenses (min drop from boxing centre to aperture bottom).

    Only admitted products (entries in LENS_SPECS) are tested; shapes may be admitted
    for some size codes and not others depending on their aspect ratio.
    """
    contour = SHAPE_CATALOGUE[lens_spec.shape_code]
    size_spec = SIZE_CATALOGUE[lens_spec.size_code]
    _, _, y_min, _ = _bbox(contour.points)
    drop_mm = abs(y_min) * size_spec.boxing_width
    assert drop_mm >= PROGRESSIVE_LENS_MIN_DROP, (
        f"Product '{product_code}': drop = {drop_mm:.2f} mm "
        f"< {PROGRESSIVE_LENS_MIN_DROP} mm required for progressive lenses"
    )
