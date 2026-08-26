import math

CARDINAL_DIRECTIONS = ["NORTH", "SOUTH", "WEST", "EAST"]
OPPOSITE_DIRECTIONS = {
	"NORTH": "SOUTH",
	"SOUTH": "NORTH",
	"WEST": "EAST",
	"EAST": "WEST"
}
LEFT_DIRECTIONS = {
	"NORTH": "WEST",
	"SOUTH": "EAST",
	"WEST": "SOUTH",
	"EAST": "NORTH"
}
RIGHT_DIRECTIONS = {
	"NORTH": "EAST",
	"SOUTH": "WEST",
	"WEST": "NORTH",
	"EAST": "SOUTH"
}

OFFSET_BY_DIR = {
	"NORTH": (0, 0, -1),
	"SOUTH": (0, 0, 1),
	"WEST": (-1, 0, 0),
	"EAST": (1, 0, 0)
}

class BlockState:
	def __init__(self, block_id, facing="NORTH", half="LOWER", hinge="LEFT", open_state=False, shape="STRAIGHT", axis="Y", connections=None):
		self.block_id = block_id
		self.facing = facing         # "NORTH", "SOUTH", "WEST", "EAST"
		self.half = half             # "LOWER", "UPPER", "BOTTOM", "TOP", "DOUBLE"
		self.hinge = hinge           # "LEFT", "RIGHT"
		self.open_state = open_state # True / False
		self.shape = shape           # "STRAIGHT", "INNER_LEFT", "INNER_RIGHT", "OUTER_LEFT", "OUTER_RIGHT"
		self.axis = axis             # "Y", "X", "Z"
		self.connections = connections or {"north": False, "south": False, "west": False, "east": False}

	def to_dict(self):
		return {
			"b_id": self.block_id,
			"f": self.facing,
			"h": self.half,
			"hg": self.hinge,
			"o": self.open_state,
			"s": self.shape,
			"a": self.axis,
			"c": self.connections.copy()
		}

	@staticmethod
	def from_dict(d):
		if not d: return None
		return BlockState(
			block_id=d.get("b_id", 0),
			facing=d.get("f", "NORTH"),
			half=d.get("h", "LOWER"),
			hinge=d.get("hg", "LEFT"),
			open_state=d.get("o", False),
			shape=d.get("s", "STRAIGHT"),
			axis=d.get("a", "Y"),
			connections=d.get("c", {"north": False, "south": False, "west": False, "east": False})
		)


def get_player_facing(camera_rotation):
	"""Calculate cardinal direction from camera rotation."""
	rad_x = camera_rotation[0]
	deg = (math.degrees(rad_x) + 360) % 360
	if deg < 45 or deg >= 315:
		return "NORTH"
	elif 45 <= deg < 135:
		return "EAST"
	elif 135 <= deg < 225:
		return "SOUTH"
	else:
		return "WEST"


def calculate_stair_shape(world, pos, facing, half):
	"""Deterministic calculation of stair shape from neighboring stairs."""
	x, y, z = pos
	
	# Check block behind this stair
	behind_offset = OFFSET_BY_DIR[OPPOSITE_DIRECTIONS[facing]]
	behind_pos = (x + behind_offset[0], y + behind_offset[1], z + behind_offset[2])
	behind_state = world.get_block_state(behind_pos)
	behind_b = world.get_block_number(behind_pos)

	if behind_b in (41, 42, 73, 74, 92, 93, 178, 179, 227, 237, 247, 257, 267) and behind_state:
		b_half = getattr(behind_state, "half", "BOTTOM")
		if b_half == half or (half == "BOTTOM" and b_half == "LOWER") or (half == "TOP" and b_half == "UPPER"):
			if behind_state.facing == RIGHT_DIRECTIONS[facing]:
				return "INNER_RIGHT"
			elif behind_state.facing == LEFT_DIRECTIONS[facing]:
				return "INNER_LEFT"

	# Check block in front of this stair
	front_offset = OFFSET_BY_DIR[facing]
	front_pos = (x + front_offset[0], y + front_offset[1], z + front_offset[2])
	front_state = world.get_block_state(front_pos)
	front_b = world.get_block_number(front_pos)

	if front_b in (41, 42, 73, 74, 92, 93, 178, 179, 227, 237, 247, 257, 267) and front_state:
		f_half = getattr(front_state, "half", "BOTTOM")
		if f_half == half or (half == "BOTTOM" and f_half == "LOWER") or (half == "TOP" and f_half == "UPPER"):
			if front_state.facing == RIGHT_DIRECTIONS[facing]:
				return "OUTER_RIGHT"
			elif front_state.facing == LEFT_DIRECTIONS[facing]:
				return "OUTER_LEFT"

	return "STRAIGHT"


