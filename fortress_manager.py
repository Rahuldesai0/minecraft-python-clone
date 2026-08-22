"""
Minecraft Java Edition Nether Fortress Generation & Mob Spawn System
---------------------------------------------------------------------
Implements authentic Minecraft Java Edition connected puzzle-piece Nether Fortresses:
- Open Sections: Bridges, Crossings, Platforms, Blaze Spawner platforms, Bridge Stairs, Gateways, End Capping.
- Closed Sections: Roofed Corridors, Turns, Crossings, Nether Wart Farm rooms, Balconies, Stairs.
- Fully connected graph generation with 3D AABB collision detection & bedrock bounds validation.
- Seamless chunk integration: stamps fortress voxels deterministically across chunk boundaries.
- Fortress Mob Spawn Region Index: fast AABB query for Blaze and Fortress Skeleton spawning eligibility.
- Nearest Fortress locator for debug & exploration.
"""

import math
import random
from random import Random

# Block IDs used in Nether Fortresses
BLOCK_AIR = 0
BLOCK_SOUL_SAND = 85
BLOCK_GLOWSTONE = 86
BLOCK_NETHER_BRICK = 90
BLOCK_NETHER_BRICK_FENCE = 91
BLOCK_NETHER_BRICK_STAIRS = 92
BLOCK_NETHER_WART = 94
BLOCK_NETHER_BRICK_SLAB = 95
BLOCK_LAVA = 15
BLOCK_FIRE = 78

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
		rotate_point(max_pt[0], min_pt[1], min_pt[2], rot),
		rotate_point(min_pt[0], max_pt[1], min_pt[2], rot),
		rotate_point(max_pt[0], max_pt[1], min_pt[2], rot),
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
# Fortress Piece Base & Concrete Variants
# =========================================================================

class FortressPiece:
	def __init__(self, piece_type, origin, rot, category="open"):
		self.piece_type = piece_type
		self.origin = origin  # (world_x, world_y, world_z)
		self.rot = rot        # 0, 1, 2, 3
		self.category = category # "open" or "closed"
		self.local_box = (-2, -1, 0, 2, 6, 8)
		self.world_box = (0, 0, 0, 0, 0, 0)
		self.connectors = [] # list of (world_x, world_y, world_z, exit_rot, target_category)
		self.is_spawner_area = False

	def calculate_world_bounds_and_connectors(self, local_connectors):
		ox, oy, oz = self.origin
		self.world_box = transform_box(self.local_box[:3], self.local_box[3:], self.origin, self.rot)
		self.connectors = []
		for lx, ly, lz, exit_rot_rel, cat in local_connectors:
			rx, ry, rz = rotate_point(lx, ly, lz, self.rot)
			abs_dir = (self.rot + exit_rot_rel) % 4
			self.connectors.append((ox + rx, oy + ry, oz + rz, abs_dir, cat))

	def get_blocks(self):
		"""Returns iterable of (world_x, world_y, world_z, block_id)."""
		return []


class BridgeStraightPiece(FortressPiece):
	"""Standard 19-block open Nether Brick bridge with fence railings and support pillars."""
	def __init__(self, origin, rot):
		super().__init__("bridge_straight", origin, rot, category="open")
		self.length = 19
		self.local_box = (-2, -1, 0, 2, 6, self.length)
		# Connection at far end
		local_conns = [(0, 0, self.length, 0, "open")]
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		for z in range(self.length):
			for x in range(-2, 3):
				rx, ry, rz = rotate_point(x, 0, z, self.rot)
				# Bridge floor
				blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))

				# Fence railings on left/right outer borders
				if x in (-2, 2):
					frx, fry, frz = rotate_point(x, 1, z, self.rot)
					blocks.append((ox + frx, oy + fry, oz + frz, BLOCK_NETHER_BRICK_FENCE))

				# Clear passage
				for y in range(1, 5):
					if x not in (-2, 2) or y > 1:
						crx, cry, crz = rotate_point(x, y, z, self.rot)
						blocks.append((ox + crx, oy + cry, oz + crz, BLOCK_AIR))

			# Support pillars under bridge every 6 blocks
			if z in (4, 14):
				for px in (-2, 2):
					for py in range(-1, -25, -1):
						prx, pry, prz = rotate_point(px, py, z, self.rot)
						blocks.append((ox + prx, oy + pry, oz + prz, BLOCK_NETHER_BRICK))

		return blocks


