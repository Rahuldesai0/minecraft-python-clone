"""
Nether Portal Model along Z-Axis (North-South vertical plane, X is constant)
"""
transparent = True
transparency = 2
is_cube = False
glass = True
translucent = True

# No physical collision box (entities walk through portal freely)
colliders = []

# Thin vertical portal quad plane along Z-axis (Thickness 0.125 centered at X=0)
vertex_positions = [
	# Right Face (+Z edge)
	[ 0.0625,  0.5,  0.5,   0.0625, -0.5,  0.5,  -0.0625, -0.5,  0.5,  -0.0625,  0.5,  0.5],
	# Left Face (-Z edge)
	[-0.0625,  0.5, -0.5,  -0.0625, -0.5, -0.5,   0.0625, -0.5, -0.5,   0.0625,  0.5, -0.5],
	# Top Face (+Y edge)
	[ 0.0625,  0.5,  0.5,   0.0625,  0.5, -0.5,  -0.0625,  0.5, -0.5,  -0.0625,  0.5,  0.5],
	# Bottom Face (-Y edge)
	[-0.0625, -0.5,  0.5,  -0.0625, -0.5, -0.5,   0.0625, -0.5, -0.5,   0.0625, -0.5,  0.5],
	# Front Face (+X)
	[ 0.0625,  0.5, -0.5,   0.0625, -0.5, -0.5,   0.0625, -0.5,  0.5,   0.0625,  0.5,  0.5],
	# Back Face (-X)
	[-0.0625,  0.5,  0.5,  -0.0625, -0.5,  0.5,  -0.0625, -0.5, -0.5,  -0.0625,  0.5, -0.5],
]

tex_coords = [
	[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0] for _ in range(6)
]

shading_values = [
	[1.1, 1.1, 1.1, 1.1] for _ in range(6)
]
