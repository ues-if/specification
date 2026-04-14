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

from __future__ import annotations
from dataclasses import dataclass
from typing import Union

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

# Lens contour dataclasses — define the 2-D perimeter shape of a lens

@dataclass
class CircularContour:
    diameter: float

@dataclass
class RectangularContour:
    width: float
    height: float
    corner_radius: float = 2.0

@dataclass
class BezierContour:
    control_points: list  # list of (x, y) tuples, closed via Spline(periodic=True)

LensContour = Union[CircularContour, RectangularContour, BezierContour]

@dataclass
class LensSizeSpec:
    contour: LensContour
    bridge_width: float

# Lens sizes: {size_code: LensSizeSpec}
# Bridge width terminology per ISO 8624
LENS_SPECS = {
    "XS": LensSizeSpec(CircularContour(51), 15),  # Children (ages 4-10)
    "S":  LensSizeSpec(CircularContour(56), 17),  # Small adults / Youth (ages 11-16)
    "M":  LensSizeSpec(CircularContour(61), 19),  # Average adults
    "L":  LensSizeSpec(CircularContour(67), 21),  # Large adults
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
# CONTOUR HELPERS
# ============================================================================

def make_lens_wire(contour: LensContour) -> Wire:
    """Return a closed Wire in the XY plane representing the lens perimeter."""
    if isinstance(contour, CircularContour):
        return Wire([Edge.make_circle(contour.diameter / 2)])
    if isinstance(contour, RectangularContour):
        with BuildSketch() as sk:
            RectangleRounded(contour.width, contour.height, contour.corner_radius)
        return sk.sketch.faces()[0].outer_wire()
    if isinstance(contour, BezierContour):
        with BuildLine() as bl:
            Spline(*contour.control_points, periodic=True)
        return bl.line.wires()[0]
    raise ValueError(f"Unknown contour type: {type(contour)}")


def contour_half_width(contour: LensContour) -> float:
    """Return the X half-extent of the contour (used for frame horizontal positioning)."""
    if isinstance(contour, CircularContour):
        return contour.diameter / 2
    bb = make_lens_wire(contour).bounding_box()
    return bb.size.X / 2


def _profile_plane_at_wire_start(wire: Wire) -> Plane:
    """
    Return a Plane at the wire's start point for sweep profile placement.

    Local (u, v) sketch coordinates:
      u = 0  at the wire perimeter, u > 0  outward (away from centroid)
      v      along global Z (axial direction)

    The plane's normal is chosen so that  y_dir = z_dir x x_dir = (0, 0, 1).
    """
    start_pt = wire.start_point()
    t = wire.edges()[0].tangent_at(0.0)
    # Candidate outward normal: tangent rotated -90 deg in XY
    cand_out = Vector(t.Y, -t.X, 0)
    center = wire.center()
    sp_xy = Vector(start_pt.X, start_pt.Y, 0)
    ct_xy = Vector(center.X, center.Y, 0)
    if (sp_xy - ct_xy).dot(cand_out) < 0:
        cand_out = Vector(-t.Y, t.X, 0)
    outward = cand_out.normalized()
    # z_dir (plane normal) s.t. y_dir = z_dir x outward = (0, 0, 1).
    # Derivation: z_dir = (outward.Y, -outward.X, 0)
    plane_normal = Vector(outward.Y, -outward.X, 0)
    return Plane(origin=start_pt, x_dir=outward, z_dir=plane_normal)


def _bevel_tip_params():
    """Shared rounded-apex geometry derived from BEVEL_DEPTH / BEVEL_WIDTH."""
    D  = BEVEL_DEPTH
    W2 = BEVEL_WIDTH / 2
    TIP_RADIUS = 0.20
    bevel_len = (D ** 2 + W2 ** 2) ** 0.5
    s     = min(TIP_RADIUS, bevel_len * 0.45)
    ux    = -D  / bevel_len
    uz_up =  W2 / bevel_len
    uz_dn = -W2 / bevel_len
    return D, W2, TIP_RADIUS, s, ux, uz_up, uz_dn


# ============================================================================
# COMPONENT BUILDERS
# ============================================================================

def create_lens_rim(contour: LensContour) -> Part:
    """
    Create a lens rim with a rounded V-groove on the inner wall matching the lens bevel
    ridge.  Works for any lens contour shape via sweep.
    """
    lens_wire     = make_lens_wire(contour)
    outer_wire    = lens_wire.offset_2d(+RIM_WIDTH,   kind=Kind.ARC)
    aperture_wire = lens_wire.offset_2d(-BEVEL_DEPTH, kind=Kind.ARC)

    D, W2, TIP_RADIUS, s, ux, uz_up, uz_dn = _bevel_tip_params()
    Zc = RIM_DEPTH / 2

    # Groove profile in local (u, z): u = 0 at aperture inner wall, u > 0 into rim
    p_up = (D + ux * s, Zc + uz_up * s)
    p_dn = (D + ux * s, Zc + uz_dn * s)
    mid  = (D - TIP_RADIUS, Zc)

    profile_plane = _profile_plane_at_wire_start(aperture_wire)

    with BuildPart() as lens_rim:
        # Outer rim body
        with BuildSketch():
            add(Face(outer_wire))
        extrude(amount=RIM_DEPTH, mode=Mode.ADD)

        # Aperture (inner opening)
        with BuildSketch():
            add(Face(aperture_wire))
        extrude(amount=RIM_DEPTH, mode=Mode.SUBTRACT)

        # Rounded V-groove swept around the aperture perimeter
        with BuildSketch(profile_plane):
            with BuildLine():
                Line((0, Zc + W2), p_up)              # upper bevel face
                ThreePointArc(p_up, mid, p_dn)         # rounded apex
                Line(p_dn, (0, Zc - W2))              # lower bevel face
                Line((0, Zc - W2), (0, Zc + W2))      # close along inner wall
            make_face()
        sweep(path=aperture_wire, mode=Mode.SUBTRACT)

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
    spec         = LENS_SPECS[size_code]
    hw           = contour_half_width(spec.contour)
    bridge_width = spec.bridge_width

    with BuildPart() as frame:
        # Left lens rim
        if SHOW_LEFT_LENS:
            left_rim = create_lens_rim(spec.contour)
            add(left_rim.move(Location((-(bridge_width / 2 + hw), 0, 0))))

        # Right lens rim
        if SHOW_RIGHT_LENS:
            right_rim = create_lens_rim(spec.contour)
            add(right_rim.move(Location((bridge_width / 2 + hw, 0, 0))))

        # Bridge
        if SHOW_BRIDGE:
            bridge = create_bridge(bridge_width)
            add(bridge)

        # Left temple
        if SHOW_LEFT_TEMPLE:
            left_temple = create_temple()
            left_temple_positioned = left_temple.rotate(Axis.Y, -90).rotate(Axis.Z, -90)
            add(left_temple_positioned.move(Location((
                -(bridge_width / 2 + hw * 2 + RIM_WIDTH), 0, 0
            ))))

        # Right temple
        if SHOW_RIGHT_TEMPLE:
            right_temple = create_temple()
            right_temple_positioned = right_temple.rotate(Axis.Y, -90).rotate(Axis.Z, -90)
            add(right_temple_positioned.move(Location((
                bridge_width / 2 + hw * 2 + RIM_WIDTH, 0, 0
            ))))

    return frame.part

def create_reference_lens(contour: LensContour, lens_thickness: float = 2.0) -> Part:
    """
    Create a reference lens with a rounded V-ridge bevel on its outer edge.
    Works for any lens contour shape via sweep.
    """
    lens_wire = make_lens_wire(contour)
    T         = lens_thickness
    D, W2, TIP_RADIUS, s, ux, uz_up, uz_dn = _bevel_tip_params()
    overhang  = 0.5

    # Bevel cutter in local (u, z): u = 0 at contour perimeter, u > 0 outward
    p_up = (ux * s,       uz_up * s)
    p_dn = (ux * s,       uz_dn * s)
    mid  = (-TIP_RADIUS,  0)

    profile_plane = _profile_plane_at_wire_start(lens_wire)

    with BuildPart() as lens:
        # Main lens body — extruded from face, centered on Z=0
        lens_face = Face(lens_wire)
        add(Solid.extrude(lens_face, Vector(0, 0, T)).move(Location((0, 0, -T / 2))))

        # Bevel cutter swept around the perimeter
        with BuildSketch(profile_plane):
            with BuildLine():
                Line((-D,        W2),          (-D,        T / 2))    # up inner wall
                Line((-D,        T / 2),       (+overhang, T / 2))    # top face out
                Line((+overhang, T / 2),       (+overhang, -T / 2))   # outer wall
                Line((+overhang, -T / 2),      (-D,        -T / 2))   # bottom face in
                Line((-D,        -T / 2),      (-D,        -W2))      # down inner wall
                Line((-D,        -W2),          p_dn)                  # lower bevel face
                ThreePointArc(p_dn, mid, p_up)                         # rounded apex
                Line(p_up,                     (-D,        W2))       # upper bevel face
            make_face()
        sweep(path=lens_wire, mode=Mode.SUBTRACT)

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
