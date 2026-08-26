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
import models.enchanting_table
import models.bed
import models.bed_foot
import models.bed_head

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

	import array
	import biome
	flat_bytes = array.array('H', [0] * (chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH))

	rng = Random((x * 341873128712 + z * 132897987541 + seed) & ((1 << 64) - 1))
	surface_heights = [0] * 256  # 16x16 column surface heights

	chunk_offset_x = x * chunk.CHUNK_WIDTH
	chunk_offset_z = z * chunk.CHUNK_LENGTH

	# 1. Heightmap Calculation (Smooth continuous biome blending)
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i
			wz = chunk_offset_z + k
			final_y = biome.get_blended_height(wx, wz, seed=seed)
			surface_heights[i * 16 + k] = final_y

	# Helper for flat 1D indexing into flat_bytes
	def set_b(i, j, k, val):
		if 0 <= i < 16 and 0 <= j < 256 and 0 <= k < 16:
			flat_bytes[i * 4096 + j * 16 + k] = val

	def get_b(i, j, k):
		if 0 <= i < 16 and 0 <= j < 256 and 0 <= k < 16:
			return flat_bytes[i * 4096 + j * 16 + k]
		return 0

	# 2. Fill Solid Terrain, Surface Layers & Sea Water (Sea Level = 63)
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i
			wz = chunk_offset_z + k
			sy = surface_heights[i * 16 + k]

			set_b(i, 0, k, biome.BLOCK_BEDROCK)

			sub_depth = max(1, sy - 3)
			for j in range(1, sub_depth):
				block_num = biome.BLOCK_STONE
				if 30 <= j and rng.randrange(100) < 4:
					block_num = 16  # Coal Ore
				elif 10 <= j <= 50 and rng.randrange(100) < 2:
					block_num = 17  # Iron Ore
				elif 2 <= j <= 15 and rng.randrange(1000) < 3:
					block_num = 18  # Diamond Ore
				elif 10 <= j <= 32 and rng.randrange(1000) < 8:
					block_num = 212  # Lapis Lazuli Ore
				elif 15 <= j <= 65 and rng.randrange(100) < 3:
					block_num = biome.BLOCK_GRAVEL
				set_b(i, j, k, block_num)

			top_mat, sub1_mat, sub2_mat = biome.get_surface_column(wx, wz, sy, seed=seed)

			if sy < 63:
				# Underwater column
				for j in range(sub_depth, sy + 1):
					set_b(i, j, k, sub1_mat)
				# Fill water up to sea level 63 (or ice if freezing)
				t = biome.get_temperature(wx, wz, seed=seed)
				water_mat = biome.BLOCK_ICE if (t < 0.16 and sy >= 60) else biome.BLOCK_WATER
				for water_y in range(sy + 1, 64):
					set_b(i, water_y, k, water_mat)
			else:
				# Above water column
				for j in range(sub_depth, max(sub_depth, sy - 2)):
					set_b(i, j, k, sub2_mat)
				if sy - 1 >= sub_depth:
					set_b(i, sy - 1, k, sub1_mat)
				if sy - 2 >= sub_depth:
					set_b(i, sy - 2, k, sub2_mat)
				set_b(i, sy, k, top_mat)

	# 3. 3D Caves (Worms, Cheese, Ravines)
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
				if get_b(i, j, k) == biome.BLOCK_BEDROCK:
					continue

				c1 = pnoise3(wx / 22.0, j / 12.0, wz / 22.0)
				c2 = pnoise3((wx + 400.0) / 22.0, j / 12.0, (wz + 400.0) / 22.0)
				cheese = pnoise3((wx - 200.0) / 32.0, j / 20.0, (wz - 200.0) / 32.0)

				tunnel_thresh = 0.0070
				if is_surface_open and j >= sy - 8:
					tunnel_thresh = 0.0130

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

	# 5. Underground Cave Lava Lakes & Water Pools
	if rng.randrange(100) < 65:
		for _ in range(rng.randrange(1, 4)):
			pool_lx = rng.randrange(3, chunk.CHUNK_WIDTH - 3)
			pool_lz = rng.randrange(3, chunk.CHUNK_LENGTH - 3)
			
			found_y = None
			for check_y in range(11, 52):
				if get_b(pool_lx, check_y, pool_lz) == 0 and get_b(pool_lx, check_y - 1, pool_lz) in (5, 1, 16, 17, 18, 77, biome.BLOCK_SANDSTONE):
					found_y = check_y
					break

			if found_y is not None:
				pool_ly = found_y
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
										set_b(px, ry, pz, 5)

	# 6. Surface Water Lakes (outside deserts)
	center_wx = chunk_offset_x + 8
	center_wz = chunk_offset_z + 8
	primary_biome = biome.get_biome_at(center_wx, center_wz, seed=seed)

	if primary_biome != biome.BIOME_DESERT and rng.randrange(100) < 35:
		lake_cx = rng.randrange(3, chunk.CHUNK_WIDTH - 3)
		lake_cz = rng.randrange(3, chunk.CHUNK_LENGTH - 3)
		radius = rng.randrange(3, 6)
		sample_heights = [surface_heights[px * 16 + pz] for px in range(lake_cx - radius - 1, lake_cx + radius + 2) for pz in range(lake_cz - radius - 1, lake_cz + radius + 2) if 0 <= px < 16 and 0 <= pz < 16]

		if sample_heights:
			min_h = min(sample_heights)
			max_h = max(sample_heights)
			if (max_h - min_h <= 3) and (min_h >= 62):
				lake_surface_y = min_h
				for dx in range(-radius - 1, radius + 2):
					for dz in range(-radius - 1, radius + 2):
						dist_sq = dx * dx + dz * dz
						px, pz = lake_cx + dx, lake_cz + dz
						if 0 <= px < chunk.CHUNK_WIDTH and 0 <= pz < chunk.CHUNK_LENGTH:
							col_h = surface_heights[px * 16 + pz]
							if dist_sq <= radius * radius:
								for cy in range(lake_surface_y + 1, col_h + 1):
									set_b(px, cy, pz, 0)
								set_b(px, lake_surface_y, pz, 9)
								set_b(px, lake_surface_y - 1, pz, 9)
								set_b(px, lake_surface_y - 2, pz, 4)
								set_b(px, lake_surface_y - 3, pz, 5)
							elif dist_sq <= (radius + 1) * (radius + 1):
								for ry in range(lake_surface_y - 2, lake_surface_y + 2):
									b_curr = get_b(px, ry, pz)
									if b_curr == 0 or b_curr in (9, 19, 15, 20):
										set_b(px, ry, pz, 4)

	# 7. Procedural Tree & Flora Generation per Biome
	tree_count_by_biome = {
		biome.BIOME_DESERT: 0,
		biome.BIOME_SAVANNA: 1 if rng.random() < 0.60 else 0, # Low density: sparse open savanna grasslands with occasional solitary acacia
		biome.BIOME_PLAINS: 1 if rng.random() < 0.25 else 0,
		biome.BIOME_FOREST: rng.randint(4, 7),
		biome.BIOME_BIRCH_FOREST: rng.randint(6, 9),
		biome.BIOME_SPRUCE_TAIGA: rng.randint(6, 9),
		biome.BIOME_SNOW_FOREST: rng.randint(5, 8),
		biome.BIOME_JUNGLE: rng.randint(16, 26), # High density: dense lush tropical rainforest canopy & undergrowth
		biome.BIOME_HILLS: rng.randint(1, 3),
		biome.BIOME_MOUNTAINS: 1 if rng.random() < 0.35 else 0,
	}

	num_trees = tree_count_by_biome.get(primary_biome, 2)
	planted_trees = []

	import village
	attempts = max(12, num_trees * 3) if num_trees > 0 else 0
	for _ in range(attempts):
		if len(planted_trees) >= num_trees:
			break
		tx = rng.randrange(2, chunk.CHUNK_WIDTH - 2)
		tz = rng.randrange(2, chunk.CHUNK_LENGTH - 2)
		gy = surface_heights[tx * 16 + tz]
		ground_b = get_b(tx, gy, tz)
		col_wx = chunk_offset_x + tx
		col_wz = chunk_offset_z + tz
		col_biome = biome.get_biome_at(col_wx, col_wz, seed=seed)

		if 62 <= gy < 100 and gy + 15 < chunk.CHUNK_HEIGHT and ground_b in (biome.BLOCK_GRASS, biome.BLOCK_DIRT, biome.BLOCK_PODZOL, biome.BLOCK_SNOW_BLOCK):
			if not village.is_in_village(col_wx, col_wz, seed):
				min_dist = 2 if col_biome == biome.BIOME_JUNGLE else 3
				if not any(abs(tx - px) <= min_dist and abs(tz - pz) <= min_dist for px, pz in planted_trees):
					if col_biome == biome.BIOME_BIRCH_FOREST:
						biome.generate_birch_tree(flat_bytes, tx, gy + 1, tz, rng)
					elif col_biome in (biome.BIOME_SPRUCE_TAIGA, biome.BIOME_SNOW_FOREST):
						biome.generate_spruce_tree(flat_bytes, tx, gy + 1, tz, rng)
					elif col_biome == biome.BIOME_JUNGLE:
						if rng.random() < 0.45:
							biome.generate_jungle_bush(flat_bytes, tx, gy + 1, tz, rng)
						else:
							biome.generate_jungle_tree(flat_bytes, tx, gy + 1, tz, rng)
					elif col_biome == biome.BIOME_SAVANNA:
						biome.generate_acacia_tree(flat_bytes, tx, gy + 1, tz, rng)
					elif col_biome == biome.BIOME_FOREST:
						if rng.random() < 0.40:
							biome.generate_birch_tree(flat_bytes, tx, gy + 1, tz, rng)
						else:
							biome.generate_oak_tree(flat_bytes, tx, gy + 1, tz, rng)
					else:
						biome.generate_oak_tree(flat_bytes, tx, gy + 1, tz, rng)
					planted_trees.append((tx, tz))

	# 8. Biome-Specific Flora & Ground Decoration
	for _ in range(rng.randint(6, 16)):
		fx = rng.randrange(1, chunk.CHUNK_WIDTH - 1)
		fz = rng.randrange(1, chunk.CHUNK_LENGTH - 1)
		gy = surface_heights[fx * 16 + fz]
		ground_b = get_b(fx, gy, fz)
		col_wx = chunk_offset_x + fx
		col_wz = chunk_offset_z + fz
		col_biome = biome.get_biome_at(col_wx, col_wz, seed=seed)

		if gy + 1 < chunk.CHUNK_HEIGHT and get_b(fx, gy + 1, fz) == 0:
			if col_biome == biome.BIOME_DESERT and ground_b == biome.BLOCK_SAND:
				if rng.random() < 0.45:
					c_height = rng.randint(1, 3)
					for cy in range(1, c_height + 1):
						set_b(fx, gy + cy, fz, biome.BLOCK_CACTUS)
				else:
					set_b(fx, gy + 1, fz, biome.BLOCK_DEAD_BUSH)
			elif col_biome == biome.BIOME_JUNGLE and ground_b == biome.BLOCK_GRASS:
				if rng.random() < 0.15:
					set_b(fx, gy + 1, fz, biome.BLOCK_MELON)
				else:
					set_b(fx, gy + 1, fz, biome.BLOCK_FERN)
			elif col_biome == biome.BIOME_SPRUCE_TAIGA and ground_b in (biome.BLOCK_GRASS, biome.BLOCK_PODZOL):
				if rng.random() < 0.10:
					set_b(fx, gy + 1, fz, 82)
				else:
					set_b(fx, gy + 1, fz, biome.BLOCK_FERN)
			elif col_biome == biome.BIOME_PLAINS and ground_b == biome.BLOCK_GRASS:
				flower_choice = rng.choice([biome.BLOCK_DANDELION, biome.BLOCK_ROSE, biome.BLOCK_RED_TULIP, biome.BLOCK_ORANGE_TULIP, biome.BLOCK_OXEYE_DAISY])
				set_b(fx, gy + 1, fz, flower_choice)
			elif col_biome in (biome.BIOME_FOREST, biome.BIOME_BIRCH_FOREST) and ground_b == biome.BLOCK_GRASS:
				flower_choice = rng.choice([biome.BLOCK_DANDELION, biome.BLOCK_ROSE, biome.BLOCK_OXEYE_DAISY])
				set_b(fx, gy + 1, fz, flower_choice)
			elif col_biome == biome.BIOME_SAVANNA and ground_b == biome.BLOCK_GRASS:
				if rng.random() < 0.60:
					set_b(fx, gy + 1, fz, biome.BLOCK_DANDELION)

	# 9. Village Structures Generation (High Priority)
	try:
		import village
		v_blocks, v_air, _ = village.get_village_blocks_for_chunk(x, z, seed)
		if v_blocks or v_air:
			for (lx, ly, lz) in v_air:
				if 0 <= lx < 16 and 0 <= ly < 256 and 0 <= lz < 16:
					set_b(lx, ly, lz, 0)
			for (lx, ly, lz), b_id in v_blocks.items():
				if 0 <= lx < 16 and 0 <= ly < 256 and 0 <= lz < 16:
					set_b(lx, ly, lz, b_id)
	except Exception as e:
		print(f"[Village Error in chunk {x}, {z}]: {e}")

	# 10. Stronghold Structures Generation
	try:
		import stronghold_manager
		stronghold_manager.stamp_stronghold_blocks_for_chunk(x, z, flat_bytes, seed=seed)
	except Exception as e:
		pass

	if hasattr(flat_bytes, 'tobytes'):
		return flat_bytes.tobytes()
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
	def unpack_chunk_blocks(raw_data):
		if raw_data is None:
			return None
		if isinstance(raw_data, array.array):
			return raw_data
		if isinstance(raw_data, (bytes, bytearray)):
			if len(raw_data) >= 131072:
				arr = array.array('H')
				arr.frombytes(raw_data[:131072])
				return arr
			elif len(raw_data) >= 65536:
				return array.array('H', raw_data[:65536])
		return raw_data

	center_blocks = unpack_chunk_blocks(center_blocks)
	north_blocks = unpack_chunk_blocks(north_blocks)
	south_blocks = unpack_chunk_blocks(south_blocks)
	east_blocks = unpack_chunk_blocks(east_blocks)
	west_blocks = unpack_chunk_blocks(west_blocks)

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

				def rotate_bed_vertex(vx, vy, vz, rot_facing):
					if rot_facing == "SOUTH": return (vx, vy, vz)
					elif rot_facing == "NORTH": return (-vx, vy, -vz)
					elif rot_facing == "EAST": return (vz, vy, -vx)
					elif rot_facing == "WEST": return (-vz, vy, vx)
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
					is_log = b_num in (8, 60, 61, 223, 233, 243, 253, 263)

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
							if not n_info or n_info['transparent'] or not n_info.get('is_cube', True):
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
					rot_f = facing if b_num in (41, 42, 73, 74, 92, 93, 178, 179, 181, 182, 43, 44, 45, 46, 65, 66, 67, 68, 47, 48, 49, 50, 69, 70, 71, 72, 75, 76, 227, 237, 247, 257, 267, 228, 229, 238, 239, 248, 249, 258, 259, 268, 269, 230, 240, 250, 260, 270, 272, 273, 274, 275, 276) else "NORTH"

					if b_num in (38, 39, 40, 62, 63, 64, 95, 180, 226, 236, 246, 256, 266):
						# Slabs (Bottom, Top, Double)
						sl_h = "TOP" if b_num in (62, 63, 64) else half
						if sl_h == "DOUBLE":
							add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.5, 0.5), [0, 0, 0, 0, 0, 0])
						elif sl_h == "TOP":
							add_custom_box((-0.5, 0.0, -0.5), (0.5, 0.5, 0.5), [0, 0, 0, 0, 0, 0])
						else:
							add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.0, 0.5), [0, 0, 0, 0, 0, 0])

					elif b_num in (41, 42, 73, 74, 92, 93, 178, 179, 227, 237, 247, 257, 267):
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

					elif b_num in (43, 44, 45, 46, 65, 66, 67, 68, 228, 229, 238, 239, 248, 249, 258, 259, 268, 269):
						# Doors (Facing, Hinge, Half, Open)
						d_open = open_state or (b_num in (44, 46, 66, 68))
						if d_open:
							if hinge == "RIGHT":
								add_custom_box((0.3125, -0.5, -0.5), (0.5, 0.5, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
							else:
								add_custom_box((-0.5, -0.5, -0.5), (-0.3125, 0.5, 0.5), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)
						else:
							add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.5, -0.3125), [0, 0, 0, 0, 0, 0], rot_facing=rot_f)

					elif b_num in (47, 48, 49, 50, 69, 70, 71, 72, 230, 240, 250, 260, 270):
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

					elif b_num in (75, 76, 272, 273, 274, 275, 276):
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

					elif b_num in (51, 52, 53, 91, 99, 231, 241, 251, 261, 271):
						# Fences (51, 91, 231, 241, 251, 261, 271), Walls (52), Glass Panes (53), Iron Bars (99)
						nb_n = get_nb(local_x, local_y, local_z - 1)
						nb_s = get_nb(local_x, local_y, local_z + 1)
						nb_w = get_nb(local_x - 1, local_y, local_z)
						nb_e = get_nb(local_x + 1, local_y, local_z)

						def can_conn(nb, d_key):
							if conns and d_key in conns: return conns[d_key]
							if nb in (0, 9, 10, 11, 12, 13, 15, 19, 20, 25, 31, 33, 43, 44, 45, 46, 47, 48, 49, 50, 65, 66, 67, 68, 69, 70, 71, 72, 78, 79, 81, 88, 89, 94, 156, 181, 182, 183, 190, 191, 192, 193, 194, 195, 196, 197, 204, 205, 206, 207, 210, 213, 218, 219, 220, 221, 224, 225, 228, 229, 230, 234, 235, 238, 239, 240, 244, 245, 248, 249, 250, 254, 255, 258, 259, 260, 264, 265, 268, 269, 270, 279, 280, 283, 284, 285):
								return False
							if b_num in (51, 91, 231, 241, 251, 261, 271):
								return nb in (51, 91, 231, 241, 251, 261, 271, 75, 76, 272, 273, 274, 275, 276) or (block_types_info.get(nb, {}).get('is_cube', False) and not block_types_info.get(nb, {}).get('transparent', False))
							elif b_num == 52:
								return nb in (52, 53, 99, 75, 76, 272, 273, 274, 275, 276) or (block_types_info.get(nb, {}).get('is_cube', False) and not block_types_info.get(nb, {}).get('transparent', False))
							elif b_num in (53, 99):
								# Glass panes and iron bars connect to other panes/bars, walls, fences, gates, stairs, slabs, and solid blocks!
								return True
							return False

						c_n = can_conn(nb_n, 'north')
						c_s = can_conn(nb_s, 'south')
						c_w = can_conn(nb_w, 'west')
						c_e = can_conn(nb_e, 'east')

						is_straight = (c_n and c_s and not c_w and not c_e) or (c_w and c_e and not c_n and not c_s)

						if b_num in (51, 91, 231, 241, 251, 261, 271):
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
					elif b_num in (81, 204, 205, 206, 207, 210):
						# Multi-stage crops, stems, and sugarcane
						tex_map = block_types_info.get('textures_map', {})
						if b_num == 81:
							st_stage = int(shape) if shape.isdigit() else 7
							t_name = f"wheat_stage_{min(7, max(0, st_stage))}"
						elif b_num == 204:
							st_stage = int(shape) if shape.isdigit() else 3
							t_name = f"carrots_stage_{min(3, max(0, st_stage))}"
						elif b_num == 205:
							st_stage = int(shape) if shape.isdigit() else 3
							t_name = f"potatoes_stage_{min(3, max(0, st_stage))}"
						elif b_num == 206:
							t_name = "pumpkin_stem_disconnected"
						elif b_num == 207:
							t_name = "melon_stem_disconnected"
						elif b_num == 210:
							t_name = "sugar_cane"
						else:
							t_name = None

						t_layer = float(tex_map[t_name]) if (t_name and t_name in tex_map) else (b_info['tex_coords'][0][2] if b_info.get('tex_coords') else 0.0)

						for face_idx in range(len(b_info['vertex_positions'])):
							vp = b_info['vertex_positions'][face_idx]
							sh = b_info['shading_values'][face_idx]
							base_tc = b_info['tex_coords'][face_idx] if face_idx < len(b_info['tex_coords']) else b_info['tex_coords'][0]
							tc = list(base_tc)
							for vi in range(4):
								tc[vi * 3 + 2] = t_layer

							c = trans_vert_count if is_translucent else opaque_vert_count
							idx_arr = trans_idx if is_translucent else opaque_idx
							idx_arr.extend((c, c + 1, c + 2, c, c + 2, c + 3))

							pos_arr = trans_pos if is_translucent else opaque_pos
							for vi in range(4):
								pos_arr.extend((vp[vi * 3 + 0] + x, vp[vi * 3 + 1] + y, vp[vi * 3 + 2] + z))

							if is_translucent:
								trans_vert_count += 4
								trans_tex.extend(tc)
								trans_shd.extend(sh)
							else:
								opaque_vert_count += 4
								opaque_tex.extend(tc)
								opaque_shd.extend(sh)
					elif b_num in (220, 221):
						# Bed Foot (220) and Bed Head (221) directional rotation
						bed_facing = facing if facing in ("NORTH", "SOUTH", "EAST", "WEST") else "SOUTH"
						for face_idx in range(len(b_info['vertex_positions'])):
							vp = b_info['vertex_positions'][face_idx]
							sh = b_info['shading_values'][face_idx]
							tc = b_info['tex_coords'][face_idx] if face_idx < len(b_info['tex_coords']) else b_info['tex_coords'][0]

							c = trans_vert_count if is_translucent else opaque_vert_count
							idx_arr = trans_idx if is_translucent else opaque_idx
							idx_arr.extend((c, c + 1, c + 2, c, c + 2, c + 3))

							pos_arr = trans_pos if is_translucent else opaque_pos
							for vi in range(4):
								vx = vp[vi * 3 + 0]
								vy = vp[vi * 3 + 1]
								vz = vp[vi * 3 + 2]
								rx, ry, rz = rotate_bed_vertex(vx, vy, vz, bed_facing)
								pos_arr.extend((rx + x, ry + y, rz + z))

							if is_translucent:
								trans_vert_count += 4
								trans_tex.extend(tc)
								trans_shd.extend(sh)
							else:
								opaque_vert_count += 4
								opaque_tex.extend(tc)
								opaque_shd.extend(sh)
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
		self.accumulated_xp = 0.0

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

					# Accumulate smelting experience
					xp_per_item = getattr(gui, 'SMELTING_XP', {}).get(result_id, 0.35)
					self.accumulated_xp += xp_per_item * result_cnt

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

		self.texture_manager = texture_manager.Texture_manager(16, 16, 1024)
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
		self.block_types.append(block_type.Block_type(self.texture_manager, name="rose", block_face_textures={"all": "rose"}, model=models.plant, transparent=True, break_time=0.15, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="cactus", block_face_textures={"top": "cactus_top", "bottom": "cactus_bottom", "sides": "cactus_side"}, model=models.cactus, transparent=True, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dead_bush", block_face_textures={"all": "dead_bush"}, model=models.plant, transparent=True, break_time=0.15, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="leaves", block_face_textures={"all": "leaves"}, model=models.leaves, transparent=True, break_time=0.2, requires_tool=False))
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
		self.block_types.append(block_type.Block_type(self.texture_manager, name="yellow_flower", block_face_textures={"all": "yellow_flower"}, model=models.plant, transparent=True, break_time=0.15, requires_tool=False))
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

		# Pad slots up to 204 with placeholder Block_types
		while len(self.block_types) < 204:
			curr_id = len(self.block_types)
			self.block_types.append(block_type.Block_type(self.texture_manager, name=f"item_{curr_id}", block_face_textures={"all": "stonebrick"}, transparent=True, break_time=1.0, requires_tool=False))

		# Farming Blocks (204-210)
		self.block_types.append(block_type.Block_type(self.texture_manager, name="carrot_crops", block_face_textures={"all": "carrots_stage_3"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="potato_crops", block_face_textures={"all": "potatoes_stage_3"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="pumpkin_stem", block_face_textures={"all": "pumpkin_stem_disconnected"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="melon_stem", block_face_textures={"all": "melon_stem_disconnected"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="pumpkin", block_face_textures={"top": "pumpkin_top", "bottom": "pumpkin_top", "sides": "pumpkin_side"}, break_time=1.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="melon", block_face_textures={"top": "melon_top", "bottom": "melon_top", "sides": "melon_side"}, break_time=1.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="sugar_cane", block_face_textures={"all": "sugar_cane"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))

		# Pad slot 211 with placeholder
		while len(self.block_types) < 212:
			curr_id = len(self.block_types)
			self.block_types.append(block_type.Block_type(self.texture_manager, name=f"item_{curr_id}", block_face_textures={"all": "stonebrick"}, transparent=True, break_time=1.0, requires_tool=False))

		# Lapis Lazuli Ore (212) and Enchanting Table (213)
		self.block_types.append(block_type.Block_type(self.texture_manager, name="lapis_ore", block_face_textures={"all": "lapis_ore"}, break_time=3.0, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="enchanting_table", block_face_textures={"top": "enchanting_table_top", "bottom": "obsidian", "sides": "enchanting_table_side"}, model=models.enchanting_table, transparent=True, break_time=5.0, requires_tool=True))

		# Pad slots up to 220 for items (214: Lapis, 215: Paper, 216: Book, 217: Enchanted Book, 218: Bottle o' Enchanting, 219: Bed item)
		while len(self.block_types) < 220:
			curr_id = len(self.block_types)
			self.block_types.append(block_type.Block_type(self.texture_manager, name=f"item_{curr_id}", block_face_textures={"all": "stonebrick"}, transparent=True, break_time=1.0, requires_tool=False))

		# Bed Blocks (220 = Bed Foot, 221 = Bed Head)
		self.block_types.append(block_type.Block_type(
			self.texture_manager,
			name="bed_foot",
			block_face_textures={
				"top": "bed_feet_top",
				"bottom": "planks",
				"right": "bed_feet_side",
				"left": "bed_feet_side",
				"back": "bed_feet_end",
				"front": "planks"
			},
			model=models.bed_foot,
			transparent=True,
			break_time=0.3,
			requires_tool=False
		))
		self.block_types.append(block_type.Block_type(
			self.texture_manager,
			name="bed_head",
			block_face_textures={
				"top": "bed_head_top",
				"bottom": "planks",
				"right": "bed_head_side",
				"left": "bed_head_side",
				"front": "bed_head_end",
				"back": "planks"
			},
			model=models.bed_head,
			transparent=True,
			break_time=0.3,
			requires_tool=False
		))

		# -------------------------------------------------------------------
		# Birch Family (222-231, 272)
		# -------------------------------------------------------------------
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_planks", block_face_textures={"all": "planks_birch"}, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_log", block_face_textures={"top": "log_birch_top", "bottom": "log_birch_top", "sides": "log_birch"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_leaves", block_face_textures={"all": "leaves_birch"}, model=models.leaves, transparent=True, break_time=0.2, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_sapling", block_face_textures={"all": "sapling_birch"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_slab", block_face_textures={"all": "planks_birch"}, model=models.slab, transparent=True, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_stairs", block_face_textures={"all": "planks_birch"}, model=models.stairs, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_door", block_face_textures={"all": "door_birch_lower"}, model=models.door, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_door_top", block_face_textures={"all": "door_birch_upper"}, model=models.door_top, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_trapdoor", block_face_textures={"all": "trapdoor_birch"}, model=models.trapdoor, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_fence", block_face_textures={"all": "planks_birch"}, model=models.fence, transparent=True, break_time=0.6, requires_tool=False))

		# -------------------------------------------------------------------
		# Spruce Family (232-241, 273)
		# -------------------------------------------------------------------
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_planks", block_face_textures={"all": "planks_spruce"}, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_log", block_face_textures={"top": "log_spruce_top", "bottom": "log_spruce_top", "sides": "log_spruce"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_leaves", block_face_textures={"all": "leaves_spruce"}, model=models.leaves, transparent=True, break_time=0.2, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_sapling", block_face_textures={"all": "sapling_spruce"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_slab", block_face_textures={"all": "planks_spruce"}, model=models.slab, transparent=True, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_stairs", block_face_textures={"all": "planks_spruce"}, model=models.stairs, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_door", block_face_textures={"all": "door_spruce_lower"}, model=models.door, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_door_top", block_face_textures={"all": "door_spruce_upper"}, model=models.door_top, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_trapdoor", block_face_textures={"all": "trapdoor_spruce"}, model=models.trapdoor, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_fence", block_face_textures={"all": "planks_spruce"}, model=models.fence, transparent=True, break_time=0.6, requires_tool=False))

		# -------------------------------------------------------------------
		# Jungle Family (242-251, 274)
		# -------------------------------------------------------------------
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_planks", block_face_textures={"all": "planks_jungle"}, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_log", block_face_textures={"top": "log_jungle_top", "bottom": "log_jungle_top", "sides": "log_jungle"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_leaves", block_face_textures={"all": "leaves_jungle"}, model=models.leaves, transparent=True, break_time=0.2, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_sapling", block_face_textures={"all": "sapling_jungle"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_slab", block_face_textures={"all": "planks_jungle"}, model=models.slab, transparent=True, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_stairs", block_face_textures={"all": "planks_jungle"}, model=models.stairs, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_door", block_face_textures={"all": "door_jungle_lower"}, model=models.door, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_door_top", block_face_textures={"all": "door_jungle_upper"}, model=models.door_top, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_trapdoor", block_face_textures={"all": "trapdoor_jungle"}, model=models.trapdoor, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_fence", block_face_textures={"all": "planks_jungle"}, model=models.fence, transparent=True, break_time=0.6, requires_tool=False))

		# -------------------------------------------------------------------
		# Acacia Family (252-261, 275)
		# -------------------------------------------------------------------
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_planks", block_face_textures={"all": "planks_acacia"}, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_log", block_face_textures={"top": "log_acacia_top", "bottom": "log_acacia_top", "sides": "log_acacia"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_leaves", block_face_textures={"all": "leaves_acacia"}, model=models.leaves, transparent=True, break_time=0.2, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_sapling", block_face_textures={"all": "sapling_acacia"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_slab", block_face_textures={"all": "planks_acacia"}, model=models.slab, transparent=True, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_stairs", block_face_textures={"all": "planks_acacia"}, model=models.stairs, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_door", block_face_textures={"all": "door_acacia_lower"}, model=models.door, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_door_top", block_face_textures={"all": "door_acacia_upper"}, model=models.door_top, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_trapdoor", block_face_textures={"all": "trapdoor_acacia"}, model=models.trapdoor, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_fence", block_face_textures={"all": "planks_acacia"}, model=models.fence, transparent=True, break_time=0.6, requires_tool=False))

		# -------------------------------------------------------------------
		# Dark Oak Family (262-271, 276)
		# -------------------------------------------------------------------
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_planks", block_face_textures={"all": "planks_big_oak"}, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_log", block_face_textures={"top": "log_big_oak_top", "bottom": "log_big_oak_top", "sides": "log_big_oak"}, break_time=0.9, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_leaves", block_face_textures={"all": "leaves_big_oak"}, model=models.leaves, transparent=True, break_time=0.2, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_sapling", block_face_textures={"all": "sapling_roofed_oak"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_slab", block_face_textures={"all": "planks_big_oak"}, model=models.slab, transparent=True, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_stairs", block_face_textures={"all": "planks_big_oak"}, model=models.stairs, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_door", block_face_textures={"all": "door_dark_oak_lower"}, model=models.door, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_door_top", block_face_textures={"all": "door_dark_oak_upper"}, model=models.door_top, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_trapdoor", block_face_textures={"all": "trapdoor_dark_oak"}, model=models.trapdoor, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_fence", block_face_textures={"all": "planks_big_oak"}, model=models.fence, transparent=True, break_time=0.6, requires_tool=False))

		# -------------------------------------------------------------------
		# Fence Gates (272-276)
		# -------------------------------------------------------------------
		self.block_types.append(block_type.Block_type(self.texture_manager, name="birch_fence_gate", block_face_textures={"all": "planks_birch"}, model=models.fence_gate, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="spruce_fence_gate", block_face_textures={"all": "planks_spruce"}, model=models.fence_gate, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="jungle_fence_gate", block_face_textures={"all": "planks_jungle"}, model=models.fence_gate, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="acacia_fence_gate", block_face_textures={"all": "planks_acacia"}, model=models.fence_gate, transparent=True, break_time=0.6, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dark_oak_fence_gate", block_face_textures={"all": "planks_big_oak"}, model=models.fence_gate, transparent=True, break_time=0.6, requires_tool=False))

		# -------------------------------------------------------------------
		# Biome Terrain & Flora (277-285)
		# -------------------------------------------------------------------
		self.block_types.append(block_type.Block_type(self.texture_manager, name="sandstone", block_face_textures={"top": "sandstone_top", "bottom": "sandstone_bottom", "sides": "sandstone_normal"}, break_time=0.8, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="podzol", block_face_textures={"top": "dirt_podzol_top", "bottom": "dirt", "sides": "dirt_podzol_side"}, break_time=0.5, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="fern", block_face_textures={"all": "fern"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="vines", block_face_textures={"all": "vine"}, model=models.plant, transparent=True, break_time=0.2, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="red_sand", block_face_textures={"all": "red_sand"}, break_time=0.4, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="packed_ice", block_face_textures={"all": "ice_packed"}, break_time=0.5, requires_tool=True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="red_tulip", block_face_textures={"all": "flower_tulip_red"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="orange_tulip", block_face_textures={"all": "flower_tulip_orange"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="oxeye_daisy", block_face_textures={"all": "flower_oxeye_daisy"}, model=models.plant, transparent=True, break_time=0.0, requires_tool=False))

		import gui
		for item_id, item_name, tex_name in gui.ALL_ITEMS:
			self.texture_manager.add_texture(tex_name)

		# Wood Variant & Biome Textures
		for wood in ("birch", "spruce", "jungle", "acacia", "big_oak"):
			self.texture_manager.add_texture(f"planks_{wood}")
			self.texture_manager.add_texture(f"log_{wood}")
			self.texture_manager.add_texture(f"log_{wood}_top")
			self.texture_manager.add_texture(f"leaves_{wood}")
		self.texture_manager.add_texture("sapling_birch")
		self.texture_manager.add_texture("sapling_spruce")
		self.texture_manager.add_texture("sapling_jungle")
		self.texture_manager.add_texture("sapling_acacia")
		self.texture_manager.add_texture("sapling_roofed_oak")
		self.texture_manager.add_texture("door_birch_lower")
		self.texture_manager.add_texture("door_birch_upper")
		self.texture_manager.add_texture("door_spruce_lower")
		self.texture_manager.add_texture("door_spruce_upper")
		self.texture_manager.add_texture("door_jungle_lower")
		self.texture_manager.add_texture("door_jungle_upper")
		self.texture_manager.add_texture("door_acacia_lower")
		self.texture_manager.add_texture("door_acacia_upper")
		self.texture_manager.add_texture("door_dark_oak_lower")
		self.texture_manager.add_texture("door_dark_oak_upper")
		self.texture_manager.add_texture("sandstone_top")
		self.texture_manager.add_texture("sandstone_bottom")
		self.texture_manager.add_texture("sandstone_normal")
		self.texture_manager.add_texture("dirt_podzol_top")
		self.texture_manager.add_texture("dirt_podzol_side")
		self.texture_manager.add_texture("fern")
		self.texture_manager.add_texture("vine")
		self.texture_manager.add_texture("red_sand")
		self.texture_manager.add_texture("ice_packed")
		self.texture_manager.add_texture("flower_tulip_red")
		self.texture_manager.add_texture("flower_tulip_orange")
		self.texture_manager.add_texture("flower_oxeye_daisy")

		for stage in range(8):
			self.texture_manager.add_texture(f"wheat_stage_{stage}")
		for stage in range(4):
			self.texture_manager.add_texture(f"carrots_stage_{stage}")
			self.texture_manager.add_texture(f"potatoes_stage_{stage}")
		self.texture_manager.add_texture("pumpkin_stem_disconnected")
		self.texture_manager.add_texture("melon_stem_disconnected")
		self.texture_manager.add_texture("pumpkin_top")
		self.texture_manager.add_texture("pumpkin_side")
		self.texture_manager.add_texture("melon_top")
		self.texture_manager.add_texture("melon_side")
		self.texture_manager.add_texture("sugar_cane")
		self.texture_manager.add_texture("soil")

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
		self.texture_manager.add_texture("experience_orb")
		for frame in range(4):
			self.texture_manager.add_texture(f"experience_orb_{frame}")
		self.texture_manager.add_texture("lapis_ore")
		self.texture_manager.add_texture("bed_feet_top")
		self.texture_manager.add_texture("bed_feet_side")
		self.texture_manager.add_texture("bed_feet_end")
		self.texture_manager.add_texture("bed_head_top")
		self.texture_manager.add_texture("bed_head_side")
		self.texture_manager.add_texture("bed_head_end")
		self.texture_manager.add_texture("items/bed")
		self.texture_manager.add_texture("enchanting_table_top")
		self.texture_manager.add_texture("enchanting_table_side")
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
		self.farm_tick_timer = 0.0
		self.farmlands = set()
		self.crops = set()
		self.sugar_canes = set()
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

		self.tick_farming(dt)

	def tick_farming(self, dt):
		self.farm_tick_timer += dt
		if self.farm_tick_timer < 1.0:
			return
		self.farm_tick_timer = 0.0

		import random

		# 1. Farmland Hydration & Decay
		for pos in list(self.farmlands):
			if self.get_block_number(pos) != 80:
				self.farmlands.discard(pos)
				continue

			px, py, pz = pos
			hydrated = False
			for dx in range(-4, 5):
				for dz in range(-4, 5):
					for dy in (-1, 0, 1):
						nb = self.get_block_number((px + dx, py + dy, pz + dz))
						if nb in (9, 19, 13):
							hydrated = True
							break
					if hydrated:
						break
				if hydrated:
					break

			if not hydrated:
				above_b = self.get_block_number((px, py + 1, pz))
				if above_b not in (81, 204, 205, 206, 207):
					if random.random() < 0.00075:
						self.set_block(pos, 4)  # Dry out to Dirt
						self.farmlands.discard(pos)

		# 2. Crop & Stem Growth (0.005x growth rate: 0.125% chance per second per crop)
		for pos in list(self.crops):
			b_num = self.get_block_number(pos)
			if b_num not in (81, 204, 205, 206, 207):
				self.crops.discard(pos)
				continue

			px, py, pz = pos
			below_b = self.get_block_number((px, py - 1, pz))
			if below_b != 80:
				self.set_block(pos, 0)
				self.crops.discard(pos)
				if hasattr(self, "item_drop_manager") and self.item_drop_manager:
					drop_id = 155 if b_num == 81 else (195 if b_num == 204 else (196 if b_num == 205 else (199 if b_num == 206 else 200)))
					self.item_drop_manager.spawn_drop(drop_id, 1, [px + 0.5, py + 0.2, pz + 0.5])
				continue

			st = self.get_block_state(pos)
			curr_stage = int(st.shape) if (st and st.shape.isdigit()) else 0
			max_stage = 7 if b_num in (81, 206, 207) else 3

			if random.random() < 0.00125:
				if curr_stage < max_stage:
					new_stage = curr_stage + 1
					import block_state
					new_st = block_state.BlockState(b_num, shape=str(new_stage))
					self.set_block_state(pos, new_st)
				elif b_num in (206, 207):
					cardinals = [(1, 0), (-1, 0), (0, 1), (0, -1)]
					random.shuffle(cardinals)
					for cdx, cdz in cardinals:
						side_pos = (px + cdx, py, pz + cdz)
						ground_pos = (px + cdx, py - 1, pz + cdz)
						if self.get_block_number(side_pos) == 0:
							ground_b = self.get_block_number(ground_pos)
							if ground_b in (2, 4, 80):
								fruit_block = 208 if b_num == 206 else 209
								self.set_block(side_pos, fruit_block)
								break

		# 3. Sugar Cane Growth (0.005x growth rate: 0.100% chance per second)
		for pos in list(self.sugar_canes):
			if self.get_block_number(pos) != 210:
				self.sugar_canes.discard(pos)
				continue

			px, py, pz = pos
			below_b = self.get_block_number((px, py - 1, pz))
			is_valid = False
			if below_b == 210:
				is_valid = True
			elif below_b in (2, 4, 6):
				for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
					if self.get_block_number((px + dx, py - 1, pz + dz)) in (9, 19, 13):
						is_valid = True
						break

			if not is_valid:
				self.set_block(pos, 0)
				self.sugar_canes.discard(pos)
				if hasattr(self, "item_drop_manager") and self.item_drop_manager:
					self.item_drop_manager.spawn_drop(202, 1, [px + 0.5, py + 0.2, pz + 0.5])
				continue

			h_count = 1
			check_y = py - 1
			while self.get_block_number((px, check_y, pz)) == 210:
				h_count += 1
				check_y -= 1

			if h_count < 3 and random.random() < 0.00100:
				above_pos = (px, py + 1, pz)
				if self.get_block_number(above_pos) == 0:
					self.set_block(above_pos, 210)

	def get_block_types_info(self):
		if self._block_info_cache is None:
			info = {}
			for idx, b in enumerate(self.block_types):
				if b is None:
					continue
				info[idx] = {
					'name': b.name,
					'is_cube': b.is_cube,
					'transparent': b.transparent or getattr(b.model, "transparent", False) or (not b.is_cube),
					'translucent': b.translucent or b.name in ('water', 'under_water'),
					'vertex_positions': b.vertex_positions,
					'tex_coords': b.tex_coords,
					'shading_values': b.shading_values,
				}
			info['textures_map'] = {name: idx for idx, name in enumerate(self.texture_manager.textures)}
			self._block_info_cache = info
		return self._block_info_cache

	def set_render_distance(self, new_rd):
		self.render_distance = max(2, min(12, new_rd))
		self.unload_distance = self.render_distance + 3
		self._load_queue.clear()
		self._last_player_chunk = None

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
		if state and state.block_id in (81, 204, 205, 206, 207):
			self.crops.add(tuple(position))
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
			if nb_b in (41, 42, 73, 74, 92, 93, 178, 179, 227, 237, 247, 257, 267):
				if not nb_st:
					nb_st = block_state.BlockState(nb_b)
				new_shape = block_state.calculate_stair_shape(self, nb_pos, nb_st.facing, nb_st.half)
				if new_shape != nb_st.shape:
					nb_st.shape = new_shape
					self.set_block_state(nb_pos, nb_st)

			# 2. Fence connection recalculation
			elif nb_b in (51, 91, 231, 241, 251, 261, 271):
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
			elif nb_b in (53, 99):
				if not nb_st:
					nb_st = block_state.BlockState(nb_b)
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
		import block_state
		x, y, z = pos
		if y < 1 or y >= chunk.CHUNK_HEIGHT:
			return False
		b_num = self.get_block_number(pos)
		return b_num in block_state.PASSABLE_BLOCKS

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

		if number == 80:
			self.farmlands.add(tuple(position))
		else:
			self.farmlands.discard(tuple(position))

		if number in (81, 204, 205, 206, 207):
			self.crops.add(tuple(position))
		else:
			self.crops.discard(tuple(position))

		if number == 210:
			self.sugar_canes.add(tuple(position))
		else:
			self.sugar_canes.discard(tuple(position))

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
		raw_blocks = chk.blocks.tobytes() if hasattr(chk.blocks, 'tobytes') else bytes(chk.blocks)
		data = raw_blocks + b"|STATE_DATA|" + state_bytes

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