def _get_world_info(world):
	if hasattr(world, "get_block_types_info"):
		return world.get_block_types_info()
	return getattr(world, "block_types_info", {})


PASSABLE_BLOCKS = {
	0,
	# Liquids
	9, 19, 15, 20,
	# Flowers, Ferns, Foliage & Vines
	10, 12, 31, 33, 210, 279, 280, 283, 284, 285,
	# Saplings
	156, 225, 235, 245, 255, 265,
	# Crops & Stems
	81, 94, 204, 205, 206, 207,
	# Hazards, Torches, Portals, Redstone components
	78, 79, 88, 89, 183, 190, 191, 192, 193, 194, 195, 196, 197
}

FLOWERS_AND_SAPLINGS = {
	10, 33, 279, 283, 284, 285,
	156, 225, 235, 245, 255, 265
}

VALID_SOIL_BLOCKS = {2, 3, 4, 80, 278}

NON_CONNECTABLE_BLOCKS = {
	0, 9, 10, 11, 12, 13, 15, 19, 20, 25, 31, 33, 43, 44, 45, 46, 47, 48, 49, 50,
	65, 66, 67, 68, 69, 70, 71, 72, 78, 79, 81, 88, 89, 94, 156, 181, 182, 183,
	190, 191, 192, 193, 194, 195, 196, 197, 204, 205, 206, 207, 210, 213, 218, 219, 220, 221,
	224, 225, 228, 229, 230, 234, 235, 238, 239, 240, 244, 245, 248, 249, 250,
	254, 255, 258, 259, 260, 264, 265, 268, 269, 270, 279, 280, 283, 284, 285
}


def is_connectable_fence(nb_b, my_b, world_info):
	if nb_b in NON_CONNECTABLE_BLOCKS:
		return False
	if my_b in (51, 91, 231, 241, 251, 261, 271) and nb_b in (51, 91, 231, 241, 251, 261, 271, 75, 76, 272, 273, 274, 275, 276): return True
	if my_b == 52 and nb_b in (52, 53, 99, 75, 76, 272, 273, 274, 275, 276): return True
	if my_b in (53, 99):
		# Glass panes & Iron bars connect to other panes (53), iron bars (99), glass blocks (21), walls (52), fences, gates, and all solid blocks/stairs/slabs
		return True
	info = world_info.get(nb_b, {}) if world_info else {}
	if info:
		return info.get("is_cube", False) and not info.get("transparent", False)
	return 1 <= nb_b <= 300


def calculate_fence_connections(world, pos, my_b):
	x, y, z = pos
	res = {}
	info_map = _get_world_info(world)
	for dir_name, (dx, dy, dz) in OFFSET_BY_DIR.items():
		nb_pos = (x + dx, y + dy, z + dz)
		nb_b = world.get_block_number(nb_pos)
		res[dir_name.lower()] = is_connectable_fence(nb_b, my_b, info_map)
	return res


def calculate_wall_connections(world, pos, my_b):
	x, y, z = pos
	res = {}
	info_map = _get_world_info(world)
	for dir_name, (dx, dy, dz) in OFFSET_BY_DIR.items():
		nb_pos = (x + dx, y + dy, z + dz)
		nb_b = world.get_block_number(nb_pos)
		res[dir_name.lower()] = is_connectable_fence(nb_b, my_b, info_map)
	return res


