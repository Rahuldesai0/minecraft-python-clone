import math
import random
import ctypes
import array
import pyglet
import pyglet.gl as gl
import gui as gui_module

class DroppedItem:
	def __init__(self, block_id, count, position, velocity=None):
		self.block_id = block_id
		self.count = count
		self.position = list(position)
		if velocity:
			self.velocity = list(velocity)
		else:
			self.velocity = [random.uniform(-0.8, 0.8), 2.2, random.uniform(-0.8, 0.8)]
		
		self.age = 0.0
		self.rotation = random.uniform(0, 360)
		self.grounded = False
		self.pickup_delay = 1.2  # 1.2s delay before dropped item can be picked up!

	def update(self, dt, world, player_pos):
		self.age += dt
		if self.pickup_delay > 0:
			self.pickup_delay -= dt

		# Continuous smooth 360-degree rotation around vertical Y-axis
		self.rotation = (self.rotation + 120.0 * dt) % 360.0

		# Gravity & Ground Collision Physics
		if not self.grounded:
			self.velocity[1] -= 16.0 * dt

			nx = self.position[0] + self.velocity[0] * dt
			ny = self.position[1] + self.velocity[1] * dt
			nz = self.position[2] + self.velocity[2] * dt

			bx = int(round(nx))
			by = int(math.floor(ny - 0.15))
			bz = int(round(nz))

			if world.get_block_number((bx, by, bz)) != 0:
				self.velocity = [0.0, 0.0, 0.0]
				self.grounded = True
				self.position[1] = by + 1.25
			else:
				self.position[0] = nx
				self.position[1] = ny
				self.position[2] = nz

		# Magnet attraction toward player when pickup delay is finished
		px, py, pz = player_pos
		dx = px - self.position[0]
		dy = (py - 0.8) - self.position[1]
		dz = pz - self.position[2]
		dist = math.sqrt(dx * dx + dy * dy + dz * dz)

		if self.pickup_delay <= 0 and dist < 2.5:
			speed = 7.0 * (1.0 - dist / 2.5) + 2.5
			self.position[0] += (dx / dist) * speed * dt
			self.position[1] += (dy / dist) * speed * dt
			self.position[2] += (dz / dist) * speed * dt

