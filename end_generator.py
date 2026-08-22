"""
End Dimension World Generator (Minecraft Java Edition)
------------------------------------------------------
Procedurally generates the authentic End dimension:
1. Central End Island (End Stone, 3D noise tapering into the void)
2. Central Obsidian Spawn Platform at (100, 48, 0)
3. 10 Obsidian Pillars (Heights 76..103, radius 43 ring, End Crystal mounts, Iron cages)
4. Central Exit Bedrock Fountain at (0, Y, 0)
"""

import math
import random

# Block IDs
BLOCK_AIR = 0
BLOCK_BEDROCK = 14
BLOCK_TORCH = 33
BLOCK_OBSIDIAN = 24
BLOCK_IRON_BARS = 99
BLOCK_END_PORTAL = 183
BLOCK_END_STONE = 188
BLOCK_DRAGON_EGG = 189

# 10 Obsidian Pillars layout (radius 43 blocks from (0, 0))
PILLAR_HEIGHTS = [76, 79, 82, 85, 88, 91, 94, 97, 100, 103]
PILLAR_RADIUS = 43.0


def get_pillar_definitions():
	"""
	Returns list of dicts for the 10 obsidian pillars:
	[{'index': i, 'x': x, 'z': z, 'height': h, 'radius': r, 'has_cage': bool, 'crystal_pos': (x, h+1, z)}]
	"""
	pillars = []
	for i in range(10):
		angle = i * (math.tau / 10.0)
		px = int(round(math.cos(angle) * PILLAR_RADIUS))
		pz = int(round(math.sin(angle) * PILLAR_RADIUS))
		h = PILLAR_HEIGHTS[i]
		# Pillars with cages in Java Edition (heights 85 and 97)
		has_cage = (h in (85, 97))
		radius = 3.2 if (i % 2 == 0) else 2.5
		pillars.append({
			'index': i,
			'x': px,
			'z': pz,
			'height': h,
			'radius': radius,
			'has_cage': has_cage,
			'crystal_pos': (px + 0.5, h + 1.0, pz + 0.5)
		})
	return pillars


def get_island_height_range(x, z, seed=0):
	"""
	Calculates the top surface Y and bottom underside Y of the main End island at (x, z).
	Returns (y_bottom, y_top) or None if in void.
	"""
	dist = math.sqrt(x * x + z * z)
	if dist > 145.0:
		return None

	# Smooth radial falloff factor (1.0 at center -> 0.0 at radius 130)
	rad_factor = max(0.0, 1.0 - (dist / 135.0))
	if rad_factor <= 0.001:
		return None

	# Procedural multi-frequency undulation
	n1 = math.sin(x * 0.035 + seed * 0.1) * math.cos(z * 0.035 + seed * 0.1)
	n2 = math.sin(x * 0.08 - z * 0.06) * 0.5 + math.cos(x * 0.06 + z * 0.08) * 0.5
	n3 = math.sin(x * 0.15) * math.cos(z * 0.15) * 0.25

	surface_undulation = (n1 * 4.0 + n2 * 2.5 + n3 * 1.5) * rad_factor
	y_top = int(round(60.0 + surface_undulation + (rad_factor * 5.0)))

	# Bottom underside bowl
	underside_thick = 22.0 * (rad_factor ** 1.3)
	y_bottom = max(30, int(round(y_top - underside_thick)))

	if y_bottom >= y_top:
		return None

	return (y_bottom, y_top)


def get_spawn_platform_y(seed=0):
	"""Returns the surface Y level for the Obsidian spawn platform at (100, 0)."""
	h_range = get_island_height_range(100, 0, seed)
	if h_range:
		return h_range[1]
	return 48


def get_fountain_y(seed=0):
	"""Returns the surface Y level for the Central Exit Bedrock Fountain at (0, 0)."""
	h_range = get_island_height_range(0, 0, seed)
	if h_range:
		return h_range[1]
	return 60


