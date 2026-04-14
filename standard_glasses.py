#!/usr/bin/env python3
"""
Standard Glasses Frame Generator
Based on Universal Eyeglass Standard Lens System Specification v0.1.0
Date: 2026-04-13

This file contains a REFERENCE IMPLEMENTATION of eyeglass frames
that are compatible with the standardized lens attachment interface.

The standardized interface (from spec) includes:
  - Four circular lens sizes: 51, 56, 61, 67 mm
  - Edge bevel geometry for lens retention (defined by this standard)
  - Measurement terminology per ISO 8624

The frame design itself is a reference model and not part of the spec.
"""

from build123d import *

# ============================================================================
# PARAMETERS
# ============================================================================

# Render options
SHOW_LEFT_LENS = True
SHOW_RIGHT_LENS = True
SHOW_BRIDGE = True
SHOW_LEFT_TEMPLE = True
SHOW_RIGHT_TEMPLE = True

# ============================================================================
# STANDARDIZED LENS INTERFACE (from technical-spec.adoc)
# ============================================================================

# Lens sizes: {size_code: (lens_diameter, bridge_width)}
# Bridge width terminology per ISO 8624
LENS_SPECS = {
    "XS": (51, 15),  # Children (ages 4-10)
    "S": (56, 17),   # Small adults / Youth (ages 11-16)
    "M": (61, 19),   # Average adults
    "L": (67, 21),   # Large adults
}

# Lens edge bevel specification (defined by this standard)
# This is the STANDARDIZED INTERFACE that all lenses MUST have
BEVEL_DEPTH = 1.0         # mm from lens edge surface to apex
BEVEL_WIDTH = 1.2         # mm at surface
BEVEL_ANGLE = 120         # degrees (symmetrical V-groove)
BEVEL_APEX_POSITION = 1.5 # mm from lens outer circumference

# ============================================================================
# REFERENCE FRAME DESIGN PARAMETERS
# ============================================================================
# These parameters define a reference frame implementation.

# Rim design (reference)
RIM_WIDTH = 2.5           # mm - width of frame rim
RIM_DEPTH = 3.0           # mm - depth/thickness of rim
RIM_WALL_THICKNESS = 1.5  # mm - wall thickness

# Bridge design (reference)
BRIDGE_HEIGHT = 3         # mm
BRIDGE_THICKNESS = 1.5    # mm

# Temple design (reference)
TEMPLE_LENGTH = 140       # mm (standard for all sizes)
TEMPLE_HEIGHT = 8         # mm (vertical dimension when worn)
TEMPLE_THICKNESS = 2      # mm (horizontal depth/width)

# ============================================================================
# COMPONENT BUILDERS
# ============================================================================

def create_lens_rim(diameter: float) -> Part:
    """
    Create a lens rim with a V-groove on the inner wall matching the lens bevel ridge.
    """
    R  = diameter / 2
    D  = BEVEL_DEPTH        # 1.0 mm — groove depth (radially outward into rim)
    W2 = BEVEL_WIDTH / 2    # 0.6 mm — half-width at groove opening
    Zc = RIM_DEPTH / 2      # groove centre: midpoint of rim depth

    # Rounded groove apex — must match create_reference_lens
    TIP_RADIUS = 0.20
    bevel_len = ((D ** 2) + (W2 ** 2)) ** 0.5
    s = min(TIP_RADIUS, bevel_len * 0.45)
    ux    = -D  / bevel_len
    uz_up =  W2 / bevel_len
    uz_dn = -W2 / bevel_len
    p_up = (R + ux * s, Zc + uz_up * s)
    p_dn = (R + ux * s, Zc + uz_dn * s)
    mid  = (R - TIP_RADIUS, Zc)

    with BuildPart() as lens_rim:
        # Outer rim ring
        with BuildSketch() as outer:
            Circle(radius=R + RIM_WIDTH)
        extrude(amount=RIM_DEPTH, mode=Mode.ADD)

        # Aperture: sized to the lens body at the bevel foot (r = R - D)
        with BuildSketch() as inner:
            Circle(radius=R - D)
        extrude(amount=RIM_DEPTH, mode=Mode.SUBTRACT)

        # Rounded V-groove on the inner wall — mirrors the lens V-ridge.
        # In Plane.XZ (X = radial, Z = axial):
        #   (R-D, Zc+W2)  upper foot
        #         \
        #   p_up  (near apex, upper bevel face)
        #         ) rounded apex arc (same TIP_RADIUS as lens bevel)
        #   p_dn  (near apex, lower bevel face)
        #         /
        #   (R-D, Zc-W2)  lower foot
        with BuildSketch(Plane.XZ) as groove_profile:
            with BuildLine():
                Line((R - D, Zc + W2), p_up)               # upper bevel face
                ThreePointArc(p_up, mid, p_dn)              # rounded apex
                Line(p_dn, (R - D, Zc - W2))               # lower bevel face
                Line((R - D, Zc - W2), (R - D, Zc + W2))  # close along inner wall
            make_face()
        revolve(axis=Axis.Z, mode=Mode.SUBTRACT)

    return lens_rim.part

def create_bridge(width: float) -> Part:
    with BuildPart() as bridge:
        Box(width, BRIDGE_THICKNESS, BRIDGE_HEIGHT, 
            align=(Align.CENTER, Align.CENTER, Align.MAX))
        # Move to top of rim
        bridge.part.move(Location((0, 0, RIM_DEPTH/2)))
    
    return bridge.part


