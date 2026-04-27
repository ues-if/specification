import sys
from pathlib import Path

# Allow `import ues` from any working directory
sys.path.insert(0, str(Path(__file__).parent.parent))

import ocp_vscode as ocp
from build123d import Location, Plane

from ues.spec.frame import RIM_DEPTH
from ues.spec.lens import LENS_SPECS
from ues.frame_example import SHOWCASE
from ues.to_build123d.contour import contour_half_width
from ues.to_build123d.lens import create_reference_lens
from ues.to_build123d.frame import create_frame

# ── change these two lines to try different sizes / designs ──────────────────
spec   = "UES-C-M"
design = SHOWCASE
# ─────────────────────────────────────────────────────────────────────────────

rim_x     = LENS_SPECS[spec].bridge_width / 2 + contour_half_width(LENS_SPECS[spec])
Zc        = design.rim_depth / 2   # groove centre — lens Z must match when seated

frame      = create_frame(spec, design=design)
left_lens  = create_reference_lens(spec)
right_lens = left_lens.mirror(Plane.YZ)   # correct handedness for right side

ocp.show_object(frame,      options={"color": (80, 60, 40)},    reset_camera=ocp.Camera.RESET)
ocp.show_object(left_lens.move(Location((-rim_x, 0, Zc - 30))),  options={"color": (180, 180, 200)})
ocp.show_object(right_lens.move(Location(( rim_x, 0, Zc - 30))), options={"color": (180, 180, 200)})

