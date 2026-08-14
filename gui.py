import os
import math
import pyglet
import pyglet.gl as gl

# List of all available block items for the inventory palette
# Each entry is (block_id, display_name, texture_name)
PALETTE_ITEMS = [
	(2, "Grass Block", "grass"),
	(4, "Dirt", "dirt"),
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
]

ALL_ITEMS = PALETTE_ITEMS + TOOL_ITEMS
BLOCK_INFO = {item[0]: (item[1], item[2]) for item in ALL_ITEMS}

# Smelting Recipes: input_item_id -> (result_item_id, result_count)
SMELTING_RECIPES = {
	17: (123, 1),   # Iron Ore -> Iron Ingot
	35: (124, 1),   # Gold Ore -> Gold Ingot
	1:  (5, 1),     # Cobblestone -> Stone
	8:  (121, 1),   # Oak Log -> Coal (Charcoal)
	6:  (21, 1),    # Sand -> Glass
	4:  (22, 1),    # Clay/Dirt -> Bricks
}

# Fuel Durations (in seconds of burn time): item_id -> burn_time_seconds
# 1 item smelt takes 10.0 seconds
FUEL_BURN_TIMES = {
	121: 80.0,  # Coal item -> 80s (8 smelts)
	16:  80.0,  # Coal Ore -> 80s (8 smelts)
	8:   15.0,  # Oak Log -> 15s (1.5 smelts)
	7:   15.0,  # Oak Planks -> 15s (1.5 smelts)
	26:  15.0,  # Crafting Table -> 15s
	23:  15.0,  # Bookshelf -> 15s
	101: 10.0,  # Wooden Pickaxe -> 10s
	105: 10.0,  # Wooden Axe -> 10s
	109: 10.0,  # Wooden Shovel -> 10s
	113: 10.0,  # Wooden Sword -> 10s
	100: 5.0,   # Stick -> 5s (0.5 smelts)
}

# Tool Properties: item_id -> (category, tier, speed_multiplier)
# Category: "pickaxe", "axe", "shovel", "sword"
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
	23: ("axe", 0, 1.2, 23),       # Bookshelf
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
}

def draw_bordered_box(x, y, width, height, border, bg_color, border_color):
	outer = pyglet.shapes.Rectangle(x, y, width, height, color=border_color)
	outer.draw()
	if width > 2 * border and height > 2 * border:
		inner = pyglet.shapes.Rectangle(x + border, y + border, width - 2 * border, height - 2 * border, color=bg_color)
		inner.draw()

