"""
Universal Eyeglass Socket — Lens builder

Builds the reference compliant lens body: a flat disc with a standardised
bevel ridge on its outer edge, swept around any contour shape.
"""

from __future__ import annotations
from build123d import *

from ..spec.lens import LENS_SPECS, BEVEL_ZONE_WIDTH
from .contour import make_lens_wire, bevel_tip_params, profile_plane_at_wire_start


def create_reference_lens(size_code: str, lens_thickness: float = 2.0) -> Part:
    """
    Reference lens with a rounded V-ridge bevel on its outer edge.
    Works for any contour shape via sweep.
    """
    spec = LENS_SPECS[size_code]
    lens_wire = make_lens_wire(spec)
    T         = lens_thickness
    BZ_TOP    = T / 2                        # anterior face of lens (= anterior face of bevel zone)
    BZ_BOT    = T / 2 - BEVEL_ZONE_WIDTH     # posterior end of bevel zone
    BZ_CEN    = T / 2 - BEVEL_ZONE_WIDTH / 2 # centre of bevel zone (ridge sits here, equal flat lands)
    D, W2, TIP_R, s, ux, uz_up, uz_dn = bevel_tip_params()
    # Cutter extends this far *outward* past the perimeter (u > 0) so the boolean
    # subtract cleanly removes the outer face regardless of spline numerical slop.
    # The disc boundary caps it — this value does not appear in the output geometry.
    cutter_overhang = 0.5

    # Bevel cutter profile in local (u, z): u=0 at perimeter, u<0 inward.
    # The bevel zone is anchored at the anterior face (BZ_TOP) and extends
    # posteriorly to BZ_BOT.  The V-ridge sits at BZ_CEN with 0.72 mm flat lands
    # on each side.  The cutter removes the outer ring posterior to BZ_BOT (for
    # lenses thicker than BEVEL_ZONE_WIDTH) and carves the V-ridge.
    p_up          = (ux * s,   uz_up * s + BZ_CEN)
    p_dn          = (ux * s,   uz_dn * s + BZ_CEN)
    mid           = (-TIP_R,   BZ_CEN)
    profile_plane = profile_plane_at_wire_start(lens_wire)

    with BuildPart() as lens:
        lens_face = Face(lens_wire)
        add(Solid.extrude(lens_face, Vector(0, 0, T)).move(Location((0, 0, -T / 2))))

        with BuildSketch(profile_plane):
            with BuildLine():
                Line((-D,        W2 + BZ_CEN),  (-D,        BZ_TOP))
                Line((-D,        BZ_TOP),        (+cutter_overhang, BZ_TOP))
                Line((+cutter_overhang, BZ_TOP), (+cutter_overhang, BZ_BOT))
                Line((+cutter_overhang, BZ_BOT), (-D,        BZ_BOT))
                Line((-D,        BZ_BOT),        (-D,        -W2 + BZ_CEN))
                Line((-D,        -W2 + BZ_CEN),  p_dn)
                ThreePointArc(p_dn, mid, p_up)
                Line(p_up,                       (-D,        W2 + BZ_CEN))
            make_face()
        sweep(path=lens_wire, mode=Mode.SUBTRACT)

    return lens.part
