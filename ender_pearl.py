"""
Minecraft Java Edition Ender Pearl Projectile, Chunk Generation & Teleportation System
---------------------------------------------------------------------------------------
Implements:
1. Authentic Ender Pearl physics & ballistic trajectory:
   - Initial throwing speed ~30.0 m/s (1.5 blocks/tick) along player view vector.
   - Gravity: 15.0 m/s^2 (0.03 blocks/tick^2).
   - Air drag: 0.99 per tick.
2. Dynamic Chunk Generation & Meshing along trajectory:
   - Seamlessly generates and meshes the pearl's own chunk as it travels across
     the world, even when flying far outside the player's render distance.
3. Teleportation & Damage:
   - On solid block impact, immediately teleports the player to the landing coordinates.
   - Inflicts 5 fall/magic damage to the player in Survival mode (0 in Creative mode).
   - Emits purple and cyan portal teleport particles.
4. Batch OpenGL 3.3 3D Renderer for flying pearls and portal particle trails.
"""

import math
import random
import time
import ctypes
import pyglet
import pyglet.gl as gl
import block_state

PEARL_VERT_SHADER = """
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

PEARL_FRAG_SHADER = """
#version 330
in vec4 interpolated_color;
out vec4 fragment_colour;

void main(void) {
	if (interpolated_color.a < 0.05) discard;
	fragment_colour = interpolated_color;
}
"""


class EnderPearlEntity:
	"""Minecraft Java Edition Ender Pearl Projectile Entity."""
	def __init__(self, position, velocity, shooter="player"):
		self.position = list(position)
		self.velocity = list(velocity)
		self.shooter = shooter
		self.age = 0.0
		self.max_age = 20.0  # Max flight duration
		self.despawn = False
		self.trail_particles = [] # [(x, y, z, life, color), ...]
		self.last_chunk = None

	def update(self, dt, world, camera=None, gui=None, mob_manager=None):
		if self.despawn:
			# Update remaining trail particles
			alive_p = []
			for p in self.trail_particles:
				p[3] -= dt
				p[1] += dt * 0.2
				if p[3] > 0.0:
					alive_p.append(p)
			self.trail_particles = alive_p
			return

		dt_ticks = dt * 20.0
		self.age += dt

		if self.age >= self.max_age:
			self.despawn = True
			return

		# Gravity (0.03 blocks/tick^2 = 12.0 m/s^2)
		self.velocity[1] -= 15.0 * dt

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
			prev_px, prev_py, prev_pz = self.position[0], self.position[1], self.position[2]
			self.position[0] += step_x
			self.position[1] += step_y
			self.position[2] += step_z

			px, py, pz = self.position

			# 1. Dynamic Single-Chunk Loading & Meshing along path
			# Ensure the pearl's own chunk is generated and meshed even outside render distance!
			cx = int(round(px)) >> 4
			cz = int(round(pz)) >> 4
			cur_chunk = (cx, cz)

			if cur_chunk != self.last_chunk:
				self.last_chunk = cur_chunk
				if world and hasattr(world, "chunks"):
					cpos = (cx, 0, cz)
					if cpos not in world.chunks:
						world.chunks[cpos] = world.generate_chunk(cx, cz)
						world.queue_chunk_sections_for_meshing(cx, cz)

			# 2. Trail Portal Particles
			if random.random() < 0.80:
				p_col = random.choice([
					(0.10, 0.70, 0.60, 0.95),  # Dark Teal
					(0.70, 0.15, 0.95, 0.95),  # Magenta
					(0.20, 0.90, 0.80, 0.95),  # Bright Cyan
					(0.50, 0.05, 0.75, 0.95)   # Purple
				])
				self.trail_particles.append([
					px + random.uniform(-0.1, 0.1),
					py + random.uniform(-0.1, 0.1),
					pz + random.uniform(-0.1, 0.1),
					0.8,
					p_col
				])

			# 3. Solid Block Collision & Teleportation
			bx = int(round(px))
			by = int(round(py))
			bz = int(round(pz))

			if world:
				b_num = world.get_block_number((bx, by, bz))
				# Non-solid passable blocks (Air, Waters, Lavas, Fire, Flowers, Ferns, End Portal)
				if b_num != 0 and b_num not in block_state.PASSABLE_BLOCKS:
					# Solid block impact!
					# Determine impact face normal from previous position
					prev_bx = int(round(prev_px))
					prev_by = int(round(prev_py))
					prev_bz = int(round(prev_pz))

					norm_x = prev_bx - bx
					norm_y = prev_by - by
					norm_z = prev_bz - bz

					# If prev and curr are in the same block, determine normal from velocity direction
					if norm_x == 0 and norm_y == 0 and norm_z == 0:
						abs_vx, abs_vy, abs_vz = abs(step_x), abs(step_y), abs(step_z)
						if abs_vy >= abs_vx and abs_vy >= abs_vz:
							norm_y = 1 if step_y < 0 else -1
						elif abs_vx >= abs_vz:
							norm_x = -1 if step_x > 0 else 1
						else:
							norm_z = -1 if step_z > 0 else 1

					hit_normal = (norm_x, norm_y, norm_z)
					self._on_impact(world, camera, gui, (px, py, pz), (bx, by, bz), hit_normal, (prev_px, prev_py, prev_pz))
					return

				# Void bottom boundary impact
				if py <= -30.0:
					self.despawn = True
					return

		# Update particles
		alive_p = []
		for p in self.trail_particles:
			p[3] -= dt
			p[1] += dt * 0.2
			if p[3] > 0.0:
				alive_p.append(p)
		self.trail_particles = alive_p

	def _on_impact(self, world, camera, gui, hit_pos, block_pos, hit_normal, prev_pos):
		"""Handles landing impact, player teleportation, damage, and portal particles without clipping into blocks."""
		self.despawn = True
		px, py, pz = hit_pos
		bx, by, bz = block_pos
		nx, ny, nz = hit_normal
		prev_x, prev_y, prev_z = prev_pos

		eye_off = getattr(camera, 'eye_offset', 1.62) if camera else 1.62

		# Generate ordered candidate teleport positions outside the solid block
		candidates = []

		# Candidate 1: Landing on top face (+Y normal)
		if ny > 0:
			# Stand on top of the solid block
			candidates.append([bx + 0.0, by + 0.5 + eye_off, bz + 0.0])
			candidates.append([px, by + 0.5 + eye_off, pz])

		# Candidate 2: Hitting a side face (nx != 0 or nz != 0)
		elif nx != 0 or nz != 0:
			# Place player in the adjacent air block outside the wall
			adj_x = bx + nx
			adj_z = bz + nz

			# Check if there is solid ground below the adjacent block to stand on
			if world:
				for cy in range(by + 1, by - 6, -1):
					floor_b = world.get_block_number((adj_x, cy, adj_z))
					if floor_b != 0 and floor_b not in block_state.PASSABLE_BLOCKS:
						# Check if 2 vertical blocks above the floor are passable
						above1 = world.get_block_number((adj_x, cy + 1, adj_z))
						above2 = world.get_block_number((adj_x, cy + 2, adj_z))
						if above1 in block_state.PASSABLE_BLOCKS and above2 in block_state.PASSABLE_BLOCKS:
							candidates.append([adj_x + 0.0, cy + 0.5 + eye_off, adj_z + 0.0])
							break

			# Position outside the wall at impact height
			candidates.append([adj_x + 0.0, py, adj_z + 0.0])
			candidates.append([bx + nx * 0.75, py, bz + nz * 0.75])
			candidates.append([prev_x, prev_y, prev_z])

		# Candidate 3: Hitting a ceiling (-Y normal)
		elif ny < 0:
			candidates.append([prev_x, by - 0.5 - eye_off - 0.1, prev_z])
			candidates.append([bx + 0.0, by - 0.5 - eye_off - 0.1, bz + 0.0])

		# Fallback candidates
		candidates.append([prev_x, prev_y, prev_z])
		candidates.append([bx + nx * 0.8, by + max(0.0, ny * 0.5) + eye_off, bz + nz * 0.8])

		# Select the first candidate position where player body is completely unobstructed
		safe_pos = None
		if camera and hasattr(camera, 'check_collision'):
			for cand in candidates:
				if camera.check_collision(world, cand):
					safe_pos = cand
					break

			# If still stuck, perform a 3D radial search around hit normal to find the nearest clear air space
			if safe_pos is None:
				for d_dist in (0.8, 1.0, 1.2):
					for dx in (0, nx, -nx):
						for dz in (0, nz, -nz):
							for dy in (0, 1, -1, 2):
								test_pos = [bx + dx * d_dist, by + dy * 0.5 + eye_off, bz + dz * d_dist]
								if camera.check_collision(world, test_pos):
									safe_pos = test_pos
									break
							if safe_pos:
								break
						if safe_pos:
							break
					if safe_pos:
						break

		if safe_pos is None:
			safe_pos = [bx + nx * 0.8, by + max(0.0, ny * 0.5) + eye_off, bz + nz * 0.8]

		# Spawn burst of purple/cyan portal particles at landing destination
		for _ in range(25):
			p_col = random.choice([
				(0.15, 0.85, 0.75, 1.0),
				(0.85, 0.20, 0.95, 1.0),
				(0.40, 0.95, 0.85, 1.0)
			])
			self.trail_particles.append([
				safe_pos[0] + random.uniform(-0.4, 0.4),
				safe_pos[1] - eye_off + random.uniform(0.1, 1.8),
				safe_pos[2] + random.uniform(-0.4, 0.4),
				0.7,
				p_col
			])

		# Teleport Player Camera
		if camera:
			camera.position = [safe_pos[0], safe_pos[1], safe_pos[2]]
			camera.velocity_y = 0.0
			camera.fall_start_y = None

			# Inflict 5 fall/magic damage in Survival mode (0 in Creative)
			is_creative = getattr(camera, 'flying', False) or getattr(getattr(camera, 'window', None), 'flying', False)
			if not is_creative and hasattr(camera, 'take_damage'):
				camera.take_damage(5, flying=False, gui=gui, world=world)


class EnderPearlManager:
	"""Manages active Ender Pearl projectiles and batch rendering."""
	def __init__(self, world):
		self.world = world
		self.pearls = []
		self.shader_program = None
		self.initialized = False
		self.vao = None
		self.vbo = None

	def throw_pearl(self, player_pos, camera_rotation, shooter="player"):
		"""Throws an Ender Pearl projectile along player camera rotation."""
		yaw, pitch = camera_rotation
		cos_p = math.cos(pitch)
		dir_x = math.cos(yaw) * cos_p
		dir_y = math.sin(pitch)
		dir_z = math.sin(yaw) * cos_p

		# Start at eye height + slight forward offset
		start_x = player_pos[0] + dir_x * 0.3
		start_y = player_pos[1] + dir_y * 0.3
		start_z = player_pos[2] + dir_z * 0.3

		speed = 30.0  # 1.5 blocks/tick = 30.0 m/s
		velocity = [
			dir_x * speed,
			dir_y * speed,
			dir_z * speed
		]

		pearl = EnderPearlEntity((start_x, start_y, start_z), velocity, shooter=shooter)
		self.pearls.append(pearl)
		return pearl

	def update(self, dt, camera=None, gui=None, mob_manager=None):
		i = 0
		while i < len(self.pearls):
			pearl = self.pearls[i]
			pearl.update(dt, self.world, camera=camera, gui=gui, mob_manager=mob_manager)
			if pearl.despawn and not pearl.trail_particles:
				self.pearls.pop(i)
			else:
				i += 1

	def _init_gl(self):
		if self.initialized:
			return
		try:
			vs = pyglet.graphics.shader.Shader(PEARL_VERT_SHADER, 'vertex')
			fs = pyglet.graphics.shader.Shader(PEARL_FRAG_SHADER, 'fragment')
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
		if not self.pearls:
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

		for pearl in self.pearls:
			px, py, pz = pearl.position
			if not pearl.despawn:
				# 3D Ender Pearl Cube (Dark Teal shell + bright cyan core)
				add_cube(px, py, pz, 0.12, 0.08, 0.45, 0.40, 1.0)
				add_cube(px, py, pz, 0.07, 0.15, 0.85, 0.75, 1.0)

			for tx, ty, tz, life, col in pearl.trail_particles:
				alpha = max(0.0, min(1.0, life / 0.5))
				add_cube(tx, ty, tz, 0.04, col[0], col[1], col[2], alpha)

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