def calculate_pane_connections(world, pos, my_b):
	x, y, z = pos
	res = {}
	info_map = _get_world_info(world)
	for dir_name, (dx, dy, dz) in OFFSET_BY_DIR.items():
		nb_pos = (x + dx, y + dy, z + dz)
		nb_b = world.get_block_number(nb_pos)
		res[dir_name.lower()] = is_connectable_fence(nb_b, my_b, info_map)
	return res


def calculate_door_hinge(world, pos, facing, hit_pos=None):
	"""Determine door hinge (LEFT vs RIGHT) based on neighboring block context and clicked position."""
	x, y, z = pos
	right_dir = RIGHT_DIRECTIONS[facing]
	left_dir = LEFT_DIRECTIONS[facing]

	r_off = OFFSET_BY_DIR[right_dir]
	l_off = OFFSET_BY_DIR[left_dir]

	r_pos = (x + r_off[0], y + r_off[1], z + r_off[2])
	l_pos = (x + l_off[0], y + l_off[1], z + l_off[2])

	r_b = world.get_block_number(r_pos)
	l_b = world.get_block_number(l_pos)
	r_st = world.get_block_state(r_pos)
	l_st = world.get_block_state(l_pos)

	# 1. Double door mirror check: if adjacent block has a door facing same direction
	if r_st and r_st.facing == facing and r_b in (43, 44, 45, 46, 65, 66, 67, 68, 228, 229, 238, 239, 248, 249, 258, 259, 268, 269):
		return "RIGHT" if r_st.hinge == "LEFT" else "LEFT"
	if l_st and l_st.facing == facing and l_b in (43, 44, 45, 46, 65, 66, 67, 68, 228, 229, 238, 239, 248, 249, 258, 259, 268, 269):
		return "LEFT" if l_st.hinge == "RIGHT" else "RIGHT"

	# 2. Solid neighbor blocks
	info_map = getattr(world, "block_types_info", {})
	r_solid = r_b != 0 and info_map.get(r_b, {}).get("is_cube", False) and not info_map.get(r_b, {}).get("transparent", False)
	l_solid = l_b != 0 and info_map.get(l_b, {}).get("is_cube", False) and not info_map.get(l_b, {}).get("transparent", False)

	if r_solid and not l_solid:
		return "RIGHT"
	if l_solid and not r_solid:
		return "LEFT"

	# 3. Hit position on target block face
	if hit_pos is not None:
		hx, hy, hz = hit_pos
		lx = hx - math.floor(hx)
		lz = hz - math.floor(hz)
		if facing == "NORTH": cross = lx
		elif facing == "SOUTH": cross = 1.0 - lx
		elif facing == "EAST": cross = lz
		else: cross = 1.0 - lz
		if cross >= 0.5:
			return "RIGHT"

	return "LEFT"


