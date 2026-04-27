"""
Universal Eyeglass Socket — Frame interface specification (normative)

Defines the frame-side dimensional requirements that any UES-compliant frame
rim MUST satisfy.  The lens-side counterpart (bevel ridge geometry) and the
groove clearance live in spec/lens.py.

These are the only frame values fixed by the standard.  Everything else
(bridge shape, temple length, hinge style, …) is left to the frame designer
and belongs in a reference or example module.
"""

from .lens import BEVEL_ZONE_WIDTH

# Minimum axial depth of the frame rim channel.
# Must be at least deep enough to fully contain the bevel zone (BEVEL_ZONE_WIDTH)
# with 0.10 mm axial clearance on each face.
RIM_DEPTH = BEVEL_ZONE_WIDTH + 0.20       # mm

# Minimum radial wall thickness of the rim channel.
# Below this the groove flanks have insufficient material strength.
RIM_WALL_THICKNESS = 1.5                  # mm
