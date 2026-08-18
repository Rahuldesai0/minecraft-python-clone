import ctypes
import math
import pyglet.gl as gl

CHUNK_WIDTH = 16
CHUNK_HEIGHT = 256
CHUNK_LENGTH = 16
SECTION_SIZE = 16
NUM_SECTIONS = 16

class ChunkSection:
	def __init__(self, chunk, y_sec):
		self.chunk = chunk
		self.world = chunk.world
		self.y_sec = y_sec

		self.vao = None
		self.vertex_position_vbo = None
		self.tex_coord_vbo = None
		self.shading_values_vbo = None
		self.ibo = None

		self.opaque_indices_length = 0
		self.translucent_indices_length = 0

	def upload_mesh_bytes(self, op_pos, op_tex, op_shd, op_idx, tr_pos, tr_tex, tr_shd, tr_idx):
		pos_bytes = op_pos + tr_pos
		if not pos_bytes:
			self.delete()
			return

		if self.vao is None:
			if hasattr(self.world, 'free_chunk_pool') and self.world.free_chunk_pool:
				self.vao, self.vertex_position_vbo, self.tex_coord_vbo, self.shading_values_vbo, self.ibo = self.world.free_chunk_pool.pop()
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
		
		gl.glBindVertexArray(self.vao)

		# Upload Position VBO
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.vertex_position_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(pos_bytes), (gl.GLchar * len(pos_bytes)).from_buffer_copy(pos_bytes), gl.GL_STATIC_DRAW)
		gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(0)

		# Upload TexCoord VBO
		tex_bytes = op_tex + tr_tex
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.tex_coord_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(tex_bytes), (gl.GLchar * len(tex_bytes)).from_buffer_copy(tex_bytes), gl.GL_STATIC_DRAW)
		gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(1)

		# Upload Shading VBO
		shd_bytes = op_shd + tr_shd
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.shading_values_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(shd_bytes), (gl.GLchar * len(shd_bytes)).from_buffer_copy(shd_bytes), gl.GL_STATIC_DRAW)
		gl.glVertexAttribPointer(2, 1, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
		gl.glEnableVertexAttribArray(2)

		# Upload Index Buffer (IBO)
		idx_bytes = op_idx + tr_idx
		gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, self.ibo)
		gl.glBufferData(gl.GL_ELEMENT_ARRAY_BUFFER, len(idx_bytes), (gl.GLchar * len(idx_bytes)).from_buffer_copy(idx_bytes), gl.GL_STATIC_DRAW)

		self.opaque_indices_length = len(op_idx) // 4
		self.translucent_indices_length = len(tr_idx) // 4

	def draw_opaque(self, bound_vao=None):
		if not self.opaque_indices_length or self.vao is None:
			return bound_vao
		if bound_vao != self.vao.value:
			gl.glBindVertexArray(self.vao)
			bound_vao = self.vao.value
		gl.glDrawElements(gl.GL_TRIANGLES, self.opaque_indices_length, gl.GL_UNSIGNED_INT, None)
		return bound_vao

	def draw_translucent(self, bound_vao=None):
		if not self.translucent_indices_length or self.vao is None:
			return bound_vao
		if bound_vao != self.vao.value:
			gl.glBindVertexArray(self.vao)
			bound_vao = self.vao.value
		gl.glDrawElements(gl.GL_TRIANGLES, self.translucent_indices_length, gl.GL_UNSIGNED_INT, ctypes.c_void_p(self.opaque_indices_length * 4))
		return bound_vao

	def delete(self):
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
			self.opaque_indices_length = 0
			self.translucent_indices_length = 0


