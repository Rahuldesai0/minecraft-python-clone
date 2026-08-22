import math
import time
import collections
from random import Random
from noise import *
import threading
import gzip
import os
import array
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pyglet.gl as gl

import chunk
import block_type
import texture_manager

# Import custom block models
import models.leaves
import models.liquid
import models.plant
import models.cactus
import models.slab
import models.stairs
import models.stairs_top
import models.door
import models.door_open
import models.door_top
import models.door_top_open
import models.trapdoor
import models.trapdoor_open
import models.trapdoor_top
import models.trapdoor_top_open
import models.fence
import models.wall
import models.glass_pane
import models.fence_gate
import models.fence_gate_open
import models.portal_x
import models.portal_z
import models.end_portal_frame
import models.end_portal
import models.iron_bars

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'save', 'chunks')
MAX_RENDER_DISTANCE = 32

_RING_OFFSETS_CACHE = {}

def get_ring_offsets(rd):
	if rd not in _RING_OFFSETS_CACHE:
		offsets = []
		for dx in range(-rd, rd + 1):
			for dz in range(-rd, rd + 1):
				offsets.append((dx * dx + dz * dz, dx, dz))
		offsets.sort(key=lambda item: item[0])
		_RING_OFFSETS_CACHE[rd] = [(dx, dz) for _, dx, dz in offsets]
	return _RING_OFFSETS_CACHE[rd]

RING_OFFSETS = get_ring_offsets(MAX_RENDER_DISTANCE)


def build_chunk_blocks_process(x, z, scale, octaves, persistence, lacunarity, cave_scale, cave_threshold, save_dir, seed=0):
	"""Independent worker function for ProcessPoolExecutor.
	Generates authentic Minecraft 1.0 style terrain directly into a flat 1D bytearray (65536 bytes)."""
	save_path = os.path.join(save_dir, f"{x}_{z}.chunk")
	if os.path.exists(save_path):
		try:
			with gzip.open(save_path, 'rb') as f:
				data = f.read()
			if len(data) >= chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH:
				return data
		except Exception:
			pass

	flat_bytes = bytearray(chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH)

	seed_offset_x = float((seed * 10007) % 50000)
	seed_offset_z = float((seed * 16007) % 50000)

	rng = Random((x * 341873128712 + z * 132897987541 + seed) & ((1 << 64) - 1))
	surface_heights = [0] * 256  # 16x16 column surface heights

	chunk_offset_x = x * chunk.CHUNK_WIDTH
	chunk_offset_z = z * chunk.CHUNK_LENGTH

	# 1. Heightmap Calculation (Minecraft Java Edition Mean Surface & Biome Scaling)
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i + seed_offset_x
			wz = chunk_offset_z + k + seed_offset_z

			cont = pnoise2(wx / 350.0, wz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)
			peaks_raw = pnoise2((wx + 1000.0) / 85.0, (wz + 1000.0) / 85.0, octaves=4, persistence=0.5, lacunarity=2.0)
			ridge = 1.0 - abs(peaks_raw * 2.0)

			if cont < -0.32:
				# Deep Ocean & Ocean basin
				t = max(0.0, min(1.0, (cont - (-0.50)) / 0.18))
				smooth_t = 3.0 * t * t - 2.0 * t * t * t
				target_y = 38.0 + smooth_t * 16.0 + (peaks_raw * 1.5)
			elif cont < -0.22:
				# Narrow Coastal / Shoreline Transition & Beaches
				t = (cont - (-0.32)) / 0.10
				smooth_t = 3.0 * t * t - 2.0 * t * t * t
				target_y = 54.0 + smooth_t * 10.0 + (ridge * 1.5)
			else:
				# Vast Continents: Plains, Forests & Lowlands (Mean Surface ~66-68)
				t = min(1.0, (cont - (-0.22)) / 0.50)
				smooth_t = 3.0 * t * t - 2.0 * t * t * t
				target_y = 65.0 + smooth_t * 6.0 + (ridge * 2.0)

				# Occasional Standalone Mountain Clusters (3 to 4 Peaks & Semi-Ridges)
				mtn_mask = pnoise2((wx + 5000.0) / 450.0, (wz + 5000.0) / 450.0, octaves=1)
				if mtn_mask > 0.36:
					t_mtn = min(1.0, (mtn_mask - 0.36) / 0.10)
					smooth_mtn = 3.0 * t_mtn * t_mtn - 2.0 * t_mtn * t_mtn * t_mtn
					peak_noise = pnoise2((wx + 1000.0) / 60.0, (wz + 1000.0) / 60.0, octaves=1)
					semi_ridge = 1.0 - abs(peak_noise * 1.5)
					summit = max(0.0, semi_ridge) ** 1.4
					mtn_height = (smooth_mtn * 14.0) + (smooth_mtn * summit * 32.0)
					target_y += mtn_height

			river_raw = abs(pnoise2((wx + 2000.0) / 240.0, (wz + 2000.0) / 240.0, octaves=3))
			if river_raw < 0.028:
				t_r = 1.0 - (river_raw / 0.028)
				r_blend = (t_r * t_r) * 3.0
				target_y = min(target_y, 61.0 - r_blend)

			sculpt = pnoise3(wx / 25.0, target_y / 15.0, wz / 25.0) * 2.0
			final_y = math.floor(target_y + sculpt)
			final_y = max(4, min(final_y, chunk.CHUNK_HEIGHT - 6))
			surface_heights[i * 16 + k] = final_y

	# Helper for flat 1D indexing into flat_bytes
	def set_b(i, j, k, val):
		flat_bytes[i * 4096 + j * 16 + k] = val

	def get_b(i, j, k):
		return flat_bytes[i * 4096 + j * 16 + k]

	# 2. Fill Solid Terrain, Surface Layers & Sea Water (Sea Level = 63)
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i
			wz = chunk_offset_z + k
			sy = surface_heights[i * 16 + k]

			set_b(i, 0, k, 14)  # Bedrock

			sub_depth = max(1, sy - 3)
			for j in range(1, sub_depth):
				block_num = 5  # Stone
				if 30 <= j and rng.randrange(100) < 4:
					block_num = 16  # Coal Ore
				elif 10 <= j <= 50 and rng.randrange(100) < 2:
					block_num = 17  # Iron Ore
				elif 2 <= j <= 15 and rng.randrange(1000) < 3:
					block_num = 18  # Diamond Ore
				elif 15 <= j <= 65 and rng.randrange(100) < 3:
					block_num = 77  # Gravel pocket
				set_b(i, j, k, block_num)

			cont = pnoise2(wx / 350.0, wz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)
			river_raw = abs(pnoise2((wx + 2000.0) / 240.0, (wz + 2000.0) / 240.0, octaves=3))
			is_river = river_raw < 0.028
			gravel_noise = pnoise2((wx + 4500.0) / 22.0, (wz + 4500.0) / 22.0, octaves=2)

			if sy > 105:
				for j in range(sub_depth, sy):
					set_b(i, j, k, 5)
				set_b(i, sy, k, 2)
			elif sy > 85:
				for j in range(sub_depth, sy + 1):
					set_b(i, j, k, 5)
			elif sy < 63:
				# Ocean, deep sea, and riverbed generation with natural Gravel, Sand, and Dirt patches
				if gravel_noise > 0.12:
					underwater_mat = 77  # Gravel patch
				elif cont < -0.22 or (cont < -0.15 and sy < 58):
					underwater_mat = 6   # Sand patch
				else:
					underwater_mat = 4   # Dirt floor

				for j in range(sub_depth, sy + 1):
					set_b(i, j, k, underwater_mat)
			elif cont < -0.15 and not is_river:
				# Beach sand & occasional gravel beaches
				beach_mat = 77 if gravel_noise > 0.38 else 6
				for j in range(sub_depth, sy + 1):
					set_b(i, j, k, beach_mat)
			else:
				for j in range(sub_depth, sy):
					set_b(i, j, k, 4)
				set_b(i, sy, k, 2)

			if sy < 63:
				for water_y in range(sy + 1, 64):
					set_b(i, water_y, k, 9)

	# 3. Carve 3D Caves (Worm tunnels, chambers, surface openings, and ravines)
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i
			wz = chunk_offset_z + k
			sy = surface_heights[i * 16 + k]

			entrance_noise = pnoise2((wx + 8000.0) / 90.0, (wz + 8000.0) / 90.0)
			ravine_raw = abs(pnoise2((wx + 5500.0) / 60.0, (wz + 5500.0) / 60.0))
			is_surface_open = (entrance_noise > 0.18) and (sy >= 64)
			is_ravine = (ravine_raw < 0.020) and (entrance_noise > -0.05) and (sy >= 64)

			if sy <= 63:
				max_cave_y = min(sy - 5, 52)
			else:
				max_cave_y = min(sy + 1 if (is_surface_open or is_ravine) else sy - 4, 115)

			for j in range(9, max_cave_y):
				if get_b(i, j, k) == 14:  # Bedrock
					continue

				c1 = pnoise3(wx / 22.0, j / 12.0, wz / 22.0)
				c2 = pnoise3((wx + 400.0) / 22.0, j / 12.0, (wz + 400.0) / 22.0)
				cheese = pnoise3((wx - 200.0) / 32.0, j / 20.0, (wz - 200.0) / 32.0)

				# Dynamic threshold expanding near surface opening
				tunnel_thresh = 0.0070
				if is_surface_open and j >= sy - 8:
					tunnel_thresh = 0.0130  # Wider tunnel breaches out of hillside

				is_tunnel = (c1 * c1 + c2 * c2) < tunnel_thresh
				is_chamber = (cheese > 0.52 and j < 55)
				is_ravine_cut = is_ravine and (22 <= j <= sy + 1)

				if is_tunnel or is_chamber or is_ravine_cut:
					set_b(i, j, k, 0)

	# 4. Lava Oceans in Deep Caves (y <= 10)
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			for j in range(1, 11):
				if get_b(i, j, k) == 0:
					set_b(i, j, k, 15)

	# 5. Underground Cave Lava Lakes & Water Pools (Probability of lava increases with lower Y)
	if rng.randrange(100) < 65:
		for _ in range(rng.randrange(1, 4)):
			pool_lx = rng.randrange(3, chunk.CHUNK_WIDTH - 3)
			pool_lz = rng.randrange(3, chunk.CHUNK_LENGTH - 3)
			
			found_y = None
			for check_y in range(11, 52):
				if get_b(pool_lx, check_y, pool_lz) == 0 and get_b(pool_lx, check_y - 1, pool_lz) in (5, 1, 16, 17, 18, 77):
					found_y = check_y
					break

			if found_y is not None:
				pool_ly = found_y
				# Probability of lava increases with lower Y:
				# Y=11..18 -> ~90% lava. Y=25 -> ~65% lava. Y=40 -> ~28% lava. Y=50 -> ~5% lava.
				lava_prob = max(0.05, min(0.92, 1.0 - ((pool_ly - 10.0) / 42.0)))
				liquid_type = 15 if (rng.random() < lava_prob) else 9

				lake_rad = rng.randrange(2, 5)
				for dx in range(-lake_rad, lake_rad + 1):
					for dz in range(-lake_rad, lake_rad + 1):
						dist_sq = dx * dx + dz * dz
						px = pool_lx + dx
						pz = pool_lz + dz
						if 0 <= px < chunk.CHUNK_WIDTH and 0 <= pz < chunk.CHUNK_LENGTH:
							if dist_sq <= lake_rad * lake_rad:
								set_b(px, pool_ly, pz, liquid_type)
								set_b(px, pool_ly - 1, pz, liquid_type)
								floor_mat = 24 if (liquid_type == 15 and rng.random() < 0.25) else 5
								set_b(px, pool_ly - 2, pz, floor_mat)
							elif dist_sq <= (lake_rad + 1) * (lake_rad + 1):
								for ry in range(pool_ly - 1, pool_ly + 2):
									if get_b(px, ry, pz) == 0:
										set_b(px, ry, pz, 5)  # Regular stone (5) border

	# 6. Surface Water Lakes (Carved & filled at a single uniform Y level, 100% bounded by solid dirt/stone retaining walls)
	if rng.randrange(100) < 40:
		lake_cx = rng.randrange(3, chunk.CHUNK_WIDTH - 3)
		lake_cz = rng.randrange(3, chunk.CHUNK_LENGTH - 3)
		radius = rng.randrange(3, 6)
		sample_heights = []

		for dx in range(-radius - 1, radius + 2):
			for dz in range(-radius - 1, radius + 2):
				px, pz = lake_cx + dx, lake_cz + dz
				if 0 <= px < chunk.CHUNK_WIDTH and 0 <= pz < chunk.CHUNK_LENGTH:
					sample_heights.append(surface_heights[px * 16 + pz])

		if sample_heights:
			min_h = min(sample_heights)
			max_h = max(sample_heights)

			if (max_h - min_h <= 3) and (min_h >= 62):
				lake_surface_y = min_h  # Single uniform flat surface height for entire lake

				for dx in range(-radius - 1, radius + 2):
					for dz in range(-radius - 1, radius + 2):
						dist_sq = dx * dx + dz * dz
						px, pz = lake_cx + dx, lake_cz + dz
						if 0 <= px < chunk.CHUNK_WIDTH and 0 <= pz < chunk.CHUNK_LENGTH:
							col_h = surface_heights[px * 16 + pz]

							if dist_sq <= radius * radius:
								# Clear terrain blocks above lake surface to keep lake open to sky
								for cy in range(lake_surface_y + 1, col_h + 1):
									set_b(px, cy, pz, 0)

								# Perfectly flat water surface
								set_b(px, lake_surface_y, pz, 9)       # Water source top
								set_b(px, lake_surface_y - 1, pz, 9)   # Water source in body
								
								# Basin floor with Gravel patches, Dirt, Sand, and Stone
								gx = chunk_offset_x + px
								gz = chunk_offset_z + pz
								pond_gravel = pnoise2((gx + 1200.0) / 12.0, (gz + 1200.0) / 12.0)
								if pond_gravel > 0.05:
									floor_block = 77  # Gravel patch in pond!
								else:
									f_roll = rng.randrange(100)
									if f_roll < 65:
										floor_block = 4  # Dirt
									elif f_roll < 85:
										floor_block = 6  # Sand
									else:
										floor_block = 5  # Stone

								set_b(px, lake_surface_y - 2, pz, floor_block)
								set_b(px, lake_surface_y - 3, pz, 77 if pond_gravel > 0.15 else 5)
							elif dist_sq <= (radius + 1) * (radius + 1):
								# Watertight solid dirt/stone/gravel retaining wall rim extending 1 block above water level
								gx = chunk_offset_x + px
								gz = chunk_offset_z + pz
								pond_gravel = pnoise2((gx + 1200.0) / 12.0, (gz + 1200.0) / 12.0)
								if pond_gravel > 0.20:
									shore_block = 77  # Gravel shore patch
								else:
									s_roll = rng.randrange(100)
									if s_roll < 60:
										shore_block = 4  # Dirt
									elif s_roll < 80:
										shore_block = 6  # Sand
									else:
										shore_block = 5  # Stone
								for ry in range(lake_surface_y - 2, lake_surface_y + 2):
									b_curr = get_b(px, ry, pz)
									if b_curr == 0 or b_curr in (9, 19, 15, 20):
										set_b(px, ry, pz, shore_block)

	# 7. Surface Lava Pools (Slightly bigger, 100% bounded by regular STONE 5 retaining walls)
	if rng.randrange(100) < 12:
		pool_x = rng.randrange(4, chunk.CHUNK_WIDTH - 4)
		pool_z = rng.randrange(4, chunk.CHUNK_LENGTH - 4)
		pool_surface_y = surface_heights[pool_x * 16 + pool_z]  # Single uniform flat surface height for entire pool

		if 62 <= pool_surface_y <= 85:
			lava_rad = rng.randrange(3, 5)  # Bigger radius (3 to 4 blocks = 7 to 9 block diameter)
			for dx in range(-lava_rad - 1, lava_rad + 2):
				for dz in range(-lava_rad - 1, lava_rad + 2):
					dist_sq = dx * dx + dz * dz
					px, pz = pool_x + dx, pool_z + dz
					if 0 <= px < chunk.CHUNK_WIDTH and 0 <= pz < chunk.CHUNK_LENGTH:
						col_h = surface_heights[px * 16 + pz]

						if dist_sq <= lava_rad * lava_rad:
							# Clear terrain blocks above pool
							for cy in range(pool_surface_y + 1, col_h + 1):
								set_b(px, cy, pz, 0)

							# Perfectly flat lava surface
							set_b(px, pool_surface_y, pz, 15)       # Lava source top
							set_b(px, pool_surface_y - 1, pz, 15)   # Lava source in body
							floor_mat = 24 if rng.random() < 0.20 else 5  # Obsidian/Stone floor
							set_b(px, pool_surface_y - 2, pz, floor_mat)
						elif dist_sq <= (lava_rad + 1) * (lava_rad + 1):
							# Watertight regular STONE (5) retaining wall rim extending 1 block above lava level
							for ry in range(pool_surface_y - 2, pool_surface_y + 2):
								b_curr = get_b(px, ry, pz)
								if b_curr == 0 or b_curr in (9, 19, 15, 20):
									set_b(px, ry, pz, 5)

	# 7. Tree Generation
	trees = []
	for _ in range(8):
		tree_x = rng.randrange(1, chunk.CHUNK_WIDTH - 1)
		tree_z = rng.randrange(1, chunk.CHUNK_LENGTH - 1)
		gy = surface_heights[tree_x * 16 + tree_z]

		if (62 <= gy < 85 and gy + 8 < chunk.CHUNK_HEIGHT and get_b(tree_x, gy, tree_z) == 2):
			# Do not plant trees inside village perimeter
			import village
			if not village.is_in_village(chunk_offset_x + tree_x, chunk_offset_z + tree_z, seed):
				has_adjacent_tree = any((tree_x + dx, gy, tree_z + dz) in trees for dx in range(-2, 3) for dz in range(-2, 3))
				if not has_adjacent_tree:
					trunk_y = gy + 1
					for n in range(5):
						set_b(tree_x, trunk_y + n, tree_z, 8)

					leaves_height = trunk_y + 3
					for dx in range(-2, 3):
						for dz in range(-2, 3):
							if 0 <= tree_x + dx < chunk.CHUNK_WIDTH and 0 <= tree_z + dz < chunk.CHUNK_LENGTH:
								set_b(tree_x + dx, leaves_height, tree_z + dz, 13)
								set_b(tree_x + dx, leaves_height + 1, tree_z + dz, 13)
					for dx in range(-1, 2):
						for dz in range(-1, 2):
							if 0 <= tree_x + dx < chunk.CHUNK_WIDTH and 0 <= tree_z + dz < chunk.CHUNK_LENGTH:
								set_b(tree_x + dx, leaves_height + 2, tree_z + dz, 13)
					trees.append((tree_x, gy, tree_z))

	# 8. Village Structures Generation (High Priority: Overwrite terrain & trees)
	try:
		import village
		v_blocks, v_air, _ = village.get_village_blocks_for_chunk(x, z, seed)
		if v_blocks or v_air:
			# 1. Clear air volumes above/inside structures, roads, and wells
			for (lx, ly, lz) in v_air:
				if 0 <= lx < 16 and 0 <= ly < 256 and 0 <= lz < 16:
					set_b(lx, ly, lz, 0)
			# 2. Place structure blocks (cobblestone, wood, doors, crops, chests, etc.)
			for (lx, ly, lz), b_id in v_blocks.items():
				if 0 <= lx < 16 and 0 <= ly < 256 and 0 <= lz < 16:
					set_b(lx, ly, lz, b_id)
	except Exception as e:
		print(f"[Village Error in chunk {x}, {z}]: {e}")

	# 9. Stronghold Structures Generation (Underground stone brick corridors, rooms, libraries, prison, portal room)
	try:
		import stronghold_manager
		stronghold_manager.stamp_stronghold_blocks_for_chunk(x, z, flat_bytes, seed=seed)
	except Exception as e:
		pass

	return bytes(flat_bytes)


