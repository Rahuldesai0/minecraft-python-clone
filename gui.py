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
]

ALL_ITEMS = PALETTE_ITEMS + TOOL_ITEMS
BLOCK_INFO = {item[0]: (item[1], item[2]) for item in ALL_ITEMS}

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

		# Creative hotbar starts with full stacks of 64
		self.creative_hotbar = [[2, 64], [4, 64], [5, 64], [1, 64], [7, 64], [8, 64], [6, 64], [21, 64], [9, 64]]
		
		# Survival hotbar & inventory start completely empty [0, 0]
		self.survival_hotbar = [[0, 0] for _ in range(9)]
		self.survival_inventory = [[0, 0] for _ in range(27)]

		# Crafting System Grid (3x3) & Result Slot
		self.crafting_grid = [[0, 0] for _ in range(9)]
		self.crafting_result = [0, 0]

		self.selected_slot = 0  # 0 to 8
		self.held_stack = None  # [block_id, count] or None

		self.mouse_x = 0
		self.mouse_y = 0

		self.icon_textures = {}
		self._load_icons()

		self.tooltip_label = pyglet.text.Label(
			"", font_name="Arial", font_size=11,
			x=0, y=0, anchor_x="center", anchor_y="bottom",
			color=(255, 255, 255, 255)
		)

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

	def evaluate_crafting(self):
		"""Evaluate 3x3 crafting grid and set self.crafting_result."""
		grid_ids = [slot[0] for slot in self.crafting_grid]
		
		rows = []
		cols = []
		for r in range(3):
			for c in range(3):
				if grid_ids[r * 3 + c] != 0:
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
				row.append(grid_ids[r * 3 + c])
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

		# Recipe 4: Pickaxes (3 top items + 2 vertical sticks)
		if h == 3 and w == 3:
			top = matrix[0]
			center_col = [matrix[0][1], matrix[1][1], matrix[2][1]]
			if center_col[1] == 100 and center_col[2] == 100 and matrix[1][0] == 0 and matrix[1][2] == 0 and matrix[2][0] == 0 and matrix[2][2] == 0:
				mat = top[0]
				if top == [mat, mat, mat]:
					if mat == 7: self.crafting_result = [101, 1]; return   # Wood Pickaxe
					if mat == 1: self.crafting_result = [102, 1]; return   # Stone Pickaxe
					if mat == 17: self.crafting_result = [103, 1]; return  # Iron Pickaxe
					if mat == 18: self.crafting_result = [104, 1]; return  # Diamond Pickaxe
					if mat == 35: self.crafting_result = [117, 1]; return  # Gold Pickaxe

		# Recipe 5: Axes (2x3 shape)
		if h == 3 and w == 2:
			mat = matrix[0][0]
			if matrix[0][1] == mat and matrix[1][0] == mat and matrix[1][1] == 100 and matrix[2][1] == 100 and matrix[2][0] == 0:
				if mat == 7: self.crafting_result = [105, 1]; return   # Wood Axe
				if mat == 1: self.crafting_result = [106, 1]; return   # Stone Axe
				if mat == 17: self.crafting_result = [107, 1]; return  # Iron Axe
				if mat == 18: self.crafting_result = [108, 1]; return  # Diamond Axe
				if mat == 35: self.crafting_result = [118, 1]; return  # Gold Axe

		# Recipe 6: Shovels (1x3 shape: 1 head item + 2 sticks)
		if h == 3 and w == 1:
			mat = matrix[0][0]
			if matrix[1][0] == 100 and matrix[2][0] == 100:
				if mat == 7: self.crafting_result = [109, 1]; return   # Wood Shovel
				if mat == 1: self.crafting_result = [110, 1]; return   # Stone Shovel
				if mat == 17: self.crafting_result = [111, 1]; return  # Iron Shovel
				if mat == 18: self.crafting_result = [112, 1]; return  # Diamond Shovel
				if mat == 35: self.crafting_result = [119, 1]; return  # Gold Shovel

		# Recipe 7: Swords (1x3 shape: 2 blade items + 1 stick)
		if h == 3 and w == 1:
			mat = matrix[0][0]
			if matrix[1][0] == mat and matrix[2][0] == 100:
				if mat == 7: self.crafting_result = [113, 1]; return   # Wood Sword
				if mat == 1: self.crafting_result = [114, 1]; return   # Stone Sword
				if mat == 17: self.crafting_result = [115, 1]; return  # Iron Sword
				if mat == 18: self.crafting_result = [116, 1]; return  # Diamond Sword
				if mat == 35: self.crafting_result = [120, 1]; return  # Gold Sword

		self.crafting_result = [0, 0]

	def set_selected_slot(self, slot_idx):
		if 0 <= slot_idx < 9:
			self.selected_slot = slot_idx
			self.window.holding = self.get_current_block_id()

	def toggle_inventory(self):
		self.inventory_open = not self.inventory_open
		if self.inventory_open:
			self.window.mouse_captured = False
			self.window.set_exclusive_mouse(False)
		else:
			# Return ingredients left in crafting grid to inventory when closing
			for slot in self.crafting_grid:
				if slot[0] != 0 and slot[1] > 0:
					self.add_item(slot[0], slot[1])
					slot[0] = 0
					slot[1] = 0
			self.crafting_result = [0, 0]
			self.held_stack = None
			self.window.mouse_captured = True
			self.window.set_exclusive_mouse(True)

	def draw(self):
		gl.glDisable(gl.GL_DEPTH_TEST)
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

	def _draw_inventory_overlay(self, current_hover):
		veil = pyglet.shapes.Rectangle(0, 0, self.window.width, self.window.height, color=(0, 0, 0, 160))
		veil.draw()

		win_w = 640
		win_h = 460
		win_x = (self.window.width - win_w) // 2
		win_y = (self.window.height - win_h) // 2

		draw_bordered_box(win_x, win_y, win_w, win_h, 2, (20, 22, 28, 240), (180, 180, 200, 255))

		mode_str = "Creative Item Palette" if self.window.flying else "Survival Inventory & Crafting"
		title = pyglet.text.Label(f"Inventory ({mode_str})", font_name="Arial", font_size=15, x=win_x + 20, y=win_y + win_h - 24, color=(255, 255, 255, 255))
		title.draw()

		sub_text = "Click an item to get a stack of 64." if self.window.flying else "Crafting: Place items in 3x3 Grid -> Click Result Slot to claim!"
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
		else:
			# Survival 3x3 Crafting Grid & Output Slot (Top Half)
			craft_lbl = pyglet.text.Label("Crafting Table Grid (3x3):", font_name="Arial", font_size=10, x=win_x + 24, y=win_y + win_h - 68, color=(220, 220, 240, 255))
			craft_lbl.draw()

			cg_x = win_x + 24
			cg_y = win_y + win_h - 180

			for r in range(3):
				for c in range(3):
					idx = r * 3 + c
					sx = cg_x + c * (slot_s + pad)
					sy = cg_y + (2 - r) * (slot_s + pad)

					is_h = (sx <= self.mouse_x <= sx + slot_s and sy <= self.mouse_y <= sy + slot_s)
					bg_c = (55, 60, 75, 230) if is_h else (35, 38, 48, 200)
					border_c = (255, 215, 0, 255) if is_h else (70, 75, 90, 200)

					draw_bordered_box(sx, sy, slot_s, slot_s, 2 if is_h else 1, bg_c, border_c)

					slot = self.crafting_grid[idx]
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
			arr_lbl = pyglet.text.Label("==>", font_name="Arial", font_size=16, x=cg_x + 3 * (slot_s + pad) + 10, y=cg_y + slot_s + 4, color=(255, 215, 0, 255))
			arr_lbl.draw()

			res_x = cg_x + 3 * (slot_s + pad) + 60
			res_y = cg_y + slot_s

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

		is_right = (button == pyglet.window.mouse.RIGHT)

		slot_s = 40
		pad = 6
		win_w = 640
		win_h = 460
		win_x = (self.window.width - win_w) // 2
		win_y = (self.window.height - win_h) // 2

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
					self.held_stack = [b_id, 64 if not is_right else 1]
					return True
		else:
			# Survival Crafting 3x3 Grid Clicks
			cg_x = win_x + 24
			cg_y = win_y + win_h - 180

			for r in range(3):
				for c in range(3):
					idx = r * 3 + c
					sx = cg_x + c * (slot_s + pad)
					sy = cg_y + (2 - r) * (slot_s + pad)

					if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
						self.handle_slot_click(self.crafting_grid[idx], is_right)
						self.evaluate_crafting()
						return True

			# Survival Crafting Result Slot Click
			res_x = cg_x + 3 * (slot_s + pad) + 60
			res_y = cg_y + slot_s

			if res_x <= x <= res_x + slot_s + 8 and res_y <= y <= res_y + slot_s + 8:
				rb_id, rcnt = self.crafting_result[0], self.crafting_result[1]
				if rb_id != 0 and rcnt > 0:
					if self.held_stack is None:
						self.held_stack = [rb_id, rcnt]
					elif self.held_stack[0] == rb_id and self.held_stack[1] + rcnt <= 64:
						self.held_stack[1] += rcnt
					else:
						return True

					for slot in self.crafting_grid:
						if slot[0] != 0 and slot[1] > 0:
							slot[1] -= 1
							if slot[1] == 0:
								slot[0] = 0

					self.evaluate_crafting()
					return True

			# Survival 27-slot Storage Grid Clicks
			cols = 9
			grid_x = win_x + (win_w - (cols * slot_s + (cols - 1) * pad)) // 2
			grid_y = win_y + 145

			for idx in range(27):
				r = idx // cols
				c = idx % cols
				sx = grid_x + c * (slot_s + pad)
				sy = grid_y - r * (slot_s + pad)

				if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
					self.handle_slot_click(self.survival_inventory[idx], is_right)
					return True

		# Hotbar row clicks inside Inventory Window
		hb_x = win_x + (win_w - (9 * slot_s + 8 * pad)) // 2
		hb_y = win_y + 12

		for i in range(9):
			sx = hb_x + i * (slot_s + pad)
			sy = hb_y

			if sx <= x <= sx + slot_s and sy <= y <= sy + slot_s:
				if self.window.flying:
					if self.held_stack:
						self.hotbar_slots[i] = [self.held_stack[0], 64]
						self.set_selected_slot(i)
						self.held_stack = None
					else:
						self.set_selected_slot(i)
				else:
					self.handle_slot_click(self.survival_hotbar[i], is_right)
					self.set_selected_slot(i)
				return True

		# Clicked outside inventory window -> Drop held items into overworld!
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
