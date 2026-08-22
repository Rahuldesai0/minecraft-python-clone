"""
Minecraft Java Edition Eye of Ender Projectile & Stronghold Guidance System
----------------------------------------------------------------------------
Implements authentic Minecraft Java Edition Eye of Ender entity:
- Thrown by right-clicking with an Eye of Ender in the Overworld.
- Calculates direction to the nearest Stronghold via concentric ring algorithm.
- Upward guiding flight path (~12 m/s) when far; downward diving flight path when directly above.
- 80 ticks (4.0s) lifetime.
- 80% chance to drop as a recoverable Eye of Ender item; 20% chance to shatter.
- Purple/teal portal particle trail and 3D rendering.
"""

import math
import random
import ctypes
import pyglet
import pyglet.gl as gl
import stronghold_manager
import gui as gui_module


EYE_VERT_SHADER = """
#version 330
layout(location = 0) in vec3 vertex_position;
layout(location = 1) in vec4 vertex_color;

out vec4 interpolated_color;

uniform mat4 matrix;

void main(void) {
	interpolated_color = vertex_color;
	gl_Position = matrix * vec4(vertex_position, 1.0);
}
"""

EYE_FRAG_SHADER = """
#version 330
in vec4 interpolated_color;
out vec4 fragment_colour;

void main(void) {
	if (interpolated_color.a < 0.05) discard;
	fragment_colour = interpolated_color;
}
"""


class EnderEyeEntity:
	def __init__(self, position, target_stronghold_pos):
		self.position = list(position)
		self.target_pos = list(target_stronghold_pos)
		self.age = 0.0
		self.max_age = 4.0  # 80 ticks = 4.0s
		self.despawn = False
		self.trail_particles = [] # [(x, y, z, life, color), ...]

		# Calculate trajectory to Stronghold
		px, py, pz = self.position
		sx, sy, sz = self.target_pos
		dx = sx - px
		dz = sz - pz
		dist_xz = math.sqrt(dx * dx + dz * dz)

		self.is_diving = (dist_xz <= 16.0)

		if not self.is_diving:
			# Ascending and guiding horizontally toward Stronghold
			speed = 12.0
			self.velocity = [
				(dx / dist_xz) * speed,
				2.2, # Initial upward boost
				(dz / dist_xz) * speed
			]
		else:
			# Directly above Stronghold! Dive down to indicate entrance
			self.velocity = [
				(dx / max(0.1, dist_xz)) * 1.5,
				-4.5, # Dive downwards
				(dz / max(0.1, dist_xz)) * 1.5
			]

	def update(self, dt, world, item_drop_manager=None):
		if self.despawn:
			return

		self.age += dt

		# Flight kinematics
		if not self.is_diving:
			# Gradually level off vertical velocity
			if self.age < 1.5:
				self.velocity[1] = max(0.2, self.velocity[1] - dt * 1.5)
			else:
				self.velocity[1] = max(-0.5, self.velocity[1] - dt * 0.8)
		else:
			# Accelerate downward
			self.velocity[1] = max(-8.0, self.velocity[1] - dt * 4.0)

		self.position[0] += self.velocity[0] * dt
		self.position[1] += self.velocity[1] * dt
		self.position[2] += self.velocity[2] * dt

		# Emit purple and cyan portal trail particles
		if random.random() < 0.85:
			p_col = random.choice([
				(0.65, 0.15, 0.95, 0.9),  # Purple
				(0.20, 0.85, 0.75, 0.9),  # Cyan
				(0.85, 0.35, 1.00, 0.9)   # Magenta
			])
			ox = self.position[0] + random.uniform(-0.15, 0.15)
			oy = self.position[1] + random.uniform(-0.15, 0.15)
			oz = self.position[2] + random.uniform(-0.15, 0.15)
			self.trail_particles.append([ox, oy, oz, 0.6, p_col])

		# Update particle lifetimes
		i = 0
		while i < len(self.trail_particles):
			p = self.trail_particles[i]
			p[3] -= dt
			p[1] += dt * 0.2
			if p[3] <= 0.0:
				self.trail_particles.pop(i)
			else:
				i += 1

		# Flight completion after max_age
		if self.age >= self.max_age:
			self.despawn = True
			# 80% chance: drops as recoverable Eye of Ender item (177)
			# 20% chance: shatters and disappears
			if random.random() < 0.80:
				if item_drop_manager:
					item_drop_manager.spawn_drop(177, 1, self.position)


class EnderEyeManager:
	def __init__(self, world):
		self.world = world
		self.eyes = []
		self.shader_program = None
		self.initialized = False
		self.vao = None
		self.vbo = None

	def throw_eye(self, player_pos, world_seed=0):
		"""Throws an Eye of Ender projectile from player_pos towards the nearest Stronghold."""
		# Eye spawn position (player eye height: +1.62)
		eye_pos = (player_pos[0], player_pos[1] + 1.62, player_pos[2])

		# Determine nearest Stronghold via concentric ring algorithm
		sx, sy, sz, dist = stronghold_manager.get_nearest_stronghold(eye_pos, seed=world_seed)

		eye = EnderEyeEntity(eye_pos, (sx, sy, sz))
		self.eyes.append(eye)
		return eye

	def update(self, dt, item_drop_manager=None):
		i = 0
		while i < len(self.eyes):
			eye = self.eyes[i]
			eye.update(dt, self.world, item_drop_manager=item_drop_manager)
			if eye.despawn and not eye.trail_particles:
				self.eyes.pop(i)
			else:
				i += 1

	def _init_gl(self):
		if self.initialized:
			return
		try:
			vs = pyglet.graphics.shader.Shader(EYE_VERT_SHADER, 'vertex')
			fs = pyglet.graphics.shader.Shader(EYE_FRAG_SHADER, 'fragment')
			self.shader_program = pyglet.graphics.shader.ShaderProgram(vs, fs)

			self.vao = gl.GLuint()
			gl.glGenVertexArrays(1, ctypes.byref(self.vao))
			self.vbo = gl.GLuint()
			gl.glGenBuffers(1, ctypes.byref(self.vbo))

			gl.glBindVertexArray(self.vao)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)

			# Vertex position (loc=0, 3 floats)
			gl.glEnableVertexAttribArray(0)
			gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 7 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0))

			# Vertex color (loc=1, 4 floats)
			gl.glEnableVertexAttribArray(1)
			gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 7 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(3 * ctypes.sizeof(ctypes.c_float)))

			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
			gl.glBindVertexArray(0)
			self.initialized = True
		except Exception:
			pass

	def draw(self, camera):
		if not self.eyes:
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

		for eye in self.eyes:
			ex, ey, ez = eye.position
			if not eye.despawn:
				# 3D Eye of Ender Cube (outer teal layer + inner core)
				add_cube(ex, ey, ez, 0.12, 0.15, 0.85, 0.65, 1.0)
				add_cube(ex, ey, ez, 0.06, 0.10, 0.40, 0.30, 1.0)

			for px, py, pz, life, color in eye.trail_particles:
				alpha = max(0.0, min(1.0, life / 0.6))
				add_cube(px, py, pz, 0.04, color[0], color[1], color[2], alpha)

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
