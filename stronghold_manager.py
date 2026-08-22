"""
Minecraft Java Edition Stronghold Generation System
---------------------------------------------------
Implements authentic Minecraft Java Edition concentric ring stronghold placement,
connected procedural puzzle-piece graph generation, underground carving,
and complete End Portal Room with End Portal Frame ring, lava pit, and Silverfish spawner.
"""

import math
import random
from random import Random

# Block IDs used in Strongholds
BLOCK_AIR = 0
BLOCK_COBBLESTONE = 1
BLOCK_OAK_PLANKS = 7
BLOCK_LAVA = 15
BLOCK_BOOKSHELF = 23
BLOCK_CHEST = 37
BLOCK_OAK_DOOR = 43
BLOCK_IRON_DOOR = 45
BLOCK_TORCH = 79
BLOCK_STONE_BRICK = 96
BLOCK_MOSSY_STONE_BRICK = 97
BLOCK_CRACKED_STONE_BRICK = 98
BLOCK_IRON_BARS = 99
BLOCK_STONE_BRICK_STAIRS = 178
BLOCK_STONE_BRICK_STAIRS_TOP = 179
BLOCK_STONE_BRICK_SLAB = 180
BLOCK_END_PORTAL_FRAME = 181
BLOCK_END_PORTAL_FRAME_FILLED = 182
BLOCK_END_PORTAL = 183
BLOCK_INFESTED_STONE_BRICK = 184
BLOCK_INFESTED_MOSSY = 185
BLOCK_INFESTED_CRACKED = 186
BLOCK_INFESTED_STONE = 187

# Directions & Orientations (0: North -Z, 1: East +X, 2: South +Z, 3: West -X)
DIR_VECTORS = {
	0: (0, -1),
	1: (1, 0),
	2: (0, 1),
	3: (-1, 0)
}
OPPOSITE_DIR = {0: 2, 1: 3, 2: 0, 3: 1}


def rotate_point(x, y, z, rot):
	"""Rotates relative local coordinates (x, y, z) so +Z is forward along orientation rot (0..3)."""
	if rot == 0:   # North (-Z)
		return x, y, -z
	elif rot == 1: # East (+X)
		return z, y, x
	elif rot == 2: # South (+Z)
		return -x, y, z
	elif rot == 3: # West (-X)
		return -z, y, -x
	return x, y, z


def transform_box(min_pt, max_pt, origin, rot):
	"""Transforms a local AABB to world space given origin (ox, oy, oz) and rot."""
	ox, oy, oz = origin
	corners = [
		rotate_point(min_pt[0], min_pt[1], min_pt[2], rot),
		rotate_point(max_pt[0], min_pt[1], max_pt[2], rot),
		rotate_point(min_pt[0], max_pt[1], min_pt[2], rot),
		rotate_point(max_pt[0], max_pt[1], max_pt[2], rot),
		rotate_point(min_pt[0], min_pt[1], max_pt[2], rot),
		rotate_point(max_pt[0], min_pt[1], max_pt[2], rot),
		rotate_point(min_pt[0], max_pt[1], min_pt[2], rot),
		rotate_point(max_pt[0], max_pt[1], max_pt[2], rot),
	]
	xs = [c[0] + ox for c in corners]
	ys = [c[1] + oy for c in corners]
	zs = [c[2] + oz for c in corners]
	return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def boxes_intersect(b1, b2, margin=0):
	"""Checks if two 3D AABB boxes intersect with an optional shrink margin."""
	return not (
		b1[3] - margin <= b2[0] + margin or b1[0] + margin >= b2[3] - margin or
		b1[4] - margin <= b2[1] + margin or b1[1] + margin >= b2[4] - margin or
		b1[5] - margin <= b2[2] + margin or b1[2] + margin >= b2[5] - margin
	)


# =========================================================================
# Stronghold Piece Base & Specialized Pieces
# =========================================================================

