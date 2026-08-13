import ctypes
import math
import array

import pyglet.gl as gl

import subchunk

CHUNK_WIDTH = 16
CHUNK_HEIGHT = 256
CHUNK_LENGTH = 16

class Chunk:
	def __init__(self, world, chunk_position, blocks=None):
		self.world = world
		
		self.chunk_position = chunk_position

		self.position = (
			self.chunk_position[0] * CHUNK_WIDTH,
			self.chunk_position[1] * CHUNK_HEIGHT,
			self.chunk_position[2] * CHUNK_LENGTH)
		
		if blocks is not None:
			self.blocks = blocks
		else:
			self.blocks = [[[0
				for z in range(CHUNK_LENGTH)]
				for y in range(CHUNK_HEIGHT)]
				for x in range(CHUNK_WIDTH )]
		
		self.subchunks = {}

		for x in range(int(CHUNK_WIDTH / subchunk.SUBCHUNK_WIDTH)):
			for y in range(int(CHUNK_HEIGHT / subchunk.SUBCHUNK_HEIGHT)):
				for z in range(int(CHUNK_LENGTH / subchunk.SUBCHUNK_LENGTH)):
					self.subchunks[(x, y, z)] = subchunk.Subchunk(self, (x, y, z))

		# mesh variables (C-native array.array for zero-copy GPU buffer uploads)

		self.mesh_vertex_positions = array.array('f')
		self.mesh_tex_coords = array.array('f')
		self.mesh_shading_values = array.array('f')

		self.mesh_index_counter = 0
		self.mesh_indices = array.array('I')

		self.mesh_indices_length = 0
		self.opaque_indices_length = 0
		self.translucent_indices_length = 0
		self.pending_opaque_indices_length = 0
		self.pending_translucent_indices_length = 0

		self.vao = gl.GLuint(0)
		gl.glGenVertexArrays(1, self.vao)
		gl.glBindVertexArray(self.vao)

		self.vertex_position_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.vertex_position_vbo)
		self.tex_coord_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.tex_coord_vbo)
		self.shading_values_vbo = gl.GLuint(0)
		gl.glGenBuffers(1, self.shading_values_vbo)
		self.ibo = gl.GLuint(0)
		gl.glGenBuffers(1, self.ibo)
	
	def update_subchunk_meshes(self):
		for subchunk_position in self.subchunks:
			subchunk = self.subchunks[subchunk_position]
			subchunk.update_mesh()

	def update_at_position(self, position):
		x, y, z = position

		lx = int(x % subchunk.SUBCHUNK_WIDTH )
		ly = int(y % subchunk.SUBCHUNK_HEIGHT)
		lz = int(z % subchunk.SUBCHUNK_LENGTH)

		clx, cly, clz = self.world.get_local_position(position)

		sx = math.floor(clx / subchunk.SUBCHUNK_WIDTH )
		sy = math.floor(cly / subchunk.SUBCHUNK_HEIGHT)
		sz = math.floor(clz / subchunk.SUBCHUNK_LENGTH)

		self.subchunks[(sx, sy, sz)].update_mesh()

		def try_update_subchunk_mesh(subchunk_position):
			if subchunk_position in self.subchunks:
				self.subchunks[subchunk_position].update_mesh()
		
		if lx == subchunk.SUBCHUNK_WIDTH - 1: try_update_subchunk_mesh((sx + 1, sy, sz))
		if lx == 0: try_update_subchunk_mesh((sx - 1, sy, sz))

		if ly == subchunk.SUBCHUNK_HEIGHT - 1: try_update_subchunk_mesh((sx, sy + 1, sz))
		if ly == 0: try_update_subchunk_mesh((sx, sy - 1, sz))

		if lz == subchunk.SUBCHUNK_LENGTH - 1: try_update_subchunk_mesh((sx, sy, sz + 1))
		if lz == 0: try_update_subchunk_mesh((sx, sy, sz - 1))

	def update_mesh(self):
		self.mesh_vertex_positions = array.array('f')
		self.mesh_tex_coords = array.array('f')
		self.mesh_shading_values = array.array('f')

		self.mesh_index_counter = 0
		self.mesh_indices = array.array('I')
		self.pending_opaque_indices_length = 0
		self.pending_translucent_indices_length = 0

		for subchunk_position in self.subchunks:
			subchunk = self.subchunks[subchunk_position]

			self.mesh_vertex_positions.extend(subchunk.opaque_mesh_vertex_positions)
			self.mesh_tex_coords.extend(subchunk.opaque_mesh_tex_coords)
			self.mesh_shading_values.extend(subchunk.opaque_mesh_shading_values)

			for index in subchunk.opaque_mesh_indices:
				self.mesh_indices.append(index + self.mesh_index_counter)

			self.mesh_index_counter += int(len(subchunk.opaque_mesh_vertex_positions) / 3)

		self.pending_opaque_indices_length = len(self.mesh_indices)

		for subchunk_position in self.subchunks:
			subchunk = self.subchunks[subchunk_position]

			self.mesh_vertex_positions.extend(subchunk.translucent_mesh_vertex_positions)
			self.mesh_tex_coords.extend(subchunk.translucent_mesh_tex_coords)
			self.mesh_shading_values.extend(subchunk.translucent_mesh_shading_values)

			for index in subchunk.translucent_mesh_indices:
				self.mesh_indices.append(index + self.mesh_index_counter)

			self.mesh_index_counter += int(len(subchunk.translucent_mesh_vertex_positions) / 3)

		self.pending_translucent_indices_length = len(self.mesh_indices) - self.pending_opaque_indices_length

	def send_mesh_data_to_gpu(self):
		if not hasattr(self, "mesh_indices") or not len(self.mesh_indices):
			return

		if self.vao is None:
			# Check if there is a recycled VAO/VBO handle tuple in world's free pool!
			if hasattr(self.world, 'free_chunk_pool') and self.world.free_chunk_pool:
				handles = self.world.free_chunk_pool.pop()
				self.vao, self.vertex_position_vbo, self.tex_coord_vbo, self.shading_values_vbo, self.ibo = handles
				gl.glBindVertexArray(self.vao)
			else:
				self.vao = gl.GLuint(0)
				gl.glGenVertexArrays(1, self.vao)
				gl.glBindVertexArray(self.vao)

				self.vertex_position_vbo = gl.GLuint(0)
				gl.glGenBuffers(1, self.vertex_position_vbo)
				self.tex_coord_vbo = gl.GLuint(0)
				gl.glGenBuffers(1, self.tex_coord_vbo)
				self.shading_values_vbo = gl.GLuint(0)
				gl.glGenBuffers(1, self.shading_values_vbo)
				self.ibo = gl.GLuint(0)
				gl.glGenBuffers(1, self.ibo)
		else:
			gl.glBindVertexArray(self.vao)

		pos_ptr = (gl.GLfloat * len(self.mesh_vertex_positions)).from_buffer(self.mesh_vertex_positions)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vertex_position_vbo)
		gl.glBufferData(
			gl.GL_ARRAY_BUFFER,
			ctypes.sizeof(pos_ptr),
			pos_ptr,
			gl.GL_STATIC_DRAW)
		
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		tex_ptr = (gl.GLfloat * len(self.mesh_tex_coords)).from_buffer(self.mesh_tex_coords)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.tex_coord_vbo)
		gl.glBufferData(
			gl.GL_ARRAY_BUFFER,
			ctypes.sizeof(tex_ptr),
			tex_ptr,
			gl.GL_STATIC_DRAW)
		
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		shading_ptr = (gl.GLfloat * len(self.mesh_shading_values)).from_buffer(self.mesh_shading_values)
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.shading_values_vbo)
		gl.glBufferData(
			gl.GL_ARRAY_BUFFER,
			ctypes.sizeof(shading_ptr),
			shading_ptr,
			gl.GL_STATIC_DRAW)
		
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(2)

		idx_ptr = (gl.GLuint * len(self.mesh_indices)).from_buffer(self.mesh_indices)
		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ibo)
		gl.glBufferData(
			gl.GL_ELEMENT_ARRAY_BUFFER,
			ctypes.sizeof(idx_ptr),
			idx_ptr,
			gl.GL_STATIC_DRAW)
		
		del self.mesh_vertex_positions
		del self.mesh_tex_coords
		del self.mesh_shading_values

		del self.mesh_indices

		# Set draw lengths AFTER GPU buffers are fully populated and bound
		self.opaque_indices_length = getattr(self, "pending_opaque_indices_length", 0)
		self.translucent_indices_length = getattr(self, "pending_translucent_indices_length", 0)
		self.mesh_indices_length = len(idx_ptr)
	
	def delete(self):
		"""Recycle OpenGL buffers to free pool instead of invoking driver pipeline flushes!"""
		if self.vao is not None:
			if hasattr(self.world, 'free_chunk_pool'):
				self.world.free_chunk_pool.append((
					self.vao,
					self.vertex_position_vbo,
					self.tex_coord_vbo,
					self.shading_values_vbo,
					self.ibo
				))
			else:
				gl.glDeleteVertexArrays(1, self.vao)
				gl.glDeleteBuffers(1, self.vertex_position_vbo)
				gl.glDeleteBuffers(1, self.tex_coord_vbo)
				gl.glDeleteBuffers(1, self.shading_values_vbo)
				gl.glDeleteBuffers(1, self.ibo)
			self.vao = None

	def draw_opaque(self):
		if not self.opaque_indices_length:
			return

		gl.glBindVertexArray(self.vao)
		gl.glDrawElements(
			gl.GL_TRIANGLES,
			self.opaque_indices_length,
			gl.GL_UNSIGNED_INT,
			None)

	def draw_translucent(self):
		if not self.translucent_indices_length:
			return

		gl.glBindVertexArray(self.vao)
		gl.glDrawElements(
			gl.GL_TRIANGLES,
			self.translucent_indices_length,
			gl.GL_UNSIGNED_INT,
			ctypes.c_void_p(self.opaque_indices_length * 4))

	def draw(self):
		self.draw_opaque()
		self.draw_translucent()
