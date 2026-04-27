"""
Universal Eyeglass Socket — Frame builder

Builds a complete UES-compatible frame: rim(s), nasal bridge, and temple arms.
All dimensions that govern appearance (rim width, bridge arch, temple length, …)
come from a FrameDesign instance; the bevel-groove interface contract comes from
spec/ and is intentionally kept separate.
"""

from __future__ import annotations
from build123d import *

from ..spec.lens import LensSpec, LENS_SPECS, BEVEL_DEPTH, GROOVE_CLEARANCE
from ..frame_example import FrameDesign, DEFAULT as DEFAULT_DESIGN
from .contour import (
    make_lens_wire,
    bevel_tip_params,
    profile_plane_at_wire_start,
    wire_y_at_max_x,
)


def _create_lens_rim(spec: LensSpec, design: FrameDesign = DEFAULT_DESIGN) -> Part:
    """
    Rim with a rounded V-groove on the inner wall that mates with the lens bevel ridge.
    Works for any contour shape via sweep.
    """
    lens_wire     = make_lens_wire(spec)
    outer_wire    = lens_wire.offset_2d(+design.rim_width, kind=Kind.ARC)
    aperture_wire = lens_wire.offset_2d(-BEVEL_DEPTH,      kind=Kind.ARC)
    assert isinstance(aperture_wire, Wire)  # sanity check: offset should not produce multiple wires for a simple contour

    D, W2, TIP_R, s, ux, uz_up, uz_dn = bevel_tip_params(clearance=GROOVE_CLEARANCE)
    Zc = design.rim_depth / 2

    # Groove profile in local (u, z): u=0 at aperture wall, u>0 into rim material
    #   (0, Zc+W2)  upper foot
    #       \_ p_up
    #          ) rounded apex arc
    #       /_ p_dn
    #   (0, Zc-W2)  lower foot
    p_up          = (D + ux * s, Zc + uz_up * s)
    p_dn          = (D + ux * s, Zc + uz_dn * s)
    mid           = (D - TIP_R,  Zc)
    profile_plane = profile_plane_at_wire_start(aperture_wire)

    with BuildPart() as rim:
        with BuildSketch():
            add(Face(outer_wire))
        extrude(amount=design.rim_depth, mode=Mode.ADD)

        with BuildSketch():
            add(Face(aperture_wire))
        extrude(amount=design.rim_depth, mode=Mode.SUBTRACT)

        with BuildSketch(profile_plane):
            with BuildLine():
                Line((0, Zc + W2), p_up)
                ThreePointArc(p_up, mid, p_dn)
                Line(p_dn, (0, Zc - W2))
                Line((0, Zc - W2), (0, Zc + W2))
            make_face()
        sweep(path=aperture_wire, mode=Mode.SUBTRACT)

    return rim.part


def _create_bridge(width: float, y_offset: float, design: FrameDesign = DEFAULT_DESIGN) -> Part:
    """
    Arched nasal bridge sweeping a rounded-rectangle profile along a
    three-point arc that dips ``design.bridge_arch_drop`` mm below the
    nasal attachment points. Optional nose-pad bumps are added at each end.
    """
    z_c  = design.rim_depth / 2
    half = width / 2
    drop = design.bridge_arch_drop
    bt   = design.bridge_thickness
    bd   = design.bridge_depth

    # Arch path: three-point arc in the XY plane, dipping by `drop`.
    with BuildLine() as bl:
        ThreePointArc(
            Vector(-half, y_offset, z_c),
            Vector(0.0,   y_offset - drop, z_c),
            Vector(+half, y_offset, z_c),
        )
    path_wire = bl.line.wires()[0]

    # Profile plane at path start (left nasal tip).
    # Sketch axes: x → global −Z (depth), y → ≈ global +Y (vertical).
    start      = path_wire.start_point()
    tangent    = path_wire.edges()[0].tangent_at(0.0).normalized()
    prof_plane = Plane(origin=start, x_dir=Vector(0, 0, -1), z_dir=tangent)

    with BuildPart() as bp:
        with BuildSketch(prof_plane):
            RectangleRounded(bd, bt, bt / 4)
        sweep(path=path_wire)

        if design.nose_pad_bumps:
            pad_r = bt * 0.85
            with Locations(
                Location((-half, y_offset - pad_r * 0.4, z_c)),
                Location((+half, y_offset - pad_r * 0.4, z_c)),
            ):
                Sphere(radius=pad_r)

    return bp.part


