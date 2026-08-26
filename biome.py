"""
Biome Engine: Temperature & Moisture Noise Sampling, Continuous Biome Blending,
Procedural Multi-Biome Terrain Generation, and Tree / Flora Stamping.
"""
import math
import random
from noise import pnoise2, pnoise3

# -------------------------------------------------------------------
# Biome IDs & Display Names
# -------------------------------------------------------------------
BIOME_PLAINS = 0
BIOME_FOREST = 1
BIOME_BIRCH_FOREST = 2
BIOME_SPRUCE_TAIGA = 3
BIOME_JUNGLE = 4
BIOME_SAVANNA = 5
BIOME_DESERT = 6
BIOME_SNOW_FOREST = 7
BIOME_HILLS = 8
BIOME_MOUNTAINS = 9

BIOME_NAMES = {
	BIOME_PLAINS: "Plains",
	BIOME_FOREST: "Forest",
	BIOME_BIRCH_FOREST: "Birch Forest",
	BIOME_SPRUCE_TAIGA: "Spruce Taiga",
	BIOME_JUNGLE: "Jungle",
	BIOME_SAVANNA: "Savanna",
	BIOME_DESERT: "Desert",
	BIOME_SNOW_FOREST: "Snow Forest",
	BIOME_HILLS: "Windswept Hills",
	BIOME_MOUNTAINS: "Extreme Mountains",
}

# -------------------------------------------------------------------
# Block ID Constants
# -------------------------------------------------------------------
# Core Blocks
BLOCK_AIR = 0
BLOCK_COBBLESTONE = 1
BLOCK_GRASS = 2
BLOCK_DIRT = 4
BLOCK_STONE = 5
BLOCK_SAND = 6
BLOCK_WATER = 9
BLOCK_LAVA = 15
BLOCK_GRAVEL = 77
BLOCK_SNOW_BLOCK = 31
BLOCK_ICE = 32
BLOCK_BEDROCK = 14

# Flora & Decoration
BLOCK_ROSE = 10
BLOCK_CACTUS = 11
BLOCK_DEAD_BUSH = 12
BLOCK_DANDELION = 33
BLOCK_MELON = 209
BLOCK_PUMPKIN = 208
BLOCK_SUGAR_CANE = 210

# Wood Families:
# Oak (Original)
BLOCK_OAK_PLANKS = 7
BLOCK_OAK_LOG = 8
BLOCK_OAK_LEAVES = 13
BLOCK_OAK_SAPLING = 156
BLOCK_OAK_SLAB = 38
BLOCK_OAK_STAIRS = 41
BLOCK_OAK_DOOR = 43
BLOCK_OAK_DOOR_TOP = 65
BLOCK_OAK_TRAPDOOR = 47
BLOCK_OAK_FENCE = 51
BLOCK_OAK_FENCE_GATE = 75

# Birch
BLOCK_BIRCH_PLANKS = 222
BLOCK_BIRCH_LOG = 223
BLOCK_BIRCH_LEAVES = 224
BLOCK_BIRCH_SAPLING = 225
BLOCK_BIRCH_SLAB = 226
BLOCK_BIRCH_STAIRS = 227
BLOCK_BIRCH_DOOR = 228
BLOCK_BIRCH_DOOR_TOP = 229
BLOCK_BIRCH_TRAPDOOR = 230
BLOCK_BIRCH_FENCE = 231
BLOCK_BIRCH_FENCE_GATE = 272

# Spruce
BLOCK_SPRUCE_PLANKS = 232
BLOCK_SPRUCE_LOG = 233
BLOCK_SPRUCE_LEAVES = 234
BLOCK_SPRUCE_SAPLING = 235
BLOCK_SPRUCE_SLAB = 236
BLOCK_SPRUCE_STAIRS = 237
BLOCK_SPRUCE_DOOR = 238
BLOCK_SPRUCE_DOOR_TOP = 239
BLOCK_SPRUCE_TRAPDOOR = 240
BLOCK_SPRUCE_FENCE = 241
BLOCK_SPRUCE_FENCE_GATE = 273

# Jungle
BLOCK_JUNGLE_PLANKS = 242
BLOCK_JUNGLE_LOG = 243
BLOCK_JUNGLE_LEAVES = 244
BLOCK_JUNGLE_SAPLING = 245
BLOCK_JUNGLE_SLAB = 246
BLOCK_JUNGLE_STAIRS = 247
BLOCK_JUNGLE_DOOR = 248
BLOCK_JUNGLE_DOOR_TOP = 249
BLOCK_JUNGLE_TRAPDOOR = 250
BLOCK_JUNGLE_FENCE = 251
BLOCK_JUNGLE_FENCE_GATE = 274

