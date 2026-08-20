"""
Nether Portal Model along X-Axis (East-West vertical plane, Z is constant)
"""
transparent = True
transparency = 2
is_cube = False
glass = True
translucent = True

# No physical collision box (entities walk through portal freely)
colliders = []

# Thin vertical portal quad plane along X-axis (Thickness 0.125 centered at Z=0)
vertex_positions = [
	# Right Face (+X edge)
	[ 0.5,  0.5,  0.0625,   0.5, -0.5,  0.0625,   0.5, -0.5, -0.0625,   0.5,  0.5, -0.0625],
	# Left Face (-X edge)
	[-0.5,  0.5, -0.0625,  -0.5, -0.5, -0.0625,  -0.5, -0.5,  0.0625,  -0.5,  0.5,  0.0625],
	# Top Face (+Y edge)
	[ 0.5,  0.5,  0.0625,   0.5,  0.5, -0.0625,  -0.5,  0.5, -0.0625,  -0.5,  0.5,  0.0625],
	# Bottom Face (-Y edge)
	[-0.5, -0.5,  0.0625,  -0.5, -0.5, -0.0625,   0.5, -0.5, -0.0625,   0.5, -0.5,  0.0625],
	# Front Face (+Z)
	[-0.5,  0.5,  0.0625,  -0.5, -0.5,  0.0625,   0.5, -0.5,  0.0625,   0.5,  0.5,  0.0625],
	# Back Face (-Z)
	[ 0.5,  0.5, -0.0625,   0.5, -0.5, -0.0625,  -0.5, -0.5, -0.0625,  -0.5,  0.5, -0.0625],
]

tex_coords = [
	[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0] for _ in range(6)
]

shading_values = [
	[1.1, 1.1, 1.1, 1.1] for _ in range(6)
]
