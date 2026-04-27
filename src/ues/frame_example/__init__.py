"""
Universal Eyeglass Socket — Reference frame design

Defines the FrameDesign dataclass and three reference design instances
(DEFAULT, MINIMAL, SHOWCASE).  None of these are normative — they are
provided as starting points and for use by the reference CAD builders in
ues.to_build123d.

The normative frame-side interface constants (RIM_DEPTH, RIM_WALL_THICKNESS)
live in ues.spec.frame.
"""

from .design import (
    FrameDesign,
    RIM_WIDTH,
    BRIDGE_DEPTH, BRIDGE_THICKNESS, BRIDGE_ARCH_DROP, BRIDGE_HEIGHT,
    TEMPLE_LENGTH, TEMPLE_HEIGHT, TEMPLE_TIP_HEIGHT, TEMPLE_THICKNESS,
    HINGE_PIN_DIAMETER, HINGE_BARREL_OD,
    DEFAULT, MINIMAL, SHOWCASE,
)

__all__ = [
    "FrameDesign",
    "RIM_WIDTH",
    "BRIDGE_DEPTH", "BRIDGE_THICKNESS", "BRIDGE_ARCH_DROP", "BRIDGE_HEIGHT",
    "TEMPLE_LENGTH", "TEMPLE_HEIGHT", "TEMPLE_TIP_HEIGHT", "TEMPLE_THICKNESS",
    "HINGE_PIN_DIAMETER", "HINGE_BARREL_OD",
    "DEFAULT", "MINIMAL", "SHOWCASE",
]