def draw_vector_heart(x, y, is_full=True, is_half=False):
	outer_c1 = pyglet.shapes.Circle(x + 4, y + 10, 4, color=(30, 0, 0, 220))
	outer_c2 = pyglet.shapes.Circle(x + 11, y + 10, 4, color=(30, 0, 0, 220))
	outer_tri = pyglet.shapes.Triangle(x, y + 9, x + 15, y + 9, x + 7.5, y + 1, color=(30, 0, 0, 220))
	outer_c1.draw()
	outer_c2.draw()
	outer_tri.draw()

	if not is_full and not is_half:
		return

	red_c = (230, 25, 25, 255)

	if is_full:
		c1 = pyglet.shapes.Circle(x + 4, y + 10, 3, color=red_c)
		c2 = pyglet.shapes.Circle(x + 11, y + 10, 3, color=red_c)
		tri = pyglet.shapes.Triangle(x + 1, y + 9, x + 14, y + 9, x + 7.5, y + 2, color=red_c)
		c1.draw()
		c2.draw()
		tri.draw()
	elif is_half:
		c1 = pyglet.shapes.Circle(x + 4, y + 10, 3, color=red_c)
		tri = pyglet.shapes.Triangle(x + 1, y + 9, x + 7.5, y + 9, x + 7.5, y + 2, color=red_c)
		c1.draw()
		tri.draw()

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
		
		# Survival hotbar & inventory start completely empty [0, 0]
		self.survival_hotbar = [[0, 0] for _ in range(9)]
		self.survival_inventory = [[0, 0] for _ in range(27)]

		# Crafting System Grid (2x2 & 3x3) & Result Slot
		self.crafting_grid_2x2 = [[0, 0] for _ in range(4)]
		self.crafting_grid_3x3 = [[0, 0] for _ in range(9)]
		self.crafting_result = [0, 0]

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

	def reset_inventory(self):
		self.survival_hotbar = [[0, 0] for _ in range(9)]
		self.survival_inventory = [[0, 0] for _ in range(27)]
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

	def _load_icons(self):
		for b_id, name, tex_name in ALL_ITEMS:
			img_path = os.path.join("textures", f"{tex_name}.png")
			if os.path.exists(img_path):
				try:
					img = pyglet.image.load(img_path)
					self.icon_textures[b_id] = img
				except Exception:
					pass

	@property
	def hotbar_slots(self):
		return self.creative_hotbar if getattr(self.window, "flying", False) else self.survival_hotbar

	def get_current_block_id(self):
		slot = self.hotbar_slots[self.selected_slot]
		return slot[0] if slot[1] > 0 else 0

	def consume_active_item(self):
		if getattr(self.window, "flying", False):
			return  # Creative mode: unlimited placement

		slot = self.hotbar_slots[self.selected_slot]
		if slot[0] != 0 and slot[1] > 0:
			slot[1] -= 1
			if slot[1] == 0:
				slot[0] = 0

	def add_item(self, block_id, count=1):
		if getattr(self.window, "flying", False) or block_id in (0, 9, 19, 15, 20, 14):
			return True

		# 1. Stack into existing hotbar matching slots
		for slot in self.survival_hotbar:
			if slot[0] == block_id and slot[1] < 64:
				addable = min(count, 64 - slot[1])
				slot[1] += addable
				count -= addable
				if count == 0:
					return True

		# 2. Stack into existing inventory matching slots
		for slot in self.survival_inventory:
			if slot[0] == block_id and slot[1] < 64:
				addable = min(count, 64 - slot[1])
				slot[1] += addable
				count -= addable
				if count == 0:
					return True

		# 3. Place into first empty hotbar slot
		for slot in self.survival_hotbar:
			if slot[0] == 0 or slot[1] == 0:
				slot[0] = block_id
				slot[1] = min(count, 64)
				count -= slot[1]
				if count == 0:
					return True

		# 4. Place into first empty inventory slot
		for slot in self.survival_inventory:
			if slot[0] == 0 or slot[1] == 0:
				slot[0] = block_id
				slot[1] = min(count, 64)
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
			'hotbar': [list(slot) for slot in self.survival_hotbar],
			'inventory': [list(slot) for slot in self.survival_inventory],
			'crafting_grid_2x2': [list(slot) for slot in self.crafting_grid_2x2],
			'crafting_grid_3x3': [list(slot) for slot in self.crafting_grid_3x3],
			'crafting_result': list(self.crafting_result),
			'selected_slot': self.selected_slot
		}

	def load_inventory_data(self, data):
		if not data:
			return
		if 'hotbar' in data:
			self.survival_hotbar = [list(slot) for slot in data['hotbar']]
		if 'inventory' in data:
			self.survival_inventory = [list(slot) for slot in data['inventory']]
		if 'crafting_grid_2x2' in data:
			self.crafting_grid_2x2 = [list(slot) for slot in data['crafting_grid_2x2']]
		if 'crafting_grid_3x3' in data:
			self.crafting_grid_3x3 = [list(slot) for slot in data['crafting_grid_3x3']]
		elif 'crafting_grid' in data and len(data['crafting_grid']) == 9:
			self.crafting_grid_3x3 = [list(slot) for slot in data['crafting_grid']]
		if 'crafting_result' in data:
			self.crafting_result = list(data['crafting_result'])
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

		# Recipe 1: 1 Log (8) -> 4 Planks (7)
		if h == 1 and w == 1 and matrix[0][0] == 8:
			self.crafting_result = [7, 4]
			return

		# Recipe 2: 2 Planks (7) vertical -> 4 Sticks (100)
		if h == 2 and w == 1 and matrix[0][0] == 7 and matrix[1][0] == 7:
			self.crafting_result = [100, 4]
			return

		# Recipe 3: 4 Planks (7) 2x2 -> 1 Crafting Table (26)
		if h == 2 and w == 2 and matrix == [[7, 7], [7, 7]]:
			self.crafting_result = [26, 1]
			return

		# Recipe 4: Pickaxes (3 top items + 2 vertical sticks) - Requires 3x3 Crafting Table
		if h == 3 and w == 3:
			top = matrix[0]
			center_col = [matrix[0][1], matrix[1][1], matrix[2][1]]
			if center_col[1] == 100 and center_col[2] == 100 and matrix[1][0] == 0 and matrix[1][2] == 0 and matrix[2][0] == 0 and matrix[2][2] == 0:
				mat = top[0]
				if top == [mat, mat, mat]:
					if mat in (7,): self.crafting_result = [101, 1]; return          # Wood Pickaxe (Planks)
					if mat in (1, 5): self.crafting_result = [102, 1]; return        # Stone Pickaxe (Cobblestone / Stone)
					if mat in (123, 17, 29): self.crafting_result = [103, 1]; return # Iron Pickaxe (Iron Ingot / Ore / Block)
					if mat in (122, 18, 30): self.crafting_result = [104, 1]; return # Diamond Pickaxe (Diamond / Ore / Block)
					if mat in (124, 35, 28): self.crafting_result = [117, 1]; return # Gold Pickaxe (Gold Ingot / Ore / Block)

		# Recipe 5: Axes (2x3 shape: 3 head items + 2 sticks) - Left or Right Facing
		if h == 3 and w == 2:
			# Left-facing Axe
			mat = matrix[0][0]
			if matrix[0][1] == mat and matrix[1][0] == mat and matrix[1][1] == 100 and matrix[2][1] == 100 and matrix[2][0] == 0:
				if mat in (7,): self.crafting_result = [105, 1]; return          # Wood Axe
				if mat in (1, 5): self.crafting_result = [106, 1]; return        # Stone Axe
				if mat in (123, 17, 29): self.crafting_result = [107, 1]; return # Iron Axe
				if mat in (122, 18, 30): self.crafting_result = [108, 1]; return # Diamond Axe
				if mat in (124, 35, 28): self.crafting_result = [118, 1]; return # Gold Axe
			# Right-facing Axe
			mat = matrix[0][1]
			if matrix[0][0] == mat and matrix[1][1] == mat and matrix[1][0] == 100 and matrix[2][0] == 100 and matrix[2][1] == 0:
				if mat in (7,): self.crafting_result = [105, 1]; return          # Wood Axe
				if mat in (1, 5): self.crafting_result = [106, 1]; return        # Stone Axe
				if mat in (123, 17, 29): self.crafting_result = [107, 1]; return # Iron Axe
				if mat in (122, 18, 30): self.crafting_result = [108, 1]; return # Diamond Axe
				if mat in (124, 35, 28): self.crafting_result = [118, 1]; return # Gold Axe

		# Recipe 6: Shovels (1x3 shape: 1 head item + 2 sticks) - Requires 3x3 Crafting Table
		if h == 3 and w == 1:
			mat = matrix[0][0]
			if matrix[1][0] == 100 and matrix[2][0] == 100:
				if mat in (7,): self.crafting_result = [109, 1]; return          # Wood Shovel
				if mat in (1, 5): self.crafting_result = [110, 1]; return        # Stone Shovel
				if mat in (123, 17, 29): self.crafting_result = [111, 1]; return # Iron Shovel
				if mat in (122, 18, 30): self.crafting_result = [112, 1]; return # Diamond Shovel
				if mat in (124, 35, 28): self.crafting_result = [119, 1]; return # Gold Shovel

		# Recipe 7: Swords (1x3 shape: 2 blade items + 1 stick) - Requires 3x3 Crafting Table
		if h == 3 and w == 1:
			mat = matrix[0][0]
			if matrix[1][0] == mat and matrix[2][0] == 100:
				if mat in (7,): self.crafting_result = [113, 1]; return          # Wood Sword
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
				mat = ring[0]
				if mat != 0 and all(x == mat for x in ring):
					if mat == 1: self.crafting_result = [27, 1]; return   # Furnace (27)
					if mat == 7: self.crafting_result = [37, 1]; return   # Chest (37)

		self.crafting_result = [0, 0]

	def set_selected_slot(self, slot_idx):
		if 0 <= slot_idx < 9:
			self.selected_slot = slot_idx
			self.window.holding = self.get_current_block_id()

	def toggle_inventory(self):
		self.inventory_open = not self.inventory_open
		if self.inventory_open:
			self.crafting_mode = "creative" if self.window.flying else "2x2"
			self.window.mouse_captured = False
			self.window.set_exclusive_mouse(False)
			self.evaluate_crafting()
		else:
			# Return ingredients left in active crafting grids to inventory when closing
			for grid in (self.crafting_grid_2x2, self.crafting_grid_3x3):
				for slot in grid:
					if slot[0] != 0 and slot[1] > 0:
						self.add_item(slot[0], slot[1])
						slot[0] = 0
						slot[1] = 0
			self.crafting_result = [0, 0]
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
			flash = pyglet.shapes.Rectangle(0, 0, self.window.width, self.window.height, color=(255, 0, 0, alpha))
			flash.draw()

		hover_text = None

		hover_text = self._draw_hotbar(hover_text)

		if not self.window.flying:
			self._draw_health_bar()

		if self.inventory_open:
			hover_text = self._draw_inventory_overlay(hover_text)

		if hover_text:
			self.tooltip_label.text = hover_text
			self.tooltip_label.x = self.mouse_x
			self.tooltip_label.y = self.mouse_y + 16
			
			tw = self.tooltip_label.content_width + 12
			th = self.tooltip_label.content_height + 6
			tx = self.mouse_x - tw // 2
			ty = self.mouse_y + 12
			
			draw_bordered_box(tx, ty, tw, th, 1, (10, 10, 15, 230), (200, 200, 220, 255))
			self.tooltip_label.draw()

		if self.inventory_open and self.held_stack and self.held_stack[0] in self.icon_textures:
			b_id, cnt = self.held_stack[0], self.held_stack[1]
			img = self.icon_textures[b_id]
			spr = pyglet.sprite.Sprite(img, x=self.mouse_x - 16, y=self.mouse_y - 16)
			spr.scale_x = 32.0 / img.width
			spr.scale_y = 32.0 / img.height
			spr.draw()

			if cnt > 1 or not self.window.flying:
				cnt_lbl = pyglet.text.Label(str(cnt), font_name="Arial", font_size=10, x=self.mouse_x + 14, y=self.mouse_y - 14, anchor_x="right", anchor_y="bottom", color=(255, 255, 255, 255))
				cnt_lbl.draw()

		gl.glDepthMask(gl.GL_TRUE)
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_CULL_FACE)
		self.window.shader.use()

	def _draw_health_bar(self):
		slot_size = 44
		padding = 6
		total_w = 9 * slot_size + 8 * padding
		start_x = (self.window.width - total_w) // 2
		start_y = 64

		health = self.window.camera.health

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
				spr = pyglet.sprite.Sprite(img, x=sx + 6, y=sy + 6)
				spr.scale_x = 32.0 / img.width
				spr.scale_y = 32.0 / img.height
				spr.draw()

				if cnt > 1 or not self.window.flying:
					cnt_lbl = pyglet.text.Label(str(cnt), font_name="Arial", font_size=10, x=sx + slot_size - 4, y=sy + 3, anchor_x="right", anchor_y="bottom", color=(255, 255, 255, 255))
					cnt_lbl.draw()

			num_lbl = pyglet.text.Label(str(i + 1), font_name="Arial", font_size=9, x=sx + 3, y=sy + slot_size - 2, anchor_x="left", anchor_y="top", color=(220, 220, 220, 255))
			num_lbl.draw()

			if sx <= self.mouse_x <= sx + slot_size and sy <= self.mouse_y <= sy + slot_size:
				b_name = BLOCK_INFO.get(b_id, ("Empty", ""))[0] if cnt > 0 else "Empty"
				current_hover = f"[{i + 1}] {b_name} ({cnt})" if cnt > 0 else f"[{i + 1}] Empty"

		return current_hover

	def _draw_item_in_slot(self, slot, sx, sy, slot_s):
		if not slot:
			return
		b_id, cnt = slot[0], slot[1]
		if b_id in self.icon_textures and cnt > 0:
			img = self.icon_textures[b_id]
			spr = pyglet.sprite.Sprite(img, x=sx + 4, y=sy + 4)
			spr.scale_x = 32.0 / img.width
			spr.scale_y = 32.0 / img.height
			spr.draw()

			cnt_lbl = pyglet.text.Label(str(cnt), font_name="Arial", font_size=9, x=sx + slot_s - 3, y=sy + 2, anchor_x="right", anchor_y="bottom", color=(255, 255, 255, 255))
			cnt_lbl.draw()

	def _draw_inventory_overlay(self, current_hover):
		veil = pyglet.shapes.Rectangle(0, 0, self.window.width, self.window.height, color=(0, 0, 0, 160))
		veil.draw()

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
			# Creative Palette Grid (8 columns x 5 rows)
			cols = 8
			grid_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			grid_y = win_y + win_h - 90

			for idx, (b_id, b_name, tex_name) in enumerate(ALL_ITEMS):
				r = idx // cols
				c = idx % cols

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
					current_hover = b_name
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

			# 3. Flame Burn Meter (between input & fuel)
			flame_bg = pyglet.shapes.Rectangle(f_x + 12, f_y + 43, 16, 14, color=(40, 40, 50, 255))
			flame_bg.draw()
			if self.active_furnace.burn_time_remaining > 0 and self.active_furnace.max_burn_time > 0:
				ratio = min(1.0, self.active_furnace.burn_time_remaining / self.active_furnace.max_burn_time)
				fh = int(14 * ratio)
				flame_fg = pyglet.shapes.Rectangle(f_x + 12, f_y + 43, 16, fh, color=(255, 140, 0, 255))
				flame_fg.draw()

			# 4. Progress Arrow (between slots and output)
			arr_bg = pyglet.shapes.Rectangle(f_x + 55, f_y + 32, 55, 16, color=(40, 40, 50, 255))
			arr_bg.draw()
			if self.active_furnace.smelt_progress > 0:
				ratio = min(1.0, self.active_furnace.smelt_progress / 10.0)
				pw = int(55 * ratio)
				arr_fg = pyglet.shapes.Rectangle(f_x + 55, f_y + 32, pw, 16, color=(50, 205, 50, 255))
				arr_fg.draw()
			arr_lbl = pyglet.text.Label("==>", font_name="Arial", font_size=10, x=f_x + 68, y=f_y + 33, color=(255, 255, 255, 220))
			arr_lbl.draw()

			# 5. Output Result Slot
			res_x = f_x + 130
			res_y = f_y + 22
			is_h_out = (res_x <= self.mouse_x <= res_x + slot_s + 8 and res_y <= self.mouse_y <= res_y + slot_s + 8)
			draw_bordered_box(res_x, res_y, slot_s + 8, slot_s + 8, 2, (75, 80, 100, 240) if is_h_out else (45, 50, 65, 220), (255, 215, 0, 255) if is_h_out else (120, 140, 180, 255))
			self._draw_item_in_slot(self.active_furnace.output_slot, res_x + 4, res_y + 4, slot_s)

			if is_h_in:
				b_id, cnt = self.active_furnace.input_slot[0], self.active_furnace.input_slot[1]
				b_name = BLOCK_INFO.get(b_id, ("Empty", ""))[0] if cnt > 0 else "Ingredient Slot"
				current_hover = f"Ingredient: {b_name} ({cnt})" if cnt > 0 else "Furnace Ingredient Slot (Empty)"
			elif is_h_fuel:
				b_id, cnt = self.active_furnace.fuel_slot[0], self.active_furnace.fuel_slot[1]
				b_name = BLOCK_INFO.get(b_id, ("Empty", ""))[0] if cnt > 0 else "Fuel Slot"
				current_hover = f"Fuel: {b_name} ({cnt})" if cnt > 0 else "Furnace Fuel Slot (Empty)"
			elif is_h_out:
				b_id, cnt = self.active_furnace.output_slot[0], self.active_furnace.output_slot[1]
				b_name = BLOCK_INFO.get(b_id, ("Empty", ""))[0] if cnt > 0 else "Output Slot"
				current_hover = f"Smelt Output: {b_name} ({cnt})" if cnt > 0 else "Furnace Output Slot (Empty)"
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
					b_id, cnt = slot[0], slot[1]
					b_name = BLOCK_INFO.get(b_id, ("Empty", ""))[0] if cnt > 0 else "Empty Chest Slot"
					current_hover = f"Chest Slot {idx + 1}: {b_name} ({cnt})" if cnt > 0 else "Empty Chest Slot"

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
					b_id, cnt = slot[0], slot[1]
					b_name = BLOCK_INFO.get(b_id, ("Empty", ""))[0] if cnt > 0 else "Empty Chest Slot"
					current_hover = f"Large Chest Slot {idx + 1}: {b_name} ({cnt})" if cnt > 0 else "Empty Chest Slot"
		else:
			grid_dim = 3 if self.crafting_mode == "3x3" else 2
			grid = self.active_crafting_grid

			grid_title_text = "Crafting Table Grid (3x3):" if self.crafting_mode == "3x3" else "Crafting Grid (2x2):"
			craft_lbl = pyglet.text.Label(grid_title_text, font_name="Arial", font_size=10, x=win_x + 24, y=win_y + win_h - 68, color=(220, 220, 240, 255))
			craft_lbl.draw()

			cg_x = win_x + 24
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
						b_name = BLOCK_INFO.get(b_id, ("Empty", ""))[0] if cnt > 0 else "Empty Crafting Slot"
						current_hover = f"{b_name} ({cnt})" if cnt > 0 else "Empty Crafting Slot"

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
				b_name = BLOCK_INFO.get(rb_id, ("Result", ""))[0] if rcnt > 0 else "Result Slot"
				current_hover = f"Craft Result: {b_name} x{rcnt}" if rcnt > 0 else "Result Slot (Empty)"

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
					b_name = BLOCK_INFO.get(b_id, ("Empty", ""))[0] if cnt > 0 else "Empty"
					current_hover = f"{b_name} ({cnt})" if cnt > 0 else "Empty Slot"

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
				b_name = BLOCK_INFO.get(b_id, ("Empty", ""))[0] if cnt > 0 else "Empty"
				current_hover = f"Slot {i + 1}: {b_name} ({cnt})" if cnt > 0 else f"Slot {i + 1}: Empty"

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
			cols = 8
			grid_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			grid_y = win_y + win_h - 90
			for idx, (b_id, b_name, tex_name) in enumerate(ALL_ITEMS):
				r = idx // cols
				c = idx % cols
				sx = grid_x + c * (slot_s + pad)
				sy = grid_y - r * (slot_s + pad)
				if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
					return ("creative", idx, [b_id, 64])
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
		else:
			grid_dim = 3 if self.crafting_mode == "3x3" else 2
			grid = self.active_crafting_grid
			cg_x = win_x + 24
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
		if stype == "craft":
			return self.active_crafting_grid[sidx]
		elif stype == "inv":
			return self.survival_inventory[sidx]
		elif stype == "hotbar":
			return self.survival_hotbar[sidx]
		elif stype == "result":
			return self.crafting_result
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
				self.evaluate_crafting()
			return

		if stype in ("furnace_output", "furnace_input", "furnace_fuel"):
			b_id, cnt = target_slot[0], target_slot[1]
			if b_id != 0 and cnt > 0:
				if self.add_item(b_id, cnt):
					target_slot[0] = 0
					target_slot[1] = 0
			return

		if stype == "chest":
			b_id, cnt = target_slot[0], target_slot[1]
			if b_id != 0 and cnt > 0:
				if self.add_item(b_id, cnt):
					target_slot[0] = 0
					target_slot[1] = 0
			return

		b_id, cnt = target_slot[0], target_slot[1]
		if b_id == 0 or cnt <= 0:
			return

		if self.crafting_mode in ("single_chest", "double_chest") and stype in ("inv", "hotbar"):
			chests = [self.active_chest1]
			if self.crafting_mode == "double_chest" and self.active_chest2:
				chests.append(self.active_chest2)

			for ch in chests:
				for slot in ch.slots:
					if slot[0] == b_id and slot[1] < 64:
						addable = min(cnt, 64 - slot[1])
						slot[1] += addable
						cnt -= addable
						if cnt == 0: break
				if cnt == 0: break

			if cnt > 0:
				for ch in chests:
					for slot in ch.slots:
						if slot[0] == 0 or slot[1] == 0:
							slot[0] = b_id
							slot[1] = cnt
							cnt = 0
							break
					if cnt == 0: break

			target_slot[1] = cnt
			if cnt == 0: target_slot[0] = 0
			return

		if self.crafting_mode == "furnace" and self.active_furnace and stype in ("inv", "hotbar"):
			if b_id in FUEL_BURN_TIMES:
				f_slot = self.active_furnace.fuel_slot
				if f_slot[0] == 0 or (f_slot[0] == b_id and f_slot[1] + cnt <= 64):
					f_slot[0] = b_id
					f_slot[1] += cnt
					target_slot[0] = 0
					target_slot[1] = 0
					return
			if b_id in SMELTING_RECIPES:
				i_slot = self.active_furnace.input_slot
				if i_slot[0] == 0 or (i_slot[0] == b_id and i_slot[1] + cnt <= 64):
					i_slot[0] = b_id
					i_slot[1] += cnt
					target_slot[0] = 0
					target_slot[1] = 0
					return

		if stype == "craft":
			if self.add_item(b_id, cnt):
				target_slot[0] = 0
				target_slot[1] = 0
				self.evaluate_crafting()
		elif stype == "inv":
			# Move from storage inventory into hotbar
			for slot in self.survival_hotbar:
				if slot[0] == b_id and slot[1] < 64:
					addable = min(cnt, 64 - slot[1])
					slot[1] += addable
					cnt -= addable
					if cnt == 0: break
			if cnt > 0:
				for slot in self.survival_hotbar:
					if slot[0] == 0 or slot[1] == 0:
						slot[0] = b_id
						slot[1] = cnt
						cnt = 0
						break
			target_slot[1] = cnt
			if cnt == 0: target_slot[0] = 0
		elif stype == "hotbar":
			# Move from hotbar into storage inventory
			for slot in self.survival_inventory:
				if slot[0] == b_id and slot[1] < 64:
					addable = min(cnt, 64 - slot[1])
					slot[1] += addable
					cnt -= addable
					if cnt == 0: break
			if cnt > 0:
				for slot in self.survival_inventory:
					if slot[0] == 0 or slot[1] == 0:
						slot[0] = b_id
						slot[1] = cnt
						cnt = 0
						break
			target_slot[1] = cnt
			if cnt == 0: target_slot[0] = 0

	def _update_left_drag(self):
		if not self.drag_visited_keys or not self.drag_initial_held:
			return

		b_id, total_cnt = self.drag_initial_held
		n_slots = len(self.drag_visited_keys)
		per_slot = total_cnt // n_slots
		remainder = total_cnt % n_slots

		# Reset all visited slots to baseline snapshot first
		for key in self.drag_visited_keys:
			slot_ref = self._get_slot_ref_by_key(key)
			if slot_ref:
				orig_b, orig_c = self.drag_slot_snapshots[key]
				slot_ref[0] = orig_b
				slot_ref[1] = orig_c

		if per_slot > 0:
			for key in self.drag_visited_keys:
				slot_ref = self._get_slot_ref_by_key(key)
				if slot_ref:
					orig_b, orig_c = self.drag_slot_snapshots[key]
					if orig_b == 0 or orig_c == 0:
						slot_ref[0] = b_id
						slot_ref[1] = min(64, per_slot)
					elif orig_b == b_id:
						slot_ref[1] = min(64, orig_c + per_slot)
		else:
			remainder = total_cnt

		self.held_stack = [b_id, remainder] if remainder > 0 else None
		self.evaluate_crafting()

	def gather_matching_items(self):
		"""Gathers all matching items scattered across inventory/hotbar/crafting into held_stack up to 64."""
		if not self.held_stack or self.held_stack[0] == 0 or self.held_stack[1] >= 64:
			return

		target_id = self.held_stack[0]

		# 1. Gather from active crafting grid
		grid = self.active_crafting_grid
		for slot in grid:
			if slot[0] == target_id and slot[1] > 0:
				needed = 64 - self.held_stack[1]
				take = min(needed, slot[1])
				self.held_stack[1] += take
				slot[1] -= take
				if slot[1] <= 0:
					slot[0] = 0
				if self.held_stack[1] >= 64:
					self.evaluate_crafting()
					return

		self.evaluate_crafting()

		# 2. Gather from storage inventory (27 slots)
		for slot in self.survival_inventory:
			if slot[0] == target_id and slot[1] > 0:
				needed = 64 - self.held_stack[1]
				take = min(needed, slot[1])
				self.held_stack[1] += take
				slot[1] -= take
				if slot[1] <= 0:
					slot[0] = 0
				if self.held_stack[1] >= 64:
					return

		# 3. Gather from hotbar (9 slots)
		for slot in self.survival_hotbar:
			if slot[0] == target_id and slot[1] > 0:
				needed = 64 - self.held_stack[1]
				take = min(needed, slot[1])
				self.held_stack[1] += take
				slot[1] -= take
				if slot[1] <= 0:
					slot[0] = 0
				if self.held_stack[1] >= 64:
					return

	def handle_slot_click(self, target_slot, is_right_click):
		"""
		Handles slot clicks for inventory, hotbar, and crafting grid slots.
		Left Click: Pick up / place full stack, or swap stacks.
		Right Click:
		  - If holding NO item: Splits target slot items in half (takes math.ceil(count / 2) onto cursor).
		  - If HOLDING an item: Places exactly ONE (1) item into target slot!
		"""
		held = self.held_stack

		if is_right_click:
			if held is None or held[0] == 0 or held[1] <= 0:
				# Right click when NOT holding an item: Split stack in half!
				if target_slot[0] != 0 and target_slot[1] > 0:
					total = target_slot[1]
					take = (total + 1) // 2  # math.ceil(total / 2)
					leave = total - take
					
					self.held_stack = [target_slot[0], take]
					if leave > 0:
						target_slot[1] = leave
					else:
						target_slot[0] = 0
						target_slot[1] = 0
				return
			else:
				# Right click when HOLDING an item: Place 1 item into target slot!
				b_id = held[0]
				if target_slot[0] == 0 or target_slot[1] == 0:
					target_slot[0] = b_id
					target_slot[1] = 1
					held[1] -= 1
					if held[1] <= 0:
						self.held_stack = None
				elif target_slot[0] == b_id and target_slot[1] < 64:
					target_slot[1] += 1
					held[1] -= 1
					if held[1] <= 0:
						self.held_stack = None
				return
		else:
			# Left click: Standard stack swap / transfer
			self.held_stack = self._swap_slot(target_slot, held)

	def on_mouse_press(self, x, y, button, modifiers):
		if not self.inventory_open:
			return False

		import time
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

		# 2. CREATIVE PALETTE CLICKS
		if self.window.flying:
			if slot_info and slot_info[0] == "creative":
				b_id = slot_info[2][0]
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
					if self.held_stack is None:
						self.held_stack = [out_id, out_cnt]
						target_slot[0] = 0
						target_slot[1] = 0
					elif self.held_stack[0] == out_id and self.held_stack[1] + out_cnt <= 64:
						self.held_stack[1] += out_cnt
						target_slot[0] = 0
						target_slot[1] = 0
				return True
			else:
				# Regular slot click (crafting, inventory, or hotbar)
				self.handle_slot_click(target_slot, is_right)
				if stype == "craft":
					self.evaluate_crafting()

				# Start drag tracking if holding an item stack
				if self.held_stack and self.held_stack[0] != 0 and self.held_stack[1] > 0:
					self.is_dragging = True
					self.drag_button = button
					self.drag_initial_held = list(self.held_stack)
					self.drag_visited_keys = [(stype, sidx)]
					self.drag_slot_snapshots = {(stype, sidx): list(target_slot)}
				return True

		# Clicked outside window -> Drop item into world
		if self.held_stack and self.held_stack[0] != 0 and self.held_stack[1] > 0:
			if hasattr(self.window, "item_drop_manager"):
				px, py, pz = self.window.camera.position
				rad_x = self.window.camera.rotation[0]
				rad_y = self.window.camera.rotation[1]
				vx = math.sin(rad_x) * math.cos(rad_y) * 3.5
				vy = math.sin(rad_y) * 3.5 + 1.2
				vz = -math.cos(rad_x) * math.cos(rad_y) * 3.5

				drop_cnt = 1 if is_right else self.held_stack[1]
				self.window.item_drop_manager.spawn_drop(
					self.held_stack[0], drop_cnt,
					[px, py - 0.4, pz], velocity=[vx, vy, vz]
				)
				self.held_stack[1] -= drop_cnt
				if self.held_stack[1] <= 0:
					self.held_stack = None
			else:
				self.held_stack = None
		return True

	def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
		if not self.inventory_open or not self.is_dragging or not self.held_stack:
			return

		slot_info = self.get_slot_at_pos(x, y)
		if not slot_info or slot_info[0] == "result" or slot_info[0] == "creative":
			return

		stype, sidx, target_slot = slot_info
		key = (stype, sidx)

		b_id = self.held_stack[0]
		if target_slot[0] != 0 and target_slot[0] != b_id:
			return

		if self.drag_button == pyglet.window.mouse.RIGHT:
			if key not in self.drag_visited_keys:
				self.drag_visited_keys.append(key)
				if target_slot[0] == 0 or target_slot[1] == 0:
					target_slot[0] = b_id
					target_slot[1] = 1
					self.held_stack[1] -= 1
				elif target_slot[0] == b_id and target_slot[1] < 64:
					target_slot[1] += 1
					self.held_stack[1] -= 1

				if self.held_stack[1] <= 0:
					self.held_stack = None
					self.is_dragging = False

				if stype == "craft":
					self.evaluate_crafting()
		elif self.drag_button == pyglet.window.mouse.LEFT:
			if key not in self.drag_visited_keys:
				self.drag_visited_keys.append(key)
				self.drag_slot_snapshots[key] = list(target_slot)
				self._update_left_drag()

	def on_mouse_release(self, x, y, button, modifiers):
		self.is_dragging = False
		self.drag_button = None
		self.drag_visited_keys.clear()
		self.drag_slot_snapshots.clear()

	def _swap_slot(self, target_slot, held):
		if held is None or held[0] == 0:
			new_held = list(target_slot)
			target_slot[0] = 0
			target_slot[1] = 0
			return new_held if new_held[0] != 0 else None
		else:
			if target_slot[0] == 0 or target_slot[1] == 0:
				target_slot[0] = held[0]
				target_slot[1] = held[1]
				return None
			elif target_slot[0] == held[0]:
				space = 64 - target_slot[1]
				addable = min(space, held[1])
				target_slot[1] += addable
				held[1] -= addable
				return held if held[1] > 0 else None
			else:
				old_target = list(target_slot)
				target_slot[0] = held[0]
				target_slot[1] = held[1]
				return old_target

	def on_mouse_scroll(self, scroll_y):
		if scroll_y > 0:
			new_slot = (self.selected_slot - 1) % 9
		elif scroll_y < 0:
			new_slot = (self.selected_slot + 1) % 9
		else:
			return
		self.set_selected_slot(new_slot)
