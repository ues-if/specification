import ocp_vscode as ocp

import standard_glasses

#lens = standard_glasses.create_reference_lens("M")
frame = standard_glasses.create_frame("M")
ocp.show_object(frame, options={"color": (180, 180, 200)}, reset_camera=ocp.Camera.RESET)