class BridgeCrossingPiece(FortressPiece):
	"""4-Way Open Bridge Crossing (Start piece of the Fortress). Size: 19x19."""
	def __init__(self, origin, rot):
		super().__init__("bridge_crossing", origin, rot, category="open")
		self.local_box = (-9, -2, -9, 9, 8, 9)
		# 4 exits: Forward (Z=+9, dir 0), Right (X=+9, dir 1), Backward (Z=-9, dir 2), Left (X=-9, dir 3)
		# Local offsets relative to center:
		# In local rot=0: forward is (0, 0, 9) in local space
		local_conns = [
			(0, 0, 9, 0, "open"),     # Forward exit
			(9, 0, 0, 1, "open"),     # Right exit
			(0, 0, -9, 2, "open"),    # Backward exit
			(-9, 0, 0, 3, "open")     # Left exit
		]
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		# 19x19 floor crossing
		for x in range(-9, 10):
			for z in range(-9, 10):
				is_walkway = (abs(x) <= 2) or (abs(z) <= 2)
				if is_walkway:
					rx, ry, rz = rotate_point(x, 0, z, self.rot)
					blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))

					# Clear air above
					for y in range(1, 6):
						arx, ary, arz = rotate_point(x, y, z, self.rot)
						blocks.append((ox + arx, oy + ary, oz + arz, BLOCK_AIR))

					# Fence railings on outer corners
					is_outer_edge = (abs(x) == 2 and abs(z) >= 3) or (abs(z) == 2 and abs(x) >= 3)
					if is_outer_edge:
						frx, fry, frz = rotate_point(x, 1, z, self.rot)
						blocks.append((ox + frx, oy + fry, oz + frz, BLOCK_NETHER_BRICK_FENCE))

		# Massive 4 corner pillars down to ground/lava
		for cx in (-3, 3):
			for cz in (-3, 3):
				for py in range(-1, -30, -1):
					prx, pry, prz = rotate_point(cx, py, cz, self.rot)
					blocks.append((ox + prx, oy + pry, oz + prz, BLOCK_NETHER_BRICK))

		return blocks


class BridgeStairsPiece(FortressPiece):
	"""Ascending Bridge Staircase elevating by +3 blocks."""
	def __init__(self, origin, rot):
		super().__init__("bridge_stairs", origin, rot, category="open")
		self.local_box = (-2, -1, 0, 2, 7, 10)
		local_conns = [(0, 3, 10, 0, "open")]
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		for z in range(10):
			step_y = min(3, z // 3)
			for x in range(-2, 3):
				# Floor & stairs
				for fy in range(0, step_y + 1):
					rx, ry, rz = rotate_point(x, fy, z, self.rot)
					blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))

				# Fence railings
				if x in (-2, 2):
					frx, fry, frz = rotate_point(x, step_y + 1, z, self.rot)
					blocks.append((ox + frx, oy + fry, oz + frz, BLOCK_NETHER_BRICK_FENCE))

				# Air clearance
				for ay in range(step_y + 1, step_y + 5):
					if x not in (-2, 2) or ay > step_y + 1:
						arx, ary, arz = rotate_point(x, ay, z, self.rot)
						blocks.append((ox + arx, oy + ary, oz + arz, BLOCK_AIR))
		return blocks


