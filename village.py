import math
import random
import hashlib
from noise import pnoise2, pnoise3

# -------------------------------------------------------------------
# Block ID Constants
# -------------------------------------------------------------------
BLOCK_AIR = 0
BLOCK_COBBLESTONE = 1
BLOCK_GRASS = 2
BLOCK_DIRT = 4
BLOCK_STONE = 5
BLOCK_SAND = 6
BLOCK_PLANKS = 7
BLOCK_LOG = 8
BLOCK_WATER = 9
BLOCK_LAVA = 15
BLOCK_GLASS = 21
BLOCK_BOOKSHELF = 23
BLOCK_OBSIDIAN = 24
BLOCK_CRAFTING_TABLE = 26
BLOCK_FURNACE = 27
BLOCK_CHEST = 37
BLOCK_OAK_SLAB = 38
BLOCK_COBBLE_SLAB = 39
BLOCK_OAK_STAIRS = 41
BLOCK_COBBLE_STAIRS = 42
BLOCK_OAK_DOOR = 43
BLOCK_OAK_FENCE = 51
BLOCK_COBBLE_WALL = 52
BLOCK_GLASS_PANE = 53
BLOCK_OAK_DOOR_TOP = 65
BLOCK_OAK_FENCE_GATE = 75
BLOCK_GRAVEL = 77
BLOCK_TORCH = 79
BLOCK_FARMLAND = 80
BLOCK_CROPS = 81
BLOCK_MOSSY_COBBLE = 82

# Item IDs for Loot Tables
ITEM_STICK = 100
ITEM_WOOD_PICKAXE = 101
ITEM_STONE_PICKAXE = 102
ITEM_IRON_PICKAXE = 103
ITEM_DIAMOND_PICKAXE = 104
ITEM_WOOD_AXE = 105
ITEM_STONE_AXE = 106
ITEM_IRON_AXE = 107
ITEM_WOOD_SHOVEL = 109
ITEM_STONE_SHOVEL = 110
ITEM_IRON_SHOVEL = 111
ITEM_WOOD_SWORD = 113
ITEM_STONE_SWORD = 114
ITEM_IRON_SWORD = 115
ITEM_GOLD_SWORD = 120
ITEM_COAL = 121
ITEM_DIAMOND = 122
ITEM_IRON_INGOT = 123
ITEM_GOLD_INGOT = 124
ITEM_RAW_PORKCHOP = 125
ITEM_LEATHER = 126
ITEM_RAW_BEEF = 127
ITEM_COOKED_PORKCHOP = 128
ITEM_STEAK = 129
ITEM_LEATHER_HELMET = 130
ITEM_LEATHER_CHESTPLATE = 131
ITEM_LEATHER_LEGGINGS = 132
ITEM_LEATHER_BOOTS = 133
ITEM_IRON_HELMET = 138
ITEM_IRON_CHESTPLATE = 139
ITEM_IRON_LEGGINGS = 140
ITEM_IRON_BOOTS = 141
ITEM_FLINT = 146
ITEM_BUCKET = 147
ITEM_BREAD = 152
ITEM_APPLE = 153
ITEM_WHEAT = 154
ITEM_SEEDS = 155
ITEM_OAK_SAPLING = 156
ITEM_BOW = 157
ITEM_ARROW = 158
ITEM_STRING = 159
ITEM_FEATHER = 160
ITEM_GOLDEN_APPLE = 161
ITEM_OBSIDIAN = 24

REGION_SIZE_CHUNKS = 18  # 18 chunks = 288 blocks per village region

# -------------------------------------------------------------------
# Continuous Surface Height Evaluation (Synchronized with World Seed)
# -------------------------------------------------------------------
def get_terrain_surface_y(wx, wz, seed=0):
	"""Exact mathematical surface height matching world generation."""
	seed_offset_x = float((seed * 10007) % 50000)
	seed_offset_z = float((seed * 16007) % 50000)

	sx = wx + seed_offset_x
	sz = wz + seed_offset_z

	cont = pnoise2(sx / 350.0, sz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)
	peaks_raw = pnoise2((sx + 1000.0) / 85.0, (sz + 1000.0) / 85.0, octaves=4, persistence=0.5, lacunarity=2.0)
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

	river_raw = abs(pnoise2((sx + 2000.0) / 240.0, (sz + 2000.0) / 240.0, octaves=3))
	if river_raw < 0.055:
		t_r = 1.0 - (river_raw / 0.055)
		r_blend = (t_r * t_r) * 3.5
		target_y = min(target_y, 60.0 - r_blend)

	sculpt = pnoise3(sx / 25.0, target_y / 15.0, sz / 25.0) * 2.0
	final_y = math.floor(target_y + sculpt)
	return max(4, min(final_y, 250))


def is_dry_plains(wx, wz, seed=0):
	"""Checks if coordinate is on dry land above sea level (63+) and strictly outside ocean/river."""
	seed_offset_x = float((seed * 10007) % 50000)
	seed_offset_z = float((seed * 16007) % 50000)

	sx = wx + seed_offset_x
	sz = wz + seed_offset_z

	cont = pnoise2(sx / 350.0, sz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)
	river_raw = abs(pnoise2((sx + 2000.0) / 240.0, (sz + 2000.0) / 240.0, octaves=3))
	sy = get_terrain_surface_y(wx, wz, seed)

	return (sy >= 63) and (cont >= 0.12) and (river_raw >= 0.06)