# Acacia
BLOCK_ACACIA_PLANKS = 252
BLOCK_ACACIA_LOG = 253
BLOCK_ACACIA_LEAVES = 254
BLOCK_ACACIA_SAPLING = 255
BLOCK_ACACIA_SLAB = 256
BLOCK_ACACIA_STAIRS = 257
BLOCK_ACACIA_DOOR = 258
BLOCK_ACACIA_DOOR_TOP = 259
BLOCK_ACACIA_TRAPDOOR = 260
BLOCK_ACACIA_FENCE = 261
BLOCK_ACACIA_FENCE_GATE = 275

# Dark Oak
BLOCK_DARK_OAK_PLANKS = 262
BLOCK_DARK_OAK_LOG = 263
BLOCK_DARK_OAK_LEAVES = 264
BLOCK_DARK_OAK_SAPLING = 265
BLOCK_DARK_OAK_SLAB = 266
BLOCK_DARK_OAK_STAIRS = 267
BLOCK_DARK_OAK_DOOR = 268
BLOCK_DARK_OAK_DOOR_TOP = 269
BLOCK_DARK_OAK_TRAPDOOR = 270
BLOCK_DARK_OAK_FENCE = 271
BLOCK_DARK_OAK_FENCE_GATE = 276

# New Biome Terrain & Flora Blocks
BLOCK_SANDSTONE = 277
BLOCK_PODZOL = 278
BLOCK_FERN = 279
BLOCK_VINES = 280
BLOCK_RED_SAND = 281
BLOCK_PACKED_ICE = 282
BLOCK_RED_TULIP = 283
BLOCK_ORANGE_TULIP = 284
BLOCK_OXEYE_DAISY = 285

# -------------------------------------------------------------------
# Biome Parameter Centroids (Temperature [0..1], Moisture [0..1])
# -------------------------------------------------------------------
BIOME_CENTROIDS = {
	BIOME_DESERT:       (0.66, 0.28),
	BIOME_SAVANNA:      (0.62, 0.42),
	BIOME_JUNGLE:       (0.66, 0.68),
	BIOME_PLAINS:       (0.50, 0.32),
	BIOME_FOREST:       (0.48, 0.54),
	BIOME_BIRCH_FOREST: (0.38, 0.44),
	BIOME_SPRUCE_TAIGA: (0.30, 0.64),
	BIOME_SNOW_FOREST:  (0.20, 0.48),
}

# -------------------------------------------------------------------
# Noise Sampling
# -------------------------------------------------------------------
def get_temperature(wx, wz, seed=0):
	"""Returns continuous temperature value in range [0.0, 1.0]."""
	sx = wx + float((seed * 11003) % 50000)
	sz = wz + float((seed * 17011) % 50000)
	t_raw = pnoise2(sx / 750.0, sz / 750.0, octaves=2, persistence=0.5, lacunarity=2.0)
	return max(0.0, min(1.0, (t_raw + 0.55) / 1.10))


def get_moisture(wx, wz, seed=0):
	"""Returns continuous moisture value in range [0.0, 1.0]."""
	sx = wx + float((seed * 23017) % 50000) + 4000.0
	sz = wz + float((seed * 31013) % 50000) + 4000.0
	m_raw = pnoise2(sx / 750.0, sz / 750.0, octaves=2, persistence=0.5, lacunarity=2.0)
	return max(0.0, min(1.0, (m_raw + 0.55) / 1.10))


def get_foliage_color(t, m):
	"""
	Calculates authentic Minecraft RGB foliage color multiplier (r, g, b) in [0.0, 1.0]
	proportional to continuous Temperature (t) and Moisture/Humidity (m).
	- High Temp + High Moisture (Jungle): Vibrant lush emerald green.
	- High Temp + Low Moisture (Savanna/Desert): Warm yellowish-green / golden olive.
	- Moderate Temp + Moderate Moisture (Plains/Forest): Rich lush forest green.
	- Low Temp + High Moisture (Spruce Taiga): Cool dark pine evergreen.
	- Low Temp (Snow Forest): Cool muted pale pine green.
	"""
	t = max(0.0, min(1.0, t))
	m = max(0.0, min(1.0, m))
	r = 0.38 * (1.0 - t) + (0.70 * (1.0 - m) + 0.20 * m) * t
	g = 0.62 * (1.0 - t) + (0.75 * (1.0 - m) + 0.88 * m) * t
	b = 0.48 * (1.0 - t) + (0.22 * (1.0 - m) + 0.12 * m) * t
	return (r, g, b)


