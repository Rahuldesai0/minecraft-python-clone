import math
import time
from random import Random
from noise import *
import threading
import gzip
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pyglet.gl as gl

import chunk

import block_type
import texture_manager

# import custom block models
import models.leaves
import models.liquid
import models.plant
import models.cactus

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


def build_chunk_blocks_process(x, z, scale, octaves, persistence, lacunarity, cave_scale, cave_threshold, save_dir):
	"""Independent worker function for ProcessPoolExecutor.
	Generates authentic Minecraft 1.0 style terrain:
	- Smooth plains, sandy beaches, deep oceans, and high mountain ranges.
	- NO grass underwater or on shores (sand/dirt only for y <= 61).
	- NO floating water walls (water is cleanly bounded in ocean/river basins).
	- Dry underground caves carved through stone with lava pools at y <= 8.
	- Rare surface lava lakes on plains/hills."""
	save_path = os.path.join(save_dir, f"{x}_{z}.chunk")
	if os.path.exists(save_path):
		try:
			with gzip.open(save_path, 'rb') as f:
				data = f.read()
			if len(data) == chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH:
				blocks = [[[0 for _ in range(chunk.CHUNK_LENGTH)]
					for _ in range(chunk.CHUNK_HEIGHT)]
					for _ in range(chunk.CHUNK_WIDTH)]
				idx = 0
				for x_pos in range(chunk.CHUNK_WIDTH):
					for y_pos in range(chunk.CHUNK_HEIGHT):
						for z_pos in range(chunk.CHUNK_LENGTH):
							blocks[x_pos][y_pos][z_pos] = data[idx]
							idx += 1
				return blocks
		except Exception:
			pass

	blocks = [[[0 for _ in range(chunk.CHUNK_LENGTH)]
		for _ in range(chunk.CHUNK_HEIGHT)]
		for _ in range(chunk.CHUNK_WIDTH)]

	rng = Random((x * 341873128712 + z * 132897987541) & ((1 << 64) - 1))
	surface_heights = [[0 for _ in range(chunk.CHUNK_LENGTH)]
		for _ in range(chunk.CHUNK_WIDTH)]

	chunk_offset_x = x * chunk.CHUNK_WIDTH
	chunk_offset_z = z * chunk.CHUNK_LENGTH

	# 1. Heightmap (Smooth Beach Descent, Plains, Rolling Hills & Steep Cone-Shaped Mountain Peaks)
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i
			wz = chunk_offset_z + k

			# Continentalness: Ocean vs Coast vs Plains vs High Mountains
			cont = pnoise2(wx / 350.0, wz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)

			# Hills / Cone Peak noise (steep exponent for sharp cone mountain peaks)
			peaks_raw = pnoise2((wx + 1000.0) / 85.0, (wz + 1000.0) / 85.0, octaves=4, persistence=0.5, lacunarity=2.0)
			ridge = 1.0 - abs(peaks_raw * 2.0)
			cone_shape = max(0.0, ridge) ** 2.4  # Sharp, steep cone peak profile

			# Compute target surface height
			if cont < 0.10:
				# Smooth gradual S-curve from deep ocean (y=48) to beach (y=60) to plains (y=62)
				t = max(0.0, min(1.0, (cont - (-0.25)) / 0.35))
				smooth_t = 3.0 * t * t - 2.0 * t * t * t
				target_y = 48.0 + smooth_t * 14.0 + (peaks_raw * 1.5)
			elif cont < 0.20:
				# Grassy Plains & Rolling Hills (y = 62..75)
				t = (cont - 0.10) / 0.10
				target_y = 62.0 + t * 13.0 + (ridge * 5.0)
			else:
				# Soaring Cone-Shaped Mountain Peaks (reaching heights 140 to 155 blocks!)
				t = min(1.0, (cont - 0.20) / 0.50)
				mountain_boost = (t ** 1.1) * 80.0 * (0.25 + 0.75 * cone_shape)
				target_y = 75.0 + mountain_boost

			# Winding Rivers (smooth shallow U-shaped channels)
			river_raw = abs(pnoise2((wx + 2000.0) / 240.0, (wz + 2000.0) / 240.0, octaves=3))
			if river_raw < 0.055:
				t_r = 1.0 - (river_raw / 0.055)
				r_blend = (t_r * t_r) * 3.5
				target_y = min(target_y, 60.0 - r_blend)

			sculpt = pnoise3(wx / 25.0, target_y / 15.0, wz / 25.0) * 2.0
			final_y = math.floor(target_y + sculpt)
			final_y = max(4, min(final_y, chunk.CHUNK_HEIGHT - 6))
			surface_heights[i][k] = final_y

	# 2. Step 1 & 2: Fill Solid Terrain, Surface Layers & Sea Water
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i
			wz = chunk_offset_z + k
			sy = surface_heights[i][k]
			col_blocks = blocks[i]

			col_blocks[0][k] = 14  # bedrock

			# Fill solid stone & ores below sub-surface
			sub_depth = max(1, sy - 3)
			for j in range(1, sub_depth):
				block_num = 5  # stone
				if 30 <= j and rng.randrange(100) < 4:
					block_num = 16  # coal
				elif 10 <= j <= 50 and rng.randrange(100) < 2:
					block_num = 17  # iron
				elif 2 <= j <= 15 and rng.randrange(1000) < 3:
					block_num = 18  # diamond
				col_blocks[j][k] = block_num

			cont = pnoise2(wx / 350.0, wz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)
			river_raw = abs(pnoise2((wx + 2000.0) / 240.0, (wz + 2000.0) / 240.0, octaves=3))
			is_river = river_raw < 0.055

			# Sub-surface & Top surface layer decoration
			if sy > 110:
				# Snow-capped high mountain peak
				for j in range(sub_depth, sy):
					col_blocks[j][k] = 5
				col_blocks[sy][k] = 2  # grass / snow cap
			elif sy > 90:
				# Stone cliff peak face
				for j in range(sub_depth, sy + 1):
					col_blocks[j][k] = 5
			elif cont < 0.05 and not is_river:
				# Coastal Ocean & Sea Bed (SAND - gradual beach descent)
				for j in range(sub_depth, sy + 1):
					col_blocks[j][k] = 6  # sand
			else:
				# Rivers, Plains & Hills (Dirt under water, Grass on banks)
				for j in range(sub_depth, sy):
					col_blocks[j][k] = 4  # dirt
				col_blocks[sy][k] = 4 if sy < 60 else 2  # dirt under water, grass above water!

			# Clean sea-level water fill (ONLY above ocean/river bed up to y=60)
			if sy < 60:
				for water_y in range(sy + 1, 61):
					col_blocks[water_y][k] = 19 if water_y < 60 else 9

	# 3. Step 3: Carve 3D Caves (Noodle Tunnels & Caverns)
	# Allows select cave tunnels to breach the surface on dry land (sy >= 62) as cave entrances!
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			wx = chunk_offset_x + i
			wz = chunk_offset_z + k
			sy = surface_heights[i][k]
			col_blocks = blocks[i]

			entrance_noise = pnoise2((wx + 8000.0) / 100.0, (wz + 8000.0) / 100.0)
			allows_entrance = (entrance_noise > 0.28) and (sy >= 62)

			if allows_entrance:
				max_cave_y = min(sy + 1, 115)
			else:
				max_cave_y = min(sy - 4, 112)

			if sy <= 61:
				max_cave_y = min(max_cave_y, 48)

			for j in range(9, max_cave_y):
				if col_blocks[j][k] == 14:  # bedrock
					continue

				c1 = pnoise3(wx / 20.0, j / 12.0, wz / 20.0)
				c2 = pnoise3((wx + 400.0) / 20.0, j / 12.0, (wz + 400.0) / 20.0)
				cheese = pnoise3((wx - 200.0) / 35.0, j / 22.0, (wz - 200.0) / 35.0)

				is_noodle = (c1 * c1 + c2 * c2) < 0.0065
				is_cheese = cheese > 0.54 and j < 52

				if is_noodle or is_cheese:
					col_blocks[j][k] = 0  # carve cave air

	# 4. Step 4: Lava Levels in Caves (y <= 8)
	for i in range(chunk.CHUNK_WIDTH):
		for k in range(chunk.CHUNK_LENGTH):
			col_blocks = blocks[i]
			for j in range(1, 9):
				if col_blocks[j][k] == 0:  # air inside cave
					col_blocks[j][k] = 20 if j < 8 else 15  # lava!

	# 5. Surface Water Lakes (Placed on flat areas with dirt & stone floor & shores, like lava pools)
	if rng.randrange(100) < 40:  # ~40% chance per chunk
		lake_cx = rng.randrange(2, chunk.CHUNK_WIDTH - 2)
		lake_cz = rng.randrange(2, chunk.CHUNK_LENGTH - 2)

		radius = rng.randrange(3, 7)  # Lake radius: 3 to 6 blocks
		sample_heights = []
		for dx in range(-radius, radius + 1):
			for dz in range(-radius, radius + 1):
				px = lake_cx + dx
				pz = lake_cz + dz
				if 0 <= px < chunk.CHUNK_WIDTH and 0 <= pz < chunk.CHUNK_LENGTH:
					sample_heights.append(surface_heights[px][pz])

		if sample_heights:
			min_h = min(sample_heights)
			max_h = max(sample_heights)

			# Only place lake if terrain is approximately flat
			if (max_h - min_h <= 2) and (min_h >= 62):
				lake_y = min_h

				for dx in range(-radius - 1, radius + 2):
					for dz in range(-radius - 1, radius + 2):
						dist_sq = dx * dx + dz * dz
						px = lake_cx + dx
						pz = lake_cz + dz
						if 0 <= px < chunk.CHUNK_WIDTH and 0 <= pz < chunk.CHUNK_LENGTH:
							py = surface_heights[px][pz]
							if dist_sq <= radius * radius:
								# Water basin center
								blocks[px][py][pz] = 9      # water top
								blocks[px][py - 1][pz] = 19  # under water
								
								# Dirt and stone floor
								floor_block = 4 if rng.randrange(100) < 70 else 5  # dirt / stone
								blocks[px][py - 2][pz] = floor_block
								blocks[px][py - 3][pz] = 5  # stone underneath
							elif dist_sq <= (radius + 1) * (radius + 1):
								# Lake shore rim (dirt & stone)
								shore_block = 4 if rng.randrange(100) < 60 else 5  # dirt / stone shore
								blocks[px][py][pz] = shore_block

	# 6. Surface Lava Pools (Rare surface lava lakes surrounded by stone/cobble)
	if rng.randrange(100) < 10:  # ~10% chance per chunk for a surface lava pool
		pool_x = rng.randrange(3, chunk.CHUNK_WIDTH - 3)
		pool_z = rng.randrange(3, chunk.CHUNK_LENGTH - 3)
		pool_y = surface_heights[pool_x][pool_z]

		if 62 <= pool_y <= 80:
			for dx in range(-2, 3):
				for dz in range(-2, 3):
					dist_sq = dx * dx + dz * dz
					px = pool_x + dx
					pz = pool_z + dz
					py = surface_heights[px][pz]
					if dist_sq <= 2:
						blocks[px][py][pz] = 15  # lava
					elif dist_sq <= 5:
						blocks[px][py][pz] = 1  # cobblestone/stone

	# 6. Tree Generation (Spawns ONLY on Grass y >= 62)
	trees = []
	for _ in range(8):
		tree_x = rng.randrange(1, chunk.CHUNK_WIDTH - 1)
		tree_z = rng.randrange(1, chunk.CHUNK_LENGTH - 1)
		gy = surface_heights[tree_x][tree_z]

		if (62 <= gy < 85 and
				gy + 8 < chunk.CHUNK_HEIGHT and
				blocks[tree_x][gy][tree_z] == 2):
			has_adjacent_tree = False
			for dx in range(-2, 3):
				for dz in range(-2, 3):
					if (tree_x + dx, gy, tree_z + dz) in trees:
						has_adjacent_tree = True
						break
				if has_adjacent_tree:
					break

			if not has_adjacent_tree:
				trunk_y = gy + 1
				for n in range(5):
					blocks[tree_x][trunk_y + n][tree_z] = 8

				leaves_height = trunk_y + 3
				for dx in range(-2, 3):
					for dz in range(-2, 3):
						if 0 <= tree_x + dx < chunk.CHUNK_WIDTH and 0 <= tree_z + dz < chunk.CHUNK_LENGTH:
							blocks[tree_x + dx][leaves_height][tree_z + dz] = 13
							blocks[tree_x + dx][leaves_height + 1][tree_z + dz] = 13
				for dx in range(-1, 2):
					for dz in range(-1, 2):
						if 0 <= tree_x + dx < chunk.CHUNK_WIDTH and 0 <= tree_z + dz < chunk.CHUNK_LENGTH:
							blocks[tree_x + dx][leaves_height + 2][tree_z + dz] = 13

				trees.append((tree_x, gy, tree_z))

	return blocks