class SpawnerPlatformPiece(FortressPiece):
	"""Elevated Blaze Spawner Platform with fence railings, spawner pedestal & stairs."""
	def __init__(self, origin, rot):
		super().__init__("spawner_platform", origin, rot, category="open")
		self.local_box = (-5, -2, 0, 5, 8, 12)
		self.is_spawner_area = True
		# Spawner platforms are terminal points or branch endpoints
		local_conns = []
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_spawner_center(self):
		ox, oy, oz = self.origin
		rx, ry, rz = rotate_point(0, 3, 8, self.rot)
		return (ox + rx, oy + ry, oz + rz)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		# 1. Entrance stairs (Z=0..3, rising from Y=0 to Y=2)
		for z in range(4):
			sy = z // 2
			for x in range(-2, 3):
				for fy in range(0, sy + 1):
					rx, ry, rz = rotate_point(x, fy, z, self.rot)
					blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
				if x in (-2, 2):
					frx, fry, frz = rotate_point(x, sy + 1, z, self.rot)
					blocks.append((ox + frx, oy + fry, oz + frz, BLOCK_NETHER_BRICK_FENCE))
				for ay in range(sy + 1, sy + 5):
					if x not in (-2, 2) or ay > sy + 1:
						arx, ary, arz = rotate_point(x, ay, z, self.rot)
						blocks.append((ox + arx, oy + ary, oz + arz, BLOCK_AIR))

		# 2. Main 9x9 Spawner Platform (Z=4..12, X=-4..4, Y=2)
		for z in range(4, 13):
			for x in range(-4, 5):
				# Solid platform floor
				rx, ry, rz = rotate_point(x, 2, z, self.rot)
				blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))

				# Outer fence boundary
				if (abs(x) == 4 or z == 12) and not (z == 4 and abs(x) <= 2):
					frx, fry, frz = rotate_point(x, 3, z, self.rot)
					blocks.append((ox + frx, oy + fry, oz + frz, BLOCK_NETHER_BRICK_FENCE))

				# Clear air space for blazes to fly
				for y in range(3, 8):
					if (abs(x) != 4 and z != 12) or y > 3:
						arx, ary, arz = rotate_point(x, y, z, self.rot)
						blocks.append((ox + arx, oy + ary, oz + arz, BLOCK_AIR))

		# 3. Center Spawner Pedestal (X=0, Z=8, Y=3) & Glowstone lights
		crx, cry, crz = rotate_point(0, 3, 8, self.rot)
		blocks.append((ox + crx, oy + cry, oz + crz, BLOCK_NETHER_BRICK_FENCE))

		for gx, gz in ((-3, 5), (3, 5), (-3, 11), (3, 11)):
			rx, ry, rz = rotate_point(gx, 3, gz, self.rot)
			blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_GLOWSTONE))

		# 4. Support Pillars under the 4 corners of platform
		for px, pz in ((-4, 4), (4, 4), (-4, 12), (4, 12)):
			for py in range(1, -25, -1):
				rx, ry, rz = rotate_point(px, py, pz, self.rot)
				blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))

		return blocks


class BridgeGatePiece(FortressPiece):
	"""Transition Gateway between Open Bridge and Closed Roofed Corridor."""
	def __init__(self, origin, rot):
		super().__init__("bridge_gate", origin, rot, category="closed")
		self.local_box = (-2, -1, 0, 2, 6, 5)
		# Connects to closed corridor
		local_conns = [(0, 0, 5, 0, "closed")]
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		for z in range(5):
			for x in range(-2, 3):
				# Floor
				rx, ry, rz = rotate_point(x, 0, z, self.rot)
				blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))

				# Solid side walls
				if x in (-2, 2):
					for y in range(1, 5):
						wrx, wry, wrz = rotate_point(x, y, z, self.rot)
						blocks.append((ox + wrx, oy + wry, oz + wrz, BLOCK_NETHER_BRICK))
				else:
					# Air hallway
					for y in range(1, 5):
						arx, ary, arz = rotate_point(x, y, z, self.rot)
						blocks.append((ox + arx, oy + ary, oz + arz, BLOCK_AIR))

				# Roof
				rrx, rry, rrz = rotate_point(x, 5, z, self.rot)
				blocks.append((ox + rrx, oy + rry, oz + rrz, BLOCK_NETHER_BRICK))
		return blocks


class CorridorStraightPiece(FortressPiece):
	"""Standard 9-block enclosed roofed corridor."""
	def __init__(self, origin, rot):
		super().__init__("corridor_straight", origin, rot, category="closed")
		self.length = 9
		self.local_box = (-2, -1, 0, 2, 6, self.length)
		local_conns = [(0, 0, self.length, 0, "closed")]
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		for z in range(self.length):
			for x in range(-2, 3):
				# Floor
				rx, ry, rz = rotate_point(x, 0, z, self.rot)
				blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))

				# Solid Side Walls
				if x in (-2, 2):
					for y in range(1, 5):
						wrx, wry, wrz = rotate_point(x, y, z, self.rot)
						blocks.append((ox + wrx, oy + wry, oz + wrz, BLOCK_NETHER_BRICK))
				else:
					for y in range(1, 5):
						arx, ary, arz = rotate_point(x, y, z, self.rot)
						blocks.append((ox + arx, oy + ary, oz + arz, BLOCK_AIR))

				# Roof
				rrx, rry, rrz = rotate_point(x, 5, z, self.rot)
				blocks.append((ox + rrx, oy + rry, oz + rrz, BLOCK_NETHER_BRICK))
		return blocks


