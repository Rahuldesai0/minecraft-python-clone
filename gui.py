import os
import math
import random
import time
import pyglet
import pyglet.gl as gl
import enchanting

# List of all available block items for the inventory palette
# Each entry is (block_id, display_name, texture_name)
PALETTE_ITEMS = [
	(2, "Grass Block", "grass"),
	(4, "Dirt", "dirt"),
	(77, "Gravel", "gravel"),
	(5, "Stone", "stone"),
	(1, "Cobblestone", "cobblestone"),
	(7, "Oak Planks", "planks"),
	(8, "Oak Log", "log_side"),
	(6, "Sand", "sand"),
	(13, "Oak Leaves", "leaves"),
	(21, "Glass", "glass"),
	(22, "Bricks", "bricks"),
	(23, "Bookshelf", "bookshelf"),
	(24, "Obsidian", "obsidian"),
	(25, "TNT", "tnt_side"),
	(26, "Crafting Table", "crafting_table_top"),
	(27, "Furnace", "furnace_front"),
	(28, "Gold Block", "gold_block"),
	(29, "Iron Block", "iron_block"),
	(30, "Diamond Block", "diamond_block"),
	(16, "Coal Ore", "coal_ore"),
	(17, "Iron Ore", "iron_ore"),
	(18, "Diamond Ore", "diamond_ore"),
	(35, "Gold Ore", "gold_ore"),
	(36, "Redstone Ore", "redstone_ore"),
	(14, "Bedrock", "bedrock"),
	(9, "Water Source", "water"),
	(15, "Lava Source", "lava"),
	(31, "Snow", "snow"),
	(32, "Ice", "ice"),
	(10, "Rose", "rose"),
	(33, "Dandelion", "yellow_flower"),
	(11, "Cactus", "cactus_side"),
	(12, "Dead Bush", "dead_bush"),
	(34, "Sponge", "sponge"),
	(37, "Chest", "chest_front"),
	(38, "Oak Slab", "items/oak_slab"),
	(39, "Cobblestone Slab", "items/cobblestone_slab"),
	(40, "Stone Slab", "items/stone_slab"),
	(41, "Oak Stairs", "items/oak_stairs"),
	(42, "Cobblestone Stairs", "items/cobblestone_stairs"),
	(43, "Oak Door", "items/door_wood"),
	(45, "Iron Door", "items/door_iron"),
	(47, "Oak Trapdoor", "items/oak_trapdoor"),
	(49, "Iron Trapdoor", "iron_trapdoor"),
	(51, "Oak Fence", "items/oak_fence"),
	(52, "Cobblestone Wall", "items/cobblestone_wall"),
	(53, "Glass Pane", "items/glass_pane"),
	(56, "Oak Fence Gate", "items/oak_fence_gate"),
	(77, "Gravel", "gravel"),
	(79, "Torch", "torch"),
	(80, "Farmland", "soil"),
	(81, "Wheat Crops", "crops"),
	(82, "Mossy Cobblestone", "mossy_cobblestone"),
	(83, "White Wool", "white_cloth"),
	(84, "Netherrack", "netherrack"),
	(85, "Soul Sand", "soul_sand"),
	(86, "Glowstone", "glowstone"),
	(87, "Nether Quartz Ore", "quartz_ore"),
	(90, "Nether Brick", "nether_brick"),
	(91, "Nether Brick Fence", "items/nether_brick_fence"),
	(92, "Nether Brick Stairs", "items/nether_brick_stairs"),
	(94, "Nether Wart", "nether_wart_stage_2"),
	(95, "Nether Brick Slab", "items/nether_brick_slab"),
	(96, "Stone Bricks", "stonebrick"),
	(97, "Mossy Stone Bricks", "stonebrick_mossy"),
	(98, "Cracked Stone Bricks", "stonebrick_cracked"),
	(99, "Iron Bars", "items/iron_bars"),
	(178, "Stone Brick Stairs", "items/stone_brick_stairs"),
	(180, "Stone Brick Slab", "items/stone_brick_slab"),
	(181, "End Portal Frame", "endframe_top"),
	(147, "Bucket", "items/bucket_empty"),
	(148, "Water Bucket", "items/bucket_water"),
	(149, "Lava Bucket", "items/bucket_lava"),
	(151, "Flint and Steel", "items/flint_and_steel"),
	(204, "Carrot Crops", "carrots_stage_3"),
	(205, "Potato Crops", "potatoes_stage_3"),
	(206, "Pumpkin Stem", "pumpkin_stem_disconnected"),
	(207, "Melon Stem", "melon_stem_disconnected"),
	(208, "Pumpkin", "pumpkin_side"),
	(209, "Melon", "melon_side"),
	(210, "Sugar Cane", "sugar_cane"),
	(212, "Lapis Lazuli Ore", "lapis_ore"),
	(213, "Enchanting Table", "enchanting_table_top"),
	(219, "Bed", "items/bed"),
	# Birch Family (222-231, 272)
	(222, "Birch Planks", "planks_birch"),
	(223, "Birch Log", "log_birch"),
	(224, "Birch Leaves", "leaves_birch"),
	(225, "Birch Sapling", "sapling_birch"),
	(226, "Birch Slab", "items/birch_slab"),
	(227, "Birch Stairs", "items/birch_stairs"),
	(228, "Birch Door", "items/door_birch"),
	(230, "Birch Trapdoor", "items/birch_trapdoor"),
	(231, "Birch Fence", "items/birch_fence"),
	(272, "Birch Fence Gate", "items/birch_fence_gate"),
	# Spruce Family (232-241, 273)
	(232, "Spruce Planks", "planks_spruce"),
	(233, "Spruce Log", "log_spruce"),
	(234, "Spruce Leaves", "leaves_spruce"),
	(235, "Spruce Sapling", "sapling_spruce"),
	(236, "Spruce Slab", "items/spruce_slab"),
	(237, "Spruce Stairs", "items/spruce_stairs"),
	(238, "Spruce Door", "items/door_spruce"),
	(240, "Spruce Trapdoor", "items/spruce_trapdoor"),
	(241, "Spruce Fence", "items/spruce_fence"),
	(273, "Spruce Fence Gate", "items/spruce_fence_gate"),
	# Jungle Family (242-251, 274)
	(242, "Jungle Planks", "planks_jungle"),
	(243, "Jungle Log", "log_jungle"),
	(244, "Jungle Leaves", "leaves_jungle"),
	(245, "Jungle Sapling", "sapling_jungle"),
	(246, "Jungle Slab", "items/jungle_slab"),
	(247, "Jungle Stairs", "items/jungle_stairs"),
	(248, "Jungle Door", "items/door_jungle"),
	(250, "Jungle Trapdoor", "items/jungle_trapdoor"),
	(251, "Jungle Fence", "items/jungle_fence"),
	(274, "Jungle Fence Gate", "items/jungle_fence_gate"),
	# Acacia Family (252-261, 275)
	(252, "Acacia Planks", "planks_acacia"),
	(253, "Acacia Log", "log_acacia"),
	(254, "Acacia Leaves", "leaves_acacia"),
	(255, "Acacia Sapling", "sapling_acacia"),
	(256, "Acacia Slab", "items/acacia_slab"),
	(257, "Acacia Stairs", "items/acacia_stairs"),
	(258, "Acacia Door", "items/door_acacia"),
	(260, "Acacia Trapdoor", "items/acacia_trapdoor"),
	(261, "Acacia Fence", "items/acacia_fence"),
	(275, "Acacia Fence Gate", "items/acacia_fence_gate"),
	# Dark Oak Family (262-271, 276)
	(262, "Dark Oak Planks", "planks_big_oak"),
	(263, "Dark Oak Log", "log_big_oak"),
	(264, "Dark Oak Leaves", "leaves_big_oak"),
	(265, "Dark Oak Sapling", "sapling_roofed_oak"),
	(266, "Dark Oak Slab", "items/dark_oak_slab"),
	(267, "Dark Oak Stairs", "items/dark_oak_stairs"),
	(268, "Dark Oak Door", "items/door_dark_oak"),
	(270, "Dark Oak Trapdoor", "items/dark_oak_trapdoor"),
	(271, "Dark Oak Fence", "items/dark_oak_fence"),
	(276, "Dark Oak Fence Gate", "items/dark_oak_fence_gate"),
	# Biome Terrain & Flora (277-285)
	(277, "Sandstone", "sandstone_normal"),
	(278, "Podzol", "dirt_podzol_top"),
	(279, "Fern", "fern"),
	(280, "Vines", "vine"),
	(281, "Red Sand", "red_sand"),
	(282, "Packed Ice", "ice_packed"),
	(283, "Red Tulip", "flower_tulip_red"),
	(284, "Orange Tulip", "flower_tulip_orange"),
	(285, "Oxeye Daisy", "flower_oxeye_daisy"),
]

TOOL_ITEMS = [
	(100, "Stick", "items/stick"),
	(101, "Wooden Pickaxe", "items/wood_pickaxe"),
	(102, "Stone Pickaxe", "items/stone_pickaxe"),
	(103, "Iron Pickaxe", "items/iron_pickaxe"),
	(104, "Diamond Pickaxe", "items/diamond_pickaxe"),
	(105, "Wooden Axe", "items/wood_axe"),
	(106, "Stone Axe", "items/stone_axe"),
	(107, "Iron Axe", "items/iron_axe"),
	(108, "Diamond Axe", "items/diamond_axe"),
	(109, "Wooden Shovel", "items/wood_shovel"),
	(110, "Stone Shovel", "items/stone_shovel"),
	(111, "Iron Shovel", "items/iron_shovel"),
	(112, "Diamond Shovel", "items/diamond_shovel"),
	(113, "Wooden Sword", "items/wood_sword"),
	(114, "Stone Sword", "items/stone_sword"),
	(115, "Iron Sword", "items/iron_sword"),
	(116, "Diamond Sword", "items/diamond_sword"),
	(117, "Gold Pickaxe", "items/gold_pickaxe"),
	(118, "Gold Axe", "items/gold_axe"),
	(119, "Gold Shovel", "items/gold_shovel"),
	(120, "Gold Sword", "items/gold_sword"),
	(121, "Coal", "items/coal"),
	(122, "Diamond", "items/diamond"),
	(123, "Iron Ingot", "items/iron_ingot"),
	(124, "Gold Ingot", "items/gold_ingot"),
	(125, "Raw Porkchop", "items/porkchop_raw"),
	(126, "Leather", "items/leather"),
	(127, "Raw Beef", "items/beef_raw"),
	(128, "Cooked Porkchop", "items/porkchop_cooked"),
	(129, "Steak", "items/beef_cooked"),
	# Armor Pieces (130-145)
	(130, "Leather Cap", "items/leather_helmet"),
	(131, "Leather Tunic", "items/leather_chestplate"),
	(132, "Leather Pants", "items/leather_leggings"),
	(133, "Leather Boots", "items/leather_boots"),
	(134, "Golden Helmet", "items/gold_helmet"),
	(135, "Golden Chestplate", "items/gold_chestplate"),
	(136, "Golden Leggings", "items/gold_leggings"),
	(137, "Golden Boots", "items/gold_boots"),
	(138, "Iron Helmet", "items/iron_helmet"),
	(139, "Iron Chestplate", "items/iron_chestplate"),
	(140, "Iron Leggings", "items/iron_leggings"),
	(141, "Iron Boots", "items/iron_boots"),
	(142, "Diamond Helmet", "items/diamond_helmet"),
	(143, "Diamond Chestplate", "items/diamond_chestplate"),
	(144, "Diamond Leggings", "items/diamond_leggings"),
	(145, "Diamond Boots", "items/diamond_boots"),
	(146, "Flint", "items/flint"),
	(147, "Bucket", "items/bucket_empty"),
	(148, "Water Bucket", "items/bucket_water"),
	(149, "Lava Bucket", "items/bucket_lava"),
	(151, "Flint and Steel", "items/flint_and_steel"),
	(152, "Bread", "items/bread"),
	(153, "Apple", "items/apple"),
	(154, "Wheat", "items/wheat"),
	(155, "Seeds", "items/seeds_wheat"),
	(156, "Oak Sapling", "sapling"),
	(157, "Bow", "items/bow_standby"),
	(158, "Arrow", "items/arrow"),
	(159, "String", "items/string"),
	(160, "Feather", "items/feather"),
	(161, "Golden Apple", "items/apple_golden"),
	(162, "Raw Chicken", "items/chicken_raw"),
	(163, "Cooked Chicken", "items/chicken_cooked"),
	(164, "Raw Mutton", "items/mutton_raw"),
	(165, "Cooked Mutton", "items/mutton_cooked"),
	(166, "Rotten Flesh", "items/rotten_flesh"),
	(167, "Bone", "items/bone"),
	(168, "Spider Eye", "items/spider_eye"),
	(169, "Gunpowder", "items/gunpowder"),
	(170, "Nether Quartz", "items/quartz"),
	(171, "Glowstone Dust", "items/glowstone_dust"),
	(172, "Blaze Rod", "items/blaze_rod"),
	(173, "Nether Wart", "items/nether_wart"),
	(174, "Nether Brick", "items/netherbrick"),
	(175, "Blaze Powder", "items/blaze_powder"),
	(176, "Ender Pearl", "items/ender_pearl"),
	(177, "Eye of Ender", "items/ender_eye"),
	# Hoes (190-194)
	(190, "Wooden Hoe", "items/wood_hoe"),
	(191, "Stone Hoe", "items/stone_hoe"),
	(192, "Iron Hoe", "items/iron_hoe"),
	(193, "Golden Hoe", "items/gold_hoe"),
	(194, "Diamond Hoe", "items/diamond_hoe"),
	# Crops, Seeds, Food & Plants (195-203)
	(195, "Carrot", "items/carrot"),
	(196, "Potato", "items/potato"),
	(197, "Baked Potato", "items/potato_baked"),
	(198, "Poisonous Potato", "items/potato_poisonous"),
	(199, "Pumpkin Seeds", "items/seeds_pumpkin"),
	(200, "Melon Seeds", "items/seeds_melon"),
	(201, "Melon Slice", "items/melon"),
	(202, "Sugar Cane", "items/reeds"),
	(203, "Sugar", "items/sugar"),
	# Bone Meal (211)
	(211, "Bone Meal", "items/dye_powder_white"),
	# Enchanting & Lapis (214-217)
	(214, "Lapis Lazuli", "items/dye_powder_blue"),
	(215, "Paper", "items/paper"),
	(216, "Book", "items/book_normal"),
	(217, "Enchanted Book", "items/book_enchanted"),
	(218, "Bottle o' Enchanting", "items/experience_bottle"),
]

ALL_ITEMS = PALETTE_ITEMS + TOOL_ITEMS
BLOCK_INFO = {item[0]: (item[1], item[2]) for item in ALL_ITEMS}
BLOCK_INFO[88] = ("Nether Portal", "portal")
BLOCK_INFO[89] = ("Nether Portal", "portal")
BLOCK_INFO[90] = ("Nether Brick", "nether_brick")
BLOCK_INFO[91] = ("Nether Brick Fence", "items/nether_brick_fence")
BLOCK_INFO[92] = ("Nether Brick Stairs", "items/nether_brick_stairs")
BLOCK_INFO[93] = ("Nether Brick Stairs", "items/nether_brick_stairs")
BLOCK_INFO[94] = ("Nether Wart", "nether_wart_stage_2")
BLOCK_INFO[95] = ("Nether Brick Slab", "items/nether_brick_slab")
BLOCK_INFO[96] = ("Stone Bricks", "stonebrick")
BLOCK_INFO[97] = ("Mossy Stone Bricks", "stonebrick_mossy")
BLOCK_INFO[98] = ("Cracked Stone Bricks", "stonebrick_cracked")
BLOCK_INFO[99] = ("Iron Bars", "items/iron_bars")
BLOCK_INFO[178] = ("Stone Brick Stairs", "items/stone_brick_stairs")
BLOCK_INFO[179] = ("Stone Brick Stairs", "items/stone_brick_stairs")
BLOCK_INFO[180] = ("Stone Brick Slab", "items/stone_brick_slab")
BLOCK_INFO[181] = ("End Portal Frame", "endframe_top")
BLOCK_INFO[182] = ("End Portal Frame (Filled)", "endframe_eye")
BLOCK_INFO[183] = ("End Portal", "portal")
BLOCK_INFO[184] = ("Infested Stone Bricks", "stonebrick")
BLOCK_INFO[185] = ("Infested Mossy Stone Bricks", "stonebrick_mossy")
BLOCK_INFO[186] = ("Infested Cracked Stone Bricks", "stonebrick_cracked")
BLOCK_INFO[187] = ("Infested Stone", "stone")
BLOCK_INFO[188] = ("End Stone", "end_stone")
BLOCK_INFO[189] = ("Dragon Egg", "obsidian")
BLOCK_INFO[219] = ("Bed", "items/bed")
BLOCK_INFO[220] = ("Bed (Foot)", "bed_feet_top")
BLOCK_INFO[221] = ("Bed (Head)", "bed_head_top")
BLOCK_INFO[229] = ("Birch Door (Top)", "door_birch_upper")
BLOCK_INFO[239] = ("Spruce Door (Top)", "door_spruce_upper")
BLOCK_INFO[249] = ("Jungle Door (Top)", "door_jungle_upper")
BLOCK_INFO[259] = ("Acacia Door (Top)", "door_acacia_upper")
BLOCK_INFO[269] = ("Dark Oak Door (Top)", "door_dark_oak_upper")

ARMOR_SLOT_TYPES = {
	130: 0, 134: 0, 138: 0, 142: 0,  # Helmets -> Slot 0
	131: 1, 135: 1, 139: 1, 143: 1,  # Chestplates -> Slot 1
	132: 2, 136: 2, 140: 2, 144: 2,  # Leggings -> Slot 2
	133: 3, 137: 3, 141: 3, 145: 3,  # Boots -> Slot 3
}

ARMOR_DEFENSE_POINTS = {
	# Leather Set (+7 Total)
	130: 1, 131: 3, 132: 2, 133: 1,
	# Gold Set (+11 Total)
	134: 2, 135: 5, 136: 3, 137: 1,
	# Iron Set (+15 Total)
	138: 2, 139: 6, 140: 5, 141: 2,
	# Diamond Set (+20 Total)
	142: 3, 143: 8, 144: 6, 145: 3,
}

def get_max_stack_size(item_id):
	"""Returns the maximum stack size for an item ID. Tools, Armor, Bow, Liquid Buckets, Flint and Steel, & Beds do not stack (max stack = 1). Empty Buckets and Ender Pearls stack to 16. Others stack to 64."""
	if (101 <= item_id <= 120) or (130 <= item_id <= 145) or item_id in (148, 149, 151, 157, 219, 220, 221):
		return 1
	if item_id in (147, 176):
		return 16
	return 64

# Minecraft Attack Damage values (in HP):
# Fist = 1.0 (0.5 hearts)
# Swords (highest per tier): Wood (4.0), Stone (5.0), Iron (6.0), Diamond (7.0), Gold (4.0)
# Axes (second highest): Wood (3.0), Stone (4.0), Iron (5.0), Diamond (6.0), Gold (3.0)
# Pickaxes: Wood (2.0), Stone (3.0), Iron (4.0), Diamond (5.0), Gold (2.0)
# Shovels: Wood (1.5), Stone (2.5), Iron (3.5), Diamond (4.5), Gold (1.5)
ITEM_ATTACK_DAMAGE = {
	# Swords (Highest per tier)
	113: 4.0,  # Wood Sword
	114: 5.0,  # Stone Sword
	115: 6.0,  # Iron Sword
	116: 7.0,  # Diamond Sword
	120: 4.0,  # Gold Sword

	# Axes (Second highest per tier)
	105: 3.0,  # Wood Axe
	106: 4.0,  # Stone Axe
	107: 5.0,  # Iron Axe
	108: 6.0,  # Diamond Axe
	118: 3.0,  # Gold Axe

	# Pickaxes
	101: 2.0,  # Wood Pickaxe
	102: 3.0,  # Stone Pickaxe
	103: 4.0,  # Iron Pickaxe
	104: 5.0,  # Diamond Pickaxe
	117: 2.0,  # Gold Pickaxe

	# Shovels
	109: 1.5,  # Wood Shovel
	110: 2.5,  # Stone Shovel
	111: 3.5,  # Iron Shovel
	112: 4.5,  # Diamond Shovel
	119: 1.5,  # Gold Shovel
}

def get_item_attack_damage(item_id):
	"""Returns the attack damage for a given item or weapon ID (default 1.0 for fist)."""
	return ITEM_ATTACK_DAMAGE.get(item_id, 1.0)

# Minecraft Food Values: item_id -> (hunger_restored, saturation_restored, absorption_points)
FOOD_VALUES = {
	125: (3, 1.8, 0.0),    # Raw Porkchop (+3 Hunger, +1.8 Saturation)
	128: (8, 12.8, 0.0),   # Cooked Porkchop (+8 Hunger, +12.8 Saturation)
	127: (3, 1.8, 0.0),    # Raw Beef (+3 Hunger, +1.8 Saturation)
	129: (8, 12.8, 0.0),   # Steak / Cooked Beef (+8 Hunger, +12.8 Saturation)
	152: (5, 6.0, 0.0),    # Bread (+5 Hunger, +6.0 Saturation)
	153: (4, 2.4, 0.0),    # Apple (+4 Hunger, +2.4 Saturation)
	161: (4, 9.6, 4.0),    # Golden Apple (+4 Hunger, +9.6 Saturation, +4.0 Absorption = 2 extra yellow hearts)
	162: (2, 1.2, 0.0),    # Raw Chicken (+2 Hunger, +1.2 Saturation)
	163: (6, 7.2, 0.0),    # Cooked Chicken (+6 Hunger, +7.2 Saturation)
	164: (2, 1.2, 0.0),    # Raw Mutton (+2 Hunger, +1.2 Saturation)
	165: (6, 9.6, 0.0),    # Cooked Mutton (+6 Hunger, +9.6 Saturation)
	166: (4, 0.8, 0.0),    # Rotten Flesh (+4 Hunger, +0.8 Saturation)
	168: (2, 3.2, 0.0),    # Spider Eye (+2 Hunger, +3.2 Saturation)
	195: (3, 3.6, 0.0),    # Carrot (+3 Hunger, +3.6 Saturation)
	196: (1, 0.6, 0.0),    # Potato (+1 Hunger, +0.6 Saturation)
	197: (5, 6.0, 0.0),    # Baked Potato (+5 Hunger, +6.0 Saturation)
	198: (2, 1.2, 0.0),    # Poisonous Potato (+2 Hunger, +1.2 Saturation)
	201: (2, 1.2, 0.0),    # Melon Slice (+2 Hunger, +1.2 Saturation)
}

# Smelting Recipes: input_item_id -> (result_item_id, result_count)
SMELTING_RECIPES = {
	17: (123, 1),   # Iron Ore -> Iron Ingot
	35: (124, 1),   # Gold Ore -> Gold Ingot
	84: (174, 1),   # Netherrack -> Nether Brick item
	1:  (5, 1),     # Cobblestone -> Stone
	8:   (121, 1),  # Oak Log -> Coal (Charcoal)
	223: (121, 1),  # Birch Log -> Charcoal
	233: (121, 1),  # Spruce Log -> Charcoal
	243: (121, 1),  # Jungle Log -> Charcoal
	253: (121, 1),  # Acacia Log -> Charcoal
	263: (121, 1),  # Dark Oak Log -> Charcoal
	6:   (21, 1),   # Sand -> Glass
	281: (21, 1),   # Red Sand -> Glass
	4:  (22, 1),    # Clay/Dirt -> Bricks
	125: (128, 1),  # Raw Porkchop -> Cooked Porkchop
	127: (129, 1),  # Raw Beef -> Steak (Cooked Beef)
	162: (163, 1),  # Raw Chicken -> Cooked Chicken
	164: (165, 1),  # Raw Mutton -> Cooked Mutton
	196: (197, 1),  # Raw Potato -> Baked Potato
}

# Smelting Experience (XP granted per item smelted): result_item_id -> xp_amount
SMELTING_XP = {
	123: 0.7,   # Iron Ingot -> 0.7 XP
	124: 1.0,   # Gold Ingot -> 1.0 XP
	128: 0.35,  # Cooked Porkchop -> 0.35 XP
	129: 0.35,  # Steak (Cooked Beef) -> 0.35 XP
	163: 0.35,  # Cooked Chicken -> 0.35 XP
	165: 0.35,  # Cooked Mutton -> 0.35 XP
	197: 0.35,  # Baked Potato -> 0.35 XP
	5:   0.1,   # Stone -> 0.1 XP
	21:  0.1,   # Glass -> 0.1 XP
	121: 0.15,  # Charcoal -> 0.15 XP
	174: 0.1,   # Nether Brick -> 0.1 XP
	22:  0.3,   # Bricks -> 0.3 XP
}

# Fuel Durations (in seconds of burn time): item_id -> burn_time_seconds
# 1 item smelt takes 10.0 seconds
FUEL_BURN_TIMES = {
	121: 80.0,  # Coal item -> 80s (8 smelts)
	16:  80.0,  # Coal Ore -> 80s (8 smelts)
	# Logs
	8: 15.0, 223: 15.0, 233: 15.0, 243: 15.0, 253: 15.0, 263: 15.0,
	# Planks
	7: 15.0, 222: 15.0, 232: 15.0, 242: 15.0, 252: 15.0, 262: 15.0,
	# Slabs
	38: 7.5, 226: 7.5, 236: 7.5, 246: 7.5, 256: 7.5, 266: 7.5,
	# Stairs
	41: 15.0, 227: 15.0, 237: 15.0, 247: 15.0, 257: 15.0, 267: 15.0,
	# Doors
	43: 10.0, 228: 10.0, 238: 10.0, 248: 10.0, 258: 10.0, 268: 10.0,
	# Trapdoors
	47: 15.0, 230: 15.0, 240: 15.0, 250: 15.0, 260: 15.0, 270: 15.0,
	# Fences
	51: 15.0, 231: 15.0, 241: 15.0, 251: 15.0, 261: 15.0, 271: 15.0,
	# Gates
	75: 15.0, 272: 15.0, 273: 15.0, 274: 15.0, 275: 15.0, 276: 15.0,
	# Saplings
	156: 5.0, 225: 5.0, 235: 5.0, 245: 5.0, 255: 5.0, 265: 5.0,
	26:  15.0,  # Crafting Table -> 15s
	23:  15.0,  # Bookshelf -> 15s
	101: 10.0,  # Wooden Pickaxe -> 10s
	105: 10.0,  # Wooden Axe -> 10s
	109: 10.0,  # Wooden Shovel -> 10s
	113: 10.0,  # Wooden Sword -> 10s
	190: 10.0,  # Wooden Hoe -> 10s
	100: 5.0,   # Stick -> 5s (0.5 smelts)
	149: 1000.0, # Lava Bucket -> 1000s (100 smelts)
}

