"""
Universal Eyeglass Socket — Contour specification

Defines the BezierContour type and the ISO 8624 boxing-system helpers used
to normalise raw control-point coordinates to a unit shape (A = 1), where
A is the horizontal boxing width (the lens-size dimension marked on spectacle
temples per ISO 8624 §5).

NOTE on ED vs A:
  A  — horizontal boxing width; the "lens size" number on the temple.
  ED — effective diameter per ISO 8624: ED = sqrt((A/2)^2 + (B/2)^2).
       ED is smaller than A for any non-degenerate shape and is used for
       lens blank selection, NOT as the UES size parameter.
"""

from __future__ import annotations
from dataclasses import dataclass, field, InitVar


# ============================================================================
# Boxing-system helpers (ISO 8624)
# ============================================================================

def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Axis-aligned bounding box of a list of 2-D points.
    Returns (x_min, x_max, y_min, y_max).
    """
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), max(xs), min(ys), max(ys)


def _boxing_centre(x_min: float, x_max: float,
                   y_min: float, y_max: float) -> tuple[float, float]:
    """Centre of the bounding box (ISO 8624 boxing centre)."""
    return (x_min + x_max) / 2, (y_min + y_max) / 2


def _effective_diameter(x_min: float, x_max: float,
                        y_min: float, y_max: float,
                        dec: float) -> float:
    """Effective diameter (ED) per ISO 8624 boxing system.

    ED = sqrt((A/2 + dec)^2 + (B/2)^2)
    where A = bbox width, B = bbox height, dec = horizontal decentration.

    NOTE: ED is NOT the UES size parameter.  The UES size parameter is the
    boxing width A.  ED is provided here for informative use (e.g. lens blank
    selection); it is smaller than A for any non-degenerate shape.
    """
    a_half = (x_max - x_min) / 2
    b_half = (y_max - y_min) / 2
    return ((a_half + dec) ** 2 + b_half ** 2) ** 0.5


# ============================================================================
# Contour type
# ============================================================================

@dataclass(frozen=True)
class BezierContour:
    control_points: InitVar[list[tuple[float, float]]]  # raw coords (e.g. pixel picks); not stored
    flip_y: InitVar[bool] = False                        # True when Y-axis is image-pixel (Y-down); not stored
    points: tuple[tuple[float, float], ...] = field(init=False)  # unit shape: boxing-centred, ED = 1

    def __post_init__(
        self,
        control_points: list[tuple[float, float]],
        flip_y: bool,
    ) -> None:
        x_min, x_max, y_min, y_max = _bbox(control_points)
        cx, cy = _boxing_centre(x_min, x_max, y_min, y_max)
        # Normalise so that the boxing width A = 1 (the UES size parameter).
        # Dividing by A (= x_max - x_min) centres the shape so x ∈ [−0.5, 0.5].
        a = x_max - x_min   # boxing width A of the raw shape
        k = 1.0 / a
        sy = -1.0 if flip_y else 1.0
        object.__setattr__(self, 'points', tuple(
            ((x - cx) * k, sy * (y - cy) * k) for x, y in control_points
        ))