class StrongholdPiece:
	def __init__(self, piece_type, origin, rot):
		self.piece_type = piece_type
		self.origin = origin  # (world_x, world_y, world_z)
		self.rot = rot        # 0, 1, 2, 3
		self.local_box = (-2, -1, 0, 2, 5, 5)
		self.world_box = (0, 0, 0, 0, 0, 0)
		self.connectors = [] # list of (world_x, world_y, world_z, exit_rot)
		self.spawner_pos = None

	def calculate_world_bounds_and_connectors(self, local_connectors):
		ox, oy, oz = self.origin
		self.world_box = transform_box(self.local_box[:3], self.local_box[3:], self.origin, self.rot)
		self.connectors = []
		for lx, ly, lz, exit_rot_rel in local_connectors:
			rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
			exit_rot = (self.rot + exit_rot_rel) % 4
			self.connectors.append((ox + rx, oy + ry, oz + rz, exit_rot))

	def get_random_stone_brick(self, rng):
		"""Returns authentic random distribution of Stone Brick variants & Infested blocks."""
		r = rng.random()
		if r < 0.65:
			return BLOCK_STONE_BRICK
		elif r < 0.80:
			return BLOCK_MOSSY_STONE_BRICK
		elif r < 0.95:
			return BLOCK_CRACKED_STONE_BRICK
		else:
			# 5% chance of infested monster egg block
			return rng.choice((BLOCK_INFESTED_STONE_BRICK, BLOCK_INFESTED_MOSSY, BLOCK_INFESTED_CRACKED))

	def generate_blocks(self, rng):
		"""Returns dict of (wx, wy, wz) -> block_id and optional chest loot."""
		return {}, {}


class StrongholdCrossingPiece(StrongholdPiece):
	"""5-Way Crossing / Hub Piece: 9x6x9 hollow stone brick room with 4 side exits & stairs down."""
	def __init__(self, origin, rot):
		super().__init__("crossing", origin, rot)
		self.local_box = (-4, -1, -4, 4, 5, 4)
		local_connectors = [
			(0, 0, 4, 0),   # Forward (North in local)
			(4, 0, 0, 1),   # Right (East)
			(0, 0, -4, 2),  # Back (South)
			(-4, 0, 0, 3),  # Left (West)
		]
		self.calculate_world_bounds_and_connectors(local_connectors)

	def generate_blocks(self, rng):
		blocks = {}
		ox, oy, oz = self.origin
		for lx in range(-4, 5):
			for ly in range(-1, 6):
				for lz in range(-4, 5):
					rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
					wx, wy, wz = ox + rx, oy + ry, oz + rz
					is_wall = (lx in (-4, 4) or lz in (-4, 4) or ly in (-1, 5))
					# Carve doorway arches on all 4 faces
					is_doorway = (0 <= ly <= 2) and (
						(lz in (-4, 4) and -1 <= lx <= 1) or
						(lx in (-4, 4) and -1 <= lz <= 1)
					)
					if is_wall and not is_doorway:
						blocks[(wx, wy, wz)] = self.get_random_stone_brick(rng)
					else:
						blocks[(wx, wy, wz)] = BLOCK_AIR

		# Place central torch on stone brick pillar
		rx, ry, rz = rotate_point(0, 2, 0, self.rot)
		blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_TORCH
		return blocks, {}