def ray_intersect_aabb(ray_orig, ray_dir, box):
	"""Returns (t_hit, face_vector) if ray intersects AABB box at t > 0, else (None, None).
	box: (min_x, min_y, min_z, max_x, max_y, max_z)
	"""
	ox, oy, oz = ray_orig
	dx, dy, dz = ray_dir
	min_x, min_y, min_z, max_x, max_y, max_z = box

	t_near = -float('inf')
	t_far = float('inf')
	near_face = None

	# X axis
	if abs(dx) < 1e-8:
		if ox < min_x or ox > max_x:
			return None, None
	else:
		t1 = (min_x - ox) / dx
		t2 = (max_x - ox) / dx
		face1 = (-1, 0, 0)
		face2 = (1, 0, 0)
		if t1 > t2:
			t1, t2 = t2, t1
			face1, face2 = face2, face1
		if t1 > t_near:
			t_near = t1
			near_face = face1
		if t2 < t_far:
			t_far = t2
		if t_near > t_far or t_far < 0:
			return None, None

	# Y axis
	if abs(dy) < 1e-8:
		if oy < min_y or oy > max_y:
			return None, None
	else:
		t1 = (min_y - oy) / dy
		t2 = (max_y - oy) / dy
		face1 = (0, -1, 0)
		face2 = (0, 1, 0)
		if t1 > t2:
			t1, t2 = t2, t1
			face1, face2 = face2, face1
		if t1 > t_near:
			t_near = t1
			near_face = face1
		if t2 < t_far:
			t_far = t2
		if t_near > t_far or t_far < 0:
			return None, None

	# Z axis
	if abs(dz) < 1e-8:
		if oz < min_z or oz > max_z:
			return None, None
	else:
		t1 = (min_z - oz) / dz
		t2 = (max_z - oz) / dz
		face1 = (0, 0, -1)
		face2 = (0, 0, 1)
		if t1 > t2:
			t1, t2 = t2, t1
			face1, face2 = face2, face1
		if t1 > t_near:
			t_near = t1
			near_face = face1
		if t2 < t_far:
			t_far = t2
		if t_near > t_far or t_far < 0:
			return None, None

	if t_near < 0:
		t_near = 0.0

	return t_near, near_face