def create_temple() -> Part:
    with BuildPart() as temple:
        # Main temple arm
        Box(TEMPLE_LENGTH, TEMPLE_THICKNESS, TEMPLE_HEIGHT,
            align=(Align.MIN, Align.CENTER, Align.CENTER))
        
        # Hinge barrel (simplified representation)
        with BuildPart(Plane.YZ) as hinge:
            Cylinder(radius=2, height=BRIDGE_THICKNESS, 
                    align=(Align.CENTER, Align.CENTER, Align.CENTER))
            hinge.part.rotate(Axis.X, 90)

    return temple.part


def create_frame(size_code: str) -> Part:
    lens_diameter, bridge_width = LENS_SPECS[size_code]

    with BuildPart() as frame:
        # Left lens rim
        if SHOW_LEFT_LENS:
            left_rim = create_lens_rim(lens_diameter)
            add(left_rim.move(Location((-(bridge_width/2 + lens_diameter/2), 0, 0))))
        
        # Right lens rim
        if SHOW_RIGHT_LENS:
            right_rim = create_lens_rim(lens_diameter)
            add(right_rim.move(Location((bridge_width/2 + lens_diameter/2, 0, 0))))
        
        # Bridge
        if SHOW_BRIDGE:
            bridge = create_bridge(bridge_width)
            add(bridge)
        
        # Left temple
        if SHOW_LEFT_TEMPLE:
            left_temple = create_temple()
            left_temple_positioned = left_temple.rotate(Axis.Y, -90).rotate(Axis.Z, -90)
            add(left_temple_positioned.move(Location((
                -(bridge_width/2 + lens_diameter + RIM_WIDTH),
                0,
                0
            ))))
        
        # Right temple
        if SHOW_RIGHT_TEMPLE:
            right_temple = create_temple()
            right_temple_positioned = right_temple.rotate(Axis.Y, -90).rotate(Axis.Z, -90)
            add(right_temple_positioned.move(Location((
                bridge_width/2 + lens_diameter + RIM_WIDTH,
                0,
                0
            ))))
        
    return frame.part

def create_reference_lens(size_code: str) -> Part:
    diameter, _ = LENS_SPECS[size_code]
    lens_thickness = 2  # mm

    with BuildPart() as lens:
        # Main lens body
        Cylinder(
            radius=diameter / 2,
            height=lens_thickness,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        )

        # Rounded V-bevel parameters
        R = diameter / 2
        T = lens_thickness
        W2 = BEVEL_WIDTH / 2
        D = BEVEL_DEPTH
        overhang = 0.5
        TIP_RADIUS = 0.20  # mm, start here and tune

        # Distance to step back from the sharp apex along each bevel face
        # so we can replace the point with a small rounding arc.
        bevel_len = ((D ** 2) + (W2 ** 2)) ** 0.5
        s = min(TIP_RADIUS, bevel_len * 0.45)

        # Unit vectors from apex toward each bevel foot
        ux = -D / bevel_len
        uz_up =  W2 / bevel_len
        uz_dn = -W2 / bevel_len

        apex = (R, 0)
        p_up = (R + ux * s, 0 + uz_up * s)
        p_dn = (R + ux * s, 0 + uz_dn * s)

        # Bulge point for the round tip.
        # Push slightly inward in radial direction to create a soft crest.
        mid = (R - TIP_RADIUS, 0)

        with BuildSketch(Plane.XZ) as bevel_profile:
            with BuildLine():
                Line((R - D,  W2),       (R - D,  T / 2))         # up inner wall
                Line((R - D,  T / 2),    (R + overhang,  T / 2))  # top face out
                Line((R + overhang,  T / 2), (R + overhang, -T / 2))  # outer wall
                Line((R + overhang, -T / 2), (R - D, -T / 2))     # bottom face in
                Line((R - D, -T / 2),    (R - D, -W2))            # down inner wall

                # Lower bevel face up toward rounded tip
                Line((R - D, -W2), p_dn)

                # Rounded tip replacing the sharp apex
                ThreePointArc(p_dn, mid, p_up)

                # Upper bevel face back to bevel foot
                Line(p_up, (R - D, W2))

            make_face()

        revolve(axis=Axis.Z, mode=Mode.SUBTRACT)

    return lens.part

# ============================================================================
# MAIN ASSEMBLY
# ============================================================================

def main():
    """Generate and export the frame."""
    # Create the frame
    size = "M"  # Change this to "XS", "S", "M", or "L" to generate different sizes
    frame = create_frame(size)
    
    # Export options
    export_step = True
    export_stl = True
    
    if export_step:
        filename = f"standard-glasses-{size}.step"
        export_step_func = getattr(frame, 'export_step', None)
        if export_step_func:
            export_step_func(filename)
        else:
            # Use build123d export functions
            from pathlib import Path
            from build123d import export_step as exp_step
            exp_step(frame, str(Path(filename)))
        print(f"Exported STEP file: {filename}")
    
    if export_stl:
        filename = f"standard-glasses-{size}.stl"
        export_stl_func = getattr(frame, 'export_stl', None)
        if export_stl_func:
            export_stl_func(filename)
        else:
            # Use build123d export functions
            from pathlib import Path
            from build123d import export_stl as exp_stl
            exp_stl(frame, str(Path(filename)))
        print(f"Exported STL file: {filename}")

    return frame

if __name__ == "__main__":
    main()
