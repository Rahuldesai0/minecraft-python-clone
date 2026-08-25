import random
import math

# Roman numeral conversion
ROMAN_NUMERALS = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}

def to_roman(num):
	return ROMAN_NUMERALS.get(num, str(num))

# Complete Enchantment Metadata
ENCHANTMENTS = {
	"protection": {
		"name": "Protection",
		"max_level": 4,
		"weight": 10,
		"target": "armor",
		"min_power": [1, 12, 23, 34],
		"max_power": [21, 32, 43, 54],
	},
	"sharpness": {
		"name": "Sharpness",
		"max_level": 5,
		"weight": 10,
		"target": "sword_axe",
		"min_power": [1, 12, 23, 34, 45],
		"max_power": [21, 32, 43, 54, 65],
	},
	"efficiency": {
		"name": "Efficiency",
		"max_level": 5,
		"weight": 10,
		"target": "tool",
		"min_power": [1, 11, 21, 31, 41],
		"max_power": [51, 61, 71, 81, 91],
	},
	"power": {
		"name": "Power",
		"max_level": 5,
		"weight": 10,
		"target": "bow",
		"min_power": [1, 11, 21, 31, 41],
		"max_power": [16, 26, 36, 46, 56],
	},
	"fire_aspect": {
		"name": "Fire Aspect",
		"max_level": 2,
		"weight": 2,
		"target": "sword",
		"min_power": [10, 30],
		"max_power": [60, 80],
	},
	"infinity": {
		"name": "Infinity",
		"max_level": 1,
		"weight": 1,
		"target": "bow",
		"min_power": [20],
		"max_power": [70],
	},
	"fortune": {
		"name": "Fortune",
		"max_level": 3,
		"weight": 2,
		"target": "tool",
		"min_power": [15, 24, 33],
		"max_power": [65, 74, 83],
	},
	"looting": {
		"name": "Looting",
		"max_level": 3,
		"weight": 2,
		"target": "sword",
		"min_power": [15, 24, 33],
		"max_power": [65, 74, 83],
	},
}

# Item Categorization & Base Enchantability
ARMOR_IDS = {
	130: ("helmet", 15), 131: ("chestplate", 15), 132: ("leggings", 15), 133: ("boots", 15),  # Leather
	134: ("helmet", 25), 135: ("chestplate", 25), 136: ("leggings", 25), 137: ("boots", 25),  # Gold
	138: ("helmet", 9),  139: ("chestplate", 9),  140: ("leggings", 9),  141: ("boots", 9),   # Iron
	142: ("helmet", 10), 143: ("chestplate", 10), 144: ("leggings", 10), 145: ("boots", 10),  # Diamond
}

SWORD_IDS = {
	113: ("sword", 15),  # Wood
	114: ("sword", 5),   # Stone
	115: ("sword", 14),  # Iron
	116: ("sword", 10),  # Diamond
	120: ("sword", 22),  # Gold
}

AXE_IDS = {
	105: ("axe", 15), 106: ("axe", 5), 107: ("axe", 14), 108: ("axe", 10), 118: ("axe", 22)
}

TOOL_IDS = {
	101: ("pickaxe", 15), 102: ("pickaxe", 5), 103: ("pickaxe", 14), 104: ("pickaxe", 10), 117: ("pickaxe", 22),
	109: ("shovel", 15),  110: ("shovel", 5),  111: ("shovel", 14),  112: ("shovel", 10),  119: ("shovel", 22),
	190: ("hoe", 15),     191: ("hoe", 5),     192: ("hoe", 14),     193: ("hoe", 22),     194: ("hoe", 10),
}

BOW_ID = 157
BOOK_ID = 216
ENCHANTED_BOOK_ID = 217

def get_item_category(item_id):
	if item_id in ARMOR_IDS:
		return "armor"
	if item_id in SWORD_IDS:
		return "sword"
	if item_id in AXE_IDS:
		return "axe"
	if item_id in TOOL_IDS:
		return "tool"
	if item_id == BOW_ID:
		return "bow"
	if item_id in (BOOK_ID, ENCHANTED_BOOK_ID):
		return "book"
	return None

def is_enchantable(item_id):
	return get_item_category(item_id) is not None

def get_item_enchantability(item_id):
	if item_id in ARMOR_IDS:
		return ARMOR_IDS[item_id][1]
	if item_id in SWORD_IDS:
		return SWORD_IDS[item_id][1]
	if item_id in AXE_IDS:
		return AXE_IDS[item_id][1]
	if item_id in TOOL_IDS:
		return TOOL_IDS[item_id][1]
	if item_id == BOW_ID:
		return 1
	if item_id in (BOOK_ID, ENCHANTED_BOOK_ID):
		return 1
	return 1

def get_valid_enchantments_for_item(item_id):
	cat = get_item_category(item_id)
	if not cat:
		return []
	if cat == "armor":
		return ["protection"]
	if cat == "sword":
		return ["sharpness", "fire_aspect", "looting"]
	if cat == "axe":
		return ["efficiency", "sharpness", "fortune"]
	if cat == "tool":
		return ["efficiency", "fortune"]
	if cat == "bow":
		return ["power", "infinity"]
	if cat == "book":
		return list(ENCHANTMENTS.keys())
	return []