def is_in_village(wx, wz, seed=0):
	"""Returns True if world coordinate (wx, wz) is within a village perimeter."""
	rx_min = (wx // 16 - 3) // REGION_SIZE_CHUNKS
	rx_max = (wx // 16 + 3) // REGION_SIZE_CHUNKS
	rz_min = (wz // 16 - 3) // REGION_SIZE_CHUNKS
	rz_max = (wz // 16 + 3) // REGION_SIZE_CHUNKS

	for rx in range(rx_min, rx_max + 1):
		for rz in range(rz_min, rz_max + 1):
			plan = get_village_for_region(seed, rx, rz)
			if plan:
				dist_sq = (wx - plan.center_x) ** 2 + (wz - plan.center_z) ** 2
				if dist_sq <= 50 * 50:
					return True
	return False


# -------------------------------------------------------------------
# Random Loot Tables
# -------------------------------------------------------------------
def _fill_chest_slots(slots, possible_loot, rng, min_items=3, max_items=7):
	item_count = rng.randint(min_items, max_items)
	used_slots = set()
	for _ in range(item_count):
		roll = rng.randint(1, 100)
		candidates = [item for item in possible_loot if item[3] >= roll]
		if not candidates:
			candidates = possible_loot
		chosen = rng.choice(candidates)
		item_id = chosen[0]
		cnt = rng.randint(chosen[1], chosen[2])

		slot_idx = rng.randint(0, 26)
		while slot_idx in used_slots and len(used_slots) < 27:
			slot_idx = rng.randint(0, 26)
		used_slots.add(slot_idx)
		slots[slot_idx] = [item_id, cnt]


def generate_blacksmith_loot(rng):
	slots = [[0, 0] for _ in range(27)]
	possible_loot = [
		(ITEM_IRON_INGOT, 1, 5, 55),
		(ITEM_GOLD_INGOT, 1, 3, 25),
		(ITEM_DIAMOND, 1, 2, 10),
		(ITEM_BREAD, 2, 5, 65),
		(ITEM_APPLE, 1, 3, 50),
		(ITEM_GOLDEN_APPLE, 1, 2, 15),
		(ITEM_IRON_SWORD, 1, 1, 20),
		(ITEM_IRON_PICKAXE, 1, 1, 20),
		(ITEM_BOW, 1, 1, 25),
		(ITEM_ARROW, 4, 16, 45),
		(ITEM_IRON_HELMET, 1, 1, 15),
		(ITEM_IRON_CHESTPLATE, 1, 1, 10),
		(ITEM_IRON_LEGGINGS, 1, 1, 12),
		(ITEM_IRON_BOOTS, 1, 1, 15),
		(ITEM_OBSIDIAN, 2, 5, 25),
		(ITEM_OAK_SAPLING, 2, 6, 40),
	]
	_fill_chest_slots(slots, possible_loot, rng, 4, 8)
	return slots


def generate_cottage_loot(rng):
	slots = [[0, 0] for _ in range(27)]
	possible_loot = [
		(ITEM_BREAD, 2, 5, 70),
		(ITEM_APPLE, 1, 4, 55),
		(ITEM_WHEAT, 2, 6, 60),
		(ITEM_SEEDS, 2, 5, 50),
		(ITEM_RAW_PORKCHOP, 1, 3, 40),
		(ITEM_RAW_BEEF, 1, 3, 40),
		(ITEM_STICK, 2, 6, 65),
		(ITEM_STRING, 2, 5, 40),
		(ITEM_FEATHER, 2, 6, 40),
		(ITEM_ARROW, 2, 8, 35),
		(ITEM_COAL, 1, 4, 45),
		(ITEM_LEATHER, 1, 3, 35),
		(BLOCK_TORCH, 2, 6, 50),
		(ITEM_WOOD_PICKAXE, 1, 1, 25),
		(ITEM_STONE_PICKAXE, 1, 1, 20),
		(ITEM_WOOD_SWORD, 1, 1, 20),
		(ITEM_STONE_SWORD, 1, 1, 15),
		(ITEM_IRON_INGOT, 1, 2, 15),
		(ITEM_OAK_SAPLING, 1, 3, 35),
	]
	_fill_chest_slots(slots, possible_loot, rng, 3, 6)
	return slots


def generate_butcher_loot(rng):
	slots = [[0, 0] for _ in range(27)]
	possible_loot = [
		(ITEM_RAW_BEEF, 2, 5, 75),
		(ITEM_RAW_PORKCHOP, 2, 5, 75),
		(ITEM_STEAK, 1, 3, 45),
		(ITEM_COOKED_PORKCHOP, 1, 3, 45),
		(ITEM_LEATHER, 2, 5, 60),
		(ITEM_COAL, 2, 6, 60),
		(ITEM_STONE_AXE, 1, 1, 30),
		(ITEM_FLINT, 1, 3, 40),
		(ITEM_BREAD, 1, 3, 50),
		(ITEM_LEATHER_HELMET, 1, 1, 20),
		(ITEM_LEATHER_CHESTPLATE, 1, 1, 15),
		(ITEM_LEATHER_BOOTS, 1, 1, 20),
	]
	_fill_chest_slots(slots, possible_loot, rng, 4, 7)
	return slots


def generate_library_loot(rng):
	slots = [[0, 0] for _ in range(27)]
	possible_loot = [
		(BLOCK_BOOKSHELF, 1, 2, 50),
		(ITEM_BREAD, 2, 4, 60),
		(ITEM_APPLE, 2, 4, 55),
		(ITEM_STICK, 3, 7, 60),
		(BLOCK_TORCH, 2, 6, 60),
		(ITEM_LEATHER, 2, 4, 50),
		(ITEM_IRON_INGOT, 1, 3, 35),
		(ITEM_GOLD_INGOT, 1, 2, 20),
		(ITEM_DIAMOND, 1, 1, 8),
		(ITEM_WHEAT, 2, 5, 40),
	]
	_fill_chest_slots(slots, possible_loot, rng, 3, 6)
	return slots


def generate_farm_loot(rng):
	slots = [[0, 0] for _ in range(27)]
	possible_loot = [
		(ITEM_BREAD, 2, 6, 75),
		(ITEM_WHEAT, 4, 10, 80),
		(ITEM_SEEDS, 3, 8, 75),
		(ITEM_APPLE, 2, 4, 50),
		(ITEM_OAK_SAPLING, 2, 5, 45),
		(ITEM_STICK, 2, 6, 50),
		(ITEM_WOOD_SHOVEL, 1, 1, 25),
		(ITEM_STONE_SHOVEL, 1, 1, 20),
	]
	_fill_chest_slots(slots, possible_loot, rng, 3, 6)
	return slots


# -------------------------------------------------------------------
# Structure Blueprints & Builders (With Priority Air Clearance)
# -------------------------------------------------------------------
class VillageStructure:
	def __init__(self, stype, world_pos, rotation=0):
		self.stype = stype
		self.world_pos = tuple(world_pos)
		self.rotation = rotation  # 0, 90, 180, 270
		self.blocks = {}   # (wx, wy, wz): block_id
		self.air_blocks = set() # (wx, wy, wz)
		self.chests = {}   # (wx, wy, wz): [27 slots]

	def set_local_block(self, lx, ly, lz, block_id, width, length):
		"""Transforms local structure coords with rotation to world coords."""
		if self.rotation == 0:
			rx, rz = lx, lz
		elif self.rotation == 90:
			rx, rz = length - 1 - lz, lx
		elif self.rotation == 180:
			rx, rz = width - 1 - lx, length - 1 - lz
		else:  # 270
			rx, rz = lz, width - 1 - lx

		wx = self.world_pos[0] + rx
		wy = self.world_pos[1] + ly
		wz = self.world_pos[2] + rz

		if block_id == BLOCK_AIR:
			self.air_blocks.add((wx, wy, wz))
			if (wx, wy, wz) in self.blocks:
				del self.blocks[(wx, wy, wz)]
		else:
			self.blocks[(wx, wy, wz)] = block_id
			if (wx, wy, wz) in self.air_blocks:
				self.air_blocks.remove((wx, wy, wz))

	def set_local_chest(self, lx, ly, lz, slots, width, length):
		if self.rotation == 0: rx, rz = lx, lz
		elif self.rotation == 90: rx, rz = length - 1 - lz, lx
		elif self.rotation == 180: rx, rz = width - 1 - lx, length - 1 - lz
		else: rx, rz = lz, width - 1 - lx
		wx = self.world_pos[0] + rx
		wy = self.world_pos[1] + ly
		wz = self.world_pos[2] + rz
		self.blocks[(wx, wy, wz)] = BLOCK_CHEST
		self.chests[(wx, wy, wz)] = slots


def build_well(center_x, center_z, base_y):
	"""Builds the central 6x6 Town Well with deep water basin and roof."""
	struct = VillageStructure("WELL", (center_x - 3, base_y, center_z - 3), rotation=0)
	w, l = 6, 6

	# 1. Clear complete air volume above well (up to y + 9)
	for x in range(w):
		for z in range(l):
			for y in range(1, 10):
				struct.set_local_block(x, y, z, BLOCK_AIR, w, l)

	# 2. Downward foundation and water shaft
	for x in range(w):
		for z in range(l):
			for fy in range(base_y - 8, base_y):
				if x in (0, 5) or z in (0, 5) or x in (1, 4) or z in (1, 4):
					struct.set_local_block(x, fy - base_y, z, BLOCK_COBBLESTONE, w, l)

			if x in (0, 5) or z in (0, 5):
				struct.set_local_block(x, 0, z, BLOCK_COBBLESTONE, w, l)
			elif x in (1, 4) or z in (1, 4):
				struct.set_local_block(x, 0, z, BLOCK_COBBLESTONE, w, l)
			else:
				struct.set_local_block(x, 0, z, BLOCK_WATER, w, l)
				struct.set_local_block(x, -1, z, BLOCK_WATER, w, l)
				struct.set_local_block(x, -2, z, BLOCK_WATER, w, l)
				struct.set_local_block(x, -3, z, BLOCK_WATER, w, l)
				struct.set_local_block(x, -4, z, BLOCK_COBBLESTONE, w, l)

	# 3. Fence Pillars & Roof
	corner_fences = [(1, 1), (4, 1), (1, 4), (4, 4)]
	for fx, fz in corner_fences:
		struct.set_local_block(fx, 1, fz, BLOCK_OAK_FENCE, w, l)
		struct.set_local_block(fx, 2, fz, BLOCK_OAK_FENCE, w, l)

	for rx in range(1, 5):
		for rz in range(1, 5):
			struct.set_local_block(rx, 3, rz, BLOCK_COBBLESTONE, w, l)
	struct.set_local_block(2, 4, 2, BLOCK_COBBLE_SLAB, w, l)
	struct.set_local_block(3, 4, 2, BLOCK_COBBLE_SLAB, w, l)
	struct.set_local_block(2, 4, 3, BLOCK_COBBLE_SLAB, w, l)
	struct.set_local_block(3, 4, 3, BLOCK_COBBLE_SLAB, w, l)

	return struct


def build_cottage(origin_x, origin_z, base_y, rotation, seed, rng):
	"""Builds a classic 5x5 Village Cottage / Small House with Loot Chest."""
	struct = VillageStructure("COTTAGE", (origin_x, base_y, origin_z), rotation)
	w, l, h = 5, 5, 5

	# 1. Clear full air volume including roof headroom and entrance path
	for x in range(w):
		for z in range(l):
			for y in range(1, 8):
				struct.set_local_block(x, y, z, BLOCK_AIR, w, l)
	for ez in (-1, -2):
		for ey in (1, 2, 3):
			struct.set_local_block(2, ey, ez, BLOCK_AIR, w, l)

	# 2. Foundation & Floor
	for x in range(w):
		for z in range(l):
			ground_y = get_terrain_surface_y(origin_x + x, origin_z + z, seed)
			for fy in range(min(ground_y, base_y - 1), base_y):
				struct.set_local_block(x, fy - base_y, z, BLOCK_COBBLESTONE, w, l)
			struct.set_local_block(x, 0, z, BLOCK_COBBLESTONE, w, l)

	# 3. Walls
	for y in range(1, 4):
		for x in range(w):
			for z in range(l):
				is_corner = (x in (0, w - 1)) and (z in (0, l - 1))
				is_wall = (x in (0, w - 1)) or (z in (0, l - 1))
				if is_corner:
					struct.set_local_block(x, y, z, BLOCK_LOG, w, l)
				elif is_wall:
					struct.set_local_block(x, y, z, BLOCK_PLANKS, w, l)

	# 4. Windows & Door
	struct.set_local_block(0, 2, 2, BLOCK_GLASS_PANE, w, l)
	struct.set_local_block(4, 2, 2, BLOCK_GLASS_PANE, w, l)
	struct.set_local_block(2, 2, 4, BLOCK_GLASS_PANE, w, l)
	struct.set_local_block(2, 1, 0, BLOCK_OAK_DOOR, w, l)
	struct.set_local_block(2, 2, 0, BLOCK_OAK_DOOR_TOP, w, l)

	# 5. Roof
	for x in range(w):
		for z in range(l):
			struct.set_local_block(x, 4, z, BLOCK_PLANKS, w, l)
	for x in range(1, w - 1):
		struct.set_local_block(x, 5, 2, BLOCK_OAK_SLAB, w, l)

	# 6. Furniture & Cottage Loot Chest
	struct.set_local_block(1, 1, 3, BLOCK_CRAFTING_TABLE, w, l)
	struct.set_local_block(3, 1, 3, BLOCK_BOOKSHELF, w, l)
	struct.set_local_block(2, 3, 3, BLOCK_TORCH, w, l)
	struct.set_local_chest(3, 1, 1, generate_cottage_loot(rng), w, l)

	return struct


def build_blacksmith(origin_x, origin_z, base_y, rotation, seed, rng):
	"""Builds a Blacksmith / Armory with Lava Pool, Double Furnaces & Armory Loot Chest."""
	struct = VillageStructure("BLACKSMITH", (origin_x, base_y, origin_z), rotation)
	w, l, h = 7, 8, 5

	# 1. Clear full air volume including porch and roof clearance
	for x in range(w):
		for z in range(l):
			for y in range(1, 8):
				struct.set_local_block(x, y, z, BLOCK_AIR, w, l)
	for ez in (-1, -2):
		for ey in (1, 2, 3):
			struct.set_local_block(3, ey, ez, BLOCK_AIR, w, l)

	# 2. Foundation & Floor
	for x in range(w):
		for z in range(l):
			ground_y = get_terrain_surface_y(origin_x + x, origin_z + z, seed)
			for fy in range(min(ground_y, base_y - 1), base_y):
				struct.set_local_block(x, fy - base_y, z, BLOCK_COBBLESTONE, w, l)
			struct.set_local_block(x, 0, z, BLOCK_COBBLESTONE, w, l)

	# 3. Workshop Walls
	for y in range(1, 4):
		for x in range(w):
			for z in range(3, l):
				is_corner = (x in (0, w - 1)) and (z in (3, l - 1))
				is_wall = (x in (0, w - 1)) or (z in (3, l - 1))
				if is_corner:
					struct.set_local_block(x, y, z, BLOCK_LOG, w, l)
				elif is_wall:
					struct.set_local_block(x, y, z, BLOCK_COBBLESTONE if y == 1 else BLOCK_PLANKS, w, l)

	# 4. Porch Pillars
	struct.set_local_block(0, 1, 0, BLOCK_OAK_FENCE, w, l)
	struct.set_local_block(0, 2, 0, BLOCK_OAK_FENCE, w, l)
	struct.set_local_block(6, 1, 0, BLOCK_OAK_FENCE, w, l)
	struct.set_local_block(6, 2, 0, BLOCK_OAK_FENCE, w, l)

	# 5. Lava Tank
	struct.set_local_block(1, 1, 1, BLOCK_COBBLESTONE, w, l)
	struct.set_local_block(2, 1, 1, BLOCK_COBBLESTONE, w, l)
	struct.set_local_block(1, 1, 2, BLOCK_COBBLESTONE, w, l)
	struct.set_local_block(2, 1, 2, BLOCK_LAVA, w, l)
	struct.set_local_block(1, 2, 1, BLOCK_COBBLE_WALL, w, l)
	struct.set_local_block(2, 2, 1, BLOCK_COBBLE_WALL, w, l)

	# 6. Furnaces & Blacksmith Loot Chest
	struct.set_local_block(3, 1, 4, BLOCK_FURNACE, w, l)
	struct.set_local_block(4, 1, 4, BLOCK_FURNACE, w, l)
	struct.set_local_block(1, 1, 6, BLOCK_CRAFTING_TABLE, w, l)
	chest_loot = generate_blacksmith_loot(rng)
	struct.set_local_chest(5, 1, 6, chest_loot, w, l)

	# 7. Door Opening & Windows
	struct.set_local_block(3, 1, 3, BLOCK_AIR, w, l)
	struct.set_local_block(3, 2, 3, BLOCK_AIR, w, l)
	struct.set_local_block(0, 2, 5, BLOCK_GLASS_PANE, w, l)
	struct.set_local_block(6, 2, 5, BLOCK_GLASS_PANE, w, l)

	# 8. Roof
	for x in range(w):
		for z in range(l):
			struct.set_local_block(x, 4, z, BLOCK_COBBLE_SLAB, w, l)

	return struct


def build_library(origin_x, origin_z, base_y, rotation, seed, rng):
	"""Builds a large Village Library / Hall with Bookshelves & Library Loot Chest."""
	struct = VillageStructure("LIBRARY", (origin_x, base_y, origin_z), rotation)
	w, l, h = 6, 7, 6

	# 1. Clear full air volume including roof headroom and entrance path
	for x in range(w):
		for z in range(l):
			for y in range(1, 9):
				struct.set_local_block(x, y, z, BLOCK_AIR, w, l)
	for ez in (-1, -2):
		for ey in (1, 2, 3):
			struct.set_local_block(2, ey, ez, BLOCK_AIR, w, l)
			struct.set_local_block(3, ey, ez, BLOCK_AIR, w, l)

	# 2. Foundation & Floor
	for x in range(w):
		for z in range(l):
			ground_y = get_terrain_surface_y(origin_x + x, origin_z + z, seed)
			for fy in range(min(ground_y, base_y - 1), base_y):
				struct.set_local_block(x, fy - base_y, z, BLOCK_COBBLESTONE, w, l)
			struct.set_local_block(x, 0, z, BLOCK_PLANKS, w, l)

	# 3. Walls
	for y in range(1, 4):
		for x in range(w):
			for z in range(l):
				is_corner = (x in (0, w - 1)) and (z in (0, l - 1))
				is_wall = (x in (0, w - 1)) or (z in (0, l - 1))
				if is_corner:
					struct.set_local_block(x, y, z, BLOCK_LOG, w, l)
				elif is_wall:
					struct.set_local_block(x, y, z, BLOCK_PLANKS, w, l)

	# 4. Windows & Doors
	struct.set_local_block(0, 2, 3, BLOCK_GLASS_PANE, w, l)
	struct.set_local_block(5, 2, 3, BLOCK_GLASS_PANE, w, l)
	struct.set_local_block(2, 1, 0, BLOCK_OAK_DOOR, w, l)
	struct.set_local_block(2, 2, 0, BLOCK_OAK_DOOR_TOP, w, l)
	struct.set_local_block(3, 1, 0, BLOCK_OAK_DOOR, w, l)
	struct.set_local_block(3, 2, 0, BLOCK_OAK_DOOR_TOP, w, l)

	# 5. Bookshelves & Library Loot Chest
	for bx in (1, 2, 3, 4):
		struct.set_local_block(bx, 1, 5, BLOCK_BOOKSHELF, w, l)
		struct.set_local_block(bx, 2, 5, BLOCK_BOOKSHELF, w, l)
	struct.set_local_block(1, 1, 3, BLOCK_CRAFTING_TABLE, w, l)
	struct.set_local_block(4, 1, 3, BLOCK_BOOKSHELF, w, l)
	struct.set_local_block(2, 3, 3, BLOCK_TORCH, w, l)
	struct.set_local_chest(4, 1, 1, generate_library_loot(rng), w, l)

	# 6. High Roof
	for x in range(w):
		for z in range(l):
			struct.set_local_block(x, 4, z, BLOCK_PLANKS, w, l)
	for x in range(1, w - 1):
		for z in range(1, l - 1):
			struct.set_local_block(x, 5, z, BLOCK_OAK_SLAB, w, l)

	return struct


def build_crop_farm(origin_x, origin_z, base_y, rotation, seed, rng):
	"""Builds a standard Village Crop Farm with water canal, crops, and storage chest."""
	struct = VillageStructure("FARM", (origin_x, base_y, origin_z), rotation)
	w, l = 7, 9

	# 1. Clear complete air volume above farm (up to y + 8)
	for x in range(w):
		for z in range(l):
			for y in range(1, 9):
				struct.set_local_block(x, y, z, BLOCK_AIR, w, l)

	# 2. Downward foundation & farm blocks
	for x in range(w):
		for z in range(l):
			ground_y = get_terrain_surface_y(origin_x + x, origin_z + z, seed)
			for fy in range(min(ground_y, base_y - 1), base_y):
				struct.set_local_block(x, fy - base_y, z, BLOCK_DIRT, w, l)

			is_border = (x in (0, w - 1)) or (z in (0, l - 1))
			is_water_canal = (x == 3) and not is_border

			if is_border:
				struct.set_local_block(x, 0, z, BLOCK_LOG, w, l)
			elif is_water_canal:
				struct.set_local_block(x, 0, z, BLOCK_WATER, w, l)
				struct.set_local_block(x, -1, z, BLOCK_DIRT, w, l)
			else:
				struct.set_local_block(x, 0, z, BLOCK_FARMLAND, w, l)
				struct.set_local_block(x, 1, z, BLOCK_CROPS, w, l)

	# 3. Farm shed storage chest
	struct.set_local_chest(1, 1, 0, generate_farm_loot(rng), w, l)

	return struct


def build_butcher_shop(origin_x, origin_z, base_y, rotation, seed, rng):
	"""Builds a Butcher / Cook Shop with Furnaces, back counter, and Butcher Loot Chest."""
	struct = VillageStructure("BUTCHER", (origin_x, base_y, origin_z), rotation)
	w, l, h = 5, 6, 5

	# 1. Clear full air volume including roof headroom and entrance path
	for x in range(w):
		for z in range(l):
			for y in range(1, 8):
				struct.set_local_block(x, y, z, BLOCK_AIR, w, l)
	for ez in (-1, -2):
		for ey in (1, 2, 3):
			struct.set_local_block(2, ey, ez, BLOCK_AIR, w, l)

	# 2. Foundation & Floor
	for x in range(w):
		for z in range(l):
			ground_y = get_terrain_surface_y(origin_x + x, origin_z + z, seed)
			for fy in range(min(ground_y, base_y - 1), base_y):
				struct.set_local_block(x, fy - base_y, z, BLOCK_COBBLESTONE, w, l)
			struct.set_local_block(x, 0, z, BLOCK_COBBLESTONE, w, l)

	# 3. Walls
	for y in range(1, 4):
		for x in range(w):
			for z in range(l):
				is_corner = (x in (0, w - 1)) and (z in (0, l - 1))
				is_wall = (x in (0, w - 1)) or (z in (0, l - 1))
				if is_corner:
					struct.set_local_block(x, y, z, BLOCK_LOG, w, l)
				elif is_wall:
					struct.set_local_block(x, y, z, BLOCK_PLANKS, w, l)

	# 4. Doors & Counters
	struct.set_local_block(2, 1, 0, BLOCK_OAK_DOOR, w, l)
	struct.set_local_block(2, 2, 0, BLOCK_OAK_DOOR_TOP, w, l)
	struct.set_local_block(1, 1, 4, BLOCK_FURNACE, w, l)
	struct.set_local_block(2, 1, 4, BLOCK_FURNACE, w, l)
	struct.set_local_block(3, 1, 4, BLOCK_CRAFTING_TABLE, w, l)

	# 5. Butcher Meat & Supply Loot Chest
	struct.set_local_chest(1, 1, 2, generate_butcher_loot(rng), w, l)

	# 6. Roof
	for x in range(w):
		for z in range(l):
			struct.set_local_block(x, 4, z, BLOCK_PLANKS, w, l)

	return struct


# -------------------------------------------------------------------
# Village Plan Planner
# -------------------------------------------------------------------
class VillagePlan:
	def __init__(self, world_seed, layout_seed, center_x, center_z, base_y):
		self.world_seed = world_seed
		self.layout_seed = layout_seed
		self.center_x = center_x
		self.center_z = center_z
		self.base_y = base_y
		self.structures = []
		self.roads = {}      # (wx, wy, wz): BLOCK_GRAVEL
		self.lamp_posts = {} # (wx, wy, wz): block_id
		self.all_blocks = {} # (wx, wy, wz): block_id
		self.air_blocks = set()
		self.chests = {}     # (wx, wy, wz): slots
		self.occupied_boxes = [] # (min_x, max_x, min_z, max_z)
		self._generate_layout()

	def _is_box_free(self, min_x, max_x, min_z, max_z, padding=2):
		for bx0, bx1, bz0, bz1 in self.occupied_boxes:
			if not (max_x + padding < bx0 or min_x - padding > bx1 or
					max_z + padding < bz0 or min_z - padding > bz1):
				return False
		return True

	def _generate_layout(self):
		rng = random.Random(self.layout_seed)

		# 1. Place Central Town Well (Always Present)
		well = build_well(self.center_x, self.center_z, self.base_y)
		self.structures.append(well)
		self.occupied_boxes.append((self.center_x - 4, self.center_x + 4, self.center_z - 4, self.center_z + 4))

		# 2. Road Network: 2 to 4 cardinal branches
		cardinal_dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
		num_branches = rng.randint(3, 4)
		selected_dirs = rng.sample(cardinal_dirs, num_branches)

		building_weights = [
			("COTTAGE", 30),
			("BLACKSMITH", 15),
			("LIBRARY", 20),
			("FARM", 20),
			("BUTCHER", 15),
		]

		for dx, dz in selected_dirs:
			branch_len = rng.randint(24, 36)
			# Generate 2-block wide gravel road with 4-block overhead air clearance
			for step in range(3, branch_len):
				if dx != 0:
					rx = self.center_x + dx * step
					for off_z in (0, 1):
						rz = self.center_z + off_z
						sy = get_terrain_surface_y(rx, rz, self.world_seed)
						self.roads[(rx, sy, rz)] = BLOCK_GRAVEL
						self.roads[(rx, sy - 1, rz)] = BLOCK_DIRT
						# Clear overhead walking clearance above road
						for cy in range(sy + 1, sy + 5):
							self.air_blocks.add((rx, cy, rz))
				else:
					rz = self.center_z + dz * step
					for off_x in (0, 1):
						rx = self.center_x + off_x
						sy = get_terrain_surface_y(rx, rz, self.world_seed)
						self.roads[(rx, sy, rz)] = BLOCK_GRAVEL
						self.roads[(rx, sy - 1, rz)] = BLOCK_DIRT
						# Clear overhead walking clearance above road
						for cy in range(sy + 1, sy + 5):
							self.air_blocks.add((rx, cy, rz))

				# Lamp Posts along road every ~10 blocks
				if step % 10 == 0:
					lamp_x = self.center_x + dx * step + (2 if dx == 0 else 0)
					lamp_z = self.center_z + dz * step + (2 if dz == 0 else 0)
					ly = get_terrain_surface_y(lamp_x, lamp_z, self.world_seed)
					self.lamp_posts[(lamp_x, ly + 1, lamp_z)] = BLOCK_COBBLE_WALL
					self.lamp_posts[(lamp_x, ly + 2, lamp_z)] = BLOCK_OAK_FENCE
					self.lamp_posts[(lamp_x, ly + 3, lamp_z)] = BLOCK_OAK_FENCE
					self.lamp_posts[(lamp_x, ly + 4, lamp_z)] = BLOCK_TORCH
					for cy in range(ly + 5, ly + 8):
						self.air_blocks.add((lamp_x, cy, lamp_z))

			# 3. Probabilistic Buildings along this road branch
			for step in (6, 12, 18, 24):
				if step + 4 >= branch_len:
					break

				for side in (-1, 1):
					if rng.random() > 0.85:
						continue

					roll = rng.randint(1, 100)
					btype = "COTTAGE"
					cum = 0
					for name, wt in building_weights:
						cum += wt
						if roll <= cum:
							btype = name
							break

					if btype == "COTTAGE": bw, bl = 5, 5
					elif btype == "BLACKSMITH": bw, bl = 7, 8
					elif btype == "LIBRARY": bw, bl = 6, 7
					elif btype == "FARM": bw, bl = 7, 9
					elif btype == "BUTCHER": bw, bl = 5, 6
					else: bw, bl = 6, 6

					if dx != 0:
						bx = self.center_x + dx * step - (bw // 2)
						bz = self.center_z + side * (3 + bl // 2)
						rot = 0 if side > 0 else 180
					else:
						bx = self.center_x + side * (3 + bw // 2)
						bz = self.center_z + dz * step - (bl // 2)
						rot = 90 if side > 0 else 270

					box = (bx, bx + bw, bz, bz + bl)
					if not self._is_box_free(bx, bx + bw, bz, bz + bl):
						continue

					b_center_y = get_terrain_surface_y(bx + bw // 2, bz + bl // 2, self.world_seed)
					if not is_dry_plains(bx + bw // 2, bz + bl // 2, self.world_seed):
						continue
					if abs(b_center_y - self.base_y) > 8:
						continue

					self.occupied_boxes.append(box)

					if btype == "COTTAGE":
						st = build_cottage(bx, bz, b_center_y, rot, self.world_seed, rng)
					elif btype == "BLACKSMITH":
						st = build_blacksmith(bx, bz, b_center_y, rot, self.world_seed, rng)
					elif btype == "LIBRARY":
						st = build_library(bx, bz, b_center_y, rot, self.world_seed, rng)
					elif btype == "FARM":
						st = build_crop_farm(bx, bz, b_center_y, rot, self.world_seed, rng)
					elif btype == "BUTCHER":
						st = build_butcher_shop(bx, bz, b_center_y, rot, self.world_seed, rng)
					else:
						st = build_cottage(bx, bz, b_center_y, rot, self.world_seed, rng)

					self.structures.append(st)

		# 4. Consolidate all blocks & chests
		for st in self.structures:
			self.all_blocks.update(st.blocks)
			self.air_blocks.update(st.air_blocks)
			self.chests.update(st.chests)

		self.all_blocks.update(self.roads)
		self.all_blocks.update(self.lamp_posts)

		# Ensure no structure block is in air_blocks
		for pos in self.all_blocks:
			if pos in self.air_blocks:
				self.air_blocks.remove(pos)


# -------------------------------------------------------------------
# Village Generator & Region Query Manager
# -------------------------------------------------------------------
_village_cache = {}

def get_village_for_region(seed, rx, rz):
	"""Returns VillagePlan if a valid dry-land village exists in region (rx, rz), else None."""
	cache_key = (seed, rx, rz)
	if cache_key in _village_cache:
		return _village_cache[cache_key]

	hash_str = f"{seed}:{rx}:{rz}:minecraft_village_v4"
	v_hash = int(hashlib.md5(hash_str.encode()).hexdigest()[:8], 16)

	center_chunk_x = rx * REGION_SIZE_CHUNKS + 4 + (v_hash % (REGION_SIZE_CHUNKS - 8))
	center_chunk_z = rz * REGION_SIZE_CHUNKS + 4 + ((v_hash >> 8) % (REGION_SIZE_CHUNKS - 8))
	center_x = center_chunk_x * 16 + 8
	center_z = center_chunk_z * 16 + 8

	# Check terrain suitability: Sample 9 points around candidate center
	samples = []
	for off_x in (-24, 0, 24):
		for off_z in (-24, 0, 24):
			sx = center_x + off_x
			sz = center_z + off_z
			if not is_dry_plains(sx, sz, seed):
				_village_cache[cache_key] = None
				return None
			samples.append(get_terrain_surface_y(sx, sz, seed))

	# Steepness check
	if max(samples) - min(samples) > 10:
		_village_cache[cache_key] = None
		return None

	base_y = get_terrain_surface_y(center_x, center_z, seed)
	plan = VillagePlan(seed, v_hash, center_x, center_z, base_y)
	_village_cache[cache_key] = plan
	return plan


def get_village_blocks_for_chunk(chunk_x, chunk_z, seed):
	"""Returns (block_dict, air_set, chest_dict) for chunk (chunk_x, chunk_z)."""
	rx_min = (chunk_x - 3) // REGION_SIZE_CHUNKS
	rx_max = (chunk_x + 3) // REGION_SIZE_CHUNKS
	rz_min = (chunk_z - 3) // REGION_SIZE_CHUNKS
	rz_max = (chunk_z + 3) // REGION_SIZE_CHUNKS

	min_wx = chunk_x * 16
	max_wx = min_wx + 15
	min_wz = chunk_z * 16
	max_wz = min_wz + 15

	chunk_blocks = {}
	chunk_air = set()
	chunk_chests = {}

	for rx in range(rx_min, rx_max + 1):
		for rz in range(rz_min, rz_max + 1):
			plan = get_village_for_region(seed, rx, rz)
			if plan is None:
				continue

			for (wx, wy, wz), b_id in plan.all_blocks.items():
				if min_wx <= wx <= max_wx and min_wz <= wz <= max_wz:
					lx = wx - min_wx
					lz = wz - min_wz
					chunk_blocks[(lx, wy, lz)] = b_id

			for (wx, wy, wz) in plan.air_blocks:
				if min_wx <= wx <= max_wx and min_wz <= wz <= max_wz:
					lx = wx - min_wx
					lz = wz - min_wz
					chunk_air.add((lx, wy, lz))

			for (wx, wy, wz), slots in plan.chests.items():
				if min_wx <= wx <= max_wx and min_wz <= wz <= max_wz:
					chunk_chests[(wx, wy, wz)] = slots

	return chunk_blocks, chunk_air, chunk_chests


def find_closest_villages_to_spawn(seed, count=3, max_region_radius=8):
	"""Finds and returns the closest N valid villages to spawn (0, 0)."""
	villages = []
	for rx in range(-max_region_radius, max_region_radius + 1):
		for rz in range(-max_region_radius, max_region_radius + 1):
			plan = get_village_for_region(seed, rx, rz)
			if plan:
				dist = math.sqrt(plan.center_x * plan.center_x + plan.center_z * plan.center_z)
				villages.append({
					"x": plan.center_x,
					"y": plan.base_y,
					"z": plan.center_z,
					"distance": dist,
					"buildings": len(plan.structures),
				})

	villages.sort(key=lambda v: v["distance"])
	return villages[:count]