def get_grass_color(t, m):
	"""
	Calculates authentic Minecraft RGB grass color multiplier (r, g, b) in [0.0, 1.0]
	proportional to continuous Temperature (t) and Moisture/Humidity (m).
	- High Temp + High Moisture (Jungle): Vibrant neon emerald green.
	- High Temp + Low Moisture (Savanna/Desert): Warm golden yellowish-green.
	- Moderate Temp + Moderate Moisture (Plains/Forest): Vivid classic lush green.
	- Low Temp + High Moisture (Spruce Taiga): Cool muted pine green.
	- Low Temp (Snow Forest): Cool frosty pale teal green.
	"""
	t = max(0.0, min(1.0, t))
	m = max(0.0, min(1.0, m))
	r = 0.45 * (1.0 - t) + (0.75 * (1.0 - m) + 0.28 * m) * t
	g = 0.68 * (1.0 - t) + (0.72 * (1.0 - m) + 0.88 * m) * t
	b = 0.58 * (1.0 - t) + (0.22 * (1.0 - m) + 0.18 * m) * t
	return (r, g, b)


def get_biome_weights(t, m):
	"""Calculate normalized softmax weights for each climate biome based on (t, m)."""
	weights = {}
	total = 0.0
	k = 25.0  # Softness parameter: smooth transitions across boundaries
	for b_id, (ct, cm) in BIOME_CENTROIDS.items():
		dist_sq = (t - ct) ** 2 + (m - cm) ** 2
		w = math.exp(-k * dist_sq)
		weights[b_id] = w
		total += w

	if total > 0.0:
		for b_id in weights:
			weights[b_id] /= total
	else:
		weights[BIOME_PLAINS] = 1.0

	return weights


def get_biome_at(wx, wz, seed=0):
	"""Determines primary biome enum at world coordinate (wx, wz)."""
	sx = wx + float((seed * 10007) % 50000)
	sz = wz + float((seed * 16007) % 50000)

	# Mountain / Elevation mask
	mtn_mask = pnoise2((sx + 5000.0) / 450.0, (sz + 5000.0) / 450.0, octaves=1)
	if mtn_mask > 0.46:
		return BIOME_MOUNTAINS
	elif mtn_mask > 0.32:
		return BIOME_HILLS

	t = get_temperature(wx, wz, seed)
	m = get_moisture(wx, wz, seed)

	best_biome = BIOME_PLAINS
	min_dist_sq = float('inf')
	for b_id, (ct, cm) in BIOME_CENTROIDS.items():
		dist_sq = (t - ct) ** 2 + (m - cm) ** 2
		if dist_sq < min_dist_sq:
			min_dist_sq = dist_sq
			best_biome = b_id

	return best_biome