def _create_temple(design: FrameDesign = DEFAULT_DESIGN) -> Part:
    """
    Tapered temple arm, lofted from a tall profile at the hinge end to a
    slimmer profile at the ear tip.  A cylindrical hinge barrel sits at the
    hinge end; its axis becomes vertical (Y) after the rotations applied in
    create_frame, ready to receive a 2 mm pin.

    Print note: separate from the frame body and pin after printing for a
    working hinge.  Or fuse/print together for a rigid showcase piece.
    """
    L    = design.temple_length
    th   = design.temple_thickness
    h    = design.temple_height
    h_t  = design.temple_tip_height
    bo   = design.hinge_barrel_od
    bp_d = design.hinge_pin_diameter

    # Temple body runs along +X (x=0 = hinge end, x=L = ear tip).
    # Profiles are in planes with normal = +X.
    hinge_pln = Plane(origin=Vector(0, 0, 0), x_dir=Vector(0, 1, 0), z_dir=Vector(1, 0, 0))
    tip_pln   = Plane(origin=Vector(L, 0, 0), x_dir=Vector(0, 1, 0), z_dir=Vector(1, 0, 0))

    r_hinge = min(th, h)   * 0.20   # corner radius at hinge end
    r_tip   = min(th, h_t) * 0.20   # corner radius at ear tip
    th_tip  = th * 0.75              # tapered thickness at ear tip

    with BuildPart() as tp:
        # --- tapered body ---
        with BuildSketch(hinge_pln):
            RectangleRounded(th, h, r_hinge)
        with BuildSketch(tip_pln):
            RectangleRounded(th_tip, h_t, r_tip)
        loft()

        # --- hinge barrel ---
        # Cylinder centred at origin, axis = Z (becomes the vertical Y after
        # the two rotations in create_frame).  Its circular footprint in XY
        # (radius = bo/2) protrudes beyond the loft start in ±X, which after
        # rotation becomes the ±Z depth direction — exactly the visible hinge
        # knuckle that sits flush with the front and rear rim faces.
        barrel_half_h = h / 2 + 2.0    # extends ±this in Z
        with BuildSketch(Plane.XY):     # circle in X–Y, extruded along Z
            Circle(radius=bo / 2)
        extrude(amount=barrel_half_h * 2, both=True, mode=Mode.ADD)

        # --- pin through-hole (axis = Z) ---
        with BuildSketch(Plane.XY):
            Circle(radius=bp_d / 2)
        extrude(amount=(barrel_half_h + 1) * 2, both=True, mode=Mode.SUBTRACT)

    return tp.part


def create_frame(size_code: str, design: FrameDesign = DEFAULT_DESIGN) -> Part:
    """
    Assemble a complete frame: left + right rim, bridge, and two temples.

    Parameters
    ----------
    size_code:
        Key into LENS_SPECS (e.g. ``"UES-C-M"``).
    design:
        FrameDesign instance controlling all aesthetic dimensions.  Defaults
        to ``DEFAULT_DESIGN`` (the original reference dimensions).  Use
        ``spec.frame.SHOWCASE`` for a chunky 3‑D‑printable prototype.
    """
    spec         = LENS_SPECS[size_code]
    bridge_width = spec.bridge_width
    wire         = make_lens_wire(spec)
    bbox         = wire.bounding_box()
    nasal_reach  = bbox.max.X              # rightmost edge = nasal side of left lens
    total_span   = bbox.size.X             # full lens width (temporal-to-nasal)
    nasal_y      = wire_y_at_max_x(wire)   # Y at the nasal tip (bridge attachment)

    temporal_x = bridge_width / 2 + total_span + design.rim_width

    with BuildPart() as frame:
        # Left rim — nasal edge at −bridge_width/2 (ISO 8624 bridge gap)
        left_rim = _create_lens_rim(spec, design).move(
            Location((-(bridge_width / 2 + nasal_reach), 0, 0)))
        add(left_rim)
        add(left_rim.mirror(Plane.YZ))  # mirror for right rim

        # Arch bridge
        add(_create_bridge(bridge_width, y_offset=nasal_y, design=design))

        # Temples (left side = −1, right side = +1)
        for side in (-1, 1):
            t = _create_temple(design).rotate(Axis.Y, -90).rotate(Axis.Z, -90)
            add(t.move(Location((side * temporal_x, 0, 0))))

    return frame.part