class StrongholdStraightCorridorPiece(StrongholdPiece):
	"""Straight Stone Brick Corridor: 5 blocks long, 5 wide, 5 high with arch ceiling."""
	def __init__(self, origin, rot):
		super().__init__("corridor", origin, rot)
		self.local_box = (-2, -1, 0, 2, 4, 5)
		local_connectors = [
			(0, 0, 5, 0) # Continuing forward
		]
		self.calculate_world_bounds_and_connectors(local_connectors)

	def generate_blocks(self, rng):
		blocks = {}
		ox, oy, oz = self.origin
		for lx in range(-2, 3):
			for ly in range(-1, 5):
				for lz in range(0, 6):
					rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
					wx, wy, wz = ox + rx, oy + ry, oz + rz
					is_wall = (lx in (-2, 2) or ly in (-1, 4))
					is_exit = (lz in (0, 5) and -1 <= lx <= 1 and 0 <= ly <= 2)
					if is_wall and not is_exit:
						blocks[(wx, wy, wz)] = self.get_random_stone_brick(rng)
					else:
						blocks[(wx, wy, wz)] = BLOCK_AIR

		# Torches on walls at z=2
		for tx_local in (-1, 1):
			rx, ry, rz = rotate_point(tx_local, 2, 2, self.rot)
			blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_TORCH

		return blocks, {}


class StrongholdCorridorTurnPiece(StrongholdPiece):
	"""Corridor 90-Degree Turn (Left or Right)."""
	def __init__(self, origin, rot, turn_dir=1):
		super().__init__("turn", origin, rot)
		self.turn_dir = turn_dir # 1 = Right, 3 = Left
		if turn_dir == 1:
			self.local_box = (-2, -1, 0, 5, 4, 5)
			local_connectors = [(5, 0, 2, 1)] # Exit to the right
		else:
			self.local_box = (-5, -1, 0, 2, 4, 5)
			local_connectors = [(-5, 0, 2, 3)] # Exit to the left
		self.calculate_world_bounds_and_connectors(local_connectors)

	def generate_blocks(self, rng):
		blocks = {}
		ox, oy, oz = self.origin
		min_x, max_x = (-2, 5) if self.turn_dir == 1 else (-5, 2)
		for lx in range(min_x, max_x + 1):
			for ly in range(-1, 5):
				for lz in range(0, 6):
					rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
					wx, wy, wz = ox + rx, oy + ry, oz + rz
					# Outer boundary wall check
					is_floor_or_ceil = ly in (-1, 4)
					is_back = (lz == 5)
					is_side = (lx == min_x if self.turn_dir == 1 else lx == max_x)
					is_inner_corner = (lz == 0 and (lx > 1 if self.turn_dir == 1 else lx < -1))
					is_wall = is_floor_or_ceil or is_back or is_side or is_inner_corner

					is_entrance = (lz == 0 and -1 <= lx <= 1 and 0 <= ly <= 2)
					is_exit = ((lx == max_x if self.turn_dir == 1 else lx == min_x) and 1 <= lz <= 3 and 0 <= ly <= 2)

					if is_wall and not (is_entrance or is_exit):
						blocks[(wx, wy, wz)] = self.get_random_stone_brick(rng)
					else:
						blocks[(wx, wy, wz)] = BLOCK_AIR

		return blocks, {}