class CorridorCrossingPiece(FortressPiece):
	"""4-Way Enclosed Corridor Intersection (9x9)."""
	def __init__(self, origin, rot):
		super().__init__("corridor_crossing", origin, rot, category="closed")
		self.local_box = (-4, -1, 0, 4, 6, 8)
		local_conns = [
			(0, 0, 8, 0, "closed"),   # Forward
			(4, 0, 4, 1, "closed"),   # Right
			(-4, 0, 4, 3, "closed")   # Left
		]
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		for z in range(9):
			for x in range(-4, 5):
				# Floor & Roof
				rx, ry, rz = rotate_point(x, 0, z, self.rot)
				blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
				rrx, rry, rrz = rotate_point(x, 5, z, self.rot)
				blocks.append((ox + rrx, oy + rry, oz + rrz, BLOCK_NETHER_BRICK))

				# Wall columns on 4 outer corners
				is_corner_wall = (abs(x) >= 2 and (z <= 2 or z >= 6))
				for y in range(1, 5):
					wrx, wry, wrz = rotate_point(x, y, z, self.rot)
					if is_corner_wall:
						blocks.append((ox + wrx, oy + wry, oz + wrz, BLOCK_NETHER_BRICK))
					else:
						blocks.append((ox + wrx, oy + wry, oz + wrz, BLOCK_AIR))
		return blocks


class CorridorTurnPiece(FortressPiece):
	"""90-Degree Enclosed Corridor Corner Turn (Left or Right)."""
	def __init__(self, origin, rot, turn_dir="left"):
		super().__init__(f"corridor_turn_{turn_dir}", origin, rot, category="closed")
		self.turn_dir = turn_dir
		self.local_box = (-4, -1, 0, 4, 6, 7)
		exit_rot = 3 if turn_dir == "left" else 1
		exit_x = -4 if turn_dir == "left" else 4
		local_conns = [(exit_x, 0, 4, exit_rot, "closed")]
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		for z in range(7):
			for x in range(-4, 5):
				rx, ry, rz = rotate_point(x, 0, z, self.rot)
				blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
				rrx, rry, rrz = rotate_point(x, 5, z, self.rot)
				blocks.append((ox + rrx, oy + rry, oz + rrz, BLOCK_NETHER_BRICK))

				# Corner walls vs hallway opening
				if self.turn_dir == "left":
					is_wall = (x >= 2) or (z >= 6) or (x <= -2 and z <= 2) or (z <= 0 and x < -2)
				else:
					is_wall = (x <= -2) or (z >= 6) or (x >= 2 and z <= 2) or (z <= 0 and x > 2)

				for y in range(1, 5):
					wrx, wry, wrz = rotate_point(x, y, z, self.rot)
					if is_wall:
						blocks.append((ox + wrx, oy + wry, oz + wrz, BLOCK_NETHER_BRICK))
					else:
						blocks.append((ox + wrx, oy + wry, oz + wrz, BLOCK_AIR))
		return blocks


