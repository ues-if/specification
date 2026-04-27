"""
Universal Eyeglass Socket — build123d geometry sub-package

Re-exports all public builder functions so that
``from ues.to_build123d import …`` works as a single import point.
"""

from .contour import (
    make_lens_wire,
    contour_half_width,
    wire_y_at_max_x,
    profile_plane_at_wire_start,
    bevel_tip_params,
)
from .lens import create_reference_lens
from .frame import create_frame

__all__ = [
    "make_lens_wire",
    "contour_half_width",
    "wire_y_at_max_x",
    "profile_plane_at_wire_start",
    "bevel_tip_params",
    "create_reference_lens",
    "create_frame",
]
