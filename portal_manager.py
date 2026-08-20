"""
Minecraft Java Edition Nether Portal Manager & Dimension Linking Engine
------------------------------------------------------------------------
Implements authentic Minecraft Java Edition Nether Portal mechanics:
- Dynamic vertical rectangular Obsidian frame detection along X and Z axes
- Minimum 2x3 interior opening up to 21x21 custom frame sizes
- 4 corners are strictly optional (empty corners allowed)
- Instant invalidation of all connected portal blocks if required frame breaks
- 1:8 coordinate conversion (Overworld <-> Nether)
- Proximity portal search & bidirectional linking
- Automatic safe destination portal generation with 4x4 obsidian exit platform
"""

import math
import random

# Block IDs
OBSIDIAN = 24
FIRE = 78
PORTAL_X = 88
PORTAL_Z = 89
AIR = 0
BEDROCK = 14
LAVA = 15
WATER = 9


class PortalStructure:
	"""Represents an active connected Nether Portal structure in a dimension."""
	def __init__(self, dimension, axis, min_h, max_h, min_y, max_y, fixed_coord):
		self.dimension = dimension  # "overworld" or "nether"
		self.axis = axis            # "X" or "Z"
		self.min_h = min_h          # min_x if axis=="X" else min_z
		self.max_h = max_h          # max_x if axis=="X" else max_z
		self.min_y = min_y
		self.max_y = max_y
		self.fixed_coord = fixed_coord  # fixed z if axis=="X" else fixed x

	def get_interior_blocks(self):
		"""Returns list of (x, y, z) coordinates of all portal opening blocks."""
		blocks = []
		for h in range(self.min_h, self.max_h + 1):
			for y in range(self.min_y, self.max_y + 1):
				if self.axis == "X":
					blocks.append((h, y, self.fixed_coord))
				else:
					blocks.append((self.fixed_coord, y, h))
		return blocks

	def get_required_frame_blocks(self):
		"""Returns set of (x, y, z) coordinates of all required (non-corner) obsidian frame blocks."""
		frame = set()
		# Bottom & Top frame
		for h in range(self.min_h, self.max_h + 1):
			if self.axis == "X":
				frame.add((h, self.min_y - 1, self.fixed_coord))
				frame.add((h, self.max_y + 1, self.fixed_coord))
			else:
				frame.add((self.fixed_coord, self.min_y - 1, h))
				frame.add((self.fixed_coord, self.max_y + 1, h))
		# Left & Right frame
		for y in range(self.min_y, self.max_y + 1):
			if self.axis == "X":
				frame.add((self.min_h - 1, y, self.fixed_coord))
				frame.add((self.max_h + 1, y, self.fixed_coord))
			else:
				frame.add((self.fixed_coord, y, self.min_h - 1))
				frame.add((self.fixed_coord, y, self.max_h + 1))
		return frame

	def get_teleport_center(self):
		"""Returns (x, y, z) spawn coordinate inside the bottom of the portal."""
		center_h = (self.min_h + self.max_h) * 0.5 + 0.5
		if self.axis == "X":
			return (center_h, float(self.min_y), float(self.fixed_coord) + 0.5)
		else:
			return (float(self.fixed_coord) + 0.5, float(self.min_y), center_h)