# -------------------------------------------------------------------
# Smooth Continuous Terrain Height Blending
# -------------------------------------------------------------------
def get_blended_height(wx, wz, seed=0):
	"""Computes continuous terrain height smoothly blended across biomes with no abrupt cliff edges."""
	seed_offset_x = float((seed * 10007) % 50000)
	seed_offset_z = float((seed * 16007) % 50000)

	sx = wx + seed_offset_x
	sz = wz + seed_offset_z

	cont = pnoise2(sx / 350.0, sz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)
	peaks_raw = pnoise2((sx + 1000.0) / 85.0, (sz + 1000.0) / 85.0, octaves=4, persistence=0.5, lacunarity=2.0)
	ridge = 1.0 - abs(peaks_raw * 2.0)

	# Climate factors
	t = get_temperature(wx, wz, seed)
	m = get_moisture(wx, wz, seed)
	b_weights = get_biome_weights(t, m)

	biome_base_y = {
		BIOME_DESERT:       65.0 + (peaks_raw * 2.5),
		BIOME_SAVANNA:      66.0 + (ridge * 1.5),
		BIOME_PLAINS:       66.0 + (peaks_raw * 1.8),
		BIOME_FOREST:       67.0 + (ridge * 2.0),
		BIOME_BIRCH_FOREST: 67.0 + (ridge * 2.2),
		BIOME_SPRUCE_TAIGA: 68.0 + (ridge * 2.8),
		BIOME_SNOW_FOREST:  68.0 + (ridge * 3.0),
		BIOME_JUNGLE:       68.0 + (ridge * 3.5),
	}

	land_target_y = sum(b_weights[b_id] * biome_base_y[b_id] for b_id in BIOME_CENTROIDS)

	if cont < -0.32:
		# Deep Ocean basin
		progress = max(0.0, min(1.0, (cont - (-0.50)) / 0.18))
		smooth_prog = 3.0 * progress * progress - 2.0 * progress * progress * progress
		target_y = 38.0 + smooth_prog * 16.0 + (peaks_raw * 1.5)
	elif cont < -0.22:
		# Coastal Shoreline & Beach Transition
		progress = (cont - (-0.32)) / 0.10
		smooth_prog = 3.0 * progress * progress - 2.0 * progress * progress * progress
		target_y = 54.0 + smooth_prog * (land_target_y - 54.0) + (ridge * 1.5)
	else:
		# Continental Landmass
		progress = min(1.0, (cont - (-0.22)) / 0.50)
		smooth_prog = 3.0 * progress * progress - 2.0 * progress * progress * progress
		target_y = land_target_y + (smooth_prog * 2.0)

		# Mountains and Hills overlay
		mtn_mask = pnoise2((sx + 5000.0) / 450.0, (sz + 5000.0) / 450.0, octaves=1)
		if mtn_mask > 0.32:
			t_mtn = min(1.0, (mtn_mask - 0.32) / 0.16)
			smooth_mtn = 3.0 * t_mtn * t_mtn - 2.0 * t_mtn * t_mtn * t_mtn
			peak_noise = pnoise2((sx + 1000.0) / 60.0, (sz + 1000.0) / 60.0, octaves=1)
			semi_ridge = 1.0 - abs(peak_noise * 1.5)
			summit = max(0.0, semi_ridge) ** 1.4
			mtn_height = (smooth_mtn * 16.0) + (smooth_mtn * summit * 38.0)
			target_y += mtn_height

	# Rivers Carving
	river_raw = abs(pnoise2((sx + 2000.0) / 240.0, (sz + 2000.0) / 240.0, octaves=3))
	if river_raw < 0.028:
		t_r = 1.0 - (river_raw / 0.028)
		r_blend = (t_r * t_r) * 3.5
		target_y = min(target_y, 61.0 - r_blend)

	# Micro sculpt
	sculpt = pnoise3(sx / 25.0, target_y / 15.0, sz / 25.0) * 1.5
	final_y = math.floor(target_y + sculpt)
	return max(4, min(final_y, 250))


# -------------------------------------------------------------------
# Surface Composition & Dithering
# -------------------------------------------------------------------
def get_surface_column(wx, wz, surface_y, seed=0):
	"""Determines the top block and sub-surface blocks for a column (wx, wz) at surface_y."""
	sx = wx + float((seed * 10007) % 50000)
	sz = wz + float((seed * 16007) % 50000)

	cont = pnoise2(sx / 350.0, sz / 350.0, octaves=3, persistence=0.5, lacunarity=2.0)
	t = get_temperature(wx, wz, seed)
	b_weights = get_biome_weights(t, get_moisture(wx, wz, seed))
	primary_biome = get_biome_at(wx, wz, seed)

	# Dither noise for natural transitions
	dither = pnoise2((sx + 800.0) / 12.0, (sz + 800.0) / 12.0, octaves=1) * 0.12

	# 1. High Mountain Tops: Snow & Stone Summits
	if surface_y >= 98:
		top = BLOCK_SNOW_BLOCK if (surface_y >= 105 or (surface_y >= 98 and (t + dither) < 0.45)) else BLOCK_STONE
		sub = BLOCK_STONE
		return top, sub, BLOCK_STONE
	elif primary_biome == BIOME_MOUNTAINS and surface_y >= 88:
		return (BLOCK_STONE if (dither > -0.02) else BLOCK_GRAVEL), BLOCK_STONE, BLOCK_STONE

	# 2. Beach & Shorelines
	if cont < -0.22 and surface_y <= 64:
		return BLOCK_SAND, BLOCK_SAND, BLOCK_SANDSTONE

	# 3. Desert Biome
	desert_weight = b_weights.get(BIOME_DESERT, 0.0)
	if desert_weight + dither > 0.38 or primary_biome == BIOME_DESERT:
		return BLOCK_SAND, BLOCK_SAND, BLOCK_SANDSTONE

	# 4. Cold / Snow Forest Biome
	if (t + dither) < 0.18 or primary_biome == BIOME_SNOW_FOREST:
		return BLOCK_SNOW_BLOCK, BLOCK_DIRT, BLOCK_DIRT

	# 5. Spruce Taiga: Podzol patches
	if primary_biome == BIOME_SPRUCE_TAIGA:
		podzol_noise = pnoise2((sx + 300.0) / 16.0, (sz + 300.0) / 16.0, octaves=1)
		if podzol_noise > 0.15:
			return BLOCK_PODZOL, BLOCK_DIRT, BLOCK_DIRT

	# Default: Rich Grass over Dirt
	return BLOCK_GRASS, BLOCK_DIRT, BLOCK_DIRT