# Tool Properties: item_id -> (category, tier, speed_multiplier)
# Category: "pickaxe", "axe", "shovel", "sword", "hoe"
# Tiers: 1=Wood, 2=Stone, 3=Iron, 4=Diamond, 5=Gold
TOOL_PROPERTIES = {
	101: ("pickaxe", 1, 2.0),   # Wood Pickaxe
	102: ("pickaxe", 2, 4.0),   # Stone Pickaxe
	103: ("pickaxe", 3, 6.0),   # Iron Pickaxe
	104: ("pickaxe", 4, 8.0),   # Diamond Pickaxe
	117: ("pickaxe", 5, 12.0),  # Gold Pickaxe

	105: ("axe", 1, 2.0),       # Wood Axe
	106: ("axe", 2, 4.0),       # Stone Axe
	107: ("axe", 3, 6.0),       # Iron Axe
	108: ("axe", 4, 8.0),       # Diamond Axe
	118: ("axe", 5, 12.0),      # Gold Axe

	109: ("shovel", 1, 2.0),    # Wood Shovel
	110: ("shovel", 2, 4.0),    # Stone Shovel
	111: ("shovel", 3, 6.0),    # Iron Shovel
	112: ("shovel", 4, 8.0),    # Diamond Shovel
	119: ("shovel", 5, 12.0),   # Gold Shovel

	113: ("sword", 1, 1.5),     # Wood Sword
	114: ("sword", 2, 2.0),     # Stone Sword
	115: ("sword", 3, 2.5),     # Iron Sword
	116: ("sword", 4, 3.0),     # Diamond Sword
	120: ("sword", 5, 4.0),     # Gold Sword

	190: ("hoe", 1, 2.0),       # Wood Hoe
	191: ("hoe", 2, 4.0),       # Stone Hoe
	192: ("hoe", 3, 6.0),       # Iron Hoe
	193: ("hoe", 5, 12.0),      # Gold Hoe
	194: ("hoe", 4, 8.0),       # Diamond Hoe
}

# Block Mining Specifications: b_num -> (preferred_tool_category, min_required_tier, base_break_seconds, drop_item_id)
# min_required_tier: 0 = Hand/Any Tool can harvest, 1 = Wood+, 2 = Stone+, 3 = Iron+, 4 = Diamond+, 99 = No drop (Glass)
BLOCK_MINING_PROPERTIES = {
	1:  ("pickaxe", 1, 1.8, 1),    # Cobblestone (Requires Wood Pickaxe+)
	2:  ("shovel", 0, 0.6, 4),     # Grass Block (Drops Dirt)
	3:  ("shovel", 0, 0.6, 4),     # Grass
	4:  ("shovel", 0, 0.6, 4),     # Dirt
	5:  ("pickaxe", 1, 1.8, 1),    # Stone (Requires Wood Pickaxe+, drops Cobblestone)
	6:  ("shovel", 0, 0.5, 6),     # Sand
	7:  ("axe", 0, 1.2, 7),        # Planks
	8:  ("axe", 0, 1.5, 8),        # Log
	10: (None, 0, 0.1, 10),        # Rose
	11: (None, 0, 0.4, 11),        # Cactus
	12: (None, 0, 0.1, 12),        # Dead Bush
	13: ("sword", 0, 0.2, 13),     # Leaves
	16: ("pickaxe", 1, 2.2, 121),  # Coal Ore -> drops Coal item (121)
	17: ("pickaxe", 2, 2.5, 17),   # Iron Ore -> drops Iron Ore block (17)
	18: ("pickaxe", 3, 3.0, 122),  # Diamond Ore -> drops Diamond item (122)
	21: (None, 99, 0.3, None),     # Glass (Breaks with no drop)
	22: ("pickaxe", 1, 1.8, 22),   # Bricks (Requires Wood Pickaxe+)
	23: ("axe", 0, 1.2, 216),       # Bookshelf (Drops 3 Books 216)
	24: ("pickaxe", 4, 9.0, 24),   # Obsidian (Requires Diamond Pickaxe!)
	25: (None, 0, 0.4, 25),        # TNT
	26: ("axe", 0, 1.5, 26),       # Crafting Table
	27: ("pickaxe", 1, 2.2, 27),   # Furnace (Requires Wood Pickaxe+)
	28: ("pickaxe", 3, 2.5, 28),   # Gold Block (Requires Iron Pickaxe+)
	29: ("pickaxe", 2, 2.5, 29),   # Iron Block (Requires Stone Pickaxe+)
	30: ("pickaxe", 3, 3.0, 30),   # Diamond Block (Requires Iron Pickaxe+)
	31: ("shovel", 0, 0.3, 31),    # Snow
	32: ("pickaxe", 0, 0.5, 32),    # Ice
	33: (None, 0, 0.1, 33),        # Yellow Flower
	34: (None, 0, 0.5, 34),        # Sponge
	35: ("pickaxe", 3, 2.5, 35),   # Gold Ore -> drops Gold Ore block (35)
	36: ("pickaxe", 3, 2.5, 36),   # Redstone Ore (Requires Iron Pickaxe+)
	37: ("axe", 0, 1.5, 37),       # Chest
	# Non-Cube Blocks (38-53)
	38: ("axe", 0, 0.4, 38),       # Oak Slab
	39: ("pickaxe", 1, 1.0, 39),   # Cobblestone Slab
	40: ("pickaxe", 1, 1.0, 40),   # Stone Slab
	41: ("axe", 0, 0.6, 41),       # Oak Stairs
	42: ("pickaxe", 1, 1.2, 42),   # Cobblestone Stairs
	43: ("axe", 0, 0.6, 43),       # Oak Door (Closed)
	44: ("axe", 0, 0.6, 43),       # Oak Door (Open drops Closed item 43)
	45: ("pickaxe", 1, 1.5, 45),   # Iron Door (Closed)
	46: ("pickaxe", 1, 1.5, 45),   # Iron Door (Open drops Closed item 45)
	47: ("axe", 0, 0.6, 47),       # Oak Trapdoor (Closed)
	48: ("axe", 0, 0.6, 47),       # Oak Trapdoor (Open drops Closed item 47)
	49: ("pickaxe", 1, 1.5, 49),   # Iron Trapdoor (Closed)
	50: ("pickaxe", 1, 1.5, 49),   # Iron Trapdoor (Open drops Closed item 49)
	51: ("axe", 0, 0.6, 51),       # Oak Fence
	52: ("pickaxe", 1, 1.2, 52),   # Cobblestone Wall
	53: (None, 0, 0.2, 53),        # Glass Pane
	# Block State Variations (54-74)
	54: ("pickaxe", 1, 2.2, 27),   # Furnace South -> drops Furnace item 27
	55: ("pickaxe", 1, 2.2, 27),   # Furnace West -> drops Furnace item 27
	56: ("pickaxe", 1, 2.2, 27),   # Furnace East -> drops Furnace item 27
	57: ("axe", 0, 1.5, 37),       # Chest South -> drops Chest item 37
	58: ("axe", 0, 1.5, 37),       # Chest West -> drops Chest item 37
	59: ("axe", 0, 1.5, 37),       # Chest East -> drops Chest item 37
	60: ("axe", 0, 1.5, 8),        # Log X-Axis -> drops Log item 8
	61: ("axe", 0, 1.5, 8),        # Log Z-Axis -> drops Log item 8
	62: ("axe", 0, 0.4, 38),       # Oak Top Slab -> drops Oak Slab item 38
	63: ("pickaxe", 1, 1.0, 39),   # Cobblestone Top Slab -> drops Cobblestone Slab item 39
	64: ("pickaxe", 1, 1.0, 40),   # Stone Top Slab -> drops Stone Slab item 40
	65: ("axe", 0, 0.6, 43),       # Oak Door Top -> drops Oak Door item 43
	66: ("axe", 0, 0.6, 43),       # Oak Door Top Open -> drops Oak Door item 43
	67: ("pickaxe", 1, 1.5, 45),   # Iron Door Top -> drops Iron Door item 45
	68: ("pickaxe", 1, 1.5, 45),   # Iron Door Top Open -> drops Iron Door item 45
	69: ("axe", 0, 0.6, 47),       # Oak Trapdoor Top -> drops Oak Trapdoor item 47
	70: ("axe", 0, 0.6, 47),       # Oak Trapdoor Top Open -> drops Oak Trapdoor item 47
	71: ("pickaxe", 1, 1.5, 49),   # Iron Trapdoor Top -> drops Iron Trapdoor item 49
	72: ("pickaxe", 1, 1.5, 49),   # Iron Trapdoor Top Open -> drops Iron Trapdoor item 49
	73: ("axe", 0, 0.6, 41),       # Oak Top Stairs -> drops Oak Stairs item 41
	74: ("pickaxe", 1, 1.2, 42),   # Cobblestone Top Stairs -> drops Cobblestone Stairs item 42
	75: ("axe", 0, 0.6, 75),       # Oak Fence Gate (Closed)
	76: ("axe", 0, 0.6, 75),       # Oak Fence Gate (Open -> drops Closed item 75)
	77: ("shovel", 0, 0.6, 77),    # Gravel (10% Flint drop handled on break)
	80: ("shovel", 0, 0.6, 4),     # Farmland (Drops Dirt)
	81: (None, 0, 0.0, 155),       # Wheat Crops
	83: (None, 0, 0.8, 83),        # White Wool
	84: ("pickaxe", 1, 0.4, 84),   # Netherrack (Requires Wood Pickaxe+)
	85: ("shovel", 0, 0.5, 85),    # Soul Sand
	86: (None, 0, 0.3, 171),       # Glowstone (Drops Glowstone Dust 171)
	87: ("pickaxe", 1, 1.5, 170),  # Nether Quartz Ore (Drops Nether Quartz 170)
	88: (None, 0, 0.0, None),      # Nether Portal X
	89: (None, 0, 0.0, None),      # Nether Portal Z
	90: ("pickaxe", 1, 2.0, 90),   # Nether Brick
	91: ("pickaxe", 1, 2.0, 91),   # Nether Brick Fence
	92: ("pickaxe", 1, 2.0, 92),   # Nether Brick Stairs
	93: ("pickaxe", 1, 2.0, 92),   # Nether Brick Stairs Top -> drops Stairs 92
	94: (None, 0, 0.1, 173),       # Nether Wart Crop -> drops Nether Wart 173
	95: ("pickaxe", 1, 2.0, 95),   # Nether Brick Slab
	156: (None, 0, 0.0, 156),      # Oak Sapling
	181: (None, 0, float('inf'), None), # End Portal Frame (Indestructible)
	182: (None, 0, float('inf'), None), # Filled End Portal Frame (Indestructible)
	183: (None, 0, float('inf'), None), # End Portal (Indestructible)
	204: (None, 0, 0.0, 195),      # Carrot Crops
	205: (None, 0, 0.0, 196),      # Potato Crops
	206: (None, 0, 0.0, 199),      # Pumpkin Stem
	207: (None, 0, 0.0, 200),      # Melon Stem
	208: ("axe", 0, 1.0, 208),     # Pumpkin Block
	209: ("axe", 0, 1.0, 201),     # Melon Block
	210: (None, 0, 0.0, 202),      # Sugar Cane
	212: ("pickaxe", 2, 3.0, 214), # Lapis Lazuli Ore (Requires Stone Pickaxe+, drops Lapis 214)
	213: ("pickaxe", 1, 5.0, 213), # Enchanting Table (Requires Wood Pickaxe+)
	220: (None, 0, 0.3, 219),      # Bed Foot (Drops Bed item 219)
	221: (None, 0, 0.3, 219),      # Bed Head (Drops Bed item 219)
	# Birch Family (222-231, 272)
	222: ("axe", 0, 0.6, 222),      # Birch Planks
	223: ("axe", 0, 1.5, 223),      # Birch Log
	224: (None, 0, 0.2, 225),       # Birch Leaves
	225: (None, 0, 0.0, 225),       # Birch Sapling
	226: ("axe", 0, 0.4, 226),      # Birch Slab
	227: ("axe", 0, 0.6, 227),      # Birch Stairs
	228: ("axe", 0, 0.6, 228),      # Birch Door
	229: ("axe", 0, 0.6, 228),      # Birch Door Top -> drops 228
	230: ("axe", 0, 0.6, 230),      # Birch Trapdoor
	231: ("axe", 0, 0.6, 231),      # Birch Fence
	272: ("axe", 0, 0.6, 272),      # Birch Fence Gate
	# Spruce Family (232-241, 273)
	232: ("axe", 0, 0.6, 232),      # Spruce Planks
	233: ("axe", 0, 1.5, 233),      # Spruce Log
	234: (None, 0, 0.2, 235),       # Spruce Leaves
	235: (None, 0, 0.0, 235),       # Spruce Sapling
	236: ("axe", 0, 0.4, 236),      # Spruce Slab
	237: ("axe", 0, 0.6, 237),      # Spruce Stairs
	238: ("axe", 0, 0.6, 238),      # Spruce Door
	239: ("axe", 0, 0.6, 238),      # Spruce Door Top -> drops 238
	240: ("axe", 0, 0.6, 240),      # Spruce Trapdoor
	241: ("axe", 0, 0.6, 241),      # Spruce Fence
	273: ("axe", 0, 0.6, 273),      # Spruce Fence Gate
	# Jungle Family (242-251, 274)
	242: ("axe", 0, 0.6, 242),      # Jungle Planks
	243: ("axe", 0, 1.5, 243),      # Jungle Log
	244: (None, 0, 0.2, 245),       # Jungle Leaves
	245: (None, 0, 0.0, 245),       # Jungle Sapling
	246: ("axe", 0, 0.4, 246),      # Jungle Slab
	247: ("axe", 0, 0.6, 247),      # Jungle Stairs
	248: ("axe", 0, 0.6, 248),      # Jungle Door
	249: ("axe", 0, 0.6, 248),      # Jungle Door Top -> drops 248
	250: ("axe", 0, 0.6, 250),      # Jungle Trapdoor
	251: ("axe", 0, 0.6, 251),      # Jungle Fence
	274: ("axe", 0, 0.6, 274),      # Jungle Fence Gate
	# Acacia Family (252-261, 275)
	252: ("axe", 0, 0.6, 252),      # Acacia Planks
	253: ("axe", 0, 1.5, 253),      # Acacia Log
	254: (None, 0, 0.2, 255),       # Acacia Leaves
	255: (None, 0, 0.0, 255),       # Acacia Sapling
	256: ("axe", 0, 0.4, 256),      # Acacia Slab
	257: ("axe", 0, 0.6, 257),      # Acacia Stairs
	258: ("axe", 0, 0.6, 258),      # Acacia Door
	259: ("axe", 0, 0.6, 258),      # Acacia Door Top -> drops 258
	260: ("axe", 0, 0.6, 260),      # Acacia Trapdoor
	261: ("axe", 0, 0.6, 261),      # Acacia Fence
	275: ("axe", 0, 0.6, 275),      # Acacia Fence Gate
	# Dark Oak Family (262-271, 276)
	262: ("axe", 0, 0.6, 262),      # Dark Oak Planks
	263: ("axe", 0, 1.5, 263),      # Dark Oak Log
	264: (None, 0, 0.2, 265),       # Dark Oak Leaves
	265: (None, 0, 0.0, 265),       # Dark Oak Sapling
	266: ("axe", 0, 0.4, 266),      # Dark Oak Slab
	267: ("axe", 0, 0.6, 267),      # Dark Oak Stairs
	268: ("axe", 0, 0.6, 268),      # Dark Oak Door
	269: ("axe", 0, 0.6, 268),      # Dark Oak Door Top -> drops 268
	270: ("axe", 0, 0.6, 270),      # Dark Oak Trapdoor
	271: ("axe", 0, 0.6, 271),      # Dark Oak Fence
	276: ("axe", 0, 0.6, 276),      # Dark Oak Fence Gate
	# Biome Terrain & Flora (277-285)
	277: ("pickaxe", 1, 0.8, 277),  # Sandstone (Requires Wood Pickaxe+)
	278: ("shovel", 0, 0.5, 4),     # Podzol (Drops Dirt without Silk Touch)
	279: (None, 0, 0.0, None),      # Fern
	280: ("axe", 0, 0.2, None),     # Vines
	281: ("shovel", 0, 0.4, 281),   # Red Sand
	282: ("pickaxe", 1, 0.5, None), # Packed Ice
	283: (None, 0, 0.0, 283),       # Red Tulip
	284: (None, 0, 0.0, 284),       # Orange Tulip
	285: (None, 0, 0.0, 285),       # Oxeye Daisy
}

# Zero-allocation reusable shape caches for HUD and UI boxes
_box_outer = None
_box_inner = None

def draw_bordered_box(x, y, width, height, border, bg_color, border_color):
	global _box_outer, _box_inner
	if _box_outer is None:
		_box_outer = pyglet.shapes.Rectangle(0, 0, 1, 1, color=(255, 255, 255, 255))
		_box_inner = pyglet.shapes.Rectangle(0, 0, 1, 1, color=(255, 255, 255, 255))

	_box_outer.x = x
	_box_outer.y = y
	_box_outer.width = width
	_box_outer.height = height
	_box_outer.color = border_color
	_box_outer.draw()

	if width > 2 * border and height > 2 * border:
		_box_inner.x = x + border
		_box_inner.y = y + border
		_box_inner.width = width - 2 * border
		_box_inner.height = height - 2 * border
		_box_inner.color = bg_color
		_box_inner.draw()

# Complete Minecraft Java Edition Tool & Armor Max Durabilities
ITEM_MAX_DURABILITIES = {
	# Wooden Tools & Weapons (59 uses)
	101: 59, 105: 59, 109: 59, 113: 59, 190: 59,
	# Stone Tools & Weapons (131 uses)
	102: 131, 106: 131, 110: 131, 114: 131, 191: 131,
	# Iron Tools & Weapons (250 uses)
	103: 250, 107: 250, 111: 250, 115: 250, 192: 250,
	# Diamond Tools & Weapons (1561 uses)
	104: 1561, 108: 1561, 112: 1561, 116: 1561, 194: 1561,
	# Golden Tools & Weapons (32 uses)
	117: 32, 118: 32, 119: 32, 120: 32, 193: 32,
	# Bow (384 uses)
	157: 384,
	# Flint and Steel (64 uses)
	151: 64,
	# Leather Armor: Helmet=55, Chest=80, Leggings=75, Boots=65
	130: 55, 131: 80, 132: 75, 133: 65,
	# Golden Armor: Helmet=77, Chest=112, Leggings=105, Boots=91
	134: 77, 135: 112, 136: 105, 137: 91,
	# Iron Armor: Helmet=165, Chest=240, Leggings=225, Boots=195
	138: 165, 139: 240, 140: 225, 141: 195,
	# Diamond Armor: Helmet=363, Chest=528, Leggings=495, Boots=429
	142: 363, 143: 528, 144: 495, 145: 429,
}

def get_item_max_durability(item_id):
	"""Returns the maximum durability of an item, or 0 if not durable."""
	return ITEM_MAX_DURABILITIES.get(item_id, 0)

def get_slot_damage(slot):
	"""Returns the current damage value of an item (0 = full durability)."""
	if slot and len(slot) > 2 and isinstance(slot[2], dict):
		return int(slot[2].get("damage", 0))
	return 0

def set_slot_damage(slot, damage):
	"""Sets the damage value of an item."""
	if not slot or slot[0] == 0:
		return
	if len(slot) <= 2:
		slot.append({})
	slot[2]["damage"] = max(0, int(damage))

def damage_slot(slot, amount=1, is_armor=False):
	"""Applies durability damage to a slot with Unbreaking checks. Returns True if item broke and was destroyed."""
	if not slot or slot[0] == 0 or slot[1] <= 0:
		return False
	max_dur = get_item_max_durability(slot[0])
	if max_dur <= 0:
		return False

	unb_lvl = enchanting.get_unbreaking_level(slot)
	if unb_lvl > 0 and enchanting.roll_unbreaking_success(unb_lvl, is_armor=is_armor):
		return False

	cur_dmg = get_slot_damage(slot)
	new_dmg = cur_dmg + amount
	if new_dmg >= max_dur:
		slot[0] = 0
		slot[1] = 0
		set_slot_metadata(slot, {})
		return True
	else:
		set_slot_damage(slot, new_dmg)
		return False

def draw_durability_bar(x, y, damage, max_durability, bar_width=28):
	"""Draws a Minecraft-style durability gauge bar under a damaged item icon."""
	if damage <= 0 or max_durability <= 0:
		return
	pct = max(0.0, min(1.0, 1.0 - damage / float(max_durability)))
	fill_w = max(1, int(round(bar_width * pct)))

	# Background dark outline
	pyglet.shapes.Rectangle(x, y, bar_width, 2, color=(0, 0, 0, 240)).draw()

	# Dynamic color from Green -> Yellow -> Red
	if pct >= 0.5:
		r = int(255 * (1.0 - pct) * 2.0)
		g = 255
	else:
		r = 255
		g = int(255 * pct * 2.0)
	b = 30

	pyglet.shapes.Rectangle(x, y, fill_w, 2, color=(r, g, b, 255)).draw()

def get_slot_metadata(slot):
	"""Returns a copy of the metadata dict (enchantments, damage, custom_name) of a slot."""
	if slot and len(slot) > 2 and isinstance(slot[2], dict) and slot[2]:
		return dict(slot[2])
	return {}

def set_slot_metadata(slot, meta):
	"""Sets the full metadata dict on a slot list without sharing object references."""
	if not slot:
		return
	if meta and isinstance(meta, dict):
		new_meta = dict(meta)
		if len(slot) > 2:
			slot[2] = new_meta
		else:
			slot.append(new_meta)
	else:
		if len(slot) > 2:
			del slot[2:]

def copy_slot(slot):
	"""Returns a deep clone of a slot list [item_id, count, metadata_dict] so that dicts are never shared."""
	if not slot:
		return [0, 0]
	if len(slot) > 2 and isinstance(slot[2], dict) and slot[2]:
		return [slot[0], slot[1], dict(slot[2])]
	return [slot[0], slot[1]]

def get_slot_enchantments(slot):
	"""Returns the enchantments dict from a slot list, or empty dict if not enchanted."""
	if slot and len(slot) > 2 and isinstance(slot[2], dict):
		meta = slot[2]
		if "enchants" in meta and isinstance(meta["enchants"], dict):
			return dict(meta["enchants"])
		return {k: v for k, v in meta.items() if k not in ("damage", "custom_name")}
	return {}

def set_slot_enchantments(slot, enchants):
	"""Sets enchantments dict on a slot list, preserving other metadata like damage without in-place mutation aliasing."""
	if not slot:
		return
	dmg = 0
	custom_name = None
	if len(slot) > 2 and isinstance(slot[2], dict):
		dmg = slot[2].get("damage", 0)
		custom_name = slot[2].get("custom_name", None)
	if enchants and isinstance(enchants, dict):
		if dmg == 0 and "damage" in enchants:
			dmg = enchants.get("damage", 0)
		if custom_name is None and "custom_name" in enchants:
			custom_name = enchants.get("custom_name", None)

	new_meta = {}
	if enchants and isinstance(enchants, dict):
		for k, v in enchants.items():
			if k not in ("damage", "custom_name"):
				new_meta[k] = v
	if dmg > 0:
		new_meta["damage"] = int(dmg)
	if custom_name:
		new_meta["custom_name"] = str(custom_name)

	if new_meta:
		if len(slot) > 2:
			slot[2] = new_meta
		else:
			slot.append(new_meta)
	else:
		if len(slot) > 2:
			del slot[2:]

def is_slot_enchanted(slot):
	"""Returns True if the slot possesses one or more enchantments."""
	return bool(get_slot_enchantments(slot))

def draw_enchanted_glint(sx, sy, size, num_enchants=1):
	"""Draws an authentic Minecraft-style animated sweeping purple glint over an enchanted item."""
	# Sweep diagonally periodically across the item slot (sweep takes ~1.1s)
	t = (time.time() * 0.9) % 1.0
	sweep_x = sx - size * 0.4 + (size * 1.8) * t
	alpha = min(180, int(70 + num_enchants * 30))
	shear = size * 0.55

	try:
		gl.glEnable(gl.GL_SCISSOR_TEST)
		gl.glScissor(int(sx), int(sy), int(size), int(size))

		for off, a_factor, width in [(-6.0, 0.35, 3.0), (0.0, 0.95, 4.5), (6.0, 0.35, 3.0)]:
			cx = sweep_x + off
			col = (190, 70, 255, int(alpha * a_factor))
			p1 = (cx, sy)
			p2 = (cx + width, sy)
			p3 = (cx + width + shear, sy + size)
			p4 = (cx + shear, sy + size)
			poly = pyglet.shapes.Polygon(p1, p2, p3, p4, color=col)
			poly.draw()
	except Exception:
		pass
	finally:
		try:
			gl.glDisable(gl.GL_SCISSOR_TEST)
		except Exception:
			pass