def count_valid_bookshelves(table_pos, world):
	"""Scans the 5x5 area around the enchanting table for up to 15 unobstructed bookshelves."""
	tx, ty, tz = table_pos
	count = 0

	# Check 5x5 square perimeter (dx, dz from -2 to +2 where max(|dx|, |dz|) == 2)
	# Layers: dy = 0 (same height as table) and dy = 1 (1 block above table)
	for dy in (0, 1):
		for dx in range(-2, 3):
			for dz in range(-2, 3):
				if max(abs(dx), abs(dz)) != 2:
					continue  # Only perimeter blocks count

				bx = tx + dx
				by = ty + dy
				bz = tz + dz

				# Bookshelf block is ID 23
				if world.get_block_number((bx, by, bz)) == 23:
					# Check for unobstructed line of sight (air blocks between table and bookshelf)
					obstructed = False
					# Intermediate block check
					step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
					step_z = 0 if dz == 0 else (1 if dz > 0 else -1)

					# Blocks directly adjacent to table towards the bookshelf must be air
					inter_pos = (tx + step_x, ty + dy, tz + step_z)
					if world.get_block_number(inter_pos) != 0:
						obstructed = True

					# For orthogonal perimeter (dx == +/-2 and dz == 0, or dz == +/-2 and dx == 0)
					if not obstructed and abs(dx) == 2 and abs(dz) == 1:
						if world.get_block_number((tx + step_x, ty + dy, tz + dz)) != 0:
							obstructed = True
					elif not obstructed and abs(dz) == 2 and abs(dx) == 1:
						if world.get_block_number((tx + dx, ty + dy, tz + step_z)) != 0:
							obstructed = True

					if not obstructed:
						count += 1
						if count >= 15:
							return 15
	return min(15, count)

