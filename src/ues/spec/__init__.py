"""
Universal Eyeglass Socket — Specification sub-package

Re-exports all public names from the three spec modules so that existing
``from ues.spec import …`` statements continue to work unchanged.
"""

from .contour import BezierContour
from .lens import (
    SizeCode, SizeSpec, SIZE_CATALOGUE,
    SHAPE_CATALOGUE,
    LensSpec, LENS_SPECS,
    BEVEL_DEPTH, BEVEL_WIDTH, BEVEL_ANGLE, BEVEL_ZONE_WIDTH, GROOVE_CLEARANCE,
)
from .frame import (
    RIM_DEPTH, RIM_WALL_THICKNESS,
)

__all__ = [
    # contour
    "BezierContour",
    # lens
    "SizeCode", "SizeSpec", "SIZE_CATALOGUE",
    "SHAPE_CATALOGUE",
    "LensSpec", "LENS_SPECS",
    "BEVEL_DEPTH", "BEVEL_WIDTH", "BEVEL_ANGLE", "BEVEL_ZONE_WIDTH", "GROOVE_CLEARANCE",
    # frame (normative only)
    "RIM_DEPTH", "RIM_WALL_THICKNESS",
]