def format_slot_hover(slot, prefix=""):
	"""Formats item tooltip with name, stack count, enchantments, durability, and combat/mining/armor/food stats."""
	if not slot or slot[0] == 0 or slot[1] == 0:
		return f"{prefix}Empty" if prefix else "Empty"
	b_id = slot[0]
	cnt = slot[1]
	b_name = BLOCK_INFO.get(b_id, (f"Item {b_id}", ""))[0]
	lines = [f"{prefix}{b_name} ({cnt})" if prefix else f"{b_name} ({cnt})"]

	enchants = get_slot_enchantments(slot)
	if enchants:
		import enchanting
		for e_key, e_lvl in enchants.items():
			if e_key in enchanting.ENCHANTMENTS:
				e_name = enchanting.ENCHANTMENTS[e_key]["name"]
				e_rom = enchanting.to_roman(e_lvl)
				lines.append(f"  • {e_name} {e_rom}")

	# Durability Breakdown
	max_dur = get_item_max_durability(b_id)
	cur_dmg = get_slot_damage(slot)
	if max_dur > 0:
		rem_dur = max(0, max_dur - cur_dmg)
		lines.append(f"Durability: {rem_dur} / {max_dur}")

	# Stats breakdown
	sharp_lvl = enchants.get("sharpness", 0) if enchants else 0
	eff_lvl = enchants.get("efficiency", 0) if enchants else 0
	power_lvl = enchants.get("power", 0) if enchants else 0
	fire_lvl = enchants.get("fire_aspect", 0) if enchants else 0
	loot_lvl = enchants.get("looting", 0) if enchants else 0
	fort_lvl = enchants.get("fortune", 0) if enchants else 0
	prot_lvl = enchants.get("protection", 0) if enchants else 0
	unb_lvl = enchants.get("unbreaking", 0) if enchants else 0
	has_silk = enchants.get("silk_touch", 0) > 0 if enchants else False
	has_inf = enchants.get("infinity", 0) > 0 if enchants else False

	if unb_lvl > 0:
		pct_mult = unb_lvl * 100
		lines.append(f"Unbreaking: +{pct_mult}% Effective Lifespan")
	if has_silk:
		lines.append("Silk Touch: Drops delicate & ore blocks intact")

	# 1. Swords
	if b_id in (113, 114, 115, 116, 120):
		base_dmg = get_item_attack_damage(b_id)
		bonus_dmg = (0.5 * sharp_lvl + 0.5) if sharp_lvl > 0 else 0.0
		total_dmg = base_dmg + bonus_dmg
		if sharp_lvl > 0:
			lines.append(f"Attack Damage: {total_dmg:.1f} ({base_dmg:.1f} + {bonus_dmg:.1f} Sharpness)")
		else:
			lines.append(f"Attack Damage: {base_dmg:.1f}")

		if fire_lvl > 0:
			lines.append(f"Fire Aspect: Sets target ablaze for {4.0 * fire_lvl:.0f}s")
		if loot_lvl > 0:
			lines.append(f"Looting: +{loot_lvl} Max Mob Drops")

	# 2. Bow
	elif b_id == 157:
		base_dmg = 9.0
		if power_lvl > 0:
			power_mult = 1.0 + 0.25 * (power_lvl + 1)
			total_dmg = base_dmg * power_mult
			pct = int(0.25 * (power_lvl + 1) * 100)
			lines.append(f"Max Arrow Damage: {total_dmg:.1f} (+{pct}% Power)")
		else:
			lines.append("Max Arrow Damage: 9.0")
		if has_inf:
			lines.append("Infinity: Unlimited Normal Arrows")

	# 3. Pickaxes
	elif b_id in (101, 102, 103, 104, 117):
		tier_names = {1: "Wood", 2: "Stone", 3: "Iron", 4: "Diamond", 5: "Gold"}
		cat, tier, base_speed = TOOL_PROPERTIES.get(b_id, ("pickaxe", 1, 2.0))
		eff_mult = (1.0 + (eff_lvl * eff_lvl + 1) * 0.25) if eff_lvl > 0 else 1.0
		total_speed = base_speed * eff_mult
		if eff_lvl > 0:
			lines.append(f"Mining Speed: {total_speed:.1f}x ({base_speed:.1f}x + Efficiency)")
		else:
			lines.append(f"Mining Speed: {base_speed:.1f}x")
		lines.append(f"Harvest Level: {tier_names.get(tier, 'Wood')}+")
		if fort_lvl > 0:
			lines.append(f"Fortune: Up to {fort_lvl + 1}x Ore Drops")

	# 4. Axes
	elif b_id in (105, 106, 107, 108, 118):
		base_dmg = get_item_attack_damage(b_id)
		bonus_dmg = (0.5 * sharp_lvl + 0.5) if sharp_lvl > 0 else 0.0
		total_dmg = base_dmg + bonus_dmg
		cat, tier, base_speed = TOOL_PROPERTIES.get(b_id, ("axe", 1, 2.0))
		eff_mult = (1.0 + (eff_lvl * eff_lvl + 1) * 0.25) if eff_lvl > 0 else 1.0
		total_speed = base_speed * eff_mult

		if sharp_lvl > 0:
			lines.append(f"Attack Damage: {total_dmg:.1f} ({base_dmg:.1f} + {bonus_dmg:.1f} Sharpness)")
		else:
			lines.append(f"Attack Damage: {base_dmg:.1f}")

		if eff_lvl > 0:
			lines.append(f"Chopping Speed: {total_speed:.1f}x ({base_speed:.1f}x + Efficiency)")
		else:
			lines.append(f"Chopping Speed: {base_speed:.1f}x")
		if fort_lvl > 0:
			lines.append(f"Fortune: Up to {fort_lvl + 1}x Drop Yield")

	# 5. Shovels
	elif b_id in (109, 110, 111, 112, 119):
		cat, tier, base_speed = TOOL_PROPERTIES.get(b_id, ("shovel", 1, 2.0))
		eff_mult = (1.0 + (eff_lvl * eff_lvl + 1) * 0.25) if eff_lvl > 0 else 1.0
		total_speed = base_speed * eff_mult
		if eff_lvl > 0:
			lines.append(f"Digging Speed: {total_speed:.1f}x ({base_speed:.1f}x + Efficiency)")
		else:
			lines.append(f"Digging Speed: {base_speed:.1f}x")
		if fort_lvl > 0:
			flint_pct = 14 if fort_lvl == 1 else (25 if fort_lvl == 2 else 100)
			lines.append(f"Fortune: {flint_pct}% Flint Chance from Gravel")

	# 6. Hoes
	elif b_id in (190, 191, 192, 193, 194):
		lines.append("Tills Dirt & Grass into Farmland")

	# 7. Armor Pieces
	elif b_id in ARMOR_DEFENSE_POINTS:
		defense_pts = ARMOR_DEFENSE_POINTS.get(b_id, 0)
		pct_reduction = defense_pts * 4.0
		lines.append(f"Armor Defense: +{defense_pts} (+{pct_reduction:.0f}% Damage Reduction)")
		if prot_lvl > 0:
			prot_pct = prot_lvl * 4.0
			lines.append(f"Protection: +{prot_pct:.0f}% Extra Reduction")

	# 8. Food Items
	elif b_id in FOOD_VALUES:
		hunger, sat, abs_hp = FOOD_VALUES[b_id]
		drumsticks = hunger / 2.0
		info = f"Restores: {hunger} Hunger ({drumsticks:.1f} Drumsticks)"
		if abs_hp > 0:
			info += f" & +{abs_hp / 2.0:.0f} Absorption Hearts"
		lines.append(info)

	# 9. Special Items
	elif b_id == 218:
		lines.append("Throwable: Drops 3–11 Experience Points")
	elif b_id == 176:
		lines.append("Throwable: Teleports on impact (5 self-damage)")
	elif b_id == 177:
		lines.append("Throwable: Locates Stronghold End Portal")
	elif b_id == 211:
		lines.append("Fertilizer: Instantly grows crops and stems")
	elif b_id == 217:
		if not enchants:
			lines.append("Enchanted Book")
	elif b_id == 216:
		lines.append("Can be enchanted at Enchanting Table")
	elif b_id in (219, 220, 221):
		lines.append("Sets respawn point & skips night in Overworld. Explodes in Nether/End!")

	return "\n".join(lines)

# Reusable HUD shapes
_heart_c1 = None
_heart_c2 = None
_heart_tri = None
_heart_in_c1 = None
_heart_in_c2 = None
_heart_in_tri = None
_heart_abs_c1 = None
_heart_abs_c2 = None
_heart_abs_tri = None

def draw_vector_heart(x, y, is_full=True, is_half=False, is_absorption=False):
	global _heart_c1, _heart_c2, _heart_tri, _heart_in_c1, _heart_in_c2, _heart_in_tri, _heart_abs_c1, _heart_abs_c2, _heart_abs_tri
	if _heart_c1 is None:
		_heart_c1 = pyglet.shapes.Circle(0, 0, 4, color=(30, 0, 0, 220))
		_heart_c2 = pyglet.shapes.Circle(0, 0, 4, color=(30, 0, 0, 220))
		_heart_tri = pyglet.shapes.Triangle(0, 0, 0, 0, 0, 0, color=(30, 0, 0, 220))
		_heart_in_c1 = pyglet.shapes.Circle(0, 0, 3, color=(230, 25, 25, 255))
		_heart_in_c2 = pyglet.shapes.Circle(0, 0, 3, color=(230, 25, 25, 255))
		_heart_in_tri = pyglet.shapes.Triangle(0, 0, 0, 0, 0, 0, color=(230, 25, 25, 255))
		_heart_abs_c1 = pyglet.shapes.Circle(0, 0, 3, color=(255, 215, 0, 255))
		_heart_abs_c2 = pyglet.shapes.Circle(0, 0, 3, color=(255, 215, 0, 255))
		_heart_abs_tri = pyglet.shapes.Triangle(0, 0, 0, 0, 0, 0, color=(255, 215, 0, 255))

	in_c1 = _heart_abs_c1 if is_absorption else _heart_in_c1
	in_c2 = _heart_abs_c2 if is_absorption else _heart_in_c2
	in_tri = _heart_abs_tri if is_absorption else _heart_in_tri

	_heart_c1.x, _heart_c1.y = x + 4, y + 10
	_heart_c2.x, _heart_c2.y = x + 11, y + 10
	_heart_tri.x, _heart_tri.y = x, y + 9
	_heart_tri.x2, _heart_tri.y2 = x + 15, y + 9
	_heart_tri.x3, _heart_tri.y3 = x + 7.5, y + 1

	_heart_c1.draw()
	_heart_c2.draw()
	_heart_tri.draw()

	if not is_full and not is_half:
		return

	if is_full:
		in_c1.x, in_c1.y = x + 4, y + 10
		in_c2.x, in_c2.y = x + 11, y + 10
		in_tri.x, in_tri.y = x + 1, y + 9
		in_tri.x2, in_tri.y2 = x + 14, y + 9
		in_tri.x3, in_tri.y3 = x + 7.5, y + 2
		in_c1.draw()
		in_c2.draw()
		in_tri.draw()
	elif is_half:
		in_c1.x, in_c1.y = x + 4, y + 10
		in_tri.x, in_tri.y = x + 1, y + 9
		in_tri.x2, in_tri.y2 = x + 7.5, y + 9
		in_tri.x3, in_tri.y3 = x + 7.5, y + 2
		in_c1.draw()
		in_tri.draw()

_shield_out = None
_shield_out_tri = None
_shield_in = None
_shield_in_tri = None

def draw_vector_shield(x, y, is_full=True, is_half=False):
	global _shield_out, _shield_out_tri, _shield_in, _shield_in_tri
	if _shield_out is None:
		_shield_out = pyglet.shapes.Rectangle(0, 0, 11, 8, color=(40, 45, 55, 230))
		_shield_out_tri = pyglet.shapes.Triangle(0, 0, 0, 0, 0, 0, color=(40, 45, 55, 230))
		_shield_in = pyglet.shapes.Rectangle(0, 0, 7, 6, color=(180, 200, 220, 255))
		_shield_in_tri = pyglet.shapes.Triangle(0, 0, 0, 0, 0, 0, color=(180, 200, 220, 255))

	_shield_out.x, _shield_out.y = x + 2, y + 3
	_shield_out_tri.x, _shield_out_tri.y = x + 2, y + 3
	_shield_out_tri.x2, _shield_out_tri.y2 = x + 13, y + 3
	_shield_out_tri.x3, _shield_out_tri.y3 = x + 7.5, y - 3

	_shield_out.draw()
	_shield_out_tri.draw()

	if not is_full and not is_half:
		return

	if is_full:
		_shield_in.x, _shield_in.y = x + 4, y + 4
		_shield_in.width = 7
		_shield_in_tri.x, _shield_in_tri.y = x + 4, y + 4
		_shield_in_tri.x2, _shield_in_tri.y2 = x + 11, y + 4
		_shield_in_tri.x3, _shield_in_tri.y3 = x + 7.5, y - 1
		_shield_in.draw()
		_shield_in_tri.draw()
	elif is_half:
		_shield_in.x, _shield_in.y = x + 4, y + 4
		_shield_in.width = 3
		_shield_in_tri.x, _shield_in_tri.y = x + 4, y + 4
		_shield_in_tri.x2, _shield_in_tri.y2 = x + 7.5, y + 4
		_shield_in_tri.x3, _shield_in_tri.y3 = x + 7.5, y - 1
		_shield_in.draw()
		_shield_in_tri.draw()

_drum_bone_out = None
_drum_meat_out = None
_drum_bone_in = None
_drum_meat_in = None

def draw_vector_drumstick(x, y, is_full=True, is_half=False):
	global _drum_bone_out, _drum_meat_out, _drum_bone_in, _drum_meat_in
	if _drum_bone_out is None:
		_drum_bone_out = pyglet.shapes.Circle(0, 0, 2.5, color=(45, 30, 15, 230))
		_drum_meat_out = pyglet.shapes.Circle(0, 0, 5.5, color=(45, 30, 15, 230))
		_drum_bone_in = pyglet.shapes.Circle(0, 0, 1.5, color=(235, 225, 210, 255))
		_drum_meat_in = pyglet.shapes.Circle(0, 0, 4.0, color=(190, 95, 35, 255))

	_drum_bone_out.x, _drum_bone_out.y = x + 2, y + 2
	_drum_meat_out.x, _drum_meat_out.y = x + 8, y + 8
	_drum_bone_out.draw()
	_drum_meat_out.draw()

	if not is_full and not is_half:
		return

	_drum_bone_in.x, _drum_bone_in.y = x + 2, y + 2
	_drum_meat_in.x, _drum_meat_in.y = x + 8, y + 8
	_drum_bone_in.draw()
	_drum_meat_in.draw()

_bubble_out = None
_bubble_in = None
_bubble_glint = None
_bubble_pop = None

def draw_vector_bubble(x, y, is_full=True):
	global _bubble_out, _bubble_in, _bubble_glint, _bubble_pop
	if _bubble_out is None:
		_bubble_out = pyglet.shapes.Circle(0, 0, 5.0, color=(10, 40, 85, 230))
		_bubble_in = pyglet.shapes.Circle(0, 0, 3.8, color=(40, 165, 245, 220))
		_bubble_glint = pyglet.shapes.Circle(0, 0, 1.2, color=(255, 255, 255, 240))
		_bubble_pop = pyglet.shapes.Circle(0, 0, 4.5, color=(15, 50, 95, 70))

	cx = x + 7
	cy = y + 7

	if is_full:
		_bubble_out.x, _bubble_out.y = cx, cy
		_bubble_in.x, _bubble_in.y = cx, cy
		_bubble_glint.x, _bubble_glint.y = cx - 1.2, cy + 1.2
		_bubble_out.draw()
		_bubble_in.draw()
		_bubble_glint.draw()
	else:
		_bubble_pop.x, _bubble_pop.y = cx, cy
		_bubble_pop.draw()

