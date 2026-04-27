"""
Universal Eyeglass Socket — Lens specification

Size catalogue, shape catalogue, LensSpec type, standard LENS_SPECS catalogue,
and the normative bevel/groove interface constants.
"""

from __future__ import annotations
import enum
from dataclasses import dataclass

from .contour import BezierContour


# ============================================================================
# SIZE CATALOGUE
# ============================================================================

class SizeCode(enum.Enum):
    XS = "XS"
    S  = "S"
    M  = "M"
    L  = "L"


@dataclass(frozen=True)
class SizeSpec:
    effective_diameter: float  # mm — ED per ISO 8624; scale multiplier applied to the unit shape
    bridge: float              # mm — bridge width per ISO 8624


SIZE_CATALOGUE: dict[SizeCode, SizeSpec] = {
    SizeCode.XS: SizeSpec(51.0, 15.0),
    SizeCode.S:  SizeSpec(56.0, 17.0),
    SizeCode.M:  SizeSpec(61.0, 19.0),
    SizeCode.L:  SizeSpec(67.0, 21.0),
}


# ============================================================================
# SHAPE CATALOGUE  (unit shapes: ED = 1)
# ============================================================================

SHAPE_CATALOGUE: dict[str, BezierContour] = {
    # "C" — circle: 8 equally-spaced points on a circle of radius 100 (normalised to ED = 1)
    "C": BezierContour([
        ( 100,     0  ),
        (  71,    71  ),
        (   0,   100  ),
        ( -71,    71  ),
        (-100,     0  ),
        ( -71,   -71  ),
        (   0,  -100  ),
        (  71,   -71  ),
    ]),
    # "R" — rounded rectangle 61 × 40 mm, corner radius 10 mm (normalised to ED = 1)
    "R": BezierContour([
        ( 30.5,   0.00),   # right mid-edge
        ( 27.57,  17.07),  # upper-right arc midpoint
        (  0.0,   20.0 ),  # top mid-edge
        (-27.57,  17.07),  # upper-left arc midpoint
        (-30.5,   0.00),   # left mid-edge
        (-27.57, -17.07),  # lower-left arc midpoint
        (  0.0,  -20.0 ),  # bottom mid-edge
        ( 27.57, -17.07),  # lower-right arc midpoint
    ]),
    # "D" — drop/teardrop: pixel-traced control points, flip_y because image Y is down
    "D": BezierContour(
        [
            (282, 139),   # P0 — upper nasal
            (387, 114),   # P1 — top
            (690, 150),   # P2 — temporal
            (553, 461),   # P3 — lower temporal
            (289, 431),   # P4 — bottom
            (160, 278),   # P5 — nasal mid
        ],
        flip_y=True,
    ),
}


# ============================================================================
# LENS SPEC  (shape + size → physical product)
# ============================================================================

@dataclass(frozen=True)
class LensSpec:
    shape_code: str
    size_code: SizeCode

    @property
    def effective_diameter(self) -> float:
        """Effective diameter (ED) in mm per ISO 8624."""
        return SIZE_CATALOGUE[self.size_code].effective_diameter

    @property
    def bridge_width(self) -> float:
        """Bridge width in mm per ISO 8624."""
        return SIZE_CATALOGUE[self.size_code].bridge

    @property
    def shape(self) -> BezierContour:
        """Unit shape (ED = 1) from the shape catalogue."""
        return SHAPE_CATALOGUE[self.shape_code]

    @property
    def points(self) -> tuple[tuple[float, float], ...]:
        """Physical Bézier control points: unit shape scaled by ED."""
        d = SIZE_CATALOGUE[self.size_code].effective_diameter
        return tuple((x * d, y * d) for x, y in self.shape.points)


LENS_SPECS: dict[str, LensSpec] = {
    "UES-C-XS": LensSpec("C", SizeCode.XS),
    "UES-C-S":  LensSpec("C", SizeCode.S),
    "UES-C-M":  LensSpec("C", SizeCode.M),
    "UES-C-L":  LensSpec("C", SizeCode.L),
    "R-M":      LensSpec("R", SizeCode.M),
    "D-M":      LensSpec("D", SizeCode.M),
}


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