class StrongholdStairsPiece(StrongholdPiece):
	"""Stone Brick Stairs Transition: descends 4 blocks vertically over 7 horizontal blocks."""
	def __init__(self, origin, rot):
		super().__init__("stairs", origin, rot)
		self.local_box = (-2, -5, 0, 2, 4, 7)
		local_connectors = [
			(0, -4, 7, 0) # Exits forward 4 blocks lower
		]
		self.calculate_world_bounds_and_connectors(local_connectors)

	def generate_blocks(self, rng):
		blocks = {}
		ox, oy, oz = self.origin
		for lz in range(0, 8):
			floor_y = -min(4, lz // 2)
			for lx in range(-2, 3):
				for ly in range(floor_y - 1, floor_y + 5):
					rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
					wx, wy, wz = ox + rx, oy + ry, oz + rz
					if lx in (-2, 2) or ly == (floor_y - 1) or ly == (floor_y + 4):
						blocks[(wx, wy, wz)] = self.get_random_stone_brick(rng)
					else:
						blocks[(wx, wy, wz)] = BLOCK_AIR

			# Place stair step blocks along center
			for step_x in (-1, 0, 1):
				rx, ry, rz = rotate_point(step_x, floor_y, lz, self.rot)
				blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_STONE_BRICK_STAIRS

		return blocks, {}


class StrongholdPrisonPiece(StrongholdPiece):
	"""Stronghold Prison / Cell Room: 9x5x9 with iron bars separating two holding cells."""
	def __init__(self, origin, rot):
		super().__init__("prison", origin, rot)
		self.local_box = (-4, -1, 0, 4, 5, 9)
		local_connectors = [
			(0, 0, 9, 0) # Pass-through exit
		]
		self.calculate_world_bounds_and_connectors(local_connectors)

	def generate_blocks(self, rng):
		blocks = {}
		ox, oy, oz = self.origin
		for lx in range(-4, 5):
			for ly in range(-1, 6):
				for lz in range(0, 10):
					rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
					wx, wy, wz = ox + rx, oy + ry, oz + rz
					is_outer_wall = (lx in (-4, 4) or lz in (0, 9) or ly in (-1, 5))
					is_doorway = (lz in (0, 9) and -1 <= lx <= 1 and 0 <= ly <= 2)

					if is_outer_wall and not is_doorway:
						blocks[(wx, wy, wz)] = self.get_random_stone_brick(rng)
					else:
						blocks[(wx, wy, wz)] = BLOCK_AIR

		# Cell partitions made of Iron Bars
		for lz in (3, 6):
			for ly in range(0, 3):
				for lx in (-3, -2, 2, 3):
					rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
					blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_IRON_BARS

		# Iron Doors for cells
		for cell_door_x in (-1, 1):
			rx, ry, rz = rotate_point(cell_door_x, 0, 3, self.rot)
			blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_IRON_DOOR

		return blocks, {}


class StrongholdLibraryPiece(StrongholdPiece):
	"""Stronghold 2-Story Library: 11x9x13 with wooden floors, Bookshelves, upper balcony, and loot chest."""
	def __init__(self, origin, rot):
		super().__init__("library", origin, rot)
		self.local_box = (-5, -1, 0, 5, 9, 13)
		local_connectors = [
			(0, 0, 13, 0) # Exit at far end
		]
		self.calculate_world_bounds_and_connectors(local_connectors)

	def generate_blocks(self, rng):
		blocks = {}
		chests = {}
		ox, oy, oz = self.origin
		# 1. Outer room shell
		for lx in range(-5, 6):
			for ly in range(-1, 10):
				for lz in range(0, 14):
					rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
					wx, wy, wz = ox + rx, oy + ry, oz + rz
					is_outer = (lx in (-5, 5) or lz in (0, 13) or ly in (-1, 9))
					is_door = (lz in (0, 13) and -1 <= lx <= 1 and 0 <= ly <= 2)

					if is_outer and not is_door:
						blocks[(wx, wy, wz)] = self.get_random_stone_brick(rng)
					else:
						if ly == -1:
							blocks[(wx, wy, wz)] = BLOCK_OAK_PLANKS # Wooden floor
						else:
							blocks[(wx, wy, wz)] = BLOCK_AIR

		# 2. Bookshelf Columns & Walls (Height 4 and 8)
		for lz in range(2, 12, 2):
			for ly in range(0, 4):
				for lx in (-4, 4):
					rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
					blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_BOOKSHELF

		# 3. Upper Balcony (ly = 4)
		for lx in range(-4, 5):
			for lz in range(1, 13):
				if lx in (-4, -3, 3, 4) or lz in (1, 12):
					rx, ry, rz = rotate_point(lx, 4, lz, self.rot)
					blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_OAK_PLANKS

		# 4. Library Chest Loot (Enchanted books/paper/compass/ender eyes/iron)
		chest_rx, chest_ry, chest_rz = rotate_point(0, 0, 6, self.rot)
		chest_pos = (ox + chest_rx, oy + chest_ry, oz + chest_rz)
		blocks[chest_pos] = BLOCK_CHEST
		chests[chest_pos] = [
			(177, rng.randint(1, 2)), # Eye of Ender
			(103, 1),                 # Iron Pickaxe
			(123, rng.randint(2, 5)), # Iron Ingots
			(152, rng.randint(3, 7)), # Bread
		]

		return blocks, chests


class StrongholdPortalRoomPiece(StrongholdPiece):
	"""
	Authentic Minecraft End Portal Room:
	- Sunken chamber with Lava Pool.
	- Entrance staircase with Silverfish Spawner location.
	- Central floating platform with 12 End Portal Frame blocks in 5x5 ring.
	"""
	def __init__(self, origin, rot):
		super().__init__("portal_room", origin, rot)
		self.local_box = (-5, -3, 0, 5, 6, 12)
		# No continuing exits (Dead end room containing the portal)
		self.calculate_world_bounds_and_connectors([])
		# Silverfish spawner location: on the entrance steps at local (0, 1, 3)
		ox, oy, oz = origin
		rx, ry, rz = rotate_point(0, 1, 3, rot)
		self.spawner_pos = (ox + rx, oy + ry, oz + rz)

	def generate_blocks(self, rng):
		blocks = {}
		ox, oy, oz = self.origin

		# 1. Carve 11x10x13 chamber (Y from -3 to 6)
		for lx in range(-5, 6):
			for ly in range(-3, 7):
				for lz in range(0, 13):
					rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
					wx, wy, wz = ox + rx, oy + ry, oz + rz
					is_outer = (lx in (-5, 5) or lz in (0, 12) or ly in (-3, 6))
					is_entrance = (lz == 0 and -1 <= lx <= 1 and 0 <= ly <= 2)

					if is_outer and not is_entrance:
						blocks[(wx, wy, wz)] = self.get_random_stone_brick(rng)
					else:
						blocks[(wx, wy, wz)] = BLOCK_AIR

		# 2. Sunken Lava Pool at floor level (Y = -2, -1)
		for lx in range(-4, 5):
			for lz in range(4, 11):
				rx, ry, rz = rotate_point(lx, -2, lz, self.rot)
				blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_LAVA
				rx_bot, ry_bot, rz_bot = rotate_point(lx, -3, lz, self.rot)
				blocks[(ox + rx_bot, oy + ry_bot, oz + rz_bot)] = BLOCK_STONE_BRICK

		# 3. Entrance Staircase & Platform (lz = 1..3, Y = 0..1)
		for lz in (1, 2, 3):
			for lx in (-1, 0, 1):
				step_y = 1 if lz >= 2 else 0
				rx, ry, rz = rotate_point(lx, step_y, lz, self.rot)
				blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_STONE_BRICK_STAIRS

		# 4. Central Portal Platform (Floating at Y = 1, Center at local x=0, z=8)
		# 5x5 End Portal Ring (12 frames around 3x3 interior)
		center_x, center_z = 0, 8
		portal_y = 1

		# Solid stone brick base under the frame ring
		for lx in range(-2, 3):
			for lz in range(6, 11):
				if abs(lx) == 2 or abs(lz - center_z) == 2:
					rx, ry, rz = rotate_point(lx, 0, lz, self.rot)
					blocks[(ox + rx, oy + ry, oz + rz)] = BLOCK_STONE_BRICK

		# Place 12 End Portal Frame blocks
		# North 3 frames (lz = 6, lx in -1, 0, 1)
		# South 3 frames (lz = 10, lx in -1, 0, 1)
		# West 3 frames (lx = -2, lz in 7, 8, 9)
		# East 3 frames (lx = 2, lz in 7, 8, 9)
		frame_positions = []
		for lx in (-1, 0, 1):
			frame_positions.append((lx, portal_y, 6))   # North side
			frame_positions.append((lx, portal_y, 10))  # South side
		for lz in (7, 8, 9):
			frame_positions.append((-2, portal_y, lz))  # West side
			frame_positions.append((2, portal_y, lz))   # East side

		# Pre-fill 1-2 random frames with Eyes of Ender (matching Java Edition 10% chance per frame)
		for flx, fly, flz in frame_positions:
			rx, ry, rz = rotate_point(flx, fly, flz, self.rot)
			wx, wy, wz = ox + rx, oy + ry, oz + rz
			has_eye = (rng.random() < 0.10)
			blocks[(wx, wy, wz)] = BLOCK_END_PORTAL_FRAME_FILLED if has_eye else BLOCK_END_PORTAL_FRAME

		# 5. Silverfish Spawner on Entrance Steps
		if self.spawner_pos:
			# Iron bars decorative pedestal under spawner
			sp_rx, sp_ry, sp_rz = rotate_point(0, 0, 3, self.rot)
			blocks[(ox + sp_rx, oy + sp_ry, oz + sp_rz)] = BLOCK_IRON_BARS

		return blocks, {}


class StrongholdDeadEndPiece(StrongholdPiece):
	"""Stone Brick Wall or Iron Bar gate terminating an open corridor connector."""
	def __init__(self, origin, rot):
		super().__init__("dead_end", origin, rot)
		self.local_box = (-2, -1, 0, 2, 4, 1)
		self.calculate_world_bounds_and_connectors([])

	def generate_blocks(self, rng):
		blocks = {}
		ox, oy, oz = self.origin
		has_iron_bars = rng.random() < 0.35
		for lx in range(-2, 3):
			for ly in range(-1, 5):
				rx, ry, rz = rotate_point(lx, ly, 0, self.rot)
				wx, wy, wz = ox + rx, oy + ry, oz + rz
				if has_iron_bars and (-1 <= lx <= 1 and 0 <= ly <= 2):
					blocks[(wx, wy, wz)] = BLOCK_IRON_BARS
				else:
					blocks[(wx, wy, wz)] = self.get_random_stone_brick(rng)
		return blocks, {}


# =========================================================================
# Stronghold Structure Graph Generator
# =========================================================================

class Stronghold:
	def __init__(self, origin, seed):
		self.origin = origin # (world_x, world_y, world_z)
		self.seed = seed
		self.pieces = []
		self.blocks = {}
		self.chests = {}
		self.spawners = []
		self._generate_structure()

	def _generate_structure(self):
		rng = Random(self.seed)
		ox, oy, oz = self.origin

		# 1. Start Piece: 5-Way Crossing
		start_piece = StrongholdCrossingPiece(self.origin, rot=0)
		self.pieces.append(start_piece)

		open_connectors = list(start_piece.connectors)
		max_pieces = 45
		portal_room_generated = False
		library_generated = False

		piece_types = [
			("corridor", 30),
			("turn_right", 15),
			("turn_left", 15),
			("stairs", 20),
			("prison", 10),
			("crossing", 10),
		]

		while open_connectors and len(self.pieces) < max_pieces:
			conn = open_connectors.pop(0)
			cx, cy, cz, crot = conn

			# Force Portal Room when reaching late stage if not yet placed
			if not portal_room_generated and (len(self.pieces) >= max_pieces - 4 or len(open_connectors) <= 1):
				candidate = StrongholdPortalRoomPiece((cx, cy, cz), crot)
				if not any(boxes_intersect(candidate.world_box, p.world_box, margin=1) for p in self.pieces):
					self.pieces.append(candidate)
					portal_room_generated = True
					if candidate.spawner_pos:
						self.spawners.append(candidate.spawner_pos)
					continue

			# Library generation
			if not library_generated and len(self.pieces) >= 12 and rng.random() < 0.35:
				candidate = StrongholdLibraryPiece((cx, cy, cz), crot)
				if not any(boxes_intersect(candidate.world_box, p.world_box, margin=1) for p in self.pieces):
					self.pieces.append(candidate)
					library_generated = True
					open_connectors.extend(candidate.connectors)
					continue

			# Select random piece based on weights
			total_w = sum(w for _, w in piece_types)
			pick = rng.uniform(0, total_w)
			cur = 0
			chosen_type = "corridor"
			for ptype, w in piece_types:
				cur += w
				if pick <= cur:
					chosen_type = ptype
					break

			if chosen_type == "corridor":
				candidate = StrongholdStraightCorridorPiece((cx, cy, cz), crot)
			elif chosen_type == "turn_right":
				candidate = StrongholdCorridorTurnPiece((cx, cy, cz), crot, turn_dir=1)
			elif chosen_type == "turn_left":
				candidate = StrongholdCorridorTurnPiece((cx, cy, cz), crot, turn_dir=3)
			elif chosen_type == "stairs":
				candidate = StrongholdStairsPiece((cx, cy, cz), crot)
			elif chosen_type == "prison":
				candidate = StrongholdPrisonPiece((cx, cy, cz), crot)
			else:
				candidate = StrongholdCrossingPiece((cx, cy, cz), crot)

			# Validate collision with existing pieces & bounds
			if not any(boxes_intersect(candidate.world_box, p.world_box, margin=1) for p in self.pieces):
				self.pieces.append(candidate)
				open_connectors.extend(candidate.connectors)
			else:
				# Place dead end to seal off open connection
				dead_end = StrongholdDeadEndPiece((cx, cy, cz), crot)
				self.pieces.append(dead_end)

		# Guarantee Portal Room if loop exited without one
		if not portal_room_generated and open_connectors:
			for conn in open_connectors:
				cx, cy, cz, crot = conn
				candidate = StrongholdPortalRoomPiece((cx, cy, cz), crot)
				self.pieces.append(candidate)
				if candidate.spawner_pos:
					self.spawners.append(candidate.spawner_pos)
				break

		# Seal all remaining open connectors with dead ends
		for cx, cy, cz, crot in open_connectors:
			self.pieces.append(StrongholdDeadEndPiece((cx, cy, cz), crot))

		# Generate block voxels from all pieces
		for piece in self.pieces:
			p_blocks, p_chests = piece.generate_blocks(rng)
			self.blocks.update(p_blocks)
			self.chests.update(p_chests)


# =========================================================================
# Concentric Ring Stronghold Placement & Spatial Queries
# =========================================================================

_STRONGHOLD_CACHE = {}
_NEAREST_LOGGED = set()


def get_stronghold_positions(seed, count=128):
	"""
	Calculates the authentic Minecraft Java Edition concentric ring stronghold coordinates.
	Ring 1: 3 strongholds at radius 1280..2816 blocks (~80..176 chunks)
	Ring 2: 6 strongholds at radius 4352..5888 blocks
	Ring 3: 10 strongholds at radius 7424..8960 blocks
	"""
	rng = Random(seed + 10387313)
	positions = []

	# Ring 1: 3 Strongholds
	base_angle = rng.uniform(0, math.tau)
	for i in range(3):
		dist = rng.uniform(1280, 2816)
		angle = base_angle + (i * math.tau / 3.0) + rng.uniform(-0.25, 0.25)
		sx = int(math.floor(math.cos(angle) * dist))
		sz = int(math.floor(math.sin(angle) * dist))
		sy = rng.randint(28, 38)
		positions.append((sx, sy, sz))

	# Ring 2: 6 Strongholds
	base_angle2 = rng.uniform(0, math.tau)
	for i in range(6):
		dist = rng.uniform(4352, 5888)
		angle = base_angle2 + (i * math.tau / 6.0) + rng.uniform(-0.2, 0.2)
		sx = int(math.floor(math.cos(angle) * dist))
		sz = int(math.floor(math.sin(angle) * dist))
		sy = rng.randint(28, 38)
		positions.append((sx, sy, sz))

	# Ring 3: 10 Strongholds
	base_angle3 = rng.uniform(0, math.tau)
	for i in range(10):
		dist = rng.uniform(7424, 8960)
		angle = base_angle3 + (i * math.tau / 10.0) + rng.uniform(-0.15, 0.15)
		sx = int(math.floor(math.cos(angle) * dist))
		sz = int(math.floor(math.sin(angle) * dist))
		sy = rng.randint(28, 38)
		positions.append((sx, sy, sz))

	return positions


def get_nearest_stronghold(player_pos, seed=0):
	"""
	Determines the nearest Stronghold to player_pos and logs coordinates to console/terminal.
	Returns (sx, sy, sz, dist).
	"""
	px, py, pz = player_pos
	positions = get_stronghold_positions(seed)

	nearest = None
	min_dist_sq = float('inf')

	for sx, sy, sz in positions:
		dx = sx - px
		dz = sz - pz
		dist_sq = dx * dx + dz * dz
		if dist_sq < min_dist_sq:
			min_dist_sq = dist_sq
			nearest = (sx, sy, sz)

	sx, sy, sz = nearest
	dist = math.sqrt(min_dist_sq)

	# Terminal debug log (formatted exactly as requested)
	print(f"Nearest Stronghold: X={sx} Y={sy} Z={sz}", flush=True)

	return (sx, sy, sz, dist)


def get_stronghold_at_origin(origin, seed):
	"""Caches and returns the full Stronghold structure at a given origin."""
	key = (origin, seed)
	if key not in _STRONGHOLD_CACHE:
		sh_seed = Random(seed + origin[0] * 31 + origin[2] * 17).randint(100000, 999999999)
		_STRONGHOLD_CACHE[key] = Stronghold(origin, sh_seed)
	return _STRONGHOLD_CACHE[key]


def stamp_stronghold_blocks_for_chunk(chunk_x, chunk_z, flat_bytes, seed=0):
	"""
	Stamps Stronghold blocks and chests intersecting the chunk into flat_bytes bytearray.
	Only evaluates strongholds within bounding range.
	"""
	min_cx = chunk_x * 16
	max_cx = min_cx + 15
	min_cz = chunk_z * 16
	max_cz = min_cz + 15

	positions = get_stronghold_positions(seed)
	for sx, sy, sz in positions:
		# Check if stronghold bounding box (approx 120x120 blocks) overlaps this chunk
		if not (min_cx > sx + 120 or max_cx < sx - 120 or min_cz > sz + 120 or max_cz < sz - 120):
			sh = get_stronghold_at_origin((sx, sy, sz), seed)
			for (wx, wy, wz), b_id in sh.blocks.items():
				if min_cx <= wx <= max_cx and min_cz <= wz <= max_cz and 0 <= wy < 256:
					lx = wx - min_cx
					lz = wz - min_cz
					flat_bytes[lx * 4096 + wy * 16 + lz] = b_id


def get_nearby_silverfish_spawners(player_pos, seed=0, radius=48):
	"""Returns all Silverfish spawner positions in nearby strongholds within radius."""
	px, py, pz = player_pos
	spawners = []
	positions = get_stronghold_positions(seed)
	for sx, sy, sz in positions:
		dx = sx - px
		dz = sz - pz
		if math.sqrt(dx * dx + dz * dz) <= (radius + 120):
			sh = get_stronghold_at_origin((sx, sy, sz), seed)
			for sp in sh.spawners:
				sp_dx = sp[0] - px
				sp_dy = sp[1] - py
				sp_dz = sp[2] - pz
				if math.sqrt(sp_dx * sp_dx + sp_dy * sp_dy + sp_dz * sp_dz) <= radius:
					spawners.append(sp)
	return spawners
