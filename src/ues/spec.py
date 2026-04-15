"""
Universal Eyeglass Socket — Specification definitions
Based on Universal Eyeglass Socket Lens System Specification v0.1.0

This module contains ONLY the standardised data:
  - Lens contour types (CircularContour, RectangularContour, BezierContour)
  - Bevel interface constants (BEVEL_*)
  - Reference frame design constants (RIM_*, BRIDGE_*, TEMPLE_*)
  - Standard lens size catalogue (LENS_SPECS)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Union

# ============================================================================
# LENS CONTOUR TYPES
# ============================================================================

@dataclass
class CircularContour:
    diameter: float

@dataclass
class RectangularContour:
    width: float
    height: float
    corner_radius: float

@dataclass
class BezierContour:
    control_points: list[tuple[float, float]]  # arbitrary coords (e.g. raw pixel picks)
    scale: float = 1.0                          # mm — physical half-extent after normalisation
    flip_y: bool = False                        # True when coords come from image pixels (Y-down)

    @property
    def normalized_points(self) -> list[tuple[float, float]]:
        """Control points centred on their centroid and scaled so max half-extent = scale (mm).
        If flip_y is True the Y axis is inverted (image-pixel → CAD convention).
        """
        cx = sum(x for x, _ in self.control_points) / len(self.control_points)
        cy = sum(y for _, y in self.control_points) / len(self.control_points)
        half = max(max(abs(x - cx), abs(y - cy)) for x, y in self.control_points)
        sy = -1.0 if self.flip_y else 1.0
        k = self.scale / half
        return [((x - cx) * k, sy * (y - cy) * k) for x, y in self.control_points]

LensContour = Union[CircularContour, RectangularContour, BezierContour]

@dataclass
class LensSizeSpec:
    contour: LensContour
    bridge_width: float  # mm, per ISO 8624

# ============================================================================
# STANDARDISED LENS INTERFACE  (defined by this standard)
# ============================================================================

# Edge bevel specification — all compliant lenses MUST have this ridge
BEVEL_DEPTH         = 1.0   # mm — from lens perimeter surface to apex
BEVEL_WIDTH         = 1.2   # mm — opening width at the lens surface
BEVEL_ANGLE         = 120   # degrees (symmetrical V-ridge)
BEVEL_APEX_POSITION = 1.5   # mm — from lens outer circumference

# Assembly clearance applied to the frame groove (per flank / per face).
# The groove is this much deeper and wider per side than the lens ridge,
# ensuring a clearance fit for tool-free hand assembly.
GROOVE_CLEARANCE    = 0.05  # mm

# ============================================================================
# REFERENCE FRAME DESIGN PARAMETERS
# ============================================================================

# Rim
RIM_WIDTH          = 2.5   # mm — radial width of frame rim
RIM_DEPTH          = 3.0   # mm — axial depth / thickness
RIM_WALL_THICKNESS = 1.5   # mm — wall thickness

# Bridge
BRIDGE_HEIGHT    = 3     # mm
BRIDGE_THICKNESS = 1.5   # mm

# Temple
TEMPLE_LENGTH    = 140   # mm (same for all sizes)
TEMPLE_HEIGHT    = 8     # mm — vertical dimension when worn
TEMPLE_THICKNESS = 2     # mm — horizontal depth

# ============================================================================
# STANDARD LENS SIZE CATALOGUE
# ============================================================================

LENS_SPECS: dict[str, LensSizeSpec] = {
    "C-XS": LensSizeSpec(CircularContour(51), 15),
    "C-S":  LensSizeSpec(CircularContour(56), 17),
    "C-M":  LensSizeSpec(CircularContour(61), 19),
    "C-L":  LensSizeSpec(CircularContour(67), 21),
    "R-M":  LensSizeSpec(RectangularContour(61, 40, 10), 18),
    "D-M": LensSizeSpec(BezierContour(
        [
            (282, 139),   # P0 — upper nasal
            (387, 114),   # P1 — top
            (690, 150),   # P2 — temporal
            (553, 461),   # P3 — lower temporal
            (289, 431),   # P4 — bottom
            (160, 278),   # P5 — nasal mid
        ],
        scale=30.0,
        flip_y=True,
    ), 19),
}
