"""
Minecraft Java Edition Dragon Fireball & Dragon's Breath Effect Cloud System
----------------------------------------------------------------------------
Implements:
1. DragonFireballEntity: Magenta/purple projectile launched by the Ender Dragon.
   - Flies towards target player/block coordinates.
   - Explodes on impact and spawns a DragonBreathCloud.
2. DragonBreathCloud: Lingering area-of-effect magic cloud (radius 3.5m, duration 6.0s).
   - Emits swirling magenta/purple particle effects.
   - Deals 3 magic damage every 0.5s to players standing inside in Survival mode.
3. DragonFireballManager: Batch OpenGL 3.3 renderer for fireballs, trails, and breath clouds.
"""

import math
import random
import time
import ctypes
import pyglet
import pyglet.gl as gl
import block_state

FIREBALL_VERT_SHADER = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec4 a_color;

uniform mat4 matrix;

out vec4 v_color;

void main() {
    v_color = a_color;
    gl_Position = matrix * vec4(a_position, 1.0);
}
"""

FIREBALL_FRAG_SHADER = """
#version 330 core
in vec4 v_color;
out vec4 fragColor;

void main() {
    if (v_color.a < 0.05) discard;
    fragColor = v_color;
}
"""


class DragonBreathCloud:
	"""Lingering Dragon's Breath square area-of-effect hazard cloud."""
	def __init__(self, position, half_size=3.0, duration=6.0):
		self.position = list(position) # [x, y, z] center on ground
		self.half_size = half_size      # 3.0m -> 6.0m x 6.0m square area
		self.duration = duration
		self.lifetime = 0.0
		self.is_dead = False
		self.particles = [] # [(x, y, z, life, max_life, col), ...]
		self.last_damage_time = 0.0

	def update(self, dt, camera=None, gui=None, world=None):
		self.lifetime += dt
		if self.lifetime >= self.duration:
			self.is_dead = True
			self.particles.clear()
			return

		cx, cy, cz = self.position
		hs = self.half_size

		# 1. Spawn swirling magenta/purple particles across the square area
		if random.random() < 0.85:
			# Interior particles
			px = cx + random.uniform(-hs, hs)
			py = cy + random.uniform(0.1, 1.2)
			pz = cz + random.uniform(-hs, hs)
			col = random.choice([
				(0.85, 0.15, 0.95),
				(0.70, 0.05, 0.85),
				(0.95, 0.35, 1.00),
				(0.55, 0.00, 0.70)
			])
			self.particles.append([px, py, pz, 0.75, 0.75, col])

		# 2. Spawn perimeter particles marking the square boundary
		if random.random() < 0.60:
			edge = random.randint(0, 3)
			if edge == 0:    # North edge (+Z)
				px, pz = cx + random.uniform(-hs, hs), cz + hs
			elif edge == 1:  # South edge (-Z)
				px, pz = cx + random.uniform(-hs, hs), cz - hs
			elif edge == 2:  # East edge (+X)
				px, pz = cx + hs, cz + random.uniform(-hs, hs)
			else:            # West edge (-X)
				px, pz = cx - hs, cz + random.uniform(-hs, hs)

			py = cy + random.uniform(0.05, 0.6)
			self.particles.append([px, py, pz, 0.6, 0.6, (1.0, 0.25, 0.95)])

		# Update active particles
		alive_p = []
		for p in self.particles:
			p[3] -= dt
			p[1] += dt * 0.35  # Slow upward drift
			if p[3] > 0:
				alive_p.append(p)
		self.particles = alive_p

		# 3. Damage Survival player standing inside the square area
		if camera:
			is_creative = getattr(camera, 'flying', False) or getattr(getattr(camera, 'window', None), 'flying', False)
			if not is_creative:
				px, py, pz = camera.position
				# Check if player is inside square bounding box
				in_square_x = (cx - hs <= px <= cx + hs)
				in_square_z = (cz - hs <= pz <= cz + hs)
				in_square_y = (-0.5 <= py - cy <= 2.4)

				if in_square_x and in_square_z and in_square_y:
					now = time.time()
					if now - self.last_damage_time >= 0.5:
						self.last_damage_time = now
						if hasattr(camera, 'take_damage'):
							camera.take_damage(3, flying=False, gui=gui, world=world)


