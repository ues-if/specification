"""
Universal Eyeglass Socket — Reference frame and lens builders

All geometry is driven by the spec constants and contour types in spec.py.
The bevel/groove cross-section profile is expressed in local (u, z) coordinates
where u=0 is the wire perimeter, so the same profile works for any contour shape
via sweep rather than revolve.
"""

from __future__ import annotations
from build123d import *

from .spec import (
    LensContour, CircularContour, RectangularContour, BezierContour,
    LensSizeSpec, LENS_SPECS,
    BEVEL_DEPTH, BEVEL_WIDTH, BEVEL_ZONE_WIDTH, GROOVE_CLEARANCE,
)
from .frames import FrameDesign, DEFAULT as DEFAULT_DESIGN

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
            Spline(*contour.normalized_points, periodic=True)
        return bl.line.wires()[0]
    raise ValueError(f"Unknown contour type: {type(contour)}")


def contour_half_width(contour: LensContour) -> float:
    """Return the nasal reach of the contour from its centroid.

    For symmetric contours this equals half the width.  For asymmetric
    contours (e.g. traced BezierContour) the centroid may not coincide
    with the bounding-box centre, so we take bbox.max.X — the distance
    from the wire origin to the rightmost (nasal) edge.  This is what
    creates the correct ISO bridge gap on the left-lens placement.
    """
    if isinstance(contour, CircularContour):
        return contour.diameter / 2
    return make_lens_wire(contour).bounding_box().max.X


def _wire_y_at_max_x(wire: Wire) -> float:
    """Return the Y coordinate at the point of maximum X on the wire.

    This is the nasal tip — the closest point to the opposite lens —
    and defines where the bridge should be vertically attached.
    Sampled densely enough to handle spline curves accurately.
    """
    best_x, best_y = -1e9, 0.0
    for edge in wire.edges():
        for i in range(21):
            pt = edge.position_at(i / 20)
            if pt.X > best_x:
                best_x, best_y = pt.X, pt.Y
    return best_y


def _profile_plane_at_wire_start(wire: Wire) -> Plane:
    """
    Return a Plane at the wire's start point for sweep profile placement.

    Sketch axes at the returned plane:
      x-axis  — outward normal from the wire centroid
      y-axis  — global +Z  (axial direction)
    So sketch coords (u, z) map directly to (outward offset, axial position).
    """
    start_pt = wire.start_point()
    tangent  = wire.edges()[0].tangent_at(0.0)

    # Rotate tangent -90° in XY to get a candidate outward normal
    cand_out = Vector(tangent.Y, -tangent.X, 0)

    # Flip if pointing inward (toward centroid)
    center = wire.center()
    sp_xy  = Vector(start_pt.X, start_pt.Y, 0)
    ct_xy  = Vector(center.X, center.Y, 0)
    if (sp_xy - ct_xy).dot(cand_out) < 0:
        cand_out = Vector(-tangent.Y, tangent.X, 0)

    outward      = cand_out.normalized()
    plane_normal = Vector(outward.Y, -outward.X, 0)  # s.t. y_dir = global Z
    return Plane(origin=start_pt, x_dir=outward, z_dir=plane_normal)


def _bevel_tip_params(clearance: float = 0.0) -> tuple:
    """Rounded-apex V-profile geometry.

    clearance > 0 makes the profile deeper and wider by that amount per side,
    producing the frame groove which must be slightly larger than the lens ridge.
    """
    D        = BEVEL_DEPTH + clearance
    W2       = BEVEL_WIDTH / 2 + clearance
    TIP_R    = 0.20
    bevel_len = (D ** 2 + W2 ** 2) ** 0.5
    s        = min(TIP_R, bevel_len * 0.45)
    ux       = -D  / bevel_len
    uz_up    =  W2 / bevel_len
    uz_dn    = -W2 / bevel_len
    return D, W2, TIP_R, s, ux, uz_up, uz_dn


# ============================================================================
# COMPONENT BUILDERS
# ============================================================================