class EndDimensionGenerator:
	def __init__(self, seed=0):
		self.seed = seed
		self.pillars = get_pillar_definitions()
		self.dragon_defeated = False

	def get_crystal_spawn_positions(self):
		return [p['crystal_pos'] for p in self.pillars]

	def stamp_chunk_blocks(self, chunk_x, chunk_z, flat_bytes):
		"""
		Fills flat_bytes (16x256x16 bytearray) with End terrain, spawn platform, pillars, and fountain.
		Obsidian platform and Bedrock fountain are stamped AFTER terrain so they dynamically sit on the surface.
		"""
		min_wx = chunk_x * 16
		max_wx = min_wx + 15
		min_wz = chunk_z * 16
		max_wz = min_wz + 15

		# 1. Main End Island Terrain (End Stone)
		for lx in range(16):
			wx = min_wx + lx
			for lz in range(16):
				wz = min_wz + lz
				h_range = get_island_height_range(wx, wz, self.seed)
				if h_range:
					y_bot, y_top = h_range
					for wy in range(y_bot, y_top + 1):
						flat_bytes[lx * 4096 + wy * 16 + lz] = BLOCK_END_STONE

		# 2. Central Obsidian Spawn Platform - Dynamically generated ON the surface at (100, 0)
		plat_y = get_spawn_platform_y(self.seed)
		if not (min_wx > 102 or max_wx < 98 or min_wz > 2 or max_wz < -2):
			for wx in range(98, 103):
				if min_wx <= wx <= max_wx:
					lx = wx - min_wx
					for wz in range(-2, 3):
						if min_wz <= wz <= max_wz:
							lz = wz - min_wz
							# Obsidian platform layer on surface
							flat_bytes[lx * 4096 + plat_y * 16 + lz] = BLOCK_OBSIDIAN
							# Clear air clearance above platform (plat_y+1 .. plat_y+4)
							for cy in range(plat_y + 1, min(256, plat_y + 5)):
								flat_bytes[lx * 4096 + cy * 16 + lz] = BLOCK_AIR

		# 3. 10 Obsidian Pillars
		for p in self.pillars:
			px, pz, ph, pr, has_cage = p['x'], p['z'], p['height'], p['radius'], p['has_cage']
			# Check bounding overlap
			pr_int = int(math.ceil(pr))
			if not (min_wx > px + pr_int + 2 or max_wx < px - pr_int - 2 or min_wz > pz + pr_int + 2 or max_wz < pz - pr_int - 2):
				for wx in range(px - pr_int, px + pr_int + 1):
					if min_wx <= wx <= max_wx:
						lx = wx - min_wx
						for wz in range(pz - pr_int, pz + pr_int + 1):
							if min_wz <= wz <= max_wz:
								lz = wz - min_wz
								dx = wx - px
								dz = wz - pz
								if (dx * dx + dz * dz) <= (pr * pr):
									# Pillar column from Y=40 up to ph
									for wy in range(40, ph + 1):
										flat_bytes[lx * 4096 + wy * 16 + lz] = BLOCK_OBSIDIAN
									# Pillar top Bedrock mount block at center
									if dx == 0 and dz == 0:
										flat_bytes[lx * 4096 + ph * 16 + lz] = BLOCK_BEDROCK

								# Iron bars cage on top if specified
								if has_cage:
									if abs(dx) <= 2 and abs(dz) <= 2:
										for cy in range(ph + 1, ph + 4):
											is_border = (abs(dx) == 2 or abs(dz) == 2 or cy == ph + 3)
											if is_border:
												flat_bytes[lx * 4096 + cy * 16 + lz] = BLOCK_IRON_BARS

		# 4. Central Bedrock Exit Fountain - Dynamically generated ON the surface at (0, 0)
		fount_y = get_fountain_y(self.seed)
		if not (min_wx > 4 or max_wx < -4 or min_wz > 4 or max_wz < -4):
			for wx in range(-3, 4):
				if min_wx <= wx <= max_wx:
					lx = wx - min_wx
					for wz in range(-3, 4):
						if min_wz <= wz <= max_wz:
							lz = wz - min_wz
							dist_sq = wx * wx + wz * wz
							# Bedrock rim / basin base
							if dist_sq <= 8:
								# Floor of the basin
								flat_bytes[lx * 4096 + fount_y * 16 + lz] = BLOCK_BEDROCK
								# Outer rim
								if dist_sq >= 5:
									flat_bytes[lx * 4096 + (fount_y + 1) * 16 + lz] = BLOCK_BEDROCK
								else:
									# Basin interior
									portal_b = BLOCK_END_PORTAL if self.dragon_defeated else BLOCK_AIR
									flat_bytes[lx * 4096 + (fount_y + 1) * 16 + lz] = portal_b
								# Clear air above fountain
								for cy in range(fount_y + 2, min(256, fount_y + 6)):
									flat_bytes[lx * 4096 + cy * 16 + lz] = BLOCK_AIR

							# Center Bedrock Pillar (Height 3)
							if wx == 0 and wz == 0:
								flat_bytes[lx * 4096 + (fount_y + 1) * 16 + lz] = BLOCK_BEDROCK
								flat_bytes[lx * 4096 + (fount_y + 2) * 16 + lz] = BLOCK_BEDROCK
								flat_bytes[lx * 4096 + (fount_y + 3) * 16 + lz] = BLOCK_BEDROCK
								if self.dragon_defeated:
									flat_bytes[lx * 4096 + (fount_y + 4) * 16 + lz] = BLOCK_DRAGON_EGG


# Global Singleton End Dimension Generator
end_generator = EndDimensionGenerator(seed=0)