# -------------------------------------------------------------------
# Procedural Tree Stamping Utilities
# -------------------------------------------------------------------
LEAF_BLOCK_IDS = {
	BLOCK_OAK_LEAVES, BLOCK_BIRCH_LEAVES, BLOCK_SPRUCE_LEAVES,
	BLOCK_JUNGLE_LEAVES, BLOCK_ACACIA_LEAVES, BLOCK_DARK_OAK_LEAVES, BLOCK_VINES
}

def set_chunk_block_safe(blocks, lx, ly, lz, block_id, overwrite=False):
	"""Sets block in chunk 1D array if within bounds."""
	if 0 <= lx < 16 and 0 <= ly < 256 and 0 <= lz < 16:
		idx = lx * 4096 + ly * 16 + lz
		if overwrite or blocks[idx] == BLOCK_AIR or blocks[idx] in LEAF_BLOCK_IDS:
			blocks[idx] = block_id


def generate_oak_tree(blocks, lx, ly, lz, rng):
	"""Generates standard Oak Tree (height 5-7)."""
	height = rng.randint(4, 6)
	for y in range(height):
		set_chunk_block_safe(blocks, lx, ly + y, lz, BLOCK_OAK_LOG, overwrite=True)

	top_y = ly + height
	for dy in range(-2, 2):
		radius = 2 if dy < 0 else (1 if dy == 0 else 0)
		for dx in range(-radius, radius + 1):
			for dz in range(-radius, radius + 1):
				if abs(dx) == radius and abs(dz) == radius and (dy >= 0 or rng.random() < 0.4):
					continue
				set_chunk_block_safe(blocks, lx + dx, top_y + dy, lz + dz, BLOCK_OAK_LEAVES)


def generate_birch_tree(blocks, lx, ly, lz, rng):
	"""Generates slender Birch Tree with bright white trunk and birch foliage (height 5-7)."""
	height = rng.randint(5, 7)
	for y in range(height):
		set_chunk_block_safe(blocks, lx, ly + y, lz, BLOCK_BIRCH_LOG, overwrite=True)

	top_y = ly + height
	for dy in range(-3, 2):
		radius = 2 if dy in (-2, -1) else 1
		for dx in range(-radius, radius + 1):
			for dz in range(-radius, radius + 1):
				if abs(dx) == radius and abs(dz) == radius and (dy >= 0 or rng.random() < 0.5):
					continue
				set_chunk_block_safe(blocks, lx + dx, top_y + dy, lz + dz, BLOCK_BIRCH_LEAVES)


def generate_spruce_tree(blocks, lx, ly, lz, rng):
	"""Generates tall conical tiered Spruce/Pine Tree (height 7-10)."""
	height = rng.randint(7, 10)
	for y in range(height):
		set_chunk_block_safe(blocks, lx, ly + y, lz, BLOCK_SPRUCE_LOG, overwrite=True)

	top_y = ly + height
	set_chunk_block_safe(blocks, lx, top_y, lz, BLOCK_SPRUCE_LEAVES)
	set_chunk_block_safe(blocks, lx, top_y + 1, lz, BLOCK_SPRUCE_LEAVES)

	current_radius = 1
	for dy in range(height - 1, 1, -1):
		cur_y = ly + dy
		rad = current_radius
		for dx in range(-rad, rad + 1):
			for dz in range(-rad, rad + 1):
				if abs(dx) == rad and abs(dz) == rad:
					continue
				set_chunk_block_safe(blocks, lx + dx, cur_y, lz + dz, BLOCK_SPRUCE_LEAVES)
		current_radius = 2 if current_radius == 1 else 1


