import ctypes
import math
import pyglet.gl as gl

CHUNK_WIDTH = 16
CHUNK_HEIGHT = 256
CHUNK_LENGTH = 16
SECTION_SIZE = 16
NUM_SECTIONS = 16

# Non-shadow-casting blocks: Air, Liquids, Foliage (Flowers, Ferns, Crops, Saplings, Bushes, Vines, Sugar Cane), Torches, Portals
NON_SHADOW_CASTING_BLOCKS = {
	0,   # Air
	9,   # Water
	10,  # Rose / Poppy / Flower
	12,  # Dead Bush
	15,  # Lava
	19,  # Under Water
	20,  # Under Lava
	33,  # Yellow Flower
	78,  # Fire
	79,  # Torch
	81,  # Crops / Wheat
	88,  # Nether Portal X
	89,  # Nether Portal Z
	94,  # Nether Wart
	156, # Oak Sapling
	183, # End Portal
	204, # Carrot Crops
	205, # Potato Crops
	206, # Pumpkin Stem
	207, # Melon Stem
	210, # Sugar Cane
	225, # Birch Sapling
	235, # Spruce Sapling
	245, # Jungle Sapling
	255, # Acacia Sapling
	265, # Dark Oak Sapling
	279, # Fern
	280, # Vines
	283, # Red Tulip
	284, # Orange Tulip
	285, # Oxeye Daisy
}

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

		needs_attrib_setup = False
		if self.vao is None:
			if hasattr(self.world, 'free_chunk_pool') and self.world.free_chunk_pool:
				self.vao, self.vertex_position_vbo, self.tex_coord_vbo, self.shading_values_vbo, self.ibo = self.world.free_chunk_pool.pop()
			else:
				needs_attrib_setup = True
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
		if needs_attrib_setup:
			gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
			gl.glEnableVertexAttribArray(0)

		# Upload TexCoord VBO
		tex_bytes = op_tex + tr_tex
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.tex_coord_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(tex_bytes), (gl.GLchar * len(tex_bytes)).from_buffer_copy(tex_bytes), gl.GL_STATIC_DRAW)
		if needs_attrib_setup:
			gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
			gl.glEnableVertexAttribArray(1)

		# Upload Shading VBO (3 floats per vertex: sky_light, block_light, face_shading)
		shd_bytes = op_shd + tr_shd
		gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.shading_values_vbo)
		gl.glBufferData(gl.GL_ARRAY_BUFFER, len(shd_bytes), (gl.GLchar * len(shd_bytes)).from_buffer_copy(shd_bytes), gl.GL_STATIC_DRAW)
		if needs_attrib_setup:
			gl.glVertexAttribPointer(2, 3, gl.GL_FLOAT, gl.GL_FALSE, 0, 0)
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
		self.center_x = self.chunk_position[0] * CHUNK_WIDTH + 8
		self.center_z = self.chunk_position[2] * CHUNK_LENGTH + 8
		self.block_states = dict(block_states) if block_states else {}
		self.active_opaque_sections = []
		self.active_translucent_sections = []
		self.had_missing_neighbors = False

		import array
		target_size = CHUNK_WIDTH * CHUNK_HEIGHT * CHUNK_LENGTH  # 65536

		# Store terrain blocks as a flat 1D uint16 array (65536 elements, values 0..65535)
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

				if len(block_bytes) >= target_size * 2:
					self.blocks = array.array('H')
					self.blocks.frombytes(block_bytes[:target_size * 2])
				elif len(block_bytes) >= target_size:
					# Legacy uint8 chunk (65536 bytes -> 65536 uint16s)
					raw_16 = bytearray(target_size * 2)
					raw_16[0::2] = block_bytes[:target_size]
					self.blocks = array.array('H')
					self.blocks.frombytes(raw_16)
				else:
					self.blocks = array.array('H', [0] * target_size)
					for i in range(min(len(block_bytes), target_size)):
						self.blocks[i] = block_bytes[i]
			elif isinstance(blocks, array.array):
				if blocks.typecode == 'H' and len(blocks) >= target_size:
					self.blocks = array.array('H', blocks[:target_size])
				elif blocks.typecode == 'B' and len(blocks) >= target_size:
					raw_16 = bytearray(target_size * 2)
					raw_16[0::2] = blocks[:target_size].tobytes()
					self.blocks = array.array('H')
					self.blocks.frombytes(raw_16)
				else:
					self.blocks = array.array('H', [0] * target_size)
					for i in range(min(len(blocks), target_size)):
						self.blocks[i] = blocks[i]
			elif isinstance(blocks, list):
				self.blocks = array.array('H', [0] * target_size)
				if blocks and isinstance(blocks[0], list):
					idx = 0
					for x in range(CHUNK_WIDTH):
						col_x = blocks[x]
						for y in range(CHUNK_HEIGHT):
							col_y = col_x[y]
							for z in range(CHUNK_LENGTH):
								self.blocks[idx] = col_y[z]
								idx += 1
				else:
					for i in range(min(len(blocks), target_size)):
						self.blocks[i] = blocks[i]
			else:
				self.blocks = array.array('H', [0] * target_size)
		else:
			self.blocks = array.array('H', [0] * target_size)
		self.column_heights = None
		self.compute_column_heights()

	def compute_column_heights(self):
		heights = bytearray(256)
		blocks = self.blocks
		max_y = 64
		for sy in range(15, 3, -1):
			s_start = sy * 16
			has_b = False
			for x in range(16):
				start_idx = x * 4096 + s_start * 16
				for z in range(16):
					if blocks[start_idx + z] not in NON_SHADOW_CASTING_BLOCKS:
						has_b = True
						break
				if has_b: break
			if has_b:
				max_y = min(255, (sy + 1) * 16)
				break

		for lx in range(16):
			base_col = lx * 4096
			for lz in range(16):
				col_start = base_col + lz
				for y in range(max_y, -1, -1):
					b = blocks[col_start + y * 16]
					if b not in NON_SHADOW_CASTING_BLOCKS:
						heights[lz * 16 + lx] = y
						break
		self.column_heights = heights

	def get_block_number(self, x, y, z):
		if 0 <= x < 16 and 0 <= y < 256 and 0 <= z < 16:
			idx = x * 4096 + y * 16 + z
			if idx < len(self.blocks):
				return self.blocks[idx]
		return 0

	def set_block_number(self, x, y, z, val):
		if 0 <= x < 16 and 0 <= y < 256 and 0 <= z < 16:
			idx = x * 4096 + y * 16 + z
			if idx < len(self.blocks):
				self.blocks[idx] = val
			if val == 0 and (x, y, z) in self.block_states:
				del self.block_states[(x, y, z)]
			if self.column_heights is not None:
				col_idx = z * 16 + x
				if val not in NON_SHADOW_CASTING_BLOCKS:
					if y > self.column_heights[col_idx]:
						self.column_heights[col_idx] = y
				elif y == self.column_heights[col_idx]:
					base_col = x * 4096 + z
					new_h = 0
					for check_y in range(y - 1, -1, -1):
						b = self.blocks[base_col + check_y * 16]
						if b not in NON_SHADOW_CASTING_BLOCKS:
							new_h = check_y
							break
					self.column_heights[col_idx] = new_h

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