class NetherWartRoomPiece(FortressPiece):
	"""Nether Wart Farm room with Soul Sand beds, stairs & growing Nether Wart crops."""
	def __init__(self, origin, rot):
		super().__init__("nether_wart_room", origin, rot, category="closed")
		self.local_box = (-6, -4, 0, 6, 6, 13)
		# Stairs lead down, exit at back
		local_conns = [(0, -3, 13, 0, "closed")]
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		# 1. Entrance stairs descending from Y=0 down to Y=-3 (Z=0..3)
		for z in range(4):
			step_y = -(z)
			for x in range(-2, 3):
				for fy in range(-4, step_y + 1):
					rx, ry, rz = rotate_point(x, fy, z, self.rot)
					blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
				if x in (-2, 2):
					for wy in range(step_y + 1, 5):
						rx, ry, rz = rotate_point(x, wy, z, self.rot)
						blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
				for ay in range(step_y + 1, 5):
					if x not in (-2, 2):
						arx, ary, arz = rotate_point(x, ay, z, self.rot)
						blocks.append((ox + arx, oy + ary, oz + arz, BLOCK_AIR))

		# 2. Main Farm Room (Z=4..12, X=-5..5, Floor at Y=-3)
		for z in range(4, 13):
			for x in range(-5, 6):
				# Enclosing walls and roof
				is_outer_wall = (abs(x) == 5 or z == 12 and abs(x) > 2)

				for y in range(-4, 6):
					rx, ry, rz = rotate_point(x, y, z, self.rot)
					if y == -4:
						# Bedrock foundation floor
						blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
					elif y == 5:
						# Roof
						blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
					elif is_outer_wall:
						# Side walls
						blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
					elif y == -3:
						# Soul Sand farm beds on left (X=-4..-2) and right (X=2..4)
						if 2 <= abs(x) <= 4 and 5 <= z <= 11:
							blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_SOUL_SAND))
						else:
							blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
					elif y == -2:
						# Growing Nether Wart crops on top of Soul Sand
						if 2 <= abs(x) <= 4 and 5 <= z <= 11:
							blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_WART))
						else:
							blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_AIR))
					else:
						# Air clearance
						blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_AIR))

		return blocks


class BridgeEndPiece(FortressPiece):
	"""Ruined/capped terminal open bridge end with decorative arch."""
	def __init__(self, origin, rot):
		super().__init__("bridge_end", origin, rot, category="open")
		self.local_box = (-2, -1, 0, 2, 5, 3)
		local_conns = []
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		for z in range(3):
			for x in range(-2, 3):
				rx, ry, rz = rotate_point(x, 0, z, self.rot)
				blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
				if x in (-2, 2) or z == 2:
					frx, fry, frz = rotate_point(x, 1, z, self.rot)
					blocks.append((ox + frx, oy + fry, oz + frz, BLOCK_NETHER_BRICK_FENCE))
				for y in range(1, 4):
					if not (x in (-2, 2) and y == 1) and not (z == 2 and y == 1):
						arx, ary, arz = rotate_point(x, y, z, self.rot)
						blocks.append((ox + arx, oy + ary, oz + arz, BLOCK_AIR))
		return blocks


class CorridorEndPiece(FortressPiece):
	"""Solid wall terminal cap for dead-end enclosed corridors."""
	def __init__(self, origin, rot):
		super().__init__("corridor_end", origin, rot, category="closed")
		self.local_box = (-2, -1, 0, 2, 6, 2)
		local_conns = []
		self.calculate_world_bounds_and_connectors(local_conns)

	def get_blocks(self):
		ox, oy, oz = self.origin
		blocks = []
		for z in range(2):
			for x in range(-2, 3):
				# Floor & Roof
				rx, ry, rz = rotate_point(x, 0, z, self.rot)
				blocks.append((ox + rx, oy + ry, oz + rz, BLOCK_NETHER_BRICK))
				rrx, rry, rrz = rotate_point(x, 5, z, self.rot)
				blocks.append((ox + rrx, oy + rry, oz + rrz, BLOCK_NETHER_BRICK))

				for y in range(1, 5):
					wrx, wry, wrz = rotate_point(x, y, z, self.rot)
					if x in (-2, 2) or z == 1:
						blocks.append((ox + wrx, oy + wry, oz + wrz, BLOCK_NETHER_BRICK))
					else:
						blocks.append((ox + wrx, oy + wry, oz + wrz, BLOCK_AIR))
		return blocks


# =========================================================================
# Nether Fortress Connected Graph Generator
# =========================================================================

