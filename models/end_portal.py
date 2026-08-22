transparent = True
transparency = 2
is_cube = False
glass = True
translucent = False

# Non-solid passable plane
colliders = []

# Horizontal Portal Star Plane at Y = 0.25 (Y = 0.75 in world block space)
vertex_positions = [
	[ 0.5,  0.25,  0.5,   0.5,  0.25, -0.5,  -0.5,  0.25, -0.5,  -0.5,  0.25,  0.5], # top face
	[-0.5,  0.25,  0.5,  -0.5,  0.25, -0.5,   0.5,  0.25, -0.5,   0.5,  0.25,  0.5], # bottom face
]

tex_coords = [
	[0.0, 1.0, 0.0,  0.0, 0.0, 0.0,  1.0, 0.0, 0.0,  1.0, 1.0, 0.0],
	[0.0, 1.0, 0.0,  0.0, 0.0, 0.0,  1.0, 0.0, 0.0,  1.0, 1.0, 0.0],
]

shading_values = [
	[1.0, 1.0, 1.0, 1.0],
	[1.0, 1.0, 1.0, 1.0],
]
