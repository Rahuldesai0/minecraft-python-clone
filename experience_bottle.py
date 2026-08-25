"""
Minecraft Java Edition Experience Bottle (Bottle o' Enchanting) Projectile System
---------------------------------------------------------------------------------
Implements:
1. Authentic throwable Experience Bottle entity with projectile physics:
   - Initial throw velocity along player camera aim vector.
   - Gravity acceleration and air drag matching Java edition.
2. Solid block and mob impact detection:
   - On impact with any solid block or mob, bottle shatters with custom sparkle particles.
   - Drops 3 to 11 XP (via XP orbs) scattered at the impact point.
3. Batch OpenGL 3.3 3D Renderer for flying bottle entity and particle bursts.
"""

import math
import random
import ctypes
import pyglet
import pyglet.gl as gl

EXP_VERT_SHADER = """
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

EXP_FRAG_SHADER = """
#version 330
in vec4 interpolated_color;
out vec4 fragment_colour;

void main(void) {
	if (interpolated_color.a < 0.05) discard;
	fragment_colour = interpolated_color;
}
"""


class ExperienceBottleEntity:
	"""Throwable Bottle o' Enchanting projectile entity."""
	def __init__(self, position, velocity, shooter="player"):
		self.position = list(position)
		self.velocity = list(velocity)
		self.shooter = shooter
		self.age = 0.0
		self.max_age = 20.0
		self.despawn = False
		self.trail_particles = []  # [(x, y, z, life, color), ...]

	def update(self, dt, world, item_drop_manager=None, mob_manager=None):
		if self.despawn:
			# Update remaining splash / trail particles
			alive_p = []
			for p in self.trail_particles:
				p[3] -= dt
				p[1] += dt * 0.25  # float slightly upwards
				if p[3] > 0.0:
					alive_p.append(p)
			self.trail_particles = alive_p
			return

		dt_ticks = dt * 20.0
		self.age += dt

		if self.age >= self.max_age:
			self.despawn = True
			return

		# Gravity (14.0 m/s^2)
		self.velocity[1] -= 14.0 * dt

		# Air drag (0.99 per tick)
		drag = 0.99 ** dt_ticks
		self.velocity[0] *= drag
		self.velocity[1] *= drag
		self.velocity[2] *= drag

		vx, vy, vz = self.velocity
		dx = vx * dt
		dy = vy * dt
		dz = vz * dt
		step_dist = math.sqrt(dx * dx + dy * dy + dz * dz)

		steps = max(1, int(step_dist / 0.15))
		step_x = dx / steps
		step_y = dy / steps
		step_z = dz / steps

		for _ in range(steps):
			self.position[0] += step_x
			self.position[1] += step_y
			self.position[2] += step_z

			px, py, pz = self.position

			# 1. Trail Particles (Magic green and sparkling gold)
			if random.random() < 0.75:
				p_col = random.choice([
					(0.35, 0.95, 0.15, 0.95),  # Lime Green
					(1.00, 0.95, 0.20, 0.95),  # Gold Yellow
					(0.20, 0.85, 0.55, 0.95),  # Emerald
					(0.85, 1.00, 0.30, 0.95)   # Light Yellow-Green
				])
				self.trail_particles.append([
					px + random.uniform(-0.08, 0.08),
					py + random.uniform(-0.08, 0.08),
					pz + random.uniform(-0.08, 0.08),
					0.6,
					p_col
				])

			# 2. Mob Hit Check
			if mob_manager and hasattr(mob_manager, "mobs"):
				for mob in mob_manager.mobs:
					if getattr(mob, "dead", False):
						continue
					mx, my, mz = mob.position
					dist_sq = (px - mx) ** 2 + (py - (my + 0.8)) ** 2 + (pz - mz) ** 2
					if dist_sq < 0.8:
						self._on_impact(world, item_drop_manager, (px, py, pz))
						return

			# 3. Solid Block Collision
			bx = int(round(px))
			by = int(round(py))
			bz = int(round(pz))

			if world:
				b_num = world.get_block_number((bx, by, bz))
				# Non-solid passable blocks
				if b_num != 0 and b_num not in (9, 19, 15, 20, 78, 183):
					self._on_impact(world, item_drop_manager, (px, py, pz))
					return

				if py <= -30.0:
					self.despawn = True
					return

	def _on_impact(self, world, item_drop_manager, hit_pos):
		"""Shatters the bottle, spawns splash particles, and drops 3 to 11 XP orbs."""
		self.despawn = True
		hx, hy, hz = hit_pos

		# 1. Burst of magical enchantment splash particles
		for _ in range(24):
			p_col = random.choice([
				(0.40, 1.00, 0.15, 1.0),  # Bright Lime
				(1.00, 0.95, 0.10, 1.0),  # Radiant Gold
				(0.15, 0.85, 0.70, 1.0),  # Teal Magic
				(0.90, 1.00, 0.40, 1.0)   # Pale Yellow
			])
			self.trail_particles.append([
				hx + random.uniform(-0.35, 0.35),
				hy + random.uniform(-0.15, 0.45),
				hz + random.uniform(-0.35, 0.35),
				random.uniform(0.5, 0.9),
				p_col
			])

		# 2. Spawn 3 to 11 XP via ItemDropManager
		total_xp = random.randint(3, 11)
		if item_drop_manager:
			# Split into 1 to 3 orbs for authentic Minecraft feel
			num_orbs = min(3, max(1, total_xp // 3))
			rem = total_xp
			for i in range(num_orbs):
				orb_val = rem // (num_orbs - i)
				rem -= orb_val
				vx = random.uniform(-1.6, 1.6)
				vy = random.uniform(1.5, 3.8)
				vz = random.uniform(-1.6, 1.6)
				item_drop_manager.spawn_xp_orb(orb_val, [hx, hy + 0.1, hz], velocity=[vx, vy, vz])


class ExperienceBottleManager:
	"""Manages active Experience Bottle projectiles and OpenGL rendering."""
	def __init__(self, world):
		self.world = world
		self.bottles = []
		self.shader_program = None
		self.initialized = False
		self.vao = None
		self.vbo = None

	def throw_bottle(self, player_pos, camera_rotation, shooter="player"):
		"""Throws an Experience Bottle projectile along player camera rotation."""
		yaw, pitch = camera_rotation
		# Slight upward loft angle (+0.05 radians)
		eff_pitch = pitch + 0.05
		cos_p = math.cos(eff_pitch)
		dir_x = math.cos(yaw) * cos_p
		dir_y = math.sin(eff_pitch)
		dir_z = math.sin(yaw) * cos_p

		# Start at eye level + forward offset
		start_x = player_pos[0] + dir_x * 0.35
		start_y = player_pos[1] + dir_y * 0.35
		start_z = player_pos[2] + dir_z * 0.35

		speed = 24.0  # Throwing velocity ~24 m/s
		velocity = [
			dir_x * speed,
			dir_y * speed,
			dir_z * speed
		]

		bottle = ExperienceBottleEntity((start_x, start_y, start_z), velocity, shooter=shooter)
		self.bottles.append(bottle)
		return bottle

	def update(self, dt, item_drop_manager=None, mob_manager=None):
		i = 0
		while i < len(self.bottles):
			bottle = self.bottles[i]
			bottle.update(dt, self.world, item_drop_manager=item_drop_manager, mob_manager=mob_manager)
			if bottle.despawn and not bottle.trail_particles:
				self.bottles.pop(i)
			else:
				i += 1

	def _init_gl(self):
		if self.initialized:
			return
		try:
			vs = pyglet.graphics.shader.Shader(EXP_VERT_SHADER, 'vertex')
			fs = pyglet.graphics.shader.Shader(EXP_FRAG_SHADER, 'fragment')
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
		if not self.bottles:
			return

		self._init_gl()
		if not self.initialized or not self.shader_program:
			return

		vertex_data = []

		def add_cube(cx, cy, cz, rx, ry, rz, cr, cg, cb, ca=1.0):
			faces = [
				(cx-rx, cy-ry, cz+rz), (cx+rx, cy-ry, cz+rz), (cx+rx, cy+ry, cz+rz),
				(cx-rx, cy-ry, cz+rz), (cx+rx, cy+ry, cz+rz), (cx-rx, cy+ry, cz+rz),
				(cx+rx, cy-ry, cz-rz), (cx-rx, cy-ry, cz-rz), (cx-rx, cy+ry, cz-rz),
				(cx+rx, cy-ry, cz-rz), (cx-rx, cy+ry, cz-rz), (cx+rx, cy+ry, cz-rz),
				(cx+rx, cy-ry, cz+rz), (cx+rx, cy-ry, cz-rz), (cx+rx, cy+ry, cz-rz),
				(cx+rx, cy-ry, cz+rz), (cx+rx, cy+ry, cz-rz), (cx+rx, cy+ry, cz+rz),
				(cx-rx, cy-ry, cz-rz), (cx-rx, cy-ry, cz+rz), (cx-rx, cy+ry, cz+rz),
				(cx-rx, cy-ry, cz-rz), (cx-rx, cy+ry, cz+rz), (cx-rx, cy+ry, cz-rz),
				(cx-rx, cy+ry, cz+rz), (cx+rx, cy+ry, cz+rz), (cx+rx, cy+ry, cz-rz),
				(cx-rx, cy+ry, cz+rz), (cx+rx, cy+ry, cz-rz), (cx-rx, cy+ry, cz-rz),
				(cx-rx, cy-ry, cz-rz), (cx+rx, cy-ry, cz-rz), (cx+rx, cy-ry, cz+rz),
				(cx-rx, cy-ry, cz-rz), (cx+rx, cy-ry, cz+rz), (cx-rx, cy-ry, cz+rz),
			]
			for vx, vy, vz in faces:
				vertex_data.extend([vx, vy, vz, cr, cg, cb, ca])

		for bottle in self.bottles:
			if not bottle.despawn:
				bx, by, bz = bottle.position
				# Render 3D Bottle: Lower Body (Glass/XP Liquid) + Neck + Cork
				# Liquid body (lime/yellow glowing glass)
				add_cube(bx, by, bz, 0.10, 0.12, 0.10, 0.40, 0.95, 0.20, 0.95)
				# Glowing liquid core
				add_cube(bx, by - 0.02, bz, 0.07, 0.07, 0.07, 0.90, 1.00, 0.25, 1.0)
				# Neck (glass)
				add_cube(bx, by + 0.14, bz, 0.05, 0.04, 0.05, 0.70, 0.90, 0.60, 0.95)
				# Cork (brown)
				add_cube(bx, by + 0.19, bz, 0.04, 0.02, 0.04, 0.60, 0.35, 0.15, 1.0)

			# Render sparkly trail & impact particles
			for px, py, pz, life, color in bottle.trail_particles:
				alpha = min(1.0, max(0.0, life / 0.6))
				pr = 0.035 * (life / 0.6)
				cr, cg, cb, _ = color
				add_cube(px, py, pz, pr, pr, pr, cr, cg, cb, alpha)

		if not vertex_data:
			return

		num_verts = len(vertex_data) // 7
		c_data = (ctypes.c_float * len(vertex_data))(*vertex_data)

		gl.glEnable(gl.GL_BLEND)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glDepthMask(gl.GL_TRUE)

		self.shader_program.use()
		if hasattr(camera, 'mvp_matrix'):
			gl.glUniformMatrix4fv(
				self.shader_program['matrix'].location,
				1, gl.GL_FALSE,
				(ctypes.c_float * 16)(*camera.mvp_matrix)
			)

		gl.glBindVertexArray(self.vao)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(vertex_data) * ctypes.sizeof(ctypes.c_float), c_data, gl.GL_DYNAMIC_DRAW)

		gl.glDrawArrays(gl.GL_TRIANGLES, 0, num_verts)

		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
		gl.glBindVertexArray(0)
		self.shader_program.stop()
		gl.glDisable(gl.GL_BLEND)