def get_block_hitboxes(world, pos, block_num):
	"""Returns list of world-space AABB bounding boxes (min_x, min_y, min_z, max_x, max_y, max_z) for block_num at pos."""
	if block_num in PASSABLE_BLOCKS:
		return []

	bx, by, bz = pos
	st = world.get_block_state(pos) if world else None
	facing = getattr(st, 'facing', 'NORTH') if st else 'NORTH'
	half = getattr(st, 'half', 'BOTTOM') if st else 'BOTTOM'
	shape = getattr(st, 'shape', 'STRAIGHT') if st else 'STRAIGHT'
	hinge = getattr(st, 'hinge', 'LEFT') if st else 'LEFT'
	open_state = getattr(st, 'open_state', False) if st else False
	conns = getattr(st, 'connections', None) if st else None

	def rotate_box(min_pt, max_pt, rot_facing):
		def rot(p):
			vx, vy, vz = p
			if rot_facing == "EAST": return (-vz, vy, vx)
			elif rot_facing == "SOUTH": return (-vx, vy, -vz)
			elif rot_facing == "WEST": return (vz, vy, -vx)
			return (vx, vy, vz)

		p1 = rot((min_pt[0], min_pt[1], min_pt[2]))
		p2 = rot((max_pt[0], max_pt[1], max_pt[2]))
		return (
			bx + min(p1[0], p2[0]),
			by + min(p1[1], p2[1]),
			bz + min(p1[2], p2[2]),
			bx + max(p1[0], p2[0]),
			by + max(p1[1], p2[1]),
			bz + max(p1[2], p2[2])
		)

	# 1. Slabs (38, 39, 40, 62, 63, 64, 95, 180, 226, 236, 246, 256, 266)
	if block_num in (38, 39, 40, 62, 63, 64, 95, 180, 226, 236, 246, 256, 266):
		sl_h = "TOP" if block_num in (62, 63, 64) else half
		if sl_h == "DOUBLE":
			return [(bx - 0.5, by - 0.5, bz - 0.5, bx + 0.5, by + 0.5, bz + 0.5)]
		elif sl_h == "TOP":
			return [(bx - 0.5, by, bz - 0.5, bx + 0.5, by + 0.5, bz + 0.5)]
		else:
			return [(bx - 0.5, by - 0.5, bz - 0.5, bx + 0.5, by, bz + 0.5)]

	# 2. Doors (43, 44, 45, 46, 65, 66, 67, 68, 228, 229, 238, 239, 248, 249, 258, 259, 268, 269)
	if block_num in (43, 44, 45, 46, 65, 66, 67, 68, 228, 229, 238, 239, 248, 249, 258, 259, 268, 269):
		d_open = open_state or (block_num in (44, 46, 66, 68))
		if d_open:
			if hinge == "RIGHT":
				return [rotate_box((0.3125, -0.5, -0.5), (0.5, 0.5, 0.5), facing)]
			else:
				return [rotate_box((-0.5, -0.5, -0.5), (-0.3125, 0.5, 0.5), facing)]
		else:
			return [rotate_box((-0.5, -0.5, -0.5), (0.5, 0.5, -0.3125), facing)]

	# 3. Trapdoors (47, 48, 49, 50, 69, 70, 71, 72, 230, 240, 250, 260, 270)
	if block_num in (47, 48, 49, 50, 69, 70, 71, 72, 230, 240, 250, 260, 270):
		is_top = block_num in (69, 70, 71, 72) or half == "TOP"
		td_open = open_state or (block_num in (48, 50, 70, 72))
		if td_open:
			return [rotate_box((-0.5, -0.5, -0.5), (0.5, 0.5, -0.3125), facing)]
		else:
			if is_top:
				return [rotate_box((-0.5, 0.3125, -0.5), (0.5, 0.5, 0.5), facing)]
			else:
				return [rotate_box((-0.5, -0.5, -0.5), (0.5, -0.3125, 0.5), facing)]

	# 4. Stairs (41, 42, 73, 74, 92, 93, 178, 179, 227, 237, 247, 257, 267)
	if block_num in (41, 42, 73, 74, 92, 93, 178, 179, 227, 237, 247, 257, 267):
		is_top_stair = (block_num in (73, 74, 93, 179) or half in ("TOP", "UPPER"))
		y_base_min, y_base_max = (0.0, 0.5) if is_top_stair else (-0.5, 0.0)
		y_step_min, y_step_max = (-0.5, 0.0) if is_top_stair else (0.0, 0.5)

		boxes = [rotate_box((-0.5, y_base_min, -0.5), (0.5, y_base_max, 0.5), facing)]
		if shape == "INNER_LEFT":
			boxes.append(rotate_box((-0.5, y_step_min, -0.5), (0.5, y_step_max, 0.0), facing))
			boxes.append(rotate_box((-0.5, y_step_min, 0.0), (0.0, y_step_max, 0.5), facing))
		elif shape == "INNER_RIGHT":
			boxes.append(rotate_box((-0.5, y_step_min, -0.5), (0.5, y_step_max, 0.0), facing))
			boxes.append(rotate_box((0.0, y_step_min, 0.0), (0.5, y_step_max, 0.5), facing))
		elif shape == "OUTER_LEFT":
			boxes.append(rotate_box((-0.5, y_step_min, -0.5), (0.0, y_step_max, 0.0), facing))
		elif shape == "OUTER_RIGHT":
			boxes.append(rotate_box((0.0, y_step_min, -0.5), (0.5, y_step_max, 0.0), facing))
		else:
			boxes.append(rotate_box((-0.5, y_step_min, -0.5), (0.5, y_step_max, 0.0), facing))
		return boxes

	# 5. Fences (51, 91, 231, 241, 251, 261, 271)
	if block_num in (51, 91, 231, 241, 251, 261, 271):
		if conns is None and world:
			conns = calculate_fence_connections(world, pos, block_num)
		boxes = [(bx - 0.125, by - 0.5, bz - 0.125, bx + 0.125, by + 0.5, bz + 0.125)]
		if conns:
			if conns.get("north", False):
				boxes.append((bx - 0.0625, by - 0.375, bz - 0.5, bx + 0.0625, by + 0.375, bz - 0.125))
			if conns.get("south", False):
				boxes.append((bx - 0.0625, by - 0.375, bz + 0.125, bx + 0.0625, by + 0.375, bz + 0.5))
			if conns.get("west", False):
				boxes.append((bx - 0.5, by - 0.375, bz - 0.0625, bx - 0.125, by + 0.375, bz + 0.0625))
			if conns.get("east", False):
				boxes.append((bx + 0.125, by - 0.375, bz - 0.0625, bx + 0.5, by + 0.375, bz + 0.0625))
		return boxes

	# 6. Walls (52)
	if block_num == 52:
		if conns is None and world:
			conns = calculate_wall_connections(world, pos, 52)
		boxes = [(bx - 0.25, by - 0.5, bz - 0.25, bx + 0.25, by + 0.5, bz + 0.25)]
		if conns:
			if conns.get("north", False):
				boxes.append((bx - 0.15, by - 0.5, bz - 0.5, bx + 0.15, by + 0.35, bz - 0.25))
			if conns.get("south", False):
				boxes.append((bx - 0.15, by - 0.5, bz + 0.25, bx + 0.15, by + 0.35, bz + 0.5))
			if conns.get("west", False):
				boxes.append((bx - 0.5, by - 0.5, bz - 0.15, bx - 0.25, by + 0.35, bz + 0.15))
			if conns.get("east", False):
				boxes.append((bx + 0.25, by - 0.5, bz - 0.15, bx + 0.5, by + 0.35, bz + 0.15))
		return boxes

	# 7. Glass Panes (53)
	if block_num == 53:
		if conns is None and world:
			conns = calculate_pane_connections(world, pos, 53)
		boxes = [(bx - 0.0625, by - 0.5, bz - 0.0625, bx + 0.0625, by + 0.5, bz + 0.0625)]
		has_conn = False
		if conns:
			if conns.get("north", False):
				boxes.append((bx - 0.0625, by - 0.5, bz - 0.5, bx + 0.0625, by + 0.5, bz - 0.0625))
				has_conn = True
			if conns.get("south", False):
				boxes.append((bx - 0.0625, by - 0.5, bz + 0.0625, bx + 0.0625, by + 0.5, bz + 0.5))
				has_conn = True
			if conns.get("west", False):
				boxes.append((bx - 0.5, by - 0.5, bz - 0.0625, bx - 0.0625, by + 0.5, bz + 0.0625))
				has_conn = True
			if conns.get("east", False):
				boxes.append((bx + 0.0625, by - 0.5, bz - 0.0625, bx + 0.5, by + 0.5, bz + 0.0625))
				has_conn = True
		if not has_conn:
			boxes = [
				(bx - 0.5, by - 0.5, bz - 0.0625, bx + 0.5, by + 0.5, bz + 0.0625),
				(bx - 0.0625, by - 0.5, bz - 0.5, bx + 0.0625, by + 0.5, bz + 0.5)
			]
		return boxes

	# 8. Fence Gates (75, 76, 272, 273, 274, 275, 276)
	if block_num in (75, 76, 272, 273, 274, 275, 276):
		gate_open = open_state or (block_num == 76)
		if gate_open:
			return [
				rotate_box((-0.5, -0.5, -0.125), (-0.375, 0.5, 0.5), facing),
				rotate_box((0.375, -0.5, -0.125), (0.5, 0.5, 0.5), facing)
			]
		else:
			return [
				rotate_box((-0.5, -0.5, -0.125), (-0.375, 0.5, 0.125), facing),
				rotate_box((0.375, -0.5, -0.125), (0.5, 0.5, 0.125), facing),
				rotate_box((-0.375, -0.375, -0.0625), (0.375, 0.375, 0.0625), facing)
			]

	# 9. Enchanting Table (213) - Height 12/16 (0.75 blocks)
	if block_num == 213:
		return [(bx - 0.5, by - 0.5, bz - 0.5, bx + 0.5, by + 0.25, bz + 0.5)]

	# 10. Cactus (11) - Indented by 1/16 (0.0625) on sides (radius 0.4375)
	if block_num == 11:
		return [(bx - 0.4375, by - 0.5, bz - 0.4375, bx + 0.4375, by + 0.5, bz + 0.4375)]

	# Standard Full Cube
	return [(bx - 0.5, by - 0.5, bz - 0.5, bx + 0.5, by + 0.5, bz + 0.5)]



