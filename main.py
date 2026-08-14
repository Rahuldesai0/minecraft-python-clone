import os
import math
import random
import ctypes
import pyglet

pyglet.options["shadow_window"] = False
pyglet.options["debug_gl"] = False

import pyglet.gl as gl

import matrix
import shader
import camera

import block_type
import texture_manager

import chunk
import world

import hit

import noise

import gui
import item_drop
import world_save

class Window(pyglet.window.Window):
	def __init__(self, **args):
		super().__init__(**args)

		# create world

		self.world = world.World()
		self.item_drop_manager = item_drop.ItemDropManager(self.world)
		
		# create shader

		self.shader = shader.Shader("vert.glsl", "frag.glsl")
		self.shader_sampler_location = self.shader.find_uniform(b"texture_array_sampler")
		self.shader.use()

		# pyglet stuff

		# Drive streaming at a normal game-update rate.  Scheduling this at 10,000
		# Hz wastes the event loop and does not make chunk generation finish faster.
		pyglet.clock.schedule_interval(self.update, 1.0 / 120)
		self.mouse_captured = False

		# camera stuff
		self.camera = camera.Camera(self.shader, self.width, self.height)

		# other stuff
		self.sprinting = False
		self.flying = False

		# Block Breaking Progress & Animation Tracking
		self.left_mouse_down = False
		self.breaking_block = None
		self.break_progress = 0.0

		# Game States: "MENU", "CREATE_WORLD", "RENAME_WORLD", "LOADING", "PLAYING", "PAUSED", "SETTINGS"
		self.game_state = "MENU"
		self.prev_state = "MENU"
		self.saved_worlds = world_save.list_saved_worlds()
		self.selected_world_index = 0

		self.create_name_text = ""
		self.create_seed_text = ""
		self.create_active_field = "name"

		self.rename_text = ""

		self.active_world_folder = None
		self.world_seed = None
		self.global_render_distance = 6

		self.is_loading_world = False
		self.is_saved_load = False
		self.saved_spawn_y = None
		self.loading_progress = 0.0
		self.loading_status = "Preparing Spawn Region..."
		self.spawn_chunk_queue = []
		self.total_spawn_chunks = 0
		self.loaded_spawn_chunks = 0

		# Inventory & Hotbar GUI System
		self.gui = gui.InventoryGUI(self)
		self.holding = self.gui.get_current_block_id()

		# F3 Debug Overlay & Key Tracking stuff
		self.show_debug = False
		self.fps = 60.0
		self.keys_down = {}
		self.debug_label = pyglet.text.Label(
			"", font_name="Consolas", font_size=11,
			x=10, y=self.height - 10,
			anchor_x="left", anchor_y="top",
			multiline=True, width=500,
			color=(255, 255, 255, 255)
		)

		# Steve 3D Player Model & Perspective System (F5)
		import player_model
		self.player_model = player_model.StevePlayerModel()
		self.perspective = 0  # 0: First Person, 1: Third Person Back, 2: Third Person Front

		# Crosshair stuff
		self.create_crosshair()

	def start_new_world_generation(self, raw_name="", raw_seed=""):
		folder_name = world_save.get_unique_world_name(raw_name)
		self.active_world_folder = folder_name

		text = raw_seed.strip()
		if not text:
			seed_val = random.randint(100000, 999999999)
		elif text.lstrip("-").isdigit():
			seed_val = int(text)
		else:
			seed_val = abs(hash(text)) % 1000000000

		self.world_seed = seed_val
		self.is_saved_load = False

		# Initialize fresh World & ItemDropManager
		self.world = world.World(seed=seed_val, save_folder=folder_name, render_distance=self.global_render_distance)
		self.item_drop_manager = item_drop.ItemDropManager(self.world)

		# Reset camera, player attributes & inventory for fresh world
		self.camera.position = [0, 81.5, 0]
		self.camera.rotation = [0, 0]
		self.camera.velocity_y = 0.0
		self.camera.health = 20
		self.flying = False
		self.sprinting = False

		# Reset GUI inventory to clean default state for the new world
		self.gui.reset_inventory()
		self.holding = self.gui.get_current_block_id()

		self._prepare_spawn_chunks()

	def load_selected_world(self, folder_name):
		w_data = world_save.load_world(folder_name)
		if not w_data:
			return

		self.active_world_folder = folder_name
		self.world_seed = w_data.get('seed', 0)
		self.is_saved_load = True

		rd = w_data.get('world', {}).get('render_distance', self.global_render_distance)
		self.global_render_distance = rd

		self.world = world.World(seed=self.world_seed, save_folder=folder_name, render_distance=rd)
		self.item_drop_manager = item_drop.ItemDropManager(self.world)
		self.world.item_drop_manager = self.item_drop_manager

		# Restore player attributes & flying state
		p_data = w_data.get('player', {})
		self.camera.position = p_data.get('position', [0.5, 80.0, 0.5])
		self.camera.rotation = p_data.get('rotation', [0.0, 0.0])
		self.camera.velocity_y = p_data.get('velocity_y', 0.0)
		self.camera.health = p_data.get('health', 20)
		self.flying = p_data.get('flying', False)
		self.sprinting = p_data.get('sprinting', False)

		# Restore world attributes
		w_info = w_data.get('world', {})
		self.time_of_day = w_info.get('time_of_day', 0.0)

		# Reset & restore inventory for this specific saved world
		self.gui.reset_inventory()
		self.gui.load_inventory_data(w_data.get('inventory', {}))
		self.holding = self.gui.get_current_block_id()

		drops = w_data.get('drops', [])
		self.item_drop_manager.drops.clear()
		for d in drops:
			self.item_drop_manager.spawn_drop(
				d['block_id'], d['count'], d['position'], velocity=d.get('velocity', [0,0,0])
			)

		# Restore Chest Storage Data
		if 'chests' in w_data and w_data['chests']:
			for key_str, slots in w_data['chests'].items():
				parts = [int(p) for p in key_str.split(',')]
				pos_key = (parts[0], parts[1], parts[2])
				c_obj = world.ChestData()
				c_obj.slots = slots
				self.world.chests[pos_key] = c_obj

		# Restore Furnace Storage & Smelting State
		if 'furnaces' in w_data and w_data['furnaces']:
			for key_str, f_dict in w_data['furnaces'].items():
				parts = [int(p) for p in key_str.split(',')]
				pos_key = (parts[0], parts[1], parts[2])
				f_obj = world.FurnaceData()
				f_obj.input_slot = f_dict.get('input_slot', [0, 0])
				f_obj.fuel_slot = f_dict.get('fuel_slot', [0, 0])
				f_obj.output_slot = f_dict.get('output_slot', [0, 0])
				f_obj.burn_time_remaining = f_dict.get('burn_time_remaining', 0.0)
				f_obj.max_burn_time = f_dict.get('max_burn_time', 0.0)
				f_obj.smelt_progress = f_dict.get('smelt_progress', 0.0)
				self.world.furnaces[pos_key] = f_obj

		self._prepare_spawn_chunks()

	def _prepare_spawn_chunks(self):
		spawn_r = getattr(self.world, "render_distance", 6)
		player_cx = math.floor(self.camera.position[0] / chunk.CHUNK_WIDTH)
		player_cz = math.floor(self.camera.position[2] / chunk.CHUNK_LENGTH)

		self.spawn_chunk_queue = []
		for cx in range(player_cx - spawn_r, player_cx + spawn_r + 1):
			for cz in range(player_cz - spawn_r, player_cz + spawn_r + 1):
				if max(abs(cx - player_cx), abs(cz - player_cz)) <= spawn_r:
					self.spawn_chunk_queue.append((cx, cz))

		self.spawn_chunk_queue.sort(key=lambda pos: (pos[0] - player_cx)**2 + (pos[1] - player_cz)**2)

		self.total_spawn_chunks = len(self.spawn_chunk_queue)
		self.loaded_spawn_chunks = 0
		self.loading_progress = 0.0
		self.loading_status = "Preparing Spawn Region..."

		self.is_loading_world = True
		self.game_state = "LOADING"

	def save_and_quit_to_title(self):
		if hasattr(self, 'world') and self.active_world_folder:
			# Save modified dirty chunks to disk
			for cpos in list(self.world.dirty_chunks):
				self.world._save_chunk_to_file(cpos)

			player_data = {
				'position': list(self.camera.position),
				'rotation': list(self.camera.rotation),
				'velocity_y': self.camera.velocity_y,
				'health': self.camera.health,
				'flying': self.flying,
				'sprinting': self.sprinting
			}

			world_data = {
				'time_of_day': self.time_of_day,
				'render_distance': self.world.render_distance
			}

			inventory_data = self.gui.serialize_inventory()

			drops_data = [
				{
					'block_id': d.block_id,
					'count': d.count,
					'position': list(d.position),
					'velocity': list(d.velocity),
					'age': d.age
				}
				for d in self.item_drop_manager.drops
			]

			chests_data = {}
			if hasattr(self.world, 'chests'):
				for (cx, cy, cz), chest_obj in self.world.chests.items():
					chests_data[f"{cx},{cy},{cz}"] = chest_obj.slots

			furnaces_data = {}
			if hasattr(self.world, 'furnaces'):
				for (fx, fy, fz), furnace_obj in self.world.furnaces.items():
					furnaces_data[f"{fx},{fy},{fz}"] = {
						'input_slot': furnace_obj.input_slot,
						'fuel_slot': furnace_obj.fuel_slot,
						'output_slot': furnace_obj.output_slot,
						'burn_time_remaining': furnace_obj.burn_time_remaining,
						'max_burn_time': furnace_obj.max_burn_time,
						'smelt_progress': furnace_obj.smelt_progress
					}

			world_save.save_world(
				self.active_world_folder, self.world_seed,
				player_data, world_data, inventory_data, drops_data,
				chests_data, furnaces_data
			)

		self.mouse_captured = False
		self.set_exclusive_mouse(False)
		self.saved_worlds = world_save.list_saved_worlds()
		self.selected_world_index = 0
		self.game_state = "MENU"

	def create_crosshair(self):
		cx = self.width // 2
		cy = self.height // 2
		self.crosshair_batch = pyglet.graphics.Batch()
		size = 8
		thick = 2
		self.crosshair_h = pyglet.shapes.Rectangle(
			cx - size, cy - thick // 2, size * 2, thick,
			color=(255, 255, 255, 255), batch=self.crosshair_batch
		)
		self.crosshair_v = pyglet.shapes.Rectangle(
			cx - thick // 2, cy - size, thick, size * 2,
			color=(255, 255, 255, 255), batch=self.crosshair_batch
		)

		self.time_of_day = 0.25  # World starts at Sunrise (0.25)
		self.cycle_speed = 1.0 / 1200.0  # Exactly 20-minute full day/night cycle (1200 seconds)

	def update_sky_color(self):
		tod = self.time_of_day % 1.0

		night_c = (0.05, 0.05, 0.12)
		dawn_c  = (0.90, 0.48, 0.22)
		day_c   = (0.50, 0.78, 1.00)
		dusk_c  = (0.85, 0.38, 0.18)

		def lerp(c1, c2, t):
			t = max(0.0, min(1.0, t))
			return (
				c1[0] + (c2[0] - c1[0]) * t,
				c1[1] + (c2[1] - c1[1]) * t,
				c1[2] + (c2[2] - c1[2]) * t,
				1.0
			)

		if tod < 0.20 or tod >= 0.80:
			# Deep Night
			r, g, b, a = night_c[0], night_c[1], night_c[2], 1.0
		elif 0.20 <= tod < 0.25:
			# Night -> Dawn / Sunrise
			r, g, b, a = lerp(night_c, dawn_c, (tod - 0.20) / 0.05)
		elif 0.25 <= tod < 0.30:
			# Dawn / Sunrise -> Day
			r, g, b, a = lerp(dawn_c, day_c, (tod - 0.25) / 0.05)
		elif 0.30 <= tod < 0.70:
			# Full Day
			r, g, b, a = day_c[0], day_c[1], day_c[2], 1.0
		elif 0.70 <= tod < 0.75:
			# Day -> Sunset / Dusk
			r, g, b, a = lerp(day_c, dusk_c, (tod - 0.70) / 0.05)
		else:  # 0.75 <= tod < 0.80
			# Sunset / Dusk -> Night
			r, g, b, a = lerp(dusk_c, night_c, (tod - 0.75) / 0.05)

		gl.glClearColor(r, g, b, a)

	def get_surface_height(self, x=0, z=0):
		"""Find the highest solid block y-coordinate at world column (x, z)."""
		for y in range(255, 0, -1):
			b = self.world.get_block_number((x, y, z))
			if b != 0 and b not in (9, 19, 15, 20):
				return y
		return 64

	def update(self, delta_time):
		if self.is_loading_world:
			batch_size = 5
			for _ in range(batch_size):
				if self.spawn_chunk_queue:
					cx, cz = self.spawn_chunk_queue.pop(0)
					cpos = (cx, 0, cz)
					if cpos not in self.world.chunks:
						chk_bytes = self.world.generate_chunk(cx, cz, blocks_only=True)
						self.world.chunks[cpos] = chunk.Chunk(self.world, cpos, blocks=chk_bytes)
						self.world.queue_chunk_sections_for_meshing(cx, cz)
					self.loaded_spawn_chunks += 1

			self.world.process_load_queue(self.camera.position, player_rotation=self.camera.rotation)

			self.loading_progress = self.loaded_spawn_chunks / self.total_spawn_chunks
			self.loading_status = f"Building Terrain... ({self.loaded_spawn_chunks}/{self.total_spawn_chunks})"

			if not self.spawn_chunk_queue:
				self.is_loading_world = False
				self.game_state = "PLAYING"
				self.mouse_captured = True
				self.set_exclusive_mouse(True)

				# Position player safely 1 block higher if generating a fresh new world
				if not self.is_saved_load:
					spawn_y = self.get_surface_height(0, 0)
					self.camera.position = [0.5, spawn_y + 2.85, 0.5]
					self.camera.velocity_y = 0.0
					self.camera.fall_start_y = None
			return

		if delta_time > 0:
			self.fps = 0.9 * self.fps + 0.1 * (1.0 / delta_time)

		# Clamp delta_time so player movement and physics remain smooth even during background tasks
		delta_time = min(delta_time, 1.0 / 30.0)

		# Update active world mechanics (liquids, furnaces)
		self.world.update(delta_time)

		# Update Steve player model animation
		is_moving = any(self.camera.input) and self.mouse_captured and not self.gui.inventory_open
		is_sneaking = getattr(self.camera, 'sneaking', False)
		is_in_liquid = self.camera.is_in_liquid(self.world)
		holding_item = (self.gui.get_current_block_id() != 0)
		self.player_model.update(
			delta_time, is_moving, self.sprinting, self.left_mouse_down,
			sneaking=is_sneaking, in_liquid=is_in_liquid, holding_item=holding_item
		)

		# Continuous Block Breaking Physics & Progress Accumulation
		if self.left_mouse_down and self.mouse_captured and not self.gui.inventory_open:
			target_block = None
			
			def find_target(current_block, next_block):
				nonlocal target_block
				target_block = next_block
				return True

			hit_ray = hit.Hit_ray(self.world, self.camera.rotation, self.camera.position)
			while hit_ray.distance < hit.HIT_RANGE:
				if hit_ray.step(find_target):
					break

			if target_block:
				b_num = self.world.get_block_number(target_block)
				if 0 < b_num < len(self.world.block_types) and b_num not in (9, 19, 15, 20, 14):
					if self.flying:
						self.break_progress = 1.0
						tool_cat, tool_tier, can_harvest, drop_id = None, 0, False, None
					else:
						# 1. Fetch active tool properties from hotbar
						held_id = self.holding
						tool_info = gui.TOOL_PROPERTIES.get(held_id)
						if tool_info:
							tool_cat, tool_tier, speed_mult = tool_info
						else:
							tool_cat, tool_tier, speed_mult = None, 0, 1.0

						# 2. Fetch block mining specifications
						mining_spec = gui.BLOCK_MINING_PROPERTIES.get(b_num, (None, 0, 0.8, b_num))
						pref_cat, req_tier, base_time, drop_id = mining_spec

						# 3. Calculate effective mining speed & break time
						if tool_cat and tool_cat == pref_cat:
							eff_speed = speed_mult
						else:
							eff_speed = 1.0  # Hand or improper tool

						actual_time = base_time / eff_speed
						can_harvest = (req_tier == 0) or (tool_cat == pref_cat and tool_tier >= req_tier)

						if self.breaking_block == target_block:
							self.break_progress += delta_time / max(0.08, actual_time)
						else:
							self.breaking_block = target_block
							self.break_progress = delta_time / max(0.08, actual_time)

					if self.break_progress >= 1.0:
						# Spawn 3D dropped item entity ONLY if harvested with proper tool tier!
						if not self.flying and can_harvest and drop_id is not None:
							self.item_drop_manager.spawn_drop(
								drop_id, 1,
								[target_block[0] + 0.5, target_block[1] + 0.5, target_block[2] + 0.5]
							)

						self.world.set_block(target_block, 0)
						self.breaking_block = None
						self.break_progress = 0.0
				else:
					self.breaking_block = None
					self.break_progress = 0.0
			else:
				self.breaking_block = None
				self.break_progress = 0.0
		else:
			self.breaking_block = None
			self.break_progress = 0.0

		# Continuously sync horizontal movement vector from physical key states
		dx = 0
		dz = 0
		if self.keys_down.get(pyglet.window.key.D, False): dx += 2
		if self.keys_down.get(pyglet.window.key.A, False): dx -= 2
		if self.keys_down.get(pyglet.window.key.W, False): dz += 2
		if self.keys_down.get(pyglet.window.key.S, False): dz -= 2

		if self.mouse_captured:
			self.camera.input = [dx, 0, dz]
		else:
			self.camera.input = [0, 0, 0]

		self.camera.update_camera(delta_time, self.sprinting, self.world, self.flying, self.keys_down)
		self.item_drop_manager.update(delta_time, self.camera.position, self.gui)
		self.world.update_chunks(self.camera.position)
		self.world.process_load_queue(self.camera.position, player_rotation=self.camera.rotation)
		self.world.tick_liquids()
		self.invalid = True
		
		self.time_of_day += self.cycle_speed * delta_time
		self.time_of_day %= 1.0  # Keep time_of_day in the range [0.0, 1.0]

        # Update the sky color
		self.update_sky_color()
	
	def on_draw(self):
		if self.game_state == "MENU":
			self.clear()
			self.gui.draw_main_menu(self.saved_worlds, self.selected_world_index)
			gl.glFlush()
			return

		if self.game_state == "CREATE_WORLD":
			self.clear()
			self.gui.draw_create_world(self.create_name_text, self.create_seed_text, self.create_active_field)
			gl.glFlush()
			return

		if self.game_state == "RENAME_WORLD":
			self.clear()
			self.gui.draw_rename_world(self.rename_text)
			gl.glFlush()
			return

		if self.game_state == "LOADING" and getattr(self, "is_loading_world", False):
			self.clear()
			self.gui.draw_loading_screen(self.loading_progress, self.loading_status)
			gl.glFlush()
			return

		# Bind 3D world shader FIRST before matrix updates or 3D rendering
		self.shader.use()
		self.camera.update_matrices(self.perspective, self.world)

		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
		gl.glUniform1i(self.shader_sampler_location, 0)

		# 1. Render 3D Overworld Terrain Geometry FIRST
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_CULL_FACE)
		gl.glDepthMask(gl.GL_TRUE)
		self.clear()

		# Draw 3D World Terrain first so terrain is 100% visible and populates depth buffer
		self.world.draw(self.camera.position, player_rotation=self.camera.rotation)

		# If 3rd Person View (Back or Front), render Steve 3D Player Model!
		if self.perspective != 0:
			self.player_model.render_third_person(self.camera, self.perspective, self.world)

		# 2. Render 3D overworld dropped items & 2D item sprites BEFORE 2D overlays
		self.item_drop_manager.draw(self.shader, self.gui)

		# 3. Render 3D Celestial Bodies (Sun & Moon) SECOND behind terrain blocks
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glDepthMask(gl.GL_FALSE)
		self.draw_celestial_bodies()
		gl.glDepthMask(gl.GL_TRUE)

		# If 1st Person View, render Steve's 1st Person 3D Arm using dedicated pipeline!
		if self.perspective == 0 and self.game_state == "PLAYING" and not self.gui.inventory_open:
			self.player_model.render_first_person_arm(
				self.camera,
				self.gui.get_current_block_id(),
				self.gui.icon_textures
			)

		# 4. Render 2D UI overlays (F3 debug, crosshair, mining progress, inventory, menus)
		self.draw_2d_overlays()

		gl.glFlush()

	def draw_celestial_bodies(self):
		if not hasattr(self, "celestial_vao") or self.celestial_vao is None:
			self.celestial_vao = gl.GLuint(0)
			gl.glGenVertexArrays(1, self.celestial_vao)

			self.celestial_vbo_pos = gl.GLuint(0)
			gl.glGenBuffers(1, self.celestial_vbo_pos)

			self.celestial_vbo_tex = gl.GLuint(0)
			gl.glGenBuffers(1, self.celestial_vbo_tex)

			self.celestial_vbo_shading = gl.GLuint(0)
			gl.glGenBuffers(1, self.celestial_vbo_shading)

			self.celestial_ibo = gl.GLuint(0)
			gl.glGenBuffers(1, self.celestial_ibo)

		tod = self.time_of_day % 1.0
		theta = (tod - 0.50) * math.tau

		# Sun & Moon East to West trajectory
		sun_dx = -math.sin(theta)
		sun_dy = math.cos(theta)
		sun_dz = 0.0

		moon_dx = math.sin(theta)
		moon_dy = -math.cos(theta)
		moon_dz = 0.0

		cam_x, cam_y, cam_z = self.camera.position
		R = 380.0

		sun_layer = float(self.world.texture_manager.textures.index("sun")) if "sun" in self.world.texture_manager.textures else 0.0
		moon_layer = float(self.world.texture_manager.textures.index("moon")) if "moon" in self.world.texture_manager.textures else 0.0

		pos_data = []
		tex_data = []
		shading_data = []
		idx_data = []
		v_idx = 0

		def build_celestial_quad(dx, dy, dz, layer, size=45.0, shading_val=1.0):
			nonlocal v_idx
			cx = cam_x + dx * R
			cy = cam_y + dy * R
			cz = cam_z + dz * R

			rx, ry, rz = 0.0, 0.0, size
			ux, uy, uz = dy * size, -dx * size, 0.0

			p0 = (cx - rx + ux, cy - ry + uy, cz - rz + uz)
			p1 = (cx + rx + ux, cy + ry + uy, cz + rz + uz)
			p2 = (cx + rx - ux, cy + ry - uy, cz + rz - uz)
			p3 = (cx - rx - ux, cy - ry - uy, cz - rz - uz)

			for px, py, pz in [p0, p1, p2, p3]:
				pos_data.extend([px, py, pz])

			tex_data.extend([
				0.0, 0.0, layer,
				1.0, 0.0, layer,
				1.0, 1.0, layer,
				0.0, 1.0, layer
			])

			shading_data.extend([shading_val, shading_val, shading_val, shading_val])

			idx_data.extend([
				v_idx, v_idx + 1, v_idx + 2,
				v_idx, v_idx + 2, v_idx + 3
			])
			v_idx += 4

		build_celestial_quad(sun_dx, sun_dy, sun_dz, sun_layer, size=45.0)
		build_celestial_quad(moon_dx, moon_dy, moon_dz, moon_layer, size=40.0)

		# Stars are ONLY drawn during Night (tod < 0.20 or tod >= 0.80)
		# They are completely undrawn (0 geometry) during daytime and sunrise!
		if tod < 0.20 or tod >= 0.80:
			if not hasattr(self, "star_base_dirs"):
				import random
				rng = random.Random(12345)
				self.star_base_dirs = []
				for _ in range(250):
					u = rng.uniform(-1.0, 1.0)
					phi = rng.uniform(0.0, math.tau)
					r_xy = math.sqrt(max(0.0, 1.0 - u * u))
					bx = r_xy * math.cos(phi)
					by = u
					bz = r_xy * math.sin(phi)
					if by < 0.05:
						by = abs(by) + 0.1
					self.star_base_dirs.append((bx, by, bz))

			cos_t = math.cos(theta)
			sin_t = math.sin(theta)

			for bx, by, bz in self.star_base_dirs:
				rx_dir = bx * cos_t - by * sin_t
				ry_dir = bx * sin_t + by * cos_t
				rz_dir = bz
				if ry_dir > 0.05:
					build_celestial_quad(rx_dir, ry_dir, rz_dir, sun_layer, size=1.8, shading_val=1.0)

		gl.glBindVertexArray(self.celestial_vao)

		pos_bytes = (gl.GLfloat * len(pos_data))()
		pos_bytes[:] = pos_data
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.celestial_vbo_pos)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(pos_bytes), pos_bytes, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		tex_bytes = (gl.GLfloat * len(tex_data))()
		tex_bytes[:] = tex_data
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.celestial_vbo_tex)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(tex_bytes), tex_bytes, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		shading_bytes = (gl.GLfloat * len(shading_data))()
		shading_bytes[:] = shading_data
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.celestial_vbo_shading)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(shading_bytes), shading_bytes, gl.GL_STREAM_DRAW)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(2)

		idx_bytes = (gl.GLuint * len(idx_data))()
		idx_bytes[:] = idx_data
		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.celestial_ibo)
		gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, ctypes.sizeof(idx_bytes), idx_bytes, gl.GL_STREAM_DRAW)

		gl.glDisable(gl.GL_CULL_FACE)
		gl.glDepthMask(gl.GL_FALSE)

		gl.glDrawElements(gl.GL_TRIANGLES, len(idx_data), gl.GL_UNSIGNED_INT, 0)

		gl.glDepthMask(gl.GL_TRUE)
		gl.glEnable(gl.GL_CULL_FACE)
		gl.glBindVertexArray(0)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, 0)

	def draw_2d_overlays(self):
		gl.glDepthMask(gl.GL_FALSE)

		# 2. Render 2D F3 Debug Text Overlay over the 3D World
		if self.show_debug:
			x, y, z = self.camera.position
			wx, wy, wz = int(round(x)), int(round(y)), int(round(z))
			cx, cz = math.floor(x / 16.0), math.floor(z / 16.0)

			cont = noise.pnoise2(wx / 350.0, wz / 350.0, octaves=3)
			erosion = noise.pnoise2((wx + 1000.0) / 300.0, (wz + 1000.0) / 300.0, octaves=3)
			peaks = noise.pnoise2((wx + 1000.0) / 120.0, (wz + 1000.0) / 120.0, octaves=4)
			river = abs(noise.pnoise2((wx + 2000.0) / 240.0, (wz + 2000.0) / 240.0, octaves=3))

			if wy > 110:
				biome = "Snow-Capped Cone Mountain Peak (Y>110)"
			elif wy > 88:
				biome = "High Mountain Range (Y>88)"
			elif cont < -0.10:
				biome = "Deep Ocean"
			elif cont < 0.10:
				biome = "Beach / Coast"
			elif cont < 0.20:
				biome = "Grassy Plains / Hills"
			else:
				biome = "Mountain Massif"

			fps = self.fps

			debug_lines = [
				f"Minecraft Clone Debug (F3)",
				f"FPS: {fps:.1f}",
				f"Seed: {self.world.seed}",
				"",
				f"XYZ: {x:.3f} / {y:.3f} / {z:.3f}",
				f"Block: {wx} {wy} {wz}",
				f"Chunk: {cx} {cz} (loaded: {len(self.world.chunks)})",
				"",
				f"Terrain Noise Variables:",
				f" - Continentalness: {cont:+.4f}",
				f" - Erosion:        {erosion:+.4f}",
				f" - Peaks/Ridges:   {peaks:+.4f}",
				f" - River Noise:    {river:+.4f}",
				f" - Biome:          {biome}",
				f" - Flying:         {self.flying}",
				f" - Sprinting:      {self.sprinting}"
			]

			gl.glDisable(gl.GL_DEPTH_TEST)
			gl.glDisable(gl.GL_CULL_FACE)

			self.debug_label.text = "\n".join(debug_lines)
			self.debug_label.y = self.height - 10
			self.debug_label.draw()

			# Re-enable 3D states & restore 3D shader for next frame
			gl.glEnable(gl.GL_DEPTH_TEST)
			gl.glEnable(gl.GL_CULL_FACE)
			self.shader.use()

		# 3. Draw inverse color crosshair (+) at screen center when mouse is captured
		if self.mouse_captured:
			gl.glEnable(gl.GL_BLEND)
			gl.glBlendFunc(gl.GL_ONE_MINUS_DST_COLOR, gl.GL_ZERO)
			gl.glDisable(gl.GL_DEPTH_TEST)
			gl.glDisable(gl.GL_CULL_FACE)

			self.crosshair_batch.draw()

			# Restore standard alpha blending
			gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		# 4. Render sleek Mining Progress Bar overlay right below crosshair
		self.draw_breaking_overlay()

		# 4. Render 2D Hotbar & Inventory GUI Overlay
		self.gui.draw()

		# Render Pause & Settings overlays
		if self.game_state == "PAUSED":
			self.gui.draw_pause_menu()
		elif self.game_state == "SETTINGS":
			rd = getattr(self.world, "render_distance", self.global_render_distance) if hasattr(self, "world") else self.global_render_distance
			self.gui.draw_settings_menu(rd)

		gl.glDepthMask(gl.GL_TRUE)

	def draw_breaking_overlay(self):
		if not self.breaking_block or self.break_progress <= 0:
			return

		cx = self.width // 2
		cy = self.height // 2 - 22

		w = 52
		h = 8
		pad = 1

		# Render sleek Mining Progress Bar right below crosshair
		gl.glDisable(gl.GL_DEPTH_TEST)
		gl.glDisable(gl.GL_CULL_FACE)
		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		gui.draw_bordered_box(cx - w // 2, cy, w, h, pad, (10, 10, 15, 230), (200, 200, 220, 255))

		fill_w = max(1, int((w - 2 * pad) * min(1.0, self.break_progress)))
		fill_bar = pyglet.shapes.Rectangle(cx - w // 2 + pad, cy + pad, fill_w, h - 2 * pad, color=(255, 180, 0, 240))
		fill_bar.draw()

		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_CULL_FACE)
		self.shader.use()

	# input functions

	def on_close(self):
		if self.game_state in ("PLAYING", "PAUSED", "SETTINGS") and getattr(self, "is_loading_world", False) is False:
			self.save_and_quit_to_title()
		super().on_close()

	def on_resize(self, width, height):
		gl.glViewport(0, 0, width, height)

		self.camera.width = width
		self.camera.height = height
		self.create_crosshair()

	def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
		self.gui.on_mouse_scroll(scroll_y)
	
	def on_text(self, text):
		if self.game_state == "CREATE_WORLD":
			if self.create_active_field == "name":
				if len(self.create_name_text) < 24 and (text.isalnum() or text in " -_()"):
					self.create_name_text += text
			elif self.create_active_field == "seed":
				if len(self.create_seed_text) < 20 and (text.isalnum() or text in "-_ "):
					self.create_seed_text += text
		elif self.game_state == "RENAME_WORLD":
			if len(self.rename_text) < 24 and (text.isalnum() or text in " -_()"):
				self.rename_text += text

	def on_mouse_press(self, x, y, button, modifiers):
		self.gui.mouse_x = x
		self.gui.mouse_y = y

		cx = self.width // 2
		cy = self.height // 2

		if self.game_state == "MENU":
			# Saved Worlds List Item Selection
			list_w = 460
			list_h = 240
			list_y = cy + 20
			item_h = 52
			start_y = list_y + list_h // 2 - 32

			for idx in range(min(4, len(self.saved_worlds))):
				item_cy = start_y - idx * (item_h + 4)
				if (cx - (list_w - 20) // 2 <= x <= cx + (list_w - 20) // 2) and (item_cy - item_h // 2 <= y <= item_cy + item_h // 2):
					self.selected_world_index = idx
					return

			btn_y = cy - 140
			btn_w = 210
			btn_h = 38

			# Play Selected World
			if (cx - btn_w - 10 <= x <= cx - 10) and (btn_y <= y <= btn_y + btn_h):
				if self.saved_worlds:
					self.load_selected_world(self.saved_worlds[self.selected_world_index]['folder_name'])
				return

			# Create New World
			if (cx + 10 <= x <= cx + btn_w + 10) and (btn_y <= y <= btn_y + btn_h):
				self.game_state = "CREATE_WORLD"
				self.create_name_text = ""
				self.create_seed_text = ""
				self.create_active_field = "name"
				return

			btn2_y = cy - 190
			btn2_w = 140
			btn2_h = 32

			# Rename World
			if (cx - btn2_w - 10 <= x <= cx - 10) and (btn2_y <= y <= btn2_y + btn2_h):
				if self.saved_worlds:
					self.game_state = "RENAME_WORLD"
					self.rename_text = self.saved_worlds[self.selected_world_index]['name']
				return

			# Delete World
			if (cx + 10 <= x <= cx + btn2_w + 10) and (btn2_y <= y <= btn2_y + btn2_h):
				if self.saved_worlds:
					w_folder = self.saved_worlds[self.selected_world_index]['folder_name']
					world_save.delete_world(w_folder)
					self.saved_worlds = world_save.list_saved_worlds()
					self.selected_world_index = 0
				return

			return

		if self.game_state == "CREATE_WORLD":
			box_w = 340
			box_h = 32
			# Name box click
			if (cx - box_w // 2 <= x <= cx + box_w // 2) and (cy + 30 <= y <= cy + 30 + box_h):
				self.create_active_field = "name"
				return
			# Seed box click
			if (cx - box_w // 2 <= x <= cx + box_w // 2) and (cy - 60 <= y <= cy - 60 + box_h):
				self.create_active_field = "seed"
				return

			btn_y = cy - 130
			btn1_w = 180
			btn1_h = 38
			# Create World button
			if (cx - btn1_w - 10 <= x <= cx - 10) and (btn_y <= y <= btn_y + btn1_h):
				self.start_new_world_generation(self.create_name_text, self.create_seed_text)
				return

			cancel_w = 120
			# Cancel button
			if (cx + 10 <= x <= cx + cancel_w + 10) and (btn_y <= y <= btn_y + btn1_h):
				self.game_state = "MENU"
				return

			return

		if self.game_state == "RENAME_WORLD":
			btn_y = cy - 60
			btn_w = 160
			btn_h = 38

			# Save Name button
			if (cx - btn_w - 10 <= x <= cx - 10) and (btn_y <= y <= btn_y + btn_h):
				if self.saved_worlds:
					old_folder = self.saved_worlds[self.selected_world_index]['folder_name']
					world_save.rename_world(old_folder, self.rename_text)
					self.saved_worlds = world_save.list_saved_worlds()
					self.selected_world_index = 0
				self.game_state = "MENU"
				return

			cancel_w = 120
			# Cancel button
			if (cx + 10 <= x <= cx + cancel_w + 10) and (btn_y <= y <= btn_y + btn_h):
				self.game_state = "MENU"
				return

			return

		if self.game_state == "PAUSED":
			btn_w = 240
			btn_h = 40

			# 1. Back to Game
			b1_y = cy + 30
			if (cx - btn_w // 2 <= x <= cx + btn_w // 2) and (b1_y - btn_h // 2 <= y <= b1_y + btn_h // 2):
				self.game_state = "PLAYING"
				self.mouse_captured = True
				self.set_exclusive_mouse(True)
				return

			# 2. Settings
			b2_y = cy - 25
			if (cx - btn_w // 2 <= x <= cx + btn_w // 2) and (b2_y - btn_h // 2 <= y <= b2_y + btn_h // 2):
				self.prev_state = "PAUSED"
				self.game_state = "SETTINGS"
				return

			# 3. Save and Quit to Title
			b3_y = cy - 80
			if (cx - btn_w // 2 <= x <= cx + btn_w // 2) and (b3_y - btn_h // 2 <= y <= b3_y + btn_h // 2):
				self.save_and_quit_to_title()
				return

			return

		if self.game_state == "SETTINGS":
			ctrl_w = 320
			ctrl_h = 44
			ctrl_y = cy + 20
			minus_w = 40
			plus_w = 40

			# Minus Button
			if (cx - ctrl_w // 2 - minus_w - 10 <= x <= cx - ctrl_w // 2 - 10) and (ctrl_y - ctrl_h // 2 <= y <= ctrl_y + ctrl_h // 2):
				self.global_render_distance = max(2, self.global_render_distance - 1)
				if hasattr(self, "world"):
					self.world.set_render_distance(self.global_render_distance)
				return

			# Plus Button
			if (cx + ctrl_w // 2 + 10 <= x <= cx + ctrl_w // 2 + plus_w + 10) and (ctrl_y - ctrl_h // 2 <= y <= ctrl_y + ctrl_h // 2):
				self.global_render_distance = min(12, self.global_render_distance + 1)
				if hasattr(self, "world"):
					self.world.set_render_distance(self.global_render_distance)
				return

			# Done Button
			done_w = 180
			done_h = 38
			done_y = cy - 60
			if (cx - done_w // 2 <= x <= cx + done_w // 2) and (done_y - done_h // 2 <= y <= done_y + done_h // 2):
				self.game_state = self.prev_state if hasattr(self, "prev_state") else "MENU"
				if self.game_state == "PLAYING":
					self.mouse_captured = True
					self.set_exclusive_mouse(True)
				return

			return

		if self.game_state == "LOADING":
			return

		if self.gui.inventory_open:
			if self.gui.on_mouse_press(x, y, button, modifiers):
				return

		if not self.mouse_captured:
			self.mouse_captured = True
			self.set_exclusive_mouse(True)
			return

		if button == pyglet.window.mouse.LEFT:
			self.left_mouse_down = True

		self.holding = self.gui.get_current_block_id()
		is_shift_down = bool(modifiers & pyglet.window.key.MOD_SHIFT) or self.keys_down.get(pyglet.window.key.LSHIFT, False) or self.keys_down.get(pyglet.window.key.RSHIFT, False)
		is_placeable = (0 < self.holding < 100)
		INTERACTIVE_BLOCKS = (26, 27, 37)  # Crafting Table, Furnace, Chest, etc.

		def hit_callback(current_block, next_block):
			if self.world.get_block_number(current_block) != 14 and 0 <= current_block[1] < 256:
				if button == pyglet.window.mouse.RIGHT:
					target_b = self.world.get_block_number(next_block)
					if target_b in INTERACTIVE_BLOCKS:
						if is_shift_down and is_placeable and not self.camera.intersects_player(current_block):
							# Shift + Right Click while holding placeable block -> OVERRIDE GUI AND PLACE BLOCK!
							self.world.set_block(current_block, self.holding)
							self.gui.consume_active_item()
							self.holding = self.gui.get_current_block_id()
							return
						else:
							# Normal Right Click OR Shift-Right Click with non-placeable item -> Open GUI!
							if target_b == 26:
								self.gui.open_crafting_table()
							elif target_b == 27:
								self.gui.open_furnace(self.world.get_furnace(next_block))
							elif target_b == 37:
								self.gui.open_chest(next_block, self.world)
							return

					if is_placeable and not self.camera.intersects_player(current_block):
						self.world.set_block(current_block, self.holding)
						self.gui.consume_active_item()
						self.holding = self.gui.get_current_block_id()
				elif button == pyglet.window.mouse.MIDDLE:
					target_b = self.world.get_block_number(next_block)
					if target_b not in (9, 19, 15, 20):
						if self.flying:
							self.gui.hotbar_slots[self.gui.selected_slot] = [target_b, 64]
						else:
							for i, slot in enumerate(self.gui.hotbar_slots):
								if slot[0] == target_b and slot[1] > 0:
									self.gui.set_selected_slot(i)
									break
						self.holding = self.gui.get_current_block_id()
		
		hit_ray = hit.Hit_ray(self.world, self.camera.rotation, self.camera.position)
		while hit_ray.distance < hit.HIT_RANGE:
			if hit_ray.step(hit_callback):
				break

	def on_mouse_release(self, x, y, button, modifiers):
		if self.gui.inventory_open:
			self.gui.on_mouse_release(x, y, button, modifiers)
		if button == pyglet.window.mouse.LEFT:
			self.left_mouse_down = False
			self.breaking_block = None
			self.break_progress = 0.0
	
	def on_mouse_motion(self, x, y, delta_x, delta_y):
		self.gui.mouse_x = x
		self.gui.mouse_y = y

		if self.mouse_captured:
			sensitivity = 0.004

			self.camera.rotation[0] += delta_x * sensitivity
			self.camera.rotation[1] += delta_y * sensitivity

			self.camera.rotation[1] = max(-math.tau / 4, min(math.tau / 4, self.camera.rotation[1]))
	
	def on_mouse_drag(self, x, y, delta_x, delta_y, buttons, modifiers):
		self.gui.mouse_x = x
		self.gui.mouse_y = y
		if self.gui.inventory_open:
			self.gui.on_mouse_drag(x, y, delta_x, delta_y, buttons, modifiers)
		else:
			self.on_mouse_motion(x, y, delta_x, delta_y)

	def on_key_press(self, key, modifiers):
		self.keys_down[key] = True

		if self.game_state == "MENU":
			if key in (pyglet.window.key.ENTER, pyglet.window.key.RETURN):
				if self.saved_worlds:
					self.load_selected_world(self.saved_worlds[self.selected_world_index]['folder_name'])
				return
			return

		if self.game_state == "CREATE_WORLD":
			if key == pyglet.window.key.BACKSPACE:
				if self.create_active_field == "name":
					self.create_name_text = self.create_name_text[:-1]
				else:
					self.create_seed_text = self.create_seed_text[:-1]
				return
			elif key == pyglet.window.key.TAB:
				self.create_active_field = "seed" if self.create_active_field == "name" else "name"
				return
			elif key in (pyglet.window.key.ENTER, pyglet.window.key.RETURN):
				self.start_new_world_generation(self.create_name_text, self.create_seed_text)
				return
			elif key == pyglet.window.key.ESCAPE:
				self.game_state = "MENU"
				return
			return

		if self.game_state == "RENAME_WORLD":
			if key == pyglet.window.key.BACKSPACE:
				self.rename_text = self.rename_text[:-1]
				return
			elif key in (pyglet.window.key.ENTER, pyglet.window.key.RETURN):
				if self.saved_worlds:
					old_folder = self.saved_worlds[self.selected_world_index]['folder_name']
					world_save.rename_world(old_folder, self.rename_text)
					self.saved_worlds = world_save.list_saved_worlds()
					self.selected_world_index = 0
				self.game_state = "MENU"
				return
			elif key == pyglet.window.key.ESCAPE:
				self.game_state = "MENU"
				return
			return

		if self.game_state == "PAUSED":
			if key == pyglet.window.key.ESCAPE:
				self.game_state = "PLAYING"
				self.mouse_captured = True
				self.set_exclusive_mouse(True)
				return
			return

		if self.game_state == "SETTINGS":
			if key == pyglet.window.key.ESCAPE:
				self.game_state = self.prev_state if hasattr(self, "prev_state") else "MENU"
				if self.game_state == "PLAYING":
					self.mouse_captured = True
					self.set_exclusive_mouse(True)
				return
			return

		if self.game_state == "LOADING":
			return

		if key == pyglet.window.key.F3:
			self.show_debug = not self.show_debug

		if key == pyglet.window.key.F5:
			self.perspective = (self.perspective + 1) % 3
			return

		# ESC Key handling in PLAYING state
		if key == pyglet.window.key.ESCAPE:
			if self.gui.inventory_open:
				self.gui.toggle_inventory()
			else:
				self.game_state = "PAUSED"
				self.mouse_captured = False
				self.set_exclusive_mouse(False)
			return

		# Number Keys 1 to 9
		if pyglet.window.key._1 <= key <= pyglet.window.key._9:
			slot_idx = key - pyglet.window.key._1
			self.gui.set_selected_slot(slot_idx)
			return
		elif pyglet.window.key.NUM_1 <= key <= pyglet.window.key.NUM_9:
			slot_idx = key - pyglet.window.key.NUM_1
			self.gui.set_selected_slot(slot_idx)
			return

		# E Key toggles Inventory
		if key == pyglet.window.key.E:
			self.gui.toggle_inventory()
			return

		# Q Key drops items
		if key == pyglet.window.key.Q and not self.gui.inventory_open:
			slot = self.gui.hotbar_slots[self.gui.selected_slot]
			if slot[0] != 0 and slot[1] > 0:
				px, py, pz = self.camera.position
				rad_x, rad_y = self.camera.rotation
				dir_x = math.cos(rad_x) * math.cos(rad_y)
				dir_y = math.sin(rad_y)
				dir_z = math.sin(rad_x) * math.cos(rad_y)

				vx = dir_x * 4.0
				vy = dir_y * 4.0 + 1.5
				vz = dir_z * 4.0

				is_ctrl = bool(modifiers & pyglet.window.key.MOD_CTRL) or self.keys_down.get(pyglet.window.key.LCTRL, False) or self.keys_down.get(pyglet.window.key.RCTRL, False)
				drop_cnt = slot[1] if is_ctrl else 1

				drop_pos = [px + dir_x * 0.5, py - 0.3 + dir_y * 0.5, pz + dir_z * 0.5]
				self.item_drop_manager.spawn_drop(
					slot[0], drop_cnt,
					drop_pos, velocity=[vx, vy, vz]
				)

				slot[1] -= drop_cnt
				if slot[1] <= 0:
					slot[0] = 0
				self.holding = self.gui.get_current_block_id()
			return

		if not self.mouse_captured:
			return

		if key == pyglet.window.key.LCTRL: 
			self.sprinting = True
		elif key == pyglet.window.key.R: 
			self.camera.position = [0, 80, 0]
		elif key == pyglet.window.key.F: 
			self.flying = not self.flying

	def on_key_release(self, key, modifiers):
		self.keys_down[key] = False

		if key == pyglet.window.key.LCTRL:
			self.sprinting = False

class Game:
	def __init__(self):
		self.config = gl.Config(major_version = 3, depth_size = 16)
		self.window = Window(config = self.config, width = 800, height = 600, caption = "Minecraft clone", resizable = True, vsync = False)
	
	def run(self):
		pyglet.app.run()

if __name__ == "__main__":
	game = Game()
	game.run()
