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

	if behind_b in (41, 42, 73, 74) and behind_state:
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

	if front_b in (41, 42, 73, 74) and front_state:
		f_half = getattr(front_state, "half", "BOTTOM")
		if f_half == half or (half == "BOTTOM" and f_half == "LOWER") or (half == "TOP" and f_half == "UPPER"):
			if front_state.facing == RIGHT_DIRECTIONS[facing]:
				return "OUTER_RIGHT"
			elif front_state.facing == LEFT_DIRECTIONS[facing]:
				return "OUTER_LEFT"

	return "STRAIGHT"


def is_connectable_fence(nb_b, my_b, world_info):
	if nb_b == 0 or nb_b in (9, 19, 15, 20): return False
	if nb_b == my_b: return True
	if my_b == 51 and nb_b == 51: return True
	if my_b == 52 and nb_b in (52, 53): return True
	if my_b == 53 and nb_b in (53, 52): return True
	info = world_info.get(nb_b, {})
	return info.get("is_cube", False) and not info.get("transparent", False)


def calculate_fence_connections(world, pos, my_b):
	x, y, z = pos
	res = {}
	info_map = getattr(world, "block_types_info", {})
	for dir_name, (dx, dy, dz) in OFFSET_BY_DIR.items():
		nb_pos = (x + dx, y + dy, z + dz)
		nb_b = world.get_block_number(nb_pos)
		res[dir_name.lower()] = is_connectable_fence(nb_b, my_b, info_map)
	return res


def calculate_wall_connections(world, pos, my_b):
	x, y, z = pos
	res = {}
	info_map = getattr(world, "block_types_info", {})
	for dir_name, (dx, dy, dz) in OFFSET_BY_DIR.items():
		nb_pos = (x + dx, y + dy, z + dz)
		nb_b = world.get_block_number(nb_pos)
		res[dir_name.lower()] = is_connectable_fence(nb_b, my_b, info_map)
	return res


def calculate_pane_connections(world, pos, my_b):
	x, y, z = pos
	res = {}
	info_map = getattr(world, "block_types_info", {})
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
	if r_st and r_st.facing == facing and r_b in (43, 44, 45, 46, 65, 66, 67, 68):
		return "RIGHT" if r_st.hinge == "LEFT" else "LEFT"
	if l_st and l_st.facing == facing and l_b in (43, 44, 45, 46, 65, 66, 67, 68):
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



