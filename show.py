import ocp_vscode as ocp
from build123d import Location

import standard_glasses

SIZE = "M"
spec = standard_glasses.LENS_SPECS[SIZE]

frame      = standard_glasses.create_frame(SIZE)
left_lens  = standard_glasses.create_reference_lens(spec.contour)
right_lens = standard_glasses.create_reference_lens(spec.contour)

rim_x = spec.bridge_width / 2 + standard_glasses.contour_half_width(spec.contour)
Zc    = standard_glasses.RIM_DEPTH / 2  # groove centre — lens Z must match when seated

ocp.show_object(frame, options={"color": (120, 80, 40)}, reset_camera=ocp.Camera.RESET)
ocp.show_object(left_lens.move(Location((-rim_x, 0, Zc - 30))),  options={"color": (180, 180, 200)})
ocp.show_object(right_lens.move(Location(( rim_x, 0, Zc - 30))), options={"color": (180, 180, 200)})