class DragonFireballEntity:
	"""Minecraft Java Edition Ender Dragon Fireball projectile."""
	def __init__(self, position, target_pos, speed=22.0):
		self.position = list(position)
		self.speed = speed
		self.despawn = False
		self.lifetime = 6.0
		self.trail_particles = []

		# Compute direction vector towards target
		dx = target_pos[0] - position[0]
		dy = target_pos[1] - position[1]
		dz = target_pos[2] - position[2]
		dist = math.sqrt(dx * dx + dy * dy + dz * dz)
		norm = max(0.001, dist)
		self.velocity = [
			(dx / norm) * speed,
			(dy / norm) * speed,
			(dz / norm) * speed
		]

	def update(self, dt, world, camera=None, gui=None, fireball_manager=None):
		if self.despawn:
			return

		self.lifetime -= dt
		if self.lifetime <= 0.0:
			self.despawn = True
			self._impact(fireball_manager)
			return

		vx, vy, vz = self.velocity
		dx = vx * dt
		dy = vy * dt
		dz = vz * dt
		step_dist = math.sqrt(dx * dx + dy * dy + dz * dz)

		steps = max(1, int(step_dist / 0.20))
		step_x = dx / steps
		step_y = dy / steps
		step_z = dz / steps

		for _ in range(steps):
			self.position[0] += step_x
			self.position[1] += step_y
			self.position[2] += step_z

			px, py, pz = self.position

			# Trail particles (magenta and dark violet)
			if random.random() < 0.45:
				self.trail_particles.append([
					px + random.uniform(-0.15, 0.15),
					py + random.uniform(-0.15, 0.15),
					pz + random.uniform(-0.15, 0.15),
					0.5,
					random.choice([(0.9, 0.2, 0.95), (0.6, 0.0, 0.8), (0.4, 0.0, 0.5)])
				])

			# 1. Player Collision Check
			if camera:
				c_pos = camera.position
				is_creative = getattr(camera, 'flying', False) or getattr(getattr(camera, 'window', None), 'flying', False)
				min_x, max_x = c_pos[0] - 0.45, c_pos[0] + 0.45
				min_y, max_y = c_pos[1] - 1.6, c_pos[1] + 0.2
				min_z, max_z = c_pos[2] - 0.45, c_pos[2] + 0.45

				if min_x <= px <= max_x and min_y <= py <= max_y and min_z <= pz <= max_z:
					if not is_creative and hasattr(camera, 'take_damage'):
						camera.take_damage(6, flying=False, gui=gui, world=world)
					self.despawn = True
					self._impact(fireball_manager)
					return

			# 2. Solid Block Collision Check
			bx = int(math.floor(px))
			by = int(math.floor(py))
			bz = int(math.floor(pz))

			if world:
				b_num = world.get_block_number((bx, by, bz))
				if b_num != 0 and b_num not in block_state.PASSABLE_BLOCKS:
					self.despawn = True
					self._impact(fireball_manager)
					return

		# Update trail particles
		alive_p = []
		for p in self.trail_particles:
			p[3] -= dt
			if p[3] > 0:
				alive_p.append(p)
		self.trail_particles = alive_p

	def _impact(self, fireball_manager):
		"""Spawn Dragon's Breath cloud at impact location."""
		if fireball_manager:
			fireball_manager.spawn_breath_cloud(self.position)


