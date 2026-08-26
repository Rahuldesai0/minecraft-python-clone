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
import mob_manager
import arrow
import world_save
import tnt_manager
import explosion
import ender_eye
import ender_pearl
import experience_bottle

class Window(pyglet.window.Window):
	def __init__(self, **args):
		super().__init__(**args)

		# create world

		self.world = world.World()
		self.dimension = "overworld"
		self.overworld = self.world
		self.nether_world = None
		self.dimension_transitioning = False
		self.item_drop_manager = item_drop.ItemDropManager(self.world)
		self.world.item_drop_manager = self.item_drop_manager
		self.mob_manager = mob_manager.MobManager(self.world)
		self.arrow_manager = arrow.ArrowManager(self.world)
		self.tnt_manager = tnt_manager.TNTManager(self.world)
		self.world.tnt_manager = self.tnt_manager
		self.ender_eye_manager = ender_eye.EnderEyeManager(self.world)
		self.ender_pearl_manager = ender_pearl.EnderPearlManager(self.world)
		self.world.ender_pearl_manager = self.ender_pearl_manager
		self.exp_bottle_manager = experience_bottle.ExperienceBottleManager(self.world)
		self.world.exp_bottle_manager = self.exp_bottle_manager
		self.ender_pearl_cooldown = 0.0
		self.bow_charging = False
		self.bow_charge_time = 0.0
		
		# create shader

		self.shader = shader.Shader("vert.glsl", "frag.glsl")
		self.shader_sampler_location = self.shader.find_uniform(b"texture_array_sampler")
		self.shader.use()

		# pyglet stuff

		# Drive game updates at a clean 60 Hz target rate.
		pyglet.clock.schedule_interval(self.update, 1.0 / 60.0)
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
		self.camera.gui = self.gui
		self.camera.window = self
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
		self.break_progress_bar = pyglet.shapes.Rectangle(0, 0, 1, 1, color=(255, 180, 0, 240))

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

		# Fresh worlds ALWAYS start at Sunrise (0.25)
		self.time_of_day = 0.25
		self.update_sky_color()

		# Initialize fresh World, ItemDropManager & MobManager
		self.world = world.World(seed=seed_val, save_folder=folder_name, render_distance=self.global_render_distance)
		self.dimension = "overworld"
		self.overworld = self.world
		self.nether_world = None
		self.item_drop_manager = item_drop.ItemDropManager(self.world)
		self.world.item_drop_manager = self.item_drop_manager
		self.mob_manager = mob_manager.MobManager(self.world)
		self.world.mob_manager = self.mob_manager
		self.arrow_manager = arrow.ArrowManager(self.world)
		self.world.arrow_manager = self.arrow_manager
		self.tnt_manager = tnt_manager.TNTManager(self.world)
		self.world.tnt_manager = self.tnt_manager
		self.ender_eye_manager = ender_eye.EnderEyeManager(self.world)
		self.world.ender_eye_manager = self.ender_eye_manager
		self.ender_pearl_manager = ender_pearl.EnderPearlManager(self.world)
		self.world.ender_pearl_manager = self.ender_pearl_manager
		self.exp_bottle_manager = experience_bottle.ExperienceBottleManager(self.world)
		self.world.exp_bottle_manager = self.exp_bottle_manager
		self.ender_pearl_cooldown = 0.0
		self.bow_charging = False
		self.bow_charge_time = 0.0

		# Reset camera, player attributes & inventory for fresh world
		self.camera.position = [0, 81.5, 0]
		self.camera.rotation = [0, 0]
		self.camera.velocity_y = 0.0
		self.camera.health = 20
		self.camera.reset_xp()
		self.camera.fov_zoom = 0.0
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

		p_data = w_data.get('player', {})
		w_info = w_data.get('world', {})

		saved_dim = p_data.get('dimension', w_info.get('dimension', 'overworld'))
		self.dimension = saved_dim

		self.world = world.World(seed=self.world_seed, save_folder=folder_name, render_distance=rd, dimension=saved_dim)
		if saved_dim == "nether":
			self.nether_world = self.world
			self.overworld = None
		else:
			self.overworld = self.world
			self.nether_world = None

		self.item_drop_manager = item_drop.ItemDropManager(self.world)
		self.world.item_drop_manager = self.item_drop_manager
		self.mob_manager = mob_manager.MobManager(self.world)
		self.world.mob_manager = self.mob_manager
		self.arrow_manager = arrow.ArrowManager(self.world)
		self.world.arrow_manager = self.arrow_manager
		self.tnt_manager = tnt_manager.TNTManager(self.world)
		self.world.tnt_manager = self.tnt_manager
		self.ender_eye_manager = ender_eye.EnderEyeManager(self.world)
		self.world.ender_eye_manager = self.ender_eye_manager
		self.ender_pearl_manager = ender_pearl.EnderPearlManager(self.world)
		self.world.ender_pearl_manager = self.ender_pearl_manager
		self.exp_bottle_manager = experience_bottle.ExperienceBottleManager(self.world)
		self.world.exp_bottle_manager = self.exp_bottle_manager
		self.ender_pearl_cooldown = 0.0
		self.bow_charging = False
		self.bow_charge_time = 0.0

		# Restore player attributes & flying state
		self.camera.position = p_data.get('position', [0.5, 80.0, 0.5])
		self.camera.rotation = p_data.get('rotation', [0.0, 0.0])
		self.camera.velocity_y = p_data.get('velocity_y', 0.0)
		self.camera.health = p_data.get('health', 20)
		self.camera.absorption = p_data.get('absorption', 0.0)
		self.camera.hunger = p_data.get('hunger', 20)
		self.camera.saturation = p_data.get('saturation', 5.0)
		self.camera.exhaustion = p_data.get('exhaustion', 0.0)
		saved_xp = p_data.get('total_xp', p_data.get('xp', 0))
		self.camera.set_xp(saved_xp)
		self.camera.spawn_point = p_data.get('spawn_point', None)
		self.flying = p_data.get('flying', False)
		self.sprinting = p_data.get('sprinting', False)

		# Restore world attributes
		self.time_of_day = w_info.get('time_of_day', 0.25)
		self.update_sky_color()

		if saved_dim == "nether":
			try:
				import fortress_manager
				nearest = fortress_manager.get_nearest_fortresses(self.camera.position, seed=self.world_seed, count=3)
				print("\n=======================================================")
				print(" [NETHER FORTRESS LOCATOR] 3 Nearest Fortresses:")
				for idx, (fx, fy, fz, dist) in enumerate(nearest, 1):
					print(f"   {idx}. Coordinates: (X={fx}, Y={fy}, Z={fz}) | Distance: {dist:.1f} blocks")
				print("=======================================================\n")
			except Exception:
				pass

		# Reset & restore inventory for this specific saved world
		self.gui.reset_inventory()
		self.gui.load_inventory_data(w_data.get('inventory', {}))
		self.holding = self.gui.get_current_block_id()

		drops = w_data.get('drops', [])
		self.item_drop_manager.drops.clear()
		for d in drops:
			self.item_drop_manager.spawn_drop(
				d['block_id'], d['count'], d['position'], velocity=d.get('velocity', [0,0,0]),
				enchantments=d.get('enchantments', {})
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

		# Debug: print top 3 closest villages to spawn in terminal
		try:
			import village
			closest = village.find_closest_villages_to_spawn(self.world.seed, count=3, max_region_radius=8)
			print(f"\n=======================================================")
			print(f" [VILLAGE LOCATOR] Seed: {self.world.seed}")
			print(f" Top 3 Closest Villages to Spawn (0, 0):")
			if closest:
				for idx, v in enumerate(closest, 1):
					print(f"   {idx}. Village Center: X={v['x']}, Y={v['y']}, Z={v['z']} | Distance: {v['distance']:.1f} blocks | Buildings: {v['buildings']}")
			else:
				print("   No villages found within immediate search radius.")
			print(f"=======================================================\n")
		except Exception as e:
			print(f"[Village Debug Error]: {e}")

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
			# Save modified dirty chunks synchronously across all initialized dimension worlds
			for w_inst in (self.world, getattr(self, "overworld", None), getattr(self, "nether_world", None)):
				if w_inst is not None and hasattr(w_inst, "dirty_chunks"):
					for cpos in list(w_inst.dirty_chunks):
						w_inst._save_chunk_to_file(cpos, synchronous=True)
					w_inst.dirty_chunks.clear()

			curr_dim = getattr(self, 'dimension', 'overworld')

			player_data = {
				'position': list(self.camera.position),
				'rotation': list(self.camera.rotation),
				'velocity_y': self.camera.velocity_y,
				'health': self.camera.health,
				'absorption': getattr(self.camera, 'absorption', 0.0),
				'hunger': getattr(self.camera, 'hunger', 20),
				'saturation': getattr(self.camera, 'saturation', 5.0),
				'exhaustion': getattr(self.camera, 'exhaustion', 0.0),
				'total_xp': getattr(self.camera, 'total_xp', 0),
				'level': getattr(self.camera, 'level', 0),
				'spawn_point': getattr(self.camera, 'spawn_point', None),
				'flying': self.flying,
				'sprinting': self.sprinting,
				'dimension': curr_dim
			}

			world_data = {
				'time_of_day': self.time_of_day,
				'render_distance': self.world.render_distance,
				'dimension': curr_dim
			}

			inventory_data = self.gui.serialize_inventory()

			drops_data = [
				{
					'block_id': d.block_id,
					'count': d.count,
					'position': list(d.position),
					'velocity': list(d.velocity),
					'age': d.age,
					'enchantments': getattr(d, 'enchantments', {})
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

	def trigger_dimension_transition(self):
		if getattr(self, "dimension_transitioning", False):
			return
		self.dimension_transitioning = True

		# 1. Determine destination dimension
		curr_dim = getattr(self, "dimension", "overworld")
		dest_dim = "nether" if curr_dim == "overworld" else "overworld"

		# Save current dimension dirty chunks
		if hasattr(self, "world") and hasattr(self.world, "save_all_chunks"):
			try:
				self.world.save_all_chunks()
			except Exception:
				pass

		# 2. Get or initialize destination world
		if dest_dim == "nether":
			if getattr(self, "nether_world", None) is None:
				self.nether_world = world.World(
					seed=self.world.seed,
					save_folder=self.world.save_folder,
					render_distance=self.global_render_distance,
					dimension="nether"
				)
				self.nether_world.texture_manager = self.world.texture_manager
				self.nether_world.block_types = self.world.block_types
				self.nether_world.item_drop_manager = item_drop.ItemDropManager(self.nether_world)
				self.nether_world.mob_manager = mob_manager.MobManager(self.nether_world)
				self.nether_world.arrow_manager = arrow.ArrowManager(self.nether_world)
				self.nether_world.tnt_manager = tnt_manager.TNTManager(self.nether_world)
			dest_world = self.nether_world
		else:
			if getattr(self, "overworld", None) is None:
				self.overworld = world.World(
					seed=self.world.seed,
					save_folder=self.world.save_folder,
					render_distance=self.global_render_distance,
					dimension="overworld"
				)
				self.overworld.texture_manager = self.world.texture_manager
				self.overworld.block_types = self.world.block_types
				self.overworld.item_drop_manager = item_drop.ItemDropManager(self.overworld)
				self.overworld.mob_manager = mob_manager.MobManager(self.overworld)
				self.overworld.arrow_manager = arrow.ArrowManager(self.overworld)
				self.overworld.tnt_manager = tnt_manager.TNTManager(self.overworld)
			dest_world = self.overworld

		# 3. Calculate 1:8 converted target coordinates
		px, py, pz = self.camera.position
		if dest_dim == "nether":
			target_x = px / 8.0
			target_z = pz / 8.0
		else:
			target_x = px * 8.0
			target_z = pz * 8.0

		# 4. Search existing portal or generate new destination portal
		import portal_manager
		portal = portal_manager.portal_manager.find_closest_portal(dest_world, (target_x, target_z), max_dist=128)
		if portal is None:
			portal = portal_manager.portal_manager.generate_destination_portal(dest_world, (target_x, target_z))

		spawn_x, spawn_y, spawn_z = portal.get_teleport_center()

		# 5. Pre-generate and mesh spawn chunks around destination
		spawn_cx = int(math.floor(spawn_x / 16.0))
		spawn_cz = int(math.floor(spawn_z / 16.0))
		for dx in range(-1, 2):
			for dz in range(-1, 2):
				cpos = (spawn_cx + dx, 0, spawn_cz + dz)
				if cpos not in dest_world.chunks:
					dest_world.chunks[cpos] = dest_world.generate_chunk(cpos[0], cpos[2])
				dest_world.queue_chunk_sections_for_meshing(cpos[0], cpos[2])

		# 6. Switch active world and entity managers
		if not hasattr(dest_world, "item_drop_manager") or dest_world.item_drop_manager is None:
			dest_world.item_drop_manager = item_drop.ItemDropManager(dest_world)
		if not hasattr(dest_world, "mob_manager") or dest_world.mob_manager is None:
			dest_world.mob_manager = mob_manager.MobManager(dest_world)
		if not hasattr(dest_world, "arrow_manager") or dest_world.arrow_manager is None:
			dest_world.arrow_manager = arrow.ArrowManager(dest_world)
		if not hasattr(dest_world, "tnt_manager") or dest_world.tnt_manager is None:
			dest_world.tnt_manager = tnt_manager.TNTManager(dest_world)

		self.dimension = dest_dim
		self.world = dest_world
		self.item_drop_manager = dest_world.item_drop_manager
		self.mob_manager = dest_world.mob_manager
		self.arrow_manager = dest_world.arrow_manager
		self.tnt_manager = dest_world.tnt_manager
		if hasattr(self, "ender_pearl_manager") and self.ender_pearl_manager:
			self.ender_pearl_manager.world = dest_world
			dest_world.ender_pearl_manager = self.ender_pearl_manager
		if hasattr(self, "exp_bottle_manager") and self.exp_bottle_manager:
			self.exp_bottle_manager.world = dest_world
			dest_world.exp_bottle_manager = self.exp_bottle_manager

		# 7. Position player inside portal opening with 4.0s cooldown
		self.camera.position = [spawn_x, spawn_y + self.camera.eye_offset, spawn_z]
		self.camera.velocity_y = 0.0
		self.camera.fall_start_y = None
		self.camera.fire_damage_timer = 0.0
		self.camera.portal_timer = 0.0
		self.camera.portal_cooldown = 4.0

		if dest_dim == "nether":
			try:
				import fortress_manager
				nearest = fortress_manager.get_nearest_fortresses((spawn_x, spawn_y, spawn_z), seed=self.world_seed, count=3)
				print("\n=======================================================")
				print(" [NETHER FORTRESS LOCATOR] 3 Nearest Fortresses:")
				for idx, (fx, fy, fz, dist) in enumerate(nearest, 1):
					print(f"   {idx}. Coordinates: (X={fx}, Y={fy}, Z={fz}) | Distance: {dist:.1f} blocks")
				print("=======================================================\n")
			except Exception:
				pass

		self.dimension_transitioning = False

	def trigger_end_dimension_transition(self, to_dimension="end"):
		if getattr(self, "dimension_transitioning", False):
			return
		self.dimension_transitioning = True

		# Save current dimension dirty chunks
		if hasattr(self, "world") and hasattr(self.world, "save_all_chunks"):
			try:
				self.world.save_all_chunks()
			except Exception:
				pass

		if to_dimension == "end":
			if getattr(self, "end_world", None) is None:
				self.end_world = world.World(
					seed=self.world_seed,
					save_folder=self.world.save_folder,
					render_distance=self.global_render_distance,
					dimension="end"
				)
				self.end_world.texture_manager = self.world.texture_manager
				self.end_world.block_types = self.world.block_types
				self.end_world.item_drop_manager = item_drop.ItemDropManager(self.end_world)
				self.end_world.mob_manager = mob_manager.MobManager(self.end_world)
				self.end_world.arrow_manager = arrow.ArrowManager(self.end_world)
				self.end_world.tnt_manager = tnt_manager.TNTManager(self.end_world)

			dest_world = self.end_world

			# Initialize Ender Dragon and End Crystals if not present
			if getattr(self, "ender_dragon", None) is None:
				import ender_dragon
				self.ender_dragon = ender_dragon.EnderDragonEntity((0.0, 75.0, 0.0))
				self.ender_dragon_renderer = ender_dragon.EnderDragonRenderer(self.world.texture_manager)
				dest_world.ender_dragon = self.ender_dragon

			if getattr(self, "end_crystal_manager", None) is None:
				import end_crystal
				import end_generator
				self.end_crystal_manager = end_crystal.EndCrystalManager(dest_world)
				self.end_crystal_manager.initialize_crystals_for_pillars(end_generator.get_pillar_definitions())
				dest_world.end_crystal_manager = self.end_crystal_manager

			if getattr(self, "dragon_fireball_manager", None) is None:
				import dragon_fireball
				self.dragon_fireball_manager = dragon_fireball.DragonFireballManager(dest_world)
				dest_world.dragon_fireball_manager = self.dragon_fireball_manager

			if getattr(self, "end_portal_renderer", None) is None:
				import end_portal_shader
				self.end_portal_renderer = end_portal_shader.EndPortalRenderer(dest_world)

			# Pre-generate chunks around Obsidian Spawn Platform (X=100, Z=0)
			spawn_cx = 6
			spawn_cz = 0
			for dx in range(-2, 3):
				for dz in range(-2, 3):
					cpos = (spawn_cx + dx, 0, spawn_cz + dz)
					if cpos not in dest_world.chunks:
						dest_world.chunks[cpos] = dest_world.generate_chunk(cpos[0], cpos[2])
					dest_world.queue_chunk_sections_for_meshing(cpos[0], cpos[2])

			import end_generator
			plat_y = end_generator.get_spawn_platform_y(self.world_seed)
			spawn_pos = [100.5, plat_y + 1.0 + self.camera.eye_offset, 0.5]

		else:
			# Returning to Overworld Spawn from End
			if getattr(self, "overworld", None) is None:
				self.overworld = world.World(
					seed=self.world_seed,
					save_folder=self.world.save_folder,
					render_distance=self.global_render_distance,
					dimension="overworld"
				)
				self.overworld.texture_manager = self.world.texture_manager
				self.overworld.block_types = self.world.block_types
				self.overworld.item_drop_manager = item_drop.ItemDropManager(self.overworld)
				self.overworld.mob_manager = mob_manager.MobManager(self.overworld)
				self.overworld.arrow_manager = arrow.ArrowManager(self.overworld)
				self.overworld.tnt_manager = tnt_manager.TNTManager(self.overworld)

			dest_world = self.overworld

			# Pre-generate chunks around (0, 0)
			for dx in range(-2, 3):
				for dz in range(-2, 3):
					cpos = (dx, 0, dz)
					if cpos not in dest_world.chunks:
						dest_world.chunks[cpos] = dest_world.generate_chunk(cpos[0], cpos[2])
					dest_world.queue_chunk_sections_for_meshing(cpos[0], cpos[2])

			spawn_y = 64
			for y in range(255, 0, -1):
				b = dest_world.get_block_number((0, y, 0))
				if b != 0 and b not in (9, 19, 15, 20):
					spawn_y = y + 1
					break

			spawn_pos = [0.5, spawn_y + self.camera.eye_offset, 0.5]

		self.dimension = to_dimension
		self.world = dest_world
		self.item_drop_manager = dest_world.item_drop_manager
		self.mob_manager = dest_world.mob_manager
		self.arrow_manager = dest_world.arrow_manager
		self.tnt_manager = dest_world.tnt_manager
		if hasattr(self, "ender_pearl_manager") and self.ender_pearl_manager:
			self.ender_pearl_manager.world = dest_world
			dest_world.ender_pearl_manager = self.ender_pearl_manager
		if hasattr(self, "exp_bottle_manager") and self.exp_bottle_manager:
			self.exp_bottle_manager.world = dest_world
			dest_world.exp_bottle_manager = self.exp_bottle_manager
		self.update_sky_color()

		self.camera.position = spawn_pos
		self.camera.velocity_y = 0.0
		self.camera.fall_start_y = None
		self.camera.fire_damage_timer = 0.0
		self.camera.portal_timer = 0.0
		self.camera.portal_cooldown = 4.0
		self.dimension_transitioning = False

	def respawn_player(self):
		"""Handles player respawn on death, ensuring Nether/End deaths return to Overworld (0, 0)."""
		# If currently in the Nether or End, switch active dimension back to Overworld
		if getattr(self, "dimension", "overworld") in ("nether", "end"):
			if getattr(self, "overworld", None) is None:
				self.overworld = world.World(
					seed=self.world_seed,
					save_folder=self.world.save_folder,
					render_distance=self.global_render_distance,
					dimension="overworld"
				)
				self.overworld.texture_manager = self.world.texture_manager
				self.overworld.block_types = self.world.block_types
				self.overworld.item_drop_manager = item_drop.ItemDropManager(self.overworld)
				self.overworld.mob_manager = mob_manager.MobManager(self.overworld)
				self.overworld.arrow_manager = arrow.ArrowManager(self.overworld)
				self.overworld.tnt_manager = tnt_manager.TNTManager(self.overworld)

			self.dimension = "overworld"
			self.world = self.overworld
			self.item_drop_manager = self.overworld.item_drop_manager
			self.mob_manager = self.overworld.mob_manager
			self.arrow_manager = self.overworld.arrow_manager
			self.tnt_manager = self.overworld.tnt_manager
			self.update_sky_color()

		# Ensure Overworld spawn chunks around (0, 0) are loaded and meshed
		for dx in range(-1, 2):
			for dz in range(-1, 2):
				cpos = (dx, 0, dz)
				if cpos not in self.world.chunks:
					self.world.chunks[cpos] = self.world.generate_chunk(cpos[0], cpos[2])
				self.world.queue_chunk_sections_for_meshing(cpos[0], cpos[2])

		# Reset camera state and position at Overworld (0, 0)
		self.camera.respawn(self.world)

	def update_sky_color(self):
		if getattr(self, "dimension", "overworld") == "nether":
			# Dark crimson Nether sky & fog
			gl.glClearColor(0.18, 0.04, 0.04, 1.0)
			return
		elif getattr(self, "dimension", "overworld") == "end":
			# Dark void purple End sky
			gl.glClearColor(0.035, 0.010, 0.055, 1.0)
			return

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

				# Position player safely on the surface if generating a fresh new world
				if not self.is_saved_load:
					spawn_y = self.get_surface_height(0, 0)
					self.camera.position = [0.5, spawn_y + 2.0 + self.camera.eye_offset, 0.5]
					self.camera.velocity_y = 0.0
					self.camera.fall_start_y = None

				# Populate initial diverse passive animals (cows, pigs, sheep, chickens)
				self.mob_manager.populate_initial_mobs(self.camera.position)
			return

		if delta_time > 0:
			self.fps = 0.9 * self.fps + 0.1 * (1.0 / delta_time)

		# If game is paused or in menus/settings, freeze all world and entity simulation completely
		if self.game_state != "PLAYING":
			return

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
			
			def find_target(current_block, next_block, face_vector=None, hit_pos=None):
				nonlocal target_block
				target_block = next_block
				return True

			hit_ray = hit.Hit_ray(self.world, self.camera.rotation, self.camera.position)
			while hit_ray.distance < hit.HIT_RANGE:
				if hit_ray.step(find_target):
					break

			if target_block:
				b_num = self.world.get_block_number(target_block)
				# Check if breaking a fire block (78) or punching a burning block side overlay
				if b_num == 78 or target_block in self.world.burning_blocks:
					self.world.extinguish_block(target_block)
					self.breaking_block = None
					self.break_progress = 0.0
				elif 0 < b_num < len(self.world.block_types) and b_num not in (9, 19, 15, 20, 14):
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
							import enchanting
							held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
							eff_mult = enchanting.get_efficiency_multiplier(held_slot)
							eff_speed = speed_mult * eff_mult
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
							actual_drop_id = drop_id
							drop_qty = 1
							if b_num == 77:
								import random
								if random.random() < 0.10:
									actual_drop_id = 146  # 10% chance to drop Flint item (146)
								else:
									actual_drop_id = 77   # 90% chance to drop Gravel block (77)
							elif b_num == 86:  # Glowstone -> drops 2-4 Glowstone Dust (171)
								import random
								actual_drop_id = 171
								drop_qty = random.randint(2, 4)
							elif b_num == 23:  # Bookshelf -> drops 3 Books (216)
								actual_drop_id = 216
								drop_qty = 3
							elif b_num == 212:  # Lapis Lazuli Ore -> drops 4-9 Lapis Lazuli (214) + 2-5 XP
								import random
								actual_drop_id = 214
								drop_qty = random.randint(4, 9)
								self.item_drop_manager.spawn_xp_orb(
									random.randint(2, 5),
									[target_block[0] + 0.5, target_block[1] + 0.5, target_block[2] + 0.5]
								)
							elif b_num == 81:  # Wheat Crops
								import random
								st = self.world.get_block_state(target_block)
								stage = int(st.shape) if (st and st.shape.isdigit()) else 7
								if stage >= 7:
									actual_drop_id = 154  # 1 Wheat item (154)
									drop_qty = 1
									# Also drop 1-3 Wheat Seeds (155)
									seed_cnt = random.randint(1, 3)
									self.item_drop_manager.spawn_drop(
										155, seed_cnt,
										[target_block[0] + 0.5, target_block[1] + 0.5, target_block[2] + 0.5]
									)
								else:
									actual_drop_id = 155  # Immature: only 1 seed returned
									drop_qty = 1
							elif b_num == 204:  # Carrot Crops
								import random
								st = self.world.get_block_state(target_block)
								stage = int(st.shape) if (st and st.shape.isdigit()) else 3
								if stage >= 3:
									actual_drop_id = 195  # Mature: 2-4 Carrots (195)
									drop_qty = random.randint(2, 4)
								else:
									actual_drop_id = 195  # Immature: 1 Carrot returned
									drop_qty = 1
							elif b_num == 205:  # Potato Crops
								import random
								st = self.world.get_block_state(target_block)
								stage = int(st.shape) if (st and st.shape.isdigit()) else 3
								if stage >= 3:
									actual_drop_id = 196  # Mature: 2-4 Potatoes (196)
									drop_qty = random.randint(2, 4)
									if random.random() < 0.02:
										self.item_drop_manager.spawn_drop(
											198, 1,
											[target_block[0] + 0.5, target_block[1] + 0.5, target_block[2] + 0.5]
										)
								else:
									actual_drop_id = 196  # Immature: 1 Potato returned
									drop_qty = 1
							elif b_num == 206:  # Pumpkin Stem
								actual_drop_id = 199  # Pumpkin Seed (199)
								drop_qty = 1
							elif b_num == 207:  # Melon Stem
								actual_drop_id = 200  # Melon Seed (200)
								drop_qty = 1
							elif b_num == 208:  # Pumpkin Block
								actual_drop_id = 208  # Pumpkin Block (208)
								drop_qty = 1
							elif b_num == 209:  # Melon Block
								import random
								actual_drop_id = 201  # 3-7 Melon Slices (201)
								drop_qty = random.randint(3, 7)
							elif b_num == 210:  # Sugar Cane
								actual_drop_id = 202
								drop_qty = 1
								# Break & drop all connected sugar cane blocks above it
								up_y = target_block[1] + 1
								while self.world.get_block_number((target_block[0], up_y, target_block[2])) == 210:
									self.world.set_block((target_block[0], up_y, target_block[2]), 0)
									self.item_drop_manager.spawn_drop(
										202, 1,
										[target_block[0] + 0.5, up_y + 0.5, target_block[2] + 0.5]
									)
									up_y += 1
							elif b_num in (13, 14, 224, 234, 244, 254, 264):  # All Leaves
								import enchanting
								held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
								if enchanting.has_silk_touch(held_slot):
									actual_drop_id = b_num if b_num != 14 else 13  # Drops exact Leaf block with Silk Touch
									drop_qty = 1
								else:
									# Without Silk Touch: Drops random amount of sticks and sometimes sapling / apple
									import random
									actual_drop_id = None
									drop_qty = 0

									# Stick drop (50% chance for 1-2 sticks)
									if random.random() < 0.50:
										stick_qty = random.randint(1, 2)
										self.item_drop_manager.spawn_drop(
											100, stick_qty,
											[target_block[0] + 0.5, target_block[1] + 0.5, target_block[2] + 0.5]
										)

									# Leaf-specific sapling and fruit drops
									leaf_sapling_map = {
										13: (156, True),   # Oak -> Sapling 156, can drop Apple
										14: (156, True),
										224: (225, False), # Birch -> Sapling 225
										234: (235, False), # Spruce -> Sapling 235
										244: (245, False), # Jungle -> Sapling 245
										254: (255, False), # Acacia -> Sapling 255
										264: (265, True),  # Dark Oak -> Sapling 265, can drop Apple
									}
									sap_id, can_apple = leaf_sapling_map.get(b_num, (156, False))

									# Apple drop (2% chance for oak/dark oak)
									if can_apple and random.random() < 0.02:
										self.item_drop_manager.spawn_drop(
											153, 1,
											[target_block[0] + 0.5, target_block[1] + 0.5, target_block[2] + 0.5]
										)

									# Sapling drop (5% chance)
									if random.random() < 0.05:
										self.item_drop_manager.spawn_drop(
											sap_id, 1,
											[target_block[0] + 0.5, target_block[1] + 0.5, target_block[2] + 0.5]
										)
							elif b_num in (220, 221):  # Bed Foot or Bed Head
								actual_drop_id = 219  # 1 Bed item (219)
								drop_qty = 1
							elif b_num in (184, 185, 186, 187):  # Infested Blocks (Monster Egg)
								actual_drop_id = None
								if hasattr(self, "mob_manager") and self.mob_manager:
									self.mob_manager.spawn_mob("silverfish", (target_block[0] + 0.5, target_block[1] + 0.1, target_block[2] + 0.5))

							# Apply Silk Touch or Fortune enchantment to mined drops
							import enchanting
							held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
							if enchanting.has_silk_touch(held_slot):
								silk_drop = enchanting.get_silk_touch_drop(b_num)
								if silk_drop is not None:
									actual_drop_id = silk_drop
									drop_qty = 1
							else:
								fortune_lvl = enchanting.get_fortune_level(held_slot)
								if fortune_lvl > 0:
									actual_drop_id, drop_qty = enchanting.apply_fortune_to_block_drop(b_num, actual_drop_id, drop_qty, fortune_lvl)

							if actual_drop_id is not None:
								self.item_drop_manager.spawn_drop(
									actual_drop_id, drop_qty,
									[target_block[0] + 0.5, target_block[1] + 0.5, target_block[2] + 0.5]
								)

						# Check 2-block door breaking synchronization
						st_curr = self.world.get_block_state(target_block)
						if b_num in (43, 44, 45, 46, 228, 238, 248, 258, 268):
							# Lower door half broken -> remove upper door half at y+1
							top_pos = (target_block[0], target_block[1] + 1, target_block[2])
							top_b = self.world.get_block_number(top_pos)
							if top_b in (43, 44, 45, 46, 65, 66, 67, 68, 228, 229, 238, 239, 248, 249, 258, 259, 268, 269):
								self.world.set_block(top_pos, 0)
								self.world.set_block_state(top_pos, None)
						elif b_num in (65, 66, 67, 68, 229, 239, 249, 259, 269):
							# Upper door half broken -> remove lower door half at y-1
							bot_pos = (target_block[0], target_block[1] - 1, target_block[2])
							bot_b = self.world.get_block_number(bot_pos)
							if bot_b in (43, 44, 45, 46, 65, 66, 67, 68, 228, 229, 238, 239, 248, 249, 258, 259, 268, 269):
								self.world.set_block(bot_pos, 0)
								self.world.set_block_state(bot_pos, None)

						# Check 2-block bed breaking synchronization (220 = foot, 221 = head)
						elif b_num in (220, 221):
							for ox, oz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
								adj_pos = (target_block[0] + ox, target_block[1], target_block[2] + oz)
								if self.world.get_block_number(adj_pos) in (220, 221):
									self.world.set_block(adj_pos, 0)
									self.world.set_block_state(adj_pos, None)
									break
							# Invalidate spawn point if bed is broken
							if hasattr(self.camera, "spawn_point") and self.camera.spawn_point:
								sx, sy, sz = self.camera.spawn_point
								if abs(sx - target_block[0]) <= 2 and abs(sy - target_block[1]) <= 1 and abs(sz - target_block[2]) <= 2:
									self.camera.spawn_point = None

						self.world.set_block(target_block, 0)
						self.world.set_block_state(target_block, None)
						self.camera.add_exhaustion(0.005)
						if not getattr(self, "flying", False):
							held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
							if held_slot and held_slot[0] != 0:
								held_id = held_slot[0]
								dmg_amt = 2 if (113 <= held_id <= 116 or held_id == 120) else 1
								gui.damage_slot(held_slot, amount=dmg_amt)
								self.holding = self.gui.get_current_block_id()
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

		# Disable sprinting if hunger <= 6 points (3 drumsticks)
		if not self.flying and self.camera.hunger <= 6:
			self.sprinting = False

		# Continuously sync horizontal movement vector from physical key states
		dx = 0
		dz = 0
		if self.keys_down.get(pyglet.window.key.D, False): dx += 2
		if self.keys_down.get(pyglet.window.key.A, False): dx -= 2
		if self.keys_down.get(pyglet.window.key.W, False): dz += 2
		if self.keys_down.get(pyglet.window.key.S, False): dz -= 2

		if self.mouse_captured:
			self.camera.input = [dx, 0, dz]
			if self.sprinting and (dx != 0 or dz != 0) and not self.flying:
				self.camera.add_exhaustion(0.1 * delta_time)
		else:
			self.camera.input = [0, 0, 0]

		self.camera.update_camera(delta_time, self.sprinting, self.world, self.flying, self.keys_down)

		# Check Nether Portal Dimension Transition
		trigger_time = 0.0 if self.flying else 4.0
		if getattr(self.camera, "is_inside_portal", False) and self.camera.portal_timer >= trigger_time and self.camera.portal_cooldown <= 0.0 and not getattr(self, "dimension_transitioning", False):
			self.trigger_dimension_transition()

		# Check End Portal Dimension Transition (instant transition in Minecraft)
		if getattr(self.camera, "is_inside_end_portal", False) and self.camera.portal_cooldown <= 0.0 and not getattr(self, "dimension_transitioning", False):
			if getattr(self, "dimension", "overworld") == "overworld":
				self.trigger_end_dimension_transition("end")
			elif getattr(self, "dimension", "overworld") == "end":
				self.trigger_end_dimension_transition("overworld")

		# Update Ender Dragon & End Crystals when in the End
		if getattr(self, "dimension", "overworld") == "end":
			if hasattr(self, "ender_dragon") and self.ender_dragon:
				self.ender_dragon.update(delta_time, end_world=self.world, camera=self.camera, gui=self.gui)
				# Check if dragon just died -> activate central exit fountain
				if self.ender_dragon.is_dead:
					import end_generator
					if not end_generator.end_generator.dragon_defeated:
						end_generator.end_generator.dragon_defeated = True
						fount_y = end_generator.get_fountain_y(self.world_seed)
						for fx in (-1, 0, 1):
							for fz in (-1, 0, 1):
								if not (fx == 0 and fz == 0):
									self.world.set_block((fx, fount_y + 1, fz), 183)
								else:
									self.world.set_block((0, fount_y + 1, 0), 14)
						self.world.set_block((0, fount_y + 4, 0), 189)

			if hasattr(self, "end_crystal_manager") and self.end_crystal_manager:
				self.end_crystal_manager.update(
					delta_time,
					dragon=getattr(self, "ender_dragon", None),
					mob_manager=self.mob_manager,
					item_drop_manager=self.item_drop_manager
				)

			if hasattr(self, "dragon_fireball_manager") and self.dragon_fireball_manager:
				self.dragon_fireball_manager.update(delta_time, camera=self.camera, gui=self.gui)

		if hasattr(self, "end_portal_renderer") and self.end_portal_renderer:
			self.end_portal_renderer.update(delta_time)

		self.item_drop_manager.update(delta_time, self.camera.position, self.gui, camera=self.camera)
		if hasattr(self, "tnt_manager"):
			self.tnt_manager.update(
				delta_time, mob_manager=self.mob_manager, camera=self.camera,
				gui=self.gui, item_drop_manager=self.item_drop_manager
			)
		self.mob_manager.update(
			delta_time, self.camera.position,
			camera=self.camera, gui=self.gui, tnt_manager=getattr(self, "tnt_manager", None),
			item_drop_manager=self.item_drop_manager,
			arrow_manager=getattr(self, "arrow_manager", None),
			time_of_day=self.time_of_day, flying=self.flying
		)
		
		# Bow drawing state & dynamic FOV zoom
		if getattr(self, "bow_charging", False):
			if self.gui.get_current_block_id() != 157:
				self.bow_charging = False
				self.bow_charge_time = 0.0
				self.camera.fov_zoom = 0.0
			else:
				self.bow_charge_time += delta_time
				charge_ticks = int(self.bow_charge_time * 20.0)
				self.camera.fov_zoom = min(1.0, charge_ticks / 20.0) * 0.15
		else:
			self.camera.fov_zoom = 0.0

		if hasattr(self, "arrow_manager"):
			self.arrow_manager.update(delta_time, self.world, self.mob_manager, self.camera, self.gui)

		if hasattr(self, "ender_eye_manager"):
			self.ender_eye_manager.update(delta_time, item_drop_manager=self.item_drop_manager)

		self.ender_pearl_cooldown = max(0.0, getattr(self, "ender_pearl_cooldown", 0.0) - delta_time)
		if hasattr(self, "ender_pearl_manager") and self.ender_pearl_manager:
			self.ender_pearl_manager.update(delta_time, camera=self.camera, gui=self.gui, mob_manager=self.mob_manager)

		if hasattr(self, "exp_bottle_manager") and self.exp_bottle_manager:
			self.exp_bottle_manager.update(delta_time, item_drop_manager=self.item_drop_manager, mob_manager=self.mob_manager)

		self.world.update_chunks(self.camera.position)
		self.world.process_load_queue(self.camera.position, player_rotation=self.camera.rotation)
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

		# Render 3D Passive & Hostile Mobs in overworld
		self.mob_manager.draw(self.camera)

		# Render 3D Primed TNT Entities
		if hasattr(self, "tnt_manager"):
			self.shader.use()
			gl.glActiveTexture(gl.GL_TEXTURE0)
			gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
			gl.glUniform1i(self.shader_sampler_location, 0)
			self.tnt_manager.draw(self.shader)

		# Render 3D Flying & Embedded Arrows
		if hasattr(self, "arrow_manager"):
			self.arrow_manager.draw(self.camera)

		# Render 3D Ender Eye projectiles & particle trails
		if hasattr(self, "ender_eye_manager"):
			self.ender_eye_manager.draw(self.camera)

		# Render 3D Ender Pearl projectiles & particle trails
		if hasattr(self, "ender_pearl_manager") and self.ender_pearl_manager:
			self.ender_pearl_manager.draw(self.camera)

		# Render 3D Experience Bottle projectiles & sparkle effects
		if hasattr(self, "exp_bottle_manager") and self.exp_bottle_manager:
			self.exp_bottle_manager.draw(self.camera)

		# Render 3D End Crystals & Healing Beams in End Dimension
		if getattr(self, "dimension", "overworld") == "end" and hasattr(self, "end_crystal_manager") and self.end_crystal_manager:
			self.end_crystal_manager.draw(self.camera)

		# Render 3D Ender Dragon Boss in End Dimension
		if getattr(self, "dimension", "overworld") == "end" and hasattr(self, "ender_dragon") and self.ender_dragon:
			if hasattr(self, "ender_dragon_renderer") and self.ender_dragon_renderer:
				self.ender_dragon_renderer.draw(self.camera, self.ender_dragon)

		# Render 3D Dragon Fireballs & Dragon's Breath Effect Clouds
		if getattr(self, "dimension", "overworld") == "end" and hasattr(self, "dragon_fireball_manager") and self.dragon_fireball_manager:
			self.dragon_fireball_manager.draw(self.camera)

		# Render 3D End Portal Infinite Void Planes
		if hasattr(self, "end_portal_renderer") and self.end_portal_renderer:
			portal_blocks = []
			for chk in self.world.chunks.values():
				cx, _, cz = chk.chunk_position
				if 183 in chk.blocks:
					for lx in range(16):
						for ly in range(256):
							for lz in range(16):
								if chk.blocks[lx * 4096 + ly * 16 + lz] == 183:
									portal_blocks.append((cx * 16 + lx, ly, cz * 16 + lz))
			if portal_blocks:
				self.end_portal_renderer.draw(self.camera, portal_blocks)

		# If 3rd Person View (Back or Front), render Steve 3D Player Model!
		if self.perspective != 0:
			self.player_model.render_third_person(self.camera, self.perspective, self.world)

		# 2. Render 3D overworld dropped items & 2D item sprites BEFORE 2D overlays
		self.shader.use()
		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
		gl.glUniform1i(self.shader_sampler_location, 0)
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
		if getattr(self, "dimension", "overworld") in ("nether", "end"):
			return

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

			# Cache debug noise calls once per block position update
			if not hasattr(self, '_last_debug_pos') or self._last_debug_pos != (wx, wz):
				import biome as biome_module
				self._last_debug_pos = (wx, wz)
				self._cached_temp = biome_module.get_temperature(wx, wz, self.world.seed)
				self._cached_moist = biome_module.get_moisture(wx, wz, self.world.seed)
				b_id = biome_module.get_biome_at(wx, wz, self.world.seed)
				self._cached_biome_name = biome_module.BIOME_NAMES.get(b_id, "Plains")

			temp_val = getattr(self, '_cached_temp', 0.5)
			moist_val = getattr(self, '_cached_moist', 0.5)
			biome_str = getattr(self, '_cached_biome_name', 'Plains')

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
				f"Climate & Biome Variables:",
				f" - Biome:          {biome_str}",
				f" - Temperature:    {temp_val:.4f}",
				f" - Moisture:       {moist_val:.4f}",
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
		self.break_progress_bar.x = cx - w // 2 + pad
		self.break_progress_bar.y = cy + pad
		self.break_progress_bar.width = fill_w
		self.break_progress_bar.height = h - 2 * pad
		self.break_progress_bar.draw()

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
		if self.flying and self.gui.inventory_open:
			if len(self.gui.creative_search_text) < 20 and (text.isalnum() or text in " -_()"):
				self.gui.creative_search_text += text
				self.gui.creative_scroll_row = 0
			return

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
			self.gui.on_mouse_press(x, y, button, modifiers)
			return

		if not self.mouse_captured:
			self.mouse_captured = True
			self.set_exclusive_mouse(True)
			return

		if button == pyglet.window.mouse.LEFT:
			self.left_mouse_down = True
			held_id = self.gui.get_current_block_id()
			held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
			damage = gui.get_item_attack_damage(held_id)
			import enchanting
			sharpness_bonus = enchanting.get_sharpness_bonus(held_slot)
			damage += sharpness_bonus
			fire_duration = enchanting.get_fire_aspect_duration(held_slot)
			looting_level = enchanting.get_looting_level(held_slot)

			# Trigger 1st/3rd person player arm swing animation
			if hasattr(self, "player_model"):
				self.player_model.is_swinging = True
				self.player_model.swing_time = 0.0

			if hasattr(self, "mob_manager") and self.mob_manager.attack_mob_at_crosshair(self.camera, damage=damage, fire_duration=fire_duration, looting_level=looting_level):
				if not getattr(self, "flying", False) and held_slot and held_slot[0] != 0:
					dmg_amt = 1 if (113 <= held_id <= 116 or held_id == 120) else 2
					gui.damage_slot(held_slot, amount=dmg_amt)
					self.holding = self.gui.get_current_block_id()
				return

			# Check End Crystal and Ender Dragon attack in End dimension
			if getattr(self, "dimension", "overworld") == "end":
				yaw, pitch = self.camera.rotation
				ray_dir = (
					math.cos(yaw) * math.cos(pitch),
					math.sin(pitch),
					math.sin(yaw) * math.cos(pitch)
				)
				if hasattr(self, "end_crystal_manager") and self.end_crystal_manager:
					if self.end_crystal_manager.check_attack_hit(
						self.camera.position, ray_dir, max_dist=6.5, damage=damage,
						dragon=getattr(self, "ender_dragon", None), mob_manager=self.mob_manager,
						camera=self.camera, gui=self.gui,
						tnt_manager=getattr(self, "tnt_manager", None),
						item_drop_manager=self.item_drop_manager
					):
						if not getattr(self, "flying", False) and held_slot and held_slot[0] != 0:
							dmg_amt = 1 if (113 <= held_id <= 116 or held_id == 120) else 2
							gui.damage_slot(held_slot, amount=dmg_amt)
							self.holding = self.gui.get_current_block_id()
						return
				if hasattr(self, "ender_dragon") and self.ender_dragon:
					dragon_hit, dragon_part = self.ender_dragon.check_ray_hit(self.camera.position, ray_dir, max_dist=14.0)
					if dragon_hit:
						self.ender_dragon.take_damage(damage, part=dragon_part, attacker_pos=self.camera.position)
						if not getattr(self, "flying", False) and held_slot and held_slot[0] != 0:
							dmg_amt = 1 if (113 <= held_id <= 116 or held_id == 120) else 2
							gui.damage_slot(held_slot, amount=dmg_amt)
							self.holding = self.gui.get_current_block_id()
						return

			# Check if hitting a Fire block (78) or burning block side overlay to extinguish it immediately
			target_block = None
			def find_target(current_block, next_block, face_vector=None, hit_pos=None):
				nonlocal target_block
				target_block = next_block

			hit_ray = hit.Hit_ray(self.world, self.camera.rotation, self.camera.position)
			while hit_ray.distance < hit.HIT_RANGE:
				if hit_ray.step(find_target):
					break

			if target_block:
				b_num = self.world.get_block_number(target_block)
				if b_num == 78 or target_block in self.world.burning_blocks:
					self.world.extinguish_block(target_block)
					self.breaking_block = None
					self.break_progress = 0.0
					return
		elif button == pyglet.window.mouse.RIGHT:
			held_id = self.gui.get_current_block_id()
			if held_id == 157:  # Bow
				has_arrow = getattr(self, "flying", False) or any(slot[0] == 158 and slot[1] > 0 for slot in self.gui.hotbar_slots + self.gui.survival_inventory)
				if has_arrow:
					self.bow_charging = True
					self.bow_charge_time = 0.0
					return
			elif held_id in gui.FOOD_VALUES and (self.camera.hunger < 20 or held_id == 161):
				food_info = gui.FOOD_VALUES[held_id]
				h_pts = food_info[0]
				s_pts = food_info[1]
				abs_pts = food_info[2] if len(food_info) > 2 else 0.0
				self.camera.eat_food(h_pts, s_pts, abs_pts)
				self.gui.consume_active_item()
				self.holding = self.gui.get_current_block_id()
				return
			elif held_id in gui.ARMOR_SLOT_TYPES:
				slot_idx = gui.ARMOR_SLOT_TYPES[held_id]
				equipped_slot = self.gui.armor_slots[slot_idx]
				active_slot = self.gui.hotbar_slots[self.gui.selected_slot]

				old_armor_id = equipped_slot[0]
				equipped_slot[0] = held_id
				equipped_slot[1] = 1

				if old_armor_id != 0:
					active_slot[0] = old_armor_id
					active_slot[1] = 1
				else:
					active_slot[1] -= 1
					if active_slot[1] <= 0:
						active_slot[0] = 0

				self.holding = self.gui.get_current_block_id()
				return
			elif held_id == 177: # Eye of Ender
				# 1. Check if clicking directly on an Empty End Portal Frame (181)
				target_block = None
				def find_frame(current_block, next_block, best_face=None, hit_pos=None):
					nonlocal target_block
					if self.world.get_block_number(next_block) != 0:
						target_block = next_block
						return True
					return False

				hit_ray = hit.Hit_ray(self.world, self.camera.rotation, self.camera.position)
				while hit_ray.distance < hit.HIT_RANGE:
					if hit_ray.step(find_frame):
						break

				if target_block and self.world.get_block_number(target_block) == 181:
					existing_st = self.world.get_block_state(target_block)
					facing = existing_st.facing if existing_st and hasattr(existing_st, "facing") else "NORTH"
					import block_state
					new_st = block_state.BlockState(182, facing=facing)
					self.world.set_block(target_block, 182) # End Portal Frame (Filled with Eye)
					self.world.set_block_state(target_block, new_st)
					self.gui.consume_active_item()
					self.holding = self.gui.get_current_block_id()
					self.world.check_and_activate_end_portal(target_block)
					return
				else:
					# 2. Thrown Eye of Ender Projectile (Overworld only)
					if getattr(self.world, "dimension", "overworld") == "overworld":
						self.ender_eye_manager.throw_eye(self.camera.position, world_seed=getattr(self.world, "seed", 0))
						self.gui.consume_active_item()
						self.holding = self.gui.get_current_block_id()
						return
			elif held_id == 176: # Ender Pearl
				if getattr(self, "ender_pearl_cooldown", 0.0) <= 0.0:
					self.ender_pearl_cooldown = 1.0  # 1.0s cooldown
					if not hasattr(self, "ender_pearl_manager") or not self.ender_pearl_manager:
						self.ender_pearl_manager = ender_pearl.EnderPearlManager(self.world)
					self.ender_pearl_manager.throw_pearl(self.camera.position, self.camera.rotation)
					self.gui.consume_active_item()
					self.holding = self.gui.get_current_block_id()
					return
			elif held_id == 218: # Experience Bottle (Bottle o' Enchanting)
				if not hasattr(self, "exp_bottle_manager") or not self.exp_bottle_manager:
					self.exp_bottle_manager = experience_bottle.ExperienceBottleManager(self.world)
				self.exp_bottle_manager.throw_bottle(self.camera.position, self.camera.rotation)
				self.gui.consume_active_item()
				self.holding = self.gui.get_current_block_id()
				return

		self.holding = self.gui.get_current_block_id()
		is_shift_down = bool(modifiers & pyglet.window.key.MOD_SHIFT) or self.keys_down.get(pyglet.window.key.LSHIFT, False) or self.keys_down.get(pyglet.window.key.RSHIFT, False)
		is_placeable = (0 < self.holding < 100) or (self.holding == 156) or (178 <= self.holding <= 187) or (204 <= self.holding <= 285) or (self.holding == 219)
		INTERACTIVE_BLOCKS = (
			26, 27, 37, 54, 55, 56, 57, 58, 59,
			43, 44, 45, 46, 65, 66, 67, 68,
			47, 48, 49, 50, 69, 70, 71, 72,
			75, 76, 213, 220, 221,
			228, 229, 238, 239, 248, 249, 258, 259, 268, 269,  # Doors
			230, 240, 250, 260, 270,                            # Trapdoors
			272, 273, 274, 275, 276                             # Fence Gates
		)
		DOOR_TRAPDOOR_TOGGLES = {
			43: 44, 44: 43,
			65: 66, 66: 65,
			45: 46, 46: 45,
			67: 68, 68: 67,
			47: 48, 48: 47,
			69: 70, 70: 69,
			49: 50, 50: 49,
			71: 72, 72: 71,
			75: 76, 76: 75,
		}

		def get_cardinal_dir():
			deg = (math.degrees(self.camera.rotation[0]) + 360) % 360
			if 45 <= deg < 135: return "SOUTH"
			elif 135 <= deg < 225: return "WEST"
			elif 225 <= deg < 315: return "NORTH"
			else: return "EAST"

		def place_block_with_state(target_pos, held_item, next_pos, face_vector=None, hit_pos=None):
			import block_state
			cardinal_dir = block_state.get_player_facing(self.camera.rotation)

			# Flowers & Saplings (only placeable on top face of grass and dirt, cannot be placed on other flora)
			if held_item in block_state.FLOWERS_AND_SAPLINGS:
				# Must be placed on the top face
				if face_vector is not None and face_vector != (0, 1, 0):
					return
				# Target position must be clear (empty or liquid)
				cur_target_b = self.world.get_block_number(target_pos)
				if cur_target_b != 0 and cur_target_b not in (9, 19, 15, 20):
					return
				# Clicked block cannot be a flower or sapling
				clicked_b = self.world.get_block_number(next_pos)
				if clicked_b in block_state.FLOWERS_AND_SAPLINGS:
					return
				# Block underneath target_pos MUST be valid soil (grass or dirt)
				ground_pos = (target_pos[0], target_pos[1] - 1, target_pos[2])
				ground_b = self.world.get_block_number(ground_pos)
				if ground_b not in block_state.VALID_SOIL_BLOCKS:
					return

			# 1. Furnace (27)
			if held_item == 27:
				st = block_state.BlockState(27, facing=cardinal_dir)
				self.world.set_block_state(target_pos, st)

			# 2. Chest (37)
			elif held_item == 37:
				st = block_state.BlockState(37, facing=cardinal_dir)
				self.world.set_block_state(target_pos, st)

			# 3. Logs (8, 223, 233, 243, 253, 263)
			elif held_item in (8, 223, 233, 243, 253, 263):
				if face_vector is not None:
					if face_vector[1] != 0: axis = "Y"
					elif face_vector[0] != 0: axis = "X"
					elif face_vector[2] != 0: axis = "Z"
					else: axis = "Y"
				else:
					dx = target_pos[0] - next_pos[0]
					dz = target_pos[2] - next_pos[2]
					axis = "X" if dx != 0 else ("Z" if dz != 0 else "Y")
				st = block_state.BlockState(held_item, axis=axis)
				self.world.set_block_state(target_pos, st)

			# 4. Slabs (38, 39, 40, 95, 180, 226, 236, 246, 256, 266)
			elif held_item in (38, 39, 40, 95, 180, 226, 236, 246, 256, 266):
				# Check slab combination on existing same-type slab
				target_b = self.world.get_block_number(next_pos)
				if target_b == held_item:
					target_st = self.world.get_block_state(next_pos)
					if target_st and target_st.half in ("BOTTOM", "TOP"):
						combine = False
						if face_vector == (0, 1, 0) and target_st.half == "BOTTOM":
							combine = True
						elif face_vector == (0, -1, 0) and target_st.half == "TOP":
							combine = True
						elif hit_pos is not None:
							y_local = hit_pos[1] - next_pos[1]
							if y_local >= 0.0 and target_st.half == "BOTTOM": combine = True
							elif y_local < 0.0 and target_st.half == "TOP": combine = True
						else:
							combine = True

						if combine:
							target_st.half = "DOUBLE"
							self.world.set_block_state(next_pos, target_st)
							self.gui.consume_active_item()
							self.holding = self.gui.get_current_block_id()
							return

				# Determine single slab placement half
				if face_vector == (0, 1, 0):
					half = "BOTTOM"
				elif face_vector == (0, -1, 0):
					half = "TOP"
				elif hit_pos is not None:
					y_local = hit_pos[1] - next_pos[1]
					half = "TOP" if y_local >= 0.0 else "BOTTOM"
				else:
					half = "TOP" if self.camera.rotation[1] > 0 else "BOTTOM"

				st = block_state.BlockState(held_item, half=half)
				self.world.set_block_state(target_pos, st)

			# 5. Doors (43, 45, 228, 238, 248, 258, 268) - 2-block structure
			elif held_item in (43, 45, 228, 238, 248, 258, 268):
				top_pos = (target_pos[0], target_pos[1] + 1, target_pos[2])
				if self.world.get_block_number(top_pos) == 0 and not self.camera.intersects_player(top_pos):
					door_top_map = {43: 65, 45: 67, 228: 229, 238: 239, 248: 249, 258: 259, 268: 269}
					b_bot = held_item
					b_top = door_top_map.get(held_item, 65)
					hinge = block_state.calculate_door_hinge(self.world, target_pos, cardinal_dir, hit_pos=hit_pos)

					st_bot = block_state.BlockState(b_bot, facing=cardinal_dir, half="LOWER", hinge=hinge, open_state=False)
					st_top = block_state.BlockState(b_top, facing=cardinal_dir, half="UPPER", hinge=hinge, open_state=False)

					self.world.set_block_state(target_pos, st_bot)
					self.world.set_block_state(top_pos, st_top)
					self.gui.consume_active_item()
					self.holding = self.gui.get_current_block_id()
					return

			# 6. Trapdoors (47, 49, 230, 240, 250, 260, 270)
			elif held_item in (47, 49, 230, 240, 250, 260, 270):
				if face_vector is not None and face_vector[1] == 0:
					if face_vector == (0, 0, -1): facing = "NORTH"
					elif face_vector == (0, 0, 1): facing = "SOUTH"
					elif face_vector == (-1, 0, 0): facing = "WEST"
					elif face_vector == (1, 0, 0): facing = "EAST"
					else: facing = cardinal_dir
					if hit_pos is not None:
						y_local = hit_pos[1] - next_pos[1]
						half = "TOP" if y_local >= 0.0 else "BOTTOM"
					else:
						half = "BOTTOM"
				elif face_vector == (0, 1, 0):
					facing = cardinal_dir
					half = "BOTTOM"
				elif face_vector == (0, -1, 0):
					facing = cardinal_dir
					half = "TOP"
				else:
					facing = cardinal_dir
					half = "BOTTOM"
				st = block_state.BlockState(held_item, facing=facing, half=half, open_state=False)
				self.world.set_block_state(target_pos, st)

			# 7. Stairs (41, 42, 92, 178, 227, 237, 247, 257, 267)
			elif held_item in (41, 42, 92, 178, 227, 237, 247, 257, 267):
				if face_vector == (0, 1, 0):
					half = "BOTTOM"
				elif face_vector == (0, -1, 0):
					half = "TOP"
				elif hit_pos is not None:
					y_local = hit_pos[1] - next_pos[1]
					half = "TOP" if y_local >= 0.0 else "BOTTOM"
				else:
					half = "TOP" if self.camera.rotation[1] > 0 else "BOTTOM"
				facing = block_state.RIGHT_DIRECTIONS[cardinal_dir]
				shape = block_state.calculate_stair_shape(self.world, target_pos, facing, half)
				st = block_state.BlockState(held_item, facing=facing, half=half, shape=shape)
				self.world.set_block_state(target_pos, st)

			# 8. Fences (51, 91, 231, 241, 251, 261, 271)
			elif held_item in (51, 91, 231, 241, 251, 261, 271):
				conns = block_state.calculate_fence_connections(self.world, target_pos, held_item)
				st = block_state.BlockState(held_item, connections=conns)
				self.world.set_block_state(target_pos, st)

			# 9. Walls (52)
			elif held_item == 52:
				conns = block_state.calculate_wall_connections(self.world, target_pos, 52)
				st = block_state.BlockState(52, connections=conns)
				self.world.set_block_state(target_pos, st)

			# 10. Glass Panes & Iron Bars (53, 99)
			elif held_item in (53, 99):
				conns = block_state.calculate_pane_connections(self.world, target_pos, held_item)
				st = block_state.BlockState(held_item, connections=conns)
				self.world.set_block_state(target_pos, st)

			# 11. Fence Gates (75, 272, 273, 274, 275, 276)
			elif held_item in (75, 272, 273, 274, 275, 276):
				facing = block_state.LEFT_DIRECTIONS[cardinal_dir]
				st = block_state.BlockState(held_item, facing=facing, open_state=False)
				self.world.set_block_state(target_pos, st)

			# 12. End Portal Frame (181, 182)
			elif held_item in (181, 182):
				st = block_state.BlockState(held_item, facing=cardinal_dir)
				self.world.set_block_state(target_pos, st)

			# 13. Bed (219, 220, 221) - 2-block structure (Foot & Head)
			elif held_item in (219, 220, 221):
				dir_offsets = {
					"NORTH": (0, -1),
					"SOUTH": (0, 1),
					"EAST": (1, 0),
					"WEST": (-1, 0),
				}
				ox, oz = dir_offsets.get(cardinal_dir, (0, 1))
				head_pos = (target_pos[0] + ox, target_pos[1], target_pos[2] + oz)
				if self.world.get_block_number(head_pos) == 0 and not self.camera.intersects_player(head_pos):
					# Check solid ground beneath foot and head
					g_foot = self.world.get_block_number((target_pos[0], target_pos[1] - 1, target_pos[2]))
					g_head = self.world.get_block_number((head_pos[0], head_pos[1] - 1, head_pos[2]))
					if g_foot not in (0, 9, 15, 19, 20) and g_head not in (0, 9, 15, 19, 20):
						st_foot = block_state.BlockState(220, facing=cardinal_dir)
						st_head = block_state.BlockState(221, facing=cardinal_dir)
						self.world.set_block(target_pos, 220)  # Bed Foot
						self.world.set_block_state(target_pos, st_foot)
						self.world.set_block(head_pos, 221)    # Bed Head
						self.world.set_block_state(head_pos, st_head)
						self.gui.consume_active_item()
						self.holding = self.gui.get_current_block_id()
						return
				return

			else:
				self.world.set_block(target_pos, held_item)

			self.gui.consume_active_item()
			self.holding = self.gui.get_current_block_id()

		def hit_callback(current_block, next_block, face_vector=None, hit_pos=None):
			if self.world.get_block_number(current_block) != 14 and 0 <= current_block[1] < 256:
				if button == pyglet.window.mouse.RIGHT:
					target_b = self.world.get_block_number(next_block)

					# 1. Bucket interactions (147 = Empty Bucket, 148 = Water Bucket, 149 = Lava Bucket)
					if self.holding == 147:
						if target_b in (9, 15):
							# Scoop liquid source block!
							self.world.set_block(next_block, 0)
							new_bucket = 148 if target_b == 9 else 149
							active_slot = self.gui.hotbar_slots[self.gui.selected_slot]
							if getattr(self, "flying", False):
								active_slot[0] = new_bucket
								active_slot[1] = 1
							else:
								if active_slot[1] == 1:
									active_slot[0] = new_bucket
								else:
									active_slot[1] -= 1
									self.gui.add_item(new_bucket, 1)
							self.holding = self.gui.get_current_block_id()
							return
						elif target_b in INTERACTIVE_BLOCKS and not is_shift_down:
							pass  # Fall through to interactive block GUI/toggle below
						else:
							return  # Empty bucket on non-liquid does nothing

					elif self.holding in (148, 149):
						if target_b in INTERACTIVE_BLOCKS and not is_shift_down:
							pass  # Fall through to interactive block GUI/toggle below
						else:
							# Place liquid source block at current_block (adjacent open space)
							if 0 <= current_block[1] < 256:
								liquid_id = 9 if self.holding == 148 else 15
								self.world.set_block(current_block, liquid_id)
								active_slot = self.gui.hotbar_slots[self.gui.selected_slot]
								if not getattr(self, "flying", False):
									active_slot[0] = 147  # Empty Bucket
									active_slot[1] = 1
								self.holding = self.gui.get_current_block_id()
								return

					# 2. Flint and Steel interactions (151)
					elif self.holding == 151:
						if target_b == 25:  # Right-click placed TNT to prime it!
							self.world.set_block(next_block, 0)
							if hasattr(self, "tnt_manager"):
								self.tnt_manager.spawn_primed_tnt((next_block[0] + 0.5, next_block[1], next_block[2] + 0.5), fuse_ticks=80)
							if not getattr(self, "flying", False):
								held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
								if held_slot and held_slot[0] == 151:
									gui.damage_slot(held_slot, amount=1)
									self.holding = self.gui.get_current_block_id()
							return
						elif target_b == 24 or (0 <= current_block[1] < 256 and any(self.world.get_block_number((current_block[0] + dx, current_block[1] + dy, current_block[2] + dz)) == 24 for dx, dy, dz in ((0, -1, 0), (0, 1, 0), (-1, 0, 0), (1, 0, 0), (0, 0, -1), (0, 0, 1)))):
							# Attempt Nether Portal Ignition inside Obsidian Frame!
							import portal_manager
							ignite_pos = current_block if self.world.get_block_number(current_block) in (0, 78) else next_block
							if portal_manager.portal_manager.try_ignite_portal(self.world, ignite_pos):
								if not getattr(self, "flying", False):
									held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
									if held_slot and held_slot[0] == 151:
										gui.damage_slot(held_slot, amount=1)
										self.holding = self.gui.get_current_block_id()
								return
						if target_b in INTERACTIVE_BLOCKS and not is_shift_down:
							pass  # Fall through to interactive block GUI/toggle below
						else:
							import random
							if face_vector == (0, 1, 0):
								# Top face: place full fire block (78) in open space above
								if 0 <= current_block[1] < 256:
									cur_b = self.world.get_block_number(current_block)
									if cur_b == 0 or cur_b in (10, 12, 31, 33):
										import portal_manager
										if portal_manager.portal_manager.try_ignite_portal(self.world, current_block):
											if not getattr(self, "flying", False):
												held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
												if held_slot and held_slot[0] == 151:
													gui.damage_slot(held_slot, amount=1)
													self.holding = self.gui.get_current_block_id()
											return
										self.world.set_fire(current_block, duration=random.uniform(8.0, 10.0))
										if not getattr(self, "flying", False):
											held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
											if held_slot and held_slot[0] == 151:
												gui.damage_slot(held_slot, amount=1)
												self.holding = self.gui.get_current_block_id()
										return
							elif face_vector in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, -1, 0)):
								# Side or bottom face: mask only the 4 lateral side faces of that block with fire texture for 8-10s
								if target_b != 0:
									self.world.ignite_block_face(next_block, face_idx={0, 1, 4, 5}, duration=random.uniform(8.0, 10.0))
									if not getattr(self, "flying", False):
										held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
										if held_slot and held_slot[0] == 151:
											gui.damage_slot(held_slot, amount=1)
											self.holding = self.gui.get_current_block_id()
									return

					# 3. Hoe Tilling (190 = Wood, 191 = Stone, 192 = Iron, 193 = Gold, 194 = Diamond)
					elif self.holding in (190, 191, 192, 193, 194):
						if target_b in (2, 3, 4):  # Grass Block, Grass, Dirt
							above_num = self.world.get_block_number((next_block[0], next_block[1] + 1, next_block[2]))
							if above_num == 0 or above_num in (10, 12, 31, 33):  # Air or replaceable foliage
								self.world.set_block(next_block, 80)  # Convert to Farmland
								if not getattr(self, "flying", False):
									held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
									if held_slot and held_slot[0] in (190, 191, 192, 193, 194):
										gui.damage_slot(held_slot, amount=1)
								self.holding = self.gui.get_current_block_id()
								return
						elif target_b in INTERACTIVE_BLOCKS and not is_shift_down:
							pass
						else:
							return

					# 4. Crop & Seed Planting (155 = Wheat Seeds, 195 = Carrot, 196 = Potato, 199 = Pumpkin Seeds, 200 = Melon Seeds)
					elif self.holding in (155, 195, 196, 199, 200):
						if target_b == 80 and face_vector == (0, 1, 0) and self.world.get_block_number(current_block) == 0:
							crop_id = 81 if self.holding == 155 else (204 if self.holding == 195 else (205 if self.holding == 196 else (206 if self.holding == 199 else 207)))
							import block_state
							st = block_state.BlockState(crop_id, shape="0")
							self.world.set_block_state(current_block, st)
							self.world.set_block(current_block, crop_id)
							self.gui.consume_active_item()
							self.holding = self.gui.get_current_block_id()
							return
						elif target_b in INTERACTIVE_BLOCKS and not is_shift_down:
							pass
						else:
							return

					# 5. Sugar Cane Planting (202 = Sugar Cane item)
					elif self.holding == 202:
						if self.world.get_block_number(current_block) == 0 and face_vector == (0, 1, 0):
							can_plant = False
							if target_b == 210:
								h_count = 1
								check_y = next_block[1] - 1
								while self.world.get_block_number((next_block[0], check_y, next_block[2])) == 210:
									h_count += 1
									check_y -= 1
								if h_count < 3:
									can_plant = True
							elif target_b in (2, 4, 6):  # Grass, Dirt, Sand touching water
								can_plant = any(
									self.world.get_block_number((next_block[0] + dx, next_block[1], next_block[2] + dz)) in (9, 19, 13)
									for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
								)
							if can_plant:
								self.world.set_block(current_block, 210)
								self.gui.consume_active_item()
								self.holding = self.gui.get_current_block_id()
								return
						if target_b in INTERACTIVE_BLOCKS and not is_shift_down:
							pass
						else:
							return

					# 6. Bone Meal Fertilization (211 = Bone Meal)
					elif self.holding == 211:
						target_pos = next_block
						cur_target_b = target_b
						if cur_target_b == 80:  # Farmland clicked -> check crop on top
							above_crop_pos = (next_block[0], next_block[1] + 1, next_block[2])
							above_crop_b = self.world.get_block_number(above_crop_pos)
							if above_crop_b in (81, 204, 205, 206, 207):
								target_pos = above_crop_pos
								cur_target_b = above_crop_b
						elif cur_target_b not in (81, 204, 205, 206, 207, 210, 156, 225, 235, 245, 255, 265):
							# Ground clicked -> check if sapling or crop is on top of clicked block
							above_pos = (next_block[0], next_block[1] + 1, next_block[2])
							above_b = self.world.get_block_number(above_pos)
							if above_b in (156, 225, 235, 245, 255, 265, 81, 204, 205, 206, 207, 210):
								target_pos = above_pos
								cur_target_b = above_b

						# Crops & Stems (81=Wheat, 204=Carrot, 205=Potato, 206=Pumpkin Stem, 207=Melon Stem)
						if cur_target_b in (81, 204, 205, 206, 207):
							st = self.world.get_block_state(target_pos)
							curr_stage = int(st.shape) if (st and st.shape.isdigit()) else 0
							max_stage = 7 if cur_target_b in (81, 206, 207) else 3
							if curr_stage < max_stage:
								import random, block_state
								# Advances 2-5 growth stages (skipping growth time)
								new_stage = min(max_stage, curr_stage + random.randint(2, 5))
								self.world.set_block_state(target_pos, block_state.BlockState(cur_target_b, shape=str(new_stage)))
								self.gui.consume_active_item()
								self.holding = self.gui.get_current_block_id()
								return
							elif cur_target_b in (206, 207):
								# Mature stem -> try to instantly spawn fruit
								import random
								cardinals = [(1, 0), (-1, 0), (0, 1), (0, -1)]
								random.shuffle(cardinals)
								fruit_spawned = False
								for cdx, cdz in cardinals:
									side_pos = (target_pos[0] + cdx, target_pos[1], target_pos[2] + cdz)
									ground_pos = (target_pos[0] + cdx, target_pos[1] - 1, target_pos[2] + cdz)
									if self.world.get_block_number(side_pos) == 0:
										ground_b = self.world.get_block_number(ground_pos)
										if ground_b in (2, 4, 80):
											fruit_block = 208 if cur_target_b == 206 else 209
											self.world.set_block(side_pos, fruit_block)
											fruit_spawned = True
											break
								if fruit_spawned:
									self.gui.consume_active_item()
									self.holding = self.gui.get_current_block_id()
									return

						# Sugar Cane (210) -> grow +1 stalk up to 3 height
						elif cur_target_b == 210:
							top_y = target_pos[1]
							while self.world.get_block_number((target_pos[0], top_y + 1, target_pos[2])) == 210:
								top_y += 1
							bot_y = target_pos[1]
							while self.world.get_block_number((target_pos[0], bot_y - 1, target_pos[2])) == 210:
								bot_y -= 1
							total_h = (top_y - bot_y) + 1
							if total_h < 3 and self.world.get_block_number((target_pos[0], top_y + 1, target_pos[2])) == 0:
								self.world.set_block((target_pos[0], top_y + 1, target_pos[2]), 210)
								self.gui.consume_active_item()
								self.holding = self.gui.get_current_block_id()
								return

						# All 6 Sapling Varieties (156=Oak, 225=Birch, 235=Spruce, 245=Jungle, 255=Acacia, 265=Dark Oak)
						elif cur_target_b in (156, 225, 235, 245, 255, 265):
							if self.world.can_grow_tree(target_pos, cur_target_b):
								import random
								# High probability (65%) to grow into a tree, 100% in Creative mode
								if random.random() < 0.65 or getattr(self, "flying", False):
									self.world.grow_tree(target_pos, cur_target_b)
								self.gui.consume_active_item()
								self.holding = self.gui.get_current_block_id()
								return
							else:
								# Not enough vertical space / headroom to grow tree
								return

						if target_b in INTERACTIVE_BLOCKS and not is_shift_down:
							pass
						else:
							return

					if target_b in INTERACTIVE_BLOCKS:
						if is_shift_down and is_placeable and not self.camera.intersects_player(current_block, self.holding):
							place_block_with_state(current_block, self.holding, next_block, face_vector, hit_pos)
							return
						else:
							# Normal Right Click -> Toggle Doors/Trapdoors/Fence Gates or Open GUIs
							if target_b in (43, 44, 45, 46, 65, 66, 67, 68, 228, 229, 238, 239, 248, 249, 258, 259, 268, 269):
								st = self.world.get_block_state(next_block)
								cur_open = st.open_state if st else (target_b in (44, 46, 66, 68))
								new_open = not cur_open
								
								# Determine vertical pair positions
								if (st and st.half == "UPPER") or target_b in (65, 66, 67, 68, 229, 239, 249, 259, 269):
									top_pos = next_block
									bot_pos = (next_block[0], next_block[1] - 1, next_block[2])
								else:
									bot_pos = next_block
									top_pos = (next_block[0], next_block[1] + 1, next_block[2])

								for p in (bot_pos, top_pos):
									p_st = self.world.get_block_state(p)
									p_b = self.world.get_block_number(p)
									if p_st:
										p_st.open_state = new_open
										if p_st.block_id in DOOR_TRAPDOOR_TOGGLES and (p_st.block_id in (44, 46, 66, 68)) != new_open:
											p_st.block_id = DOOR_TRAPDOOR_TOGGLES[p_st.block_id]
										self.world.set_block_state(p, p_st)
									elif p_b in DOOR_TRAPDOOR_TOGGLES:
										new_b = DOOR_TRAPDOOR_TOGGLES[p_b] if new_open != (p_b in (44, 46, 66, 68)) else p_b
										self.world.set_block(p, new_b)

							elif target_b in (47, 48, 49, 50, 69, 70, 71, 72, 230, 240, 250, 260, 270):
								st = self.world.get_block_state(next_block)
								if st:
									st.open_state = not st.open_state
									if st.block_id in DOOR_TRAPDOOR_TOGGLES and (st.block_id in (48, 50, 70, 72)) != st.open_state:
										st.block_id = DOOR_TRAPDOOR_TOGGLES[st.block_id]
									self.world.set_block_state(next_block, st)
								elif target_b in DOOR_TRAPDOOR_TOGGLES:
									self.world.set_block(next_block, DOOR_TRAPDOOR_TOGGLES[target_b])

							elif target_b in (75, 76, 272, 273, 274, 275, 276):
								st = self.world.get_block_state(next_block)
								if st:
									st.open_state = not st.open_state
									if st.block_id in (75, 76):
										st.block_id = 76 if st.open_state else 75
									self.world.set_block_state(next_block, st)
								elif target_b in DOOR_TRAPDOOR_TOGGLES:
									self.world.set_block(next_block, DOOR_TRAPDOOR_TOGGLES[target_b])

							elif target_b in (26,):
								self.gui.open_crafting_table()
							elif target_b in (213,):
								self.gui.open_enchanting_table(next_block, self.world)
							elif target_b in (27, 54, 55, 56):
								self.gui.open_furnace(self.world.get_furnace(next_block))
							elif target_b in (37, 57, 58, 59):
								self.gui.open_chest(next_block, self.world)
							elif target_b in (220, 221):
								# Bed interaction
								dim = getattr(self, "dimension", "overworld")
								if dim in ("nether", "end"):
									# Detonate Bed with massive Power 5.0 explosion!
									self.world.set_block(next_block, 0)
									for ox, oz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
										adj_pos = (next_block[0] + ox, next_block[1], next_block[2] + oz)
										if self.world.get_block_number(adj_pos) in (220, 221):
											self.world.set_block(adj_pos, 0)
											break
									import explosion
									explosion.create_explosion(
										self.world,
										(next_block[0] + 0.5, next_block[1] + 0.5, next_block[2] + 0.5),
										power=5.0,
										camera=self.camera,
										mob_manager=getattr(self, "mob_manager", None),
										tnt_manager=getattr(self, "tnt_manager", None),
										item_drop_manager=self.item_drop_manager
									)
									return
								else:
									# Overworld: Set Respawn Point & Sleep / Skip Night
									self.camera.spawn_point = (next_block[0], next_block[1], next_block[2])
									tod = self.time_of_day % 1.0
									is_night = (tod >= 0.75 or tod < 0.23)
									if is_night:
										self.time_of_day = 0.25  # Skip night to dawn
										if hasattr(self, "gui") and hasattr(self.gui, "show_message"):
											self.gui.show_message("Respawn point set. You wake up at dawn.")
									else:
										if hasattr(self, "gui") and hasattr(self.gui, "show_message"):
											self.gui.show_message("Respawn point set. You can sleep only at night.")
									return
							return

					if is_placeable and not self.camera.intersects_player(current_block, self.holding):
						place_block_with_state(current_block, self.holding, next_block, face_vector, hit_pos)

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
		
		hit_ray = hit.Hit_ray(self.world, self.camera.rotation, self.camera.position, hit_liquids=(self.holding == 147))
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
		elif button == pyglet.window.mouse.RIGHT:
			if getattr(self, "bow_charging", False):
				self.bow_charging = False
				charge_ticks = int(self.bow_charge_time * 20.0)
				self.bow_charge_time = 0.0
				self.camera.fov_zoom = 0.0

				# Exact Minecraft Java pull progress formula:
				f = charge_ticks / 20.0
				f = (f * f + f * 2.0) / 3.0
				f = min(1.0, f)

				if f >= 0.1:  # Min 3 ticks to fire
					import enchanting
					held_slot = self.gui.get_current_slot() if hasattr(self.gui, "get_current_slot") else None
					has_inf = enchanting.has_infinity(held_slot)
					if not getattr(self, "flying", False) and not has_inf:
						self.gui.consume_item(158, 1)  # Consume 1 Arrow in Survival mode (unless Infinity)
					is_crit = (f >= 1.0)
					dmg_mult = enchanting.get_bow_power_multiplier(held_slot)
					if hasattr(self, "arrow_manager"):
						self.arrow_manager.shoot_arrow(self.camera, f, is_critical=is_crit, damage_multiplier=dmg_mult)
					if not getattr(self, "flying", False) and held_slot and held_slot[0] == 157:
						gui.damage_slot(held_slot, amount=1)
						self.holding = self.gui.get_current_block_id()
	
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

		if self.flying and self.gui.inventory_open:
			if key == pyglet.window.key.BACKSPACE:
				self.gui.creative_search_text = self.gui.creative_search_text[:-1]
				self.gui.creative_scroll_row = 0
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
				self.left_mouse_down = False
				self.breaking_block = None
				self.break_progress = 0.0
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

		# E Key toggles Inventory (unless search bar is focused in Creative menu)
		if key == pyglet.window.key.E:
			if self.flying and self.gui.inventory_open and getattr(self.gui, 'creative_search_focused', False):
				self.on_text('e')
				return
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
				ench = gui.get_slot_enchantments(slot)

				drop_pos = [px + dir_x * 0.5, py - 0.3 + dir_y * 0.5, pz + dir_z * 0.5]
				self.item_drop_manager.spawn_drop(
					slot[0], drop_cnt,
					drop_pos, velocity=[vx, vy, vz],
					enchantments=ench
				)

				slot[1] -= drop_cnt
				if slot[1] <= 0:
					slot[0] = 0
					gui.set_slot_enchantments(slot, {})
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
