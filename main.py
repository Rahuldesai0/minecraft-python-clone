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

class Window(pyglet.window.Window):
	def __init__(self, **args):
		super().__init__(**args)

		# create world

		self.world = world.World()
		
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

		# other stuff

		self.holding = 7
		self.sprinting = False
		self.flying = False

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

        # Define sky colors for different times of the day
		self.sky_colors = {
            'midnight': (15/255, 15/255, 45/255, 1.0),
            'dawn': (135/255, 206/255, 250/255, 1.0),
            'noon': (135/255, 206/255, 250/255, 1.0),
            'dusk': (250/255, 128/255, 114/255, 1.0),
            'night': (25/255, 25/255, 112/255, 1.0)
        }

	def interpolate_color(self, color1, color2, factor):
		return tuple(c1 + (c2 - c1) * factor for c1, c2 in zip(color1, color2))

	def update_sky_color(self):
		if self.time_of_day < 0.25:
            # Dawn
			factor = self.time_of_day / 0.25
			color = self.interpolate_color(self.sky_colors['midnight'], self.sky_colors['dawn'], factor)
		elif self.time_of_day < 0.5:
            # Noon
			factor = (self.time_of_day - 0.25) / 0.25
			color = self.interpolate_color(self.sky_colors['dawn'], self.sky_colors['noon'], factor)
		elif self.time_of_day < 0.75:
            # Dusk
			factor = (self.time_of_day - 0.5) / 0.25
			color = self.interpolate_color(self.sky_colors['noon'], self.sky_colors['dusk'], factor)
		else:
            # Night to Midnight
			factor = (self.time_of_day - 0.75) / 0.25
			color = self.interpolate_color(self.sky_colors['dusk'], self.sky_colors['night'], factor)

            # Additional blending for smoother transition from night to midnight
			if self.time_of_day > 0.99:
				additional_factor = (self.time_of_day - 0.99) / 0.01
				color = self.interpolate_color(color, self.sky_colors['midnight'], additional_factor)

		gl.glClearColor(*color)
	
	def update(self, delta_time):
		if delta_time > 0:
			self.fps = 0.9 * self.fps + 0.1 * (1.0 / delta_time)

		# Clamp delta_time so player movement and physics remain smooth even during background tasks
		delta_time = min(delta_time, 1.0 / 30.0)

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

		# Pyglet's non-vsync window needs commands submitted explicitly here.
		gl.glFlush()

	
	# input functions

	def on_resize(self, width, height):
		gl.glViewport(0, 0, width, height)

		self.camera.width = width
		self.camera.height = height
		self.create_crosshair()
	
	def on_mouse_press(self, x, y, button, modifiers):
		if not self.mouse_captured:
			self.mouse_captured = True
			self.set_exclusive_mouse(True)

			return

		def hit_callback(current_block, next_block):
			if self.world.get_block_number(current_block) != 14 and 0 <= current_block[1] < 256:
				if button == pyglet.window.mouse.RIGHT:
					# Do not allow placing blocks inside the player's body bounding box
					if not self.camera.intersects_player(current_block):
						self.world.set_block(current_block, self.holding)
				elif button == pyglet.window.mouse.LEFT:
					# Cannot break liquids (9, 19, 15, 20) or unbreakable Bedrock (14)
					if self.world.get_block_number(next_block) not in (9, 19, 15, 20, 14):
						self.world.set_block(next_block, 0)
				elif button == pyglet.window.mouse.MIDDLE:
					target_b = self.world.get_block_number(next_block)
					if target_b not in (9, 19, 15, 20):
						self.holding = target_b
		
		hit_ray = hit.Hit_ray(self.world, self.camera.rotation, self.camera.position)

		while hit_ray.distance < hit.HIT_RANGE:
			if hit_ray.step(hit_callback):
				break
	
	def on_mouse_motion(self, x, y, delta_x, delta_y):
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

		if not self.mouse_captured:
			return

		if key == pyglet.window.key.LCTRL: 
			self.sprinting = True
		elif key == pyglet.window.key.R: 
			self.camera.position = [0, 80, 0]
		elif key == pyglet.window.key.F: 
			self.flying = not self.flying
		elif key == pyglet.window.key.ESCAPE:
			self.mouse_captured = False
			self.set_exclusive_mouse(False)

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
