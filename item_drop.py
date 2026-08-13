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
			self.velocity = [random.uniform(-1.0, 1.0), 2.5, random.uniform(-1.0, 1.0)]
		
		self.age = 0.0
		self.rotation = random.uniform(0, 360)
		self.grounded = False
		self.pickup_delay = 1.5  # 1.5s timer after dropping before item can be picked up!

	def update(self, dt, world, player_pos):
		self.age += dt
		if self.pickup_delay > 0:
			self.pickup_delay -= dt

		self.rotation = (self.rotation + 120.0 * dt) % 360.0

		# Gravity & Ground Collision Physics
		if not self.grounded:
			self.velocity[1] -= 16.0 * dt

			nx = self.position[0] + self.velocity[0] * dt
			ny = self.position[1] + self.velocity[1] * dt
			nz = self.position[2] + self.velocity[2] * dt

			bx, by, bz = int(round(nx)), int(math.floor(ny - 0.15)), int(round(nz))
			if world.get_block_number((bx, by, bz)) != 0:
				self.velocity[1] = 0.0
				self.velocity[0] *= 0.3
				self.velocity[2] *= 0.3
				self.grounded = True
				self.position[1] = by + 1.15
			else:
				self.position[0] = nx
				self.position[1] = ny
				self.position[2] = nz

		# Magnet attraction toward player within 2.5 blocks (only when pickup_delay <= 0)
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

		# Base 3D mini-cube geometry template for block drops (scale 0.16)
		s = 0.16
		self.raw_cube = [
			# Front
			(-s, -s,  s), ( s, -s,  s), ( s,  s,  s), (-s,  s,  s),
			# Back
			(-s, -s, -s), (-s,  s, -s), ( s,  s, -s), ( s, -s, -s),
			# Top
			(-s,  s, -s), (-s,  s,  s), ( s,  s,  s), ( s,  s, -s),
			# Bottom
			(-s, -s, -s), ( s, -s, -s), ( s, -s,  s), (-s, -s,  s),
			# Right
			( s, -s, -s), ( s,  s, -s), ( s,  s,  s), ( s, -s,  s),
			# Left
			(-s, -s, -s), (-s, -s,  s), (-s,  s,  s), (-s,  s, -s),
		]

		self.shading_values = [
			0.9, 0.9, 0.9, 0.9,
			0.7, 0.7, 0.7, 0.7,
			1.0, 1.0, 1.0, 1.0,
			0.5, 0.5, 0.5, 0.5,
			0.8, 0.8, 0.8, 0.8,
			0.8, 0.8, 0.8, 0.8,
		]

		# Flat 2D Item Sprite Billboard template for non-block items (scale 0.22)
		sf = 0.22
		self.raw_flat_sprite = [
			# Front face quad
			(-sf, -sf, 0), ( sf, -sf, 0), ( sf,  sf, 0), (-sf,  sf, 0),
			# Back face quad
			(-sf, -sf, 0), (-sf,  sf, 0), ( sf,  sf, 0), ( sf, -sf, 0),
		]

		self.flat_uv = [
			0.0, 0.0,  1.0, 0.0,  1.0, 1.0,  0.0, 1.0,
			0.0, 0.0,  0.0, 1.0,  1.0, 1.0,  1.0, 0.0,
		]

		self.flat_shading = [1.0] * 8

		# VAO & VBO Buffer Setup for 3D Shader Rendering
		self.vao = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.vao)
		gl.glBindVertexArray(self.vao)

		self.vbo_pos = gl.GLuint(0)
		gl.glGenBuffers(1, self.vbo_pos)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos)
		gl.glEnableVertexAttribArray(0)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)

		self.vbo_tex = gl.GLuint(0)
		gl.glGenBuffers(1, self.vbo_tex)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tex)
		gl.glEnableVertexAttribArray(1)
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)

		self.vbo_shading = gl.GLuint(0)
		gl.glGenBuffers(1, self.vbo_shading)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_shading)
		gl.glEnableVertexAttribArray(2)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)

		gl.glBindVertexArray(0)

	def spawn_drop(self, block_id, count, position, velocity=None):
		if block_id == 0 or count <= 0:
			return
		drop = DroppedItem(block_id, count, position, velocity)
		self.drops.append(drop)
		self.merge_nearby_drops()

	def merge_nearby_drops(self):
		"""Merge nearby drops of the same block_id within 1.5 blocks ('club together')."""
		i = 0
		while i < len(self.drops):
			d1 = self.drops[i]
			j = i + 1
			while j < len(self.drops):
				d2 = self.drops[j]
				if d1.block_id == d2.block_id and d1.count < 64:
					dx = d1.position[0] - d2.position[0]
					dy = d1.position[1] - d2.position[1]
					dz = d1.position[2] - d2.position[2]
					if dx * dx + dy * dy + dz * dz < 2.25:  # 1.5 blocks distance threshold
						addable = min(d2.count, 64 - d1.count)
						d1.count += addable
						d2.count -= addable
						if d2.count <= 0:
							self.drops.pop(j)
							continue
				j += 1
			i += 1

	def update(self, dt, player_pos, gui):
		self.merge_nearby_drops()

		px, py, pz = player_pos

		i = 0
		while i < len(self.drops):
			drop = self.drops[i]
			drop.update(dt, self.world, player_pos)

			# Pickup check when player is within 0.75 blocks and pickup delay is finished
			dx = px - drop.position[0]
			dy = (py - 0.8) - drop.position[1]
			dz = pz - drop.position[2]
			dist = math.sqrt(dx * dx + dy * dy + dz * dz)

			if drop.pickup_delay <= 0 and dist < 0.75:
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

		pos_data = array.array('f')
		tex_data = array.array('f')
		shd_data = array.array('f')

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
				# 1. Block Item: Render 3D mini cube with exact 6-face block textures
				for vx, vy, vz in self.raw_cube:
					rx = vx * cos_r - vz * sin_r
					rz = vx * sin_r + vz * cos_r
					pos_data.extend([rx + x, vy + y_pos, rz + z])

				b_type = self.world.block_types[b_num]
				for f_idx in face_map:
					if f_idx < len(b_type.tex_coords):
						tex_data.extend(b_type.tex_coords[f_idx])
					else:
						tex_data.extend(b_type.tex_coords[0])

				shd_data.extend(self.shading_values)
			else:
				# 2. Non-Block Tool Item (Sticks, Pickaxes, Axes, Shovels, Swords): Render flat 2D double-sided item sprite card!
				for vx, vy, vz in self.raw_flat_sprite:
					rx = vx * cos_r - vz * sin_r
					rz = vx * sin_r + vz * cos_r
					pos_data.extend([rx + x, vy + y_pos, rz + z])

				if b_num in gui_module.BLOCK_INFO:
					tex_name = gui_module.BLOCK_INFO[b_num][1]
					if tex_name in self.world.texture_manager.textures:
						layer = float(self.world.texture_manager.textures.index(tex_name))
					else:
						layer = 0.0
				else:
					layer = 0.0

				for i in range(8):
					u = self.flat_uv[i * 2]
					v = self.flat_uv[i * 2 + 1]
					tex_data.extend([u, v, layer])

				shd_data.extend(self.flat_shading)

		if pos_data:
			gl.glBindVertexArray(self.vao)

			c_pos = (gl.GLfloat * len(pos_data))(*pos_data)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_pos)
			gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_pos), c_pos, gl.GL_DYNAMIC_DRAW)

			c_tex = (gl.GLfloat * len(tex_data))(*tex_data)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_tex)
			gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_tex), c_tex, gl.GL_DYNAMIC_DRAW)

			c_shd = (gl.GLfloat * len(shd_data))(*shd_data)
			gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vbo_shading)
			gl.glBufferData(gl.GL_ARRAY_BUFFER, ctypes.sizeof(c_shd), c_shd, gl.GL_DYNAMIC_DRAW)

			num_vertices = len(pos_data) // 3
			gl.glDrawArrays(gl.GL_QUADS, 0, num_vertices)

			gl.glBindVertexArray(0)
