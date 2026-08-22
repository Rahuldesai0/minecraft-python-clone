"""
End Crystal Entity & Manager (Minecraft Java Edition)
-----------------------------------------------------
Implements:
1. 3D rotating glass crystal with pulsating glowing core
2. Continuous healing beam and health restoration to Ender Dragon
3. Explosion upon damage (immune: Bedrock, Obsidian, spawn platform, pillars)
4. Dynamic OpenGL rendering for crystal cubes & healing energy beams
"""

import math
import random
import ctypes
import pyglet
import pyglet.gl as gl

CRYSTAL_VERT_SHADER = """
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

CRYSTAL_FRAG_SHADER = """
#version 330 core
in vec4 v_color;
out vec4 fragColor;

void main() {
    fragColor = v_color;
}
"""


class EndCrystalEntity:
	"""Represents an active End Crystal sitting atop an Obsidian pillar."""
	def __init__(self, position, crystal_id=0):
		self.position = list(position) # [x, y, z]
		self.crystal_id = crystal_id
		self.health = 1
		self.is_dead = False
		self.rotation = 0.0
		self.inner_rotation = 0.0
		self.bob_timer = random.uniform(0.0, math.tau)
		self.heal_timer = 0.0
		self.is_healing_dragon = False
		self.beam_target = None
		self.beam_alpha = 1.0

	def take_damage(self, damage, world=None, mob_manager=None, dragon=None, camera=None, gui=None, tnt_manager=None, item_drop_manager=None):
		"""Damage destroys the crystal and causes a powerful explosion (power 6.0, 1.5x TNT)."""
		if self.is_dead:
			return
		self.health = 0
		self.is_dead = True

		cx, cy, cz = self.position

		# If healing the dragon when destroyed, deal 10 damage to the Dragon
		if self.is_healing_dragon and dragon and not getattr(dragon, "is_dead", False):
			dragon.take_damage(10, attacker_pos=self.position)

		# Trigger power 6.0 explosion using the canonical Minecraft explosion engine
		if world:
			try:
				import explosion
				explosion.create_explosion(
					world=world,
					position=(cx, cy, cz),
					power=6.0,
					source_entity=self,
					tnt_manager=tnt_manager,
					mob_manager=mob_manager,
					camera=camera,
					gui=gui,
					item_drop_manager=item_drop_manager
				)
			except Exception:
				pass

	def update(self, dt, dragon=None):
		if self.is_dead:
			return

		# Rotation and floating bobbing animations
		self.rotation = (self.rotation + dt * 1.8) % math.tau
		self.inner_rotation = (self.inner_rotation - dt * 2.4) % math.tau
		self.bob_timer = (self.bob_timer + dt * 3.0) % math.tau

		# Dragon healing beam logic
		if dragon and not dragon.is_dead and dragon.health < dragon.max_health:
			self.is_healing_dragon = True
			self.beam_target = (dragon.position[0], dragon.position[1] + 1.0, dragon.position[2])
			self.heal_timer += dt
			# Heal dragon +1 HP every 0.5s
			if self.heal_timer >= 0.5:
				self.heal_timer = 0.0
				dragon.heal(1)
		else:
			self.is_healing_dragon = False
			self.beam_target = None


class EndCrystalManager:
	"""Manages all End Crystals, healing beams, and rendering in the End dimension."""
	def __init__(self, world):
		self.world = world
		self.crystals = []
		self.shader_program = None
		self.initialized = False
		self.vao = None
		self.vbo = None

	def initialize_crystals_for_pillars(self, pillar_defs):
		"""Spawns 10 End Crystals on the obsidian pillars."""
		self.crystals.clear()
		for p in pillar_defs:
			crystal = EndCrystalEntity(p['crystal_pos'], crystal_id=p['index'])
			self.crystals.append(crystal)

	def update(self, dt, dragon=None, mob_manager=None, item_drop_manager=None):
		for crystal in self.crystals:
			crystal.update(dt, dragon=dragon)

	def check_attack_hit(self, ray_origin, ray_dir, max_dist=6.5, damage=1, dragon=None, mob_manager=None, camera=None, gui=None, tnt_manager=None, item_drop_manager=None):
		"""Checks if a player click / arrow ray intersects any End Crystal hitbox."""
		ox, oy, oz = ray_origin
		dx, dy, dz = ray_dir

		closest_crystal = None
		closest_dist = max_dist

		for crystal in self.crystals:
			if crystal.is_dead:
				continue
			cx, cy, cz = crystal.position
			# Generous End Crystal Hitbox: [-1.0, -0.6, -1.0] to [1.0, 1.8, 1.0]
			min_x, max_x = cx - 1.0, cx + 1.0
			min_y, max_y = cy - 0.6, cy + 1.8
			min_z, max_z = cz - 1.0, cz + 1.0

			steps = int(max_dist / 0.05)
			for step in range(1, steps + 1):
				dist = step * 0.05
				rx = ox + dx * dist
				ry = oy + dy * dist
				rz = oz + dz * dist

				if min_x <= rx <= max_x and min_y <= ry <= max_y and min_z <= rz <= max_z:
					if dist < closest_dist:
						closest_dist = dist
						closest_crystal = crystal
					break

		if closest_crystal:
			closest_crystal.take_damage(
				damage,
				world=self.world,
				mob_manager=mob_manager or getattr(self.world, "mob_manager", None),
				dragon=dragon or getattr(self.world, "ender_dragon", None),
				camera=camera,
				gui=gui,
				tnt_manager=tnt_manager or getattr(self.world, "tnt_manager", None),
				item_drop_manager=item_drop_manager or getattr(self.world, "item_drop_manager", None)
			)
			return True
		return False

	def _init_gl(self):
		if self.initialized:
			return
		try:
			vs = pyglet.graphics.shader.Shader(CRYSTAL_VERT_SHADER, 'vertex')
			fs = pyglet.graphics.shader.Shader(CRYSTAL_FRAG_SHADER, 'fragment')
			self.shader_program = pyglet.graphics.shader.ShaderProgram(vs, fs)

			self.vao = gl.GLuint()
			gl.glGenVertexArrays(1, ctypes.byref(self.vao))
			self.vbo = gl.GLuint()
			gl.glGenBuffers(1, ctypes.byref(self.vbo))

			gl.glBindVertexArray(self.vao)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo)

			# Position: location 0 (3 floats)
			gl.glEnableVertexAttribArray(0)
			gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 7 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(0))

			# Color: location 1 (4 floats)
			gl.glEnableVertexAttribArray(1)
			gl.glVertexAttribPointer(1, 4, gl.GL_FLOAT, gl.GL_FALSE, 7 * ctypes.sizeof(ctypes.c_float), ctypes.c_void_p(3 * ctypes.sizeof(ctypes.c_float)))

			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
			gl.glBindVertexArray(0)
			self.initialized = True
		except Exception:
			pass

	def draw(self, camera):
		if not self.crystals:
			return

		self._init_gl()
		if not self.initialized or not self.shader_program:
			return

		vertex_data = []

		def add_cube_rotated(cx, cy, cz, r, yaw, pitch, cr, cg, cb, ca):
			cos_y, sin_y = math.cos(yaw), math.sin(yaw)
			cos_p, sin_p = math.cos(pitch), math.sin(pitch)

			def rot_pt(x, y, z):
				# Pitch rotation
				y1 = y * cos_p - z * sin_p
				z1 = y * sin_p + z * cos_p
				# Yaw rotation
				x2 = x * cos_y + z1 * sin_y
				z2 = -x * sin_y + z1 * cos_y
				return cx + x2, cy + y1, cz + z2

			corners = [
				rot_pt(-r, -r, -r), rot_pt(r, -r, -r), rot_pt(r, r, -r), rot_pt(-r, r, -r),
				rot_pt(-r, -r, r),  rot_pt(r, -r, r),  rot_pt(r, r, r),  rot_pt(-r, r, r),
			]

			quads = [
				(0, 1, 2, 3), (5, 4, 7, 6), (4, 0, 3, 7),
				(1, 5, 6, 2), (3, 2, 6, 7), (4, 5, 1, 0)
			]

			for q in quads:
				for idx in (q[0], q[1], q[2], q[0], q[2], q[3]):
					vx, vy, vz = corners[idx]
					vertex_data.extend([vx, vy, vz, cr, cg, cb, ca])

		def add_beam(p1, p2, width, cr, cg, cb, ca):
			x1, y1, z1 = p1
			x2, y2, z2 = p2
			dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
			length = max(0.1, math.sqrt(dx * dx + dz * dz))

			# Perpendicular unit vectors
			nx = -dz / length * width
			nz = dx / length * width

			# 2 crossed ribbon quads
			# Quad 1 (Horizontal)
			vertex_data.extend([x1 + nx, y1, z1 + nz, cr, cg, cb, ca])
			vertex_data.extend([x1 - nx, y1, z1 - nz, cr, cg, cb, ca])
			vertex_data.extend([x2 - nx, y2, z2 - nz, cr, cg, cb, ca])
			vertex_data.extend([x1 + nx, y1, z1 + nz, cr, cg, cb, ca])
			vertex_data.extend([x2 - nx, y2, z2 - nz, cr, cg, cb, ca])
			vertex_data.extend([x2 + nx, y2, z2 + nz, cr, cg, cb, ca])

			# Quad 2 (Vertical)
			vertex_data.extend([x1, y1 + width, z1, cr, cg, cb, ca])
			vertex_data.extend([x1, y1 - width, z1, cr, cg, cb, ca])
			vertex_data.extend([x2, y2 - width, z2, cr, cg, cb, ca])
			vertex_data.extend([x1, y1 + width, z1, cr, cg, cb, ca])
			vertex_data.extend([x2, y2 - width, z2, cr, cg, cb, ca])
			vertex_data.extend([x2, y2 + width, z2, cr, cg, cb, ca])

		for crystal in self.crystals:
			if crystal.is_dead:
				continue
			cx, cy, cz = crystal.position
			bob_y = cy + math.sin(crystal.bob_timer) * 0.15

			# 1. Base Bedrock/Obsidian Stand (-0.4 to 0.0)
			add_cube_rotated(cx, cy - 0.2, cz, 0.45, 0.0, 0.0, 0.15, 0.15, 0.18, 1.0)

			# 2. Outer Rotating Glass Cube (radius 0.45, semi-transparent teal/white)
			add_cube_rotated(cx, bob_y + 0.35, cz, 0.45, crystal.rotation, 0.35, 0.85, 0.95, 1.0, 0.45)

			# 3. Inner Counter-Rotating Glass Cube (radius 0.32, semi-transparent purple)
			add_cube_rotated(cx, bob_y + 0.35, cz, 0.32, crystal.inner_rotation, -0.45, 0.75, 0.25, 0.95, 0.55)

			# 4. Glowing Magenta Crystal Core (radius 0.18, solid glowing purple/red)
			add_cube_rotated(cx, bob_y + 0.35, cz, 0.18, crystal.rotation * 1.5, 0.0, 1.00, 0.20, 0.65, 0.95)

			# 5. Healing Beam connecting to Ender Dragon
			if crystal.is_healing_dragon and crystal.beam_target:
				add_beam((cx, bob_y + 0.35, cz), crystal.beam_target, 0.18, 0.85, 0.25, 1.0, 0.85)
				add_beam((cx, bob_y + 0.35, cz), crystal.beam_target, 0.08, 1.00, 0.85, 1.0, 0.95)

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