def calculate_enchantment_levels(bookshelves, seed=None):
	"""Returns the required player levels for the 3 enchanting table slots based on bookshelf count."""
	rng = random.Random(seed) if seed is not None else random.Random()
	b = min(15, max(0, bookshelves))

	base_val = rng.randint(1, 8) + (b // 2) + rng.randint(0, b)

	lvl_1 = max(1, base_val // 3)
	lvl_2 = (base_val * 2) // 3 + 1
	lvl_3 = max(b * 2, base_val)

	# Cap slot 3 at Level 30 max in Java 1.8+
	if b == 15:
		lvl_3 = max(30, lvl_3)
	lvl_3 = min(30, max(1, lvl_3))
	lvl_2 = min(lvl_3, max(1, lvl_2))
	lvl_1 = min(lvl_2, max(1, lvl_1))

	return lvl_1, lvl_2, lvl_3

def generate_enchantment_offer(item_id, tier, req_level, seed=None):
	"""Selects a valid enchantment and rank for the given item and power level."""
	valid_keys = get_valid_enchantments_for_item(item_id)
	if not valid_keys:
		return None

	rng = random.Random(seed) if seed is not None else random.Random()
	enchantability = get_item_enchantability(item_id)

	# Modified level formula
	k = req_level + rng.randint(0, enchantability // 4 + 1) + rng.randint(0, enchantability // 4 + 1)
	scale = rng.uniform(0.85, 1.15)
	mod_level = max(1, int(round(k * scale)))

	# Find valid enchantments and highest valid rank
	eligible = []
	for key in valid_keys:
		info = ENCHANTMENTS[key]
		max_rank = info["max_level"]
		chosen_rank = 1
		for rank in range(max_rank, 0, -1):
			min_p = info["min_power"][rank - 1]
			max_p = info["max_power"][rank - 1]
			if min_p <= mod_level <= max_p:
				chosen_rank = rank
				break
			elif mod_level >= min_p:
				chosen_rank = rank
				break

		weight = info["weight"]
		eligible.append((key, chosen_rank, weight))

	if not eligible:
		key = rng.choice(valid_keys)
		chosen_rank = 1
	else:
		total_w = sum(w for _, _, w in eligible)
		roll = rng.randint(1, total_w)
		curr = 0
		key, chosen_rank = eligible[0][0], eligible[0][1]
		for e_key, e_rank, w in eligible:
			curr += w
			if roll <= curr:
				key, chosen_rank = e_key, e_rank
				break

	name = ENCHANTMENTS[key]["name"]
	disp_text = f"{name} {to_roman(chosen_rank)}" if ENCHANTMENTS[key]["max_level"] > 1 else name
	return {
		"key": key,
		"level": chosen_rank,
		"name": name,
		"display": disp_text,
		"req_level": req_level,
		"lapis_cost": tier,      # Tier 1 = 1 Lapis, Tier 2 = 2 Lapis, Tier 3 = 3 Lapis
		"level_cost": tier       # Tier 1 = 1 Level, Tier 2 = 2 Levels, Tier 3 = 3 Levels
	}

def apply_enchantment_to_slot(slot, ench_key, ench_level):
	"""Applies the enchantment to slot, creating/updating enchantment dict and turning Books into Enchanted Books."""
	if not slot or slot[0] == 0:
		return slot

	item_id = slot[0]
	count = slot[1]
	enchants = dict(slot[2]) if len(slot) > 2 and isinstance(slot[2], dict) else {}

	enchants[ench_key] = max(enchants.get(ench_key, 0), ench_level)

	# Transform regular Book into Enchanted Book
	if item_id == BOOK_ID:
		item_id = ENCHANTED_BOOK_ID

	return [item_id, count, enchants]

# Real Gameplay Effect Helpers
def get_protection_reduction(armor_slots):
	"""Returns damage reduction fraction (0.0 to 0.80) from Protection enchantments on equipped armor."""
	if not armor_slots:
		return 0.0
	total_levels = 0
	for slot in armor_slots:
		if slot and slot[0] != 0 and len(slot) > 2 and isinstance(slot[2], dict):
			total_levels += slot[2].get("protection", 0)
	# 4% damage reduction per protection level, capped at 80%
	return min(0.80, total_levels * 0.04)

def get_sharpness_bonus(slot):
	"""Returns extra melee damage from Sharpness enchantment (+0.5 * level + 0.5)."""
	if slot and slot[0] != 0 and len(slot) > 2 and isinstance(slot[2], dict):
		lvl = slot[2].get("sharpness", 0)
		if lvl > 0:
			return 0.5 * lvl + 0.5
	return 0.0

def get_fire_aspect_duration(slot):
	"""Returns fire duration in seconds from Fire Aspect enchantment (4.0 * level)."""
	if slot and slot[0] != 0 and len(slot) > 2 and isinstance(slot[2], dict):
		lvl = slot[2].get("fire_aspect", 0)
		if lvl > 0:
			return 4.0 * lvl
	return 0.0

def get_efficiency_multiplier(slot):
	"""Returns mining speed multiplier from Efficiency enchantment."""
	if slot and slot[0] != 0 and len(slot) > 2 and isinstance(slot[2], dict):
		lvl = slot[2].get("efficiency", 0)
		if lvl > 0:
			return 1.0 + (lvl * lvl + 1) * 0.25
	return 1.0

def get_bow_power_multiplier(slot):
	"""Returns arrow damage multiplier from Power enchantment (+25% * (level + 1))."""
	if slot and slot[0] != 0 and len(slot) > 2 and isinstance(slot[2], dict):
		lvl = slot[2].get("power", 0)
		if lvl > 0:
			return 1.0 + 0.25 * (lvl + 1)
	return 1.0

def has_infinity(slot):
	"""Returns True if the bow possesses the Infinity enchantment."""
	if slot and slot[0] != 0 and len(slot) > 2 and isinstance(slot[2], dict):
		return slot[2].get("infinity", 0) > 0
	return False

def get_fortune_level(slot):
	"""Returns the Fortune enchantment level on slot (0 to 3)."""
	if slot and slot[0] != 0 and len(slot) > 2 and isinstance(slot[2], dict):
		return slot[2].get("fortune", 0)
	return 0

def get_looting_level(slot):
	"""Returns the Looting enchantment level on slot (0 to 3)."""
	if slot and slot[0] != 0 and len(slot) > 2 and isinstance(slot[2], dict):
		return slot[2].get("looting", 0)
	return 0

def apply_fortune_to_block_drop(block_num, drop_id, drop_qty, fortune_level):
	"""Calculates bonus drop item quantity using vanilla Minecraft Java Edition Fortune mechanics."""
	if fortune_level <= 0 or drop_id is None:
		return drop_id, drop_qty

	# 1. Gravel (77) -> Flint (146) drop chance
	if block_num == 77:
		flint_chances = {1: 0.14, 2: 0.25, 3: 1.00}
		chance = flint_chances.get(fortune_level, 1.0)
		if random.random() < chance:
			return 146, 1
		else:
			return 77, 1

	# 2. Lapis Lazuli Ore (212) -> drops 4-9 base, multiplied by uniform(1, fortune_level + 1)
	if block_num == 212:
		mult = random.randint(1, fortune_level + 1)
		return drop_id, drop_qty * mult

	# 3. Glowstone (86) -> drops 2-4 dust, capped at 4 max
	if block_num == 86:
		bonus = random.randint(0, fortune_level)
		return drop_id, min(4, drop_qty + bonus)

	# 4. Melon Block (209) -> drops 3-7 slices, capped at 9 max
	if block_num == 209:
		bonus = random.randint(0, fortune_level)
		return drop_id, min(9, drop_qty + bonus)

	# 5. Mature Crops (Wheat 81, Carrots 204, Potatoes 205) -> bonus yield
	if block_num in (81, 204, 205):
		bonus = random.randint(0, fortune_level)
		return drop_id, drop_qty + bonus

	# 6. Discrete Ore drops: Coal (16 -> 121), Diamond (18 -> 122), Nether Quartz (87 -> 170)
	if block_num in (16, 18, 87) or (drop_id in (121, 122, 170)):
		roll = random.randint(0, fortune_level + 1)
		mult = max(1, roll)
		return drop_id, drop_qty * mult

	return drop_id, drop_qty
