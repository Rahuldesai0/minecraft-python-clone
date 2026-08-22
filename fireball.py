"""
Minecraft Java Edition Blaze Small Fireball Projectile System & 3D Renderer
----------------------------------------------------------------------------
Implements authentic Minecraft Java Edition Blaze Small Fireball projectiles:
- Zero gravity (flies in a straight line)
- Constant speed (approx 15 blocks/second / 0.75 blocks/tick)
- Direct hit deals 5 HP (2.5 hearts) damage to the player
- Sets the player on fire for 5.0 seconds on contact
- Ignites fire or fizzles on solid block impact
- 3D Fireball cube mesh with flame trail particles
"""

import math
import random
import ctypes
import pyglet
import pyglet.gl as gl


FIREBALL_VERT_SHADER = """
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

FIREBALL_FRAG_SHADER = """
#version 330
in vec4 interpolated_color;
out vec4 fragment_colour;

void main(void) {
	if (interpolated_color.a < 0.05) discard;
	fragment_colour = interpolated_color;
}
"""


class SmallFireballEntity:
	def __init__(self, position, velocity, shooter=None):
		self.position = list(position)
		self.velocity = list(velocity)  # in blocks/sec
		self.shooter = shooter
		self.lifetime = 5.0
		self.despawn = False
		self.trail_particles = [] # [(x, y, z, life, color), ...]

	def update(self, dt, world, camera=None, gui=None):
		if self.despawn:
			return

		self.lifetime -= dt
		if self.lifetime <= 0.0:
			self.despawn = True
			return

		vx, vy, vz = self.velocity
		dx = vx * dt
		dy = vy * dt
		dz = vz * dt
		step_dist = math.sqrt(dx * dx + dy * dy + dz * dz)

		steps = max(1, int(step_dist / 0.15))
		step_x = dx / steps
		step_y = dy / steps
		step_z = dz * (1.0 / steps)

		# Check collision along trajectory
		for _ in range(steps):
			self.position[0] += step_x
			self.position[1] += step_y
			self.position[2] += step_z

			px, py, pz = self.position

			# Trail flame particles
			if random.random() < 0.35:
				self.trail_particles.append([
					px + random.uniform(-0.1, 0.1),
					py + random.uniform(-0.1, 0.1),
					pz + random.uniform(-0.1, 0.1),
					0.4, # lifetime
					(255, random.randint(100, 220), 0)
				])

			# 1. Player Collision Check
			if camera:
				c_pos = camera.position
				# Player hitbox: 0.6x1.8 bounding box centered at eye level - 0.9
				min_x, max_x = c_pos[0] - 0.35, c_pos[0] + 0.35
				min_y, max_y = c_pos[1] - 1.6, c_pos[1] + 0.2
				min_z, max_z = c_pos[2] - 0.35, c_pos[2] + 0.35

				if min_x <= px <= max_x and min_y <= py <= max_y and min_z <= pz <= max_z:
					is_flying = getattr(camera, 'flying', False)
					if hasattr(camera, 'take_damage'):
						camera.take_damage(5, flying=is_flying, gui=gui, world=world)
					if hasattr(camera, 'fire_timer'):
						camera.fire_timer = max(getattr(camera, 'fire_timer', 0.0), 5.0)
					self.despawn = True
					return

			# 2. Solid Block Collision Check
			bx = int(math.floor(px))
			by = int(math.floor(py))
			bz = int(math.floor(pz))

			if world:
				b_num = world.get_block_number((bx, by, bz))
				if b_num != 0 and b_num not in (9, 19, 15, 20, 78, 88, 89, 94):
					# Hit solid block! Place fire on adjacent top/side if air
					if world.get_block_number((bx, by + 1, bz)) == 0 and 0 <= by + 1 < 127:
						world.set_block((bx, by + 1, bz), 78) # Fire
					self.despawn = True
					return

		# Update trail particles
		alive_particles = []
		for p in self.trail_particles:
			p[3] -= dt
			if p[3] > 0:
				alive_particles.append(p)
		self.trail_particles = alive_particles


class FireballManager:
	def __init__(self, world):
		self.world = world
		self.fireballs = []
		self.vao = None
		self.vbo = None
		self.shader_program = None
		self.initialized = False

	def spawn_fireball(self, position, velocity, shooter=None):
		fb = SmallFireballEntity(position, velocity, shooter=shooter)
		self.fireballs.append(fb)
		return fb

	def update(self, dt, camera=None, gui=None):
		alive = []
		for fb in self.fireballs:
			fb.update(dt, self.world, camera=camera, gui=gui)
			if not fb.despawn or fb.trail_particles:
				alive.append(fb)
		self.fireballs = alive

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
		if not self.fireballs:
			return

		self._init_gl()
		if not self.initialized or not self.shader_program:
			return

		vertex_data = []

		def add_cube(cx, cy, cz, r, cr, cg, cb, ca=1.0):
			# 6 faces * 2 triangles * 3 vertices = 36 vertices
			faces = [
				# +Z
				(cx-r, cy-r, cz+r), (cx+r, cy-r, cz+r), (cx+r, cy+r, cz+r),
				(cx-r, cy-r, cz+r), (cx+r, cy+r, cz+r), (cx-r, cy+r, cz+r),
				# -Z
				(cx+r, cy-r, cz-r), (cx-r, cy-r, cz-r), (cx-r, cy+r, cz-r),
				(cx+r, cy-r, cz-r), (cx-r, cy+r, cz-r), (cx+r, cy+r, cz-r),
				# +X
				(cx+r, cy-r, cz+r), (cx+r, cy-r, cz-r), (cx+r, cy+r, cz-r),
				(cx+r, cy-r, cz+r), (cx+r, cy+r, cz-r), (cx+r, cy+r, cz+r),
				# -X
				(cx-r, cy-r, cz-r), (cx-r, cy-r, cz+r), (cx-r, cy+r, cz+r),
				(cx-r, cy-r, cz-r), (cx-r, cy+r, cz+r), (cx-r, cy+r, cz-r),
				# +Y
				(cx-r, cy+r, cz+r), (cx+r, cy+r, cz+r), (cx+r, cy+r, cz-r),
				(cx-r, cy+r, cz+r), (cx+r, cy+r, cz-r), (cx-r, cy+r, cz-r),
				# -Y
				(cx-r, cy-r, cz-r), (cx+r, cy-r, cz-r), (cx+r, cy-r, cz+r),
				(cx-r, cy-r, cz-r), (cx+r, cy-r, cz+r), (cx-r, cy-r, cz+r),
			]
			for vx, vy, vz in faces:
				vertex_data.extend([vx, vy, vz, cr, cg, cb, ca])

		for fb in self.fireballs:
			if not fb.despawn:
				fx, fy, fz = fb.position
				# Outer flame core (size 0.20)
				add_cube(fx, fy, fz, 0.16, 1.0, 0.5, 0.0, 0.95)
				# Inner bright core (size 0.10)
				add_cube(fx, fy, fz, 0.09, 1.0, 0.95, 0.2, 1.0)

			for px, py, pz, life, col in fb.trail_particles:
				alpha = max(0.0, min(1.0, life / 0.4))
				add_cube(px, py, pz, 0.05, col[0]/255.0, col[1]/255.0, col[2]/255.0, alpha)

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

		gl.glBindVertexArray(self.vao)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_data), c_data, gl.GL_DYNAMIC_DRAW)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, v_count)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
		gl.glBindVertexArray(0)
		self.shader_program.stop()