class InventoryGUI:
	def __init__(self, window):
		self.window = window
		self.inventory_open = False
		self.crafting_mode = "2x2"  # "2x2", "3x3", "creative", "furnace", "single_chest", or "double_chest"
		self.active_furnace = None
		self.active_chest1 = None
		self.active_chest2 = None

		# Creative hotbar starts with full stacks of 64
		self.creative_hotbar = [[2, 64], [4, 64], [5, 64], [1, 64], [7, 64], [8, 64], [6, 64], [21, 64], [9, 64]]
		self.creative_search_text = ""
		self.creative_scroll_row = 0
		self.creative_search_focused = False
		
		# Survival hotbar, inventory, & 4 Armor Slots (Helmet, Chestplate, Leggings, Boots)
		self.survival_hotbar = [[0, 0] for _ in range(9)]
		self.survival_inventory = [[0, 0] for _ in range(27)]
		self.armor_slots = [[0, 0] for _ in range(4)]

		# Crafting System Grid (2x2 & 3x3) & Result Slot
		self.crafting_grid_2x2 = [[0, 0] for _ in range(4)]
		self.crafting_grid_3x3 = [[0, 0] for _ in range(9)]
		self.crafting_result = [0, 0]

		# Enchanting Table Slots & State
		self.enchant_item_slot = [0, 0, {}]
		self.enchant_lapis_slot = [0, 0, {}]
		self.enchant_bookshelves = 0
		self.enchant_offers = []
		self.enchant_seed = 0

		self.selected_slot = 0  # 0 to 8
		self.held_stack = None  # [block_id, count] or None

		# Drag Tracking State (Minecraft-style drag & drop)
		self.is_dragging = False
		self.drag_button = None
		self.drag_visited_keys = []
		self.drag_initial_held = None
		self.drag_slot_snapshots = {}

		# Double Click Tracking State
		self.last_left_click_time = 0.0

		self.mouse_x = 0
		self.mouse_y = 0

		self.icon_textures = {}
		self._load_icons()

		self.tooltip_label = pyglet.text.Label(
			"", font_name="Arial", font_size=11,
			x=0, y=0, anchor_x="center", anchor_y="bottom",
			color=(255, 255, 255, 255)
		)

		# Reusable static labels and sprites for zero-allocation rendering
		dummy_img = self.icon_textures.get(1, list(self.icon_textures.values())[0]) if self.icon_textures else pyglet.image.ImageData(1, 1, 'RGBA', b'\x00\x00\x00\x00')
		self.slot_sprite = pyglet.sprite.Sprite(dummy_img)
		self.count_label = pyglet.text.Label("", font_name="Arial", font_size=10, anchor_x="right", anchor_y="bottom", color=(255, 255, 255, 255))
		self.hotbar_num_labels = [pyglet.text.Label(str(i + 1), font_name="Arial", font_size=9, anchor_x="left", anchor_y="top", color=(220, 220, 220, 255)) for i in range(9)]
		self.veil_rect = pyglet.shapes.Rectangle(0, 0, 1, 1, color=(0, 0, 0, 160))
		self.hurt_flash = pyglet.shapes.Rectangle(0, 0, 1, 1, color=(255, 0, 0, 140))
		self.toast_message = ""
		self.toast_timer = 0.0
		self.toast_duration = 3.0
		self.toast_label = pyglet.text.Label("", font_name="Arial", font_size=12, anchor_x="center", anchor_y="center", color=(255, 255, 255, 255))

	def show_message(self, text, duration=3.0):
		"""Displays an on-screen toast notification message at the top of the HUD."""
		import time
		self.toast_message = str(text)
		self.toast_timer = float(duration)
		self.toast_duration = float(duration)
		self._last_toast_draw_time = time.time()

	def get_total_armor_protection(self):
		"""Returns total defense points (0 to 20) provided by currently equipped armor pieces."""
		total_defense = 0
		for slot in self.armor_slots:
			if slot[0] != 0 and slot[1] > 0:
				total_defense += ARMOR_DEFENSE_POINTS.get(slot[0], 0)
		return total_defense

	def damage_armor_slots(self, amount=1):
		"""Applies durability damage across all equipped armor pieces with Unbreaking checks."""
		if getattr(self.window, "flying", False):
			return
		for slot in self.armor_slots:
			if slot[0] != 0 and slot[1] > 0:
				damage_slot(slot, amount=amount, is_armor=True)

	def reset_inventory(self):
		self.survival_hotbar = [[0, 0] for _ in range(9)]
		self.survival_inventory = [[0, 0] for _ in range(27)]
		self.armor_slots = [[0, 0] for _ in range(4)]
		self.creative_hotbar = [[2, 64], [4, 64], [5, 64], [1, 64], [7, 64], [8, 64], [6, 64], [21, 64], [9, 64]]
		self.crafting_grid_2x2 = [[0, 0] for _ in range(4)]
		self.crafting_grid_3x3 = [[0, 0] for _ in range(9)]
		self.crafting_result = [0, 0]
		self.crafting_mode = "2x2"
		self.active_furnace = None
		self.active_chest1 = None
		self.active_chest2 = None
		self.selected_slot = 0
		self.held_stack = None
		self.is_dragging = False
		self.drag_button = None
		self.drag_visited_keys.clear()
		self.drag_initial_held = None
		self.drag_slot_snapshots.clear()
		self.last_left_click_time = 0.0
		self.inventory_open = False
		self.creative_search_text = ""
		self.creative_scroll_row = 0
		self.creative_search_focused = False

	@property
	def active_crafting_grid(self):
		return self.crafting_grid_3x3 if self.crafting_mode == "3x3" else self.crafting_grid_2x2

	def open_crafting_table(self):
		self.crafting_mode = "3x3"
		self.inventory_open = True
		self.window.mouse_captured = False
		self.window.set_exclusive_mouse(False)
		self.evaluate_crafting()

	def open_furnace(self, furnace_data):
		self.active_furnace = furnace_data
		self.crafting_mode = "furnace"
		self.inventory_open = True
		self.window.mouse_captured = False
		self.window.set_exclusive_mouse(False)

	def open_chest(self, pos, world):
		is_double, chest1, chest2 = world.get_chest_info(pos)
		self.active_chest1 = chest1
		self.active_chest2 = chest2
		self.crafting_mode = "double_chest" if is_double else "single_chest"
		self.inventory_open = True
		self.window.mouse_captured = False
		self.window.set_exclusive_mouse(False)

	def open_enchanting_table(self, pos, world):
		import enchanting, random
		self.crafting_mode = "enchanting"
		self.enchant_bookshelves = enchanting.count_valid_bookshelves(pos, world)
		self.enchant_item_slot = [0, 0, {}]
		self.enchant_lapis_slot = [0, 0, {}]
		self.enchant_offers = []
		self.enchant_seed = random.randint(0, 1000000)
		self.inventory_open = True
		self.window.mouse_captured = False
		self.window.set_exclusive_mouse(False)
		self.update_enchantment_offers()

	def update_enchantment_offers(self):
		import enchanting
		if not hasattr(self, "enchant_item_slot") or self.enchant_item_slot[0] == 0 or not enchanting.is_enchantable(self.enchant_item_slot[0]):
			self.enchant_offers = []
			return
		item_id = self.enchant_item_slot[0]
		lvl1, lvl2, lvl3 = enchanting.calculate_enchantment_levels(getattr(self, "enchant_bookshelves", 0), seed=self.enchant_seed)
		o1 = enchanting.generate_enchantment_offer(item_id, 1, lvl1, seed=self.enchant_seed + 1)
		o2 = enchanting.generate_enchantment_offer(item_id, 2, lvl2, seed=self.enchant_seed + 2)
		o3 = enchanting.generate_enchantment_offer(item_id, 3, lvl3, seed=self.enchant_seed + 3)
		self.enchant_offers = [o1, o2, o3]

	def _load_icons(self):
		for b_id, (name, tex_name) in BLOCK_INFO.items():
			img_path = os.path.join("textures", f"{tex_name}.png")
			if os.path.exists(img_path):
				try:
					img = pyglet.image.load(img_path)
					self.icon_textures[b_id] = img
				except Exception:
					pass

		# Load bow pulling animation stages
		self.bow_pulling_textures = []
		for stage in range(3):
			stage_path = os.path.join("textures", "items", f"bow_pulling_{stage}.png")
			if os.path.exists(stage_path):
				try:
					self.bow_pulling_textures.append(pyglet.image.load(stage_path))
				except Exception:
					self.bow_pulling_textures.append(None)
			else:
				self.bow_pulling_textures.append(None)

	@property
	def hotbar_slots(self):
		return self.creative_hotbar if getattr(self.window, "flying", False) else self.survival_hotbar

	def get_current_block_id(self):
		slot = self.hotbar_slots[self.selected_slot]
		return slot[0] if slot[1] > 0 else 0

	def get_current_slot(self):
		return self.hotbar_slots[self.selected_slot]

	def get_total_protection_reduction(self):
		import enchanting
		return enchanting.get_protection_reduction(self.armor_slots)

	def consume_active_item(self):
		if getattr(self.window, "flying", False):
			return  # Creative mode: unlimited placement

		slot = self.hotbar_slots[self.selected_slot]
		if slot[0] != 0 and slot[1] > 0:
			slot[1] -= 1
			if slot[1] == 0:
				slot[0] = 0
				set_slot_metadata(slot, {})

	def consume_item(self, item_id, count=1):
		if getattr(self.window, "flying", False):
			return True

		# Try to consume from active hotbar slot first
		active_slot = self.hotbar_slots[self.selected_slot]
		if active_slot[0] == item_id and active_slot[1] > 0:
			take = min(active_slot[1], count)
			active_slot[1] -= take
			count -= take
			if active_slot[1] == 0:
				active_slot[0] = 0
				set_slot_metadata(active_slot, {})
			if count <= 0:
				return True

		# Search remaining hotbar
		for slot in self.survival_hotbar:
			if slot[0] == item_id and slot[1] > 0:
				take = min(slot[1], count)
				slot[1] -= take
				count -= take
				if slot[1] == 0:
					slot[0] = 0
					set_slot_metadata(slot, {})
				if count <= 0:
					return True

		# Search inventory
		for slot in self.survival_inventory:
			if slot[0] == item_id and slot[1] > 0:
				take = min(slot[1], count)
				slot[1] -= take
				count -= take
				if slot[1] == 0:
					slot[0] = 0
					set_slot_metadata(slot, {})
				if count <= 0:
					return True
		return False

	def add_item_to_inventory(self, item_id, count=1, enchantments=None):
		return self.add_item(item_id, count, enchantments=enchantments)

	def can_add_item(self, block_id, count=1, enchantments=None, metadata=None):
		"""Returns True if the player's inventory has capacity to receive at least part of this item stack."""
		if getattr(self.window, "flying", False) or block_id in (0, 9, 19, 15, 20, 14):
			return True

		max_stack = get_max_stack_size(block_id)
		final_meta = {}
		if metadata and isinstance(metadata, dict):
			final_meta.update(metadata)
		if enchantments and isinstance(enchantments, dict):
			final_meta.update(enchantments)

		is_special = bool(final_meta)

		if max_stack > 1 and not is_special:
			for slot in self.survival_hotbar:
				if slot[0] == block_id and slot[1] < max_stack and not is_slot_enchanted(slot) and not get_slot_damage(slot):
					return True
			for slot in self.survival_inventory:
				if slot[0] == block_id and slot[1] < max_stack and not is_slot_enchanted(slot) and not get_slot_damage(slot):
					return True

		for slot in self.survival_hotbar:
			if slot[0] == 0 or slot[1] == 0:
				return True
		for slot in self.survival_inventory:
			if slot[0] == 0 or slot[1] == 0:
				return True

		return False

	def add_item(self, block_id, count=1, enchantments=None, metadata=None):
		if getattr(self.window, "flying", False) or block_id in (0, 9, 19, 15, 20, 14):
			return True

		max_stack = get_max_stack_size(block_id)
		final_meta = {}
		if metadata and isinstance(metadata, dict):
			final_meta.update(metadata)
		if enchantments and isinstance(enchantments, dict):
			final_meta.update(enchantments)

		is_special = bool(final_meta)

		if max_stack > 1 and not is_special:
			# 1. Stack into existing hotbar matching non-enchanted slots
			for slot in self.survival_hotbar:
				if slot[0] == block_id and slot[1] < max_stack and not is_slot_enchanted(slot) and not get_slot_damage(slot):
					addable = min(count, max_stack - slot[1])
					slot[1] += addable
					count -= addable
					if count == 0:
						return True

			# 2. Stack into existing inventory matching non-enchanted slots
			for slot in self.survival_inventory:
				if slot[0] == block_id and slot[1] < max_stack and not is_slot_enchanted(slot) and not get_slot_damage(slot):
					addable = min(count, max_stack - slot[1])
					slot[1] += addable
					count -= addable
					if count == 0:
						return True

		# 3. Place into first empty hotbar slot
		for slot in self.survival_hotbar:
			if slot[0] == 0 or slot[1] == 0:
				slot[0] = block_id
				slot[1] = min(count, max_stack)
				set_slot_metadata(slot, final_meta)
				count -= slot[1]
				if count == 0:
					return True

		# 4. Place into first empty inventory slot
		for slot in self.survival_inventory:
			if slot[0] == 0 or slot[1] == 0:
				slot[0] = block_id
				slot[1] = min(count, max_stack)
				set_slot_metadata(slot, final_meta)
				count -= slot[1]
				if count == 0:
					return True

		return count == 0

	def draw_loading_screen(self, progress, status_text="Generating Terrain..."):
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glDisable(gl.GL_CULL_FACE)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		w = self.window.width
		h = self.window.height

		# Dark dirt backdrop (Minecraft dirt background color)
		bg = pyglet.shapes.Rectangle(0, 0, w, h, color=(35, 25, 20, 255))
		bg.draw()

		# Tile dirt texture if available
		if 4 in self.icon_textures:
			img = self.icon_textures[4]
			for bx in range(0, w, 64):
				for by in range(0, h, 64):
					spr = pyglet.sprite.Sprite(img, x=bx, y=by)
					spr.scale_x = 64.0 / img.width
					spr.scale_y = 64.0 / img.height
					spr.color = (60, 50, 45)
					spr.draw()

		# Dark dimming veil
		veil = pyglet.shapes.Rectangle(0, 0, w, h, color=(0, 0, 0, 160))
		veil.draw()

		cx = w // 2
		cy = h // 2

		# Title Header: "Generating World"
		title_lbl = pyglet.text.Label(
			"Generating World", font_name="Arial", font_size=22,
			x=cx, y=cy + 75, anchor_x="center", anchor_y="center",
			color=(255, 215, 0, 255)
		)
		title_lbl.draw()

		# Progress Bar Outer Frame
		bar_w = 400
		bar_h = 24
		pad = 2
		draw_bordered_box(cx - bar_w // 2, cy - bar_h // 2, bar_w, bar_h, pad, (15, 15, 20, 230), (180, 180, 200, 255))

		# Progress Fill (Minecraft Emerald Green)
		pct = max(0.0, min(1.0, progress))
		fill_w = max(1, int((bar_w - 2 * pad) * pct))
		fill_bar = pyglet.shapes.Rectangle(cx - bar_w // 2 + pad, cy - bar_h // 2 + pad, fill_w, bar_h - 2 * pad, color=(80, 210, 90, 255))
		fill_bar.draw()

		# Percentage Text centered on Progress Bar
		pct_text = f"{int(pct * 100)}%"
		pct_lbl = pyglet.text.Label(
			pct_text, font_name="Arial", font_size=11,
			x=cx, y=cy, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		pct_lbl.draw()

		# Status Text below Progress Bar
		stat_lbl = pyglet.text.Label(
			status_text, font_name="Arial", font_size=11,
			x=cx, y=cy - 45, anchor_x="center", anchor_y="center",
			color=(200, 200, 220, 255)
		)
		# Status Text below Progress Bar
		stat_lbl = pyglet.text.Label(
			status_text, font_name="Arial", font_size=11,
			x=cx, y=cy - 45, anchor_x="center", anchor_y="center",
			color=(200, 200, 220, 255)
		)
		stat_lbl.draw()

	def serialize_inventory(self):
		return {
			'hotbar': [copy_slot(slot) for slot in self.survival_hotbar],
			'inventory': [copy_slot(slot) for slot in self.survival_inventory],
			'creative_hotbar': [copy_slot(slot) for slot in self.creative_hotbar],
			'armor_slots': [copy_slot(slot) for slot in self.armor_slots],
			'crafting_grid_2x2': [copy_slot(slot) for slot in self.crafting_grid_2x2],
			'crafting_grid_3x3': [copy_slot(slot) for slot in self.crafting_grid_3x3],
			'crafting_result': copy_slot(self.crafting_result),
			'selected_slot': self.selected_slot
		}

	def load_inventory_data(self, data):
		if not data:
			return
		if 'hotbar' in data:
			self.survival_hotbar = [copy_slot(slot) for slot in data['hotbar']]
		if 'inventory' in data:
			self.survival_inventory = [copy_slot(slot) for slot in data['inventory']]
		if 'creative_hotbar' in data:
			self.creative_hotbar = [copy_slot(slot) for slot in data['creative_hotbar']]
		if 'armor_slots' in data:
			self.armor_slots = [copy_slot(slot) for slot in data['armor_slots']]
		if 'crafting_grid_2x2' in data:
			self.crafting_grid_2x2 = [copy_slot(slot) for slot in data['crafting_grid_2x2']]
		if 'crafting_grid_3x3' in data:
			self.crafting_grid_3x3 = [copy_slot(slot) for slot in data['crafting_grid_3x3']]
		elif 'crafting_grid' in data and len(data['crafting_grid']) == 9:
			self.crafting_grid_3x3 = [copy_slot(slot) for slot in data['crafting_grid']]
		if 'crafting_result' in data:
			self.crafting_result = copy_slot(data['crafting_result'])
		if 'selected_slot' in data:
			self.selected_slot = data['selected_slot']

	def draw_menu_background(self):
		w = self.window.width
		h = self.window.height

		bg = pyglet.shapes.Rectangle(0, 0, w, h, color=(35, 25, 20, 255))
		bg.draw()

		if 4 in self.icon_textures:
			img = self.icon_textures[4]
			for bx in range(0, w, 64):
				for by in range(0, h, 64):
					spr = pyglet.sprite.Sprite(img, x=bx, y=by)
					spr.scale_x = 64.0 / img.width
					spr.scale_y = 64.0 / img.height
					spr.color = (60, 50, 45)
					spr.draw()

		veil = pyglet.shapes.Rectangle(0, 0, w, h, color=(0, 0, 0, 170))
		veil.draw()

	def draw_main_menu(self, saved_worlds, selected_index=0):
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glDisable(gl.GL_CULL_FACE)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		self.draw_menu_background()

		w = self.window.width
		h = self.window.height
		cx = w // 2
		cy = h // 2

		# Title Header: MINECRAFT CLONE
		title_lbl = pyglet.text.Label(
			"MINECRAFT CLONE", font_name="Arial", font_size=26,
			x=cx, y=h - 45, anchor_x="center", anchor_y="center",
			color=(255, 215, 0, 255)
		)
		title_lbl.draw()

		sub_lbl = pyglet.text.Label(
			"Select Saved World", font_name="Arial", font_size=12,
			x=cx, y=h - 75, anchor_x="center", anchor_y="center",
			color=(200, 200, 220, 255)
		)
		sub_lbl.draw()

		# Saved Worlds List Box (Center Screen)
		list_w = 460
		list_h = 240
		list_y = cy + 20
		draw_bordered_box(cx - list_w // 2, list_y - list_h // 2, list_w, list_h, 2, (15, 15, 20, 230), (140, 140, 160, 255))

		if not saved_worlds:
			no_lbl = pyglet.text.Label(
				"No Saved Worlds Found. Click 'Create New World' below!", font_name="Arial", font_size=11,
				x=cx, y=list_y, anchor_x="center", anchor_y="center",
				color=(180, 180, 190, 255)
			)
			no_lbl.draw()
		else:
			item_h = 52
			start_y = list_y + list_h // 2 - 32
			for idx, w_info in enumerate(saved_worlds[:4]):  # display up to 4 worlds
				item_cy = start_y - idx * (item_h + 4)
				is_sel = (idx == selected_index)

				box_bg = (40, 70, 40, 230) if is_sel else (25, 25, 30, 210)
				border_c = (255, 215, 0, 255) if is_sel else (100, 100, 120, 255)

				draw_bordered_box(cx - (list_w - 20) // 2, item_cy - item_h // 2, list_w - 20, item_h, 2, box_bg, border_c)

				w_name = w_info.get('name', 'New World')
				w_seed = w_info.get('seed', 0)
				w_date = w_info.get('last_played_str', 'Recently')

				name_lbl = pyglet.text.Label(
					w_name, font_name="Arial", font_size=12,
					x=cx - (list_w - 40) // 2, y=item_cy + 10, anchor_x="left", anchor_y="center",
					color=(255, 230, 120, 255) if is_sel else (240, 240, 240, 255)
				)
				name_lbl.draw()

				info_text = f"Seed: {w_seed}  |  Last Played: {w_date}"
				info_lbl = pyglet.text.Label(
					info_text, font_name="Arial", font_size=9,
					x=cx - (list_w - 40) // 2, y=item_cy - 12, anchor_x="left", anchor_y="center",
					color=(170, 170, 190, 255)
				)
				info_lbl.draw()

		# Action Buttons at Bottom
		btn_y = cy - 140
		btn_w = 210
		btn_h = 38

		# Play Selected World
		play_bg = (30, 120, 40, 230) if saved_worlds else (40, 40, 45, 180)
		play_border = (100, 230, 110, 255) if saved_worlds else (80, 80, 90, 255)
		draw_bordered_box(cx - btn_w - 10, btn_y, btn_w, btn_h, 2, play_bg, play_border)
		play_lbl = pyglet.text.Label(
			"Play Selected World", font_name="Arial", font_size=12,
			x=cx - btn_w // 2 - 10, y=btn_y + btn_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255) if saved_worlds else (140, 140, 140, 255)
		)
		play_lbl.draw()

		# Create New World
		draw_bordered_box(cx + 10, btn_y, btn_w, btn_h, 2, (30, 80, 130, 230), (100, 170, 240, 255))
		create_lbl = pyglet.text.Label(
			"Create New World", font_name="Arial", font_size=12,
			x=cx + btn_w // 2 + 10, y=btn_y + btn_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		create_lbl.draw()

		# Secondary Buttons: Rename & Delete
		btn2_y = cy - 190
		btn2_w = 140
		btn2_h = 32

		# Rename World
		ren_bg = (45, 45, 55, 220) if saved_worlds else (40, 40, 45, 180)
		draw_bordered_box(cx - btn2_w - 10, btn2_y, btn2_w, btn2_h, 2, ren_bg, (160, 160, 180, 255))
		ren_lbl = pyglet.text.Label(
			"Rename World", font_name="Arial", font_size=10,
			x=cx - btn2_w // 2 - 10, y=btn2_y + btn2_h // 2, anchor_x="center", anchor_y="center",
			color=(240, 240, 240, 255) if saved_worlds else (140, 140, 140, 255)
		)
		ren_lbl.draw()

		# Delete World
		del_bg = (120, 30, 30, 220) if saved_worlds else (40, 40, 45, 180)
		del_border = (230, 90, 90, 255) if saved_worlds else (80, 80, 90, 255)
		draw_bordered_box(cx + 10, btn2_y, btn2_w, btn2_h, 2, del_bg, del_border)
		del_lbl = pyglet.text.Label(
			"Delete World", font_name="Arial", font_size=10,
			x=cx + btn2_w // 2 + 10, y=btn2_y + btn2_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255) if saved_worlds else (140, 140, 140, 255)
		)
		del_lbl.draw()

	def draw_create_world(self, name_text="", seed_text="", active_field="name"):
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glDisable(gl.GL_CULL_FACE)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		self.draw_menu_background()

		w = self.window.width
		h = self.window.height
		cx = w // 2
		cy = h // 2

		title_lbl = pyglet.text.Label(
			"Create New World", font_name="Arial", font_size=24,
			x=cx, y=cy + 130, anchor_x="center", anchor_y="center",
			color=(255, 215, 0, 255)
		)
		title_lbl.draw()

		# 1. World Name Field
		name_lbl = pyglet.text.Label(
			"World Name (Default: New World):", font_name="Arial", font_size=11,
			x=cx, y=cy + 75, anchor_x="center", anchor_y="center",
			color=(220, 220, 230, 255)
		)
		name_lbl.draw()

		box_w = 340
		box_h = 32
		pad = 2
		is_name_act = (active_field == "name")
		draw_bordered_box(cx - box_w // 2, cy + 30, box_w, box_h, pad, (15, 15, 20, 230), (255, 215, 0, 255) if is_name_act else (140, 140, 160, 255))

		disp_name = (name_text + ("|" if is_name_act else "")) if name_text else ("| New World" if is_name_act else "New World")
		disp_name_lbl = pyglet.text.Label(
			disp_name, font_name="Arial", font_size=12,
			x=cx, y=cy + 30 + box_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255) if name_text else (150, 150, 170, 255)
		)
		disp_name_lbl.draw()

		# 2. Seed Field
		seed_lbl = pyglet.text.Label(
			"World Seed (Leave blank for random seed):", font_name="Arial", font_size=11,
			x=cx, y=cy - 15, anchor_x="center", anchor_y="center",
			color=(220, 220, 230, 255)
		)
		seed_lbl.draw()

		is_seed_act = (active_field == "seed")
		draw_bordered_box(cx - box_w // 2, cy - 60, box_w, box_h, pad, (15, 15, 20, 230), (255, 215, 0, 255) if is_seed_act else (140, 140, 160, 255))

		disp_seed = (seed_text + ("|" if is_seed_act else "")) if seed_text else ("| Random Seed" if is_seed_act else "Random Seed")
		disp_seed_lbl = pyglet.text.Label(
			disp_seed, font_name="Arial", font_size=12,
			x=cx, y=cy - 60 + box_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255) if seed_text else (150, 150, 170, 255)
		)
		disp_seed_lbl.draw()

		# Buttons: Create World & Cancel
		btn_y = cy - 130
		btn1_w = 180
		btn1_h = 38

		# Create
		draw_bordered_box(cx - btn1_w - 10, btn_y, btn1_w, btn1_h, 2, (30, 120, 40, 230), (100, 230, 110, 255))
		create_btn_lbl = pyglet.text.Label(
			"Create World", font_name="Arial", font_size=13,
			x=cx - btn1_w // 2 - 10, y=btn_y + btn1_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		create_btn_lbl.draw()

		# Cancel
		cancel_w = 120
		draw_bordered_box(cx + 10, btn_y, cancel_w, btn1_h, 2, (100, 30, 30, 230), (220, 90, 90, 255))
		cancel_btn_lbl = pyglet.text.Label(
			"Cancel", font_name="Arial", font_size=13,
			x=cx + cancel_w // 2 + 10, y=btn_y + btn1_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		cancel_btn_lbl.draw()

	def draw_rename_world(self, name_text=""):
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glDisable(gl.GL_CULL_FACE)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		self.draw_menu_background()

		w = self.window.width
		h = self.window.height
		cx = w // 2
		cy = h // 2

		title_lbl = pyglet.text.Label(
			"Rename World", font_name="Arial", font_size=24,
			x=cx, y=cy + 90, anchor_x="center", anchor_y="center",
			color=(255, 215, 0, 255)
		)
		title_lbl.draw()

		box_w = 340
		box_h = 34
		draw_bordered_box(cx - box_w // 2, cy + 10, box_w, box_h, 2, (15, 15, 20, 230), (255, 215, 0, 255))

		disp_name = (name_text + "|") if name_text else "|"
		disp_name_lbl = pyglet.text.Label(
			disp_name, font_name="Arial", font_size=13,
			x=cx, y=cy + 10 + box_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		disp_name_lbl.draw()

		btn_y = cy - 60
		btn_w = 160
		btn_h = 38

		# Save Name
		draw_bordered_box(cx - btn_w - 10, btn_y, btn_w, btn_h, 2, (30, 120, 40, 230), (100, 230, 110, 255))
		save_lbl = pyglet.text.Label(
			"Save Name", font_name="Arial", font_size=13,
			x=cx - btn_w // 2 - 10, y=btn_y + btn_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		save_lbl.draw()

		# Cancel
		cancel_w = 120
		draw_bordered_box(cx + 10, btn_y, cancel_w, btn_h, 2, (100, 30, 30, 230), (220, 90, 90, 255))
		cancel_lbl = pyglet.text.Label(
			"Cancel", font_name="Arial", font_size=13,
			x=cx + cancel_w // 2 + 10, y=btn_y + btn_h // 2, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		cancel_lbl.draw()

	def draw_pause_menu(self):
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glDisable(gl.GL_CULL_FACE)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		w = self.window.width
		h = self.window.height
		cx = w // 2
		cy = h // 2

		# Translucent dark veil over 3D world
		veil = pyglet.shapes.Rectangle(0, 0, w, h, color=(0, 0, 0, 175))
		veil.draw()

		title_lbl = pyglet.text.Label(
			"Game Paused", font_name="Arial", font_size=24,
			x=cx, y=cy + 110, anchor_x="center", anchor_y="center",
			color=(255, 215, 0, 255)
		)
		title_lbl.draw()

		btn_w = 240
		btn_h = 40
		pad = 2

		# 1. Back to Game
		b1_y = cy + 30
		draw_bordered_box(cx - btn_w // 2, b1_y - btn_h // 2, btn_w, btn_h, pad, (30, 110, 40, 230), (100, 220, 110, 255))
		lbl1 = pyglet.text.Label(
			"Back to Game", font_name="Arial", font_size=13,
			x=cx, y=b1_y, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		lbl1.draw()

		# 2. Settings
		b2_y = cy - 25
		draw_bordered_box(cx - btn_w // 2, b2_y - btn_h // 2, btn_w, btn_h, pad, (45, 45, 55, 230), (160, 160, 180, 255))
		lbl2 = pyglet.text.Label(
			"Settings", font_name="Arial", font_size=13,
			x=cx, y=b2_y, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		lbl2.draw()

		# 3. Save and Quit to Title
		b3_y = cy - 80
		draw_bordered_box(cx - btn_w // 2, b3_y - btn_h // 2, btn_w, btn_h, pad, (110, 35, 35, 230), (230, 100, 100, 255))
		lbl3 = pyglet.text.Label(
			"Save and Quit to Title", font_name="Arial", font_size=13,
			x=cx, y=b3_y, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		lbl3.draw()

	def draw_settings_menu(self, render_distance=6):
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glDisable(gl.GL_CULL_FACE)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		w = self.window.width
		h = self.window.height
		cx = w // 2
		cy = h // 2

		veil = pyglet.shapes.Rectangle(0, 0, w, h, color=(0, 0, 0, 185))
		veil.draw()

		title_lbl = pyglet.text.Label(
			"Options / Settings", font_name="Arial", font_size=22,
			x=cx, y=cy + 100, anchor_x="center", anchor_y="center",
			color=(255, 215, 0, 255)
		)
		title_lbl.draw()

		# Render Distance Control Box
		ctrl_w = 320
		ctrl_h = 44
		ctrl_y = cy + 20
		draw_bordered_box(cx - ctrl_w // 2, ctrl_y - ctrl_h // 2, ctrl_w, ctrl_h, 2, (20, 20, 25, 230), (140, 140, 160, 255))

		rd_lbl = pyglet.text.Label(
			f"Render Distance:  {render_distance} Chunks", font_name="Arial", font_size=13,
			x=cx, y=ctrl_y, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		rd_lbl.draw()

		# Minus Button
		minus_w = 40
		draw_bordered_box(cx - ctrl_w // 2 - minus_w - 10, ctrl_y - ctrl_h // 2, minus_w, ctrl_h, 2, (45, 45, 55, 230), (180, 180, 200, 255))
		m_lbl = pyglet.text.Label(
			"-", font_name="Arial", font_size=18,
			x=cx - ctrl_w // 2 - minus_w // 2 - 10, y=ctrl_y, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		m_lbl.draw()

		# Plus Button
		plus_w = 40
		draw_bordered_box(cx + ctrl_w // 2 + 10, ctrl_y - ctrl_h // 2, plus_w, ctrl_h, 2, (45, 45, 55, 230), (180, 180, 200, 255))
		p_lbl = pyglet.text.Label(
			"+", font_name="Arial", font_size=18,
			x=cx + ctrl_w // 2 + plus_w // 2 + 10, y=ctrl_y, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		p_lbl.draw()

		# Done Button
		done_w = 180
		done_h = 38
		done_y = cy - 60
		draw_bordered_box(cx - done_w // 2, done_y - done_h // 2, done_w, done_h, 2, (30, 110, 40, 230), (100, 220, 110, 255))
		done_lbl = pyglet.text.Label(
			"Done", font_name="Arial", font_size=13,
			x=cx, y=done_y, anchor_x="center", anchor_y="center",
			color=(255, 255, 255, 255)
		)
		done_lbl.draw()

	def evaluate_crafting(self):
		"""Evaluate active crafting grid (2x2 or 3x3) and set self.crafting_result."""
		grid = self.active_crafting_grid
		grid_dim = 3 if self.crafting_mode == "3x3" else 2

		grid_ids = [slot[0] for slot in grid]
		
		rows = []
		cols = []
		for r in range(grid_dim):
			for c in range(grid_dim):
				if grid_ids[r * grid_dim + c] != 0:
					rows.append(r)
					cols.append(c)

		if not rows:
			self.crafting_result = [0, 0]
			return

		min_r, max_r = min(rows), max(rows)
		min_c, max_c = min(cols), max(cols)

		matrix = []
		for r in range(min_r, max_r + 1):
			row = []
			for c in range(min_c, max_c + 1):
				row.append(grid_ids[r * grid_dim + c])
			matrix.append(row)

		h = len(matrix)
		w = len(matrix[0])

		ALL_PLANKS = (7, 222, 232, 242, 252, 262)
		LOG_TO_PLANKS = {8: 7, 223: 222, 233: 232, 243: 242, 253: 252, 263: 262}
		PLANK_TO_SLAB = {7: 38, 222: 226, 232: 236, 242: 246, 252: 256, 262: 266, 1: 39, 5: 40, 90: 95, 96: 180}
		PLANK_TO_STAIRS = {7: 41, 222: 227, 232: 237, 242: 247, 252: 257, 262: 267, 1: 42, 90: 92, 96: 178}
		PLANK_TO_DOOR = {7: 43, 222: 228, 232: 238, 242: 248, 252: 258, 262: 268}
		PLANK_TO_TRAPDOOR = {7: 47, 222: 230, 232: 240, 242: 250, 252: 260, 262: 270}
		PLANK_TO_FENCE = {7: 51, 222: 231, 232: 241, 242: 251, 252: 261, 262: 271, 90: 91}
		PLANK_TO_GATE = {7: 75, 222: 272, 232: 273, 242: 274, 252: 275, 262: 276}

		# Recipe 1: 1 Log -> 4 Planks
		if h == 1 and w == 1 and matrix[0][0] in LOG_TO_PLANKS:
			self.crafting_result = [LOG_TO_PLANKS[matrix[0][0]], 4]
			return

		# Recipe 2: 2 Planks vertical -> 4 Sticks (100)
		if h == 2 and w == 1 and matrix[0][0] in ALL_PLANKS and matrix[1][0] in ALL_PLANKS:
			self.crafting_result = [100, 4]
			return

		# Recipe 3: 4 Planks 2x2 -> 1 Crafting Table (26)
		if h == 2 and w == 2 and all(matrix[r][c] in ALL_PLANKS for r in range(2) for c in range(2)):
			self.crafting_result = [26, 1]
			return

		# Recipe: Sandstone (4 Sand 6 in 2x2 grid) -> 4 Sandstone (277)
		if h == 2 and w == 2 and matrix == [[6, 6], [6, 6]]:
			self.crafting_result = [277, 4]
			return

		# Recipe 4: Pickaxes (3 top items + 2 vertical sticks) - Requires 3x3 Crafting Table
		if h == 3 and w == 3:
			top = matrix[0]
			center_col = [matrix[0][1], matrix[1][1], matrix[2][1]]
			if center_col[1] == 100 and center_col[2] == 100 and matrix[1][0] == 0 and matrix[1][2] == 0 and matrix[2][0] == 0 and matrix[2][2] == 0:
				mat = top[0]
				if top == [mat, mat, mat] or (all(x in ALL_PLANKS for x in top)):
					if top[0] in ALL_PLANKS and top[1] in ALL_PLANKS and top[2] in ALL_PLANKS: self.crafting_result = [101, 1]; return  # Wood Pickaxe
					if mat in (1, 5): self.crafting_result = [102, 1]; return        # Stone Pickaxe (Cobblestone / Stone)
					if mat in (123, 17, 29): self.crafting_result = [103, 1]; return # Iron Pickaxe (Iron Ingot / Ore / Block)
					if mat in (122, 18, 30): self.crafting_result = [104, 1]; return # Diamond Pickaxe (Diamond / Ore / Block)
					if mat in (124, 35, 28): self.crafting_result = [117, 1]; return # Gold Pickaxe (Gold Ingot / Ore / Block)

		# Recipe 5: Axes (2x3 shape: 3 head items + 2 sticks) - Left or Right Facing
		if h == 3 and w == 2:
			# Left-facing Axe
			mat = matrix[0][0]
			if matrix[1][1] == 100 and matrix[2][1] == 100 and matrix[2][0] == 0:
				heads = [matrix[0][0], matrix[0][1], matrix[1][0]]
				if all(h_item in ALL_PLANKS for h_item in heads):
					self.crafting_result = [105, 1]; return          # Wood Axe
				elif heads[0] == heads[1] == heads[2]:
					if mat in (1, 5): self.crafting_result = [106, 1]; return        # Stone Axe
					if mat in (123, 17, 29): self.crafting_result = [107, 1]; return # Iron Axe
					if mat in (122, 18, 30): self.crafting_result = [108, 1]; return # Diamond Axe
					if mat in (124, 35, 28): self.crafting_result = [118, 1]; return # Gold Axe
			# Right-facing Axe
			mat = matrix[0][1]
			if matrix[1][0] == 100 and matrix[2][0] == 100 and matrix[2][1] == 0:
				heads = [matrix[0][0], matrix[0][1], matrix[1][1]]
				if all(h_item in ALL_PLANKS for h_item in heads):
					self.crafting_result = [105, 1]; return          # Wood Axe
				elif heads[0] == heads[1] == heads[2]:
					if mat in (1, 5): self.crafting_result = [106, 1]; return        # Stone Axe
					if mat in (123, 17, 29): self.crafting_result = [107, 1]; return # Iron Axe
					if mat in (122, 18, 30): self.crafting_result = [108, 1]; return # Diamond Axe
					if mat in (124, 35, 28): self.crafting_result = [118, 1]; return # Gold Axe

		# Recipe 6: Shovels (1x3 shape: 1 head item + 2 sticks) - Requires 3x3 Crafting Table
		if h == 3 and w == 1:
			mat = matrix[0][0]
			if matrix[1][0] == 100 and matrix[2][0] == 100:
				if mat in ALL_PLANKS: self.crafting_result = [109, 1]; return      # Wood Shovel
				if mat in (1, 5): self.crafting_result = [110, 1]; return        # Stone Shovel
				if mat in (123, 17, 29): self.crafting_result = [111, 1]; return # Iron Shovel
				if mat in (122, 18, 30): self.crafting_result = [112, 1]; return # Diamond Shovel
				if mat in (124, 35, 28): self.crafting_result = [119, 1]; return # Gold Shovel

		# Recipe 7: Swords (1x3 shape: 2 blade items + 1 stick) - Requires 3x3 Crafting Table
		if h == 3 and w == 1:
			mat = matrix[0][0]
			if matrix[2][0] == 100:
				if matrix[0][0] in ALL_PLANKS and matrix[1][0] in ALL_PLANKS:
					self.crafting_result = [113, 1]; return      # Wood Sword
				if matrix[0][0] == matrix[1][0]:
					if mat in (1, 5): self.crafting_result = [114, 1]; return        # Stone Sword
					if mat in (123, 17, 29): self.crafting_result = [115, 1]; return # Iron Sword
					if mat in (122, 18, 30): self.crafting_result = [116, 1]; return # Diamond Sword
					if mat in (124, 35, 28): self.crafting_result = [120, 1]; return # Gold Sword

		# Recipe 8: Furnace (8 Cobblestone 3x3 hollow ring) & Chest (8 Planks 3x3 hollow ring)
		if h == 3 and w == 3:
			if matrix[1][1] == 0:
				ring = [matrix[0][0], matrix[0][1], matrix[0][2],
				        matrix[1][0],               matrix[1][2],
				        matrix[2][0], matrix[2][1], matrix[2][2]]
				if ring[0] == 1 and all(x == 1 for x in ring):
					self.crafting_result = [27, 1]; return   # Furnace (27)
				if all(x in ALL_PLANKS for x in ring):
					self.crafting_result = [37, 1]; return   # Chest (37)

		# Recipe 9: Helmets (5 materials in 2x3 top arch: [[M, M, M], [M, 0, M]])
		if h == 2 and w == 3:
			m0 = matrix[0][0]
			if m0 != 0 and m0 == matrix[0][1] == matrix[0][2] == matrix[1][0] == matrix[1][2] and matrix[1][1] == 0:
				if m0 in (126,): self.crafting_result = [130, 1]; return  # Leather Cap
				if m0 in (124, 35, 28): self.crafting_result = [134, 1]; return  # Golden Helmet
				if m0 in (123, 17, 29): self.crafting_result = [138, 1]; return  # Iron Helmet
				if m0 in (122, 18, 30): self.crafting_result = [142, 1]; return  # Diamond Helmet

		# Recipe 10: Boots (4 materials in 2x3 bottom corners: [[M, 0, M], [M, 0, M]])
		if h == 2 and w == 3:
			m0 = matrix[0][0]
			if m0 != 0 and matrix[0][1] == 0 and m0 == matrix[0][2] == matrix[1][0] == matrix[1][2] and matrix[1][1] == 0:
				if m0 in (126,): self.crafting_result = [133, 1]; return  # Leather Boots
				if m0 in (124, 35, 28): self.crafting_result = [137, 1]; return  # Golden Boots
				if m0 in (123, 17, 29): self.crafting_result = [141, 1]; return  # Iron Boots
				if m0 in (122, 18, 30): self.crafting_result = [145, 1]; return  # Diamond Boots

		# Recipe: Bucket (3 Iron Ingots in V-shape: [[M, 0, M], [0, M, 0]]) -> 1 Bucket (147)
		if h == 2 and w == 3:
			m0 = matrix[0][0]
			if m0 in (123, 17, 29) and matrix[0][1] == 0 and matrix[0][2] == m0 and matrix[1][0] == 0 and matrix[1][1] == m0 and matrix[1][2] == 0:
				self.crafting_result = [147, 1]
				return

		# Recipe 11: Chestplates (8 materials in 3x3 hollow neck ring: [[M, 0, M], [M, M, M], [M, M, M]])
		if h == 3 and w == 3:
			m0 = matrix[0][0]
			if m0 != 0 and matrix[0][1] == 0 and m0 == matrix[0][2] == matrix[1][0] == matrix[1][1] == matrix[1][2] == matrix[2][0] == matrix[2][1] == matrix[2][2]:
				if m0 in (126,): self.crafting_result = [131, 1]; return  # Leather Tunic
				if m0 in (124, 35, 28): self.crafting_result = [135, 1]; return  # Golden Chestplate
				if m0 in (123, 17, 29): self.crafting_result = [139, 1]; return  # Iron Chestplate
				if m0 in (122, 18, 30): self.crafting_result = [143, 1]; return  # Diamond Chestplate

		# Recipe 12: Leggings (7 materials in 3x3 upside-down U: [[M, M, M], [M, 0, M], [M, 0, M]])
		if h == 3 and w == 3:
			m0 = matrix[0][0]
			if m0 != 0 and m0 == matrix[0][1] == matrix[0][2] == matrix[1][0] == matrix[1][2] == matrix[2][0] == matrix[2][2] and matrix[1][1] == 0 and matrix[2][1] == 0:
				if m0 in (126,): self.crafting_result = [132, 1]; return  # Leather Pants
				if m0 in (124, 35, 28): self.crafting_result = [136, 1]; return  # Golden Leggings
				if m0 in (123, 17, 29): self.crafting_result = [140, 1]; return  # Iron Leggings
				if m0 in (122, 18, 30): self.crafting_result = [144, 1]; return  # Diamond Leggings

		# Recipe 13: Slabs (3 horizontal matching materials: [[M, M, M]]) -> 6 Slabs
		if h == 1 and w == 3:
			m0 = matrix[0][0]
			if m0 != 0 and m0 == matrix[0][1] == matrix[0][2] and m0 in PLANK_TO_SLAB:
				self.crafting_result = [PLANK_TO_SLAB[m0], 6]
				return

		# Recipe 14: Stairs (6 materials in 3x3 stair shape: [[M, 0, 0], [M, M, 0], [M, M, M]]) -> 4 Stairs
		if h == 3 and w == 3:
			m0 = matrix[0][0]
			if (matrix[0][0] != 0 and matrix[0][0] == matrix[1][0] == matrix[1][1] == matrix[2][0] == matrix[2][1] == matrix[2][2] and matrix[0][1] == 0 and matrix[0][2] == 0 and matrix[1][2] == 0) or \
			   (matrix[0][2] != 0 and matrix[0][2] == matrix[1][1] == matrix[1][2] == matrix[2][0] == matrix[2][1] == matrix[2][2] and matrix[0][0] == 0 and matrix[0][1] == 0 and matrix[1][0] == 0):
				stair_mat = matrix[2][0]
				if stair_mat in PLANK_TO_STAIRS:
					self.crafting_result = [PLANK_TO_STAIRS[stair_mat], 4]
					return

		# Recipe 15: Doors (6 materials in 2x3 vertical rectangle: [[M, M], [M, M], [M, M]]) -> 3 Doors
		if h == 3 and w == 2:
			m0 = matrix[0][0]
			if m0 != 0 and m0 == matrix[0][1] == matrix[1][0] == matrix[1][1] == matrix[2][0] == matrix[2][1]:
				if m0 in PLANK_TO_DOOR: self.crafting_result = [PLANK_TO_DOOR[m0], 3]; return
				if m0 in (123, 17, 29): self.crafting_result = [45, 3]; return  # Iron Door (45)

		# Recipe 16: Trapdoors & Bars (6 materials in 2x3 horizontal rectangle: [[M, M, M], [M, M, M]])
		if h == 2 and w == 3:
			m0 = matrix[0][0]
			if m0 != 0 and m0 == matrix[0][1] == matrix[0][2] == matrix[1][0] == matrix[1][1] == matrix[1][2]:
				if m0 in PLANK_TO_TRAPDOOR: self.crafting_result = [PLANK_TO_TRAPDOOR[m0], 2]; return
				if m0 in (123, 17, 29): self.crafting_result = [99, 16]; return  # Iron Bars (99)
				if m0 == 1: self.crafting_result = [52, 6]; return   # Cobblestone Wall (52)
				if m0 == 21: self.crafting_result = [53, 16]; return # Glass Pane (53)

		# Recipe: Iron Trapdoor (4 Iron Ingots in 2x2 square) -> 1 Iron Trapdoor (49)
		if h == 2 and w == 2 and matrix in ([[123, 123], [123, 123]], [[17, 17], [17, 17]], [[29, 29], [29, 29]]):
			self.crafting_result = [49, 1]  # Iron Trapdoor (49)
			return

		# Recipe 17: Fences (4 Planks + 2 Sticks in 2x3: [[P, 100, P], [P, 100, P]]) -> 3 Fences
		if h == 2 and w == 3:
			p0 = matrix[0][0]
			if p0 in PLANK_TO_FENCE and p0 == matrix[0][2] == matrix[1][0] == matrix[1][2] and matrix[0][1] == 100 and matrix[1][1] == 100:
				self.crafting_result = [PLANK_TO_FENCE[p0], 3]
				return

		# Recipe 18: Fence Gates (4 Sticks + 2 Planks in 2x3: [[100, P, 100], [100, P, 100]]) -> 1 Fence Gate
		if h == 2 and w == 3:
			p0 = matrix[0][1]
			if p0 in PLANK_TO_GATE and p0 == matrix[1][1] and matrix[0][0] == 100 and matrix[0][2] == 100 and matrix[1][0] == 100 and matrix[1][2] == 100:
				self.crafting_result = [PLANK_TO_GATE[p0], 1]
				return

		# Recipe: Bed (3 Wool + 3 Planks: [[83, 83, 83], [P, P, P]]) -> 1 Bed (219)
		if h == 2 and w == 3:
			if matrix[0] == [83, 83, 83] and all(x in ALL_PLANKS or x == 5 for x in matrix[1]):
				self.crafting_result = [219, 1]  # Bed (219)
				return

		# Recipe 19: Flint and Steel (1 Iron Ingot 123 + 1 Flint 146 in any 2-slot arrangement)
		flat_items = [x for row in matrix for x in row if x != 0]
		if sorted(flat_items) == [123, 146]:
			self.crafting_result = [151, 1]  # Flint and Steel (151)
			return

		# Recipe 20: Bow (3 Sticks 100 + 3 Strings 159 in 3x3 crafting grid)
		if h == 3 and w == 3:
			# Right-facing string / Left-facing sticks
			if matrix[0][2] == 159 and matrix[1][2] == 159 and matrix[2][2] == 159:
				if matrix[0][1] == 100 and matrix[1][0] == 100 and matrix[2][1] == 100:
					self.crafting_result = [157, 1]  # Bow (157)
					return
			# Left-facing string / Right-facing sticks
			if matrix[0][0] == 159 and matrix[1][0] == 159 and matrix[2][0] == 159:
				if matrix[0][1] == 100 and matrix[1][2] == 100 and matrix[2][1] == 100:
					self.crafting_result = [157, 1]  # Bow (157)
					return

		# Recipe 21: Arrow (1 Flint 146 + 1 Stick 100 + 1 Feather 160 or Sapling in 1x3 vertical column) -> 4 Arrows
		if h == 3 and w == 1:
			if matrix[0][0] == 146 and matrix[1][0] == 100 and (matrix[2][0] == 160 or matrix[2][0] in (156, 225, 235, 245, 255, 265)):
				self.crafting_result = [158, 4]  # 4 Arrows (158)
				return

		# Recipe 22: Bread (3 Wheat 154 in a 1x3 horizontal row) -> 1 Bread (152)
		if h == 1 and w == 3:
			if matrix[0][0] == 154 and matrix[0][1] == 154 and matrix[0][2] == 154:
				self.crafting_result = [152, 1]  # Bread (152)
				return

		# Recipe 23: Golden Apple (1 Apple 153 in center surrounded by 8 Gold Ingots 124 in 3x3) -> 1 Golden Apple (161)
		if h == 3 and w == 3:
			if matrix[1][1] == 153:
				if all(matrix[r][c] == 124 for r in range(3) for c in range(3) if (r, c) != (1, 1)):
					self.crafting_result = [161, 1]  # Golden Apple (161)
					return

		# Recipe 24: White Wool (4 Strings 159 in 2x2 grid) -> 1 White Wool (83)
		if h == 2 and w == 2:
			if matrix[0][0] == 159 and matrix[0][1] == 159 and matrix[1][0] == 159 and matrix[1][1] == 159:
				self.crafting_result = [83, 1]  # White Wool (83)
				return

		# Recipe 25: TNT (5 Gunpowder 169 + 4 Sand 6/281 in 3x3 X-pattern) -> 1 TNT Block (25)
		if h == 3 and w == 3:
			if (matrix[0][0] == 169 and matrix[0][1] in (6, 281) and matrix[0][2] == 169 and
				matrix[1][0] in (6, 281) and matrix[1][1] == 169 and matrix[1][2] in (6, 281) and
				matrix[2][0] == 169 and matrix[2][1] in (6, 281) and matrix[2][2] == 169):
				self.crafting_result = [25, 1]  # TNT Block (25)
				return

		# Recipe 26: Glowstone (4 Glowstone Dust 171 in 2x2 grid) -> 1 Glowstone Block (86)
		if h == 2 and w == 2:
			if matrix[0][0] == 171 and matrix[0][1] == 171 and matrix[1][0] == 171 and matrix[1][1] == 171:
				self.crafting_result = [86, 1]  # Glowstone (86)
				return

		# Recipe 27: Blaze Powder (1 Blaze Rod 172 in any slot) -> 2 Blaze Powder (175)
		if sorted(flat_items) == [172]:
			self.crafting_result = [175, 2]  # 2 Blaze Powder (175)
			return

		# Recipe 28: Eye of Ender (1 Ender Pearl 176 + 1 Blaze Powder 175 in any 2-slot arrangement) -> 1 Eye of Ender (177)
		if sorted(flat_items) == [175, 176]:
			self.crafting_result = [177, 1]  # 1 Eye of Ender (177)
			return

		# Recipe 29: Stone Bricks (4 Stone 5 in 2x2 grid) -> 4 Stone Bricks (96)
		if h == 2 and w == 2 and matrix == [[5, 5], [5, 5]]:
			self.crafting_result = [96, 4]  # 4 Stone Bricks (96)
			return

		# Recipe 30: Stone Brick Stairs (6 Stone Bricks 96 in 3x3 stairs pattern) -> 4 Stone Brick Stairs (178)
		if h == 3 and w == 3:
			if (matrix[0][0] == 96 and matrix[0][1] == 0 and matrix[0][2] == 0 and
				matrix[1][0] == 96 and matrix[1][1] == 96 and matrix[1][2] == 0 and
				matrix[2][0] == 96 and matrix[2][1] == 96 and matrix[2][2] == 96) or \
			   (matrix[0][0] == 0 and matrix[0][1] == 0 and matrix[0][2] == 96 and
				matrix[1][0] == 0 and matrix[1][1] == 96 and matrix[1][2] == 96 and
				matrix[2][0] == 96 and matrix[2][1] == 96 and matrix[2][2] == 96):
				self.crafting_result = [178, 4]  # 4 Stone Brick Stairs (178)
				return

		# Recipe 31: Stone Brick Slab (3 Stone Bricks 96 in 1x3 horizontal row) -> 6 Stone Brick Slabs (180)
		if h == 1 and w == 3 and matrix[0] == [96, 96, 96]:
			self.crafting_result = [180, 6]  # 6 Stone Brick Slabs (180)
			return

		# Recipe 32: Iron Bars (6 Iron Ingots 123 in 2x3 grid: [[123, 123, 123], [123, 123, 123]]) -> 16 Iron Bars (99)
		if h == 2 and w == 3 and matrix == [[123, 123, 123], [123, 123, 123]]:
			self.crafting_result = [99, 16]  # 16 Iron Bars (99)
			return

		# Recipe 33: Hoes (2 head items + 2 sticks in 2x3 grid) - Left or Right facing
		if h == 3 and w == 2:
			# Left-facing Hoe: [[mat, mat], [0, 100], [0, 100]]
			if matrix[1][0] == 0 and matrix[1][1] == 100 and matrix[2][0] == 0 and matrix[2][1] == 100:
				mat = matrix[0][0]
				if matrix[0][0] in ALL_PLANKS and matrix[0][1] in ALL_PLANKS:
					self.crafting_result = [190, 1]; return      # Wood Hoe
				elif matrix[0][0] == matrix[0][1]:
					if mat in (1, 5): self.crafting_result = [191, 1]; return        # Stone Hoe
					if mat in (123, 17, 29): self.crafting_result = [192, 1]; return # Iron Hoe
					if mat in (122, 18, 30): self.crafting_result = [194, 1]; return # Diamond Hoe
					if mat in (124, 35, 28): self.crafting_result = [193, 1]; return # Gold Hoe
			# Right-facing Hoe: [[mat, mat], [100, 0], [100, 0]]
			if matrix[1][0] == 100 and matrix[1][1] == 0 and matrix[2][0] == 100 and matrix[2][1] == 0:
				mat = matrix[0][0]
				if matrix[0][0] in ALL_PLANKS and matrix[0][1] in ALL_PLANKS:
					self.crafting_result = [190, 1]; return      # Wood Hoe
				elif matrix[0][0] == matrix[0][1]:
					if mat in (1, 5): self.crafting_result = [191, 1]; return        # Stone Hoe
					if mat in (123, 17, 29): self.crafting_result = [192, 1]; return # Iron Hoe
					if mat in (122, 18, 30): self.crafting_result = [194, 1]; return # Diamond Hoe
					if mat in (124, 35, 28): self.crafting_result = [193, 1]; return # Gold Hoe

		# Recipe 34: Bread (3 Wheat 154 in 1x3 horizontal row) -> 1 Bread (152)
		if h == 1 and w == 3 and matrix[0] == [154, 154, 154]:
			self.crafting_result = [152, 1]  # 1 Bread (152)
			return

		# Recipe 35: Pumpkin Seeds (1 Pumpkin Block 208 in any slot) -> 4 Pumpkin Seeds (199)
		if sorted(flat_items) == [208]:
			self.crafting_result = [199, 4]  # 4 Pumpkin Seeds (199)
			return

		# Recipe 36: Melon Slices (1 Melon Block 209 in any slot) -> 9 Melon Slices (201)
		if sorted(flat_items) == [209]:
			self.crafting_result = [201, 9]  # 9 Melon Slices (201)
			return

		# Recipe 37: Melon Block (9 Melon Slices 201 in 3x3 grid) -> 1 Melon Block (209)
		if h == 3 and w == 3 and matrix == [[201, 201, 201], [201, 201, 201], [201, 201, 201]]:
			self.crafting_result = [209, 1]  # 1 Melon Block (209)
			return

		# Recipe 38: Melon Seed (1 Melon Slice 201 in any slot) -> 1 Melon Seed (200)
		if sorted(flat_items) == [201]:
			self.crafting_result = [200, 1]  # 1 Melon Seed (200)
			return

		# Recipe 39: Sugar (1 Sugar Cane 202 in any slot) -> 1 Sugar (203)
		if sorted(flat_items) == [202]:
			self.crafting_result = [203, 1]  # 1 Sugar (203)
			return

		# Recipe 40: Bone Meal (1 Bone 167 in any slot) -> 3 Bone Meal (211)
		if sorted(flat_items) == [167]:
			self.crafting_result = [211, 3]  # 3 Bone Meal (211)
			return

		# Recipe 41: Paper (3 Sugar Cane 202 in 1x3 horizontal row) -> 3 Paper (215)
		if h == 1 and w == 3 and matrix[0] == [202, 202, 202]:
			self.crafting_result = [215, 3]  # 3 Paper (215)
			return

		# Recipe 42: Book (3 Paper 215 + 1 Leather 126 shapeless) -> 1 Book (216)
		if sorted(flat_items) == [126, 215, 215, 215]:
			self.crafting_result = [216, 1]  # 1 Book (216)
			return

		# Recipe 43: Enchanting Table (1 Book 216, 2 Diamonds 122, 4 Obsidian 24 in 3x3)
		if h == 3 and w == 3:
			if (matrix[0] == [0, 216, 0] and
				matrix[1] == [122, 24, 122] and
				matrix[2] == [24, 24, 24]):
				self.crafting_result = [213, 1]  # 1 Enchanting Table (213)
				return

		self.crafting_result = [0, 0]

	def set_selected_slot(self, slot_idx):
		if 0 <= slot_idx < 9:
			self.selected_slot = slot_idx
			self.window.holding = self.get_current_block_id()

	def toggle_inventory(self):
		self.inventory_open = not self.inventory_open
		if self.inventory_open:
			self.crafting_mode = "creative" if self.window.flying else "2x2"
			self.creative_search_focused = self.window.flying
			self.window.mouse_captured = False
			self.window.set_exclusive_mouse(False)
			self.evaluate_crafting()
		else:
			self.creative_search_focused = False
			# Return ingredients left in active crafting grids or enchanting table to inventory when closing
			for grid in (self.crafting_grid_2x2, self.crafting_grid_3x3):
				for slot in grid:
					if slot[0] != 0 and slot[1] > 0:
						meta = get_slot_metadata(slot)
						self.add_item(slot[0], slot[1], metadata=meta)
						slot[0] = 0
						slot[1] = 0
						set_slot_metadata(slot, {})
			if hasattr(self, "enchant_item_slot") and self.enchant_item_slot[0] != 0 and self.enchant_item_slot[1] > 0:
				meta = get_slot_metadata(self.enchant_item_slot)
				self.add_item(self.enchant_item_slot[0], self.enchant_item_slot[1], metadata=meta)
				self.enchant_item_slot = [0, 0, {}]
			if hasattr(self, "enchant_lapis_slot") and self.enchant_lapis_slot[0] != 0 and self.enchant_lapis_slot[1] > 0:
				self.add_item(self.enchant_lapis_slot[0], self.enchant_lapis_slot[1])
				self.enchant_lapis_slot = [0, 0, {}]
			self.crafting_result = [0, 0, {}]
			if self.held_stack and self.held_stack[0] != 0 and self.held_stack[1] > 0:
				held_meta = get_slot_metadata(self.held_stack)
				self.add_item(self.held_stack[0], self.held_stack[1], metadata=held_meta)
			self.held_stack = None
			self.active_chest1 = None
			self.active_chest2 = None
			self.window.mouse_captured = True
			self.window.set_exclusive_mouse(True)

	def draw(self):
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glDepthMask(gl.GL_FALSE)
		gl.glDisable(gl.GL_CULL_FACE)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		if self.window.camera.hurt_time > 0:
			alpha = int(140 * (self.window.camera.hurt_time / 0.4))
			self.hurt_flash.width = self.window.width
			self.hurt_flash.height = self.window.height
			self.hurt_flash.color = (255, 0, 0, alpha)
			self.hurt_flash.draw()

		if getattr(self.window.camera, "fire_timer", 0) > 0 and not getattr(self.window, "flying", False):
			import time
			f_alpha = int(55 + 30 * math.sin(time.time() * 14.0))
			draw_bordered_box(0, 0, self.window.width, int(self.window.height * 0.38), 0, (255, 120, 20, f_alpha), (0, 0, 0, 0))

		hover_text = None

		hover_text = self._draw_hotbar(hover_text)

		if not self.window.flying:
			self._draw_health_bar()
			self._draw_armor_bar()
			self._draw_hunger_bar()
			self._draw_bubble_bar()
			self._draw_xp_bar()

		self._draw_boss_bar()

		if self.toast_timer > 0 and self.toast_message:
			self._draw_message_popup()

		if self.inventory_open:
			hover_text = self._draw_inventory_overlay(hover_text)

		if hover_text:
			self._draw_tooltip(hover_text, self.mouse_x, self.mouse_y)

		if self.inventory_open and self.held_stack and self.held_stack[0] in self.icon_textures:
			b_id, cnt = self.held_stack[0], self.held_stack[1]
			img = self.icon_textures[b_id]
			self.slot_sprite.image = img
			self.slot_sprite.x = self.mouse_x - 16
			self.slot_sprite.y = self.mouse_y - 16
			self.slot_sprite.scale_x = 32.0 / img.width
			self.slot_sprite.scale_y = 32.0 / img.height
			self.slot_sprite.draw()

			if is_slot_enchanted(self.held_stack):
				draw_enchanted_glint(self.mouse_x - 16, self.mouse_y - 16, 32, len(get_slot_enchantments(self.held_stack)))

			max_dur = get_item_max_durability(b_id)
			cur_dmg = get_slot_damage(self.held_stack)
			if max_dur > 0 and cur_dmg > 0:
				draw_durability_bar(self.mouse_x - 14, self.mouse_y - 14, cur_dmg, max_dur, bar_width=28)

			if cnt > 1 or not self.window.flying:
				self.count_label.text = str(cnt)
				self.count_label.font_size = 10
				self.count_label.x = self.mouse_x + 14
				self.count_label.y = self.mouse_y - 14
				self.count_label.draw()

		gl.glDepthMask(gl.GL_TRUE)
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_CULL_FACE)
		self.window.shader.use()

	def _draw_health_bar(self):
		slot_size = 44
		padding = 6
		total_w = 9 * slot_size + 8 * padding
		start_x = (self.window.width - total_w) // 2
		start_y = 70

		health = self.window.camera.health

		# 1. Base 10 Health Hearts
		for i in range(10):
			hx = start_x + i * 18
			hy = start_y

			hp_val = i * 2
			if health >= hp_val + 2:
				draw_vector_heart(hx, hy, is_full=True, is_half=False)
			elif health == hp_val + 1:
				draw_vector_heart(hx, hy, is_full=False, is_half=True)
			else:
				draw_vector_heart(hx, hy, is_full=False, is_half=False)

		# 2. Golden Absorption Hearts (Extra yellow hearts that disappear when lost)
		absorption = getattr(self.window.camera, "absorption", 0.0)
		if absorption > 0:
			total_def = self.get_total_armor_protection()
			abs_y = start_y + 18 if total_def <= 0 else start_y + 36
			num_hearts = int(math.ceil(absorption / 2.0))
			for i in range(num_hearts):
				hx = start_x + i * 18
				hy = abs_y
				abs_val = i * 2
				if absorption >= abs_val + 2:
					draw_vector_heart(hx, hy, is_full=True, is_half=False, is_absorption=True)
				elif absorption >= abs_val + 1:
					draw_vector_heart(hx, hy, is_full=False, is_half=True, is_absorption=True)

	def _draw_armor_bar(self):
		total_def = self.get_total_armor_protection()
		if total_def <= 0:
			return

		slot_size = 44
		padding = 6
		total_w = 9 * slot_size + 8 * padding
		start_x = (self.window.width - total_w) // 2
		start_y = 88

		for i in range(10):
			ax = start_x + i * 18
			ay = start_y

			def_val = i * 2
			if total_def >= def_val + 2:
				draw_vector_shield(ax, ay, is_full=True, is_half=False)
			elif total_def == def_val + 1:
				draw_vector_shield(ax, ay, is_full=False, is_half=True)
			else:
				draw_vector_shield(ax, ay, is_full=False, is_half=False)

	def _draw_hunger_bar(self):
		slot_size = 44
		padding = 6
		total_w = 9 * slot_size + 8 * padding
		start_x = (self.window.width + total_w) // 2 - 180
		start_y = 70

		hunger = getattr(self.window.camera, "hunger", 20)

		for i in range(10):
			fx = start_x + (9 - i) * 18
			fy = start_y

			food_val = i * 2
			if hunger >= food_val + 2:
				draw_vector_drumstick(fx, fy, is_full=True, is_half=False)
			elif hunger == food_val + 1:
				draw_vector_drumstick(fx, fy, is_full=False, is_half=True)
			else:
				draw_vector_drumstick(fx, fy, is_full=False, is_half=False)

	def _draw_bubble_bar(self):
		air = getattr(self.window.camera, "air", 10.0)
		head_underwater = getattr(self.window.camera, "is_head_underwater", lambda w: False)(self.window.world)
		if not head_underwater and air >= 10.0:
			return

		slot_size = 44
		padding = 6
		total_w = 9 * slot_size + 8 * padding
		start_x = (self.window.width + total_w) // 2 - 180
		start_y = 88  # Positioned directly above hunger bar (which is at y = 70)

		bubbles_remaining = int(math.ceil(air))  # 0 to 10

		for i in range(10):
			bx = start_x + (9 - i) * 18
			by = start_y

			if i < bubbles_remaining:
				draw_vector_bubble(bx, by, is_full=True)
			else:
				draw_vector_bubble(bx, by, is_full=False)

	def _draw_xp_bar(self):
		slot_size = 44
		padding = 6
		total_w = 9 * slot_size + 8 * padding
		start_x = (self.window.width - total_w) // 2
		start_y = 60
		bar_h = 5

		cam = getattr(self.window, "camera", None)
		if not cam:
			return

		level = getattr(cam, "level", 0)
		xp_prog = getattr(cam, "xp_progress", 0)
		xp_need = getattr(cam, "xp_needed", 7)
		pct = max(0.0, min(1.0, xp_prog / float(max(1, xp_need))))

		# 1. Dark background bar with 1px black outline
		draw_bordered_box(start_x - 1, start_y - 1, total_w + 2, bar_h + 2, 1, (20, 30, 10, 240), (0, 0, 0, 255))

		# 2. Green XP Progress Fill
		fill_w = int(total_w * pct)
		if fill_w > 0:
			draw_bordered_box(start_x, start_y, fill_w, bar_h, 0, (128, 255, 32, 255), (0, 0, 0, 0))
			draw_bordered_box(start_x, start_y + bar_h - 1, fill_w, 1, 0, (195, 255, 110, 255), (0, 0, 0, 0))

		# 3. 1px dark segment lines every 10%
		for notch in range(1, 10):
			nx = start_x + int(total_w * (notch / 10.0))
			draw_bordered_box(nx, start_y, 1, bar_h, 0, (0, 0, 0, 180), (0, 0, 0, 0))

		# 4. Central Level Number Label
		if level > 0:
			txt = str(level)
			cx = self.window.width // 2
			cy = start_y + 4

			if not hasattr(self, "xp_level_label"):
				self.xp_level_label = pyglet.text.Label(
					"", font_name="Arial", font_size=11,
					x=cx, y=cy, anchor_x="center", anchor_y="bottom",
					color=(128, 255, 32, 255)
				)
				self.xp_level_shadow = pyglet.text.Label(
					"", font_name="Arial", font_size=11,
					x=cx, y=cy, anchor_x="center", anchor_y="bottom",
					color=(0, 0, 0, 255)
				)

			self.xp_level_label.text = txt
			self.xp_level_shadow.text = txt

			# Draw 4-way dark outline/shadow for readability
			for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
				self.xp_level_shadow.x = cx + ox
				self.xp_level_shadow.y = cy + oy
				self.xp_level_shadow.draw()

			self.xp_level_label.x = cx
			self.xp_level_label.y = cy
			self.xp_level_label.draw()

	def _draw_boss_bar(self):
		dim = getattr(self.window, "dimension", None)
		if dim is None and hasattr(self.window, "world"):
			dim = getattr(self.window.world, "dimension", None)
		if dim != "end":
			return

		dragon = getattr(self.window, "ender_dragon", None)
		if dragon is None and hasattr(self.window, "world"):
			dragon = getattr(self.window.world, "ender_dragon", None)

		if dragon and not getattr(dragon, "is_dead", False) and getattr(dragon, "health", 0) > 0:
			bar_w = 360
			bar_h = 12
			bar_x = (self.window.width - bar_w) // 2
			bar_y = self.window.height - 38

			# 1. Boss Name Label
			if not hasattr(self, "boss_name_label"):
				self.boss_name_label = pyglet.text.Label(
					"Ender Dragon",
					font_name="Arial",
					font_size=11,
					x=self.window.width // 2,
					y=bar_y + 16,
					anchor_x="center",
					anchor_y="bottom",
					color=(240, 180, 255, 255)
				)
			else:
				self.boss_name_label.x = self.window.width // 2
				self.boss_name_label.y = bar_y + 16

			self.boss_name_label.draw()

			# 2. Outer Bar Border & Background
			draw_bordered_box(bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4, 1, (20, 8, 25, 235), (80, 30, 95, 255))

			# 3. Magenta/Purple Health Fill
			max_hp = getattr(dragon, "max_health", 200)
			fill_pct = max(0.0, min(1.0, dragon.health / float(max_hp)))
			fill_w = int(bar_w * fill_pct)
			if fill_w > 0:
				draw_bordered_box(bar_x, bar_y, fill_w, bar_h, 0, (185, 35, 215, 255), (0, 0, 0, 0))
				draw_bordered_box(bar_x, bar_y + bar_h - 3, fill_w, 2, 0, (230, 120, 255, 255), (0, 0, 0, 0))

			# 4. Notch Segment Dividers (10 segments)
			for notch in range(1, 10):
				nx = bar_x + int(bar_w * (notch / 10.0))
				draw_bordered_box(nx, bar_y, 1, bar_h, 0, (40, 15, 50, 255), (0, 0, 0, 0))

	def _draw_message_popup(self):
		if self.toast_timer <= 0 or not self.toast_message:
			return

		import time
		now = time.time()
		last_t = getattr(self, "_last_toast_draw_time", now)
		dt = max(0.0, min(0.5, now - last_t))
		self._last_toast_draw_time = now
		self.toast_timer = max(0.0, self.toast_timer - dt)

		if self.toast_timer <= 0:
			return

		cx = self.window.width // 2
		cy = self.window.height - 70

		# Fade out alpha in the last 0.5s
		if self.toast_timer < 0.5:
			alpha = int(255 * (self.toast_timer / 0.5))
		else:
			alpha = 255
		alpha = max(10, min(255, alpha))

		if not hasattr(self, "toast_label") or self.toast_label is None:
			self.toast_label = pyglet.text.Label(
				"",
				font_name="Arial",
				font_size=12,
				anchor_x="center",
				anchor_y="center",
				color=(255, 255, 255, 255)
			)

		self.toast_label.text = self.toast_message
		self.toast_label.color = (255, 255, 255, alpha)
		self.toast_label.x = cx
		self.toast_label.y = cy

		pad_x = 16
		pad_y = 8
		bw = self.toast_label.content_width + pad_x * 2
		bh = self.toast_label.content_height + pad_y * 2

		draw_bordered_box(cx - bw // 2, cy - bh // 2, bw, bh, 2, (15, 15, 20, int(alpha * 0.85)), (255, 215, 0, alpha))
		self.toast_label.draw()

	def _draw_tooltip(self, hover_text, mouse_x, mouse_y):
		if not hover_text:
			return

		lines = hover_text.split('\n')
		line_height = 15
		pad_x = 8
		pad_y = 6

		# Calculate max line width
		max_w = 0
		for line in lines:
			self.tooltip_label.text = line
			self.tooltip_label.font_size = 10
			w = self.tooltip_label.content_width
			if w > max_w:
				max_w = w

		tw = int(max_w + pad_x * 2)
		th = int(len(lines) * line_height + pad_y * 2)

		# Position tooltip slightly above & to the right of cursor, clamped within window bounds
		tx = mouse_x + 12
		ty = mouse_y + 12

		if tx + tw > self.window.width - 4:
			tx = mouse_x - tw - 8
		tx = max(4, min(self.window.width - tw - 4, tx))

		if ty + th > self.window.height - 4:
			ty = mouse_y - th - 8
		ty = max(4, min(self.window.height - th - 4, ty))

		# Draw tooltip background with double border
		draw_bordered_box(tx, ty, tw, th, 2, (16, 14, 24, 245), (80, 50, 130, 255))

		# Render lines from top to bottom
		cur_y = ty + th - pad_y - 12
		for idx, line in enumerate(lines):
			if idx == 0:
				color = (255, 220, 100, 255) if ("•" in hover_text or "Enchanted" in line) else (255, 255, 255, 255)
			elif line.startswith("  •"):
				color = (175, 130, 255, 255)  # Enchantment purple/magenta
			elif any(stat in line for stat in ("Damage", "Speed", "Defense", "Reduction", "Restores", "Tier", "Level")):
				color = (130, 225, 150, 255)  # Stat green
			else:
				color = (185, 190, 205, 255)  # Description gray

			self.tooltip_label.text = line
			self.tooltip_label.font_size = 10
			self.tooltip_label.x = tx + pad_x
			self.tooltip_label.y = cur_y
			self.tooltip_label.anchor_x = "left"
			self.tooltip_label.anchor_y = "bottom"
			self.tooltip_label.color = color
			self.tooltip_label.draw()
			cur_y -= line_height

	def _draw_hotbar(self, current_hover):
		slot_size = 44
		padding = 6
		total_w = 9 * slot_size + 8 * padding
		start_x = (self.window.width - total_w) // 2
		start_y = 12

		draw_bordered_box(start_x - 8, start_y - 6, total_w + 16, slot_size + 12, 2, (0, 0, 0, 180), (120, 120, 140, 220))

		for i in range(9):
			sx = start_x + i * (slot_size + padding)
			sy = start_y

			is_selected = (i == self.selected_slot)
			bg_color = (60, 60, 75, 220) if is_selected else (30, 30, 40, 180)
			border_color = (255, 215, 0, 255) if is_selected else (80, 80, 100, 200)
			border_w = 3 if is_selected else 1

			draw_bordered_box(sx, sy, slot_size, slot_size, border_w, bg_color, border_color)

			slot = self.hotbar_slots[i]
			b_id, cnt = slot[0], slot[1]

			if b_id in self.icon_textures and cnt > 0:
				img = self.icon_textures[b_id]
				# Dynamic bow pulling stage texture
				if b_id == 157 and is_selected and getattr(self.window, "bow_charging", False) and hasattr(self, "bow_pulling_textures"):
					charge_ticks = int(getattr(self.window, "bow_charge_time", 0.0) * 20.0)
					stage = 2 if charge_ticks >= 14 else (1 if charge_ticks >= 6 else 0)
					if stage < len(self.bow_pulling_textures) and self.bow_pulling_textures[stage]:
						img = self.bow_pulling_textures[stage]

				self.slot_sprite.image = img
				self.slot_sprite.x = sx + 6
				self.slot_sprite.y = sy + 6
				self.slot_sprite.scale_x = 32.0 / img.width
				self.slot_sprite.scale_y = 32.0 / img.height
				self.slot_sprite.draw()

				# Animated sweeping purple glint for enchanted items
				if is_slot_enchanted(slot):
					draw_enchanted_glint(sx + 6, sy + 6, 32, len(get_slot_enchantments(slot)))

				# Durability gauge bar under damaged tools/armor/weapons
				max_dur = get_item_max_durability(b_id)
				cur_dmg = get_slot_damage(slot)
				if max_dur > 0 and cur_dmg > 0:
					draw_durability_bar(sx + 7, sy + 7, cur_dmg, max_dur, bar_width=30)

				if cnt > 1 or not self.window.flying:
					self.count_label.text = str(cnt)
					self.count_label.font_size = 10
					self.count_label.x = sx + slot_size - 4
					self.count_label.y = sy + 3
					self.count_label.draw()

			num_lbl = self.hotbar_num_labels[i]
			num_lbl.x = sx + 3
			num_lbl.y = sy + slot_size - 2
			num_lbl.draw()

			if sx <= self.mouse_x <= sx + slot_size and sy <= self.mouse_y <= sy + slot_size:
				current_hover = format_slot_hover(slot, f"[{i + 1}] ")

		return current_hover

	def _draw_item_in_slot(self, slot, sx, sy, slot_s):
		if not slot:
			return
		b_id, cnt = slot[0], slot[1]
		if b_id in self.icon_textures and cnt > 0:
			img = self.icon_textures[b_id]
			self.slot_sprite.image = img
			self.slot_sprite.x = sx + 4
			self.slot_sprite.y = sy + 4
			self.slot_sprite.scale_x = 32.0 / img.width
			self.slot_sprite.scale_y = 32.0 / img.height
			self.slot_sprite.draw()

			# Animated sweeping purple glint for enchanted items
			if is_slot_enchanted(slot):
				draw_enchanted_glint(sx + 4, sy + 4, 32, len(get_slot_enchantments(slot)))

			# Durability gauge bar under damaged tools/armor/weapons
			max_dur = get_item_max_durability(b_id)
			cur_dmg = get_slot_damage(slot)
			if max_dur > 0 and cur_dmg > 0:
				draw_durability_bar(sx + 6, sy + 6, cur_dmg, max_dur, bar_width=slot_s - 12)

			if cnt > 1 or not self.window.flying:
				self.count_label.text = str(cnt)
				self.count_label.font_size = 9
				self.count_label.x = sx + slot_s - 3
				self.count_label.y = sy + 2
				self.count_label.draw()

	def _draw_inventory_overlay(self, current_hover):
		self.veil_rect.width = self.window.width
		self.veil_rect.height = self.window.height
		self.veil_rect.draw()

		win_w = 640
		win_h = 540 if self.crafting_mode == "double_chest" else 460
		win_x = (self.window.width - win_w) // 2
		win_y = (self.window.height - win_h) // 2

		draw_bordered_box(win_x, win_y, win_w, win_h, 2, (20, 22, 28, 240), (180, 180, 200, 255))

		if self.window.flying:
			mode_title = "Inventory (Creative Item Palette)"
			sub_text = "Click an item to get a stack of 64."
		elif self.crafting_mode == "single_chest":
			mode_title = "Chest Storage (27 Slots)"
			sub_text = "Click or Shift-Click items to transfer between inventory and chest."
		elif self.crafting_mode == "double_chest":
			mode_title = "Large Chest Storage (54 Slots)"
			sub_text = "Click or Shift-Click items to transfer between inventory and chest."
		elif self.crafting_mode == "furnace":
			mode_title = "Furnace Smelting"
			sub_text = "Place ingredients and fuel to smelt items in real-time."
		elif self.crafting_mode == "3x3":
			mode_title = "Crafting Table (3x3 Grid)"
			sub_text = "Crafting Table: Place items in 3x3 Grid -> Click Result Slot to claim!"
		else:
			mode_title = "Inventory (Survival 2x2 Crafting)"
			sub_text = "Crafting (2x2 Grid): Place items in 2x2 Grid -> Click Result Slot to claim!"

		title = pyglet.text.Label(mode_title, font_name="Arial", font_size=15, x=win_x + 20, y=win_y + win_h - 24, color=(255, 255, 255, 255))
		title.draw()

		sub = pyglet.text.Label(sub_text, font_name="Arial", font_size=9, x=win_x + 20, y=win_y + win_h - 44, color=(170, 170, 190, 255))
		sub.draw()

		slot_s = 40
		pad = 6

		if self.window.flying:
			# Filter items by search text
			if self.creative_search_text.strip():
				query = self.creative_search_text.strip().lower()
				filtered_items = [item for item in ALL_ITEMS if query in item[1].lower()]
			else:
				filtered_items = ALL_ITEMS

			cols = 8
			visible_rows = 5
			total_rows = math.ceil(len(filtered_items) / float(cols)) if filtered_items else 1
			max_scroll = max(0, total_rows - visible_rows)
			self.creative_scroll_row = max(0, min(self.creative_scroll_row, max_scroll))

			# Render Search Box at Top of Creative Menu
			search_x = win_x + 24
			search_y = win_y + win_h - 78
			search_w = 260
			search_h = 24
			is_foc = getattr(self, "creative_search_focused", False)
			border_c = (255, 215, 0, 255) if is_foc else (100, 140, 180, 255)
			draw_bordered_box(search_x, search_y, search_w, search_h, 2 if is_foc else 1, (20, 20, 30, 230), border_c)

			stext = f"Search: {self.creative_search_text}_" if self.creative_search_text else ("Search: (focused)_" if is_foc else "Search: (type to filter)_")
			scol = (255, 255, 255, 255) if self.creative_search_text or is_foc else (150, 150, 170, 200)
			s_lbl = pyglet.text.Label(stext, font_name="Arial", font_size=9, x=search_x + 6, y=search_y + search_h // 2, anchor_x="left", anchor_y="center", color=scol)
			s_lbl.draw()

			cnt_str = f"Items: {len(filtered_items)}"
			c_lbl = pyglet.text.Label(cnt_str, font_name="Arial", font_size=9, x=search_x + search_w + 15, y=search_y + search_h // 2, anchor_x="left", anchor_y="center", color=(180, 180, 200, 255))
			c_lbl.draw()

			grid_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			grid_y = win_y + win_h - 115

			for idx, (b_id, b_name, tex_name) in enumerate(filtered_items):
				row_idx = idx // cols
				r = row_idx - self.creative_scroll_row
				c = idx % cols

				if 0 <= r < visible_rows:
					sx = grid_x + c * (slot_s + pad)
					sy = grid_y - r * (slot_s + pad)

					is_hover = (sx <= self.mouse_x <= sx + slot_s and sy <= self.mouse_y <= sy + slot_s)
					bg_c = (55, 60, 75, 230) if is_hover else (35, 38, 48, 200)
					border_c = (255, 215, 0, 255) if is_hover else (70, 75, 90, 200)

					draw_bordered_box(sx, sy, slot_s, slot_s, 2 if is_hover else 1, bg_c, border_c)

					if b_id in self.icon_textures:
						img = self.icon_textures[b_id]
						spr = pyglet.sprite.Sprite(img, x=sx + 4, y=sy + 4)
						spr.scale_x = 32.0 / img.width
						spr.scale_y = 32.0 / img.height
						spr.draw()
					if is_hover:
						current_hover = format_slot_hover([b_id, 64])

			# Draw Vertical Scrollbar
			if max_scroll > 0:
				sb_x = grid_x + cols * (slot_s + pad) + 4
				sb_y = grid_y - (visible_rows - 1) * (slot_s + pad)
				sb_h = visible_rows * slot_s + (visible_rows - 1) * pad
				sb_w = 8

				# Track background
				pyglet.shapes.Rectangle(sb_x, sb_y, sb_w, sb_h, color=(30, 30, 40, 200)).draw()

				# Thumb
				thumb_h = max(20, int(sb_h * (visible_rows / float(total_rows))))
				scroll_ratio = self.creative_scroll_row / float(max_scroll)
				thumb_y = sb_y + sb_h - thumb_h - int((sb_h - thumb_h) * scroll_ratio)
				pyglet.shapes.Rectangle(sb_x, thumb_y, sb_w, thumb_h, color=(140, 150, 180, 255)).draw()
		elif self.crafting_mode == "furnace" and self.active_furnace:
			furn_lbl = pyglet.text.Label("Furnace Smelting:", font_name="Arial", font_size=10, x=win_x + 24, y=win_y + win_h - 68, color=(220, 220, 240, 255))
			furn_lbl.draw()

			f_x = win_x + 80
			f_y = win_y + win_h - 180

			# Slot Labels
			in_lbl = pyglet.text.Label("Ingredient", font_name="Arial", font_size=9, x=f_x, y=f_y + 105, color=(180, 180, 200, 255))
			in_lbl.draw()
			fuel_lbl = pyglet.text.Label("Fuel", font_name="Arial", font_size=9, x=f_x, y=f_y - 15, color=(180, 180, 200, 255))
			fuel_lbl.draw()

			# 1. Input Slot
			is_h_in = (f_x <= self.mouse_x <= f_x + slot_s and f_y + 60 <= self.mouse_y <= f_y + 60 + slot_s)
			draw_bordered_box(f_x, f_y + 60, slot_s, slot_s, 2 if is_h_in else 1, (55, 60, 75, 230) if is_h_in else (35, 38, 48, 200), (255, 215, 0, 255) if is_h_in else (70, 75, 90, 200))
			self._draw_item_in_slot(self.active_furnace.input_slot, f_x, f_y + 60, slot_s)

			# 2. Fuel Slot
			is_h_fuel = (f_x <= self.mouse_x <= f_x + slot_s and f_y <= self.mouse_y <= f_y + slot_s)
			draw_bordered_box(f_x, f_y, slot_s, slot_s, 2 if is_h_fuel else 1, (55, 60, 75, 230) if is_h_fuel else (35, 38, 48, 200), (255, 215, 0, 255) if is_h_fuel else (70, 75, 90, 200))
			self._draw_item_in_slot(self.active_furnace.fuel_slot, f_x, f_y, slot_s)

			# 3. Animated Smelting Flame Icon
			flame_bg = pyglet.shapes.Rectangle(f_x + 12, f_y + 43, 16, 14, color=(40, 40, 50, 255))
			flame_bg.draw()
			if self.active_furnace.is_burning():
				fh = max(2, int(14 * (self.active_furnace.burn_time / max(0.1, self.active_furnace.max_burn_time))))
				flame_fg = pyglet.shapes.Rectangle(f_x + 12, f_y + 43, 16, fh, color=(255, 140, 0, 255))
				flame_fg.draw()

			# 4. Progress Arrow
			arr_bg = pyglet.shapes.Rectangle(f_x + 55, f_y + 32, 55, 16, color=(40, 40, 50, 255))
			arr_bg.draw()
			if self.active_furnace.cook_progress > 0:
				pw = int(55 * (self.active_furnace.cook_progress / 10.0))
				arr_fg = pyglet.shapes.Rectangle(f_x + 55, f_y + 32, pw, 16, color=(50, 205, 50, 255))
				arr_fg.draw()
			arr_lbl = pyglet.text.Label("==>", font_name="Arial", font_size=12, x=f_x + 68, y=f_y + 34, color=(240, 240, 240, 255))
			arr_lbl.draw()

			# 5. Output Result Slot
			res_x = f_x + 130
			res_y = f_y + 22
			is_h_out = (res_x <= self.mouse_x <= res_x + slot_s + 8 and res_y <= self.mouse_y <= res_y + slot_s + 8)
			draw_bordered_box(res_x, res_y, slot_s + 8, slot_s + 8, 2, (75, 80, 100, 240) if is_h_out else (45, 50, 65, 220), (255, 215, 0, 255) if is_h_out else (120, 140, 180, 255))
			self._draw_item_in_slot(self.active_furnace.output_slot, res_x + 4, res_y + 4, slot_s)

			if is_h_in:
				current_hover = format_slot_hover(self.active_furnace.input_slot, "Ingredient: ")
			elif is_h_fuel:
				current_hover = format_slot_hover(self.active_furnace.fuel_slot, "Fuel: ")
			elif is_h_out:
				current_hover = format_slot_hover(self.active_furnace.output_slot, "Smelt Output: ")
		elif self.crafting_mode == "single_chest" and self.active_chest1:
			c_lbl = pyglet.text.Label("Chest Storage (27 Slots):", font_name="Arial", font_size=10, x=win_x + 24, y=win_y + win_h - 68, color=(220, 220, 240, 255))
			c_lbl.draw()

			cols = 9
			c_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			c_y = win_y + win_h - 90

			for idx in range(27):
				r = idx // cols
				c = idx % cols
				sx = c_x + c * (slot_s + pad)
				sy = c_y - r * (slot_s + pad)

				is_h = (sx <= self.mouse_x <= sx + slot_s and sy <= self.mouse_y <= sy + slot_s)
				bg_c = (55, 60, 75, 230) if is_h else (35, 38, 48, 200)
				border_c = (255, 215, 0, 255) if is_h else (70, 75, 90, 200)

				draw_bordered_box(sx, sy, slot_s, slot_s, 2 if is_h else 1, bg_c, border_c)

				slot = self.active_chest1.slots[idx]
				self._draw_item_in_slot(slot, sx, sy, slot_s)

				if is_h:
					current_hover = format_slot_hover(slot, f"Chest Slot {idx + 1}: ")

		elif self.crafting_mode == "double_chest" and self.active_chest1 and self.active_chest2:
			c_lbl = pyglet.text.Label("Large Chest Storage (54 Slots):", font_name="Arial", font_size=10, x=win_x + 24, y=win_y + win_h - 68, color=(220, 220, 240, 255))
			c_lbl.draw()

			cols = 9
			c_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			c_y = win_y + win_h - 75

			for idx in range(54):
				r = idx // cols
				c = idx % cols
				sx = c_x + c * (slot_s + pad)
				sy = c_y - r * (slot_s + pad)

				is_h = (sx <= self.mouse_x <= sx + slot_s and sy <= self.mouse_y <= sy + slot_s)
				bg_c = (55, 60, 75, 230) if is_h else (35, 38, 48, 200)
				border_c = (255, 215, 0, 255) if is_h else (70, 75, 90, 200)

				draw_bordered_box(sx, sy, slot_s, slot_s, 2 if is_h else 1, bg_c, border_c)

				slot = self.active_chest1.slots[idx] if idx < 27 else self.active_chest2.slots[idx - 27]
				self._draw_item_in_slot(slot, sx, sy, slot_s)

				if is_h:
					current_hover = format_slot_hover(slot, f"Large Chest Slot {idx + 1}: ")
		elif self.crafting_mode == "enchanting":
			enc_title = pyglet.text.Label("Enchanting Table", font_name="Arial", font_size=11, x=win_x + 24, y=win_y + win_h - 68, color=(240, 240, 255, 255))
			enc_title.draw()

			bs_info = f"Bookshelf Power: {getattr(self, 'enchant_bookshelves', 0)} / 15"
			bs_lbl = pyglet.text.Label(bs_info, font_name="Arial", font_size=9, x=win_x + 24, y=win_y + win_h - 85, color=(160, 200, 240, 255))
			bs_lbl.draw()

			# Left Side: Target Item Slot & Lapis Slot
			e_x = win_x + 45
			e_y = win_y + win_h - 170

			# Target Item Slot
			is_h_item = (e_x <= self.mouse_x <= e_x + slot_s and e_y <= self.mouse_y <= e_y + slot_s)
			draw_bordered_box(e_x, e_y, slot_s, slot_s, 2 if is_h_item else 1, (50, 55, 70, 230) if is_h_item else (32, 35, 45, 200), (255, 215, 0, 255) if is_h_item else (80, 85, 100, 200))
			self._draw_item_in_slot(getattr(self, "enchant_item_slot", [0, 0, {}]), e_x, e_y, slot_s)

			# Lapis Slot
			l_x = e_x + slot_s + 16
			is_h_lapis = (l_x <= self.mouse_x <= l_x + slot_s and e_y <= self.mouse_y <= e_y + slot_s)
			draw_bordered_box(l_x, e_y, slot_s, slot_s, 2 if is_h_lapis else 1, (30, 45, 80, 230) if is_h_lapis else (20, 25, 45, 200), (60, 140, 255, 255) if is_h_lapis else (40, 70, 130, 200))
			lapis_slot = getattr(self, "enchant_lapis_slot", [0, 0, {}])
			if lapis_slot[0] != 0:
				self._draw_item_in_slot(lapis_slot, l_x, e_y, slot_s)
			elif 214 in self.icon_textures:
				img = self.icon_textures[214]
				self.slot_sprite.image = img
				self.slot_sprite.x = l_x + 4
				self.slot_sprite.y = e_y + 4
				self.slot_sprite.scale_x = 32.0 / img.width
				self.slot_sprite.scale_y = 32.0 / img.height
				self.slot_sprite.opacity = 90
				self.slot_sprite.draw()
				self.slot_sprite.opacity = 255

			# Slot Labels
			item_lbl = pyglet.text.Label("Item", font_name="Arial", font_size=8, x=e_x + slot_s // 2, y=e_y - 12, anchor_x="center", color=(180, 180, 200, 255))
			item_lbl.draw()
			lapis_lbl = pyglet.text.Label("Lapis Lazuli", font_name="Arial", font_size=8, x=l_x + slot_s // 2, y=e_y - 12, anchor_x="center", color=(100, 160, 255, 255))
			lapis_lbl.draw()

			# Right Side: 3 Enchantment Option Bars
			opt_x = win_x + 180
			opt_w = 420
			opt_h = 36
			opt_start_y = win_y + win_h - 110

			player_level = self.window.camera.level if (self.window and hasattr(self.window, "camera") and self.window.camera) else 0
			lapis_count = lapis_slot[1] if lapis_slot[0] == 214 else 0
			offers = getattr(self, "enchant_offers", [])

			for i in range(3):
				opt_y = opt_start_y - i * (opt_h + 8)
				is_h_opt = (opt_x <= self.mouse_x <= opt_x + opt_w and opt_y <= self.mouse_y <= opt_y + opt_h)

				offer = offers[i] if (i < len(offers) and offers[i]) else None
				tier = i + 1

				can_afford = (offer is not None) and (player_level >= offer["req_level"]) and (lapis_count >= tier)

				if not offer:
					# Empty / inactive button state
					draw_bordered_box(opt_x, opt_y, opt_w, opt_h, 1, (25, 28, 35, 180), (50, 55, 65, 200))
					tier_lbl = pyglet.text.Label(f"Choice {tier}", font_name="Arial", font_size=9, x=opt_x + 12, y=opt_y + opt_h // 2, anchor_y="center", color=(80, 85, 95, 255))
					tier_lbl.draw()
				else:
					# Active or Locked option button
					if can_afford:
						bg_c = (40, 60, 45, 240) if is_h_opt else (25, 45, 30, 220)
						border_c = (120, 255, 120, 255) if is_h_opt else (60, 180, 80, 255)
						txt_c = (230, 255, 230, 255)
						lvl_tag_c = (140, 255, 60, 255)
						cost_c = (160, 220, 255, 255)
					else:
						bg_c = (35, 30, 35, 200) if is_h_opt else (28, 26, 30, 180)
						border_c = (100, 70, 70, 200) if is_h_opt else (65, 55, 60, 180)
						txt_c = (140, 130, 140, 255)
						lvl_tag_c = (180, 100, 100, 255)
						cost_c = (120, 120, 140, 255)

					draw_bordered_box(opt_x, opt_y, opt_w, opt_h, 2 if (is_h_opt and can_afford) else 1, bg_c, border_c)

					# Level requirement tag
					tag_str = f"[{offer['req_level']}]"
					tag_lbl = pyglet.text.Label(tag_str, font_name="Arial", font_size=11, x=opt_x + 10, y=opt_y + opt_h // 2, anchor_y="center", color=lvl_tag_c)
					tag_lbl.draw()

					# Enchantment name & rank
					name_lbl = pyglet.text.Label(offer["display"], font_name="Arial", font_size=10, x=opt_x + 55, y=opt_y + opt_h // 2, anchor_y="center", color=txt_c)
					name_lbl.draw()

					# Cost text
					cost_str = f"{tier} Lapis • {tier} Lvl"
					cost_lbl = pyglet.text.Label(cost_str, font_name="Arial", font_size=9, x=opt_x + opt_w - 10, y=opt_y + opt_h // 2, anchor_x="right", anchor_y="center", color=cost_c)
					cost_lbl.draw()

					if is_h_opt:
						if can_afford:
							current_hover = f"Enchant with {offer['display']} (Requires Level {offer['req_level']}; Costs {tier} Lapis & {tier} XP Levels)"
						else:
							current_hover = f"Requires Player Level {offer['req_level']} and {tier} Lapis Lazuli"

			if is_h_item:
				current_hover = format_slot_hover(self.enchant_item_slot, "Target Item: ")
			elif is_h_lapis:
				current_hover = format_slot_hover(lapis_slot, "Lapis Slot: ")
		else:
			grid_dim = 3 if self.crafting_mode == "3x3" else 2
			grid = self.active_crafting_grid

			# Render 4 Armor Slots (Helmet, Chestplate, Leggings, Boots) in 2x2 mode
			if self.crafting_mode == "2x2":
				arm_title = pyglet.text.Label("Armor:", font_name="Arial", font_size=10, x=win_x + 24, y=win_y + win_h - 68, color=(220, 220, 240, 255))
				arm_title.draw()

				arm_x = win_x + 24
				arm_y = win_y + win_h - 90
				arm_names = ["Helmet", "Chestplate", "Leggings", "Boots"]
				arm_outlines = ["HEAD", "CHEST", "LEGS", "FEET"]

				for idx in range(4):
					sy = arm_y - idx * (slot_s + pad)
					is_h = (arm_x <= self.mouse_x <= arm_x + slot_s and sy <= self.mouse_y <= sy + slot_s)
					bg_c = (55, 60, 75, 230) if is_h else (35, 38, 48, 200)
					border_c = (255, 215, 0, 255) if is_h else (90, 90, 120, 200)

					draw_bordered_box(arm_x, sy, slot_s, slot_s, 2 if is_h else 1, bg_c, border_c)

					slot = self.armor_slots[idx]
					b_id = slot[0]

					if b_id in self.icon_textures and slot[1] > 0:
						img = self.icon_textures[b_id]
						spr = pyglet.sprite.Sprite(img, x=arm_x + 4, y=sy + 4)
						spr.scale_x = 32.0 / img.width
						spr.scale_y = 32.0 / img.height
						spr.draw()
					else:
						p_lbl = pyglet.text.Label(arm_outlines[idx], font_name="Arial", font_size=7, x=arm_x + slot_s // 2, y=sy + slot_s // 2, anchor_x="center", anchor_y="center", color=(120, 120, 140, 180))
						p_lbl.draw()

					if is_h:
						current_hover = format_slot_hover(slot, f"{arm_names[idx]}: ")

			grid_title_text = "Crafting Table Grid (3x3):" if self.crafting_mode == "3x3" else "Crafting Grid (2x2):"
			cg_title_x = win_x + 24 if self.crafting_mode == "3x3" else win_x + 140
			craft_lbl = pyglet.text.Label(grid_title_text, font_name="Arial", font_size=10, x=cg_title_x, y=win_y + win_h - 68, color=(220, 220, 240, 255))
			craft_lbl.draw()

			cg_x = win_x + 24 if self.crafting_mode == "3x3" else win_x + 140
			cg_y = win_y + win_h - 180 if self.crafting_mode == "3x3" else win_y + win_h - 160

			for r in range(grid_dim):
				for c in range(grid_dim):
					idx = r * grid_dim + c
					sx = cg_x + c * (slot_s + pad)
					sy = cg_y + (grid_dim - 1 - r) * (slot_s + pad)

					is_h = (sx <= self.mouse_x <= sx + slot_s and sy <= self.mouse_y <= sy + slot_s)
					bg_c = (55, 60, 75, 230) if is_h else (35, 38, 48, 200)
					border_c = (255, 215, 0, 255) if is_h else (70, 75, 90, 200)

					draw_bordered_box(sx, sy, slot_s, slot_s, 2 if is_h else 1, bg_c, border_c)

					slot = grid[idx]
					b_id, cnt = slot[0], slot[1]

					if b_id in self.icon_textures and cnt > 0:
						img = self.icon_textures[b_id]
						spr = pyglet.sprite.Sprite(img, x=sx + 4, y=sy + 4)
						spr.scale_x = 32.0 / img.width
						spr.scale_y = 32.0 / img.height
						spr.draw()

						cnt_lbl = pyglet.text.Label(str(cnt), font_name="Arial", font_size=9, x=sx + slot_s - 3, y=sy + 2, anchor_x="right", anchor_y="bottom", color=(255, 255, 255, 255))
						cnt_lbl.draw()

					if is_h:
						current_hover = format_slot_hover(slot)

			# Arrow -> Result Slot
			arr_x = cg_x + grid_dim * (slot_s + pad) + 10
			arr_y = cg_y + (grid_dim * (slot_s + pad)) // 2 - 10
			arr_lbl = pyglet.text.Label("==>", font_name="Arial", font_size=16, x=arr_x, y=arr_y, color=(255, 215, 0, 255))
			arr_lbl.draw()

			res_x = arr_x + 50
			res_y = arr_y - 12

			is_res_h = (res_x <= self.mouse_x <= res_x + slot_s + 8 and res_y <= self.mouse_y <= res_y + slot_s + 8)
			res_bg = (75, 80, 100, 240) if is_res_h else (45, 50, 65, 220)
			res_border = (255, 215, 0, 255) if is_res_h else (120, 140, 180, 255)

			draw_bordered_box(res_x, res_y, slot_s + 8, slot_s + 8, 2, res_bg, res_border)

			rb_id, rcnt = self.crafting_result[0], self.crafting_result[1]
			if rb_id in self.icon_textures and rcnt > 0:
				img = self.icon_textures[rb_id]
				spr = pyglet.sprite.Sprite(img, x=res_x + 8, y=res_y + 8)
				spr.scale_x = 32.0 / img.width
				spr.scale_y = 32.0 / img.height
				spr.draw()

				cnt_lbl = pyglet.text.Label(str(rcnt), font_name="Arial", font_size=10, x=res_x + slot_s + 4, y=res_y + 3, anchor_x="right", anchor_y="bottom", color=(255, 255, 255, 255))
				cnt_lbl.draw()

			if is_res_h:
				current_hover = format_slot_hover(self.crafting_result, "Craft Result: ")

		if not self.window.flying:
			# Survival 27-slot Storage Grid (9 columns x 3 rows - Bottom Half)
			inv_lbl = pyglet.text.Label("Inventory Storage (27 Slots):", font_name="Arial", font_size=10, x=win_x + 24, y=win_y + 195, color=(220, 220, 240, 255))
			inv_lbl.draw()

			cols = 9
			grid_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			grid_y = win_y + 145

			for idx in range(27):
				r = idx // cols
				c = idx % cols

				sx = grid_x + c * (slot_s + pad)
				sy = grid_y - r * (slot_s + pad)

				is_hover = (sx <= self.mouse_x <= sx + slot_s and sy <= self.mouse_y <= sy + slot_s)
				bg_c = (55, 60, 75, 230) if is_hover else (35, 38, 48, 200)
				border_c = (255, 215, 0, 255) if is_hover else (70, 75, 90, 200)

				draw_bordered_box(sx, sy, slot_s, slot_s, 2 if is_hover else 1, bg_c, border_c)

				slot = self.survival_inventory[idx]
				b_id, cnt = slot[0], slot[1]

				if b_id in self.icon_textures and cnt > 0:
					img = self.icon_textures[b_id]
					spr = pyglet.sprite.Sprite(img, x=sx + 4, y=sy + 4)
					spr.scale_x = 32.0 / img.width
					spr.scale_y = 32.0 / img.height
					spr.draw()

					cnt_lbl = pyglet.text.Label(str(cnt), font_name="Arial", font_size=9, x=sx + slot_s - 3, y=sy + 2, anchor_x="right", anchor_y="bottom", color=(255, 255, 255, 255))
					cnt_lbl.draw()

				if is_hover:
					current_hover = format_slot_hover(slot)

		# Hotbar Section Title & Grid Row inside Inventory
		hb_title = pyglet.text.Label("Hotbar (Slots 1 - 9):", font_name="Arial", font_size=10, x=win_x + 24, y=win_y + 60, color=(220, 220, 240, 255))
		hb_title.draw()

		hb_x = win_x + (win_w - (9 * slot_s + 8 * pad)) // 2
		hb_y = win_y + 12

		for i in range(9):
			sx = hb_x + i * (slot_s + pad)
			sy = hb_y

			is_sel = (i == self.selected_slot)
			is_h = (sx <= self.mouse_x <= sx + slot_s and sy <= self.mouse_y <= sy + slot_s)

			bg_c = (70, 70, 90, 240) if is_h else ((50, 50, 65, 220) if is_sel else (30, 30, 40, 200))
			border_c = (255, 215, 0, 255) if (is_sel or is_h) else (90, 90, 110, 200)

			draw_bordered_box(sx, sy, slot_s, slot_s, 2 if (is_sel or is_h) else 1, bg_c, border_c)

			slot = self.hotbar_slots[i]
			b_id, cnt = slot[0], slot[1]

			if b_id in self.icon_textures and cnt > 0:
				img = self.icon_textures[b_id]
				spr = pyglet.sprite.Sprite(img, x=sx + 4, y=sy + 4)
				spr.scale_x = 32.0 / img.width
				spr.scale_y = 32.0 / img.height
				spr.draw()

				cnt_lbl = pyglet.text.Label(str(cnt), font_name="Arial", font_size=9, x=sx + slot_s - 3, y=sy + 2, anchor_x="right", anchor_y="bottom", color=(255, 255, 255, 255))
				cnt_lbl.draw()

			num_lbl = pyglet.text.Label(str(i + 1), font_name="Arial", font_size=9, x=sx + 3, y=sy + slot_s - 2, anchor_x="left", anchor_y="top", color=(220, 220, 220, 255))
			num_lbl.draw()

			if is_h:
				current_hover = format_slot_hover(slot, f"Slot {i + 1}: ")

		return current_hover

	def get_slot_at_pos(self, x, y):
		if not self.inventory_open:
			return None

		win_w = 640
		win_h = 540 if self.crafting_mode == "double_chest" else 460
		win_x = (self.window.width - win_w) // 2
		win_y = (self.window.height - win_h) // 2
		slot_s = 40
		pad = 6

		if self.window.flying:
			if self.creative_search_text.strip():
				query = self.creative_search_text.strip().lower()
				filtered_items = [item for item in ALL_ITEMS if query in item[1].lower()]
			else:
				filtered_items = ALL_ITEMS

			cols = 8
			visible_rows = 5
			grid_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			grid_y = win_y + win_h - 115

			for idx, (b_id, b_name, tex_name) in enumerate(filtered_items):
				row_idx = idx // cols
				r = row_idx - self.creative_scroll_row
				c = idx % cols
				if 0 <= r < visible_rows:
					sx = grid_x + c * (slot_s + pad)
					sy = grid_y - r * (slot_s + pad)
					if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
						return ("creative", idx, [b_id, 64])

			hb_x = win_x + (win_w - (9 * slot_s + 8 * pad)) // 2
			hb_y = win_y + 12
			for i in range(9):
				sx = hb_x + i * (slot_s + pad)
				sy = hb_y
				if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
					return ("hotbar", i, self.hotbar_slots[i])

			return None

		if self.crafting_mode == "single_chest" and self.active_chest1:
			cols = 9
			c_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			c_y = win_y + win_h - 90
			for idx in range(27):
				r = idx // cols
				c = idx % cols
				sx = c_x + c * (slot_s + pad)
				sy = c_y - r * (slot_s + pad)
				if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
					return ("chest", idx, self.active_chest1.slots[idx])
		elif self.crafting_mode == "double_chest" and self.active_chest1 and self.active_chest2:
			cols = 9
			c_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			c_y = win_y + win_h - 75
			for idx in range(54):
				r = idx // cols
				c = idx % cols
				sx = c_x + c * (slot_s + pad)
				sy = c_y - r * (slot_s + pad)
				if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
					slot_ref = self.active_chest1.slots[idx] if idx < 27 else self.active_chest2.slots[idx - 27]
					return ("chest", idx, slot_ref)
		elif self.crafting_mode == "furnace" and self.active_furnace:
			f_x = win_x + 80
			f_y = win_y + win_h - 180

			# 1. Input Slot
			if f_x <= x <= f_x + slot_s and f_y + 60 <= y <= f_y + 60 + slot_s:
				return ("furnace_input", 0, self.active_furnace.input_slot)

			# 2. Fuel Slot
			if f_x <= x <= f_x + slot_s and f_y <= y <= f_y + slot_s:
				return ("furnace_fuel", 0, self.active_furnace.fuel_slot)

			# 3. Output Slot
			res_x = f_x + 130
			res_y = f_y + 22
			if res_x <= x <= res_x + slot_s + 8 and res_y <= y <= res_y + slot_s + 8:
				return ("furnace_output", 0, self.active_furnace.output_slot)
		elif self.crafting_mode == "enchanting":
			e_x = win_x + 45
			e_y = win_y + win_h - 170
			l_x = e_x + slot_s + 16
			if e_x <= x <= e_x + slot_s and e_y <= y <= e_y + slot_s:
				return ("enchant_item", 0, self.enchant_item_slot)
			if l_x <= x <= l_x + slot_s and e_y <= y <= e_y + slot_s:
				return ("enchant_lapis", 0, self.enchant_lapis_slot)
		else:
			if self.crafting_mode == "2x2":
				arm_x = win_x + 24
				arm_y = win_y + win_h - 90
				for idx in range(4):
					sy = arm_y - idx * (slot_s + pad)
					if arm_x <= x <= arm_x + slot_s and sy <= y <= sy + slot_s:
						return ("armor", idx, self.armor_slots[idx])

			grid_dim = 3 if self.crafting_mode == "3x3" else 2
			grid = self.active_crafting_grid
			cg_x = win_x + 24 if self.crafting_mode == "3x3" else win_x + 140
			cg_y = win_y + win_h - 180 if self.crafting_mode == "3x3" else win_y + win_h - 160

			# Crafting Grid Slots
			for r in range(grid_dim):
				for c in range(grid_dim):
					idx = r * grid_dim + c
					sx = cg_x + c * (slot_s + pad)
					sy = cg_y + (grid_dim - 1 - r) * (slot_s + pad)
					if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
						return ("craft", idx, grid[idx])

			# Crafting Result Slot
			arr_x = cg_x + grid_dim * (slot_s + pad) + 10
			arr_y = cg_y + (grid_dim * (slot_s + pad)) // 2 - 10
			res_x = arr_x + 50
			res_y = arr_y - 12
			if res_x <= x <= res_x + slot_s + 8 and res_y <= y <= res_y + slot_s + 8:
				return ("result", 0, self.crafting_result)

		# Storage Inventory (27 slots)
		cols = 9
		grid_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
		grid_y = win_y + 145
		for idx in range(27):
			r = idx // cols
			c = idx % cols
			sx = grid_x + c * (slot_s + pad)
			sy = grid_y - r * (slot_s + pad)
			if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
				return ("inv", idx, self.survival_inventory[idx])

		# Hotbar (9 slots)
		hb_x = win_x + (win_w - (9 * slot_s + 8 * pad)) // 2
		hb_y = win_y + 12
		for i in range(9):
			sx = hb_x + i * (slot_s + pad)
			sy = hb_y
			if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
				return ("hotbar", i, self.survival_hotbar[i])

		return None

	def _get_slot_ref_by_key(self, key):
		stype, sidx = key
		if stype == "armor":
			return self.armor_slots[sidx]
		elif stype == "craft":
			return self.active_crafting_grid[sidx]
		elif stype == "inv":
			return self.survival_inventory[sidx]
		elif stype == "hotbar":
			return self.survival_hotbar[sidx]
		elif stype == "result":
			return self.crafting_result
		elif stype == "enchant_item":
			return getattr(self, "enchant_item_slot", None)
		elif stype == "enchant_lapis":
			return getattr(self, "enchant_lapis_slot", None)
		elif stype == "furnace_input":
			return self.active_furnace.input_slot if self.active_furnace else None
		elif stype == "furnace_fuel":
			return self.active_furnace.fuel_slot if self.active_furnace else None
		elif stype == "furnace_output":
			return self.active_furnace.output_slot if self.active_furnace else None
		elif stype == "chest":
			if sidx < 27:
				return self.active_chest1.slots[sidx] if self.active_chest1 else None
			else:
				return self.active_chest2.slots[sidx - 27] if self.active_chest2 else None
		return None

	def handle_shift_click(self, slot_info):
		if not slot_info:
			return
		stype, sidx, target_slot = slot_info

		if stype == "result":
			# Shift-click result slot: craft as many items as possible directly into inventory!
			while self.crafting_result[0] != 0 and self.crafting_result[1] > 0:
				rb_id, rcnt = self.crafting_result[0], self.crafting_result[1]
				if not self.add_item(rb_id, rcnt):
					break
				grid = self.active_crafting_grid
				for slot in grid:
					if slot[0] != 0 and slot[1] > 0:
						slot[1] -= 1
						if slot[1] == 0:
							slot[0] = 0
							set_slot_metadata(slot, {})
				self.evaluate_crafting()
			return

		if not target_slot or target_slot[0] == 0 or target_slot[1] <= 0:
			return

		b_id, cnt = target_slot[0], target_slot[1]
		meta = get_slot_metadata(target_slot)
		ench = get_slot_enchantments(target_slot)
		max_stack = get_max_stack_size(b_id)

		if stype in ("furnace_output", "furnace_input", "furnace_fuel"):
			if self.add_item(b_id, cnt, metadata=meta):
				target_slot[0] = 0
				target_slot[1] = 0
				set_slot_metadata(target_slot, {})
				if stype == "furnace_output" and self.active_furnace and hasattr(self.active_furnace, 'accumulated_xp') and self.active_furnace.accumulated_xp > 0:
					import math, random
					earned_xp = int(math.floor(self.active_furnace.accumulated_xp))
					if random.random() < (self.active_furnace.accumulated_xp - earned_xp):
						earned_xp += 1
					self.active_furnace.accumulated_xp = 0.0
					if earned_xp > 0 and self.window and hasattr(self.window, 'camera') and self.window.camera:
						self.window.camera.add_xp(earned_xp)
			return

		if stype == "chest":
			if self.add_item(b_id, cnt, metadata=meta):
				target_slot[0] = 0
				target_slot[1] = 0
				set_slot_metadata(target_slot, {})
			return

		if stype == "armor":
			if self.add_item(b_id, cnt, metadata=meta):
				target_slot[0] = 0
				target_slot[1] = 0
				set_slot_metadata(target_slot, {})
			return

		if stype in ("enchant_item", "enchant_lapis"):
			if self.add_item(b_id, cnt, metadata=meta):
				target_slot[0] = 0
				target_slot[1] = 0
				set_slot_metadata(target_slot, {})
				self.update_enchantment_offers()
			return

		if self.crafting_mode == "enchanting" and stype in ("inv", "hotbar"):
			import enchanting
			if b_id == 214:
				# Lapis Lazuli: Move/stack into lapis slot
				l_slot = self.enchant_lapis_slot
				max_lapis = 64
				curr_cnt = l_slot[1] if l_slot[0] == 214 else 0
				if l_slot[0] == 0 or (l_slot[0] == 214 and curr_cnt < max_lapis):
					addable = min(cnt, max_lapis - curr_cnt)
					l_slot[0] = 214
					l_slot[1] = curr_cnt + addable
					target_slot[1] -= addable
					if target_slot[1] <= 0:
						target_slot[0] = 0
						set_slot_metadata(target_slot, {})
					self.update_enchantment_offers()
					return
			elif enchanting.is_enchantable(b_id) and getattr(self, "enchant_item_slot", [0])[0] == 0:
				# Enchantable item: Move 1 into item slot
				self.enchant_item_slot[0] = b_id
				self.enchant_item_slot[1] = 1
				set_slot_metadata(self.enchant_item_slot, meta)
				target_slot[1] -= 1
				if target_slot[1] <= 0:
					target_slot[0] = 0
					set_slot_metadata(target_slot, {})
				self.update_enchantment_offers()
				return

		# Auto-equip armor pieces when shift-clicked from inventory or hotbar
		if stype in ("inv", "hotbar") and b_id in ARMOR_SLOT_TYPES:
			arm_idx = ARMOR_SLOT_TYPES[b_id]
			arm_slot = self.armor_slots[arm_idx]
			if arm_slot[0] == 0:
				arm_slot[0] = b_id
				arm_slot[1] = 1
				set_slot_metadata(arm_slot, meta)
				target_slot[1] -= 1
				if target_slot[1] <= 0:
					target_slot[0] = 0
					set_slot_metadata(target_slot, {})
				return

		if self.crafting_mode in ("single_chest", "double_chest") and stype in ("inv", "hotbar"):
			chests = [self.active_chest1]
			if self.crafting_mode == "double_chest" and self.active_chest2:
				chests.append(self.active_chest2)

			if max_stack > 1 and not meta:
				for ch in chests:
					for slot in ch.slots:
						if slot[0] == b_id and slot[1] < max_stack and not is_slot_enchanted(slot) and not get_slot_damage(slot):
							addable = min(cnt, max_stack - slot[1])
							slot[1] += addable
							cnt -= addable
							if cnt == 0: break
					if cnt == 0: break

			if cnt > 0:
				for ch in chests:
					for slot in ch.slots:
						if slot[0] == 0 or slot[1] == 0:
							slot[0] = b_id
							slot[1] = min(cnt, max_stack)
							set_slot_metadata(slot, meta)
							cnt -= slot[1]
							if cnt == 0: break
					if cnt == 0: break

			target_slot[1] = cnt
			if cnt == 0:
				target_slot[0] = 0
				set_slot_metadata(target_slot, {})
			return

		if self.crafting_mode == "furnace" and self.active_furnace and stype in ("inv", "hotbar"):
			if b_id in FUEL_BURN_TIMES:
				f_slot = self.active_furnace.fuel_slot
				f_max = get_max_stack_size(b_id)
				if f_slot[0] == 0 or (f_slot[0] == b_id and f_slot[1] + cnt <= f_max):
					f_slot[0] = b_id
					f_slot[1] += cnt
					target_slot[0] = 0
					target_slot[1] = 0
					set_slot_metadata(target_slot, {})
					return
			if b_id in SMELTING_RECIPES:
				i_slot = self.active_furnace.input_slot
				i_max = get_max_stack_size(b_id)
				if i_slot[0] == 0 or (i_slot[0] == b_id and i_slot[1] + cnt <= i_max):
					i_slot[0] = b_id
					i_slot[1] += cnt
					target_slot[0] = 0
					target_slot[1] = 0
					set_slot_metadata(target_slot, {})
					return

		if stype == "craft":
			if self.add_item(b_id, cnt, metadata=meta):
				target_slot[0] = 0
				target_slot[1] = 0
				set_slot_metadata(target_slot, {})
				self.evaluate_crafting()
		elif stype == "inv":
			# Move from storage inventory into hotbar
			if max_stack > 1 and not meta:
				for slot in self.survival_hotbar:
					if slot[0] == b_id and slot[1] < max_stack and not is_slot_enchanted(slot) and not get_slot_damage(slot):
						addable = min(cnt, max_stack - slot[1])
						slot[1] += addable
						cnt -= addable
						if cnt == 0: break
			if cnt > 0:
				for slot in self.survival_hotbar:
					if slot[0] == 0 or slot[1] == 0:
						slot[0] = b_id
						slot[1] = min(cnt, max_stack)
						set_slot_metadata(slot, meta)
						cnt -= slot[1]
						if cnt == 0: break
			target_slot[1] = cnt
			if cnt == 0:
				target_slot[0] = 0
				set_slot_metadata(target_slot, {})
		elif stype == "hotbar":
			# Move from hotbar into storage inventory
			if max_stack > 1 and not meta:
				for slot in self.survival_inventory:
					if slot[0] == b_id and slot[1] < max_stack and not is_slot_enchanted(slot) and not get_slot_damage(slot):
						addable = min(cnt, max_stack - slot[1])
						slot[1] += addable
						cnt -= addable
						if cnt == 0: break
			if cnt > 0:
				for slot in self.survival_inventory:
					if slot[0] == 0 or slot[1] == 0:
						slot[0] = b_id
						slot[1] = min(cnt, max_stack)
						set_slot_metadata(slot, meta)
						cnt -= slot[1]
						if cnt == 0: break
			target_slot[1] = cnt
			if cnt == 0:
				target_slot[0] = 0
				set_slot_metadata(target_slot, {})

	def _update_left_drag(self):
		if not self.drag_visited_keys or not self.drag_initial_held:
			return

		b_id = self.drag_initial_held[0]
		total_cnt = self.drag_initial_held[1]
		meta = get_slot_metadata(self.drag_initial_held)
		max_stack = get_max_stack_size(b_id)

		n_slots = len(self.drag_visited_keys)
		per_slot = total_cnt // n_slots

		# 1. Reset all visited slots to baseline snapshot first
		for key in self.drag_visited_keys:
			slot_ref = self._get_slot_ref_by_key(key)
			if slot_ref is not None and key in self.drag_slot_snapshots:
				snap = self.drag_slot_snapshots[key]
				slot_ref[0] = snap[0]
				slot_ref[1] = snap[1]
				set_slot_metadata(slot_ref, get_slot_metadata(snap))

		# 2. Distribute per_slot into each visited slot
		allocated = 0
		if per_slot > 0:
			for key in self.drag_visited_keys:
				slot_ref = self._get_slot_ref_by_key(key)
				if slot_ref is not None and key in self.drag_slot_snapshots:
					orig_c = self.drag_slot_snapshots[key][1]
					space = max_stack - orig_c
					addable = min(per_slot, max_stack - orig_c)
					slot_ref[0] = b_id
					slot_ref[1] = orig_c + addable
					if orig_c == 0:
						set_slot_metadata(slot_ref, meta)
					allocated += addable

		remainder = total_cnt - allocated
		if remainder > 0:
			self.held_stack = [b_id, remainder]
			set_slot_metadata(self.held_stack, meta)
		else:
			self.held_stack = None

		self.evaluate_crafting()
		self.update_enchantment_offers()

	def gather_matching_items(self):
		"""Gathers all matching items scattered across inventory/hotbar/crafting into held_stack up to max_stack."""
		if not self.held_stack or self.held_stack[0] == 0:
			return
		max_stack = get_max_stack_size(self.held_stack[0])
		if self.held_stack[1] >= max_stack or max_stack == 1:
			return

		target_id = self.held_stack[0]

		# 1. Gather from active crafting grid
		grid = self.active_crafting_grid
		for slot in grid:
			if slot[0] == target_id and slot[1] > 0:
				needed = max_stack - self.held_stack[1]
				take = min(needed, slot[1])
				self.held_stack[1] += take
				slot[1] -= take
				if slot[1] <= 0:
					slot[0] = 0
				if self.held_stack[1] >= max_stack:
					self.evaluate_crafting()
					return

		self.evaluate_crafting()

		# 2. Gather from storage inventory (27 slots)
		for slot in self.survival_inventory:
			if slot[0] == target_id and slot[1] > 0:
				needed = max_stack - self.held_stack[1]
				take = min(needed, slot[1])
				self.held_stack[1] += take
				slot[1] -= take
				if slot[1] <= 0:
					slot[0] = 0
				if self.held_stack[1] >= max_stack:
					return

		# 3. Gather from hotbar (9 slots)
		for slot in self.survival_hotbar:
			if slot[0] == target_id and slot[1] > 0:
				needed = max_stack - self.held_stack[1]
				take = min(needed, slot[1])
				self.held_stack[1] += take
				slot[1] -= take
				if slot[1] <= 0:
					slot[0] = 0
				if self.held_stack[1] >= max_stack:
					return

	def handle_slot_click(self, target_slot, is_right_click, slot_type=None, slot_idx=None):
		"""
		Handles slot clicks for inventory, hotbar, armor, enchanting, and crafting grid slots.
		Left Click: Pick up / place full stack, or swap stacks.
		Right Click:
		  - If holding NO item: Splits target slot items in half (takes math.ceil(count / 2) onto cursor).
		  - If HOLDING an item: Places exactly ONE (1) item into target slot!
		"""
		held = self.held_stack

		if slot_type == "armor" and slot_idx is not None and held and held[0] != 0:
			b_id = held[0]
			if ARMOR_SLOT_TYPES.get(b_id) != slot_idx:
				return  # Reject invalid armor piece type for this slot!

		if slot_type == "enchant_lapis" and held and held[0] != 0 and held[0] != 214:
			return  # Reject non-Lapis items in lapis slot!

		if slot_type == "enchant_item" and held and held[0] != 0:
			import enchanting
			if not enchanting.is_enchantable(held[0]):
				return  # Reject non-enchantable items in enchanting item slot!

		if is_right_click:
			if held is None or held[0] == 0 or held[1] <= 0:
				# Right click when NOT holding an item: Split stack in half!
				if target_slot[0] != 0 and target_slot[1] > 0:
					total = target_slot[1]
					take = (total + 1) // 2  # math.ceil(total / 2)
					leave = total - take
					meta = get_slot_metadata(target_slot)
					
					self.held_stack = [target_slot[0], take, dict(meta)]
					if leave > 0:
						target_slot[1] = leave
					else:
						target_slot[0] = 0
						target_slot[1] = 0
						set_slot_metadata(target_slot, {})
				return
			else:
				# Right click when HOLDING an item: Place 1 item into target slot!
				b_id = held[0]
				held_ench = get_slot_enchantments(held)
				target_ench = get_slot_enchantments(target_slot)
				held_dmg = get_slot_damage(held)
				target_dmg = get_slot_damage(target_slot)
				max_stack = get_max_stack_size(b_id)

				if target_slot[0] == 0 or target_slot[1] == 0:
					target_slot[0] = b_id
					target_slot[1] = 1
					set_slot_metadata(target_slot, get_slot_metadata(held))
					held[1] -= 1
					if held[1] <= 0:
						self.held_stack = None
				elif target_slot[0] == b_id and target_ench == held_ench and not held_ench and held_dmg == 0 and target_dmg == 0 and target_slot[1] < max_stack:
					target_slot[1] += 1
					held[1] -= 1
					if held[1] <= 0:
						self.held_stack = None
				return
		else:
			# Left click: Standard stack swap / transfer
			self.held_stack = self._swap_slot(target_slot, held, slot_type=slot_type, slot_idx=slot_idx)

	def on_mouse_press(self, x, y, button, modifiers):
		if not self.inventory_open:
			return False

		curr_time = time.time()
		is_double_left = (button == pyglet.window.mouse.LEFT) and (curr_time - self.last_left_click_time < 0.35)
		if button == pyglet.window.mouse.LEFT:
			self.last_left_click_time = 0.0 if is_double_left else curr_time

		# 0. DOUBLE LEFT-CLICK GATHERING
		if is_double_left and self.held_stack and self.held_stack[0] != 0 and self.held_stack[1] < 64 and not self.window.flying:
			self.gather_matching_items()
			return True

		slot_info = self.get_slot_at_pos(x, y)
		is_shift = bool(modifiers & pyglet.window.key.MOD_SHIFT)
		is_right = (button == pyglet.window.mouse.RIGHT)

		# 1. SHIFT-CLICK HANDLING
		if is_shift and slot_info and not self.window.flying:
			self.handle_shift_click(slot_info)
			return True

		# Check Enchanting Table Choice Click
		if self.crafting_mode == "enchanting" and not self.window.flying and button == pyglet.window.mouse.LEFT:
			win_w = 640
			win_h = 460
			win_x = (self.window.width - win_w) // 2
			win_y = (self.window.height - win_h) // 2
			opt_x = win_x + 180
			opt_w = 420
			opt_h = 36
			opt_start_y = win_y + win_h - 110

			player_level = self.window.camera.level if (self.window and hasattr(self.window, "camera") and self.window.camera) else 0
			lapis_count = self.enchant_lapis_slot[1] if self.enchant_lapis_slot[0] == 214 else 0
			offers = getattr(self, "enchant_offers", [])

			for i in range(3):
				opt_y = opt_start_y - i * (opt_h + 8)
				if opt_x <= x <= opt_x + opt_w and opt_y <= y <= opt_y + opt_h:
					offer = offers[i] if (i < len(offers) and offers[i]) else None
					tier = i + 1
					if offer and player_level >= offer["req_level"] and lapis_count >= tier and self.enchant_item_slot[0] != 0:
						# Deduct lapis
						self.enchant_lapis_slot[1] -= tier
						if self.enchant_lapis_slot[1] <= 0:
							self.enchant_lapis_slot = [0, 0, {}]
						# Deduct player levels
						if self.window and hasattr(self.window, "camera") and self.window.camera:
							self.window.camera.deduct_levels(tier)
						# Apply enchantment
						self.enchant_item_slot = enchanting.apply_enchantment_to_slot(self.enchant_item_slot, offer["key"], offer["level"])
						# Refresh seed & offers
						self.enchant_seed += 13
						self.update_enchantment_offers()
						return True

		# Update creative search focus based on click location
		if self.window.flying:
			win_w = 640
			win_h = 460
			win_x = (self.window.width - win_w) // 2
			win_y = (self.window.height - win_h) // 2
			search_x = win_x + 24
			search_y = win_y + win_h - 78
			search_w = 260
			search_h = 24

			if search_x <= x <= search_x + search_w and search_y <= y <= search_y + search_h:
				self.creative_search_focused = True
			else:
				self.creative_search_focused = False

		# 2. CREATIVE PALETTE & HOTBAR CLICKS
		if self.window.flying:
			if slot_info and slot_info[0] == "creative":
				b_id = slot_info[2][0]
				if is_shift:
					# Shift-click in creative: instantly place stack of 64 into active or first open hotbar slot!
					target_idx = self.selected_slot
					if self.hotbar_slots[target_idx][0] != 0 and self.hotbar_slots[target_idx][0] != b_id:
						for i in range(9):
							if self.hotbar_slots[i][0] == 0:
								target_idx = i
								break
					self.hotbar_slots[target_idx] = [b_id, 64]
					self.set_selected_slot(target_idx)
				else:
					self.held_stack = [b_id, 64 if not is_right else 1]
				return True
			elif slot_info and slot_info[0] == "hotbar":
				idx = slot_info[1]
				if self.held_stack:
					self.hotbar_slots[idx] = [self.held_stack[0], 64]
					self.set_selected_slot(idx)
					self.held_stack = None
				else:
					self.set_selected_slot(idx)
				return True

		# 3. SURVIVAL CLICK & START DRAG
		if slot_info:
			stype, sidx, target_slot = slot_info

			if stype == "result":
				# Crafting result slot click
				rb_id, rcnt = self.crafting_result[0], self.crafting_result[1]
				if rb_id != 0 and rcnt > 0:
					if self.held_stack is None:
						self.held_stack = [rb_id, rcnt]
					elif self.held_stack[0] == rb_id and self.held_stack[1] + rcnt <= 64:
						self.held_stack[1] += rcnt
					else:
						return True

					grid = self.active_crafting_grid
					for slot in grid:
						if slot[0] != 0 and slot[1] > 0:
							slot[1] -= 1
							if slot[1] == 0:
								slot[0] = 0
					self.evaluate_crafting()
				return True
			elif stype == "furnace_output":
				out_id, out_cnt = target_slot[0], target_slot[1]
				if out_id != 0 and out_cnt > 0:
					collected = False
					if self.held_stack is None:
						self.held_stack = [out_id, out_cnt]
						target_slot[0] = 0
						target_slot[1] = 0
						collected = True
					elif self.held_stack[0] == out_id and self.held_stack[1] + out_cnt <= 64:
						self.held_stack[1] += out_cnt
						target_slot[0] = 0
						target_slot[1] = 0
						collected = True

					if collected and self.active_furnace and hasattr(self.active_furnace, 'accumulated_xp') and self.active_furnace.accumulated_xp > 0:
						earned_xp = int(math.floor(self.active_furnace.accumulated_xp))
						if random.random() < (self.active_furnace.accumulated_xp - earned_xp):
							earned_xp += 1
						self.active_furnace.accumulated_xp = 0.0
						if earned_xp > 0 and self.window and hasattr(self.window, 'camera') and self.window.camera:
							self.window.camera.add_xp(earned_xp)
				return True
			else:
				# Regular slot click (crafting, armor, inventory, or hotbar, or enchanting)
				key = (stype, sidx)
				if self.held_stack and self.held_stack[0] != 0 and self.held_stack[1] > 0:
					b_id = self.held_stack[0]
					max_stack = get_max_stack_size(b_id)
					is_drag_compatible = (
						stype in ("inv", "hotbar", "craft", "chest", "furnace_input", "furnace_fuel") and
						(target_slot[0] == 0 or (target_slot[0] == b_id and not is_slot_enchanted(target_slot) and not is_slot_enchanted(self.held_stack) and target_slot[1] < max_stack))
					)

					if button == pyglet.window.mouse.LEFT and is_drag_compatible:
						# Start Left Click equal-split drag
						self.is_dragging = True
						self.drag_button = pyglet.window.mouse.LEFT
						self.drag_initial_held = copy_slot(self.held_stack)
						self.drag_visited_keys = [key]
						self.drag_slot_snapshots = {key: copy_slot(target_slot)}
						self._update_left_drag()
						return True
					elif button == pyglet.window.mouse.RIGHT and is_drag_compatible:
						# Place 1 item and start Right Click single-item drag
						if target_slot[0] == 0 or target_slot[1] == 0:
							target_slot[0] = b_id
							target_slot[1] = 1
							set_slot_metadata(target_slot, get_slot_metadata(self.held_stack))
							self.held_stack[1] -= 1
						elif target_slot[0] == b_id and target_slot[1] < max_stack:
							target_slot[1] += 1
							self.held_stack[1] -= 1

						if self.held_stack[1] <= 0:
							self.held_stack = None

						if self.held_stack:
							self.is_dragging = True
							self.drag_button = pyglet.window.mouse.RIGHT
							self.drag_visited_keys = [key]
						else:
							self.is_dragging = False

						if stype == "craft":
							self.evaluate_crafting()
						elif stype in ("enchant_item", "enchant_lapis"):
							self.update_enchantment_offers()
						return True
					else:
						# Standard click (swap or armor equip)
						self.handle_slot_click(target_slot, is_right, slot_type=stype, slot_idx=sidx)
						if stype == "craft":
							self.evaluate_crafting()
						elif stype in ("enchant_item", "enchant_lapis"):
							self.update_enchantment_offers()
						return True
				else:
					# Cursor has no item: normal click picks up stack or half-stack
					self.handle_slot_click(target_slot, is_right, slot_type=stype, slot_idx=sidx)
					if stype == "craft":
						self.evaluate_crafting()
					elif stype in ("enchant_item", "enchant_lapis"):
						self.update_enchantment_offers()
					return True

		# Clicked outside slots / outside window -> Drop item into world
		if self.held_stack and self.held_stack[0] != 0 and self.held_stack[1] > 0:
			id_mgr = getattr(self.window, "item_drop_manager", None)
			if not id_mgr and hasattr(self.window, "world"):
				id_mgr = getattr(self.window.world, "item_drop_manager", None)
			if id_mgr and hasattr(self.window, "camera"):
				px, py, pz = self.window.camera.position
				rad_x, rad_y = self.window.camera.rotation
				dir_x = math.cos(rad_x) * math.cos(rad_y)
				dir_y = math.sin(rad_y)
				dir_z = math.sin(rad_x) * math.cos(rad_y)
				vx = dir_x * 3.5
				vy = dir_y * 3.5 + 1.2
				vz = dir_z * 3.5

				drop_cnt = 1 if is_right else self.held_stack[1]
				ench = get_slot_enchantments(self.held_stack)
				id_mgr.spawn_drop(
					self.held_stack[0], drop_cnt,
					[px, py - 0.4, pz], velocity=[vx, vy, vz],
					enchantments=ench
				)
				self.held_stack[1] -= drop_cnt
				if self.held_stack[1] <= 0:
					self.held_stack = None
			else:
				self.held_stack = None
		return True

	def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
		if not self.inventory_open or not self.is_dragging or not self.drag_button:
			return

		slot_info = self.get_slot_at_pos(x, y)
		if not slot_info or slot_info[0] == "result" or slot_info[0] == "creative" or slot_info[0] == "armor":
			return

		stype, sidx, target_slot = slot_info
		key = (stype, sidx)
		if key in self.drag_visited_keys:
			return

		if self.drag_button == pyglet.window.mouse.LEFT:
			if not self.drag_initial_held:
				return
			b_id = self.drag_initial_held[0]
			max_stack = get_max_stack_size(b_id)
			if target_slot[0] != 0 and target_slot[0] != b_id:
				return
			if is_slot_enchanted(target_slot) and target_slot[0] != 0:
				return
			if target_slot[1] >= max_stack:
				return

			self.drag_visited_keys.append(key)
			self.drag_slot_snapshots[key] = copy_slot(target_slot)
			self._update_left_drag()

		elif self.drag_button == pyglet.window.mouse.RIGHT:
			if not self.held_stack or self.held_stack[1] <= 0:
				self.is_dragging = False
				return

			b_id = self.held_stack[0]
			max_stack = get_max_stack_size(b_id)

			if target_slot[0] == 0 or target_slot[1] == 0:
				target_slot[0] = b_id
				target_slot[1] = 1
				set_slot_metadata(target_slot, get_slot_metadata(self.held_stack))
				self.held_stack[1] -= 1
				self.drag_visited_keys.append(key)
			elif target_slot[0] == b_id and target_slot[1] < max_stack and not is_slot_enchanted(target_slot) and not get_slot_damage(target_slot):
				target_slot[1] += 1
				self.held_stack[1] -= 1
				self.drag_visited_keys.append(key)
			else:
				return

			if self.held_stack[1] <= 0:
				self.held_stack = None
				self.is_dragging = False

			if stype == "craft":
				self.evaluate_crafting()
			elif stype in ("enchant_item", "enchant_lapis"):
				self.update_enchantment_offers()

	def on_mouse_release(self, x, y, button, modifiers):
		if self.is_dragging:
			if self.drag_button == pyglet.window.mouse.LEFT:
				self._update_left_drag()
			self.is_dragging = False
			self.drag_button = None
			self.drag_visited_keys.clear()
			self.drag_slot_snapshots.clear()
			self.drag_initial_held = None
			self.evaluate_crafting()

	def _swap_slot(self, target_slot, held, slot_type=None, slot_idx=None):
		if slot_type == "armor" and slot_idx is not None and held and held[0] != 0:
			b_id = held[0]
			if ARMOR_SLOT_TYPES.get(b_id) != slot_idx:
				return held
		if held is None or held[0] == 0:
			new_held = copy_slot(target_slot)
			target_slot[0] = 0
			target_slot[1] = 0
			set_slot_metadata(target_slot, {})
			return new_held if new_held[0] != 0 else None
		else:
			held_ench = get_slot_enchantments(held)
			target_ench = get_slot_enchantments(target_slot)
			held_dmg = get_slot_damage(held)
			target_dmg = get_slot_damage(target_slot)

			if target_slot[0] == 0 or target_slot[1] == 0:
				target_slot[0] = held[0]
				target_slot[1] = held[1]
				set_slot_metadata(target_slot, get_slot_metadata(held))
				return None
			elif target_slot[0] == held[0] and target_ench == held_ench and not held_ench and held_dmg == 0 and target_dmg == 0:
				max_stack = get_max_stack_size(target_slot[0])
				space = max_stack - target_slot[1]
				addable = min(space, held[1])
				target_slot[1] += addable
				held[1] -= addable
				return held if held[1] > 0 else None
			else:
				old_target = copy_slot(target_slot)
				target_slot[0] = held[0]
				target_slot[1] = held[1]
				set_slot_metadata(target_slot, get_slot_metadata(held))
				return old_target

	def on_mouse_scroll(self, scroll_y):
		if self.inventory_open and self.window.flying:
			if self.creative_search_text.strip():
				query = self.creative_search_text.strip().lower()
				filtered_items = [item for item in ALL_ITEMS if query in item[1].lower()]
			else:
				filtered_items = ALL_ITEMS

			cols = 8
			visible_rows = 5
			total_rows = math.ceil(len(filtered_items) / float(cols)) if filtered_items else 1
			max_scroll = max(0, total_rows - visible_rows)

			if scroll_y < 0:
				self.creative_scroll_row = min(max_scroll, self.creative_scroll_row + 1)
			elif scroll_y > 0:
				self.creative_scroll_row = max(0, self.creative_scroll_row - 1)
			return

		if scroll_y > 0:
			new_slot = (self.selected_slot - 1) % 9
		elif scroll_y < 0:
			new_slot = (self.selected_slot + 1) % 9
		else:
			return
		self.set_selected_slot(new_slot)

	def drop_all_on_death(self, death_position, item_drop_manager):
		"""Drops all inventory, hotbar, armor, crafting grid, cursor held items, and exactly half XP at death_position."""
		import random
		px, py, pz = death_position

		# Drop exactly half of player's current total XP at death location
		cam = getattr(self.window, 'camera', None)
		if cam and hasattr(cam, 'total_xp'):
			total_xp = cam.total_xp
			half_xp = total_xp // 2
			cam.reset_xp()
			if half_xp > 0 and item_drop_manager:
				item_drop_manager.spawn_xp_orb(half_xp, [px, py - 0.2, pz])

		def drop_slot(slot):
			if slot and slot[0] != 0 and slot[1] > 0:
				if item_drop_manager:
					vx = random.uniform(-1.8, 1.8)
					vy = random.uniform(1.5, 3.5)
					vz = random.uniform(-1.8, 1.8)
					ench = get_slot_enchantments(slot)
					item_drop_manager.spawn_drop(
						slot[0], slot[1], [px, py - 0.4, pz],
						velocity=[vx, vy, vz], enchantments=ench
					)
				slot[0] = 0
				slot[1] = 0
				set_slot_metadata(slot, {})

		# 1. Hotbar slots
		for slot in self.survival_hotbar:
			drop_slot(slot)

		# 2. Main inventory slots
		for slot in self.survival_inventory:
			drop_slot(slot)

		# 3. Armor slots
		for slot in self.armor_slots:
			drop_slot(slot)

		# 4. Crafting 2x2 & 3x3 slots
		for slot in self.crafting_grid_2x2:
			drop_slot(slot)
		for slot in self.crafting_grid_3x3:
			drop_slot(slot)
		self.crafting_result = [0, 0, {}]

		# 5. Cursor held stack
		if self.held_stack and self.held_stack[0] != 0 and self.held_stack[1] > 0:
			if item_drop_manager:
				vx = random.uniform(-1.8, 1.8)
				vy = random.uniform(1.5, 3.5)
				vz = random.uniform(-1.8, 1.8)
				ench = get_slot_enchantments(self.held_stack)
				item_drop_manager.spawn_drop(
					self.held_stack[0], self.held_stack[1], [px, py - 0.4, pz],
					velocity=[vx, vy, vz], enchantments=ench
				)
			self.held_stack = None

		self.inventory_open = False
