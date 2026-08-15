import math
import time
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

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'save', 'chunks')
MAX_RENDER_DISTANCE = 32

def _generate_ring_offsets(max_rd):
	offsets = []
	for dx in range(-max_rd, max_rd + 1):
		for dz in range(-max_rd, max_rd + 1):
			dist_sq = dx * dx + dz * dz
			offsets.append((dist_sq, dx, dz))
	offsets.sort(key=lambda item: item[0])
	return [(dx, dz) for _, dx, dz in offsets]

RING_OFFSETS = _generate_ring_offsets(MAX_RENDER_DISTANCE)


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

	# 1. Heightmap Calculation
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i + seed_offset_x
			wz = chunk_offset_z + k + seed_offset_z

			cont = pnoise2(wx / 350.0, wz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)
			peaks_raw = pnoise2((wx + 1000.0) / 85.0, (wz + 1000.0) / 85.0, octaves=4, persistence=0.5, lacunarity=2.0)
			ridge = 1.0 - abs(peaks_raw * 2.0)

			if cont < 0.10:
				t = max(0.0, min(1.0, (cont - (-0.25)) / 0.35))
				smooth_t = 3.0 * t * t - 2.0 * t * t * t
				target_y = 48.0 + smooth_t * 14.0 + (peaks_raw * 1.5)
			elif cont < 0.30:
				t = (cont - 0.10) / 0.20
				smooth_t = 3.0 * t * t - 2.0 * t * t * t
				target_y = 62.0 + smooth_t * 12.0 + (ridge * 4.0)
			else:
				t = min(1.0, (cont - 0.30) / 0.50)
				smooth_t = 3.0 * t * t - 2.0 * t * t * t
				target_y = 74.0 + (smooth_t * 32.0 + (ridge * 6.0))

			river_raw = abs(pnoise2((wx + 2000.0) / 240.0, (wz + 2000.0) / 240.0, octaves=3))
			if river_raw < 0.055:
				t_r = 1.0 - (river_raw / 0.055)
				r_blend = (t_r * t_r) * 3.5
				target_y = min(target_y, 60.0 - r_blend)

			sculpt = pnoise3(wx / 25.0, target_y / 15.0, wz / 25.0) * 2.0
			final_y = math.floor(target_y + sculpt)
			final_y = max(4, min(final_y, chunk.CHUNK_HEIGHT - 6))
			surface_heights[i * 16 + k] = final_y

	# Helper for flat 1D indexing into flat_bytes
	def set_b(i, j, k, val):
		flat_bytes[i * 4096 + j * 16 + k] = val

	def get_b(i, j, k):
		return flat_bytes[i * 4096 + j * 16 + k]

	# 2. Fill Solid Terrain, Surface Layers & Sea Water
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i
			wz = chunk_offset_z + k
			sy = surface_heights[i * 16 + k]

			set_b(i, 0, k, 14)  # bedrock

			sub_depth = max(1, sy - 3)
			for j in range(1, sub_depth):
				block_num = 5  # stone
				if 30 <= j and rng.randrange(100) < 4:
					block_num = 16  # coal
				elif 10 <= j <= 50 and rng.randrange(100) < 2:
					block_num = 17  # iron
				elif 2 <= j <= 15 and rng.randrange(1000) < 3:
					block_num = 18  # diamond
				set_b(i, j, k, block_num)

			cont = pnoise2(wx / 350.0, wz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)
			river_raw = abs(pnoise2((wx + 2000.0) / 240.0, (wz + 2000.0) / 240.0, octaves=3))
			is_river = river_raw < 0.055

			if sy > 110:
				for j in range(sub_depth, sy):
					set_b(i, j, k, 5)
				set_b(i, sy, k, 2)
			elif sy > 90:
				for j in range(sub_depth, sy + 1):
					set_b(i, j, k, 5)
			elif cont < 0.05 and not is_river:
				for j in range(sub_depth, sy + 1):
					set_b(i, j, k, 6)
			else:
				for j in range(sub_depth, sy):
					set_b(i, j, k, 4)
				set_b(i, sy, k, 4 if sy < 60 else 2)

			if sy < 60:
				for water_y in range(sy + 1, 61):
					set_b(i, water_y, k, 19 if water_y < 60 else 9)

	# 3. Carve 3D Caves
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i
			wz = chunk_offset_z + k
			sy = surface_heights[i * 16 + k]

			entrance_noise = pnoise2((wx + 8000.0) / 100.0, (wz + 8000.0) / 100.0)
			allows_entrance = (entrance_noise > 0.28) and (sy >= 62)

			max_cave_y = min(sy + 1 if allows_entrance else sy - 4, 115)
			if sy <= 61:
				max_cave_y = min(max_cave_y, 48)

			for j in range(9, max_cave_y):
				if get_b(i, j, k) == 14:
					continue

				c1 = pnoise3(wx / 20.0, j / 12.0, wz / 20.0)
				c2 = pnoise3((wx + 400.0) / 20.0, j / 12.0, (wz + 400.0) / 20.0)
				cheese = pnoise3((wx - 200.0) / 35.0, j / 22.0, (wz - 200.0) / 35.0)

				if (c1 * c1 + c2 * c2) < 0.0065 or (cheese > 0.54 and j < 52):
					set_b(i, j, k, 0)

	# 4. Lava Levels in Caves (y <= 8)
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			for j in range(1, 9):
				if get_b(i, j, k) == 0:
					set_b(i, j, k, 20 if j < 8 else 15)

	# 5. Surface Water Lakes (Carved & filled at a single uniform Y level, 100% bounded by solid dirt/stone retaining walls)
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
								set_b(px, lake_surface_y - 1, pz, 19)  # Under water
								
								# Basin floor
								floor_block = 4 if rng.randrange(100) < 70 else 5
								set_b(px, lake_surface_y - 2, pz, floor_block)
								set_b(px, lake_surface_y - 3, pz, 5)
							elif dist_sq <= (radius + 1) * (radius + 1):
								# Watertight solid dirt/stone retaining wall rim extending 1 block above water level
								shore_block = 4 if rng.randrange(100) < 60 else 5
								for ry in range(lake_surface_y - 2, lake_surface_y + 2):
									b_curr = get_b(px, ry, pz)
									if b_curr == 0 or b_curr in (9, 19, 15, 20):
										set_b(px, ry, pz, shore_block)

	# 6. Surface Lava Pools (Carved & filled at a single uniform Y level, 100% bounded by solid stone retaining walls)
	if rng.randrange(100) < 10:
		pool_x = rng.randrange(3, chunk.CHUNK_WIDTH - 3)
		pool_z = rng.randrange(3, chunk.CHUNK_LENGTH - 3)
		pool_surface_y = surface_heights[pool_x * 16 + pool_z]  # Single uniform flat surface height for entire pool

		if 62 <= pool_surface_y <= 80:
			for dx in range(-3, 4):
				for dz in range(-3, 4):
					dist_sq = dx * dx + dz * dz
					px, pz = pool_x + dx, pool_z + dz
					if 0 <= px < chunk.CHUNK_WIDTH and 0 <= pz < chunk.CHUNK_LENGTH:
						col_h = surface_heights[px * 16 + pz]

						if dist_sq <= 2:
							# Clear terrain blocks above pool
							for cy in range(pool_surface_y + 1, col_h + 1):
								set_b(px, cy, pz, 0)

							# Perfectly flat lava surface
							set_b(px, pool_surface_y, pz, 15)       # Lava source top
							set_b(px, pool_surface_y - 1, pz, 20)   # Under lava
							set_b(px, pool_surface_y - 2, pz, 1)    # Stone floor
						elif dist_sq <= 5:
							# Watertight stone retaining wall rim extending 1 block above lava level
							for ry in range(pool_surface_y - 2, pool_surface_y + 2):
								b_curr = get_b(px, ry, pz)
								if b_curr == 0 or b_curr in (9, 19, 15, 20):
									set_b(px, ry, pz, 1)

	# 7. Tree Generation
	trees = []
	for _ in range(8):
		tree_x = rng.randrange(1, chunk.CHUNK_WIDTH - 1)
		tree_z = rng.randrange(1, chunk.CHUNK_LENGTH - 1)
		gy = surface_heights[tree_x * 16 + tree_z]

		if (62 <= gy < 85 and gy + 8 < chunk.CHUNK_HEIGHT and get_b(tree_x, gy, tree_z) == 2):
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

	return bytes(flat_bytes)


