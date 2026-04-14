import sys
from pathlib import Path

# Allow `import ues` from any working directory
sys.path.insert(0, str(Path(__file__).parent.parent))

import ocp_vscode as ocp
from build123d import Location, Plane

from ues.spec import LENS_SPECS, RIM_DEPTH
from ues.builders import create_frame, create_reference_lens, contour_half_width

spec = "D-M"
rim_x = LENS_SPECS[spec].bridge_width / 2 + contour_half_width(LENS_SPECS[spec].contour)
Zc    = RIM_DEPTH / 2  # groove centre — lens Z must match when seated

frame      = create_frame(spec)
left_lens  = create_reference_lens(spec)
right_lens = left_lens.mirror(Plane.YZ)  # mirror for correct handedness on right side

ocp.show_object(frame,      options={"color": (120, 80, 40)},   reset_camera=ocp.Camera.RESET)
ocp.show_object(left_lens.move(Location((-rim_x, 0, Zc - 30))), options={"color": (180, 180, 200)})
ocp.show_object(right_lens.move(Location(( rim_x, 0, Zc - 30))), options={"color": (180, 180, 200)})