def generate_jungle_tree(blocks, lx, ly, lz, rng):
	"""Generates tall tropical Jungle Tree with wide canopy and hanging vines (height 9-14)."""
	height = rng.randint(9, 14)
	for y in range(height):
		set_chunk_block_safe(blocks, lx, ly + y, lz, BLOCK_JUNGLE_LOG, overwrite=True)
		if y >= 2 and rng.random() < 0.45:
			for v_dx, v_dz in ((0, 1), (0, -1), (1, 0), (-1, 0)):
				if rng.random() < 0.35:
					set_chunk_block_safe(blocks, lx + v_dx, ly + y, lz + v_dz, BLOCK_VINES)

	top_y = ly + height
	for dy in range(-2, 2):
		rad = 3 if dy < 0 else (2 if dy == 0 else 1)
		for dx in range(-rad, rad + 1):
			for dz in range(-rad, rad + 1):
				if abs(dx) == rad and abs(dz) == rad and (dy >= 0 or rng.random() < 0.6):
					continue
				set_chunk_block_safe(blocks, lx + dx, top_y + dy, lz + dz, BLOCK_JUNGLE_LEAVES)


def generate_jungle_bush(blocks, lx, ly, lz, rng):
	"""Generates small Jungle Bush (1 log with spherical leaves) commonly found in Minecraft jungles."""
	set_chunk_block_safe(blocks, lx, ly, lz, BLOCK_JUNGLE_LOG, overwrite=True)
	for dy in range(0, 3):
		rad = 2 if dy == 0 else (1 if dy == 1 else 0)
		for dx in range(-rad, rad + 1):
			for dz in range(-rad, rad + 1):
				if abs(dx) == rad and abs(dz) == rad and (dy > 0 or rng.random() < 0.5):
					continue
				set_chunk_block_safe(blocks, lx + dx, ly + dy, lz + dz, BLOCK_JUNGLE_LEAVES)


def generate_acacia_tree(blocks, lx, ly, lz, rng):
	"""Generates iconic Savanna Acacia Tree with bent diagonal branches and umbrella top."""
	height = rng.randint(5, 7)
	cur_x, cur_z = lx, lz
	for y in range(3):
		set_chunk_block_safe(blocks, cur_x, ly + y, cur_z, BLOCK_ACACIA_LOG, overwrite=True)

	dir_x = rng.choice([-1, 0, 1])
	dir_z = rng.choice([-1, 0, 1])
	if dir_x == 0 and dir_z == 0:
		dir_x = 1

	for y in range(3, height):
		cur_x += dir_x if y == 3 else 0
		cur_z += dir_z if y == 3 else 0
		set_chunk_block_safe(blocks, cur_x, ly + y, cur_z, BLOCK_ACACIA_LOG, overwrite=True)

	top_y = ly + height
	for dx in range(-3, 4):
		for dz in range(-3, 4):
			if abs(dx) == 3 and abs(dz) == 3:
				continue
			set_chunk_block_safe(blocks, cur_x + dx, top_y, cur_z + dz, BLOCK_ACACIA_LEAVES)
	for dx in range(-2, 3):
		for dz in range(-2, 3):
			if abs(dx) == 2 and abs(dz) == 2:
				continue
			set_chunk_block_safe(blocks, cur_x + dx, top_y + 1, cur_z + dz, BLOCK_ACACIA_LEAVES)


def generate_dark_oak_tree(blocks, lx, ly, lz, rng):
	"""Generates thick Dark Oak Tree with dense foliage dome."""
	height = rng.randint(6, 8)
	for y in range(height):
		set_chunk_block_safe(blocks, lx, ly + y, lz, BLOCK_DARK_OAK_LOG, overwrite=True)
		set_chunk_block_safe(blocks, lx + 1, ly + y, lz, BLOCK_DARK_OAK_LOG, overwrite=True)
		set_chunk_block_safe(blocks, lx, ly + y, lz + 1, BLOCK_DARK_OAK_LOG, overwrite=True)
		set_chunk_block_safe(blocks, lx + 1, ly + y, lz + 1, BLOCK_DARK_OAK_LOG, overwrite=True)

	top_y = ly + height
	for dy in range(-2, 3):
		rad = 3 if dy <= 0 else 2
		for dx in range(-rad, rad + 2):
			for dz in range(-rad, rad + 2):
				if (dx == -rad or dx == rad + 1) and (dz == -rad or dz == rad + 1) and dy > 0:
					continue
				set_chunk_block_safe(blocks, lx + dx, top_y + dy, lz + dz, BLOCK_DARK_OAK_LEAVES)