class ItemDropManager:
	def __init__(self, world):
		self.world = world
		self.drops = []

		# 3D Mini-cube template for Block Drops (scale 0.18)
		s = 0.18
		self.raw_cube = [
			# Front (z = +s)
			[(-s, -s,  s), ( s, -s,  s), ( s,  s,  s), (-s,  s,  s)],
			# Back (z = -s)
			[( s, -s, -s), (-s, -s, -s), (-s,  s, -s), ( s,  s, -s)],
			# Top (y = +s)
			[(-s,  s,  s), ( s,  s,  s), ( s,  s, -s), (-s,  s, -s)],
			# Bottom (y = -s)
			[(-s, -s, -s), ( s, -s, -s), ( s, -s,  s), (-s, -s,  s)],
			# Right (x = +s)
			[( s, -s,  s), ( s, -s, -s), ( s,  s, -s), ( s,  s,  s)],
			# Left (x = -s)
			[(-s, -s, -s), (-s, -s,  s), (-s,  s,  s), (-s,  s, -s)],
		]

		self.cube_shading = [
			[0.9, 0.9, 0.9, 0.9],  # Front
			[0.7, 0.7, 0.7, 0.7],  # Back
			[1.0, 1.0, 1.0, 1.0],  # Top
			[0.5, 0.5, 0.5, 0.5],  # Bottom
			[0.8, 0.8, 0.8, 0.8],  # Right
			[0.8, 0.8, 0.8, 0.8],  # Left
		]

		# Flat 2D item card template for tool drops (scale 0.22)
		sf = 0.22
		self.raw_flat_sprite = [
			# Front face (+z)
			[(-sf, -sf, 0.01), ( sf, -sf, 0.01), ( sf,  sf, 0.01), (-sf,  sf, 0.01)],
			# Back face (-z)
			[( sf, -sf, -0.01), (-sf, -sf, -0.01), (-sf,  sf, -0.01), ( sf,  sf, -0.01)],
		]

		self.flat_uv_front = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
		self.flat_uv_back = [[1.0, 0.0], [0.0, 0.0], [0.0, 1.0], [1.0, 1.0]]

		# GPU Buffers
		self.vao = None
		self.vbo_pos = None
		self.vbo_tex = None
		self.vbo_shd = None

	def spawn_drop(self, block_id, count, position, velocity=None):
		if block_id == 0 or count <= 0:
			return
		drop = DroppedItem(block_id, count, position, velocity)
		self.drops.append(drop)
		self.merge_nearby_drops()

	def merge_nearby_drops(self):
		"""Merge nearby drops of the same block_id within 1.5 blocks."""
		i = 0
		while i < len(self.drops):
			d1 = self.drops[i]
			j = i + 1
			while j < len(self.drops):
				d2 = self.drops[j]
				max_stack = gui_module.get_max_stack_size(d1.block_id)
				if d1.block_id == d2.block_id and d1.count < max_stack:
					dx = d1.position[0] - d2.position[0]
					dy = d1.position[1] - d2.position[1]
					dz = d1.position[2] - d2.position[2]
					if dx * dx + dy * dy + dz * dz < 2.25:
						addable = min(d2.count, max_stack - d1.count)
						d1.count += addable
						d2.count -= addable
						if d2.count <= 0:
							self.drops.pop(j)
							continue
				j += 1
			i += 1

	def update(self, dt, player_pos, gui):
		px, py, pz = player_pos

		i = 0
		while i < len(self.drops):
			drop = self.drops[i]
			drop.update(dt, self.world, player_pos)

			# Pickup check when player is within 0.8 blocks and pickup delay is finished
			dx = px - drop.position[0]
			dy = (py - 0.8) - drop.position[1]
			dz = pz - drop.position[2]
			dist = math.sqrt(dx * dx + dy * dy + dz * dz)

			if drop.pickup_delay <= 0 and dist < 0.8:
				if gui.add_item(drop.block_id, drop.count):
					self.drops.pop(i)
					continue

			# Remove ancient drops after 300s
			if drop.age > 300.0:
				self.drops.pop(i)
				continue

			i += 1

	def draw(self, shader, gui=None):
		"""Render 3D mini-block items & flat 2D item card sprites in the overworld using 3D world shader & VAO."""
		if not self.drops:
			return

		pos_data = []
		tex_data = []
		shd_data = []

		face_map = [4, 5, 2, 3, 0, 1]

		for drop in self.drops:
			x, y, z = drop.position
			bobbing = 0.08 * math.sin(drop.age * 4.0)
			y_pos = y + bobbing

			rad = math.radians(drop.rotation)
			cos_r = math.cos(rad)
			sin_r = math.sin(rad)

			b_num = drop.block_id

			if 0 < b_num < len(self.world.block_types) and self.world.block_types[b_num] is not None:
				b_type = self.world.block_types[b_num]
				if b_num in (43, 45, 47, 49):
					# 2D Item Sprite Card for Doors & Trapdoors
					tex_name = "items/door_wood" if b_num == 43 else ("items/door_iron" if b_num == 45 else ("trapdoor" if b_num == 47 else "iron_trapdoor"))
					layer = float(self.world.texture_manager.textures.index(tex_name)) if tex_name in self.world.texture_manager.textures else 0.0
					uv_maps = [self.flat_uv_front, self.flat_uv_back]
					for q_i, face_verts in enumerate(self.raw_flat_sprite):
						v_corners = []
						for vx, vy, vz in face_verts:
							rx = vx * cos_r - vz * sin_r + x
							ry = vy + y_pos
							rz = vx * sin_r + vz * cos_r + z
							v_corners.append((rx, ry, rz))

						uv_set = uv_maps[q_i]
						t_corners = [(uv_set[k][0], uv_set[k][1], layer) for k in range(4)]
						for idx in (0, 1, 2, 0, 2, 3):
							pos_data.extend(v_corners[idx])
							tex_data.extend(t_corners[idx])
							shd_data.append(0.9)
				elif getattr(b_type, 'model', None) is not None and not getattr(b_type, 'is_cube', True):
					# Actual 3D Model Geometry for Slabs, Stairs, Fences, Walls, Panes (scale 0.35)
					scale = 0.35
					for f_idx, face_verts in enumerate(b_type.model.vertex_positions):
						raw_t = b_type.tex_coords[f_idx] if f_idx < len(b_type.tex_coords) else b_type.tex_coords[0]
						t_corners = [
							(raw_t[0], raw_t[1], raw_t[2]),
							(raw_t[3], raw_t[4], raw_t[5]),
							(raw_t[6], raw_t[7], raw_t[8]),
							(raw_t[9], raw_t[10], raw_t[11])
						]
						v_corners = []
						for v_i in range(4):
							vx = face_verts[v_i * 3 + 0] * scale
							vy = face_verts[v_i * 3 + 1] * scale
							vz = face_verts[v_i * 3 + 2] * scale
							rx = vx * cos_r - vz * sin_r + x
							ry = vy + y_pos
							rz = vx * sin_r + vz * cos_r + z
							v_corners.append((rx, ry, rz))

						for idx in (0, 1, 2, 0, 2, 3):
							pos_data.extend(v_corners[idx])
							tex_data.extend(t_corners[idx])
							shd_data.append(0.9)
				else:
					# 3D Mini Cube for Standard Block Items
					for face_i, f_idx in enumerate(face_map):
						raw_t = b_type.tex_coords[f_idx] if f_idx < len(b_type.tex_coords) else b_type.tex_coords[0]
						t_corners = [
							(raw_t[0], raw_t[1], raw_t[2]),
							(raw_t[3], raw_t[4], raw_t[5]),
							(raw_t[6], raw_t[7], raw_t[8]),
							(raw_t[9], raw_t[10], raw_t[11])
						]
						s_corners = self.cube_shading[face_i]

						v_corners = []
						for vx, vy, vz in self.raw_cube[face_i]:
							rx = vx * cos_r - vz * sin_r + x
							ry = vy + y_pos
							rz = vx * sin_r + vz * cos_r + z
							v_corners.append((rx, ry, rz))

						for idx in (0, 1, 2, 0, 2, 3):
							pos_data.extend(v_corners[idx])
							tex_data.extend(t_corners[idx])
							shd_data.append(s_corners[idx])
			else:
				# 2. 2D Item Sprite Card for Tool Items
				if b_num in gui_module.BLOCK_INFO:
					tex_name = gui_module.BLOCK_INFO[b_num][1]
					layer = float(self.world.texture_manager.textures.index(tex_name)) if tex_name in self.world.texture_manager.textures else 0.0
				else:
					layer = 0.0

				uv_maps = [self.flat_uv_front, self.flat_uv_back]

				for q_i, face_verts in enumerate(self.raw_flat_sprite):
					v_corners = []
					for vx, vy, vz in face_verts:
						rx = vx * cos_r - vz * sin_r + x
						ry = vy + y_pos
						rz = vx * sin_r + vz * cos_r + z
						v_corners.append((rx, ry, rz))

					uv_set = uv_maps[q_i]
					t_corners = [
						(uv_set[k][0], uv_set[k][1], layer)
						for k in range(4)
					]

					# Render 2 triangles per quad face (0, 1, 2) and (0, 2, 3)
					for idx in (0, 1, 2, 0, 2, 3):
						pos_data.extend(v_corners[idx])
						tex_data.extend(t_corners[idx])
						shd_data.append(1.0)

		if pos_data:
			shader.use()
			gl.glActiveTexture(gl.GL_TEXTURE0)
			gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
			if not hasattr(self, 'sampler_loc'):
				self.sampler_loc = shader.find_uniform(b"texture_array_sampler")
			if self.sampler_loc != -1:
				gl.glUniform1i(self.sampler_loc, 0)

			if self.vao is None:
				self.vao = gl.GLuint(0)
				gl.glGenVertexArrays(1, self.vao)

				self.vbo_pos = gl.GLuint(0)
				gl.glGenBuffers(1, self.vbo_pos)

				self.vbo_tex = gl.GLuint(0)
				gl.glGenBuffers(1, self.vbo_tex)

				self.vbo_shd = gl.GLuint(0)
				gl.glGenBuffers(1, self.vbo_shd)

			gl.glBindVertexArray(self.vao)

			# Fast direct Ctypes Buffer conversion
			c_pos = (gl.GLfloat * len(pos_data))(*pos_data)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos)
			gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_pos), c_pos, gl.GL_STREAM_DRAW)
			gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
			gl.glEnableVertexAttribArray(0)

			c_tex = (gl.GLfloat * len(tex_data))(*tex_data)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tex)
			gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_tex), c_tex, gl.GL_STREAM_DRAW)
			gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
			gl.glEnableVertexAttribArray(1)

			c_shd = (gl.GLfloat * len(shd_data))(*shd_data)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_shd)
			gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_shd), c_shd, gl.GL_STREAM_DRAW)
			gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
			gl.glEnableVertexAttribArray(2)

			# Disable culling so spinning items & double-sided 2D cards render cleanly
			gl.glDisable(gl.GL_CULL_FACE)
			gl.glEnable(gl.GL_DEPTH_TEST)
			gl.glDepthMask(gl.GL_TRUE)

			num_vertices = len(pos_data) // 3
			gl.glDrawArrays(gl.GL_TRIANGLES, 0, num_vertices)

			gl.glEnable(gl.GL_CULL_FACE)
			gl.glBindVertexArray(0)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