def build_nether_chunk_blocks_process(x, z, save_dir, seed=0):
	"""Independent worker function for ProcessPoolExecutor/ThreadPoolExecutor.
	Generates authentic Minecraft Java Edition 3D Nether terrain into a flat 1D bytearray (65536 bytes)."""
	save_path = os.path.join(save_dir, f"{x}_{z}.chunk")
	if os.path.exists(save_path):
		try:
			with gzip.open(save_path, 'rb') as f:
				data = f.read()
			if len(data) >= chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH:
				return data
		except Exception:
			pass

	flat_bytes = bytearray(chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH)

	seed_offset_x = float((seed * 10007) % 50000)
	seed_offset_z = float((seed * 16007) % 50000)

	rng = Random((x * 341873128712 + z * 132897987541 + seed + 99991) & ((1 << 64) - 1))

	chunk_offset_x = x * chunk.CHUNK_WIDTH
	chunk_offset_z = z * chunk.CHUNK_LENGTH

	# 1. 3D Noise Density Sampling on a 5x5x33 Grid (Spacing: 4 blocks in X/Z, 4 blocks in Y up to Y=128)
	grid = {}
	for gx in range(5):
		wx = (chunk_offset_x + gx * 4 + seed_offset_x) / 36.0
		for gz in range(5):
			wz = (chunk_offset_z + gz * 4 + seed_offset_z) / 36.0
			for gy in range(33):
				y = gy * 4
				wy = y / 30.0
				n = pnoise3(wx, wy, wz, octaves=3, persistence=0.5)
				t = y / 128.0

				# Height bias curve: solid foundation floor (Y=0..40), open caverns (Y=44..84), ceiling crust (Y=88..128)
				if t < 0.32:
					bias = (0.28 - t) * 1.6 - 0.02
				elif t > 0.68:
					bias = (t - 0.68) * 2.5 - 0.02
				else:
					bias = -0.30

				grid[(gx, gz, gy)] = n + bias

	# 2. Block Generation with Trilinear Interpolation
	def set_b(lx, ly, lz, b_id):
		flat_bytes[lx * 4096 + ly * 16 + lz] = b_id

	for i in range(16):
		gx0 = i // 4
		gx1 = min(4, gx0 + 1)
		tx = (i % 4) / 4.0

		for k in range(16):
			gz0 = k // 4
			gz1 = min(4, gz0 + 1)
			tz = (k % 4) / 4.0

			wx = chunk_offset_x + i + seed_offset_x
			wz = chunk_offset_z + k + seed_offset_z

			# Bedrock Floor: Y=0 (100%), Y=1..4 (probabilistic)
			set_b(i, 0, k, 14)  # Bedrock
			for by in range(1, 5):
				if rng.random() < (5 - by) / 5.0:
					set_b(i, by, k, 14)
				else:
					set_b(i, by, k, 84) # Netherrack

			# Bedrock Ceiling: Y=127 (100%), Y=124..126 (probabilistic)
			set_b(i, 127, k, 14) # Bedrock
			for by in range(124, 127):
				if rng.random() < (by - 123) / 4.0:
					set_b(i, by, k, 14)
				else:
					set_b(i, by, k, 84) # Netherrack

			# Nether Terrain: Y=5 to 123
			for y in range(5, 124):
				gy0 = y // 4
				gy1 = min(32, gy0 + 1)
				ty = (y % 4) / 4.0

				# Trilinear interpolation
				c000 = grid[(gx0, gz0, gy0)]
				c100 = grid[(gx1, gz0, gy0)]
				c010 = grid[(gx0, gz1, gy0)]
				c110 = grid[(gx1, gz1, gy0)]
				c001 = grid[(gx0, gz0, gy1)]
				c101 = grid[(gx1, gz0, gy1)]
				c011 = grid[(gx0, gz1, gy1)]
				c111 = grid[(gx1, gz1, gy1)]

				c00 = c000 * (1 - tx) + c100 * tx
				c10 = c010 * (1 - tx) + c110 * tx
				c01 = c001 * (1 - tx) + c101 * tx
				c11 = c011 * (1 - tx) + c111 * tx

				c0 = c00 * (1 - tz) + c10 * tz
				c1 = c01 * (1 - tz) + c11 * tz

				density = c0 * (1 - ty) + c1 * ty

				# Large Netherrack pillars & columns in middle caverns
				if 32 <= y <= 90:
					if abs(pnoise2(wx / 30.0, wz / 30.0)) < 0.07 and pnoise2((wx + 300) / 16.0, (wz + 300) / 16.0) > 0.12:
						density = max(density, 0.25)

				if density > 0.0:
					# Solid Block
					# Soul Sand valleys & shores near lava sea (Y=25..42)
					if 25 <= y <= 42 and (pnoise2(wx / 20.0, wz / 20.0, octaves=2) > 0.05):
						set_b(i, y, k, 85) # Soul Sand
					elif pnoise3((wx + 500) / 7.0, y / 7.0, (wz + 500) / 7.0) > 0.58:
						set_b(i, y, k, 87) # Nether Quartz Ore
					else:
						set_b(i, y, k, 84) # Netherrack
				else:
					# Cavity: Lava Sea at Y <= 31
					if y <= 31:
						set_b(i, y, k, 15) # Lava
					else:
						set_b(i, y, k, 0)  # Air

			# Glowstone Ceiling Clusters (Y=60..120)
			for y in range(60, 120):
				idx = i * 4096 + y * 16 + k
				idx_above = i * 4096 + (y + 1) * 16 + k
				if flat_bytes[idx] == 0 and flat_bytes[idx_above] == 84:
					# Ceiling detected! Check cluster probability
					if pnoise3(wx / 14.0, y / 14.0, wz / 14.0) > 0.45:
						hang_len = rng.randint(1, 4)
						for hy in range(y, max(5, y - hang_len), -1):
							h_idx = i * 4096 + hy * 16 + k
							if flat_bytes[h_idx] == 0:
								flat_bytes[h_idx] = 86 # Glowstone
							else:
								break

			# Ambient Fire on top of exposed Netherrack (Y=32..110)
			for y in range(32, 110):
				idx = i * 4096 + y * 16 + k
				idx_below = i * 4096 + (y - 1) * 16 + k
				if flat_bytes[idx] == 0 and flat_bytes[idx_below] == 84:
					if rng.random() < 0.02:
						flat_bytes[idx] = 78 # Fire

	# 3. Stamp Connected Nether Fortress Structures (Bridges, Corridors, Spawner Platforms, Nether Wart Farms)
	try:
		import fortress_manager
		fortress_manager.stamp_fortress_blocks_for_chunk(x, z, flat_bytes, seed=seed)
	except Exception:
		pass

	# Save to disk
	try:
		with gzip.open(save_path, 'wb', compresslevel=1) as f:
			f.write(bytes(flat_bytes))
	except Exception:
		pass

	return bytes(flat_bytes)


def build_end_chunk_blocks_process(x, z, save_dir, seed=0):
	"""Independent worker function for ProcessPoolExecutor/ThreadPoolExecutor.
	Generates authentic Minecraft Java Edition End terrain (Central Island, Spawn Platform, Pillars, Fountain) into a 65536-byte chunk."""
	save_path = os.path.join(save_dir, f"{x}_{z}.chunk")
	if os.path.exists(save_path):
		try:
			with gzip.open(save_path, 'rb') as f:
				data = f.read()
			if len(data) >= chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH:
				return data
		except Exception:
			pass

	flat_bytes = bytearray(chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH)
	import end_generator
	end_generator.end_generator.seed = seed
	end_generator.end_generator.stamp_chunk_blocks(x, z, flat_bytes)

	# Save to disk
	try:
		with gzip.open(save_path, 'wb', compresslevel=1) as f:
			f.write(bytes(flat_bytes))
	except Exception:
		pass

	return bytes(flat_bytes)