def build_section_mesh_process(chunk_x, chunk_z, section_y, center_blocks, north_blocks, south_blocks, east_blocks, west_blocks, block_types_info, water_levels=None, lava_levels=None, center_states=None):
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
					rot_f = facing if b_num in (41, 42, 73, 74, 43, 44, 45, 46, 65, 66, 67, 68, 47, 48, 49, 50, 69, 70, 71, 72) else "NORTH"

					if b_num in (38, 39, 40, 62, 63, 64):
						# Slabs (Bottom, Top, Double)
						sl_h = "TOP" if b_num in (62, 63, 64) else half
						if sl_h == "DOUBLE":
							add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.5, 0.5), [0, 0, 0, 0, 0, 0])
						elif sl_h == "TOP":
							add_custom_box((-0.5, 0.0, -0.5), (0.5, 0.5, 0.5), [0, 0, 0, 0, 0, 0])
						else:
							add_custom_box((-0.5, -0.5, -0.5), (0.5, 0.0, 0.5), [0, 0, 0, 0, 0, 0])

					elif b_num in (41, 42, 73, 74):
						# Stairs (Facing, Half, Shape)
						is_top_stair = (b_num in (73, 74) or half in ("TOP", "UPPER"))
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

					elif b_num in (51, 52, 53):
						# Fences (51), Walls (52), Glass Panes (53)
						nb_n = get_nb(local_x, local_y, local_z - 1)
						nb_s = get_nb(local_x, local_y, local_z + 1)
						nb_w = get_nb(local_x - 1, local_y, local_z)
						nb_e = get_nb(local_x + 1, local_y, local_z)

						def can_conn(nb, d_key):
							if conns and d_key in conns: return conns[d_key]
							if nb == 0 or nb in (9, 19, 15, 20): return False
							if b_num == 51:
								return nb == 51 or (block_types_info.get(nb, {}).get('is_cube', False) and not block_types_info.get(nb, {}).get('transparent', False))
							elif b_num == 52:
								return nb in (52, 53) or (block_types_info.get(nb, {}).get('is_cube', False) and not block_types_info.get(nb, {}).get('transparent', False))
							elif b_num == 53:
								return nb in (53, 52) or (block_types_info.get(nb, {}).get('is_cube', False) and not block_types_info.get(nb, {}).get('transparent', False))
							return False

						c_n = can_conn(nb_n, 'north')
						c_s = can_conn(nb_s, 'south')
						c_w = can_conn(nb_w, 'west')
						c_e = can_conn(nb_e, 'east')

						is_straight = (c_n and c_s and not c_w and not c_e) or (c_w and c_e and not c_n and not c_s)

						if b_num == 51:
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

						elif b_num == 53:
							add_custom_box((-0.03125, -0.5, -0.03125), (0.03125, 0.5, 0.03125), [0, 0, 0, 0, 0, 0])
							if c_n: add_custom_box((-0.03125, -0.5, -0.5), (0.03125, 0.5, -0.03125), [0, 0, 0, 0, 0, 0])
							if c_s: add_custom_box((-0.03125, -0.5, 0.03125), (0.03125, 0.5, 0.5), [0, 0, 0, 0, 0, 0])
							if c_w: add_custom_box((-0.5, -0.5, -0.03125), (-0.03125, 0.5, 0.03125), [0, 0, 0, 0, 0, 0])
							if c_e: add_custom_box((0.03125, -0.5, -0.03125), (0.5, 0.5, 0.03125), [0, 0, 0, 0, 0, 0])
					else:
						for face_idx in range(len(b_info['vertex_positions'])):
							add_face(face_idx, is_translucent)

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
	def __init__(self, seed=None, save_folder=None, render_distance=6):
		self.furnaces = {}  # (x, y, z) -> FurnaceData
		self.chests = {}    # (x, y, z) -> ChestData
		self.item_drop_manager = None
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
		self.save_dir = os.path.join(world_save.SAVES_DIR, self.save_folder, 'chunks')
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

		import gui
		for item_id, item_name, tex_name in gui.TOOL_ITEMS:
			self.texture_manager.add_texture(tex_name)

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

		# Multithreaded Executor (4 Workers) for in-memory Terrain Generation & Section Meshing without IPC pickling overhead
		self.process_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ChunkWorker")
		self.chunk_generation_futures = {}
		self.section_mesh_futures = {}

		self._save_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ChunkSaver")
		self.free_chunk_pool = []  # Deferred handle recycling pool

		self.pending_section_uploads = []
		self.section_mesh_queue = set()

		self.liquid_levels = {}
		self.water_levels = {}
		self.liquid_tick_queue = set()
		self._block_info_cache = None

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
		self.tick_liquids(dt)
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
				res = build_section_mesh_process(cx, cz, sy, c_bytes, n_bytes, s_bytes, e_bytes, w_bytes, info, dict(self.water_levels), dict(self.lava_levels))
				_, _, _, op_pos, op_tex, op_shd, op_idx, tr_pos, tr_tex, tr_shd, tr_idx, missing = res
				chk.send_section_mesh_to_gpu(sy, op_pos, op_tex, op_shd, op_idx, tr_pos, tr_tex, tr_shd, tr_idx)

	def generate_chunk(self, x, z, blocks_only=False):
		chunk_position = (x, 0, z)
		blocks = build_chunk_blocks_process(
			x, z, self.scale, self.octaves, self.persistence, self.lacunarity,
			self.cave_scale, self.cave_threshold, self.save_dir, self.seed)
		if blocks_only:
			return blocks
		return chunk.Chunk(self, chunk_position, blocks=blocks)

	def queue_chunk_sections_for_meshing(self, cx, cz):
		c_pos = (cx, 0, cz)
		if c_pos not in self.chunks:
			return
		chk = self.chunks[c_pos]
		for sy in range(16):
			min_y = sy * 16
			# Skip all-air sections instantly
			has_blocks = False
			for y in range(min_y, min_y + 16):
				base_y = y * 16
				for x in range(16):
					base_xy = x * 4096 + base_y
					for z in range(16):
						if chk.blocks[base_xy + z] != 0:
							has_blocks = True
							break
					if has_blocks: break
				if has_blocks: break

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

		# 2. Budgeted GPU Uploads (capped at 64 KB per frame tick)
		MAX_GPU_UPLOAD_BYTES_PER_FRAME = 64 * 1024
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

		# 3. Submit pending section meshing tasks (max 4 active workers)
		if len(self.section_mesh_futures) < 4 and self.section_mesh_queue:
			slots_free = 4 - len(self.section_mesh_futures)
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
			w_lvls = dict(self.water_levels) if self.water_levels else None
			l_lvls = dict(self.liquid_levels) if self.liquid_levels else None

			for item in pending_list[:slots_free]:
				if item in self.section_mesh_queue:
					self.section_mesh_queue.remove(item)
				cx, cz, sy = item

				c_pos = (cx, 0, cz)
				if c_pos not in self.chunks:
					continue

				center_chk = self.chunks[c_pos]
				c_bytes = bytes(center_chk.blocks)
				c_states = { f"{lx},{ly},{lz}": st.to_dict() for (lx, ly, lz), st in center_chk.block_states.items() if st }

				e_bytes = bytes(self.chunks[(cx + 1, 0, cz)].blocks) if (cx + 1, 0, cz) in self.chunks else None
				w_bytes = bytes(self.chunks[(cx - 1, 0, cz)].blocks) if (cx - 1, 0, cz) in self.chunks else None
				s_bytes = bytes(self.chunks[(cx, 0, cz + 1)].blocks) if (cx, 0, cz + 1) in self.chunks else None
				n_bytes = bytes(self.chunks[(cx, 0, cz - 1)].blocks) if (cx, 0, cz - 1) in self.chunks else None

				self.section_mesh_futures[(cx, cz, sy)] = self.process_executor.submit(
					build_section_mesh_process,
					cx, cz, sy, c_bytes, n_bytes, s_bytes, e_bytes, w_bytes, info, w_lvls, l_lvls, c_states
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
			self.chunks[c_pos] = chunk.Chunk(self, c_pos)
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
			if nb_b in (41, 42, 73, 74):
				if not nb_st:
					nb_st = block_state.BlockState(nb_b)
				new_shape = block_state.calculate_stair_shape(self, nb_pos, nb_st.facing, nb_st.half)
				if new_shape != nb_st.shape:
					nb_st.shape = new_shape
					self.set_block_state(nb_pos, nb_st)

			# 2. Fence connection recalculation
			elif nb_b in (51,):
				if not nb_st:
					nb_st = block_state.BlockState(51)
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

	def tick_liquids(self, dt=0.0):
		"""Official Minecraft Water & Lava Flow Solver."""
		if not self.liquid_tick_queue:
			return

		# Process up to 30 liquid updates per frame tick for smooth, fast fluid flow
		active_coords = [self.liquid_tick_queue.pop() for _ in range(min(30, len(self.liquid_tick_queue)))]

		for pos in active_coords:
			x, y, z = pos
			if y <= 1 or y >= 255:
				continue

			b_num = self.get_block_number(pos)

			# --- 1. TARGET IS AIR BLOCK (b_num == 0) ---
			if b_num == 0:
				above_num = self.get_block_number((x, y + 1, z))
				if above_num in (9, 19):
					self.set_block(pos, 19)
					self.water_levels[pos] = 8
					self.liquid_tick_queue.add(pos)
					if self.get_block_number((x, y - 1, z)) == 0:
						self.liquid_tick_queue.add((x, y - 1, z))
					continue

				if above_num in (15, 20):
					self.set_block(pos, 20)
					self.liquid_levels[pos] = 4
					self.liquid_tick_queue.add(pos)
					if self.get_block_number((x, y - 1, z)) == 0:
						self.liquid_tick_queue.add((x, y - 1, z))
					continue

				# Water Horizontal Spreading Check
				source_count = 0
				upstream_water = []

				for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
					n_num = self.get_block_number((nx, ny, nz))
					if n_num == 9:
						source_count += 1
						upstream_water.append(0)
					elif n_num == 19:
						w_lvl = self.get_water_level((nx, ny, nz))
						if 0 <= w_lvl < 7:
							upstream_water.append(w_lvl)

				down_num = self.get_block_number((x, y - 1, z))
				is_solid_floor = down_num not in (0, 9, 19, 15, 20) or down_num == 9

				if source_count >= 2 and is_solid_floor:
					self.set_block(pos, 9)
					self.water_levels[pos] = 0
					self.liquid_tick_queue.add(pos)
				elif upstream_water:
					min_w = min(upstream_water)
					target_w = min_w + 1
					if target_w <= 7:
						self.set_block(pos, 19)
						self.water_levels[pos] = target_w
						self.liquid_tick_queue.add(pos)
						if down_num == 0:
							self.liquid_tick_queue.add((x, y - 1, z))

				# Lava Horizontal Spreading Check
				upstream_lava = []
				for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
					n_num = self.get_block_number((nx, ny, nz))
					if n_num == 15:
						upstream_lava.append(0)
					elif n_num == 20:
						l_lvl = self.get_lava_level((nx, ny, nz))
						if 0 <= l_lvl < 3:
							upstream_lava.append(l_lvl)

				if upstream_lava:
					min_l = min(upstream_lava)
					target_l = min_l + 1
					if target_l <= 3:
						self.set_block(pos, 20)
						self.liquid_levels[pos] = target_l
						self.liquid_tick_queue.add(pos)
						if down_num == 0:
							self.liquid_tick_queue.add((x, y - 1, z))

			# --- 2. TARGET IS WATER BLOCK (b_num in 9, 19) ---
			elif b_num in (9, 19):
				curr_lvl = self.get_water_level(pos)

				down_pos = (x, y - 1, z)
				if self.get_block_number(down_pos) == 0:
					self.set_block(down_pos, 19)
					self.water_levels[down_pos] = 8
					self.liquid_tick_queue.add(down_pos)

				if curr_lvl < 7:
					for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
						n_pos = (nx, ny, nz)
						if self.get_block_number(n_pos) == 0:
							self.liquid_tick_queue.add(n_pos)

			# --- 3. TARGET IS LAVA BLOCK (b_num in 15, 20) ---
			elif b_num in (15, 20):
				curr_lvl = self.get_lava_level(pos)

				down_pos = (x, y - 1, z)
				if self.get_block_number(down_pos) == 0:
					self.set_block(down_pos, 20)
					self.liquid_levels[down_pos] = 4
					self.liquid_tick_queue.add(down_pos)

				if curr_lvl < 3:
					for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
						n_pos = (nx, ny, nz)
						if self.get_block_number(n_pos) == 0:
							self.liquid_tick_queue.add(n_pos)

	def set_block(self, position, number):
		x, y, z = position
		if y < 0 or y >= 256:
			return

		c_pos = (math.floor(x / chunk.CHUNK_WIDTH), 0, math.floor(z / chunk.CHUNK_LENGTH))
		if c_pos not in self.chunks:
			if number == 0: return
			self.chunks[c_pos] = chunk.Chunk(self, c_pos)

		chk = self.chunks[c_pos]
		lx = int(x % chunk.CHUNK_WIDTH)
		ly = int(y)
		lz = int(z % chunk.CHUNK_LENGTH)

		if chk.get_block_number(lx, ly, lz) == number:
			return

		# Liquid quantity tracking
		if number in (9, 15):
			self.liquid_levels[position] = 5
		elif number == 0:
			if position in self.liquid_levels:
				del self.liquid_levels[position]
			if position in self.water_levels:
				del self.water_levels[position]
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
		for nx, ny, nz in [(px, py, pz), (px + 1, py, pz), (px - 1, py, pz), (px, py + 1, pz), (px, py - 1, pz), (px, py, pz + 1), (px, py, pz - 1)]:
			if 0 <= ny < chunk.CHUNK_HEIGHT:
				self.liquid_tick_queue.add((nx, ny, nz))

		chk.set_block_number(lx, ly, lz, number)
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

	def _save_chunk_to_file(self, chunk_position):
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

		def async_write(path, content):
			try:
				with gzip.open(path, 'wb', compresslevel=1) as f:
					f.write(content)
			except Exception as e:
				print(f"Async chunk save failed: {e}")

		self._save_executor.submit(async_write, save_path, data)

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
				return

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
				except Exception as e:
					pass

			self.chunks[chunk_position] = chk
			self.queue_chunk_sections_for_meshing(chunk_position[0], chunk_position[2])

			# Trigger border section re-meshing for adjacent loaded neighbors
			cx, _, cz = chunk_position
			for nx, nz in [(cx + 1, cz), (cx - 1, cz), (cx, cz + 1), (cx, cz - 1)]:
				if (nx, 0, nz) in self.chunks:
					self.queue_chunk_sections_for_meshing(nx, nz)
			return  # 1 chunk per frame max to guarantee O(1) main-thread execution time

	def _rebuild_load_queue(self, player_cx, player_cz):
		rd = self.render_distance
		chunks = self.chunks
		futures = self.chunk_generation_futures

		queue = []
		for dx, dz in RING_OFFSETS:
			if max(abs(dx), abs(dz)) > rd:
				continue
			c_pos = (player_cx + dx, 0, player_cz + dz)
			if c_pos not in chunks and c_pos not in futures:
				queue.append(c_pos)
		self._load_queue = queue

	def _submit_generations(self):
		while self._load_queue and len(self.chunk_generation_futures) < 2:
			chunk_pos = self._load_queue.pop(0)
			if chunk_pos in self.chunks or chunk_pos in self.chunk_generation_futures:
				continue
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
