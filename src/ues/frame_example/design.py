"""
Universal Eyeglass Socket — Reference frame design parameters

All dimensions here are reference/example values, not normative.
Normative frame-side constants (RIM_DEPTH, RIM_WALL_THICKNESS) live in
ues.spec.frame.
"""

from __future__ import annotations
from dataclasses import dataclass

from ..spec.frame import RIM_DEPTH, RIM_WALL_THICKNESS  # normative minimums, used as defaults


# ============================================================================
# REFERENCE DIMENSIONS
# ============================================================================

# Rim
RIM_WIDTH          = 2.5   # mm — radial width of frame rim

# Bridge
BRIDGE_DEPTH      = 3.0   # mm — front-to-back depth of the bridge bar
BRIDGE_THICKNESS  = 1.5   # mm — vertical thickness of the bridge bar
BRIDGE_ARCH_DROP  = 4.0   # mm — how far the arch dips below the nasal attachment points

# Temple
TEMPLE_LENGTH     = 140   # mm — hinge to ear-tip
TEMPLE_HEIGHT     = 6.0   # mm — height at hinge end
TEMPLE_TIP_HEIGHT = 3.5   # mm — height at ear-tip (taper target)
TEMPLE_THICKNESS  = 2.2   # mm — front-to-back depth (constant along length)

# Hinge
HINGE_PIN_DIAMETER = 2.0  # mm — diameter of the barrel pin (M2-compatible)
HINGE_BARREL_OD    = 5.0  # mm — outer diameter of the hinge barrel

# Legacy alias
BRIDGE_HEIGHT = BRIDGE_DEPTH


# ============================================================================
# FRAME DESIGN DATACLASS
# ============================================================================

@dataclass
class FrameDesign:
    """
    All geometry parameters that define the appearance of a UES frame.

    Changing these values creates a different visual / printability profile
    while the bevel-groove interface (from ues.spec) remains standardised.

    Field notes
    -----------
    bridge_arch_drop : float
        Vertical distance (mm) the bridge arch dips *below* the nasal
        rim-attachment points.  Larger values produce a more pronounced
        arch and more nose clearance.
    nose_pad_bumps : bool
        If True, small spherical bumps are added at each end of the bridge
        arch to indicate nose-pad contact points.
    temple_tip_height : float
        Height of the temple cross-section at the ear end.  The temple is
        linearly lofted from temple_height (hinge end) to this value.
    hinge_pin_diameter : float
        Through-hole diameter in the hinge barrel.  Matches a 2 mm nail or
        M2 screw for a two-piece print with a real working hinge.
    """

    name: str = "Custom"

    # --- Rim ---
    rim_width: float = RIM_WIDTH
    rim_depth: float = RIM_DEPTH          # default = normative minimum

    # --- Bridge ---
    bridge_depth: float     = BRIDGE_DEPTH
    bridge_thickness: float = BRIDGE_THICKNESS
    bridge_arch_drop: float = BRIDGE_ARCH_DROP
    nose_pad_bumps: bool    = True

    # --- Temple ---
    temple_length: float     = TEMPLE_LENGTH
    temple_height: float     = TEMPLE_HEIGHT
    temple_tip_height: float = TEMPLE_TIP_HEIGHT
    temple_thickness: float  = TEMPLE_THICKNESS

    # --- Hinge ---
    hinge_pin_diameter: float = HINGE_PIN_DIAMETER
    hinge_barrel_od: float    = HINGE_BARREL_OD


# ============================================================================
# PREDEFINED DESIGNS
# ============================================================================

#: Exactly replicates the reference constants — safe default.
DEFAULT = FrameDesign(name="Default")

#: Slim, wire-like frame — minimal visual footprint.
MINIMAL = FrameDesign(
    name="Minimal",
    rim_width=1.8,
    rim_depth=2.5,
    bridge_depth=2.0,
    bridge_thickness=1.2,
    bridge_arch_drop=3.0,
    nose_pad_bumps=False,
    temple_length=140,
    temple_height=4.5,
    temple_tip_height=2.5,
    temple_thickness=1.8,
    hinge_barrel_od=4.0,
)

#: Chunky showcase / prototype frame — intentionally thick for FDM printing.
#:
#: Designed to print face-down on a 0.4 mm nozzle FDM printer:
#:   • All walls ≥ 2.0 mm (≥ 5 extrusion widths at 0.4 mm)
#:   • Rim depth 4 mm  →  ~10 layers at 0.4 mm layer height
#:   • Arch bridge provides nose clearance without support material
#:   • Hinge barrels include 2 mm through-holes for a
#:     steel wire / M2 pin — print frame + temples separately and pin.
SHOWCASE = FrameDesign(
    name="Showcase",
    rim_width=3.5,
    rim_depth=4.0,
    bridge_depth=3.5,
    bridge_thickness=2.5,
    bridge_arch_drop=6.0,
    nose_pad_bumps=True,
    temple_length=140,
    temple_height=9.0,
    temple_tip_height=5.0,
    temple_thickness=3.0,
    hinge_pin_diameter=2.0,
    hinge_barrel_od=7.0,
)