def create_lens_rim(contour: LensContour, design: FrameDesign = DEFAULT_DESIGN) -> Part:
    """
    Rim with a rounded V-groove on the inner wall that mates with the lens bevel ridge.
    Works for any contour shape via sweep.
    """
    lens_wire     = make_lens_wire(contour)
    outer_wire    = lens_wire.offset_2d(+design.rim_width, kind=Kind.ARC)
    aperture_wire = lens_wire.offset_2d(-BEVEL_DEPTH,      kind=Kind.ARC)

    D, W2, TIP_R, s, ux, uz_up, uz_dn = _bevel_tip_params(clearance=GROOVE_CLEARANCE)
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
    profile_plane = _profile_plane_at_wire_start(aperture_wire)

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


def create_reference_lens(size_code: str, lens_thickness: float = 2.0) -> Part:
    """
    Reference lens with a rounded V-ridge bevel on its outer edge.
    Works for any contour shape via sweep.
    """
    spec = LENS_SPECS[size_code]
    lens_wire = make_lens_wire(spec.contour)
    T         = lens_thickness
    BZ        = BEVEL_ZONE_WIDTH / 2   # half-width of the standardised interface band
    D, W2, TIP_R, s, ux, uz_up, uz_dn = _bevel_tip_params()
    overhang  = 0.5

    # Bevel cutter profile in local (u, z): u=0 at perimeter, u<0 inward.
    # The cutter removes everything outside the fixed BZ band, leaving a
    # cylindrical interface band of BEVEL_ZONE_WIDTH regardless of lens_thickness.
    p_up          = (ux * s,   uz_up * s)
    p_dn          = (ux * s,   uz_dn * s)
    mid           = (-TIP_R,   0)
    profile_plane = _profile_plane_at_wire_start(lens_wire)

    with BuildPart() as lens:
        lens_face = Face(lens_wire)
        add(Solid.extrude(lens_face, Vector(0, 0, T)).move(Location((0, 0, -T / 2))))

        with BuildSketch(profile_plane):
            with BuildLine():
                Line((-D,        W2),         (-D,        BZ))
                Line((-D,        BZ),         (+overhang, BZ))
                Line((+overhang, BZ),         (+overhang, -BZ))
                Line((+overhang, -BZ),        (-D,        -BZ))
                Line((-D,        -BZ),        (-D,        -W2))
                Line((-D,        -W2),         p_dn)
                ThreePointArc(p_dn, mid, p_up)
                Line(p_up,                    (-D,        W2))
            make_face()
        sweep(path=lens_wire, mode=Mode.SUBTRACT)

    return lens.part


def create_bridge(width: float, y_offset: float, design: FrameDesign = DEFAULT_DESIGN) -> Part:
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
    start   = path_wire.start_point()
    tangent = path_wire.edges()[0].tangent_at(0.0).normalized()
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


def create_temple(design: FrameDesign = DEFAULT_DESIGN) -> Part:
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
        Key into LENS_SPECS (e.g. ``"UES-C-M"`` or ``"SHOWCASE-M"``).
    design:
        FrameDesign instance controlling all aesthetic dimensions.  Defaults
        to ``DEFAULT_DESIGN`` (the original reference dimensions).  Use
        ``frames.SHOWCASE`` for a chunky 3‑D‑printable prototype.
    """
    spec         = LENS_SPECS[size_code]
    bridge_width = spec.bridge_width
    wire         = make_lens_wire(spec.contour)
    bbox         = wire.bounding_box()
    nasal_reach  = bbox.max.X          # rightmost edge = nasal side of left lens
    total_span   = bbox.size.X         # full lens width (temporal-to-nasal)
    nasal_y      = _wire_y_at_max_x(wire)  # Y at the nasal tip (bridge attachment)

    temporal_x = bridge_width / 2 + total_span + design.rim_width

    with BuildPart() as frame:
        # Left rim — nasal edge at −bridge_width/2 (ISO 8624 bridge gap)
        left_rim = create_lens_rim(spec.contour, design).move(
            Location((-(bridge_width / 2 + nasal_reach), 0, 0)))
        add(left_rim)
        add(left_rim.mirror(Plane.YZ))  # mirror for right rim

        # Arch bridge
        add(create_bridge(bridge_width, y_offset=nasal_y, design=design))

        # Temples (left side = −1, right side = +1)
        for side in (-1, 1):
            t = create_temple(design).rotate(Axis.Y, -90).rotate(Axis.Z, -90)
            add(t.move(Location((side * temporal_x, 0, 0))))

    return frame.part