class Chunk:
	def __init__(self, world, chunk_position, blocks=None, block_states=None):
		self.world = world
		self.chunk_position = chunk_position

		self.position = (
			self.chunk_position[0] * CHUNK_WIDTH,
			self.chunk_position[1] * CHUNK_HEIGHT,
			self.chunk_position[2] * CHUNK_LENGTH)

		self.sections = {}
		self.block_states = dict(block_states) if block_states else {}
		self.active_opaque_sections = []
		self.active_translucent_sections = []
		self.had_missing_neighbors = False

		target_size = CHUNK_WIDTH * CHUNK_HEIGHT * CHUNK_LENGTH  # 65536

		# Store terrain blocks as a flat 1D bytearray (65536 bytes)
		if blocks is not None:
			if isinstance(blocks, (bytes, bytearray)):
				# Handle case where raw chunk data includes |STATE_DATA|
				if b"|STATE_DATA|" in blocks:
					parts = blocks.split(b"|STATE_DATA|", 1)
					block_bytes = parts[0]
					state_bytes = parts[1]
					if state_bytes:
						import json, block_state
						try:
							st_dict = json.loads(state_bytes.decode('utf-8'))
							for key_str, s_data in st_dict.items():
								lx, ly, lz = map(int, key_str.split(','))
								self.block_states[(lx, ly, lz)] = block_state.BlockState.from_dict(s_data)
						except Exception:
							pass
				else:
					block_bytes = blocks

				if len(block_bytes) >= target_size:
					self.blocks = bytearray(block_bytes[:target_size])
				else:
					self.blocks = bytearray(target_size)
					self.blocks[:len(block_bytes)] = block_bytes
			elif isinstance(blocks, list):
				b = bytearray(target_size)
				idx = 0
				for x in range(CHUNK_WIDTH):
					col_x = blocks[x]
					for y in range(CHUNK_HEIGHT):
						col_y = col_x[y]
						for z in range(CHUNK_LENGTH):
							b[idx] = col_y[z]
							idx += 1
				self.blocks = b
			else:
				self.blocks = bytearray(target_size)
		else:
			self.blocks = bytearray(target_size)

	def get_block_number(self, x, y, z):
		if 0 <= x < 16 and 0 <= y < 256 and 0 <= z < 16:
			return self.blocks[x * 4096 + y * 16 + z]
		return 0

	def set_block_number(self, x, y, z, val):
		if 0 <= x < 16 and 0 <= y < 256 and 0 <= z < 16:
			self.blocks[x * 4096 + y * 16 + z] = val
			if val == 0 and (x, y, z) in self.block_states:
				del self.block_states[(x, y, z)]

	def get_block_state(self, x, y, z):
		if 0 <= x < 16 and 0 <= y < 256 and 0 <= z < 16:
			return self.block_states.get((x, y, z))
		return None

	def set_block_state(self, x, y, z, state):
		if 0 <= x < 16 and 0 <= y < 256 and 0 <= z < 16:
			if state is None:
				self.blocks[x * 4096 + y * 16 + z] = 0
				if (x, y, z) in self.block_states:
					del self.block_states[(x, y, z)]
			else:
				self.blocks[x * 4096 + y * 16 + z] = state.block_id
				self.block_states[(x, y, z)] = state

	def _update_active_sections(self):
		self.active_opaque_sections = [sec for sec in self.sections.values() if sec.opaque_indices_length > 0]
		self.active_translucent_sections = [sec for sec in self.sections.values() if sec.translucent_indices_length > 0]

	def send_section_mesh_to_gpu(self, section_y, op_pos, op_tex, op_shd, op_idx, tr_pos, tr_tex, tr_shd, tr_idx):
		if section_y not in self.sections:
			self.sections[section_y] = ChunkSection(self, section_y)
		sec = self.sections[section_y]
		sec.upload_mesh_bytes(op_pos, op_tex, op_shd, op_idx, tr_pos, tr_tex, tr_shd, tr_idx)
		if not sec.opaque_indices_length and not sec.translucent_indices_length:
			del self.sections[section_y]
		self._update_active_sections()

	def draw_opaque(self, bound_vao=None):
		for sec in self.active_opaque_sections:
			bound_vao = sec.draw_opaque(bound_vao)
		return bound_vao

	def draw_translucent(self, bound_vao=None):
		for sec in self.active_translucent_sections:
			bound_vao = sec.draw_translucent(bound_vao)
		return bound_vao

	def draw(self, bound_vao=None):
		bound_vao = self.draw_opaque(bound_vao)
		bound_vao = self.draw_translucent(bound_vao)
		return bound_vao

	def delete(self):
		for sec in list(self.sections.values()):
			sec.delete()
		self.sections.clear()