class DragonFireballManager:
	"""Manages active Dragon Fireballs and lingering Dragon's Breath clouds."""
	def __init__(self, world):
		self.world = world
		self.fireballs = []
		self.breath_clouds = []
		self.vao = None
		self.vbo = None
		self.shader_program = None
		self.initialized = False

	def spawn_fireball(self, position, target_pos):
		fb = DragonFireballEntity(position, target_pos)
		self.fireballs.append(fb)
		return fb

	def spawn_breath_cloud(self, position):
		cloud = DragonBreathCloud(position)
		self.breath_clouds.append(cloud)
		return cloud

	def update(self, dt, camera=None, gui=None):
		# Update Fireballs
		alive_fb = []
		for fb in self.fireballs:
			fb.update(dt, self.world, camera=camera, gui=gui, fireball_manager=self)
			if not fb.despawn or fb.trail_particles:
				alive_fb.append(fb)
		self.fireballs = alive_fb

		# Update Breath Clouds
		alive_bc = []
		for bc in self.breath_clouds:
			if not bc.is_dead:
				bc.update(dt, camera=camera, gui=gui, world=self.world)
				if not bc.is_dead:
					alive_bc.append(bc)
		self.breath_clouds = alive_bc

	def _init_gl(self):
		if self.initialized:
			return
		try:
			vs = pyglet.graphics.shader.Shader(FIREBALL_VERT_SHADER, 'vertex')
			fs = pyglet.graphics.shader.Shader(FIREBALL_FRAG_SHADER, 'fragment')
			self.shader_program = pyglet.graphics.shader.ShaderProgram(vs, fs)

			self.vao = gl.GLuint()
			gl.glGenVertexArrays(1, ctypes.byref(self.vao))
			self.vbo = gl.GLuint()
			gl.glGenBuffers(1, ctypes.byref(self.vbo))

			gl.glBindVertexArray(self.vao)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)

			# Position: loc=0 (3 floats)
			gl.glEnableVertexAttribArray(0)
			gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 7 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0))

			# Color: loc=1 (4 floats)
			gl.glEnableVertexAttribArray(1)
			gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 7 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(3 * ctypes.sizeof(ctypes.c_float)))

			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
			gl.glBindVertexArray(0)
			self.initialized = True
		except Exception:
			pass

	def draw(self, camera):
		if not self.fireballs and not self.breath_clouds:
			return

		self._init_gl()
		if not self.initialized or not self.shader_program:
			return

		vertex_data = []

		def add_cube(cx, cy, cz, r, cr, cg, cb, ca=1.0):
			faces = [
				(cx-r, cy-r, cz+r), (cx+r, cy-r, cz+r), (cx+r, cy+r, cz+r),
				(cx-r, cy-r, cz+r), (cx+r, cy+r, cz+r), (cx-r, cy+r, cz+r),
				(cx+r, cy-r, cz-r), (cx-r, cy-r, cz-r), (cx-r, cy+r, cz-r),
				(cx+r, cy-r, cz-r), (cx-r, cy+r, cz-r), (cx+r, cy+r, cz-r),
				(cx+r, cy-r, cz+r), (cx+r, cy-r, cz-r), (cx+r, cy+r, cz-r),
				(cx+r, cy-r, cz+r), (cx+r, cy+r, cz-r), (cx+r, cy+r, cz+r),
				(cx-r, cy-r, cz-r), (cx-r, cy-r, cz+r), (cx-r, cy+r, cz+r),
				(cx-r, cy-r, cz-r), (cx-r, cy+r, cz+r), (cx-r, cy+r, cz-r),
				(cx-r, cy+r, cz+r), (cx+r, cy+r, cz+r), (cx+r, cy+r, cz-r),
				(cx-r, cy+r, cz+r), (cx+r, cy+r, cz-r), (cx-r, cy+r, cz-r),
				(cx-r, cy-r, cz-r), (cx+r, cy-r, cz-r), (cx+r, cy-r, cz+r),
				(cx-r, cy-r, cz-r), (cx+r, cy-r, cz+r), (cx-r, cy-r, cz+r),
			]
			for vx, vy, vz in faces:
				vertex_data.extend([vx, vy, vz, cr, cg, cb, ca])

		# Render Fireballs
		for fb in self.fireballs:
			if not fb.despawn:
				fx, fy, fz = fb.position
				# Outer magenta flame (r=0.25)
				add_cube(fx, fy, fz, 0.25, 0.85, 0.15, 0.95, 0.95)
				# Inner bright core (r=0.14)
				add_cube(fx, fy, fz, 0.14, 1.0, 0.75, 1.0, 1.0)

			for px, py, pz, life, col in fb.trail_particles:
				alpha = max(0.0, min(1.0, life / 0.5))
				add_cube(px, py, pz, 0.08, col[0], col[1], col[2], alpha)

		# Render Breath Clouds
		for bc in self.breath_clouds:
			for px, py, pz, life, max_life, col in bc.particles:
				alpha = max(0.0, min(1.0, life / max_life)) * 0.85
				add_cube(px, py, pz, 0.12, col[0], col[1], col[2], alpha)

		if not vertex_data:
			return

		v_count = len(vertex_data) // 7
		c_data = (ctypes.c_float * len(vertex_data))(*vertex_data)

		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
		gl.glEnable(gl.GL_DEPTH_TEST)

		self.shader_program.use()
		if hasattr(camera, 'matrix'):
			gl.glUniformMatrix4fv(
				gl.glGetUniformLocation(self.shader_program.id, b"matrix"),
				1, gl.GL_FALSE,
				(gl.GLfloat * 16)(*camera.matrix)
			)
		elif hasattr(camera, 'mv_matrix'):
			mvp_matrix = camera.mv_matrix * camera.p_matrix
			flat_matrix = [val for row in mvp_matrix.data for val in row]
			gl.glUniformMatrix4fv(
				gl.glGetUniformLocation(self.shader_program.id, b"matrix"),
				1, gl.GL_FALSE,
				(gl.GLfloat * 16)(*flat_matrix)
			)

		gl.glBindVertexArray(self.vao)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_data), c_data, gl.GL_DYNAMIC_DRAW)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, v_count)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
		gl.glBindVertexArray(0)
		self.shader_program.stop()
