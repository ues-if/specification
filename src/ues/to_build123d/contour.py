"""
Universal Eyeglass Socket — Contour and cross-section helpers

Wire geometry derived from a LensSpec, and the shared bevel/groove cross-section
profile utilities used by both the lens and frame builders.
"""

from __future__ import annotations
from build123d import *

from ..spec.lens import LensSpec, BEVEL_DEPTH, BEVEL_WIDTH


def make_lens_wire(spec: LensSpec) -> Wire:
    """Return a closed Wire in the XY plane representing the physical lens perimeter."""
    pts = spec.points
    with BuildLine() as bl:
        Spline(*pts, periodic=True)
    return bl.line.wires()[0]


def contour_half_width(spec: LensSpec) -> float:
    """Return the nasal reach of the contour from its origin (boxing centre).

    Equals A/2 in ISO 8624 notation — the half bounding-box width.
    """
    return make_lens_wire(spec).bounding_box().max.X


def wire_y_at_max_x(wire: Wire) -> float:
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


def profile_plane_at_wire_start(wire: Wire) -> Plane:
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


def bevel_tip_params(clearance: float = 0.0) -> tuple:
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
