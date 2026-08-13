import math
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

import world

import hit

import noise

import gui
import item_drop

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

		# Crosshair stuff
		self.create_crosshair()

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

		self.time_of_day = 0.0  # Represents time of day, 0.0 to 1.0 where 0.0 is midnight and 0.5 is noon
		self.cycle_speed = 0.01  # Speed of the day-night cycle

	def update_sky_color(self):
		if self.time_of_day < 0.25 or self.time_of_day > 0.75:
			# Night
			gl.glClearColor(0.05, 0.05, 0.1, 1.0)
		elif 0.25 <= self.time_of_day < 0.30 or 0.70 <= self.time_of_day <= 0.75:
			# Sunrise/Sunset
			gl.glClearColor(0.8, 0.4, 0.2, 1.0)
		else:
			# Day
			gl.glClearColor(0.5, 0.8, 1.0, 1.0)
	
	def update(self, delta_time):
		if delta_time > 0:
			self.fps = 0.9 * self.fps + 0.1 * (1.0 / delta_time)

		# Clamp delta_time so player movement and physics remain smooth even during background tasks
		delta_time = min(delta_time, 1.0 / 30.0)

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
					b_type = self.world.block_types[b_num]
					
					if self.flying:
						self.break_progress = 1.0
					else:
						if self.breaking_block == target_block:
							b_time = getattr(b_type, "break_time", 0.4)
							b_time = min(b_time, 0.6)  # Responsive breaking speed
							self.break_progress += delta_time / max(0.05, b_time)
						else:
							self.breaking_block = target_block
							self.break_progress = 0.2  # Fast initial progress on first click

					if self.break_progress >= 1.0:
						# Spawn 3D dropped item entity in the overworld when breaking blocks!
						if not self.flying:
							drop_b = b_num
							if b_num == 2:
								drop_b = 4  # Grass Block drops Dirt
							elif b_num == 5:
								drop_b = 1  # Stone drops Cobblestone
							self.item_drop_manager.spawn_drop(
								drop_b, 1,
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
		self.world.process_load_queue(self.camera.position)
		self.world.tick_liquids()
		self.invalid = True
		
		self.time_of_day += self.cycle_speed * delta_time
		self.time_of_day %= 1.0  # Keep time_of_day in the range [0.0, 1.0]

        # Update the sky color
		self.update_sky_color()
	
	def on_draw(self):
		# Bind 3D world shader FIRST before matrix updates or 3D rendering
		self.shader.use()
		self.camera.update_matrices()

		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
		gl.glUniform1i(self.shader_sampler_location, 0)

		# 1. Render 3D World Geometry
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_CULL_FACE)
		self.clear()
		self.world.draw(self.camera.position)

		# Render 3D overworld dropped items & 2D item sprites
		self.item_drop_manager.draw(self.shader, self.gui)

		# Render 3D block breaking crack overlay
		self.draw_breaking_overlay()

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

			# Restore standard alpha blending, 3D states & 3D shader
			gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
			gl.glEnable(gl.GL_DEPTH_TEST)
			gl.glEnable(gl.GL_CULL_FACE)
			self.shader.use()

		# 4. Render 2D Hotbar & Inventory GUI Overlay
		self.gui.draw()

		# Pyglet's non-vsync window needs commands submitted explicitly here.
		gl.glFlush()

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

	def on_resize(self, width, height):
		gl.glViewport(0, 0, width, height)

		self.camera.width = width
		self.camera.height = height
		self.create_crosshair()

	def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
		self.gui.on_mouse_scroll(scroll_y)
	
	def on_mouse_press(self, x, y, button, modifiers):
		self.gui.mouse_x = x
		self.gui.mouse_y = y

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

		def hit_callback(current_block, next_block):
			if self.world.get_block_number(current_block) != 14 and 0 <= current_block[1] < 256:
				if button == pyglet.window.mouse.RIGHT:
					# Can only place block if player holds a valid block (1 <= block_id < 100)
					if 0 < self.holding < 100 and not self.camera.intersects_player(current_block):
						self.world.set_block(current_block, self.holding)
						# Consume 1 block from active slot in Survival Mode
						self.gui.consume_active_item()
						self.holding = self.gui.get_current_block_id()
				elif button == pyglet.window.mouse.MIDDLE:
					target_b = self.world.get_block_number(next_block)
					if target_b not in (9, 19, 15, 20):
						if self.flying:
							self.gui.hotbar_slots[self.gui.selected_slot] = [target_b, 64]
						else:
							# Search hotbar for target_b slot
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
		self.on_mouse_motion(x, y, delta_x, delta_y)

	def on_key_press(self, key, modifiers):
		self.keys_down[key] = True

		if key == pyglet.window.key.F3:
			self.show_debug = not self.show_debug
			return

		# Number Keys 1 to 9 (top row or numpad)
		if pyglet.window.key._1 <= key <= pyglet.window.key._9:
			slot_idx = key - pyglet.window.key._1
			self.gui.set_selected_slot(slot_idx)
			return
		elif pyglet.window.key.NUM_1 <= key <= pyglet.window.key.NUM_9:
			slot_idx = key - pyglet.window.key.NUM_1
			self.gui.set_selected_slot(slot_idx)
			return

		# E Key toggles Inventory overlay
		if key == pyglet.window.key.E:
			self.gui.toggle_inventory()
			return

		# Key Q drops 1 item from active hotbar slot; Ctrl + Q drops entire slot stack!
		if key == pyglet.window.key.Q and not self.gui.inventory_open:
			slot = self.gui.hotbar_slots[self.gui.selected_slot]
			if slot[0] != 0 and slot[1] > 0:
				px, py, pz = self.camera.position
				rad_x = self.camera.rotation[0]
				rad_y = self.camera.rotation[1]
				vx = math.sin(rad_x) * math.cos(rad_y) * 4.0
				vy = math.sin(rad_y) * 4.0 + 1.5
				vz = -math.cos(rad_x) * math.cos(rad_y) * 4.0

				is_ctrl = bool(modifiers & pyglet.window.key.MOD_CTRL) or self.keys_down.get(pyglet.window.key.LCTRL, False) or self.keys_down.get(pyglet.window.key.RCTRL, False)
				drop_cnt = slot[1] if is_ctrl else 1

				self.item_drop_manager.spawn_drop(
					slot[0], drop_cnt,
					[px, py - 0.4, pz], velocity=[vx, vy, vz]
				)

				slot[1] -= drop_cnt
				if slot[1] <= 0:
					slot[0] = 0
				self.holding = self.gui.get_current_block_id()
			return

		# ESC Key closes Inventory if open
		if key == pyglet.window.key.ESCAPE:
			if self.gui.inventory_open:
				self.gui.toggle_inventory()
			else:
				self.mouse_captured = False
				self.set_exclusive_mouse(False)
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