class NetherFortress:
	def __init__(self, origin_x, origin_y, origin_z, seed):
		self.origin = (origin_x, origin_y, origin_z)
		self.seed = seed
		self.pieces = []
		self.spawn_boxes = []
		self.spawner_pieces = []
		self.generate()

	def generate(self):
		rng = Random(self.seed)
		start_piece = BridgeCrossingPiece(self.origin, 0)
		self.pieces.append(start_piece)

		open_connectors = list(start_piece.connectors)
		rng.shuffle(open_connectors)

		max_pieces = rng.randint(32, 45)
		spawner_count = 0
		farm_count = 0

		while open_connectors and len(self.pieces) < max_pieces:
			conn = open_connectors.pop(0)
			cx, cy, cz, cdir, cat = conn

			# Pick candidate piece classes compatible with cat
			candidates = []
			if cat == "open":
				candidates.append((BridgeStraightPiece, 35))
				candidates.append((BridgeCrossingPiece, 15))
				candidates.append((BridgeStairsPiece, 10))
				candidates.append((BridgeGatePiece, 15)) # transition to closed corridor
				if spawner_count < 2 and len(self.pieces) > 8:
					candidates.append((SpawnerPlatformPiece, 20))
			else: # closed corridor
				candidates.append((CorridorStraightPiece, 35))
				candidates.append((CorridorCrossingPiece, 15))
				candidates.append((lambda o, r: CorridorTurnPiece(o, r, "left"), 15))
				candidates.append((lambda o, r: CorridorTurnPiece(o, r, "right"), 15))
				if farm_count < 2 and len(self.pieces) > 6:
					candidates.append((NetherWartRoomPiece, 20))

			# Weighted selection
			total_w = sum(w for _, w in candidates)
			r_val = rng.uniform(0, total_w)
			acc = 0
			selected_factory = candidates[0][0]
			for factory, w in candidates:
				acc += w
				if r_val <= acc:
					selected_factory = factory
					break

			candidate_piece = selected_factory((cx, cy, cz), cdir)

			# Check collision with existing pieces & bedrock boundaries
			c_box = candidate_piece.world_box
			is_valid = True

			# Bedrock boundary bounds (15 <= Y <= 112)
			if c_box[1] < 15 or c_box[4] > 112:
				is_valid = False

			if is_valid:
				for existing in self.pieces:
					if boxes_intersect(c_box, existing.world_box, margin=1):
						is_valid = False
						break

			if is_valid:
				self.pieces.append(candidate_piece)
				if candidate_piece.piece_type == "spawner_platform":
					spawner_count += 1
					self.spawner_pieces.append(candidate_piece)
				elif candidate_piece.piece_type == "nether_wart_room":
					farm_count += 1

				# Add new connectors
				new_conns = list(candidate_piece.connectors)
				rng.shuffle(new_conns)
				open_connectors.extend(new_conns)
			else:
				# Terminate open connector with an appropriate cap piece
				if cat == "open":
					cap = BridgeEndPiece((cx, cy, cz), cdir)
				else:
					cap = CorridorEndPiece((cx, cy, cz), cdir)
				self.pieces.append(cap)

		# Cap any remaining open connectors
		while open_connectors:
			cx, cy, cz, cdir, cat = open_connectors.pop(0)
			if cat == "open":
				cap = BridgeEndPiece((cx, cy, cz), cdir)
			else:
				cap = CorridorEndPiece((cx, cy, cz), cdir)
			self.pieces.append(cap)

		# Index all bounding boxes for fast mob spawn region queries
		self.spawn_boxes = [p.world_box for p in self.pieces]

	def is_inside_spawn_region(self, pos):
		"""Fast AABB check to see if pos (x, y, z) is inside any fortress piece."""
		x, y, z = pos
		for min_x, min_y, min_z, max_x, max_y, max_z in self.spawn_boxes:
			if min_x - 1 <= x <= max_x + 1 and min_y - 2 <= y <= max_y + 4 and min_z - 1 <= z <= max_z + 1:
				return True
		return False


# =========================================================================
# Global Fortress Manager & Spatial Registry
# =========================================================================

FORTRESS_GRID_SIZE = 480  # 1 Nether Fortress per 480x480 block region
_FORTRESS_CACHE = {}