class PortalManager:
	"""Global manager tracking all active Nether Portals across dimensions."""
	def __init__(self):
		self.portals = []  # List of PortalStructure instances

	def validate_portal_frame(self, world, click_pos):
		"""
		Validates if `click_pos` is inside a valid vertical rectangular Obsidian frame.
		Checks both X-axis and Z-axis orientations.
		Corners are optional. Minimum opening 2x3, Maximum 21x21.
		Returns PortalStructure if valid, or None.
		"""
		cx, cy, cz = click_pos
		curr_b = world.get_block_number((cx, cy, cz))
		if curr_b not in (AIR, FIRE, PORTAL_X, PORTAL_Z):
			return None

		# Test Axis 'X' (Fixed Z) and Axis 'Z' (Fixed X)
		for axis in ("X", "Z"):
			result = self._check_frame_axis(world, cx, cy, cz, axis)
			if result is not None:
				return result
		return None

	def _check_frame_axis(self, world, cx, cy, cz, axis):
		"""Helper checking a single axis orientation."""
		fixed = cz if axis == "X" else cx
		start_h = cx if axis == "X" else cz

		# 1. Find Horizontal Bounds of Opening at cy
		min_h = start_h
		while min_h > start_h - 22:
			test_pos = (min_h - 1, cy, fixed) if axis == "X" else (fixed, cy, min_h - 1)
			b = world.get_block_number(test_pos)
			if b == OBSIDIAN:
				break
			if b not in (AIR, FIRE, PORTAL_X, PORTAL_Z):
				return None
			min_h -= 1

		max_h = start_h
		while max_h < start_h + 22:
			test_pos = (max_h + 1, cy, fixed) if axis == "X" else (fixed, cy, max_h + 1)
			b = world.get_block_number(test_pos)
			if b == OBSIDIAN:
				break
			if b not in (AIR, FIRE, PORTAL_X, PORTAL_Z):
				return None
			max_h += 1

		width = max_h - min_h + 1
		if width < 2 or width > 21:
			return None

		# 2. Find Vertical Bounds of Opening
		min_y = cy
		while min_y > cy - 22:
			# Check entire row at min_y - 1
			all_obsidian = True
			all_open = True
			for h in range(min_h, max_h + 1):
				test_pos = (h, min_y - 1, fixed) if axis == "X" else (fixed, min_y - 1, h)
				b = world.get_block_number(test_pos)
				if b != OBSIDIAN:
					all_obsidian = False
				if b not in (AIR, FIRE, PORTAL_X, PORTAL_Z):
					all_open = False

			if all_obsidian:
				break
			if not all_open:
				return None
			min_y -= 1

		max_y = cy
		while max_y < cy + 22:
			# Check entire row at max_y + 1
			all_obsidian = True
			all_open = True
			for h in range(min_h, max_h + 1):
				test_pos = (h, max_y + 1, fixed) if axis == "X" else (fixed, max_y + 1, h)
				b = world.get_block_number(test_pos)
				if b != OBSIDIAN:
					all_obsidian = False
				if b not in (AIR, FIRE, PORTAL_X, PORTAL_Z):
					all_open = False

			if all_obsidian:
				break
			if not all_open:
				return None
			max_y += 1

		height = max_y - min_y + 1
		if height < 3 or height > 21:
			return None

		# 3. Verify Left and Right Frame Columns
		for y in range(min_y, max_y + 1):
			left_pos = (min_h - 1, y, fixed) if axis == "X" else (fixed, y, min_h - 1)
			right_pos = (max_h + 1, y, fixed) if axis == "X" else (fixed, y, max_h + 1)
			if world.get_block_number(left_pos) != OBSIDIAN or world.get_block_number(right_pos) != OBSIDIAN:
				return None

		# 4. Verify Entire Interior is Open
		for h in range(min_h, max_h + 1):
			for y in range(min_y, max_y + 1):
				pos = (h, y, fixed) if axis == "X" else (fixed, y, h)
				b = world.get_block_number(pos)
				if b not in (AIR, FIRE, PORTAL_X, PORTAL_Z):
					return None

		dimension = getattr(world, "dimension", "overworld")
		return PortalStructure(dimension, axis, min_h, max_h, min_y, max_y, fixed)

	def try_ignite_portal(self, world, click_pos):
		"""Attempts to ignite and fill a valid obsidian frame with portal blocks."""
		structure = self.validate_portal_frame(world, click_pos)
		if structure is None:
			return False

		portal_block_id = PORTAL_X if structure.axis == "X" else PORTAL_Z
		chunks_to_remesh = set()

		# Fill interior with Nether Portal blocks
		for pos in structure.get_interior_blocks():
			world.set_block(pos, portal_block_id)
			chunks_to_remesh.add((pos[0] >> 4, pos[2] >> 4))

		for cx, cz in chunks_to_remesh:
			world.queue_chunk_sections_for_meshing(cx, cz)

		# Register active portal structure
		self.portals.append(structure)
		return True

	def on_block_broken(self, world, broken_pos):
		"""
		Called when any block is broken.
		If a required obsidian frame block or portal block is broken, destroys the portal structure.
		"""
		i = 0
		dimension = getattr(world, "dimension", "overworld")
		while i < len(self.portals):
			portal = self.portals[i]
			if portal.dimension == dimension:
				req_frame = portal.get_required_frame_blocks()
				interior = portal.get_interior_blocks()

				if broken_pos in req_frame or broken_pos in interior:
					# Invalidate entire portal! Clear all interior portal blocks
					chunks_to_remesh = set()
					for pos in interior:
						if world.get_block_number(pos) in (PORTAL_X, PORTAL_Z):
							world.set_block(pos, AIR)
							chunks_to_remesh.add((pos[0] >> 4, pos[2] >> 4))

					for cx, cz in chunks_to_remesh:
						world.queue_chunk_sections_for_meshing(cx, cz)

					self.portals.pop(i)
					continue
			i += 1

	def find_closest_portal(self, target_world, target_xz, max_dist=128):
		"""Searches for the closest active portal in `target_world` near `target_xz`."""
		tx, tz = target_xz
		dimension = getattr(target_world, "dimension", "overworld")
		best_portal = None
		best_dist_sq = max_dist * max_dist

		for portal in self.portals:
			if portal.dimension == dimension:
				px, py, pz = portal.get_teleport_center()
				dx = px - tx
				dz = pz - tz
				dist_sq = dx * dx + dz * dz
				if dist_sq <= best_dist_sq:
					best_dist_sq = dist_sq
					best_portal = portal

		return best_portal

	def generate_destination_portal(self, target_world, target_xz):
		"""
		Generates an authentic 4x5 Obsidian Nether Portal with 2x3 opening and a safe
		4x4 obsidian exit platform in `target_world` near `target_xz`.
		"""
		tx, tz = int(math.floor(target_xz[0])), int(math.floor(target_xz[1]))
		dimension = getattr(target_world, "dimension", "overworld")

		# Find safe Y coordinate
		safe_y = 65
		if dimension == "nether":
			# Search in Nether between y=35 (above lava sea) and y=100 (below bedrock ceiling)
			found_y = None
			for y in range(36, 100):
				b = target_world.get_block_number((tx, y - 1, tz))
				if b != AIR and b not in (LAVA, WATER, BEDROCK):
					# Check 4 blocks of air clearance
					if all(target_world.get_block_number((tx, y + k, tz)) == AIR for k in range(4)):
						found_y = y
						break
			safe_y = found_y if found_y is not None else 50
		else:
			# Search in Overworld for top solid surface block
			found_y = None
			for y in range(120, 50, -1):
				b = target_world.get_block_number((tx, y - 1, tz))
				if b != AIR and b not in (LAVA, WATER):
					found_y = y
					break
			safe_y = found_y if found_y is not None else 65

		# Create standard 4x5 Obsidian Portal oriented along X-axis (Opening: tx..tx+1, safe_y..safe_y+2)
		min_x = tx
		max_x = tx + 1
		min_y = safe_y
		max_y = safe_y + 2
		cz = tz
		axis = "X"

		chunks_to_remesh = set()

		# 1. Generate Safe 4x4 Obsidian Walking Platform underneath and extending 2 blocks
		for px in range(min_x - 2, max_x + 3):
			for pz in range(cz - 2, cz + 3):
				target_world.set_block((px, min_y - 1, pz), OBSIDIAN)
				# Clear 3 blocks of air above platform for player exit clearance
				for py in range(min_y, min_y + 3):
					if (px < min_x - 1 or px > max_x + 1 or pz != cz):
						target_world.set_block((px, py, pz), AIR)
				chunks_to_remesh.add((px >> 4, pz >> 4))

		# 2. Generate Obsidian Portal Frame (4 wide x 5 high)
		# Bottom frame
		target_world.set_block((min_x, min_y - 1, cz), OBSIDIAN)
		target_world.set_block((max_x, min_y - 1, cz), OBSIDIAN)
		# Top frame
		target_world.set_block((min_x, max_y + 1, cz), OBSIDIAN)
		target_world.set_block((max_x, max_y + 1, cz), OBSIDIAN)
		# Left column
		for y in range(min_y, max_y + 1):
			target_world.set_block((min_x - 1, y, cz), OBSIDIAN)
		# Right column
		for y in range(min_y, max_y + 1):
			target_world.set_block((max_x + 1, y, cz), OBSIDIAN)

		# 3. Fill Interior with Nether Portal blocks
		portal_block = PORTAL_X if axis == "X" else PORTAL_Z
		for x in range(min_x, max_x + 1):
			for y in range(min_y, max_y + 1):
				target_world.set_block((x, y, cz), portal_block)
				chunks_to_remesh.add((x >> 4, cz >> 4))

		for rcx, rcz in chunks_to_remesh:
			target_world.queue_chunk_sections_for_meshing(rcx, rcz)

		# Register new portal structure
		new_portal = PortalStructure(dimension, axis, min_x, max_x, min_y, max_y, cz)
		self.portals.append(new_portal)
		return new_portal


# Global Singleton Portal Manager
portal_manager = PortalManager()
