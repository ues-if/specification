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

# Bevel zone: fixed-width cylindrical band machined at the lens perimeter.
# This is the ONLY dimension that must match between lens and frame — the
# prescription-driven lens body thickness inboard of this band is unconstrained.
# Ridge base (1.20 mm) + 0.90 mm flat land each side = 3.00 mm total.
BEVEL_ZONE_WIDTH    = 3.0   # mm — axial width of the standardised interface band

# Assembly clearance applied to the frame groove (per flank / per face).
# The groove is this much deeper and wider per side than the lens ridge,
# ensuring a clearance fit for tool-free hand assembly.
GROOVE_CLEARANCE    = 0.05  # mm

# ============================================================================
# FRAME DESIGN PARAMETERS  (re-exported from frames.py for convenience)
# ============================================================================
# Frame geometry (rim shape, bridge, temple) lives in frames.py.
# These re-exports keep existing callers working without changes.
from .frames import (          # noqa: E402 — intentional re-export
    RIM_WIDTH, RIM_DEPTH, RIM_WALL_THICKNESS,
    BRIDGE_DEPTH, BRIDGE_THICKNESS, BRIDGE_ARCH_DROP,
    TEMPLE_LENGTH, TEMPLE_THICKNESS,
    BRIDGE_HEIGHT,             # legacy alias for BRIDGE_DEPTH
    HINGE_PIN_DIAMETER, HINGE_BARREL_OD,
    FrameDesign, DEFAULT, MINIMAL, SHOWCASE,
)
# TEMPLE_HEIGHT and TEMPLE_TIP_HEIGHT are defined in frames.py;
# re-import explicitly to avoid shadowing the local alias there.
from .frames import TEMPLE_HEIGHT, TEMPLE_TIP_HEIGHT  # noqa: E402

# ============================================================================
# STANDARD LENS SIZE CATALOGUE
# ============================================================================

LENS_SPECS: dict[str, LensSizeSpec] = {
    "UES-C-XS": LensSizeSpec(CircularContour(51), 15),
    "UES-C-S":  LensSizeSpec(CircularContour(56), 17),
    "UES-C-M":  LensSizeSpec(CircularContour(61), 19),
    "UES-C-L":  LensSizeSpec(CircularContour(67), 21),
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