def get_fortress_for_region(rx, rz, seed):
	"""Generates or retrieves the cached Nether Fortress for grid region (rx, rz)."""
	key = (rx, rz, seed)
	if key in _FORTRESS_CACHE:
		return _FORTRESS_CACHE[key]

	rng = Random((rx * 341873128712 + rz * 132897987541 + seed + 77713) & ((1 << 64) - 1))

	# Deterministic offset within the 480x480 region
	ox = rx * FORTRESS_GRID_SIZE + rng.randint(80, FORTRESS_GRID_SIZE - 120)
	oz = rz * FORTRESS_GRID_SIZE + rng.randint(80, FORTRESS_GRID_SIZE - 120)
	oy = rng.randint(58, 68)

	fortress_seed = rng.randint(100000, 999999999)
	fortress = NetherFortress(ox, oy, oz, fortress_seed)
	_FORTRESS_CACHE[key] = fortress
	return fortress


def get_nearby_fortresses(world_x, world_z, seed, radius_blocks=700):
	"""Returns all generated fortresses whose regions overlap the search radius."""
	min_rx = int(math.floor((world_x - radius_blocks) / float(FORTRESS_GRID_SIZE)))
	max_rx = int(math.floor((world_x + radius_blocks) / float(FORTRESS_GRID_SIZE)))
	min_rz = int(math.floor((world_z - radius_blocks) / float(FORTRESS_GRID_SIZE)))
	max_rz = int(math.floor((world_z + radius_blocks) / float(FORTRESS_GRID_SIZE)))

	fortresses = []
	for rx in range(min_rx, max_rx + 1):
		for rz in range(min_rz, max_rz + 1):
			fortresses.append(get_fortress_for_region(rx, rz, seed))
	return fortresses


def is_inside_fortress_spawn_region(pos, seed=0):
	"""Returns True if world position pos is inside a Nether Fortress bounding box."""
	px, py, pz = pos
	fortresses = get_nearby_fortresses(px, pz, seed, radius_blocks=300)
	for f in fortresses:
		if f.is_inside_spawn_region(pos):
			return True
	return False


def get_nearby_spawner_positions(pos, seed=0, radius=128):
	"""Returns list of (x, y, z) coordinates for all Blaze Spawner pedestals in nearby fortresses."""
	px, py, pz = pos
	results = []
	fortresses = get_nearby_fortresses(px, pz, seed=seed, radius_blocks=radius + 200)
	for fort in fortresses:
		for sp in fort.spawner_pieces:
			sc = sp.get_spawner_center()
			dist_sq = (sc[0] - px) ** 2 + (sc[2] - pz) ** 2
			if dist_sq <= radius * radius:
				results.append(sc)
	return results


def get_nearest_fortresses(player_pos, seed=0, count=3):
	"""Returns the count nearest fortresses to player_pos as list of (x, y, z, dist)."""
	px, py, pz = player_pos
	# Search in a 3x3 region grid around player
	curr_rx = int(math.floor(px / float(FORTRESS_GRID_SIZE)))
	curr_rz = int(math.floor(pz / float(FORTRESS_GRID_SIZE)))

	candidates = []
	for dx in range(-2, 3):
		for dz in range(-2, 3):
			f = get_fortress_for_region(curr_rx + dx, curr_rz + dz, seed)
			fx, fy, fz = f.origin
			dist = math.sqrt((fx - px) ** 2 + (fz - pz) ** 2)
			candidates.append((fx, fy, fz, dist))

	candidates.sort(key=lambda item: item[3])
	return candidates[:count]


def stamp_fortress_blocks_for_chunk(chunk_x, chunk_z, flat_bytes, seed=0):
	"""Stamps fortress blocks that intersect chunk (chunk_x, chunk_z) into flat_bytes bytearray."""
	min_cx = chunk_x * 16
	max_cx = min_cx + 15
	min_cz = chunk_z * 16
	max_cz = min_cz + 15

	fortresses = get_nearby_fortresses(min_cx, min_cz, seed, radius_blocks=250)

	for f in fortresses:
		for piece in f.pieces:
			bx0, by0, bz0, bx1, by1, bz1 = piece.world_box
			# Check AABB overlap with chunk column
			if bx1 < min_cx or bx0 > max_cx or bz1 < min_cz or bz0 > max_cz:
				continue

			for wx, wy, wz, b_id in piece.get_blocks():
				if min_cx <= wx <= max_cx and min_cz <= wz <= max_cz and 0 <= wy <= 127:
					lx = wx - min_cx
					lz = wz - min_cz
					idx = lx * 4096 + wy * 16 + lz
					flat_bytes[idx] = b_id