class GeneratedChunkData:
	"""Block storage used by the background terrain generator (no OpenGL)."""
	def __init__(self):
		self.blocks = [[[0 for _ in range(chunk.CHUNK_LENGTH)]
			for _ in range(chunk.CHUNK_HEIGHT)]
			for _ in range(chunk.CHUNK_WIDTH)]

class World:
	def __init__(self):
		self.texture_manager = texture_manager.Texture_manager(16, 16, 256)
		self.block_types = [None]

		self.block_types.append(block_type.Block_type(self.texture_manager, name="cobblestone", block_face_textures = {"all": "cobblestone"}, break_time = 1.5, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="grass", block_face_textures = {"top": "grass", "bottom": "dirt", "sides": "grass_side"}, break_time = 0.4, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="grass_block", block_face_textures = {"all": "grass"}, break_time = 0.4, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dirt", block_face_textures = {"all": "dirt"}, break_time = 0.4, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="stone", block_face_textures = {"all": "stone"}, break_time = 1.5, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="sand", block_face_textures = {"all": "sand"}, break_time = 0.4, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="planks", block_face_textures = {"all": "planks"}, break_time = 0.9, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="log", block_face_textures = {"top": "log_top", "bottom": "log_top", "sides": "log_side"}, break_time = 0.9, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="water", block_face_textures = {"all": "water"},  model = models.liquid, transparent=True, break_time = float('inf'), requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="rose", block_face_textures = {"all": "rose"},  model = models.plant, break_time = 0.15, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="cactus", block_face_textures = {"top": "cactus_top", "bottom": "cactus_bottom", "sides": "cactus_side"},  model = models.cactus, break_time = 0.4, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="dead_bush", block_face_textures = {"all": "dead_bush"},  model = models.plant, break_time = 0.15, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="leaves", block_face_textures = {"all": "leaves"},  model = models.leaves, break_time = 0.2, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="bedrock", block_face_textures = {"all": "bedrock"}, break_time = float('inf'), requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="lava", block_face_textures = {"all": "lava"},  model = models.liquid, transparent=True, break_time = float('inf'), requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="coal_ore", block_face_textures = {"all": "coal_ore"}, break_time = 2.0, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_ore", block_face_textures = {"all": "iron_ore"}, break_time = 2.0, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="diamond_ore", block_face_textures = {"all": "diamond_ore"}, break_time = 2.5, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="under_water", block_face_textures = {"all": "water"}, model = models.liquid, transparent=True, break_time = float('inf'), requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="under_lava", block_face_textures = {"all": "lava"}, model = models.liquid, transparent=True, break_time = float('inf'), requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="glass", block_face_textures = {"all": "glass"}, transparent=True, break_time = 0.3, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="bricks", block_face_textures = {"all": "bricks"}, break_time = 1.5, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="bookshelf", block_face_textures = {"top": "planks", "bottom": "planks", "sides": "bookshelf"}, break_time = 0.9, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="obsidian", block_face_textures = {"all": "obsidian"}, break_time = 5.0, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="tnt", block_face_textures = {"top": "tnt_top", "bottom": "tnt_bottom", "sides": "tnt_side"}, break_time = 0.5, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="crafting_table", block_face_textures = {"top": "crafting_table_top", "bottom": "planks", "sides": "crafting_table_x"}, break_time = 0.9, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="furnace", block_face_textures = {"top": "furnace_y", "bottom": "stone", "sides": "furnace_side", "front": "furnace_front"}, break_time = 1.5, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="gold_block", block_face_textures = {"all": "gold_block"}, break_time = 2.0, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="iron_block", block_face_textures = {"all": "iron_block"}, break_time = 2.0, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="diamond_block", block_face_textures = {"all": "diamond_block"}, break_time = 2.5, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="snow", block_face_textures = {"all": "snow"}, break_time = 0.3, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="ice", block_face_textures = {"all": "ice"}, transparent=True, break_time = 0.5, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="yellow_flower", block_face_textures = {"all": "yellow_flower"}, model = models.plant, break_time = 0.15, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="sponge", block_face_textures = {"all": "sponge"}, break_time = 0.6, requires_tool = False))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="gold_ore", block_face_textures = {"all": "gold_ore"}, break_time = 2.0, requires_tool = True))
		self.block_types.append(block_type.Block_type(self.texture_manager, name="redstone_ore", block_face_textures = {"all": "redstone_ore"}, break_time = 2.0, requires_tool = True))

		# Register non-block item textures (Sticks, Pickaxes, Axes, Shovels, Swords) into texture_manager
		import gui
		for item_id, item_name, tex_name in gui.TOOL_ITEMS:
			self.texture_manager.add_texture(tex_name)

		self.texture_manager.generate_mipmaps()

		self.chunks = {}
				
		self.scale = 500.0  # Controls the frequency of the noise
		self.octaves = 4   # Increased number of layers of noise to combine for more detail
		self.persistence = 0.5
		self.lacunarity = 2.5

		self.cave_scale = 15.0  # Controls the frequency of the cave noise
		self.cave_threshold = 0.1 # Threshold for cave generation

		self.render_distance = 6
		self.unload_distance = self.render_distance + 3  # Hysteresis buffer zone (3 extra chunks) prevents load/unload thrashing
		self.dirty_chunks = set()  # chunks modified by player (need saving)
		self._last_player_chunk = None  # cache to avoid redundant work
		self._load_queue = []  # pre-sorted list of chunk positions to generate

		# ensure save directory exists
		os.makedirs(SAVE_DIR, exist_ok=True)

		# ProcessPoolExecutor runs chunk block generation in disjoint OS processes with their own GIL and CPU cores.
		self.chunk_generation_executor = ProcessPoolExecutor(max_workers=2)
		self.chunk_generation_futures = {}  # {chunk_position: future}

		# Background ThreadPoolExecutors for async mesh building and async gzip chunk saving
		self.mesh_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="MeshBuilder")
		self._save_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ChunkSaver")
		self.free_chunk_pool = []  # Sodium OpenGL VAO/VBO handle reuse pool (eliminates glDeleteBuffers pipeline flushes)
		self.load_queue_ring = 0

		self.chunk_load_queue = {}
		self.active_loading_chunks = []
		self.active_threads = 0

		# Liquid Mechanics tracking
		self.liquid_levels = {}
		self.water_levels = {}
		self.liquid_tick_queue = set()

		# Generate a small spawn area synchronously so the player has ground
		for x in range(-2, 3):
			for z in range(-2, 3):
				result = self.generate_chunk(x, z)
				self.chunks[(x, 0, z)] = result

		# Build and upload meshes for spawn chunks immediately
		for chunk_position in list(self.chunks.keys()):
			self.chunks[chunk_position].update_subchunk_meshes()
			self.chunks[chunk_position].update_mesh()
			self.chunks[chunk_position].send_mesh_data_to_gpu()

	def generate_chunk(self, x, z, blocks_only=False):
		chunk_position = (x, 0, z)
		blocks = build_chunk_blocks_process(
			x, z, self.scale, self.octaves, self.persistence, self.lacunarity,
			self.cave_scale, self.cave_threshold, SAVE_DIR)
		if blocks_only:
			return blocks
		current_chunk = chunk.Chunk(self, chunk_position)
		current_chunk.blocks = blocks
		return current_chunk

	def add_chunk_to_load_queue(self, chunk_position):
		chunk_obj = self.chunks[chunk_position]
		self.chunk_load_queue[chunk_position] = {"chunk": chunk_obj, "future": None, "running": False}

	def process_load_queue(self, player_position = (0, 0, 0)):
		start_time = time.perf_counter()
		budget_seconds = 0.0015  # 1.5 ms max budget per frame for main thread GPU uploads

		player_cx = math.floor(player_position[0] / chunk.CHUNK_WIDTH)
		player_cz = math.floor(player_position[2] / chunk.CHUNK_LENGTH)

		# 1. Upload AT MOST ONE completed mesh buffer to GPU per frame to guarantee 0 upload spikes
		for chunk_position in list(self.chunk_load_queue.keys()):
			queue_object = self.chunk_load_queue[chunk_position]
			if queue_object["running"] and queue_object["future"] is not None and queue_object["future"].done():
				# Obsolete check: if player moved too far away, discard without uploading
				if max(abs(chunk_position[0] - player_cx), abs(chunk_position[2] - player_cz)) > self.unload_distance:
					del self.chunk_load_queue[chunk_position]
					if chunk_position in self.active_loading_chunks:
						self.active_loading_chunks.remove(chunk_position)
					continue

				queue_object["chunk"].send_mesh_data_to_gpu()
				del self.chunk_load_queue[chunk_position]
				if chunk_position in self.active_loading_chunks:
					self.active_loading_chunks.remove(chunk_position)
				break  # Strictly 1 GPU mesh upload per frame cap

		# 2. Submit pending mesh generation tasks to background ThreadPoolExecutor (1 task max per frame tick)
		for chunk_position, queue_object in list(self.chunk_load_queue.items()):
			if not queue_object["running"]:
				target_chunk = queue_object["chunk"]
				def build_mesh(c=target_chunk):
					c.update_subchunk_meshes()
					c.update_mesh()
				queue_object["future"] = self.mesh_executor.submit(build_mesh)
				queue_object["running"] = True
				if chunk_position not in self.active_loading_chunks:
					self.active_loading_chunks.append(chunk_position)
				break  # Drip-feed 1 mesh submission per frame tick

	def get_chunk_position(self, position):
		x, y, z = position

		return (
			math.floor(x / chunk.CHUNK_WIDTH),
			math.floor(y / chunk.CHUNK_HEIGHT),
			math.floor(z / chunk.CHUNK_LENGTH))

	def get_local_position(self, position):
		x, y, z = position

		return (
			int(x % chunk.CHUNK_WIDTH),
			int(y % chunk.CHUNK_HEIGHT),
			int(z % chunk.CHUNK_LENGTH))

	def get_block_number(self, position):
		x, y, z = position
		chunk_position = self.get_chunk_position(position)

		# Keep a local reference: a mesh worker can be reading a neighbouring
		# chunk while the main thread unloads it.
		current_chunk = self.chunks.get(chunk_position)
		if current_chunk is None:
			return 0

		lx, ly, lz = self.get_local_position(position)

		block_number = current_chunk.blocks[lx][ly][lz]
		return block_number

	def is_opaque_block(self, position):
		block_type = self.block_types[self.get_block_number(position)]

		if not block_type:
			return False

		return not block_type.transparent

	def get_water_level(self, pos):
		"""Returns the exact Minecraft water level integer (0..8) for pos."""
		b_num = self.get_block_number(pos)
		if b_num == 9:
			return 0
		if b_num == 19:
			if pos in self.water_levels:
				return self.water_levels[pos]
			x, y, z = pos
			if self.get_block_number((x, y + 1, z)) in (9, 19):
				self.water_levels[pos] = 8
				return 8
			min_p = 999
			for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
				n_num = self.get_block_number((nx, ny, nz))
				if n_num == 9:
					min_p = min(min_p, 0)
				elif n_num == 19:
					n_lvl = self.water_levels.get((nx, ny, nz))
					if n_lvl is not None and n_lvl < 7:
						eff = 0 if n_lvl == 8 else n_lvl
						min_p = min(min_p, eff)
			if min_p < 7:
				calc_lvl = min_p + 1
				self.water_levels[pos] = calc_lvl
				return calc_lvl
			self.water_levels[pos] = 7
			return 7
		return 0

	def get_lava_level(self, pos):
		"""Returns the exact Minecraft lava level integer (0..4) for pos."""
		b_num = self.get_block_number(pos)
		if b_num == 15:
			return 0
		if b_num == 20:
			if pos in self.liquid_levels:
				return self.liquid_levels[pos]
			x, y, z = pos
			if self.get_block_number((x, y + 1, z)) in (15, 20):
				self.liquid_levels[pos] = 4
				return 4
			min_p = 999
			for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
				n_num = self.get_block_number((nx, ny, nz))
				if n_num == 15:
					min_p = min(min_p, 0)
				elif n_num == 20:
					n_lvl = self.liquid_levels.get((nx, ny, nz))
					if n_lvl is not None and n_lvl < 3:
						eff = 0 if n_lvl == 4 else n_lvl
						min_p = min(min_p, eff)
			if min_p < 3:
				calc_lvl = min_p + 1
				self.liquid_levels[pos] = calc_lvl
				return calc_lvl
			self.liquid_levels[pos] = 3
			return 3
		return 0

	def tick_liquids(self):
		"""Official Minecraft Water & Lava Flow Solver.
		Event-driven: runs only for active liquid coordinates in self.liquid_tick_queue.
		"""
		if not self.liquid_tick_queue:
			return

		active_coords = list(self.liquid_tick_queue)
		self.liquid_tick_queue.clear()

		for pos in active_coords:
			x, y, z = pos
			b_num = self.get_block_number(pos)

			# --- 1. WATER ENGINE ---
			if b_num == 0:
				above_num = self.get_block_number((x, y + 1, z))
				if above_num in (9, 19):
					self.set_block(pos, 19)
					self.water_levels[pos] = 8
					self.liquid_tick_queue.add(pos)
					down_pos = (x, y - 1, z)
					if y > 1 and self.get_block_number(down_pos) == 0:
						self.liquid_tick_queue.add(down_pos)
					continue

				if above_num in (15, 20):
					self.set_block(pos, 20)
					self.liquid_levels[pos] = 4
					self.liquid_tick_queue.add(pos)
					down_pos = (x, y - 1, z)
					if y > 1 and self.get_block_number(down_pos) == 0:
						self.liquid_tick_queue.add(down_pos)
					continue

				# Water Horizontal Flow check (Vanilla Minecraft specification)
				source_count = 0
				upstream_levels = []

				for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
					n_num = self.get_block_number((nx, ny, nz))
					n_down_num = self.get_block_number((nx, ny - 1, nz))
					if n_down_num not in (0, 9, 19, 15, 20):
						if n_num == 9:
							source_count += 1
							upstream_levels.append(0)
						elif n_num == 19:
							n_lvl = self.get_water_level((nx, ny, nz))
							if 0 <= n_lvl <= 8:
								upstream_levels.append(0 if n_lvl == 8 else n_lvl)

				down_num = self.get_block_number((x, y - 1, z))
				is_solid_floor = down_num not in (0, 9, 19, 15, 20) or down_num == 9

				# Infinite Source Creation: Requires AT LEAST 2 actual Source Blocks (9) over solid floor
				if source_count >= 2 and is_solid_floor:
					self.set_block(pos, 9)
					self.water_levels[pos] = 0
					self.liquid_tick_queue.add(pos)
				elif upstream_levels:
					min_lvl = min(upstream_levels)
					target_lvl = min_lvl + 1
					if target_lvl <= 7:
						self.set_block(pos, 19)
						self.water_levels[pos] = target_lvl
						self.liquid_tick_queue.add(pos)
						down_pos = (x, y - 1, z)
						if y > 1 and down_num == 0:
							self.liquid_tick_queue.add(down_pos)

				# Lava Horizontal Flow check (3-Block Flow Distance, NO source creation)
				lava_upstream = []
				for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
					n_num = self.get_block_number((nx, ny, nz))
					n_down_num = self.get_block_number((nx, ny - 1, nz))
					if n_down_num not in (0, 9, 19, 15, 20):
						if n_num == 15:
							lava_upstream.append(0)
						elif n_num == 20:
							n_lvl = self.get_lava_level((nx, ny, nz))
							if 0 <= n_lvl <= 4:
								lava_upstream.append(0 if n_lvl == 4 else n_lvl)

				if lava_upstream:
					min_l = min(lava_upstream)
					target_l = min_l + 1
					if target_l <= 3:
						self.set_block(pos, 20)
						self.liquid_levels[pos] = target_l
						self.liquid_tick_queue.add(pos)
						down_pos = (x, y - 1, z)
						if y > 1 and down_num == 0:
							self.liquid_tick_queue.add(down_pos)

			elif b_num in (9, 19):
				curr_lvl = self.get_water_level(pos)

				down_pos = (x, y - 1, z)
				if y > 1 and self.get_block_number(down_pos) == 0:
					self.set_block(down_pos, 19)
					self.water_levels[down_pos] = 8
					self.liquid_tick_queue.add(down_pos)
					continue

				down_num = self.get_block_number((x, y - 1, z))
				is_supported = down_num not in (0, 9, 19, 15, 20) or (self.water_levels.get((x, y - 1, z)) == 8)

				if is_supported and b_num == 19:
					source_count = 0
					upstream_levels = []

					for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
						n_num = self.get_block_number((nx, ny, nz))
						n_down_num = self.get_block_number((nx, ny - 1, nz))
						if n_down_num not in (0, 9, 19, 15, 20):
							if n_num == 9:
								source_count += 1
								upstream_levels.append(0)
							elif n_num == 19:
								n_lvl = self.get_water_level((nx, ny, nz))
								if 0 <= n_lvl <= 8:
									eff_lvl = 0 if n_lvl == 8 else n_lvl
									if eff_lvl < curr_lvl or curr_lvl == 0:
										upstream_levels.append(eff_lvl)

					is_solid_floor = down_num not in (0, 9, 19, 15, 20) or down_num == 9

					if source_count >= 2 and is_solid_floor:
						new_id, target_lvl = 9, 0
					elif upstream_levels:
						new_id = 19
						min_lvl = min(upstream_levels)
						target_lvl = min_lvl + 1
						if target_lvl > 7:
							new_id = 0
					else:
						new_id, target_lvl = 0, 7

					if (target_lvl != curr_lvl or new_id != b_num) and new_id != 0:
						self.set_block(pos, new_id)
						self.water_levels[pos] = target_lvl
						for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
							if ny > 0:
								self.liquid_tick_queue.add((nx, ny, nz))

				if is_supported and curr_lvl < 7:
					for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
						n_pos = (nx, ny, nz)
						if ny > 0 and self.get_block_number(n_pos) == 0:
							self.liquid_tick_queue.add(n_pos)

			# --- 2. LAVA ENGINE ---
			elif b_num in (15, 20):
				curr_l = self.get_lava_level(pos)

				down_pos = (x, y - 1, z)
				if y > 1 and self.get_block_number(down_pos) == 0:
					self.set_block(down_pos, 20)
					self.liquid_levels[down_pos] = 4
					self.liquid_tick_queue.add(down_pos)
					continue

				down_num = self.get_block_number((x, y - 1, z))
				is_supported = down_num not in (0, 9, 19, 15, 20) or (self.liquid_levels.get((x, y - 1, z)) == 4)

				if is_supported and b_num == 20:
					lava_upstream = []

					for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
						n_num = self.get_block_number((nx, ny, nz))
						n_down_num = self.get_block_number((nx, ny - 1, nz))
						if n_down_num not in (0, 9, 19, 15, 20):
							if n_num == 15:
								lava_upstream.append(0)
							elif n_num == 20:
								n_lvl = self.get_lava_level((nx, ny, nz))
								if 0 <= n_lvl <= 4:
									eff_l = 0 if n_lvl == 4 else n_lvl
									if eff_l < curr_l or curr_l == 0:
										lava_upstream.append(eff_l)

					if lava_upstream:
						new_id = 20
						min_l = min(lava_upstream)
						target_l = min_l + 1
						if target_l > 3:
							new_id = 0
					else:
						new_id, target_l = 0, 4

					if (target_l != curr_l or new_id != b_num) and new_id != 0:
						self.set_block(pos, new_id)
						self.liquid_levels[pos] = target_l
						for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
							if ny > 0:
								self.liquid_tick_queue.add((nx, ny, nz))

				if is_supported and curr_l < 3:
					for nx, ny, nz in [(x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1)]:
						n_pos = (nx, ny, nz)
						if ny > 0 and self.get_block_number(n_pos) == 0:
							self.liquid_tick_queue.add(n_pos)

	def set_block(self, position, number):
		x, y, z = position
		chunk_position = self.get_chunk_position(position)

		if not chunk_position in self.chunks:
			if number == 0:
				return # no point in creating a whole new chunk if we're not gonna be adding anything to it

			self.chunks[chunk_position] = chunk.Chunk(self, chunk_position)

		if self.get_block_number(position) == number:
			return

		# Liquid quantity tracking
		if number in (9, 15):
			self.liquid_levels[position] = 5
		elif number == 0:
			if position in self.liquid_levels:
				del self.liquid_levels[position]

		px, py, pz = position
		for nx, ny, nz in [(px, py, pz), (px + 1, py, pz), (px - 1, py, pz), (px, py + 1, pz), (px, py - 1, pz), (px, py, pz + 1), (px, py, pz - 1)]:
			if 0 <= ny < chunk.CHUNK_HEIGHT:
				self.liquid_tick_queue.add((nx, ny, nz))

		lx, ly, lz = self.get_local_position(position)

		def try_update_chunk_at_position(chunk_position, position):
			if chunk_position in self.chunks and not chunk_position in self.active_loading_chunks:
				self.chunks[chunk_position].update_at_position(position)

				self.chunks[chunk_position].update_mesh()
				self.chunks[chunk_position].send_mesh_data_to_gpu()

		self.chunks[chunk_position].blocks[lx][ly][lz] = number
		self.dirty_chunks.add(chunk_position)
		try_update_chunk_at_position(chunk_position, position)

		cx, cy, cz = chunk_position

		if lx == chunk.CHUNK_WIDTH - 1: try_update_chunk_at_position((cx + 1, cy, cz), (x + 1, y, z))
		if lx == 0: try_update_chunk_at_position((cx - 1, cy, cz), (x - 1, y, z))

		if ly == chunk.CHUNK_HEIGHT - 1: try_update_chunk_at_position((cx, cy + 1, cz), (x, y + 1, z))
		if ly == 0: try_update_chunk_at_position((cx, cy - 1, cz), (x, y - 1, z))

		if lz == chunk.CHUNK_LENGTH - 1: try_update_chunk_at_position((cx, cy, cz + 1), (x, y, z + 1))
		if lz == 0: try_update_chunk_at_position((cx, cy, cz - 1), (x, y, z - 1))

	def _build_chunk_blocks(self, x, z):
		"""Load or generate plain block data in the background worker."""
		save_path = os.path.join(SAVE_DIR, f"{x}_{z}.chunk")
		if os.path.exists(save_path):
			try:
				with gzip.open(save_path, 'rb') as f:
					data = f.read()
				if len(data) != chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH:
					raise ValueError("invalid chunk save size")

				blocks = GeneratedChunkData().blocks
				idx = 0
				for x_pos in range(chunk.CHUNK_WIDTH):
					for y_pos in range(chunk.CHUNK_HEIGHT):
						for z_pos in range(chunk.CHUNK_LENGTH):
							blocks[x_pos][y_pos][z_pos] = data[idx]
							idx += 1
				return blocks
			except Exception:
				pass

		return self.generate_chunk(x, z, blocks_only=True)

	def _build_chunk_blocks(self, x, z):
		return build_chunk_blocks_process(
			x, z, self.scale, self.octaves, self.persistence, self.lacunarity,
			self.cave_scale, self.cave_threshold, SAVE_DIR)

	def _load_chunk_from_file(self, chunk_position, save_path):
		"""Load chunk block data from a gzip-compressed binary file."""
		current_chunk = chunk.Chunk(self, chunk_position)
		try:
			with gzip.open(save_path, 'rb') as f:
				data = f.read()
			idx = 0
			for x_pos in range(chunk.CHUNK_WIDTH):
				for y_pos in range(chunk.CHUNK_HEIGHT):
					for z_pos in range(chunk.CHUNK_LENGTH):
						current_chunk.blocks[x_pos][y_pos][z_pos] = data[idx]
						idx += 1
			return current_chunk
		except Exception:
			# If load fails, regenerate
			return self.generate_chunk(chunk_position[0], chunk_position[2])

	def _save_chunk_to_file(self, chunk_position):
		"""Save chunk block data asynchronously without blocking main thread."""
		if chunk_position not in self.chunks:
			return
		
		current_chunk = self.chunks[chunk_position]
		cx, _, cz = chunk_position
		save_path = os.path.join(SAVE_DIR, f"{cx}_{cz}.chunk")
		
		data = bytearray(chunk.CHUNK_WIDTH * chunk.CHUNK_HEIGHT * chunk.CHUNK_LENGTH)
		idx = 0
		for x_pos in range(chunk.CHUNK_WIDTH):
			for y_pos in range(chunk.CHUNK_HEIGHT):
				for z_pos in range(chunk.CHUNK_LENGTH):
					data[idx] = current_chunk.blocks[x_pos][y_pos][z_pos]
					idx += 1

		def async_write(path, content):
			try:
				with gzip.open(path, 'wb', compresslevel=1) as f:
					f.write(content)
			except Exception as e:
				print(f"Async chunk save failed: {e}")

		self._save_executor.submit(async_write, save_path, data)

	def _collect_generated_chunks(self, player_cx, player_cz):
		"""Materialize at most 1 completed generation per frame.
		
		This prevents main-thread allocation spikes."""
		for chunk_position in list(self.chunk_generation_futures.keys()):
			future = self.chunk_generation_futures[chunk_position]
			if not future.done():
				continue

			del self.chunk_generation_futures[chunk_position]

			try:
				blocks = future.result()
			except Exception as error:
				print(f"Chunk generation failed for {chunk_position}: {error}")
				return

			# Don't materialize if player has moved too far away
			if max(abs(chunk_position[0] - player_cx), abs(chunk_position[2] - player_cz)) > self.unload_distance:
				return

			current_chunk = chunk.Chunk(self, chunk_position, blocks=blocks)
			self.chunks[chunk_position] = current_chunk
			self.add_chunk_to_load_queue(chunk_position)
			return  # 1 per frame max for constant O(1) main-thread time

	def _rebuild_load_queue(self, player_cx, player_cz):
		"""Rebuild complete load queue for render distance, sorted by proximity to player.
		Guarantees 100% complete chunk coverage around player with zero missing holes."""
		queue = []
		for dist in range(self.render_distance + 1):
			for cx in range(player_cx - dist, player_cx + dist + 1):
				for cz in range(player_cz - dist, player_cz + dist + 1):
					if max(abs(cx - player_cx), abs(cz - player_cz)) != dist:
						continue
					chunk_pos = (cx, 0, cz)
					if (chunk_pos not in self.chunks and
						chunk_pos not in self.chunk_generation_futures and
						chunk_pos not in self.chunk_load_queue and
						chunk_pos not in queue):
						queue.append(chunk_pos)

		queue.sort(key=lambda pos: (pos[0] - player_cx)**2 + (pos[2] - player_cz)**2)
		self._load_queue = queue

	def _submit_generations(self):
		"""Submit generation jobs from the pre-computed queue.
		ProcessPoolExecutor runs the job in a disjoint OS process."""
		while (self._load_queue and
			   len(self.chunk_generation_futures) < 2):
			chunk_pos = self._load_queue.pop(0)
			if (chunk_pos in self.chunks or
				chunk_pos in self.chunk_generation_futures or
				chunk_pos in self.chunk_load_queue):
				continue  # already handled, skip to next
			self.chunk_generation_futures[chunk_pos] = (
				self.chunk_generation_executor.submit(
					build_chunk_blocks_process,
					chunk_pos[0], chunk_pos[2],
					self.scale, self.octaves, self.persistence, self.lacunarity,
					self.cave_scale, self.cave_threshold, SAVE_DIR))
			return  # one submission per frame

	def update_chunks(self, player_position):
		"""Drip-feed chunk pipeline.
		
		Per-frame work is O(1) — no scanning. Smoothly handles chunk
		transitions without frame drops."""
		player_cx = math.floor(player_position[0] / chunk.CHUNK_WIDTH)
		player_cz = math.floor(player_position[2] / chunk.CHUNK_LENGTH)

		# 1. Materialize at most 1 completed background generation
		self._collect_generated_chunks(player_cx, player_cz)

		# 2. Submit at most 1 background generation job
		self._submit_generations()

		# 3. Handle chunk boundary crossing & load queue replenishment
		current_chunk_pos = (player_cx, player_cz)
		if current_chunk_pos != self._last_player_chunk or not self._load_queue:
			self._last_player_chunk = current_chunk_pos
			self._rebuild_load_queue(player_cx, player_cz)

		# 4. Unload at most 1 distant chunk per frame without temporary list allocations
		for chunk_pos in self.chunks:
			dx = abs(chunk_pos[0] - player_cx)
			dz = abs(chunk_pos[2] - player_cz)
			if max(dx, dz) > self.unload_distance:
				self.unload_chunk(chunk_pos)
				break  # 1 per frame max for O(1) constant time

	def unload_chunk(self, chunk_position):
		"""Unload a chunk, saving it to disk if it was modified."""
		if chunk_position in self.active_loading_chunks:
			return  # don't unload while mesh is being built
		
		# Save if dirty (player modified it)
		if chunk_position in self.dirty_chunks:
			self._save_chunk_to_file(chunk_position)
			self.dirty_chunks.discard(chunk_position)
		
		# Remove from load queue if pending
		if chunk_position in self.chunk_load_queue:
			del self.chunk_load_queue[chunk_position]
		
		# Delete GPU resources and remove from memory
		if chunk_position in self.chunks:
			self.chunks[chunk_position].delete()
			del self.chunks[chunk_position]

	def get_nearby_blocks(self, position):
    # Return a list of block positions near the player's position.
    # This is a placeholder implementation. You'll need to adapt this to your world's data structure.
		x, y, z = map(int, position)
		nearby_blocks = []
		for dx in range(-1, 2):
			for dy in range(-1, 2):
				for dz in range(-1, 2):
					block_pos = (x + dx, y + dy, z + dz)
					if self.get_block_number(block_pos):  # Check if there's a block at this position
						nearby_blocks.append(block_pos)
		return nearby_blocks


	def draw(self, player_position=None):
		# Pass 1: Opaque pass
		gl.glDisable(gl.GL_BLEND)
		gl.glDepthMask(gl.GL_TRUE)
		for current_chunk in self.chunks.values():
			current_chunk.draw_opaque()

		# Pass 2: Translucent pass (water)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
		gl.glDepthMask(gl.GL_FALSE)
		for current_chunk in self.chunks.values():
			current_chunk.draw_translucent()

		gl.glDepthMask(gl.GL_TRUE)
		gl.glDisable(gl.GL_BLEND)