def build_section_mesh_process(chunk_x, chunk_z, section_y, center_blocks, north_blocks, south_blocks, east_blocks, west_blocks, block_types_info, water_levels=None, lava_levels=None, center_states=None, burning_blocks=None):
	"""Standalone worker function for ProcessPoolExecutor.
	Meshes a single 16x16x16 vertical section of a chunk with 100% process pool isolation (zero GIL contention)."""
	min_y = section_y * 16
	max_y = min_y + 16

	# 1. Quick all-air check
	all_air = True
	for y in range(min_y, max_y):
		base_y = y * 16
		for x in range(16):
			base_xy = x * 4096 + base_y
			for z in range(16):
				if center_blocks[base_xy + z] != 0:
					all_air = False
					break
			if not all_air: break
		if not all_air: break

	if all_air:
		return (chunk_x, chunk_z, section_y, b'', b'', b'', b'', b'', b'', b'', b'', False)

	opaque_pos = array.array('f')
	opaque_tex = array.array('f')
	opaque_shd = array.array('f')
	opaque_idx = array.array('I')
	opaque_vert_count = 0

	trans_pos = array.array('f')
	trans_tex = array.array('f')
	trans_shd = array.array('f')
	trans_idx = array.array('I')
	trans_vert_count = 0

	missing_neighbors = False

	neighbor_offsets = [
		(1, 0, 0),
		(-1, 0, 0),
		(0, 1, 0),
		(0, -1, 0),
		(0, 0, 1),
		(0, 0, -1),
	]

	def get_nb(nx, ny, nz):
		nonlocal missing_neighbors
		if ny < 0 or ny >= 256:
			return 0
		if 0 <= nx < 16 and 0 <= nz < 16:
			return center_blocks[nx * 4096 + ny * 16 + nz]
		if nx >= 16:
			if east_blocks is None:
				missing_neighbors = True
				return 0
			return east_blocks[0 * 4096 + ny * 16 + nz]
		if nx < 0:
			if west_blocks is None:
				missing_neighbors = True
				return 0
			return west_blocks[15 * 4096 + ny * 16 + nz]
		if nz >= 16:
			if south_blocks is None:
				missing_neighbors = True
				return 0
			return south_blocks[nx * 4096 + ny * 16 + 0]
		if nz < 0:
			if north_blocks is None:
				missing_neighbors = True
				return 0
			return north_blocks[nx * 4096 + ny * 16 + 15]
		return 0

	def get_liquid_h(lx, ly, lz, is_wat):
		above_num = get_nb(lx, ly + 1, lz)
		if above_num in (9, 19, 15, 20):
			return 1.0

		wx = chunk_x * 16 + lx
		wy = ly
		wz = chunk_z * 16 + lz
		pos = (wx, wy, wz)

		b_num = get_nb(lx, ly, lz)
		if is_wat:
			if b_num == 9: return 15.0 / 16.0
			if b_num == 19:
				lvl = water_levels.get(pos, 1) if water_levels else 1
				if lvl in (0, 8): return 15.0 / 16.0
				return max(2.0, 15.0 - 1.8 * lvl) / 16.0
			return 15.0 / 16.0
		else:
			if b_num == 15: return 15.0 / 16.0
			if b_num == 20:
				lvl = lava_levels.get(pos, 1) if lava_levels else 1
				if lvl in (0, 4): return 15.0 / 16.0
				return max(2.0, 15.0 - 3.8 * lvl) / 16.0
			return 15.0 / 16.0

	for local_x in range(16):
		for local_y in range(min_y, max_y):
			for local_z in range(16):
				b_num = center_blocks[local_x * 4096 + local_y * 16 + local_z]
				if not b_num:
					continue

				b_info = block_types_info.get(b_num)
				if not b_info:
					continue

				x = chunk_x * 16 + local_x
				y = local_y
				z = chunk_z * 16 + local_z

				is_translucent = b_info['translucent']
				is_water = b_info['name'] in ('water', 'under_water')
				is_lava = b_info['name'] in ('lava', 'under_lava')
				is_liquid = is_water or is_lava

				h_scale = get_liquid_h(local_x, local_y, local_z, is_water) if is_liquid else 1.0

				st_dict = center_states.get(f"{local_x},{local_y},{local_z}") if center_states else None
				facing = st_dict.get('f', 'NORTH') if st_dict else 'NORTH'
				half = st_dict.get('h', 'LOWER') if st_dict else 'LOWER'
				hinge = st_dict.get('hg', 'LEFT') if st_dict else 'LEFT'
				open_state = st_dict.get('o', False) if st_dict else False
				shape = st_dict.get('s', 'STRAIGHT') if st_dict else 'STRAIGHT'
				axis = st_dict.get('a', 'Y') if st_dict else 'Y'
				conns = st_dict.get('c', {}) if st_dict else {}

				LEFT_DIRECTIONS = {"NORTH": "WEST", "SOUTH": "EAST", "WEST": "SOUTH", "EAST": "NORTH"}
				RIGHT_DIRECTIONS = {"NORTH": "EAST", "SOUTH": "WEST", "WEST": "NORTH", "EAST": "SOUTH"}

				def rotate_pt(vx, vy, vz, rot_facing):
					if rot_facing == "EAST": return (-vz, vy, vx)
					elif rot_facing == "SOUTH": return (-vx, vy, -vz)
					elif rot_facing == "WEST": return (vz, vy, -vx)
					return (vx, vy, vz)

				def add_custom_box(min_pt, max_pt, face_tex_indices, rot_facing="NORTH"):
					nonlocal opaque_vert_count, trans_vert_count
					pos_arr = trans_pos if is_translucent else opaque_pos
					idx_arr = trans_idx if is_translucent else opaque_idx
					x1, y1, z1 = min_pt
					x2, y2, z2 = max_pt

					# 6 Quad Faces: Right (+X), Left (-X), Top (+Y), Bottom (-Y), Front (+Z), Back (-Z)
					quads = [
						# Right (+X, face 0)
						([(x2, y2, z2), (x2, y1, z2), (x2, y1, z1), (x2, y2, z1)], face_tex_indices[0], 0.85),
						# Left (-X, face 1)
						([(x1, y2, z1), (x1, y1, z1), (x1, y1, z2), (x1, y2, z2)], face_tex_indices[1], 0.85),
						# Top (+Y, face 2)
						([(x2, y2, z2), (x2, y2, z1), (x1, y2, z1), (x1, y2, z2)], face_tex_indices[2], 1.00),
						# Bottom (-Y, face 3)
						([(x1, y1, z2), (x1, y1, z1), (x2, y1, z1), (x2, y1, z2)], face_tex_indices[3], 0.50),
						# Front (+Z, face 4)
						([(x1, y2, z2), (x1, y1, z2), (x2, y1, z2), (x2, y2, z2)], face_tex_indices[4], 0.95),
						# Back (-Z, face 5)
						([(x2, y2, z1), (x2, y1, z1), (x1, y1, z1), (x1, y2, z1)], face_tex_indices[5], 0.80),
					]

					for quad_verts, tex_idx, shading in quads:
						t_raw = b_info['tex_coords'][tex_idx] if tex_idx < len(b_info['tex_coords']) else b_info['tex_coords'][0]
						c = trans_vert_count if is_translucent else opaque_vert_count
						idx_arr.extend((c, c + 1, c + 2, c, c + 2, c + 3))

						for vx, vy, vz in quad_verts:
							rx, ry, rz = rotate_pt(vx, vy, vz, rot_facing)
							pos_arr.extend((rx + x, ry + y, rz + z))

						if is_translucent:
							trans_vert_count += 4
							trans_tex.extend(t_raw[:12] if len(t_raw) >= 12 else t_raw * 4)
							trans_shd.extend([shading] * 4)
						else:
							opaque_vert_count += 4
							opaque_tex.extend(t_raw[:12] if len(t_raw) >= 12 else t_raw * 4)
							opaque_shd.extend([shading] * 4)

				def add_face(face, is_trans, custom_tc_idx=None):
					nonlocal opaque_vert_count, trans_vert_count
					vp = b_info['vertex_positions'][face]
					tc_i = face if custom_tc_idx is None else custom_tc_idx
					tc = b_info['tex_coords'][tc_i] if tc_i < len(b_info['tex_coords']) else b_info['tex_coords'][0]
					sh = b_info['shading_values'][face]

					if is_trans:
						pos = trans_pos
						for i in range(4):
							pos.append(vp[i * 3 + 0] + x)
							vy = vp[i * 3 + 1]
							if is_liquid:
								pos.append((y - 0.5) + h_scale if vy > 0.0 else y - 0.5)
							else:
								pos.append(vy + y)
							pos.append(vp[i * 3 + 2] + z)

						c = trans_vert_count
						trans_idx.extend((c, c + 1, c + 2, c, c + 2, c + 3))
						trans_vert_count += 4

						trans_tex.extend(tc)
						trans_shd.extend(sh)
					else:
						pos = opaque_pos
						for i in range(4):
							pos.append(vp[i * 3 + 0] + x)
							vy = vp[i * 3 + 1]
							if is_liquid:
								pos.append((y - 0.5) + h_scale if vy > 0.0 else y - 0.5)
							else:
								pos.append(vy + y)
							pos.append(vp[i * 3 + 2] + z)

						c = opaque_vert_count
						opaque_idx.extend((c, c + 1, c + 2, c, c + 2, c + 3))
						opaque_vert_count += 4

						opaque_tex.extend(tc)
						opaque_shd.extend(sh)

				def get_dir_tex_idx(b_num, face_idx, facing):
					if b_num in (27, 54, 55, 56, 37, 57, 58, 59):
						if facing == "SOUTH": front_f = 0
						elif facing == "NORTH": front_f = 1
						elif facing == "EAST": front_f = 5
						elif facing == "WEST": front_f = 4
						else: front_f = 1

						if face_idx == front_f:
							return 4  # Front texture (chest_front / furnace_front)
						elif face_idx == 2:
							return 2  # Top texture
						elif face_idx == 3:
							return 3  # Bottom texture
						else:
							return 0  # Side texture
					return face_idx

				if b_info['is_cube']:
					is_dir = b_num in (27, 54, 55, 56, 37, 57, 58, 59)
					is_log = b_num in (8, 60, 61)

					for face_idx, (dx, dy, dz) in enumerate(neighbor_offsets):
						nx, ny, nz = local_x + dx, local_y + dy, local_z + dz
						neighbor_num = get_nb(nx, ny, nz)

						if neighbor_num == 0:
							if is_dir:
								tc_i = get_dir_tex_idx(b_num, face_idx, facing)
								add_face(face_idx, is_translucent, custom_tc_idx=tc_i)
							elif is_log:
								log_ax = "X" if b_num == 60 else ("Z" if b_num == 61 else axis)
								tc_i = (2 if face_idx in (0, 1) else 0) if log_ax == "X" else ((2 if face_idx in (4, 5) else 0) if log_ax == "Z" else (2 if face_idx in (2, 3) else 0))
								add_face(face_idx, is_translucent, custom_tc_idx=tc_i)
							else:
								add_face(face_idx, is_translucent)
						elif is_liquid and neighbor_num in (9, 19, 15, 20):
							if face_idx != 3:
								c_h = get_liquid_h(local_x, local_y, local_z, is_water)
								n_h = get_liquid_h(nx, ny, nz, is_water)
								if n_h < c_h - 0.01:
									add_face(face_idx, is_translucent)
						else:
							n_info = block_types_info.get(neighbor_num)
							if not n_info or n_info['transparent']:
								if is_dir:
									tc_i = get_dir_tex_idx(b_num, face_idx, facing)
									add_face(face_idx, is_translucent, custom_tc_idx=tc_i)
								elif is_log:
									log_ax = "X" if b_num == 60 else ("Z" if b_num == 61 else axis)
									tc_i = (2 if face_idx in (0, 1) else 0) if log_ax == "X" else ((2 if face_idx in (4, 5) else 0) if log_ax == "Z" else (2 if face_idx in (2, 3) else 0))
									add_face(face_idx, is_translucent, custom_tc_idx=tc_i)
								else:
									add_face(face_idx, is_translucent)

				else:
					# Non-Cube Custom Model Geometry using native 3D model definitions + BlockState parameters
					rot_f = facing if b_num in (41, 42, 73, 74, 92, 93, 178, 179, 181, 182, 43, 44, 45, 46, 65, 66, 67, 68, 47, 48, 49, 50, 69, 70, 71, 72, 75, 76) else "NORTH"

					if b_num in (38, 39, 40, 62, 63, 64, 95, 180):
						# Slabs (Bottom, Top, Double)
						sl_h = "TOP" if b_num in (62, 63, 64) else half
						if sl_h == "DOUBLE":
							add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.5, 0.5), [0, 0, 0, 0, 0, 0])
						elif sl_h == "TOP":
							add_custom_box((-0.5, 0.0, -0.5), (0.5, 0.5, 0.5), [0, 0, 0, 0, 0, 0])
						else:
							add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.0, 0.5), [0, 0, 0, 0, 0, 0])

					elif b_num in (41, 42, 73, 74, 92, 93, 178, 179):
						# Stairs (Facing, Half, Shape)
						is_top_stair = (b_num in (73, 74, 93, 179) or half in ("TOP", "UPPER"))
						y_base_min, y_base_max = (0.0, 0.5) if is_top_stair else (-0.5, 0.0)
						y_step_min, y_step_max = (-0.5, 0.0) if is_top_stair else (0.0, 0.5)

						add_custom_box((-0.5, y_base_min, -0.5), (0.5, y_base_max, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
						if shape == "INNER_LEFT":
							add_custom_box((-0.5, y_step_min, -0.5), (0.5, y_step_max, 0.0), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							add_custom_box((-0.5, y_step_min, 0.0), (0.0, y_step_max, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
						elif shape == "INNER_RIGHT":
							add_custom_box((-0.5, y_step_min, -0.5), (0.5, y_step_max, 0.0), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							add_custom_box((0.0, y_step_min, 0.0), (0.5, y_step_max, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
						elif shape == "OUTER_LEFT":
							add_custom_box((-0.5, y_step_min, -0.5), (0.0, y_step_max, 0.0), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
						elif shape == "OUTER_RIGHT":
							add_custom_box((0.0, y_step_min, -0.5), (0.5, y_step_max, 0.0), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
						else:
							add_custom_box((-0.5, y_step_min, -0.5), (0.5, y_step_max, 0.0), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)

					elif b_num in (43, 44, 45, 46, 65, 66, 67, 68):
						# Doors (Facing, Hinge, Half, Open)
						d_open = open_state or (b_num in (44, 46, 66, 68))
						if d_open:
							if hinge == "RIGHT":
								add_custom_box((0.3125, -0.5, -0.5), (0.5, 0.5, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							else:
								add_custom_box((-0.5, -0.5, -0.5), (-0.3125, 0.5, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
						else:
							add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.5, -0.3125), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)

					elif b_num in (47, 48, 49, 50, 69, 70, 71, 72):
						# Trapdoors (Facing, Half, Open)
						is_top = b_num in (69, 70, 71, 72) or half == "TOP"
						td_open = open_state or (b_num in (48, 50, 70, 72))

						if td_open:
							add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.5, -0.3125), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
						else:
							if is_top:
								add_custom_box((-0.5, 0.3125, -0.5), (0.5, 0.5, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							else:
								add_custom_box((-0.5, -0.5, -0.5), (0.5, -0.3125, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)

					elif b_num in (75, 76):
						# Fence Gates (Facing, Open)
						gate_open = open_state or (b_num == 76)
						if gate_open:
							add_custom_box((-0.5, -0.5, -0.125), (-0.375, 0.5, 0.125), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							add_custom_box((0.375, -0.5, -0.125), (0.5, 0.5, 0.125), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							add_custom_box((-0.5, -0.375, 0.125), (-0.375, 0.375, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							add_custom_box((0.375, -0.375, 0.125), (0.5, 0.375, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
						else:
							add_custom_box((-0.5, -0.5, -0.125), (-0.375, 0.5, 0.125), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							add_custom_box((0.375, -0.5, -0.125), (0.5, 0.5, 0.125), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							add_custom_box((-0.375, -0.375, -0.0625), (0.375, 0.375, 0.0625), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)

					elif b_num in (51, 52, 53, 91, 99):
						# Fences (51, 91), Walls (52), Glass Panes (53), Iron Bars (99)
						nb_n = get_nb(local_x, local_y, local_z - 1)
						nb_s = get_nb(local_x, local_y, local_z + 1)
						nb_w = get_nb(local_x - 1, local_y, local_z)
						nb_e = get_nb(local_x + 1, local_y, local_z)

						def can_conn(nb, d_key):
							if conns and d_key in conns: return conns[d_key]
							if nb in (0, 9, 10, 11, 12, 13, 15, 19, 20, 25, 31, 33, 43, 44, 45, 46, 47, 48, 49, 50, 65, 66, 67, 68, 69, 70, 71, 72, 78, 79, 81, 88, 89, 94, 181, 182, 183):
								return False
							if b_num in (51, 91):
								return nb in (51, 91, 75, 76) or (block_types_info.get(nb, {}).get('is_cube', False) and not block_types_info.get(nb, {}).get('transparent', False))
							elif b_num == 52:
								return nb in (52, 53, 99, 75, 76) or (block_types_info.get(nb, {}).get('is_cube', False) and not block_types_info.get(nb, {}).get('transparent', False))
							elif b_num in (53, 99):
								# Glass panes and iron bars connect to other panes/bars, walls, fences, gates, stairs, slabs, and solid blocks!
								return True
							return False

						c_n = can_conn(nb_n, 'north')
						c_s = can_conn(nb_s, 'south')
						c_w = can_conn(nb_w, 'west')
						c_e = can_conn(nb_e, 'east')

						is_straight = (c_n and c_s and not c_w and not c_e) or (c_w and c_e and not c_n and not c_s)

						if b_num in (51, 91):
							add_custom_box((-0.125, -0.5, -0.125), (0.125, 0.5, 0.125), [0, 0, 0, 0, 0, 0])
							if c_n:
								add_custom_box((-0.08, 0.15, -0.5), (0.08, 0.35, -0.125), [0, 0, 0, 0, 0, 0])
								add_custom_box((-0.08, -0.35, -0.5), (0.08, -0.15, -0.125), [0, 0, 0, 0, 0, 0])
							if c_s:
								add_custom_box((-0.08, 0.15, 0.125), (0.08, 0.35, 0.5), [0, 0, 0, 0, 0, 0])
								add_custom_box((-0.08, -0.35, 0.125), (0.08, -0.15, 0.5), [0, 0, 0, 0, 0, 0])
							if c_w:
								add_custom_box((-0.5, 0.15, -0.08), (-0.125, 0.35, 0.08), [0, 0, 0, 0, 0, 0])
								add_custom_box((-0.5, -0.35, -0.08), (-0.125, -0.15, 0.08), [0, 0, 0, 0, 0, 0])
							if c_e:
								add_custom_box((0.125, 0.15, -0.08), (0.5, 0.35, 0.08), [0, 0, 0, 0, 0, 0])
								add_custom_box((0.125, -0.35, -0.08), (0.5, -0.15, 0.08), [0, 0, 0, 0, 0, 0])

						elif b_num == 52:
							above_b = get_nb(local_x, local_y + 1, local_z)
							has_post = (not is_straight) or (above_b != 0 and above_b not in (9, 19, 15, 20))
							if has_post:
								add_custom_box((-0.25, -0.5, -0.25), (0.25, 0.5, 0.25), [0, 0, 0, 0, 0, 0])
							if c_n: add_custom_box((-0.15, -0.5, -0.5), (0.15, 0.35, -0.25 if has_post else 0.0), [0, 0, 0, 0, 0, 0])
							if c_s: add_custom_box((-0.15, -0.5, 0.25 if has_post else 0.0), (0.15, 0.35, 0.5), [0, 0, 0, 0, 0, 0])
							if c_w: add_custom_box((-0.5, -0.5, -0.15), (-0.25 if has_post else 0.0, 0.35, 0.15), [0, 0, 0, 0, 0, 0])
							if c_e: add_custom_box((0.25 if has_post else 0.0, -0.5, -0.15), (0.5, 0.35, 0.15), [0, 0, 0, 0, 0, 0])

						elif b_num in (53, 99):
							if not (c_n or c_s or c_w or c_e):
								add_custom_box((-0.03125, -0.5, -0.125), (0.03125, 0.5, 0.125), [0, 0, 0, 0, 0, 0])
								add_custom_box((-0.125, -0.5, -0.03125), (0.125, 0.5, 0.03125), [0, 0, 0, 0, 0, 0])
							else:
								add_custom_box((-0.03125, -0.5, -0.03125), (0.03125, 0.5, 0.03125), [0, 0, 0, 0, 0, 0])
								if c_n: add_custom_box((-0.03125, -0.5, -0.5), (0.03125, 0.5, -0.03125), [0, 0, 0, 0, 0, 0])
								if c_s: add_custom_box((-0.03125, -0.5, 0.03125), (0.03125, 0.5, 0.5), [0, 0, 0, 0, 0, 0])
								if c_w: add_custom_box((-0.5, -0.5, -0.03125), (-0.03125, 0.5, 0.03125), [0, 0, 0, 0, 0, 0])
								if c_e: add_custom_box((0.03125, -0.5, -0.03125), (0.5, 0.5, 0.03125), [0, 0, 0, 0, 0, 0])

					elif b_num in (181, 182):
						# 1. Base End Portal Frame (Height 0.8125 blocks)
						# Top is endframe_top (2), Bottom is end_stone (3), Sides are endframe_side (0, 1, 4, 5)
						add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.3125, 0.5), [0, 1, 2, 3, 4, 5], rot_facing=rot_f)

						# 2. Separate 3D Eye of Ender piece resting in socket for filled frame (182)
						if b_num == 182:
							eye_tex_idx = 6 if len(b_info['tex_coords']) > 6 else 2
							add_custom_box((-0.25, 0.3125, -0.25), (0.25, 0.50, 0.25), [eye_tex_idx] * 6, rot_facing=rot_f)

					elif b_num == 183:
						# End Portal block is rendered exclusively by EndPortalRenderer with infinite parallax shader
						pass
					else:
						for face_idx in range(len(b_info['vertex_positions'])):
							add_face(face_idx, is_translucent)

	# Render burning block fire overlays (masked side face fire)
	if burning_blocks:
		b78_info = block_types_info.get(78)
		fire_tex_idx = int(b78_info['tex_coords'][0][2]) if b78_info and b78_info.get('tex_coords') else 0
		cube_vps = block_types_info[1]['vertex_positions'] if 1 in block_types_info else None

		if cube_vps:
			for key_str_or_tuple, fire_faces in burning_blocks.items():
				if isinstance(key_str_or_tuple, str):
					lx, ly, lz = map(int, key_str_or_tuple.split(','))
				else:
					lx, ly, lz = key_str_or_tuple

				if not (min_y <= ly < max_y):
					continue

				bx = chunk_x * 16 + lx
				by = ly
				bz = chunk_z * 16 + lz

				for f_idx in fire_faces:
					if 0 <= f_idx < 6:
						dx, dy, dz = neighbor_offsets[f_idx]
						nb_num = get_nb(lx + dx, ly + dy, lz + dz)
						nb_info = block_types_info.get(nb_num)
						# Render fire face if exposed to air, liquids, transparent blocks, or other fire
						if nb_num == 0 or (nb_info and nb_info['transparent']) or nb_num in (9, 19, 15, 20, 78):
							vp = cube_vps[f_idx]
							offset_scale = 0.003

							c = trans_vert_count
							trans_idx.extend((c, c + 1, c + 2, c, c + 2, c + 3))
							trans_vert_count += 4

							for i in range(4):
								trans_pos.append(vp[i * 3 + 0] + bx + dx * offset_scale)
								trans_pos.append(vp[i * 3 + 1] + by + dy * offset_scale)
								trans_pos.append(vp[i * 3 + 2] + bz + dz * offset_scale)

							fire_tc = [
								0.0, 1.0, float(fire_tex_idx),
								0.0, 0.0, float(fire_tex_idx),
								1.0, 0.0, float(fire_tex_idx),
								1.0, 1.0, float(fire_tex_idx)
							]
							trans_tex.extend(fire_tc)
							trans_shd.extend([1.0, 1.0, 1.0, 1.0])

	final_trans_idx = array.array('I', [idx + opaque_vert_count for idx in trans_idx])

	return (
		chunk_x, chunk_z, section_y,
		opaque_pos.tobytes(), opaque_tex.tobytes(), opaque_shd.tobytes(), opaque_idx.tobytes(),
		trans_pos.tobytes(), trans_tex.tobytes(), trans_shd.tobytes(), final_trans_idx.tobytes(),
		missing_neighbors
	)


class FurnaceData:
	def __init__(self):
		self.input_slot = [0, 0]    # [item_id, count]
		self.fuel_slot = [0, 0]     # [item_id, count]
		self.output_slot = [0, 0]   # [item_id, count]
		self.burn_time_remaining = 0.0
		self.max_burn_time = 0.0
		self.smelt_progress = 0.0

	def tick(self, dt):
		import gui
		input_id, input_cnt = self.input_slot[0], self.input_slot[1]
		recipe = gui.SMELTING_RECIPES.get(input_id)

		# Check if current input item is smeltable and output slot has room
		can_smelt = False
		if recipe and input_cnt > 0:
			result_id, result_cnt = recipe
			out_id, out_cnt = self.output_slot[0], self.output_slot[1]
			if out_id == 0 or (out_id == result_id and out_cnt + result_cnt <= 64):
				can_smelt = True

		# 1. Fuel consumption: Consume fuel item if fire is out but we need to smelt
		if can_smelt and self.burn_time_remaining <= 0:
			fuel_id, fuel_cnt = self.fuel_slot[0], self.fuel_slot[1]
			burn_sec = gui.FUEL_BURN_TIMES.get(fuel_id, 0.0)
			if burn_sec > 0 and fuel_cnt > 0:
				if fuel_id == 149:  # Lava Bucket leaves Empty Bucket (147)
					self.fuel_slot[0] = 147
					self.fuel_slot[1] = 1
				else:
					self.fuel_slot[1] -= 1
					if self.fuel_slot[1] <= 0:
						self.fuel_slot[0] = 0
						self.fuel_slot[1] = 0
				self.burn_time_remaining = burn_sec
				self.max_burn_time = burn_sec

		# 2. Burn active fire
		if self.burn_time_remaining > 0:
			self.burn_time_remaining = max(0.0, self.burn_time_remaining - dt)

			if can_smelt:
				self.smelt_progress += dt
				if self.smelt_progress >= 10.0:  # 1 item takes 10 seconds to smelt!
					self.smelt_progress = 0.0
					result_id, result_cnt = recipe

					if self.output_slot[0] == 0:
						self.output_slot[0] = result_id
						self.output_slot[1] = result_cnt
					elif self.output_slot[0] == result_id:
						self.output_slot[1] += result_cnt

					self.input_slot[1] -= 1
					if self.input_slot[1] <= 0:
						self.input_slot[0] = 0
						self.input_slot[1] = 0
			else:
				self.smelt_progress = max(0.0, self.smelt_progress - dt * 2.0)
		else:
			self.smelt_progress = max(0.0, self.smelt_progress - dt * 2.0)


class ChestData:
	def __init__(self):
		self.slots = [[0, 0] for _ in range(27)]  # 27 slots per single chest


class World:
	def __init__(self, seed=None, save_folder=None, render_distance=6, dimension="overworld"):
		self.dimension = dimension  # "overworld" or "nether"
		self.furnaces = {}  # (x, y, z) -> FurnaceData
		self.chests = {}    # (x, y, z) -> ChestData
		self.item_drop_manager = None
		self.tnt_manager = None
		if seed is None or seed == "":
			self.seed = Random().randint(100000, 999999999)
		elif isinstance(seed, str):
			if seed.lstrip("-").isdigit():
				self.seed = int(seed)
			else:
				self.seed = abs(hash(seed)) % 1000000000
		else:
			self.seed = int(seed)

		self.save_folder = save_folder or "default"
		import world_save
		subfolder = 'chunks_nether' if self.dimension == 'nether' else ('chunks_end' if self.dimension == 'end' else 'chunks')
		self.save_dir = os.path.join(world_save.SAVES_DIR, self.save_folder, subfolder)
		os.makedirs(self.save_dir, exist_ok=True)

		self.texture_manager = texture_manager.Texture_manager(16, 16, 256)
		self.block_types = [None]

		self.block_types.append(block_type.Block_type(self.texture_manager, name="cobblestone", block_face_textures={"all": "cobblestone"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="grass", block_face_textures={"top": "grass", "bottom": "dirt", "sides": "grass_side"}, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="grass_block", block_face_textures={"all": "grass"}, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dirt", block_face_textures={"all": "dirt"}, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="stone", block_face_textures={"all": "stone"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="sand", block_face_textures={"all": "sand"}, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="planks", block_face_textures={"all": "planks"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="log", block_face_textures={"top": "log_top", "bottom": "log_top", "sides": "log_side"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="water", block_face_textures={"all": "water"}, model=models.liquid, transparent=True, break_time=float('inf'), requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="rose", block_face_textures={"all": "rose"}, model=models.plant, break_time=0.15, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="cactus", block_face_textures={"top": "cactus_top", "bottom": "cactus_bottom", "sides": "cactus_side"}, model=models.cactus, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dead_bush", block_face_textures={"all": "dead_bush"}, model=models.plant, break_time=0.15, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="leaves", block_face_textures={"all": "leaves"}, model=models.leaves, break_time=0.2, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="bedrock", block_face_textures={"all": "bedrock"}, break_time=float('inf'), requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="lava", block_face_textures={"all": "lava"}, model=models.liquid, transparent=True, break_time=float('inf'), requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="coal_ore", block_face_textures={"all": "coal_ore"}, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_ore", block_face_textures={"all": "iron_ore"}, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="diamond_ore", block_face_textures={"all": "diamond_ore"}, break_time=2.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="under_water", block_face_textures={"all": "water"}, model=models.liquid, transparent=True, break_time=float('inf'), requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="under_lava", block_face_textures={"all": "lava"}, model=models.liquid, transparent=True, break_time=float('inf'), requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="glass", block_face_textures={"all": "glass"}, transparent=True, break_time=0.3, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="bricks", block_face_textures={"all": "bricks"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="bookshelf", block_face_textures={"top": "planks", "bottom": "planks", "sides": "bookshelf"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="obsidian", block_face_textures={"all": "obsidian"}, break_time=5.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="tnt", block_face_textures={"top": "tnt_top", "bottom": "tnt_bottom", "sides": "tnt_side"}, break_time=0.5, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="crafting_table", block_face_textures={"top": "crafting_table_top", "bottom": "planks", "sides": "crafting_table_x"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="furnace", block_face_textures={"top": "furnace_y", "bottom": "stone", "sides": "furnace_side", "front": "furnace_front"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="gold_block", block_face_textures={"all": "gold_block"}, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_block", block_face_textures={"all": "iron_block"}, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="diamond_block", block_face_textures={"all": "diamond_block"}, break_time=2.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="snow", block_face_textures={"all": "snow"}, break_time=0.3, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="ice", block_face_textures={"all": "ice"}, transparent=True, break_time=0.5, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="yellow_flower", block_face_textures={"all": "yellow_flower"}, model=models.plant, break_time=0.15, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="sponge", block_face_textures={"all": "sponge"}, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="gold_ore", block_face_textures={"all": "gold_ore"}, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="redstone_ore", block_face_textures={"all": "redstone_ore"}, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="chest", block_face_textures={"top": "chest_top", "bottom": "planks", "sides": "chest_side", "front": "chest_front"}, break_time=1.5, requires_tool=False))
		# Non-Cube Blocks & Block State Variations (38-74)
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_slab", block_face_textures={"all": "planks"}, model=models.slab, transparent=True, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="cobblestone_slab", block_face_textures={"all": "cobblestone"}, model=models.slab, transparent=True, break_time=1.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="stone_slab", block_face_textures={"all": "stone"}, model=models.slab, transparent=True, break_time=1.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_stairs", block_face_textures={"all": "planks"}, model=models.stairs, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="cobblestone_stairs", block_face_textures={"all": "cobblestone"}, model=models.stairs, transparent=True, break_time=1.2, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_door", block_face_textures={"all": "door_wood_lower"}, model=models.door, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_door_open", block_face_textures={"all": "door_wood_lower"}, model=models.door_open, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_door", block_face_textures={"all": "iron_door_bottom_half"}, model=models.door, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_door_open", block_face_textures={"all": "iron_door_bottom_half"}, model=models.door_open, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_trapdoor", block_face_textures={"all": "trapdoor"}, model=models.trapdoor, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_trapdoor_open", block_face_textures={"all": "trapdoor"}, model=models.trapdoor_open, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_trapdoor", block_face_textures={"all": "iron_trapdoor"}, model=models.trapdoor, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_trapdoor_open", block_face_textures={"all": "iron_trapdoor"}, model=models.trapdoor_open, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_fence", block_face_textures={"all": "planks"}, model=models.fence, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="cobblestone_wall", block_face_textures={"all": "cobblestone"}, model=models.wall, transparent=True, break_time=1.2, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="glass_pane", block_face_textures={"all": "glass"}, model=models.glass_pane, transparent=True, break_time=0.2, requires_tool=False))
		# Block State Variations (54-74)
		self.block_types.append(block_type.Block_type(self.texture_manager, name="furnace_south", block_face_textures={"top": "furnace_y", "bottom": "stone", "sides": "furnace_side", "front": "furnace_front"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="furnace_west", block_face_textures={"top": "furnace_y", "bottom": "stone", "sides": "furnace_side", "front": "furnace_front"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="furnace_east", block_face_textures={"top": "furnace_y", "bottom": "stone", "sides": "furnace_side", "front": "furnace_front"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="chest_south", block_face_textures={"top": "chest_top", "bottom": "planks", "sides": "chest_side", "front": "chest_front"}, break_time=1.5, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="chest_west", block_face_textures={"top": "chest_top", "bottom": "planks", "sides": "chest_side", "front": "chest_front"}, break_time=1.5, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="chest_east", block_face_textures={"top": "chest_top", "bottom": "planks", "sides": "chest_side", "front": "chest_front"}, break_time=1.5, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="log_x", block_face_textures={"top": "log_side", "bottom": "log_side", "sides": "log_side"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="log_z", block_face_textures={"top": "log_side", "bottom": "log_side", "sides": "log_side"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_slab_top", block_face_textures={"all": "planks"}, model=models.slab, transparent=True, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="cobblestone_slab_top", block_face_textures={"all": "cobblestone"}, model=models.slab, transparent=True, break_time=1.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="stone_slab_top", block_face_textures={"all": "stone"}, model=models.slab, transparent=True, break_time=1.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_door_top", block_face_textures={"all": "door_wood_upper"}, model=models.door_top, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_door_top_open", block_face_textures={"all": "door_wood_upper"}, model=models.door_top_open, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_door_top", block_face_textures={"all": "iron_door"}, model=models.door_top, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_door_top_open", block_face_textures={"all": "iron_door"}, model=models.door_top_open, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_trapdoor_top", block_face_textures={"all": "trapdoor"}, model=models.trapdoor_top, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_trapdoor_top_open", block_face_textures={"all": "trapdoor"}, model=models.trapdoor_top_open, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_trapdoor_top", block_face_textures={"all": "iron_trapdoor"}, model=models.trapdoor_top, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_trapdoor_top_open", block_face_textures={"all": "iron_trapdoor"}, model=models.trapdoor_top_open, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_stairs_top", block_face_textures={"all": "planks"}, model=models.stairs_top, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="cobblestone_stairs_top", block_face_textures={"all": "cobblestone"}, model=models.stairs_top, transparent=True, break_time=1.2, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_fence_gate", block_face_textures={"all": "planks"}, model=models.fence_gate, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oak_fence_gate_open", block_face_textures={"all": "planks"}, model=models.fence_gate_open, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="gravel", block_face_textures={"all": "gravel"}, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="fire", block_face_textures={"all": "fire"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="torch", block_face_textures={"top": "torch_top", "bottom": "torch", "sides": "torch"}, model=models.torch, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="farmland", block_face_textures={"top": "soil", "bottom": "dirt", "sides": "dirt"}, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="crops", block_face_textures={"all": "crops"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="mossy_cobblestone", block_face_textures={"all": "mossy_cobblestone"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="white_wool", block_face_textures={"all": "white_cloth"}, break_time=0.8, requires_tool=False))

		# Nether Blocks & Nether Portal (84-89)
		self.block_types.append(block_type.Block_type(self.texture_manager, name="netherrack", block_face_textures={"all": "netherrack"}, break_time=0.4, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="soul_sand", block_face_textures={"all": "soul_sand"}, break_time=0.5, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="glowstone", block_face_textures={"all": "glowstone"}, break_time=0.3, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="nether_quartz_ore", block_face_textures={"all": "quartz_ore"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="nether_portal_x", block_face_textures={"all": "portal"}, model=models.portal_x, transparent=True, break_time=float('inf'), requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="nether_portal_z", block_face_textures={"all": "portal"}, model=models.portal_z, transparent=True, break_time=float('inf'), requires_tool=False))

		# Nether Fortress Blocks (90-95)
		self.block_types.append(block_type.Block_type(self.texture_manager, name="nether_brick", block_face_textures={"all": "nether_brick"}, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="nether_brick_fence", block_face_textures={"all": "nether_brick"}, model=models.fence, transparent=True, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="nether_brick_stairs", block_face_textures={"all": "nether_brick"}, model=models.stairs, transparent=True, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="nether_brick_stairs_top", block_face_textures={"all": "nether_brick"}, model=models.stairs_top, transparent=True, break_time=2.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="nether_wart", block_face_textures={"all": "nether_wart_stage_2"}, model=models.plant, transparent=True, break_time=0.1, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="nether_brick_slab", block_face_textures={"all": "nether_brick"}, model=models.slab, transparent=True, break_time=2.0, requires_tool=True))

		# Stronghold Blocks (96-99)
		self.block_types.append(block_type.Block_type(self.texture_manager, name="stone_brick", block_face_textures={"all": "stonebrick"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="mossy_stone_brick", block_face_textures={"all": "stonebrick_mossy"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="cracked_stone_brick", block_face_textures={"all": "stonebrick_cracked"}, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_bars", block_face_textures={"all": "iron_bars"}, model=models.iron_bars, transparent=True, break_time=5.0, requires_tool=True))

		# Pad slots 100..177 with placeholder Block_types so block_id index lookups are always valid
		while len(self.block_types) < 178:
			curr_id = len(self.block_types)
			self.block_types.append(block_type.Block_type(self.texture_manager, name=f"item_{curr_id}", block_face_textures={"all": "stonebrick"}, transparent=True, break_time=1.0, requires_tool=False))

		# Stone Brick Stairs & Slabs, End Portal Frames & Portal (178-187)
		self.block_types.append(block_type.Block_type(self.texture_manager, name="stone_brick_stairs", block_face_textures={"all": "stonebrick"}, model=models.stairs, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="stone_brick_stairs_top", block_face_textures={"all": "stonebrick"}, model=models.stairs_top, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="stone_brick_slab", block_face_textures={"all": "stonebrick"}, model=models.slab, transparent=True, break_time=1.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="end_portal_frame", block_face_textures={"top": "endframe_top", "bottom": "end_stone", "sides": "endframe_side"}, model=models.end_portal_frame, transparent=True, break_time=float('inf'), requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="end_portal_frame_filled", block_face_textures={"top": "endframe_top", "bottom": "end_stone", "sides": "endframe_side", "eye": "endframe_eye"}, model=models.end_portal_frame, transparent=True, break_time=float('inf'), requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="end_portal", block_face_textures={"all": "portal"}, model=models.end_portal, transparent=True, break_time=float('inf'), requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="infested_stone_brick", block_face_textures={"all": "stonebrick"}, break_time=0.75, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="infested_mossy_stone_brick", block_face_textures={"all": "stonebrick_mossy"}, break_time=0.75, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="infested_cracked_stone_brick", block_face_textures={"all": "stonebrick_cracked"}, break_time=0.75, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="infested_stone", block_face_textures={"all": "stone"}, break_time=0.75, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="end_stone", block_face_textures={"all": "end_stone"}, break_time=3.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dragon_egg", block_face_textures={"all": "obsidian"}, model=models.cube, transparent=True, break_time=3.0, requires_tool=False))

		import gui
		for item_id, item_name, tex_name in gui.ALL_ITEMS:
			self.texture_manager.add_texture(tex_name)

		self.texture_manager.add_texture("fire")
		self.texture_manager.add_texture("portal")
		self.texture_manager.add_texture("netherrack")
		self.texture_manager.add_texture("soul_sand")
		self.texture_manager.add_texture("glowstone")
		self.texture_manager.add_texture("quartz_ore")
		self.texture_manager.add_texture("nether_brick")
		self.texture_manager.add_texture("nether_wart_stage_2")
		self.texture_manager.add_texture("stonebrick")
		self.texture_manager.add_texture("stonebrick_mossy")
		self.texture_manager.add_texture("stonebrick_cracked")
		self.texture_manager.add_texture("iron_bars")
		self.texture_manager.add_texture("endframe_top")
		self.texture_manager.add_texture("endframe_side")
		self.texture_manager.add_texture("endframe_eye")
		self.texture_manager.add_texture("end_stone")
		self.texture_manager.add_texture("sun")
		self.texture_manager.add_texture("moon")
		self.texture_manager.generate_mipmaps()

		self.chunks = {}
		self.scale = 500.0
		self.octaves = 4
		self.persistence = 0.5
		self.lacunarity = 2.5
		self.cave_scale = 15.0
		self.cave_threshold = 0.1

		self.render_distance = max(2, min(12, render_distance))
		self.unload_distance = self.render_distance + 3
		self.dirty_chunks = set()
		self._last_player_chunk = None
		self._load_queue = []

		os.makedirs(self.save_dir, exist_ok=True)

		# Multithreaded Executor (3 Workers) balanced to eliminate GIL contention with main Pyglet render loop
		self.process_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ChunkWorker")
		self.chunk_generation_futures = {}
		self.section_mesh_futures = {}

		self._save_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ChunkSaver")
		self.free_chunk_pool = []  # Deferred handle recycling pool

		self.pending_section_uploads = []
		self.section_mesh_queue = set()

		self.liquid_levels = {}
		self.water_levels = {}
		self.liquid_tick_queue = set()
		self.liquid_tick_timer = 0.0
		self.lava_tick_timer = 0.0
		self.gravity_tick_queue = set()
		self.gravity_tick_timer = 0.0
		self.active_fires = {}      # (x, y, z) -> remaining_seconds (for standalone Fire block ID 78)
		self.burning_blocks = {}    # (x, y, z) -> {'timer': remaining_seconds, 'faces': set([face_idx])} (for masked side face fire)
		self._block_info_cache = None

	def schedule_mesh_update(self, position):
		x, y, z = position
		if y < 0 or y >= 256:
			return
		cx = math.floor(x / chunk.CHUNK_WIDTH)
		cz = math.floor(z / chunk.CHUNK_LENGTH)
		sy = int(y) // 16
		self.section_mesh_queue.add((cx, cz, sy))
		self.dirty_chunks.add((cx, 0, cz))

	def set_fire(self, position, duration=9.0):
		"""Places a Fire block (78) on top of a solid surface that burns for 8-10s."""
		self.set_block(position, 78)
		self.active_fires[tuple(position)] = duration

	def ignite_block_face(self, position, face_idx=None, duration=9.0):
		"""Masks the lateral side faces (0, 1, 4, 5) of an existing block with fire texture for 8-10s (excludes top & bottom)."""
		p_key = tuple(position)
		if face_idx is None or face_idx in ("ALL", "SIDES", "ALL_SIDES"):
			target_faces = {0, 1, 4, 5}  # Lateral side faces only (East, West, South, North)
		elif isinstance(face_idx, int):
			target_faces = {face_idx}
		else:
			target_faces = set(face_idx)

		if p_key not in self.burning_blocks:
			self.burning_blocks[p_key] = {'timer': duration, 'faces': target_faces}
		else:
			self.burning_blocks[p_key]['faces'].update(target_faces)
			self.burning_blocks[p_key]['timer'] = max(self.burning_blocks[p_key]['timer'], duration)
		self.schedule_mesh_update(position)

	def extinguish_block(self, position):
		"""Extinguishes a Fire block (78) or side fire overlay on a burning block."""
		p_key = tuple(position)
		extinguished = False
		if p_key in self.active_fires or self.get_block_number(p_key) == 78:
			self.set_block(p_key, 0)
			self.active_fires.pop(p_key, None)
			extinguished = True
		if p_key in self.burning_blocks:
			self.burning_blocks.pop(p_key, None)
			self.schedule_mesh_update(p_key)
			extinguished = True
		return extinguished

	def get_single_chest(self, pos):
		p_key = (int(pos[0]), int(pos[1]), int(pos[2]))
		if p_key not in self.chests:
			self.chests[p_key] = ChestData()
		return self.chests[p_key]

	def get_chest_info(self, pos):
		px, py, pz = int(pos[0]), int(pos[1]), int(pos[2])
		main_key = (px, py, pz)
		main_chest = self.get_single_chest(main_key)

		# Check 4 horizontal neighbors at same Y height for an adjacent chest block (37)
		for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
			adj_key = (px + dx, py, pz + dz)
			if self.get_block_number(adj_key) == 37:
				adj_chest = self.get_single_chest(adj_key)
				if main_key < adj_key:
					return (True, main_chest, adj_chest)
				else:
					return (True, adj_chest, main_chest)

		return (False, main_chest, None)

	def get_furnace(self, pos):
		p_key = (int(pos[0]), int(pos[1]), int(pos[2]))
		if p_key not in self.furnaces:
			self.furnaces[p_key] = FurnaceData()
		return self.furnaces[p_key]

	def update(self, dt):
		self.liquid_tick_timer += dt
		self.lava_tick_timer += dt

		# Water flow step timer: 0.15s (~6.6 Hz, 1 block step per 0.15s)
		tick_water = False
		if self.liquid_tick_timer >= 0.15:
			self.liquid_tick_timer = 0.0
			tick_water = True

		# Lava flow step timer: 0.30s (~3.3 Hz, half the speed of water!)
		tick_lava = False
		if self.lava_tick_timer >= 0.30:
			self.lava_tick_timer = 0.0
			tick_lava = True

		if tick_water or tick_lava:
			self.tick_liquids(dt, tick_water=tick_water, tick_lava=tick_lava)

		self.gravity_tick_timer += dt
		if self.gravity_tick_timer >= 0.16:  # ~6.25 Hz (visibly slower, smooth sand & gravel falling)
			self.gravity_tick_timer = 0.0
			self.tick_gravity_blocks()

		# Update active fire blocks (Block ID 78) - disappear after 8-10s
		for pos, rem_time in list(self.active_fires.items()):
			new_time = rem_time - dt
			if new_time <= 0.0:
				if self.get_block_number(pos) == 78:
					self.set_block(pos, 0)
				self.active_fires.pop(pos, None)
			else:
				self.active_fires[pos] = new_time
				# Ignite adjacent TNT blocks (25)
				px, py, pz = pos
				for n_pos in ((px+1, py, pz), (px-1, py, pz), (px, py-1, pz), (px, py+1, pz), (px, py, pz+1), (px, py, pz-1)):
					if self.get_block_number(n_pos) == 25:
						self.set_block(n_pos, 0)
						if hasattr(self, "tnt_manager") and self.tnt_manager:
							self.tnt_manager.spawn_primed_tnt(
								(n_pos[0] + 0.5, n_pos[1], n_pos[2] + 0.5),
								fuse_ticks=random.randint(10, 30)
							)

		# Update burning block side overlays - disappear after 8-10s
		for pos, data in list(self.burning_blocks.items()):
			data['timer'] -= dt
			if data['timer'] <= 0.0:
				self.burning_blocks.pop(pos, None)
				self.schedule_mesh_update(pos)

		for furnace in list(self.furnaces.values()):
			furnace.tick(dt)

	def get_block_types_info(self):
		if self._block_info_cache is None:
			info = {}
			for idx, b in enumerate(self.block_types):
				if b is None:
					continue
				info[idx] = {
					'name': b.name,
					'is_cube': b.is_cube,
					'transparent': b.transparent,
					'translucent': b.translucent or b.name in ('water', 'under_water'),
					'vertex_positions': b.vertex_positions,
					'tex_coords': b.tex_coords,
					'shading_values': b.shading_values,
				}
			self._block_info_cache = info
		return self._block_info_cache

	def set_render_distance(self, new_rd):
		self.render_distance = max(2, min(12, new_rd))
		self.unload_distance = self.render_distance + 3
		self._load_queue.clear()

		for x in range(-2, 3):
			for z in range(-2, 3):
				cpos = (x, 0, z)
				if cpos not in self.chunks:
					chk_bytes = self.generate_chunk(x, z, blocks_only=True)
					self.chunks[cpos] = chunk.Chunk(self, cpos, blocks=chk_bytes)

		info = self.get_block_types_info()
		for cpos, chk in list(self.chunks.items()):
			cx, _, cz = cpos
			c_bytes = bytes(chk.blocks)
			e_bytes = bytes(self.chunks[(cx + 1, 0, cz)].blocks) if (cx + 1, 0, cz) in self.chunks else None
			w_bytes = bytes(self.chunks[(cx - 1, 0, cz)].blocks) if (cx - 1, 0, cz) in self.chunks else None
			s_bytes = bytes(self.chunks[(cx, 0, cz + 1)].blocks) if (cx, 0, cz + 1) in self.chunks else None
			n_bytes = bytes(self.chunks[(cx, 0, cz - 1)].blocks) if (cx, 0, cz - 1) in self.chunks else None

			for sy in range(16):
				b_blocks = {
					(int(pos[0] % 16), int(pos[1]), int(pos[2] % 16)): list(data['faces'])
					for pos, data in self.burning_blocks.items()
					if math.floor(pos[0] / 16) == cx and math.floor(pos[2] / 16) == cz and (pos[1] // 16) == sy
				} if self.burning_blocks else None
				res = build_section_mesh_process(cx, cz, sy, c_bytes, n_bytes, s_bytes, e_bytes, w_bytes, info, dict(self.water_levels), dict(self.lava_levels), burning_blocks=b_blocks)
				_, _, _, op_pos, op_tex, op_shd, op_idx, tr_pos, tr_tex, tr_shd, tr_idx, missing = res
				chk.send_section_mesh_to_gpu(sy, op_pos, op_tex, op_shd, op_idx, tr_pos, tr_tex, tr_shd, tr_idx)

	def generate_chunk(self, x, z, blocks_only=False):
		chunk_position = (x, 0, z)
		if self.dimension == "nether":
			blocks = build_nether_chunk_blocks_process(x, z, self.save_dir, self.seed)
		elif self.dimension == "end":
			blocks = build_end_chunk_blocks_process(x, z, self.save_dir, self.seed)
		else:
			blocks = build_chunk_blocks_process(
				x, z, self.scale, self.octaves, self.persistence, self.lacunarity,
				self.cave_scale, self.cave_threshold, self.save_dir, self.seed)

		if self.dimension not in ("nether", "end"):
			# Register any village chests generated in this chunk
			try:
				import village
				_, _, v_chests = village.get_village_blocks_for_chunk(x, z, self.seed)
				if v_chests:
					for pos_key, slots in v_chests.items():
						if pos_key not in self.chests:
							c_obj = ChestData()
							c_obj.slots = [list(s) for s in slots]
							self.chests[pos_key] = c_obj
			except Exception:
				pass

		if blocks_only:
			return blocks
		return chunk.Chunk(self, chunk_position, blocks=blocks)

	def queue_chunk_sections_for_meshing(self, cx, cz):
		c_pos = (cx, 0, cz)
		if c_pos not in self.chunks:
			return
		chk = self.chunks[c_pos]
		blocks = chk.blocks
		for sy in range(16):
			min_y = sy * 16
			# Fast slice check over 16 columns (microseconds instead of 4096 iterations)
			has_blocks = False
			for x in range(16):
				start_idx = x * 4096 + min_y * 16
				if any(blocks[start_idx : start_idx + 256]):
					has_blocks = True
					break

			if has_blocks:
				self.section_mesh_queue.add((cx, cz, sy))

	def process_load_queue(self, player_position=(0, 0, 0), player_rotation=None):
		player_cx = math.floor(player_position[0] / chunk.CHUNK_WIDTH)
		player_cz = math.floor(player_position[2] / chunk.CHUNK_LENGTH)

		yaw = player_rotation[0] if player_rotation is not None else -math.tau / 4
		look_x = math.cos(yaw)
		look_z = math.sin(yaw)

		# 1. Collect completed section meshing tasks
		for sec_key in list(self.section_mesh_futures.keys()):
			fut = self.section_mesh_futures[sec_key]
			if fut.done():
				del self.section_mesh_futures[sec_key]
				try:
					result = fut.result()
					if result:
						self.pending_section_uploads.append(result)
				except Exception as e:
					print(f"Section mesh task failed for {sec_key}: {e}")

		# 2. Budgeted GPU Uploads (capped at 32 KB per frame tick for smooth 60 FPS)
		MAX_GPU_UPLOAD_BYTES_PER_FRAME = 32 * 1024
		uploaded_bytes = 0

		if self.pending_section_uploads:
			def upload_priority(item):
				cx, cz, sy = item[0], item[1], item[2]
				dx = (cx * 16 + 8) - player_position[0]
				dz = (cz * 16 + 8) - player_position[2]
				dist_sq = dx * dx + dz * dz
				dot = dx * look_x + dz * look_z
				return dist_sq + (0.0 if dot >= 0 else 2000.0)

			self.pending_section_uploads.sort(key=upload_priority)

		while self.pending_section_uploads:
			item = self.pending_section_uploads[0]
			cx, cz, sy, op_pos, op_tex, op_shd, op_idx, tr_pos, tr_tex, tr_shd, tr_idx, missing = item
			sec_bytes = len(op_pos) + len(op_tex) + len(op_shd) + len(op_idx) + len(tr_pos) + len(tr_tex) + len(tr_shd) + len(tr_idx)

			if uploaded_bytes > 0 and (uploaded_bytes + sec_bytes > MAX_GPU_UPLOAD_BYTES_PER_FRAME):
				break  # Defer remaining uploads to subsequent frames to preserve 60-80 FPS

			self.pending_section_uploads.pop(0)

			c_pos = (cx, 0, cz)
			if c_pos in self.chunks:
				chk = self.chunks[c_pos]
				chk.send_section_mesh_to_gpu(sy, op_pos, op_tex, op_shd, op_idx, tr_pos, tr_tex, tr_shd, tr_idx)
				chk.had_missing_neighbors = missing

			uploaded_bytes += max(1024, sec_bytes)

		# 3. Submit pending section meshing tasks (max 2 active workers to prevent GIL contention)
		if len(self.section_mesh_futures) < 2 and self.section_mesh_queue:
			slots_free = 2 - len(self.section_mesh_futures)
			pending_list = list(self.section_mesh_queue)
			if len(pending_list) > 1:
				def mesh_priority(item):
					cx, cz, sy = item[0], item[1], item[2]
					dx = (cx * 16 + 8) - player_position[0]
					dz = (cz * 16 + 8) - player_position[2]
					dist_sq = dx * dx + dz * dz
					dot = dx * look_x + dz * look_z
					return dist_sq + (0.0 if dot >= 0 else 2000.0)

				pending_list.sort(key=mesh_priority)

			info = self.get_block_types_info()

			for item in pending_list[:slots_free]:
				if item in self.section_mesh_queue:
					self.section_mesh_queue.remove(item)
				cx, cz, sy = item

				c_pos = (cx, 0, cz)
				if c_pos not in self.chunks:
					continue

				center_chk = self.chunks[c_pos]
				c_bytes = center_chk.blocks
				c_states = { f"{lx},{ly},{lz}": st.to_dict() for (lx, ly, lz), st in center_chk.block_states.items() if st } if center_chk.block_states else None

				e_bytes = self.chunks[(cx + 1, 0, cz)].blocks if (cx + 1, 0, cz) in self.chunks else None
				w_bytes = self.chunks[(cx - 1, 0, cz)].blocks if (cx - 1, 0, cz) in self.chunks else None
				s_bytes = self.chunks[(cx, 0, cz + 1)].blocks if (cx, 0, cz + 1) in self.chunks else None
				n_bytes = self.chunks[(cx, 0, cz - 1)].blocks if (cx, 0, cz - 1) in self.chunks else None

				w_lvls = {pos: lvl for pos, lvl in self.water_levels.items() if abs(pos[0] - (cx * 16 + 8)) <= 24 and abs(pos[2] - (cz * 16 + 8)) <= 24} if self.water_levels else None
				l_lvls = {pos: lvl for pos, lvl in self.liquid_levels.items() if abs(pos[0] - (cx * 16 + 8)) <= 24 and abs(pos[2] - (cz * 16 + 8)) <= 24} if self.liquid_levels else None
				b_blocks = {
					(int(pos[0] % 16), int(pos[1]), int(pos[2] % 16)): list(data['faces'])
					for pos, data in self.burning_blocks.items()
					if math.floor(pos[0] / 16) == cx and math.floor(pos[2] / 16) == cz and (pos[1] // 16) == sy
				} if self.burning_blocks else None

				self.section_mesh_futures[(cx, cz, sy)] = self.process_executor.submit(
					build_section_mesh_process,
					cx, cz, sy, c_bytes, n_bytes, s_bytes, e_bytes, w_bytes, info, w_lvls, l_lvls, c_states, b_blocks
				)

	def get_chunk_position(self, position):
		x, y, z = position
		return (math.floor(x / chunk.CHUNK_WIDTH), 0, math.floor(z / chunk.CHUNK_LENGTH))

	def get_local_position(self, position):
		x, y, z = position
		return (int(x % chunk.CHUNK_WIDTH), int(y % chunk.CHUNK_HEIGHT), int(z % chunk.CHUNK_LENGTH))

	def get_block_number(self, position):
		x, y, z = position
		if y < 0 or y >= 256:
			return 0
		chunk_position = (math.floor(x / chunk.CHUNK_WIDTH), 0, math.floor(z / chunk.CHUNK_LENGTH))
		chk = self.chunks.get(chunk_position)
		if chk is None:
			return 0
		lx = int(x % chunk.CHUNK_WIDTH)
		ly = int(y)
		lz = int(z % chunk.CHUNK_LENGTH)
		return chk.get_block_number(lx, ly, lz)

	def get_block_state(self, position):
		x, y, z = position
		if y < 0 or y >= 256:
			return None
		chunk_position = (math.floor(x / chunk.CHUNK_WIDTH), 0, math.floor(z / chunk.CHUNK_LENGTH))
		chk = self.chunks.get(chunk_position)
		if chk is None:
			return None
		lx = int(x % chunk.CHUNK_WIDTH)
		ly = int(y)
		lz = int(z % chunk.CHUNK_LENGTH)
		return chk.get_block_state(lx, ly, lz)

	def set_block_state(self, position, state):
		x, y, z = position
		if y < 0 or y >= 256:
			return
		c_pos = (math.floor(x / chunk.CHUNK_WIDTH), 0, math.floor(z / chunk.CHUNK_LENGTH))
		if c_pos not in self.chunks:
			if state is None: return
			self.chunks[c_pos] = self.generate_chunk(c_pos[0], c_pos[2])
		chk = self.chunks[c_pos]
		lx = int(x % chunk.CHUNK_WIDTH)
		ly = int(y)
		lz = int(z % chunk.CHUNK_LENGTH)

		chk.set_block_state(lx, ly, lz, state)
		self.dirty_chunks.add(c_pos)

		sy = ly // 16
		self.section_mesh_queue.add((c_pos[0], c_pos[2], sy))
		if ly % 16 == 0 and sy > 0: self.section_mesh_queue.add((c_pos[0], c_pos[2], sy - 1))
		if ly % 16 == 15 and sy < 15: self.section_mesh_queue.add((c_pos[0], c_pos[2], sy + 1))
		if lx == 15: self.section_mesh_queue.add((c_pos[0] + 1, c_pos[2], sy))
		if lx == 0: self.section_mesh_queue.add((c_pos[0] - 1, c_pos[2], sy))
		if lz == 15: self.section_mesh_queue.add((c_pos[0], c_pos[2] + 1, sy))
		if lz == 0: self.section_mesh_queue.add((c_pos[0], c_pos[2] - 1, sy))

		self.notify_neighbor_block_change(position)

	def notify_neighbor_block_change(self, position):
		"""Recalculates state for neighboring stairs, fences, walls, panes, and doors whenever a block changes."""
		import block_state
		px, py, pz = position
		for dx, dy, dz in [(1,0,0), (-1,0,0), (0,1,0), (0,-1,0), (0,0,1), (0,0,-1)]:
			nb_pos = (px + dx, py + dy, pz + dz)
			nb_b = self.get_block_number(nb_pos)
			if nb_b == 0: continue
			nb_st = self.get_block_state(nb_pos)

			# 1. Stairs shape recalculation
			if nb_b in (41, 42, 73, 74, 92, 93):
				if not nb_st:
					nb_st = block_state.BlockState(nb_b)
				new_shape = block_state.calculate_stair_shape(self, nb_pos, nb_st.facing, nb_st.half)
				if new_shape != nb_st.shape:
					nb_st.shape = new_shape
					self.set_block_state(nb_pos, nb_st)

			# 2. Fence connection recalculation
			elif nb_b in (51, 91):
				if not nb_st:
					nb_st = block_state.BlockState(nb_b)
				new_conn = block_state.calculate_fence_connections(self, nb_pos, nb_b)
				if new_conn != nb_st.connections:
					nb_st.connections = new_conn
					self.set_block_state(nb_pos, nb_st)

			# 3. Wall connection recalculation
			elif nb_b in (52,):
				if not nb_st:
					nb_st = block_state.BlockState(52)
				new_conn = block_state.calculate_wall_connections(self, nb_pos, nb_b)
				if new_conn != nb_st.connections:
					nb_st.connections = new_conn
					self.set_block_state(nb_pos, nb_st)

			# 4. Pane connection recalculation
			elif nb_b in (53,):
				if not nb_st:
					nb_st = block_state.BlockState(53)
				new_conn = block_state.calculate_pane_connections(self, nb_pos, nb_b)
				if new_conn != nb_st.connections:
					nb_st.connections = new_conn
					self.set_block_state(nb_pos, nb_st)

		# Check if block directly above is a gravity block (sand/gravel) needing to fall
		above_pos = (int(px), int(py + 1), int(pz))
		if py + 1 < chunk.CHUNK_HEIGHT and self.get_block_number(above_pos) in (6, 77):
			if self.is_passable_for_gravity(position):
				self.gravity_tick_queue.add(above_pos)

	def is_passable_for_gravity(self, pos):
		"""Returns True if a falling sand/gravel block can fall into this position."""
		x, y, z = pos
		if y < 1 or y >= chunk.CHUNK_HEIGHT:
			return False
		b_num = self.get_block_number(pos)
		return b_num == 0 or b_num in (9, 19, 15, 20, 10, 12, 31, 33, 78, 88, 89, 183)

	def check_and_activate_end_portal(self, frame_pos):
		"""
		Checks if the frame block at frame_pos is part of a complete 5x5 End Portal ring (12 filled frames).
		If all 12 frames contain Eyes of Ender (block ID 182), creates the 9 3x3 central End Portal blocks (183).
		Returns True if activated, False otherwise.
		"""
		fx, fy, fz = int(frame_pos[0]), int(frame_pos[1]), int(frame_pos[2])

		# Potential 3x3 portal center offsets from the clicked frame block
		for off_x in (-2, -1, 0, 1, 2):
			for off_z in (-2, -1, 0, 1, 2):
				cx = fx + off_x
				cz = fz + off_z

				# Verify 12 frame positions in the 5x5 square around (cx, cz)
				frame_coords = [
					(cx - 1, fy, cz - 2), (cx, fy, cz - 2), (cx + 1, fy, cz - 2), # North
					(cx - 1, fy, cz + 2), (cx, fy, cz + 2), (cx + 1, fy, cz + 2), # South
					(cx - 2, fy, cz - 1), (cx - 2, fy, cz), (cx - 2, fy, cz + 1), # West
					(cx + 2, fy, cz - 1), (cx + 2, fy, cz), (cx + 2, fy, cz + 1), # East
				]

				# Frame that was clicked must be one of these 12
				if (fx, fy, fz) not in frame_coords:
					continue

				# Check if all 12 positions are filled End Portal Frames (182)
				all_filled = all(self.get_block_number(coord) == 182 for coord in frame_coords)
				if all_filled:
					# Create 9 End Portal blocks (183) in 3x3 center
					for dx in (-1, 0, 1):
						for dz in (-1, 0, 1):
							p_pos = (cx + dx, fy, cz + dz)
							if self.get_block_number(p_pos) != 183:
								self.set_block(p_pos, 183)
					return True
		return False

	def tick_gravity_blocks(self):
		"""Simulates gravity for Sand (6) and Gravel (77) blocks."""
		if not self.gravity_tick_queue:
			return

		# Sort by Y ascending: lowest blocks fall first to ensure natural cascading
		current_queue = sorted(self.gravity_tick_queue, key=lambda p: p[1])
		self.gravity_tick_queue.clear()
		next_queue = set()

		for pos in current_queue:
			x, y, z = int(pos[0]), int(pos[1]), int(pos[2])
			if y <= 1 or y >= chunk.CHUNK_HEIGHT:
				continue

			b_num = self.get_block_number((x, y, z))
			if b_num not in (6, 77):
				continue

			down_pos = (x, y - 1, z)
			if self.is_passable_for_gravity(down_pos):
				b_st = self.get_block_state((x, y, z))
				down_b = self.get_block_number(down_pos)

				# If falling onto plants/flowers/snow, drop them as item
				if down_b in (10, 12, 31, 33) and self.item_drop_manager:
					self.item_drop_manager.spawn_drop(down_b, 1, [x + 0.5, y - 0.5, z + 0.5])

				# Move block downward
				self.set_block((x, y, z), 0)
				self.set_block(down_pos, b_num)
				if b_st:
					self.set_block_state(down_pos, b_st)

				# Continue falling if space below is also passable
				if y - 1 > 1 and self.is_passable_for_gravity((x, y - 2, z)):
					next_queue.add(down_pos)

				# Queue any sand/gravel directly above to fall next
				above_pos = (x, y + 1, z)
				if y + 1 < chunk.CHUNK_HEIGHT and self.get_block_number(above_pos) in (6, 77):
					next_queue.add(above_pos)

		if next_queue:
			self.gravity_tick_queue.update(next_queue)

	def is_opaque_block(self, position):
		b_num = self.get_block_number(position)
		if not b_num:
			return False
		return not self.block_types[b_num].transparent

	def get_water_level(self, pos):
		b_num = self.get_block_number(pos)
		if b_num == 9: return 0
		if b_num == 19: return self.water_levels.get(pos, 1)
		return -1

	def get_lava_level(self, pos):
		b_num = self.get_block_number(pos)
		if b_num == 15: return 0
		if b_num == 20: return self.liquid_levels.get(pos, 1)
		return -1

	def can_liquid_flow_into(self, pos, is_water):
		x, y, z = pos
		if y < 1 or y >= 255:
			return False
		b_num = self.get_block_number(pos)
		if b_num == 0 or b_num in (10, 12, 31, 33):
			return True
		if is_water:
			return b_num in (15, 20) or b_num == 19
		else:
			return b_num in (9, 19) or b_num == 20

	def is_downward_flow_open(self, pos, is_water):
		x, y, z = pos
		if y <= 1: return False
		down_b = self.get_block_number((x, y - 1, z))
		passable = (0, 10, 12, 31, 33)
		if down_b in passable:
			return True
		if is_water:
			if down_b in (15, 20): return True
			if down_b == 19:
				down_lvl = self.water_levels.get((x, y - 1, z), 1)
				if down_lvl == 8: return True
				below_down_b = self.get_block_number((x, y - 2, z))
				return below_down_b in passable
		else:
			if down_b in (9, 19): return True
			if down_b == 20:
				down_lvl = self.liquid_levels.get((x, y - 1, z), 1)
				if down_lvl == 4: return True
				below_down_b = self.get_block_number((x, y - 2, z))
				return below_down_b in passable
		return False

	def get_flow_directions(self, pos, is_water, is_source=False):
		"""Determines cardinal flow direction(s) based on vertical priority and slope-seeking using unified BFS."""
		x, y, z = pos
		max_dist = 4 if is_water else 2

		# 1. Filter valid open cardinal neighbors
		open_dirs = []
		for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
			n_pos = (x + dx, y, z + dz)
			if self.can_liquid_flow_into(n_pos, is_water):
				open_dirs.append(((dx, dz), n_pos))

		if not open_dirs:
			return []

		# 2. Fast-path: Immediate drop-off check on direct neighbors (distance = 1)
		immediate_drops = []
		for d_pair, n_pos in open_dirs:
			if self.is_downward_flow_open(n_pos, is_water):
				immediate_drops.append(d_pair)

		if immediate_drops:
			return immediate_drops

		# 3. Single unified multi-source BFS to find nearest drop-off within max_dist
		queue = collections.deque()
		visited = {(x, z)}

		for idx, (d_pair, n_pos) in enumerate(open_dirs):
			nx, nz = n_pos[0], n_pos[2]
			visited.add((nx, nz))
			queue.append((nx, nz, 1, idx))

		min_dist = 999
		winning_dirs = set()

		while queue:
			cx, cz, dist, dir_idx = queue.popleft()
			if dist > min_dist:
				break

			if self.is_downward_flow_open((cx, y, cz), is_water):
				if dist < min_dist:
					min_dist = dist
					winning_dirs = {open_dirs[dir_idx][0]}
				elif dist == min_dist:
					winning_dirs.add(open_dirs[dir_idx][0])
				continue

			if dist >= max_dist:
				continue

			for ddx, ddz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
				nx, nz = cx + ddx, cz + ddz
				if (nx, nz) not in visited:
					visited.add((nx, nz))
					if self.can_liquid_flow_into((nx, y, nz), is_water):
						queue.append((nx, nz, dist + 1, dir_idx))

		if winning_dirs:
			return list(winning_dirs)

		# Flat surface: flow in all unobstructed directions
		return [d_pair for d_pair, _ in open_dirs]

	def tick_liquids(self, dt=0.0, tick_water=True, tick_lava=True):
		"""Official Minecraft Water & Lava 1:1 Flow & Slope Simulation Engine (1 block step per tick)."""
		if not self.liquid_tick_queue:
			return

		# Snapshot current batch so that newly spawned flow advances on subsequent ticks (1 block step per tick)
		current_batch = list(self.liquid_tick_queue)
		self.liquid_tick_queue.clear()
		created_this_tick = set()

		for pos in current_batch:
			if pos in created_this_tick:
				continue

			x, y, z = pos
			if y <= 1 or y >= 255:
				continue

			b_num = self.get_block_number(pos)
			if b_num not in (9, 19, 15, 20, 0):
				continue

			# If this is water (9, 19) but water is not ticking this cycle, re-queue and skip
			if b_num in (9, 19) and not tick_water:
				self.liquid_tick_queue.add(pos)
				continue

			# If this is lava (15, 20) but lava is not ticking this cycle, re-queue and skip
			if b_num in (15, 20) and not tick_lava:
				self.liquid_tick_queue.add(pos)
				continue

			# If this is air (0), only tick if water is ticking
			if b_num == 0 and not tick_water:
				self.liquid_tick_queue.add(pos)
				continue

			# --- 1. WATER SOURCE (9) OR FLOWING WATER (19) ---
			if b_num in (9, 19):
				is_source = (b_num == 9)
				cur_lvl = 0 if is_source else self.water_levels.get(pos, 1)

				# Infinite Water Source creation (e.g. 2 adjacent sources merge on flowing water or air with solid/water floor below)
				if not is_source:
					source_count = 0
					for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
						if self.get_block_number((x + dx, y, z + dz)) == 9:
							source_count += 1

					down_num = self.get_block_number((x, y - 1, z))
					is_solid_or_source = (down_num == 9) or (down_num != 0 and down_num not in (9, 19, 15, 20, 10, 12, 31, 33))

					if source_count >= 2 and is_solid_or_source:
						self.set_block(pos, 9)
						self.water_levels[pos] = 0
						created_this_tick.add(pos)
						is_source = True
						cur_lvl = 0
						self.liquid_tick_queue.add(pos)
						for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
							self.liquid_tick_queue.add((x + dx, y, z + dz))

				# If flowing water, check if it still has valid upstream source/flow
				if not is_source:
					above_b = self.get_block_number((x, y + 1, z))
					if above_b in (9, 19):
						# Falling water from above
						self.water_levels[pos] = 8
						cur_lvl = 8
					else:
						# If it was a falling water column (level 8) and water above is gone, drain immediately!
						if cur_lvl == 8:
							self.set_block(pos, 0)
							self.water_levels.pop(pos, None)
							created_this_tick.add(pos)
							for dx, dy, dz in ((0,-1,0),(0,1,0),(1,0,0),(-1,0,0),(0,0,1),(0,0,-1)):
								self.liquid_tick_queue.add((x + dx, y + dy, z + dz))
							continue

						# Find upstream neighbors
						upstream = []
						for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
							nx, nz = x + dx, z + dz
							nb_pos = (nx, y, nz)
							nb_num = self.get_block_number(nb_pos)
							if nb_num == 9:
								upstream.append(0)
							elif nb_num == 19:
								nb_lvl = self.water_levels.get(nb_pos, 1)
								if nb_lvl == 8:
									# Only valid upstream source if it has liquid above it and is on the floor (waterfall base)
									if self.get_block_number((nx, y + 1, nz)) in (9, 19) and not self.is_downward_flow_open(nb_pos, is_water=True):
										upstream.append(0)
								elif nb_lvl < cur_lvl:
									upstream.append(nb_lvl)

						if not upstream:
							# No upstream support: drain water
							self.set_block(pos, 0)
							self.water_levels.pop(pos, None)
							created_this_tick.add(pos)
							for dx, dy, dz in ((0,-1,0),(0,1,0),(1,0,0),(-1,0,0),(0,0,1),(0,0,-1)):
								self.liquid_tick_queue.add((x + dx, y + dy, z + dz))
							continue
						else:
							min_u = min(upstream)
							new_lvl = min_u + 1
							if new_lvl > 7:
								self.set_block(pos, 0)
								self.water_levels.pop(pos, None)
								created_this_tick.add(pos)
								for dx, dy, dz in ((0,-1,0),(0,1,0),(1,0,0),(-1,0,0),(0,0,1),(0,0,-1)):
									self.liquid_tick_queue.add((x + dx, y + dy, z + dz))
								continue
							self.water_levels[pos] = new_lvl
							cur_lvl = new_lvl

				# Water + Lava Mixing Check (All 6 directions: 4 horizontal + up + down)
				for dx, dy, dz in ((0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0)):
					nx, ny, nz = x + dx, y + dy, z + dz
					n_pos = (nx, ny, nz)
					nb_num = self.get_block_number(n_pos)
					if nb_num == 15: # Lava Source -> Obsidian
						self.set_block(n_pos, 24)
						created_this_tick.add(n_pos)
					elif nb_num == 20: # Flowing Lava -> Cobblestone
						self.set_block(n_pos, 1)
						created_this_tick.add(n_pos)

				# Spread Downward
				down_pos = (x, y - 1, z)
				down_num = self.get_block_number(down_pos)
				down_is_open = (down_num == 0 or down_num in (10, 12, 31, 33))

				if down_is_open:
					self.set_block(down_pos, 19)
					self.water_levels[down_pos] = 8
					created_this_tick.add(down_pos)
					self.liquid_tick_queue.add(down_pos)
					self.liquid_tick_queue.add((x, y - 2, z))
				elif down_num == 15: # Lava Source below water -> Obsidian
					self.set_block(down_pos, 24)
					created_this_tick.add(down_pos)
				elif down_num == 20: # Flowing Lava below water -> Cobblestone
					self.set_block(down_pos, 1)
					created_this_tick.add(down_pos)

				# Horizontal Spread:
				# 1. Source blocks ALWAYS spread horizontally to open adjacent air blocks.
				# 2. Flowing blocks spread horizontally on solid ground (not dropping down a hole) when level < 7 or waterfall base (level 8).
				can_spread_horizontally = is_source or (not self.is_downward_flow_open(pos, is_water=True) and (cur_lvl < 7 or cur_lvl == 8))

				if can_spread_horizontally:
					flow_dirs = self.get_flow_directions(pos, is_water=True, is_source=is_source)
					for dx, dz in flow_dirs:
						nx, nz = x + dx, z + dz
						n_pos = (nx, y, nz)
						n_num = self.get_block_number(n_pos)
						if n_num == 0 or n_num in (10, 12, 31, 33):
							target_lvl = 1 if is_source or cur_lvl == 8 else cur_lvl + 1
							if target_lvl <= 7:
								self.set_block(n_pos, 19)
								self.water_levels[n_pos] = target_lvl
								created_this_tick.add(n_pos)
								self.liquid_tick_queue.add(n_pos)
								self.liquid_tick_queue.add((nx, y - 1, nz))
						elif n_num == 19:
							# Update existing flowing water if a shorter path reached it
							existing_lvl = self.water_levels.get(n_pos, 1)
							target_lvl = 1 if is_source or cur_lvl == 8 else cur_lvl + 1
							if target_lvl < existing_lvl:
								self.water_levels[n_pos] = target_lvl
								created_this_tick.add(n_pos)
								self.liquid_tick_queue.add(n_pos)
						elif n_num == 15: # Water flows into Lava Source -> Obsidian
							self.set_block(n_pos, 24)
							created_this_tick.add(n_pos)
						elif n_num == 20: # Water flows into Flowing Lava -> Cobblestone
							self.set_block(n_pos, 1)
							created_this_tick.add(n_pos)

			# --- 2. LAVA SOURCE (15) OR FLOWING LAVA (20) ---
			elif b_num in (15, 20):
				is_source = (b_num == 15)
				cur_lvl = 0 if is_source else self.liquid_levels.get(pos, 1)

				# Check if this lava block itself is touching water in any adjacent direction
				touches_water = False
				for dx, dy, dz in ((0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0)):
					if self.get_block_number((x + dx, y + dy, z + dz)) in (9, 19):
						touches_water = True
						break

				if touches_water:
					if is_source:
						self.set_block(pos, 24)  # Lava Source touching Water -> Obsidian
					else:
						self.set_block(pos, 1)   # Flowing Lava touching Water -> Cobblestone
					created_this_tick.add(pos)
					continue

				# If flowing lava, check upstream support
				if not is_source:
					above_b = self.get_block_number((x, y + 1, z))
					if above_b in (15, 20):
						self.liquid_levels[pos] = 4
						cur_lvl = 4
					else:
						# If it was a falling lava column (level 4) and lava above is gone, drain immediately!
						if cur_lvl == 4:
							self.set_block(pos, 0)
							self.liquid_levels.pop(pos, None)
							created_this_tick.add(pos)
							for dx, dy, dz in ((0,-1,0),(0,1,0),(1,0,0),(-1,0,0),(0,0,1),(0,0,-1)):
								self.liquid_tick_queue.add((x + dx, y + dy, z + dz))
							continue

						upstream = []
						for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
							nx, nz = x + dx, z + dz
							nb_pos = (nx, y, nz)
							nb_num = self.get_block_number(nb_pos)
							if nb_num == 15:
								upstream.append(0)
							elif nb_num == 20:
								nb_lvl = self.liquid_levels.get(nb_pos, 1)
								if nb_lvl == 4:
									if self.get_block_number((nx, y + 1, nz)) in (15, 20) and not self.is_downward_flow_open(nb_pos, is_water=False):
										upstream.append(0)
								elif nb_lvl < cur_lvl:
									upstream.append(nb_lvl)

						if not upstream:
							self.set_block(pos, 0)
							self.liquid_levels.pop(pos, None)
							created_this_tick.add(pos)
							for dx, dy, dz in ((0,-1,0),(0,1,0),(1,0,0),(-1,0,0),(0,0,1),(0,0,-1)):
								self.liquid_tick_queue.add((x + dx, y + dy, z + dz))
							continue
						else:
							min_u = min(upstream)
							new_lvl = min_u + 1
							if new_lvl > 3:
								self.set_block(pos, 0)
								self.liquid_levels.pop(pos, None)
								created_this_tick.add(pos)
								for dx, dy, dz in ((0,-1,0),(0,1,0),(1,0,0),(-1,0,0),(0,0,1),(0,0,-1)):
									self.liquid_tick_queue.add((x + dx, y + dy, z + dz))
								continue
							self.liquid_levels[pos] = new_lvl
							cur_lvl = new_lvl

				# Spread Downward
				down_pos = (x, y - 1, z)
				down_num = self.get_block_number(down_pos)
				down_is_open = (down_num == 0 or down_num in (10, 12, 31, 33))

				if down_is_open:
					self.set_block(down_pos, 20)
					self.liquid_levels[down_pos] = 4
					created_this_tick.add(down_pos)
					self.liquid_tick_queue.add(down_pos)
					self.liquid_tick_queue.add((x, y - 2, z))
				elif down_num in (9, 19): # Lava flowing down onto water -> Cobblestone
					self.set_block(down_pos, 1)
					created_this_tick.add(down_pos)

				# Horizontal Spread:
				# 1. Source blocks ALWAYS spread horizontally to open adjacent air blocks.
				# 2. Flowing blocks spread horizontally on solid ground (not dropping down a hole) when level < 3 or lavafall base (level 4).
				can_spread_horizontally = is_source or (not self.is_downward_flow_open(pos, is_water=False) and (cur_lvl < 3 or cur_lvl == 4))

				if can_spread_horizontally:
					flow_dirs = self.get_flow_directions(pos, is_water=False, is_source=is_source)
					for dx, dz in flow_dirs:
						nx, nz = x + dx, z + dz
						n_pos = (nx, y, nz)
						n_num = self.get_block_number(n_pos)
						if n_num == 0 or n_num in (10, 12, 31, 33):
							target_lvl = 1 if is_source or cur_lvl == 4 else cur_lvl + 1
							if target_lvl <= 3:
								self.set_block(n_pos, 20)
								self.liquid_levels[n_pos] = target_lvl
								created_this_tick.add(n_pos)
								self.liquid_tick_queue.add(n_pos)
								self.liquid_tick_queue.add((nx, y - 1, nz))
						elif n_num in (9, 19): # Flowing Lava flows into water -> Cobblestone
							self.set_block(n_pos, 1)
							created_this_tick.add(n_pos)

			# --- 3. AIR / PASSABLE BLOCK (Infinite Water Source Creation Check) ---
			elif b_num == 0:
				source_count = 0
				for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
					if self.get_block_number((x + dx, y, z + dz)) == 9:
						source_count += 1

				down_num = self.get_block_number((x, y - 1, z))
				is_solid_or_source = (down_num == 9) or (down_num != 0 and down_num not in (9, 19, 15, 20, 10, 12, 31, 33))

				if source_count >= 2 and is_solid_or_source:
					self.set_block(pos, 9)
					self.water_levels[pos] = 0
					created_this_tick.add(pos)
					self.liquid_tick_queue.add(pos)
					for dx, dz in ((0, -1), (0, 1), (-1, 0), (1, 0)):
						self.liquid_tick_queue.add((x + dx, y, z + dz))

	def set_block(self, position, number):
		x, y, z = position
		if y < 0 or y >= 256:
			return

		c_pos = (math.floor(x / chunk.CHUNK_WIDTH), 0, math.floor(z / chunk.CHUNK_LENGTH))
		if c_pos not in self.chunks:
			if number == 0: return
			self.chunks[c_pos] = self.generate_chunk(c_pos[0], c_pos[2])

		chk = self.chunks[c_pos]
		lx = int(x % chunk.CHUNK_WIDTH)
		ly = int(y)
		lz = int(z % chunk.CHUNK_LENGTH)

		old_num = chk.get_block_number(lx, ly, lz)
		if old_num == number:
			return

		# Liquid quantity tracking
		if number == 9:
			self.water_levels[position] = 0
		elif number == 15:
			self.liquid_levels[position] = 0
		elif number == 0:
			self.water_levels.pop(position, None)
			self.liquid_levels.pop(position, None)
			p_key = (int(x), int(y), int(z))
			if p_key in self.furnaces:
				f_data = self.furnaces[p_key]
				if self.item_drop_manager:
					for slot in (f_data.input_slot, f_data.fuel_slot, f_data.output_slot):
						if slot[0] != 0 and slot[1] > 0:
							self.item_drop_manager.spawn_drop(
								slot[0], slot[1],
								[x + 0.5, y + 0.5, z + 0.5]
							)
				del self.furnaces[p_key]

			if p_key in self.chests:
				c_data = self.chests[p_key]
				if self.item_drop_manager:
					for slot in c_data.slots:
						if slot[0] != 0 and slot[1] > 0:
							self.item_drop_manager.spawn_drop(
								slot[0], slot[1],
								[x + 0.5, y + 0.5, z + 0.5]
							)
				del self.chests[p_key]

		px, py, pz = position
		chk.set_block_number(lx, ly, lz, number)
		self.dirty_chunks.add(c_pos)

		if old_num in (24, 88, 89) or number == 0:
			try:
				import portal_manager
				portal_manager.portal_manager.on_block_broken(self, position)
			except Exception:
				pass

		for nx, ny, nz in [(px, py, pz), (px + 1, py, pz), (px - 1, py, pz), (px, py + 1, pz), (px, py - 1, pz), (px, py, pz + 1), (px, py, pz - 1)]:
			if 0 <= ny < chunk.CHUNK_HEIGHT:
				nb = self.get_block_number((nx, ny, nz))
				if nb in (9, 19, 15, 20):
					self.liquid_tick_queue.add((nx, ny, nz))
				elif nb == 0:
					for ddx, ddy, ddz in ((0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0)):
						if self.get_block_number((nx + ddx, ny + ddy, nz + ddz)) in (9, 19, 15, 20):
							self.liquid_tick_queue.add((nx, ny, nz))
							break

		sy = ly // 16
		self.section_mesh_queue.add((c_pos[0], c_pos[2], sy))

		if ly % 16 == 0 and sy > 0: self.section_mesh_queue.add((c_pos[0], c_pos[2], sy - 1))
		if ly % 16 == 15 and sy < 15: self.section_mesh_queue.add((c_pos[0], c_pos[2], sy + 1))

		if lx == 15: self.section_mesh_queue.add((c_pos[0] + 1, c_pos[2], sy))
		if lx == 0: self.section_mesh_queue.add((c_pos[0] - 1, c_pos[2], sy))
		if lz == 15: self.section_mesh_queue.add((c_pos[0], c_pos[2] + 1, sy))
		if lz == 0: self.section_mesh_queue.add((c_pos[0], c_pos[2] - 1, sy))

		# Gravity checks for Sand (6) and Gravel (77)
		if number in (6, 77):
			if ly > 1 and self.is_passable_for_gravity((px, py - 1, pz)):
				self.gravity_tick_queue.add((int(px), int(py), int(pz)))
		elif self.is_passable_for_gravity((px, py, pz)):
			above_pos = (int(px), int(py + 1), int(pz))
			if py + 1 < chunk.CHUNK_HEIGHT and self.get_block_number(above_pos) in (6, 77):
				self.gravity_tick_queue.add(above_pos)

		self.notify_neighbor_block_change(position)

	def _save_chunk_to_file(self, chunk_position, synchronous=False):
		if chunk_position not in self.chunks:
			return
		import json
		chk = self.chunks[chunk_position]
		cx, _, cz = chunk_position
		save_path = os.path.join(self.save_dir, f"{cx}_{cz}.chunk")
		
		state_map = {}
		for (lx, ly, lz), st in chk.block_states.items():
			if st:
				state_map[f"{lx},{ly},{lz}"] = st.to_dict()

		state_bytes = json.dumps(state_map).encode('utf-8')
		data = bytes(chk.blocks) + b"|STATE_DATA|" + state_bytes

		def write_content(path, content):
			try:
				with gzip.open(path, 'wb', compresslevel=1) as f:
					f.write(content)
			except Exception as e:
				print(f"Chunk save failed: {e}")

		if synchronous:
			write_content(save_path, data)
		else:
			self._save_executor.submit(write_content, save_path, data)

	def _collect_generated_chunks(self, player_cx, player_cz):
		for chunk_position in list(self.chunk_generation_futures.keys()):
			future = self.chunk_generation_futures[chunk_position]
			if not future.done():
				continue

			del self.chunk_generation_futures[chunk_position]
			try:
				raw_data = future.result()
			except Exception as error:
				print(f"Chunk generation failed for {chunk_position}: {error}")
				return

			if max(abs(chunk_position[0] - player_cx), abs(chunk_position[2] - player_cz)) > self.unload_distance:
				continue

			if b"|STATE_DATA|" in raw_data:
				parts = raw_data.split(b"|STATE_DATA|")
				blocks = parts[0]
				state_bytes = parts[1]
			else:
				blocks = raw_data
				state_bytes = None

			chk = chunk.Chunk(self, chunk_position, blocks=blocks)

			if state_bytes:
				import json, block_state
				try:
					st_dict = json.loads(state_bytes.decode('utf-8'))
					for key_str, s_data in st_dict.items():
						lx, ly, lz = map(int, key_str.split(','))
						chk.block_states[(lx, ly, lz)] = block_state.BlockState.from_dict(s_data)
				except Exception:
					pass
			self.chunks[chunk_position] = chk

			# Register any village chests generated in this chunk
			try:
				import village
				_, _, v_chests = village.get_village_blocks_for_chunk(chunk_position[0], chunk_position[2], self.seed)
				if v_chests:
					for pos_key, slots in v_chests.items():
						if pos_key not in self.chests:
							c_obj = ChestData()
							c_obj.slots = [list(s) for s in slots]
							self.chests[pos_key] = c_obj
			except Exception:
				pass

			self.queue_chunk_sections_for_meshing(chunk_position[0], chunk_position[2])

			# Trigger border section re-meshing ONLY for neighbors that were missing this chunk
			cx, _, cz = chunk_position
			for nx, nz in [(cx + 1, cz), (cx - 1, cz), (cx, cz + 1), (cx, cz - 1)]:
				n_pos = (nx, 0, nz)
				if n_pos in self.chunks:
					n_chk = self.chunks[n_pos]
					if n_chk.had_missing_neighbors:
						self.queue_chunk_sections_for_meshing(nx, nz)
			return  # 1 chunk per frame max to guarantee O(1) main-thread execution time

	def _rebuild_load_queue(self, player_cx, player_cz):
		rd = self.render_distance
		chunks = self.chunks
		futures = self.chunk_generation_futures

		queue = []
		for dx, dz in get_ring_offsets(rd):
			c_pos = (player_cx + dx, 0, player_cz + dz)
			if c_pos not in chunks and c_pos not in futures:
				queue.append(c_pos)
		self._load_queue = queue

	def _submit_generations(self):
		if self._load_queue and len(self.chunk_generation_futures) < 1:
			while self._load_queue:
				chunk_pos = self._load_queue.pop(0)
				if chunk_pos in self.chunks or chunk_pos in self.chunk_generation_futures:
					continue
				if self.dimension == "nether":
					self.chunk_generation_futures[chunk_pos] = self.process_executor.submit(
						build_nether_chunk_blocks_process,
						chunk_pos[0], chunk_pos[2],
						self.save_dir, self.seed)
				elif self.dimension == "end":
					self.chunk_generation_futures[chunk_pos] = self.process_executor.submit(
						build_end_chunk_blocks_process,
						chunk_pos[0], chunk_pos[2],
						self.save_dir, self.seed)
				else:
					self.chunk_generation_futures[chunk_pos] = self.process_executor.submit(
						build_chunk_blocks_process,
						chunk_pos[0], chunk_pos[2],
						self.scale, self.octaves, self.persistence, self.lacunarity,
						self.cave_scale, self.cave_threshold, self.save_dir, self.seed)
				return

	def update_chunks(self, player_position):
		player_cx = math.floor(player_position[0] / chunk.CHUNK_WIDTH)
		player_cz = math.floor(player_position[2] / chunk.CHUNK_LENGTH)

		self._collect_generated_chunks(player_cx, player_cz)
		self._submit_generations()

		current_chunk_pos = (player_cx, player_cz)
		if current_chunk_pos != self._last_player_chunk:
			self._last_player_chunk = current_chunk_pos
			self._rebuild_load_queue(player_cx, player_cz)

		to_unload = [pos for pos in self.chunks if max(abs(pos[0] - player_cx), abs(pos[2] - player_cz)) > self.unload_distance]
		for chunk_pos in to_unload[:2]:
			self.unload_chunk(chunk_pos)

	def unload_chunk(self, chunk_position):
		if chunk_position in self.dirty_chunks:
			self._save_chunk_to_file(chunk_position)
			self.dirty_chunks.discard(chunk_position)

		if chunk_position in self.chunks:
			self.chunks[chunk_position].delete()  # Recycles VAO/VBO handles to free_chunk_pool
			del self.chunks[chunk_position]

	def draw(self, player_position=None, player_rotation=None):
		if not self.chunks:
			return

		visible_chunks = list(self.chunks.values())
		if player_position is not None and player_rotation is not None:
			cam_x, _, cam_z = player_position
			yaw = player_rotation[0]
			look_x = math.cos(yaw)
			look_z = math.sin(yaw)

			visible_chunks = []
			for current_chunk in self.chunks.values():
				cx, _, cz = current_chunk.chunk_position
				dx = (cx * 16 + 8) - cam_x
				dz = (cz * 16 + 8) - cam_z
				dist_sq = dx * dx + dz * dz

				if dist_sq > 256:
					dot = dx * look_x + dz * look_z
					if dot < -16.0:
						continue
				visible_chunks.append(current_chunk)

		bound_vao = None
		gl.glDisable(gl.GL_BLEND)
		gl.glDepthMask(gl.GL_TRUE)
		for current_chunk in visible_chunks:
			bound_vao = current_chunk.draw_opaque(bound_vao)

		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
		gl.glDepthMask(gl.GL_FALSE)
		for current_chunk in visible_chunks:
			bound_vao = current_chunk.draw_translucent(bound_vao)

		gl.glDepthMask(gl.GL_TRUE)
		gl.glDisable(gl.GL_BLEND)
		gl.glBindVertexArray(0)
