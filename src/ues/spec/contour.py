"""
Universal Eyeglass Socket — Contour specification

Defines the BezierContour type and the ISO 8624 boxing-system helpers used
to normalise raw control-point coordinates to a unit shape (ED = 1).
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
    where A = bbox width, B = bbox height, dec = horizontal decentration
    (signed distance from the boxing centre to the fitting/reference point).
    For unit shapes dec = 0.0, since the origin IS the boxing centre.
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
        ed = _effective_diameter(x_min, x_max, y_min, y_max, dec=0.0)
        sy = -1.0 if flip_y else 1.0
        k = 1.0 / ed
        object.__setattr__(self, 'points', tuple(
            ((x - cx) * k, sy * (y - cy) * k) for x, y in control_points
        ))
